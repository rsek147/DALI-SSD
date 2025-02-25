import torch
import torch.nn as nn
from torchvision.models.resnet import resnet18, resnet34, resnet50, resnet101, resnet152
from torchvision.models import mobilenet_v2, mobilenet_v3_large

# Apex imports
try:
    from apex.fp16_utils import *
    from apex.parallel import DistributedDataParallel as DDP
except ImportError:
    raise ImportError("Please install APEX from https://github.com/nvidia/apex")


class ResNet(nn.Module):
    def __init__(self, backbone='resnet50'):
        super().__init__()
        if backbone == 'resnet18':
            backbone = resnet18(pretrained=True)
            self.out_channels = [256, 512, 512, 256, 256, 128]
        elif backbone == 'resnet34':
            backbone = resnet34(pretrained=True)
            self.out_channels = [256, 512, 512, 256, 256, 256]
        elif backbone == 'resnet50':
            backbone = resnet50(pretrained=True)
            self.out_channels = [1024, 512, 512, 256, 256, 256]
        elif backbone == 'resnet101':
            backbone = resnet101(pretrained=True)
            self.out_channels = [1024, 512, 512, 256, 256, 256]
        else:  # backbone == 'resnet152':
            backbone = resnet152(pretrained=True)
            self.out_channels = [1024, 512, 512, 256, 256, 256]

        self.feature_extractor = nn.Sequential(*list(backbone.children())[:7])

        conv4_block1 = self.feature_extractor[-1][0]
        conv4_block1.conv1.stride = (1, 1)
        conv4_block1.conv2.stride = (1, 1)
        conv4_block1.downsample[0].stride = (1, 1)

    def forward(self, x):
        x = self.feature_extractor(x)
        return x

class MobileNet(nn.Module):
    def __init__(self, backbone='mobilenetv2'):
        super().__init__()
        if backbone == 'mobilenetv2':
            backbone = mobilenet_v2(pretrained=True)
            cutoff = -1
            self.out_channels = [576, 1280, 512, 256, 256, 64]
        elif backbone == 'mobilenetv3':
            backbone = mobilenet_v3_large(pretrained=True)
            cutoff = -2
            self.out_channels = [672, 960, 512, 256, 256, 64]
        
        self.feature_extractor = nn.Sequential(*list(backbone.children())[:cutoff])
    
    def forward(self, x):
        x = self.feature_extractor(x)
        return x

class SSD300(nn.Module):
    def __init__(self, backbone='resnet50', classes=81):
        super().__init__()
        self.backbone = backbone

        if self.backbone in ['resnet18', 'resnet34', 'resnet50', 'resnet101', 'resnet152']:
            self.feature_extractor = ResNet(backbone=backbone)
        elif self.backbone in ['mobilenetv2', 'mobilenetv3']:
            self.feature_extractor = MobileNet(backbone=backbone)
            self.extra_branch_layer = [14] if self.backbone == 'mobilenetv2' else [13]

        self.label_num = classes + 1  # number of classes
        self._build_additional_features(self.feature_extractor.out_channels)
        self.num_defaults = [4, 6, 6, 6, 4, 4]
        self.loc = []
        self.conf = []

        for nd, oc in zip(self.num_defaults, self.feature_extractor.out_channels):
            self.loc.append(nn.Conv2d(oc, nd * 4, kernel_size=3, padding=1))
            self.conf.append(nn.Conv2d(oc, nd * self.label_num, kernel_size=3, padding=1))

        self.loc = nn.ModuleList(self.loc)
        self.conf = nn.ModuleList(self.conf)
        self._init_weights()

    def _build_additional_features(self, input_size):
        self.additional_blocks = []
        if self.backbone in ['resnet18', 'resnet34', 'resnet50', 'resnet101', 'resnet152']:
            for i, (input_size, output_size, channels) in enumerate(zip(input_size[:-1], input_size[1:], [256, 256, 128, 128, 128])):
                if i < 3:
                    layer = nn.Sequential(
                        nn.Conv2d(input_size, channels, kernel_size=1, bias=False),
                        nn.BatchNorm2d(channels),
                        nn.ReLU(inplace=True),
                        nn.Conv2d(channels, output_size, kernel_size=3, padding=1, stride=2, bias=False),
                        nn.BatchNorm2d(output_size),
                        nn.ReLU(inplace=True),
                    )
                else:
                    layer = nn.Sequential(
                        nn.Conv2d(input_size, channels, kernel_size=1, bias=False),
                        nn.BatchNorm2d(channels),
                        nn.ReLU(inplace=True),
                        nn.Conv2d(channels, output_size, kernel_size=3, bias=False),
                        nn.BatchNorm2d(output_size),
                        nn.ReLU(inplace=True),
                    )

                self.additional_blocks.append(layer)
        elif self.backbone in ['mobilenetv2', 'mobilenetv3']:
            activation = nn.ReLU6(inplace=True) if self.backbone == 'mobilenetv2' else nn.Hardswish(inplace=True)
            for i, (input_size, output_size, channels) in enumerate(zip(input_size[1:-1], input_size[2:], [256, 128, 128, 64])):
                layer = nn.Sequential(
                    nn.Conv2d(input_size, channels, kernel_size=1, bias=False),
                    nn.BatchNorm2d(channels),
                    activation,
                    nn.Conv2d(channels, output_size, kernel_size=3, padding=1, stride=2, bias=False),
                    nn.BatchNorm2d(output_size),
                    activation,
                )

                self.additional_blocks.append(layer)

        self.additional_blocks = nn.ModuleList(self.additional_blocks)

    def _init_weights(self):
        layers = [*self.additional_blocks, *self.loc, *self.conf]
        for layer in layers:
            for param in layer.parameters():
                if param.dim() > 1: nn.init.xavier_uniform_(param)

    # Shape the classifier to the view of bboxes
    def bbox_view(self, src, loc, conf):
        ret = []
        for s, l, c in zip(src, loc, conf):
            ret.append((l(s).view(s.size(0), 4, -1), c(s).view(s.size(0), self.label_num, -1)))

        locs, confs = list(zip(*ret))
        locs, confs = torch.cat(locs, 2).contiguous(), torch.cat(confs, 2).contiguous()
        return locs, confs

    def forward(self, x):
        if self.backbone in ['resnet18', 'resnet34', 'resnet50', 'resnet101', 'resnet152']:
            x = self.feature_extractor(x)
            detection_feed = [x]
        elif self.backbone in ['mobilenetv2', 'mobilenetv3']:
            detection_feed = []
            for i, module in enumerate(list(self.feature_extractor.feature_extractor[0].children())):
                if i in self.extra_branch_layer:
                    x = list(module.children())[0][:1](x)
                    detection_feed.append(x)
                    x = list(module.children())[0][1:](x)
                else:
                    x = module(x)
            detection_feed.append(x)

        for l in self.additional_blocks:
            x = l(x)
            detection_feed.append(x)

        # Feature Map 38x38x4, 19x19x6, 10x10x6, 5x5x6, 3x3x4, 1x1x4 for ResNet
        #             19x19x4, 10x10x6,   5x5x6, 3x3x6, 2x2x4, 1x1x4 for MobileNet
        locs, confs = self.bbox_view(detection_feed, self.loc, self.conf)

        # For SSD 300, shall return nbatch x 8732 x {nlabels, nlocs} results
        return locs, confs

def model(args, classes):
    ssd300 = SSD300(backbone=args.backbone, classes=classes)
    ssd300.cuda()

    if args.fp16 and not args.amp:
        ssd300 = network_to_half(ssd300)

    if args.distributed:
        ssd300 = DDP(ssd300)

    return ssd300


class Loss(nn.Module):
    """
        Implements the loss as the sum of the followings:
        1. Confidence Loss: All labels, with hard negative mining
        2. Localization Loss: Only on positive labels
        Suppose input dboxes has the shape 8732x4
    """
    def __init__(self, dboxes):
        super(Loss, self).__init__()
        self.scale_xy = 1.0/dboxes.scale_xy
        self.scale_wh = 1.0/dboxes.scale_wh

        self.sl1_loss = nn.SmoothL1Loss(reduce=False)
        self.dboxes = nn.Parameter(dboxes(order="xywh").transpose(0, 1).unsqueeze(dim = 0),
            requires_grad=False)
        # Two factor are from following links
        # http://jany.st/post/2017-11-05-single-shot-detector-ssd-from-scratch-in-tensorflow.html
        self.con_loss = nn.CrossEntropyLoss(reduce=False)

    def _loc_vec(self, loc):
        """
            Generate Location Vectors
        """
        gxy = self.scale_xy*(loc[:, :2, :] - self.dboxes[:, :2, :])/self.dboxes[:, 2:, ]
        gwh = self.scale_wh*(loc[:, 2:, :]/self.dboxes[:, 2:, :]).log()
        return torch.cat((gxy, gwh), dim=1).contiguous()

    def forward(self, ploc, plabel, gloc, glabel):
        """
            ploc, plabel: Nx4x8732, Nxlabel_numx8732
                predicted location and labels

            gloc, glabel: Nx4x8732, Nx8732
                ground truth location and labels
        """
        mask = glabel > 0
        pos_num = mask.sum(dim=1)

        vec_gd = self._loc_vec(gloc)

        # sum on four coordinates, and mask
        sl1 = self.sl1_loss(ploc, vec_gd).sum(dim=1)
        sl1 = (mask.float()*sl1).sum(dim=1)

        # hard negative mining
        con = self.con_loss(plabel, glabel)

        # postive mask will never selected
        con_neg = con.clone()
        con_neg[mask] = 0
        _, con_idx = con_neg.sort(dim=1, descending=True)
        _, con_rank = con_idx.sort(dim=1)

        # number of negative three times positive
        neg_num = torch.clamp(3*pos_num, max=mask.size(1)).unsqueeze(-1)
        neg_mask = con_rank < neg_num

        #print(con.shape, mask.shape, neg_mask.shape)
        closs = (con*(mask.float() + neg_mask.float())).sum(dim=1)

        # avoid no object detected
        total_loss = sl1 + closs
        num_mask = (pos_num > 0).float()
        pos_num = pos_num.float().clamp(min=1e-6)
        ret = (total_loss*num_mask/pos_num).mean(dim=0)
        return ret

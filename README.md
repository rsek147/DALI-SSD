# DALI-SSD

This repository is a forked from [NVIDIA/DALI](https://github.com/NVIDIA/DALI) to enable training of various SSD models.

## Setup

```bash
docker build -t dali-ssd docker
docker run --gpus all -it --name dali-ssd dali-ssd:latest
cd dali-ssd
```

## Download dataset

```bash
cd data
bash get_coco.sh
```

## Training

```bash
cd docs/examples/use_cases/pytorch/single_stage_detector
python3 -m torch.distributed.launch --nproc_per_node=4 ./main.py --data ../../../../data/coco/ \
                                                                 --epochs 100 \
                                                                 --batch-size 32 \
                                                                 --warmup 300 \
                                                                 --backbone resnet18 \
                                                                 --num-workers 8 \
                                                                 --fp16-mode static
```

## ToDo

- Backbone
  - [ ] MobileNetV2
  - [ ] MobileNetV3
  - [ ] GhostNet
- Head
  - [ ] SSD Lite
  - [ ] SSD 512
- Data Augmentation
  - [ ] Mosaic
  - [ ] Cutmix

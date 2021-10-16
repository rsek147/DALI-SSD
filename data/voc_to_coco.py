#!/usr/bin/python

# pip install lxml

import sys
import os
import json
import xml.etree.ElementTree as ET
import glob
import shutil

START_BOUNDING_BOX_ID = 1
PRE_DEFINE_CATEGORIES = None
# If necessary, pre-define category and its id
#  PRE_DEFINE_CATEGORIES = {"aeroplane": 1, "bicycle": 2, "bird": 3, "boat": 4,
#  "bottle":5, "bus": 6, "car": 7, "cat": 8, "chair": 9,
#  "cow": 10, "diningtable": 11, "dog": 12, "horse": 13,
#  "motorbike": 14, "person": 15, "pottedplant": 16,
#  "sheep": 17, "sofa": 18, "train": 19, "tvmonitor": 20}


def get(root, name):
    vars = root.findall(name)
    return vars


def get_and_check(root, name, length):
    vars = root.findall(name)
    if len(vars) == 0:
        raise ValueError("Can not find %s in %s." % (name, root.tag))
    if length > 0 and len(vars) != length:
        raise ValueError(
            "The size of %s is supposed to be %d, but is %d."
            % (name, length, len(vars))
        )
    if length == 1:
        vars = vars[0]
    return vars


def get_categories(xml_files):
    """Generate category name to id mapping from a list of xml files.
    
    Arguments:
        xml_files {list} -- A list of xml file paths.
    
    Returns:
        dict -- category name to id mapping.
    """
    classes_names = []
    for xml_file in xml_files:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        for member in root.findall("object"):
            classes_names.append(member[0].text)
    classes_names = list(set(classes_names))
    classes_names.sort()
    return {name: i for i, name in enumerate(classes_names)}


def convert(xml_files, json_file):
    json_dict = {"images": [], "type": "instances", "annotations": [], "categories": []}
    if PRE_DEFINE_CATEGORIES is not None:
        categories = PRE_DEFINE_CATEGORIES
    else:
        categories = get_categories(xml_files)
    bnd_id = START_BOUNDING_BOX_ID
    for idx, xml_file in enumerate(xml_files):
        tree = ET.parse(xml_file)
        root = tree.getroot()
        path = get(root, "path")
        if len(path) == 1:
            filename = os.path.basename(path[0].text)
        elif len(path) == 0:
            filename = get_and_check(root, "filename", 1).text
        else:
            raise ValueError("%d paths found in %s" % (len(path), xml_file))
        # The 'index' is given as img_id
        image_id = idx
        size = get_and_check(root, "size", 1)
        width = int(get_and_check(size, "width", 1).text)
        height = int(get_and_check(size, "height", 1).text)
        image = {
            "file_name": filename,
            "height": height,
            "width": width,
            "id": image_id,
        }
        json_dict["images"].append(image)
        ## Currently we do not support segmentation.
        #  segmented = get_and_check(root, 'segmented', 1).text
        #  assert segmented == '0'
        for obj in get(root, "object"):
            category = get_and_check(obj, "name", 1).text
            if category not in categories:
                new_id = len(categories)
                categories[category] = new_id
            category_id = categories[category]
            bndbox = get_and_check(obj, "bndbox", 1)
            xmin = int(float(get_and_check(bndbox, "xmin", 1).text)) - 1
            ymin = int(float(get_and_check(bndbox, "ymin", 1).text)) - 1
            xmax = int(float(get_and_check(bndbox, "xmax", 1).text))
            ymax = int(float(get_and_check(bndbox, "ymax", 1).text))
            assert xmax > xmin
            assert ymax > ymin
            o_width = abs(xmax - xmin)
            o_height = abs(ymax - ymin)
            ann = {
                "image_id": image_id,
                "category_id": category_id,
                "id": bnd_id,
                "area": o_width * o_height,
                "iscrowd": 0,
                "bbox": [xmin, ymin, o_width, o_height],
                # "ignore": 0,
                # "segmentation": [],
            }
            json_dict["annotations"].append(ann)
            bnd_id = bnd_id + 1

    for cate, cid in categories.items():
        cat = {"supercategory": "none", "id": cid, "name": cate}
        json_dict["categories"].append(cat)

    os.makedirs(os.path.dirname(json_file), exist_ok=True)
    json_fp = open(json_file, "w")
    json_str = json.dumps(json_dict, indent=4)
    json_fp.write(json_str)
    json_fp.close()


if __name__ == "__main__":
    _2007_img_dir = 'VOCdevkit/VOC2007/JPEGImages'
    _2012_img_dir = 'VOCdevkit/VOC2012/JPEGImages'
    _2007_xml_dir = 'VOCdevkit/VOC2007/Annotations'
    _2012_xml_dir = 'VOCdevkit/VOC2012/Annotations'
    trainval_2007_list = 'VOCdevkit/VOC2007/ImageSets/Main/trainval.txt'
    trainval_2012_list = 'VOCdevkit/VOC2012/ImageSets/Main/trainval.txt'
    test_2007_list = 'VOCdevkit/VOC2007/ImageSets/Main/test.txt'

    # gather xml files
    trainval_2007_xml_files = [os.path.join(_2007_xml_dir, file_id.strip() + '.xml') 
                            for file_id in open(trainval_2007_list, 'r').readlines()]
    trainval_2012_xml_files = [os.path.join(_2012_xml_dir, file_id.strip() + '.xml') 
                            for file_id in open(trainval_2012_list, 'r').readlines()]
    test_xml_files = [os.path.join(_2007_xml_dir, file_id.strip() + '.xml') 
                        for file_id in open(test_2007_list, 'r').readlines()]
    
    # copy image files
    dst_dir = 'VOCdevkit/train2017'
    os.makedirs(dst_dir, exist_ok=True)
    for file in trainval_2007_xml_files:
        src_img_file = os.path.join(_2007_img_dir, os.path.basename(file).replace('.xml', '.jpg'))
        dst_img_file = os.path.join(dst_dir, os.path.basename(src_img_file))
        shutil.copy2(src_img_file, dst_img_file)
    
    for file in trainval_2012_xml_files:
        src_img_file = os.path.join(_2012_img_dir, os.path.basename(file).replace('.xml', '.jpg'))
        dst_img_file = os.path.join(dst_dir, os.path.basename(src_img_file))
        shutil.copy2(src_img_file, dst_img_file)
    
    dst_dir = 'VOCdevkit/val2017'
    os.makedirs(dst_dir, exist_ok=True)
    for file in test_xml_files:
        src_img_file = os.path.join(_2007_img_dir, os.path.basename(file).replace('.xml', '.jpg'))
        dst_img_file = os.path.join(dst_dir, os.path.basename(src_img_file))
        shutil.copy2(src_img_file, dst_img_file)
    
    # If you want to do train/test split, you can pass a subset of xml files to convert function.
    dst_dir = 'VOCdevkit/annotations'
    os.makedirs(dst_dir, exist_ok=True)

    output_json = os.path.join(dst_dir, 'instances_train2017.json')
    print("Number of xml files: {}".format(len(trainval_2007_xml_files + trainval_2012_xml_files)))
    convert(trainval_2007_xml_files + trainval_2012_xml_files, output_json)
    print("Success: {}".format(output_json))

    output_json = os.path.join(dst_dir, 'instances_val2017.json')
    print("Number of xml files: {}".format(len(test_xml_files)))
    convert(test_xml_files, output_json)
    print("Success: {}".format(output_json))
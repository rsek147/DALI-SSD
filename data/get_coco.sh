mkdir coco
cd coco
curl -O http://images.cocodataset.org/zips/train2017.zip; unzip -q train2017.zip; rm train2017.zip
curl -O http://images.cocodataset.org/zips/val2017.zip; unzip -q val2017.zip; rm val2017.zip
curl -O http://images.cocodataset.org/annotations/annotations_trainval2017.zip; unzip -q annotations_trainval2017.zip; rm annotations_trainval2017.zip
cd ..
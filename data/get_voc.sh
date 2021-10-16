echo "Download VOC dataset..."
curl -LO http://pjreddie.com/media/files/VOCtrainval_06-Nov-2007.tar
curl -LO http://pjreddie.com/media/files/VOCtest_06-Nov-2007.tar
curl -LO http://pjreddie.com/media/files/VOCtrainval_11-May-2012.tar

echo "Extract files..."
tar -xf VOCtrainval_06-Nov-2007.tar
tar -xf VOCtest_06-Nov-2007.tar
tar -xf VOCtrainval_11-May-2012.tar

echo "Convert label files"
python3 voc_to_coco.py

echo "Remove files"
rm VOCtrainval_06-Nov-2007.tar
rm VOCtest_06-Nov-2007.tar
rm VOCtrainval_11-May-2012.tar
rm -rf VOCdevkit/VOC2007
rm -rf VOCdevkit/VOC2012

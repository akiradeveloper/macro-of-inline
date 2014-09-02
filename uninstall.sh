FILES=installed_files.txt
python setup.py install --record $FILES
cat $FILES | xargs rm -rvf
rm $FILES

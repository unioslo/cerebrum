#!/bin/sh

# After running "build.py --all", and db2pdf, this script can be used
# to publish the resulting docs at Source Forge.

DEST_DIR=shell.sourceforge.net:/home/groups/c/ce/cerebrum/htdocs/doc
SRC_DIR=,build

if [ ! -d $SRC_DIR ]; then
    echo "$SRC_DIR does not exist"
    exit 1
fi

# TODO: build.py should probably generate a cleaner tree that we may
# simply copy without these patterns.

rsync -avzL --delete --delete-excluded --exclude 'CVS/' --include  "*/" --include '*.css' --include '*.html' --include '*.png' --exclude "*" ${SRC_DIR}/ ${DEST_DIR}/html/
rsync -avz ${SRC_DIR}/book.pdf $DEST_DIR

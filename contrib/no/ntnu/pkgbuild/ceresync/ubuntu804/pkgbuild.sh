#!/bin/bash
if [ -z "$1" -o -z "$2" -o -z "$3" ]; then
	echo "usage: $0 DIRECTORY VERSION REVISION"
        exit 1
fi
DIR=$1
VERSION=$2-$3
NAME=ceresync
BUILDPATH=$DIR/cerebrum-ntnu-$VERSION
PKGPATH="`dirname $0`"
[ -d "$PKGPATH/debian" ] || PKGPATH="$BUILDPATH/contrib/no/ntnu/pkgbuild/ceresync/ubuntu804"

#echo "Checking build environment sanity"
#broken=false
#for i in python-zsi; do
#    echo -n "Checking for package $i: "
#    if dpkg-query -W -f='${Status}' $i 2>&1| grep -q "install ok installed"; then
#        echo "OK"
#    else
#        broken=true
#        echo "MISSING"
#    fi
#done
#if [ "$broken" == true ]; then
#    echo "Build dependencies are not met - quitting"
#    exit 1
#fi

echo "Building DEB packages for Ubuntu 8.04 of $NAME version $VERSION"
pushd $BUILDPATH > /dev/null 2>&1

echo "Adding symlink to debian build infrastructure at base of source"
ln -s $PKGPATH/debian debian

echo "Adding default changelog entry"
dch -b --newversion $VERSION "updated to $VERSION"

echo "Building package in $BUILDPATH"
dpkg-buildpackage -rfakeroot
popd > /dev/null 2>&1

echo "Finished build of $NAME. You might run  cd $BUILDPATH; ubuntu-mirror-add"
echo ""
find $DIR -name \*.deb

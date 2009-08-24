#!/bin/bash
PKGPATH="contrib/no/ntnu/pkgbuild/ceresync/ubuntu804"
DEBPATH="$PKGPATH/debian/"
if [ -z "$1" -o -z "$2" -o -z "$3" ]; then
	echo "usage: $0 DIRECTORY VERSION REVISION"
        exit 1
fi
DIR=$1
VER=$2
REV=$3
VERSION=$VER-$REV
BUILDDIR=$DIR/cerebrum-ntnu-$VERSION

echo "Checking build environment sanity"
broken=false
for i in python-cjson python-zsi python-cheetah openjdk-6-jdk; do
    echo -n "Checking for package $i: "
    dpkg-query -W -f='${Status}' $i 2>&1| grep -q "install ok installed"
    status=$?
    if [ "$status" = "0" ]; then
        echo "OK"
    else
        broken=true
        echo "MISSING"
    fi
done
if [ "$broken" == true ]; then
    echo "Build dependencies are not met.."
    exit 1
fi


echo "Building DEB packages for Ubuntu 8.04 of ceresync version $VER-$REL"
pushd $BUILDDIR > /dev/null 2>&1

echo "Adding symlink to debian build infrastructure at base of source"
ln -s $PKGPATH/debian debian

echo "Adding default changelog entry..."
dch -b --newversion $VERSION "updated to $VERSION"

echo "Building new package..."
dpkg-buildpackage -rfakeroot

popd > /dev/null 2>&1

echo "Finished build of ceresync:"
echo ""
find $DIR -name \*.deb
echo ""
echo "You might want to enter $BUILDDIR and run ubuntu-mirror-add..."



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

echo "Installing build-dep and ceresync..."
sudo apt-get build-dep ceresync || exit 1

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



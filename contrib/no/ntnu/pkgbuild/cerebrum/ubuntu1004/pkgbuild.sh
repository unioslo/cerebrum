#!/bin/bash
if [ -z "$1" -o -z "$2" -o -z "$3" ]; then
	echo "usage: $0 DIRECTORY VERSION REVISION"
        exit 1
fi
DIR=$1
VERSION=$2-$3
LOCAL=$4
NAME=cerebrum-ntnu
BUILDPATH=$DIR/cerebrum-ntnu-$VERSION

# Determine which debian directory to use
PKGPATH="`dirname $0`"
if [ -n "$LOCAL" -a -d "$PKGPATH/debian" ]; then
    [ ${PKGPATH:0:1} != "/" ] && PKGPATH="`pwd`/$PKGPATH"
else
    PKGPATH="contrib/no/ntnu/pkgbuild/cerebrum/ubuntu1004"
fi

echo "Building DEB packages for Ubuntu 10.04 of $NAME version $VERSION"
pushd $BUILDPATH > /dev/null 2>&1

echo "Adding symlink to debian build infrastructure at base of source"
ln -s $PKGPATH/debian debian

echo "Adding default changelog entry"
dch -b --newversion $VERSION "updated to $VERSION"

echo "Building new package"
dpkg-buildpackage -rfakeroot
popd > /dev/null 2>&1

echo "Finished build of $NAME."
echo "You might run the following:"
echo "# cd $BUILDPATH"
echo "# ubuntu-mirror-add lucid /web/virtualhosts/bas-pakker.itea.ntnu.no/htdocs/test/ubuntu"
echo ""
find $DIR -name \*.deb

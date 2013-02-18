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
if [ -n "$LOCAL" -a -d $PKGPATH/debian ]; then
    [ ${PKGPATH:0:1} != "/" ] && PKGPATH="`pwd`/$PKGPATH"
else
    PKGPATH="contrib/no/ntnu/pkgbuild/cerebrum/ubuntu804"
fi

echo "Building DEB packages for Ubuntu 8.04 of $NAME version $VERSION"
pushd $BUILDPATH > /dev/null 2>&1

echo "Adding symlink to debian build infrastructure at base of source"
echo "Source: $PKGPATH/debian"
echo "Target: `pwd`/debian"
ln -s $PKGPATH/debian debian

echo "Adding default changelog file"
cat > debian/changelog << EOF
$NAME (0.0-0) UNRELEASED; urgency=low

  * Initial release.

 -- Christian Haugan Toldnes <chritol@hackney.itea.ntnu.no>  Tue, 07 Sep 2010 11:40:40 +0200
EOF
dch --newversion $VERSION "updated to $VERSION"

[[ -f ~/.devscripts ]] && source ~/.devscripts
echo "Building new package"
dpkg-buildpackage -rfakeroot ${DEBSIGN_KEYID+"-k$DEBSIGN_KEYID"}
popd > /dev/null 2>&1

echo "Finished build of $NAME."
echo "You might run the following:"
echo "# cd $BUILDPATH"
echo "# ubuntu-mirror-add hardy /web/virtualhosts/bas-pakker.itea.ntnu.no/htdocs/test/ubuntu"
echo ""
find $DIR -name \*.deb

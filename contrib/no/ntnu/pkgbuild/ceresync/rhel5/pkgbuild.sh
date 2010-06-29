#!/bin/bash

BUILDPATH="/usr/src/redhat/"
SPECDEST="$BUILDPATH/SPECS"
SRCDEST="$BUILDPATH/SOURCES"
if [ -z "$1" -o -z "$2" -o -z "$3" ]; then
	echo "usage: $0 DIRECTORY VERSION REVISION"
        exit 1
fi
DIR=$1
VER=$2
REV=$3
CEREBRUM=cerebrum-ntnu-$VER-$REV
PKGPATH="$DIR/$CEREBRUM/contrib/no/ntnu/pkgbuild/ceresync/rhel5"
if [ -n "$4" ]; then
	PKGPATH="$4/ceresync/rhel5"
fi
SPECPATH="$PKGPATH/specs"
SRCPATH="$PKGPATH/src"
echo "Building RPM packages for RHEL 5 of ceresync version $VER-$REV"
pushd $DIR > /dev/null 2>&1
echo "Starting build in `pwd`"

echo "Creating tarball $CEREBRUM.tar.gz"
tar --exclude=.svn -czf $CEREBRUM.tar.gz $CEREBRUM

echo "Modifying SPEC to use correct version and release"
sed "s|VERSION|$VER|g;s|RELEASE|$REV|g" < $SPECPATH/ceresync-common.spec > $SPECDEST/ceresync-common.spec

echo "Copying sources and patches to correct location"
cp $CEREBRUM/$SRCPATH/* $SRCDEST/
cp $CEREBRUM.tar.gz $SRCDEST/

echo "Building packages in $BUILDPATH"
rpmbuild -ba $SPECDEST/ceresync-common.spec
if [ "$?" != 0 ]; then
	echo "Build failed"
	exit 1
fi
popd >/dev/null 2>&1

echo "Cleaning up $TEMPDIR"
rm -rf $TEMPDIR



echo "Finished build of $NAME."
echo "You might run the following:"
echo "# redhat-mirror-add $BUILDPATH/*/ceresync*-$VER-$REV.*.rpm /web/virtualhosts/bas-pakker.itea.ntnu.no/htdocs/test/rhel/5"

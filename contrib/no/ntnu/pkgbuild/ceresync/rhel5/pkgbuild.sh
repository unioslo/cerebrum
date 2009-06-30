#!/bin/bash

PKGPATH="contrib/no/ntnu/pkgbuild/ceresync/rhel5"
SPECPATH="$PKGPATH/specs/"
SRCPATH="$PKGPATH/src/"
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
	
echo "Building RPM packages for RHEL 5 of ceresync version $VER-$REL"
pushd $DIR > /dev/null 2>&1

echo "Creating tarball cerebrum-ntnu-$VER-$REV.tar.gz"
tar --exclude=.svn -czf cerebrum-ntnu-$VER-$REV.tar.gz cerebrum-ntnu-$VER-$REV

echo "Modifying SPEC to use correct version and release"
sed "s|VERSION|$VER|g" < cerebrum-ntnu-$VER-$REV/$SPECPATH/ceresync-common.spec |\
sed "s|RELEASE|$REV|g" > $SPECDEST/ceresync-common.spec

echo "Copying sources and patches to correct location"
cp cerebrum-ntnu-$VER-$REV/$SRCPATH/* $SRCDEST/
cp cerebrum-ntnu-$VER-$REV.tar.gz $SRCDEST/

echo "Building packages"
rpmbuild -ba $SPECDEST/ceresync-common.spec
popd >/dev/null 2>&1

echo "Cleaning up $TEMPDIR"
rm -rf $TEMPDIR

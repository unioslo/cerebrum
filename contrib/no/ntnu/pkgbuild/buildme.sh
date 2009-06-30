#!/bin/bash
#
# Main script for building server and client packages on various platforms
#

if [ -z "$1" -o -z "$2" -o -z "$3" ]; then
        echo "Build cerebrum or ceresync packages for various platforms."
        echo "usage: $0 PLATFORM TARGET TAG-VERSION [REVISION]"
        echo "Ex: $0 ubuntu804 ceresync 1.10"
        echo "Ex: $0 rhel5 cerebrum 1.09 10882"
        echo "Ex: $0 ubuntu804 ceresync trunk"
        exit 1
elif [ -z "$4" ]; then
        VER=$3
        REV="latest"
else
        VER=$3
        REV=$4
fi
PLATFORM=$1
TARGET=$2
TRUNK=0
# Qualified quess of correctness of PLATFORM argument:
case "$PLATFORM" in
    ubuntu804)
        ;;
    rhel5)
        ;;
    *)
        echo "Unknown platform: $PLATFORM"
        exit 1
        ;;
esac

if [ "$VER" == "trunk" ]; then
   URL="https://cerebrum.svn.sourceforge.net/svnroot/cerebrum/trunk"
   echo "Setting version to 0 for trunk."
   VER=0
   TRUNK=1
else
   URL="https://cerebrum.svn.sourceforge.net/svnroot/cerebrum/tags/ntnu-prod-$VER"
fi

echo "Building $PLATFORM packages for $TARGET: $VER"
echo -n "Creating temp-dir: "
TEMPDIR="`mktemp -d /tmp/cerebuild.XXXXXXXXX`"
echo $TEMPDIR
pushd $TEMPDIR >/dev/null 2>&1
if [ "$REV" == "latest" ]; then
echo "Downloading source for: $VER, latest revision"
    svn co -q $URL
    if [ "$TRUNK" == "1" ]; then
        mv cerebrum/cerebrum trunk
        rm -rf cerebrum
    fi
    mv * cerebrum
    pushd cerebrum >/dev/null 2>&1
    REV=`svn log --limit 1 | awk '/^r[0-9]+/ {print substr($1,2); exit}'`
    popd >/dev/null 2>&1
    echo "Detected the following revision as latest for $VER: '$REV'"
else
    echo "Downloadig source for $VER-$REV"
    svn co $URL -r $REV -q
fi
mv * ../cerebrum-ntnu-$VER-$REV
popd >/dev/null 2>&1
echo "Source downloaded into $TEMPDIR/cerebrum-ntnu-$VER-$REV"

# Verify existance of platform-specific build infrastructure:
PKGSCRIPT="$TEMPDIR/cerebrum-ntnu-$VER-$REV/contrib/no/ntnu/pkgbuild/$TARGET/$PLATFORM/pkgbuild.sh"
COMMAND="$PKGSCRIPT $TEMPDIR $VER $REV"
if [ ! -f "$PKGSCRIPT" ]; then
    echo "Could not find build script for next step:"
    echo "$PKGSCRIPT"
    echo "Wanted to run command:"
    echo $COMMAND
else
    echo "Executing platform and target specific buid of $TARGET for $PLATFORM"
    exec $COMMAND
fi


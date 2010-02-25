#!/bin/bash
#
# Main script for building server and client packages on various platforms
#

#
# Dont build as root...
#
if [ "`id -u`" -eq "0" ]; then
	echo "You should never run this script as root"
	exit 1
fi

# Parse parameters
if (( $# < 3 )); then
        echo "Build cerebrum or ceresync packages for various platforms."
        echo "usage: $0 PLATFORM TARGET VERSION [REVISION]"
        echo "Ex: $0 ubuntu804 ceresync 2.0.1   #tag, last revision"
        echo "Ex: $0 rhel5 ceresync trunk 12472 #trunk, specific revision"
        echo "Ex: $0 ubuntu804 cerebrum 2.0     #branch, last revision"
        exit 1
fi
PLATFORM=$1
TARGET=$2
VER=${3:-trunk}
REV=${4:-latest}
TRUNK=0

# Qualified quess of correctness of PLATFORM argument:
case "$PLATFORM" in
    ubuntu804)
        if grep -iq 'Ubuntu 8.04' /etc/issue; then
            echo "System seems to qualify as $PLATFORM"
        else
            echo "/etc/issue did not identify this system as $PLATFORM"
            exit 1
        fi
        ;;
    rhel5)
        if grep -iq 'Red Hat Enterprise Linux Server release 5' /etc/issue; then
            echo "System seems to qualify as $PLATFORM"
        else
            echo "/etc/issue did not identify this system as $PLATFORM"
            exit 1
        fi
        ;;
    *)
        echo "Unknown platform '$PLATFORM'"
        exit 1
        ;;
esac

if [ "$VER" = "trunk" ]; then	# trunk
   URL="https://cerebrum.svn.sourceforge.net/svnroot/cerebrum/trunk/cerebrum"
   echo "Setting version to 0 for trunk"
   VER=0
else	# branch or tag
   IFS=. read major medium minor <<< "$VER"

   if [[ -n $minor ]]; then	#tag
       URL="https://cerebrum.svn.sourceforge.net/svnroot/cerebrum/tags/ntnu-prod-$VER/cerebrum"
       echo "Setting version to tag $VER"
   else	# branch
       URL="https://cerebrum.svn.sourceforge.net/svnroot/cerebrum/branches/ntnu-prod-$VER/cerebrum"
       echo "Setting version to branch $VER"
   fi
fi

TEMPDIR="`mktemp -d /tmp/cerebuild.XXXXXXXXX`"
echo "Building $PLATFORM packages for $TARGET, version $VER, using temp-dir $TEMPDIR"
pushd $TEMPDIR >/dev/null 2>&1 || exit
if [ "$REV" = "latest" ]; then
    echo "Downloading source for $VER, latest revision from $URL"
    svn co -q $URL cerebrum

    REV=`svn log cerebrum --limit 1 --quiet | awk '/^r[0-9]+/ {print substr($1,2); exit}'`
    echo "Detected revision '$REV' as latest for $VER"
    if [ -d cerebrum/cerebrum ]; then
        mv cerebrum/cerebrum cerebrum-ntnu-$VER-$REV
    else
        mv cerebrum cerebrum-ntnu-$VER-$REV
    fi
else
    echo "Downloading source for $VER-$REV from $URL"
    svn co -q -r $REV $URL cerebrum-ntnu-$VER-$REV
fi
popd >/dev/null 2>&1
echo "Source downloaded into $TEMPDIR/cerebrum-ntnu-$VER-$REV"

# Verify existance of platform-specific build infrastructure:
PKGSCRIPT="`dirname $0`/$TARGET/$PLATFORM/pkgbuild.sh"
[ -f "$PKGSCRIPT" ] || PKGSCRIPT="$TEMPDIR/cerebrum-ntnu-$VER-$REV/contrib/no/ntnu/pkgbuild/$TARGET/$PLATFORM/pkgbuild.sh"

COMMAND="$PKGSCRIPT $TEMPDIR $VER $REV"
if [ ! -x "$PKGSCRIPT" ]; then
    echo "Could not find build script for next step, wanted to execute:"
    echo $COMMAND
else
    echo "Executing platform and target specific build of $TARGET for $PLATFORM"
    exec $COMMAND
fi

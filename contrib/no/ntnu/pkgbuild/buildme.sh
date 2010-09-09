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

usage () {	# exitcode [error message]
        [ -n "$2" ] && echo -e "$2\n"
        echo "Build cerebrum or ceresync packages for various platforms."
        echo "usage: $0 <PLATFORM> <TARGET> <[OPTIONS]>"
        echo "PLATFORM in ( ubuntu1004 ubuntu804 rhel5 )"
        echo "TARGET in ( cerebrum ceresync )"
        echo "OPTIONS:"
        echo "	-t | --trunk		Build packages from trunk"
	echo "	-l | --local		Use local build scripts"
	echo "	-V | --version		Package version"
	echo "				- If X.Y.Z look for tag, if only X.Y look for branch"
	echo "	-r | --revision		SVN revision and package release"
	echo "	-h | --help		This text"
	echo ""
	echo "Redirect all output to 'tee' to make a decent buildlog:"
	echo " 2>&1 | tee /someplace/buildme.log"
	echo ""
	exit $1
}
# Keep this for possible local build:
SCRIPTPATH=`dirname $0`

# default to latest revision if not provided
REV=latest
# Default to 0 as package version if not provided
VER=0
# Parse arguments
while [ $# -gt 0 ]
do
	case "$1" in
		-h|--help)  
			usage 0
			;;
		
		-l|--local)  
			LOCAL=$SCRIPTPATH
			echo "Will use build scripts local to $LOCAL"
			;;
		
		-t|--trunk)
			echo "Will try to build packages from trunk"
			TYPE="trunk"
			;;
		
		-V|--version)
			VER=$2
			echo "Will use $VER as version"
			shift
			;;
			
		-r|--revision)
			REV=$2
			echo "Will use $REV as revision"
			shift
			;;
			
		cerebrum)
			TARGET=$1
			echo "Will use $TARGET as target"
			;;

		ceresync)
			TARGET=$1
			echo "Will use $TARGET as target"
			;;

		ubuntu1004)
			PLATFORM=$1
			if grep -iq 'Ubuntu 10.04' /etc/issue; then
			    echo "System seems to qualify as $PLATFORM"
			else
			    echo "/etc/issue did not identify this system as $PLATFORM"
			    exit 1
			fi
			;;

		ubuntu804)
			PLATFORM=$1
			if grep -iq 'Ubuntu 8.04' /etc/issue; then
			    echo "System seems to qualify as $PLATFORM"
			else
			    echo "/etc/issue did not identify this system as $PLATFORM"
			    exit 1
			fi
			;;

		rhel5)
			PLATFORM=$1
			if grep -iq 'Red Hat Enterprise Linux Server release 5' /etc/issue; then
			    echo "System seems to qualify as $PLATFORM"
			else
			    echo "/etc/issue did not identify this system as $PLATFORM"
			    exit 1
			fi
			;;

		*)
			usage 1
			;;
    	esac
    	shift
done

if [ -z "$TARGET" ]; then
	usage 1 "No target specified"
elif [ -z "$PLATFORM" ]; then
	usage 1 "No platform specified"
fi
if [ "$TYPE" == "trunk" ]; then
	URL="https://cerebrum.svn.sourceforge.net/svnroot/cerebrum/trunk"
else	# branch or tag
	if [ "$VER" == "0" ]; then 
		usage 1 "Version must be specified if not building from trunk"
	fi
   IFS=. read major medium minor <<< "$VER"

   if [[ -n $minor ]]; then
       TYPE="tag"
       URL="https://cerebrum.svn.sourceforge.net/svnroot/cerebrum/tags/ntnu-prod-$VER"
   else
       TYPE="branch"
       URL="https://cerebrum.svn.sourceforge.net/svnroot/cerebrum/branches/ntnu-prod-$VER"
   fi
fi

TEMPDIR="`mktemp -d /tmp/cerebuild.XXXXXXXXX`"
echo "Building $PLATFORM packages for $TARGET, $TYPE version $VER into $TEMPDIR"
pushd $TEMPDIR >/dev/null 2>&1 || exit
if [ "$REV" = "latest" ]; then
    echo "Downloading source for $VER, latest revision from $URL"
    svn co -q $URL svn.tmp

    REV=`svn log svn.tmp -q --limit 1 | awk '/^r[0-9]+ /{print substr($1,2); exit}'`
    echo "Detected revision '$REV' as latest for $VER"
else
    echo "Downloading source for $VER-$REV from $URL"
    svn co -q -r $REV $URL svn.tmp
fi
if [ ! -d svn.tmp ]; then
    echo "svn checkout error, terminating"
    popd >/dev/null 2>&1
    exit 1
elif [ -d svn.tmp/cerebrum ]; then
    mv svn.tmp/cerebrum cerebrum-ntnu-$VER-$REV && rm -rf svn.tmp
else	# This happens only when tagging wrong directory level
    mv svn.tmp cerebrum-ntnu-$VER-$REV
fi
popd >/dev/null 2>&1
echo "Source downloaded into $TEMPDIR/cerebrum-ntnu-$VER-$REV"

# Verify existance of platform-specific build infrastructure:
PKGSCRIPT="`dirname $0`/$TARGET/$PLATFORM/pkgbuild.sh"
if [ -n "$LOCAL" ]; then
	PKGSCRIPT="$LOCAL/$TARGET/$PLATFORM/pkgbuild.sh"
fi

COMMAND="bash $PKGSCRIPT $TEMPDIR $VER $REV $LOCAL"
if [ ! -f "$PKGSCRIPT" ]; then
    echo "Could not find build script for next step, wanted to execute:"
    echo $COMMAND
else
    echo "Executing platform and target specific build of $TARGET for $PLATFORM"
    exec $COMMAND
fi

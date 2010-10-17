#!/bin/bash
#
#
#
# Small script to tag cerebrum branches
#
#
#
BASEURL="https://cerebrum.svn.sourceforge.net/svnroot/cerebrum"
BRANCH=$1
TAG=$2
BURL="$BASEURL/branches/ntnu-prod-$BRANCH/cerebrum"
TURL="$BASEURL/tags/ntnu-prod-$TAG/"

usage() {
	echo "Usage:"
	echo "$0 <BRANCH> <TAG>"
        echo "Eks:"
	echo "$0 1.2 1.2.3"
	exit 1
}

if [ -z "$BRANCH" -o -z "$TAG" ]; then
	usage
fi

COMMAND="svn copy $BURL $TURL"

echo "Going to perform the following command:"
echo $COMMAND
echo "Hit Enter or Return to continue, Ctrl-c to abort"
read
$COMMAND


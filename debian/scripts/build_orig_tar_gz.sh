#!/bin/sh -e

DATE=`date +%Y%m%d`

trap "mv cerebrum-0.0.$DATE cerebrum " 0

if [ -f cerebrum_0.0.$DATE.orig.tar.gz ] ; then
  rm -f cerebrum_0.0.$DATE.orig.tar.gz
fi

if [ -f cerebrum/debian/changelog ] ; then
  echo rm -f cerebrum/debian/changelog
fi

DEBFULLNAME="Andreas Schuldei"
DEBEMAIL="andreas@debian.org"
export DEBEMAIL DEBFULLNAME
(cd cerebrum
    cvs -q up -dPA
    dch --newversion 0.0.$DATE "new upstream cvs checkout"
)

mv cerebrum cerebrum-0.0.$DATE
tar cfz cerebrum_0.0.$DATE.orig.tar.gz cerebrum-0.0.$DATE \
 --exclude 'CVS' \
 --exclude '.cvsignore' \
 --exclude 'debian/tmp' \
 --exclude 'debian/files' \
 --exclude 'debian/substvars' \
 --exclude 'debian/cerebrum-common/' \
 --exclude 'debian/cerebrum-server/' \
 --exclude 'debian/cerebrum-jbofh/' \
 --exclude 'debian/cerebrum-doc/'


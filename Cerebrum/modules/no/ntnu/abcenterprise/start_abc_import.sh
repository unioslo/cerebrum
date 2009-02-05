#! /bin/sh
set -x
if [ ! -z "${PYTHONPATH}" ] ; then
    export PYTHONPATH="${PYTHONPATH}:"
fi

export PYTHONPATH="${PYTHONPATH}${HOME}/cerebrum/:${HOME}/install/etc/cerebrum/:${HOME}/install/lib/python2.5/site-packages/:$HOME/install/var/www/htdocs/"

cd ${HOME}
## ./import_ABC_Enterprise.py -d -f $1
./import_ABC_Enterprise.py -f $1

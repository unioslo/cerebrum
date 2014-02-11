#!/bin/bash
#
# Setup and run tests.
#
# This could probably be generalized to something reuseable.
#
# Maybe move functions out into a separate setup_tools.sh, that we can source?
#

# Directory we're working from, i.e. the dirname of this script
#
# This directory *must* contain a 'cereconf.py' file, and *should* contain a
# 'pip-packages.txt' with pip requirements.


# Should this stuff be configurable?

# Root directory is either env ${WORKSPACE} or /tmp
root_dir=${WORKSPACE:-/tmp}
env_name=demo
test_env=${root_dir}/${env_name}  # Working directory for our env
crb_src=${root_dir}/src/cerebrum

crb_src=${HOME}/src/cerebrum

error=0

# Source the setup tools
if ! source ${crb_src}/testsuite/scripts/setup_tools.sh
then
    echo "ERROR: Unable to load script tools from '${crb_src}'" >&2
    exit 1
fi

# Directory of this script. Useful if we expect local files
this_dir=$( abs_dirname "${BASH_SOURCE[0]}" )

## Setup a new test environmnet in 
setup_test_env -r"${root_dir}" -c"${crb_src}" -e"${env_name}" -s"${this_dir}"
error+=$?

pypath=$( prepare_pypath ${test_env}/etc/cerebrum ${crb_src}/testsuite/testtools )
info "pypath ($pypath)"
error+=$?

if [ $error -ne 0 ]
then
    error "Setup failed, unable to run tests"
    exit $error
fi

info "Running tests"
PYTHONPATH=$pypath ${test_env}/bin/nosetests -vv ${crb_src}/testsuite/test_Cerebrum
error+=$?

exit $error


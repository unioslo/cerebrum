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

# Exit code
error=0

# Cerebrum source dir should exist in <root>/src/cerebrum
crb_src=${WORKSPACE}/src/cerebrum

# Source the setup tools
if ! source ${crb_src}/testsuite/scripts/setup_tools.sh
then
    echo "ERROR: Unable to load script tools from '${crb_src}'" >&2
    exit 1
fi


# 
# First test
# 

# Tests should run in <root>/basetests
env_name=basetests
env_dir=${WORKSPACE}/${name}

# Config dir
config=$( abs_dirname "${BASH_SOURCE[0]}" )

## Setup a new test environmnet in 
setup_test_env -r"${root_dir}" -c"${crb_src}" -e"${env_name}" -s"${config}"
error=$(($? + $error))

## Setup pythonpath for the tests
info "pypath ($pypath)"
export PYTHONPATH=$( prepare_pypath ${env_dir}/etc/cerebrum ${crb_src}/testsuite/testtools )
error+=$?

if [ $error -ne 0 ]
then
    error "Setup failed, unable to run tests"
    exit $error
fi

# 
# Setup OK, run tests
info "Running tests"
${test_env}/bin/nosetests -c ${config}/noseconfig.cfg  ${crb_src}/testsuite/tests/test_Cerebrum
error=$(($? + $error))

exit $error

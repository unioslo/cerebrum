#!/bin/bash
#
# Setup and run tests.
#
# This could probably be generalized to something reuseable.
#



# Should this stuff be configurable?

# Root directory is either env ${WORKSPACE} or /tmp
root_dir=${WORKSPACE:-/tmp}

# Cerebrum source dir should exist in <root>/src/cerebrum
#
# TODO: Should we check out cerebrum directly into WORKSPACE?
crb_src=${root_dir}/src/cerebrum

# If the folder ${HOME}/pypi exists, we expect to find all the relevant packages
# there, and we'll install packages in 'offline mode' (pip --no-index)
if [ -d "${HOME}/pypi" ]
then
    offline="-o ${HOME}/pypi"
fi

# These tests should run in <root>/basetests
# TODO: Should we create the virtual environment in the BUILD directory in
# stead?
env_name=tsd
env_dir=${root_dir}/${env_name}


# Exit code. We'll add in exit codes from our tests, and exit from this script
# with the result. This way, we'll be able to perform all tests, regardless of
# any one test failing, and still be able to return with an error exit if one of
# the tests failed.
#
# Note that we omit return codes from static checkers. We want Jenkins (or a
# plugin) to decide that the test job failed, based on results from these.
error=0



# Source the setup functions
if ! source ${crb_src}/testsuite/scripts/setup_tools.sh
then
    echo " ** FATAL: Unable to load script tools from '${crb_src}'" >&2
    exit 1
fi

# Config dir.
# It's the directory we're working from, i.e. the dirname of this script. This
# directory *must* contain a certain set of config files, e.g. 'cereconf.py.in'.
config=$( abs_dirname "${BASH_SOURCE[0]}" )

# 
# Setup a new test environmnet 
#
setup_test_env -r"${root_dir}" -c"${crb_src}" -e"${env_name}" -s"${config}" ${offline}
error=$(($? + $error))

# 
# Setup pythonpath for the tests
#
export PYTHONPATH=$( prepare_pypath ${env_dir}/etc/cerebrum ${crb_src}/testsuite/testtools )
error=$(($? + $error))
info "New PYTHONPATH=${PYTHONPATH}"

if [ $error -ne 0 ]
then
    error "Setup failed, unable to run tests"
    exit $error
fi

# 
# Setup OK, run tests
#
info "Running nosetests"
${env_dir}/bin/nosetests -c ${config}/noseconfig.cfg ${crb_src}/testsuite/tests/test_tsd
error=$(($? + $error))

# TODO: Where should the coverage report for Jenkins go?
ln -sf ${root_dir}/coverage.xml ${crb_src}/coverage.${env_name}.xml

exit $error

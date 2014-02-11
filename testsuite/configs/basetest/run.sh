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
crb_src=${root_dir}/src/cerebrum

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
env_dir=${root_dir}/${env_name}

# Config dir
config=$( abs_dirname "${BASH_SOURCE[0]}" )

## Setup a new test environmnet in 
setup_test_env -r"${root_dir}" -c"${crb_src}" -e"${env_name}" -s"${config}"
error=$(($? + $error))

## Setup pythonpath for the tests
export PYTHONPATH=$( prepare_pypath ${env_dir}/etc/cerebrum ${crb_src}/testsuite/testtools )
info "New PYTHONPATH=${PYTHONPATH}"
error+=$?

if [ $error -ne 0 ]
then
    error "Setup failed, unable to run tests"
    exit $error
fi

# 
# Setup OK, run tests
info "Running nosetests"
${env_dir}/bin/nosetests -c ${config}/noseconfig.cfg  ${crb_src}/testsuite/tests/test_Cerebrum
error=$(($? + $error))

# The jenkins cobertura expects to find the coverage report in the SCM path, and
# refuse to accept any other addressing.
ln -sf ${root_dir}/coverage.xml ${crb_src}/coverage.xml

# Run pep8 syntax check
info "Running static test: pep8"
pushd ${root_dir}
# The violations plugin (and sanity in general) expects the pep8 report to be
# relative to the workspace root.
${env_dir}/bin/pep8 --format=default --exclude=extlib \
                    src/cerebrum/Cerebrum src/cerebum/contrib > ${root_dir}/pep8_report.txt
popd

# Run pylint error checks
# Note that we ignore E1101(no-member), as pylint won't recognize mixins that
# aren't named '*mixin'
info "Running static test: pylint"
pushd ${root_dir} # We should already be here, but we need to be sure
# As with the pep8 static check, we need the reports to be relative to the
# workspace root
${env_dir}/bin/pylint --errors-only --output-format=parseable --ignore=extlib \
                      --disable=E1101 \
                      src/cerebrum/Cerebrum src/cerebrum/contrib > ${root_dir}/pylint.txt
popd

exit $error

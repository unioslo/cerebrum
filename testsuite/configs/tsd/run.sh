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
env_name=basetests
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

# TODO: More tests here?


# The jenkins cobertura expects to find the coverage report in the SCM path, and
# refuse to accept any other addressing.
#
# TODO: Something is odd with this. Maybe the tests should be done with
# ${crb_src} in the path, and not the installed copy. It *should* be the same...
#
# Either way, this report is useless without the Jenkins cobertura plugin.
#ln -sf ${root_dir}/coverage.xml ${crb_src}/coverage.xml


#
# Run pep8 syntax check
# 
#info "Running static test: pep8"
#pushd ${root_dir}
## The violations plugin (and sanity in general) expects the pep8 report to be
## relative to the workspace root.
#${env_dir}/bin/pep8 --format=default --exclude=extlib \
#                    src/cerebrum/Cerebrum src/cerebum/contrib > ${root_dir}/pep8_report.txt
#popd
#
## Run pylint error checks
#info "Running static test: pylint"
#pushd ${root_dir}
## As with the pep8 static check, we need the reports to be relative to the
## workspace root
##
## Also, we have to do some path manipulation to make pylint check the Cerebrum
## module in the checked out source tree, and not the installed cerebrum module.
#export PYTHONPATH=$( prepare_pypath ${env_dir}/etc/cerebrum ${crb_src} )

#pylint_init="f='${env_dir}/bin/activate_this.py';execfile(f, dict(__file__=f))"

# Note that we ignore E1101(no-member), as pylint won't recognize mixins that
# aren't named '*mixin'. Maybe we should solve this better by setting
# 'ignored-classes' in pylintrc? Not entirely sure what effect that has, but
# it's recommended to do that for 'classes with dynamically set attributes'
#${env_dir}/bin/pylint --rcfile=${config}/pylintrc --errors-only \
                      #--disable=E1101 Cerebrum > ${root_dir}/pylint.txt

# Contrib and other python files outside Cerebrum are not in our path. They need
# to be checked individually. Let's do just that, and append to the pylint
# report
#for f in $( find src/cerebrum/contrib -name *.py )
#do
    #${env_dir}/bin/pylint --rcfile=${config}/pylintrc --errors-only  \
                          #$f >> ${root_dir}/pylint.txt
#done
#popd

exit $error

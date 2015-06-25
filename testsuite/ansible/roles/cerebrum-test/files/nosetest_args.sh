#!/bin/bash
#
# Print to stderr
#
# Usage:
#   printstderr LEVEL And some message
function printstderr  # level messages
{
    local level=${1:-'LEVEL'} when=$( date '+%Y-%m-%d %H:%M:%S' )
    shift
    echo " ** ${level} ${when} **" $@ >&2
}

# Create arguments for makedb.
# This function takes a list of test folders/test files, and prepares an
# argument list with absolute file path, for use with nosetests.
# 
# Returns a string:
#   /path/to/tests/test_file [ /path/to/tests/... ]
# that can be inserted as argument(s) for nosetests
#
# Example usage:
#   args=$(build_nosetest_args  /path/to/tests  relative/path/to/test \
#                                               relative/path/to/test2 ... )
# 
function build_nosetest_args # tests-dir test...
{
    local tests_dir=$1 test_list=${@:2} old_ifs=$IFS tests

    # Check args
    if [ ! -d "${tests_dir}" ]
    then
        printstderr ERROR "No test dir '${tests_dir}'"
        return 1
    fi

    tests=( $(echo "${test_list}") )

    # Insert 'test-dir/' prefix
    tests=( ${tests[@]/#/"${tests_dir}/"} )

    # Assert that each file exists
    for testtarget in ${tests[@]}
    do
        if [ ! -e "${testtarget}" ]
        then
            printstderr ERROR "Can't find test '${testtarget}'"
            return 2
        fi
    done

    IFS=' '
    echo ${tests[*]}
    IFS="${old_ifs}"

    return 0
}

build_nosetest_args $@

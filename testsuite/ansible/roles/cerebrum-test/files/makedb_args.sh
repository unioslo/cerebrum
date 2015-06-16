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

# Create --extra-files arguments for makedb.
# This function takes a list of 'mod_*.sql' file names, and prepares
# '--extra-files' arguments with absolute file path, for use with 'makedb.py'.
# 
# Returns a string:
#   --extra-file /path/to/design/mod_file.sql [ --extra-file ... ]
# that can be inserted as argument(s) for makedb.py
#
# Example usage:
#   args=$(build_extra_file_args  /path/to/cerebrum/design  file1.sql ... )
# 
function build_extra_file_args # design-dir extra-files...
{
    local design_dir=$1 file_list=${@:2} old_ifs=$IFS extras

    # Check args
    if [ ! -d "${design_dir}" ]
    then
        printstderr ERROR "No design dir '${design_dir}'"
        return 1
    fi

    extras=( $(echo "${file_list}") )

    # Insert 'design-dir/' prefix
    extras=( ${extras[@]/#/"${design_dir}/"} )

    # Assert that each file exists
    for sqlfile in ${extras[@]}
    do
        if [ ! -r "${sqlfile}" ]
        then
            printstderr ERROR "Can't read extra-file '${sqlfile}'"
            return 2
        fi
    done

    # Insert option prefix
    extras=( ${extras[@]/#/"--extra-file "} )

    IFS=' '
    echo ${extras[*]}
    IFS="${old_ifs}"

    return 0
}

build_extra_file_args $@

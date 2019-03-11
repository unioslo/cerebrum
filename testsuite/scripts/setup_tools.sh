# This script contains tools (functions) that can be used by test scripts. It
# helps setting up the test environment
# 
# NOTE: Some of the functions within requires certain environment variables to
#       be set!
# 
# 
# 
# List of environment variables:
# 
#   CRB_PY   python binary to use
#   CRB_PIP  pip binary to use
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
# Print to stderr, with given level
#
# Usage:
#   error|warning|info  This message goes to stderr
#
function error  # messages ...
{
    printstderr ERROR $@
}
function warning  # messages ...
{
    printstderr WARNING $@
}
function info  # messages ...
{
    printstderr INFO $@
}

# Simple implode function
function join_args  # separator [ item ... ]
{
    local IFS=$1
    shift
    echo "$*"
}

function split_str  # separator string
{
    local IFS=$1
    shift
    echo $@
}

# Absolute dirname
# 
# Works like dirname, but returns absolute path
# 
# Example Usage:
#   abs_dirname         # $( pwd )
#   abs_dirname ./dir/  # $( pwd )
#   abs_dirname ./dir/subdir   # /path/to/dir
#   abs_dirname ./dir/subdir/  # /path/to/dir
#   abs_dirname ./dir/subdir/content  # /path/to/dir/subdir
function abs_dirname  # target
{
    local target=$1
    echo $( cd $( dirname "${target}" ) && pwd )
}


# Test a program return value.
# Prints error and exits script if last return value != 0.
# 
# It's a shorthand for "if ! my_func; then <print error>; exit 1; fi"
#
# Example usage:
#   my_func
#   assert_retval  my_func  Something went wrong with the thing
# 
function assert_retval # [ function_name [ messages ... ] ]
{
    local retval=$? func=${1:-'last call'} msg=${@:2}

    # Add some separation, if not empty
    if [ -n "${msg}" ]; then msg=", ${msg}"; fi

    if [ ${retval} -ne 0 ]
    then
        error "${func} returned ${retval}${msg}"
        exit 1
    fi
    return 0
}


# Reads a cereconf variable.
# If no cereconf-file is given, we attempt to import cereconf. In which case, it
# must exist in the python path.
#
# Usage:
#   get_cereconf   SOME_STR_VALUE
#   get_cereconf  'SOME_INDEXABLE_VALUE[0]'
#   get_cereconf  'SOME_DICT_VALUE["key"]'
#   get_cereconf  'SOME_DICT_VALUE.get("key","default")'
#   get_cereconf   SOME_STR_VALUE  /path/to/cereconf.py
# 
# TODO: Should we make a more versatile python script?
# 
function get_cereconf # attribute-name [ cereconf-file ]
{
    local py_bin=${CRB_PY:-python} attr_name=$1 cereconf="$2" retval out

    # Check env and args
    if [ ! -x "${py_bin}" ]
    then
        error "(get_cereconf) Invalid python executeable '${py_bin}'"
        return 1
    elif [ -z "${attr_name}" ]
    then
        error "(get_cereconf) Missing attribute argument"
        return 1
    elif [ -n "${cereconf}" -a ! -r "${cereconf}" ]
    then
        error "(get_cereconf) Can't read cereconf '${cereconf}'"
        return 1
    fi

    if [ -z "${cereconf}" ]
    then
        # No file, attempt to import
        out=$( ${py_bin} - <<SCRIPT
from cereconf import *
print ${attr_name}
SCRIPT
        )
        retval=$?  # Success?
    else
        # File is given, attempt to read
        out=$( ${py_bin} - <<SCRIPT
execfile('${cereconf}')
print ${attr_name}
SCRIPT
        )
        retval=$?  # Success?
    fi
    info "get_cereconf:'$retval' '$attr_name'='out' from '$cereconf'"

    if [ $retval -eq 0 ]
    then
        echo $out
    fi
    return $retval
}


# Create --extra-files arguments for makedb.
# This function reads a text file of 'mod_*.sql' file names, and prepares
# '--extra-files' arguments with absolute file path, for use with 'makedb.py'.
# 
# The extras file must contain one mod_*.sql file name on each line.
#
# Returns a string:
#   --extra-file /path/to/design/mod_file.sql [ --extra-file ... ]
# that can be inserted as argument(s) for makedb.py
#
# Example usage:
#   args=$(build_extra_file_args  /path/to/cerebrum/design  /path/to/extras.txt)
# 
function build_extra_file_args # design-dir extras-file
{
    local design_dir=$1 file_list=$2 old_ifs=$IFS extras

    # Check args
    if [ ! -d "${design_dir}" ]
    then
        error "(get_extra_file_args) No design dir '${design_dir}'"
        return 1
    elif [ ! -r "${file_list}" ]
    then
        error "(get_extra_file_args) Can't read file list '${file_list}'"
        return 1
    fi

    extras=( $(cat "${file_list}") )

    # Insert 'design-dir/' prefix
    extras=( ${extras[@]/#/"${design_dir}/"} )

    # Assert that each file exists
    for sqlfile in ${extras[@]}
    do
        if [ ! -r "${sqlfile}" ]
        then
            error "(get_extra_file_args) Can't read extra-file '${sqlfile}'"
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




# Installs pip-packages based on a package requirement file
# 
# The requirements file is a list of packages, and optional version
# restrictions. It's on the format that `pip freeze' outputs.
# 
# The cache_dir can contain packages from earlier installs, to save us from
# downloading them again.
# 
# If no_index is given, then the cache_dir MUST contain the neccessary tar-balls
# for installing offline. This means downloading manually (with `pip --download'
# 
# 
#
function pip_install_reqs  # req_file [ cache_dir [ no_index ]]
{
    local pip_bin=${CRB_PIP:-pip} req_file=$1 cache_dir=$2 offline=$3 opts

    # Check args
    if [ ! -r "${req_file}" ]
    then
        error "(pip_intall_reqs) Can't read requirement file '${req_file}'"
        return 1
    elif [ ! -x "${pip_bin}" ]
    then
        error "(pip_install_reqs) Invalid pip executeable '${pip_bin}'"
        return 1
    fi

    # Caching sources?
    if [ -n "${cache_dir}" ]
    then
        mkdir -p ${cache_dir}
        opts="${opts} --download-cache ${cache_dir}"
    fi

    # Offline install?
    if [ -n "${offline}" ]
    then
        opts="--no-index --find-links ${cache_dir}"
    fi

    ${pip_bin} install ${opts} --requirement ${req_file} --egg
}

# Install the Cerebrum package
# Runs setup.pu from <source_dir> with <target_dir> as prefix
# 
# Uses CRB_PY as python environment
# 
function install_crb  # source_dir target_dir
{
    local py_bin=${CRB_PY:-python} source_dir=$1 target_dir=$2 ret

    # Check args
    if [ ! -r "${source_dir}/setup.py" ]
    then
        error "(install_crb) No setup script in '${source_dir}'"
        return 1
    elif [ ! -d "${target_dir}" ]
    then
        error "(install_crb) No target dir '${target_dir}'"
        return 1
    elif [ ! -x "${py_bin}" ]
    then
        error "(install_crb) Invalid python executeable '${py_bin}'"
        return 1
    fi

    pushd "${source_dir}"
    ${py_bin} setup.py install --prefix="${target_dir}"
    ret=$?
    popd
    return ${ret}
}


# Write a db password file for cerebrum, using the same arguments as the
# function to retrieve the file.
# 
# The file will not contain any password, actual auth is performed by pg_ident.
# Not sure how to do this for non-pg databases.
# 
# 
# Example usage:
#   write_passwd_file  /to/path  user  database
#   # Will write file '/to/path/passwd-user@database'
#   write_passwd_file  /to/path  user  database  host 
#   # Will write file '/to/path/passwd-user@database@host'
# 
function write_passwd_file  # target_dir db_user db_name [ db_host ]
{
    local target_dir=$1 user=$2 name=$3 host=$4 outfile

    # Check args
    if [ ! -d "${target_dir}" ]
    then
        error "(write_passwd_file) No target directory '${target_dir}'"
        return 1
    elif [ -z "${name}" -o -z "${user}" ]
    then
        error "(write_passwd_file) Empty params host(${host}) name(${name}) user(${user})"
        return 1
    fi

    outfile="${target_dir}/passwd-${user}@${name}"

    # Optional host
    if [ -n "${host}" ]
    then
        outfile="${outfile}@${host}"
    fi
    
    if ! touch "${outfile}"
    then
        error "(write_passwd_file) Unable to write to '${outfile}'"
        return 2
    fi

    echo -e "${user}\t" > ${outfile}
}


# Take a meta config file (with @REPLACE@ statements), and replace with each
# assignment given as optional arguments.
#
# Assignments are "keyword=value" assignments, and this function will attempt
# to replace any instance of '@keyword@' in the input file with 'value'.  This
# is kind of a 'poor mans autoconf'.
# 
# With no assignments, this function will only copy the given file to the
# destination directory.
# 
# Example usage:
#   write_conf cereconf.py.in /target/path 
#      # Will write the file cereconf.py.in to /target/path/cereconf.py
#      # Note that the '.in' extension is removed
#
#   write_conf somefile /target/path base_path=/something value=1
#      # Will replace @base_path@ and @value@ in 'somefile', and write the
#      # result to '/target/path/somefile'
#
function write_conf  # input_file target_dir [ assignment ... ]
{
    local infile=$1 target_dir=$2 assignments=( ${@:3} ) outfile

    # Check args
    if [ ! -r "${infile}" ]
    then
        error "(write_conf) Can't read input file '${infile}'"
        return 1
    elif [ ! -d "${target_dir}" ]
    then
        error "(write_conf) Not target directory '${target_dir}'"
        return 1
    fi

    # Get target filename, without potential .in extension
    outfile="${target_dir}/$( basename ${infile%.in} )"
    
    if ! touch "${outfile}"
    then
        error "(write_conf) Unable to write to '${outfile}'"
        return 1
    fi

    for idx in ${!assignments[@]}; do
        #IFS='=' read -a split <<< "${assignments[$idx]}"
        #assignments[$idx]="-es/@${split[0]}@/${split[@]:1}/g"
        # We need to replace '/' with '\/'
        local key value
        key=$( cut -d '=' -f 1 <<< ${assignments[$idx]} )
        value=$( cut -d '=' -f 2- <<< ${assignments[$idx]} )
        assignments[$idx]="-es/@${key}@/${value//\//\\/}/g"
    done

    # Note the eval. Not sure to execute this any other way
    if [ ${#assignments} -eq 0 ]
    then
        cat ${infile} > ${outfile}
        return
    fi

    sed_expressions="${assignments[*]}"

    echo sed ${sed_expressions} ${infile} to ${outfile}
    sed ${sed_expressions} ${infile} > ${outfile}
    return
}


# This function prints a modified, cleaned PYTHONPATH
#
# The modified path is prepended with '.', <arg1>, <arg2>, and any duplicates
# are then removed.
# 
# Example Usage:
#
#   PYTHONPATH='.:foo:bar:.:foo:.:bar' prepare_pypath bar baz
#   # Will print '.:bar:baz:foo'
# 
#   PYTHONPATH=$( prepare_pypath /path/to/foo /path/to/bar ) python script.py
# 
function prepare_pypath
{
    local path=( '.' $@ ) uniq
    
    # Append existing path
    path+=( $( split_str : ${PYTHONPATH} ) )

    # Filter unique, while preserving order
    uniq=( $( printf "%s\n" "${path[@]}" | nl | sort -u -k2 | sort -n | cut -f2- ) )

    echo $( join_args : ${uniq[@]} )
}


# This is the default setup routine for a cerebrum test. '
# 
# This is an attempt to generalize the setup procedure. It's probably not good
# enough, but let's give it a shot.
# 
function setup_test_env
{
    local root_dir env_name crb_src config_dir offline_pip
    local OPTARG OPTIND opt
    local pypath=( split_str : ${PYTHONPATH} )

    local usage=<<USAGE
Set up a new test environment for Cerebrum.

Options:
    -r DIR    Root directory, where to set up the test environment
                - In Jenkins, this should be set to \$WORKSPACE
                - Locally, this could be set to anything. I recommend /tmp
    -e NAME   Name of the virtual environment 
                We'll run virtenv <root>/<NAME>
    -c DIR    Path to the cerebrum source code
                We need this in order to run setup.py
    -s DIR    Setup directory, containing the neccessary files. We expect to
              find the following:
                - logging.ini.in: Log config template
                - cereconf.py.in: Cereconf template
                - extras.txt: List of DB design mod_*.sql-files
                - pip.txt: PIP requirements file
    -o DIR    Make PIP work offline, and supply a directory with the neccessary
              packages. Note that a tar-ball with every package from 'pip.txt'
              must already exist in this location.
              This makes it possible to install packages with pip even if we
              have no connection with pypi.python.org. It is, however, less
              automated.

USAGE

    while getopts "r:e:c:s:o:" opt
    do
        case "${opt}" in
        r)
            root_dir="${OPTARG}"
            ;;
        e)
            env_name="${OPTARG}"
            ;;
        c)
            # We could probably infer this from the dirname of this script, but
            # then again, we might also want to run the setup with some other,
            # altered Cerebrum source directory tree.
            crb_src="${OPTARG}"
            ;;
        s)
            config_dir="${OPTARG}"
            ;;
        o)
            # Directory of PIP packages, if working in offline mode
            offline_pip="${OPTARG}"
            ;;
        *)
            error "Invalid option '${opt}'" 
            echo ${usage}
            return 1
            ;;
        esac
    done
    shift $((OPTIND-1))

    # Verify that we have gathered all the neccessary input, and that the
    # directory variables actually exists.
    if [ -z "${root_dir}" -o ! -d "${root_dir}" ]
    then
        error "(setup_test_env) Invalid root directory '${root_dir}'"
        return 2
    elif [ -z "${crb_src}" -o ! -d "${crb_src}" ]
    then
        ## TODO: Check that it actually contains the cerebrum repository?
        error "(setup_test_env) Invalid cerebrum source directory '${crb_src}'"
        return 2
    elif [ -z "${config_dir}" -o ! -d "${config_dir}" ]
    then
        error "(setup_test_env) No config directory"
        return 2
    elif [ -n "${offline_pip}" -a ! -d "${offline_pip}" ]
    then
        error "(setup_test_env) No PIP package directory '${offline_pip}'"
        return 2
    elif [ -z "${env_name}" ]
    then
        error "(setup_test_env) Missing virtenv name"
        return 2
    fi

    # FILE CHECK
    # 
    # Verify that our mandatory config files are in place before we actually do
    # something

    local mandatory_files=('cereconf.py.in' \
                           'logging.ini.in' 'extras.txt' )
    for f in $mandatory_files
    do
        if [ ! -r "${config_dir}/${f}" ]
        then
            error "(setup_test_env) No setup file '${config_dir}/${f}'"
            return 3
        fi
    done

    # Directories and files
    local test_env=${root_dir}/${env_name}  # Working directory for our env

    local pip_requirements=${config_dir}/pip.txt
    local pip_cache=${test_env}/cache

    local crb_db_extras=${config_dir}/extras.txt
    local crb_cereconf=${config_dir}/cereconf.py.in
    local crb_log_config=${config_dir}/logging.ini.in

    local crb_confdir=${test_env}/etc/cerebrum

    # ENVIRONMENT SETUP
    # 
    # Set up (or reuse) the virtualenv. Install packages with pip

    if [ ! -f "${test_env}/bin/activate" ]; then
        info "Setting up new virtualenv in '${test_env}'"
        if ! virtualenv ${test_env}
        then 
            return 4
        fi
    else
        info "Using existing virtualenv in '${test_env}'"
    fi

    # Our binaries
    export CRB_PY=${test_env}/bin/python
    export CRB_PIP=${test_env}/bin/pip

    export DB_CREATE=/usr/bin/createdb 
    export DB_DROP=/usr/bin/dropdb

    # Install python packages with 'pip'
    if [ ! -e "${pip_requirements}" ]; then
        info "No required packages to install"
    elif [ -z "${pip_cache}" ]; then
        info "Installing packages with pip (no cache)"
        if ! pip_install_reqs ${pip_requirements}
        then
            return 4
        fi
    elif [ -z "${offline_pip}" ]
    then
        info "Installing packages with pip (with cache '${pip_cache}')"
        if ! pip_install_reqs ${pip_requirements} ${pip_cache}
        then
            return 4
        fi
    else
        info "Installing packages with pip offline (from '${offline_pip}')"
        if ! pip_install_reqs ${pip_requirements} ${offline_pip} true
        then
            return 4
        fi
    fi

    # CEREBRUM SETUP
    # 
    # Run the cerebrum install script, and write configs

    info "Installing Cerebrum into '${test_env}'"
    if ! install_crb ${crb_src} ${test_env}
    then 
        return 4
    fi

    # cereconf.py
    info "Writing config '${crb_cereconf}' to '${crb_confdir}'"
    if ! write_conf "${crb_cereconf}" ${crb_confdir} "test_base=${test_env}"
    then
        return 4
    fi

    # logging.ini
    info "Writing config '${crb_log_config}' to '${crb_confdir}'"
    if ! write_conf "${crb_log_config}" ${crb_confdir}
    then
        return 4
    fi


    # Given the cereconf, we should be able to extract the db setup
    # TODO: Should we SET in stead of GET the cereconf variables? Maybe it would
    # be better to set these things through script options, and not in the files
    # themselves.
    info "Fetching cereconf settings"
    local db_user db_name db_host auth_dir
    if ! db_user=$(get_cereconf 'CEREBRUM_DATABASE_CONNECT_DATA["user"]' ${crb_confdir}/cereconf.py)
    then
        return 5
    fi

    if ! db_name=$(get_cereconf 'CEREBRUM_DATABASE_NAME' ${crb_confdir}/cereconf.py)
    then
        return 5
    fi

    if ! db_host=$(get_cereconf 'CEREBRUM_DATABASE_CONNECT_DATA["host"]' ${crb_confdir}/cereconf.py)
    then
        return 5
    fi

    if ! auth_dir=$(get_cereconf 'DB_AUTH_DIR' ${crb_confdir}/cereconf.py)
    then
        return 5
    fi

    # Write a password file to the auth_dir
    if ! write_passwd_file "${auth_dir}" "${db_user}" "${db_name}" "${db_host}"
    then 
        return 4
    fi


    # BUILD DATABASE
    # 
    # Create a new database, and run makedb
    info "Creating new database"
    ${DB_DROP} -U "${db_user}" "${db_name}"
    # Could fail, if no database exists
    if ! ${DB_CREATE} -U "${db_user}" "${db_name}" "Test-database for tests in ${virt_env}"
    then
        error "Unable to create database '${db_name}'"
        return 4
    fi

    # Fetching design file arguments
    info "Fetching extra-files for makedb"
    local extra_file_args=''
    if [ -e "${crb_db_extras}" ]; then
        if ! extra_file_args=$(build_extra_file_args ${crb_src}/design ${crb_db_extras})
        then
            return 4
        fi
    fi

    info "Setting up database"
    pushd ${test_env}/sbin
    PYTHONPATH=$( prepare_pypath ${crb_confdir} ) ${CRB_PY} makedb.py $extra_file_args
    popd

}

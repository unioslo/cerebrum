#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

"""
Configurable cleaning and archiving script.

The scripts have two main functions, archiving and deleting. Old
archives can also be deleted. Options can be given as command line
options or in cereconf.

Options:

--archive      : archive mode
--delete       : delete mode
--read-config  : read options from cereconf
--dryrun       : just report what script would do
--name-pattern : The given pattern is the pattern of the file that
                 should be archived or deleted. Format is a python
                 regexp.
--filetype     : file type ('file' || 'dir')
--archive-name : name of archive file
--archive-age  : archive all files older than the given number of days.
                 If not given, archive all files that match
                 name-pattern.
--min-age      : If given, delete files older than the given number of days. 

If --read-config and --archive is given, try to read the following
data-structure from cereconf:

  ARCHIVE_FILES = [
      {'name_pattern' : <string>,   # mandatory
       'archive_name' : <string>,   # mandatory
       'file_type'    : <string>,   # default: 'file'
       'archive_age'  : <int>,      # default: 0
       'min_age'      : <int>},     # optional
      ...]

If --read-config and --delete is given, try to read the following
data-structure from cereconf:

  DELETE_FILES = [
      {'name_pattern' : <string>,   # mandatory
       'file_type'    : <string>,   # default: 'file'
       'min_age'      : <int>},     # optional
      ...]

If name_pattern, archive_name, archive_age or min_age is given by
command line options, either --archive or --delete but not both must
be given.

Age is given in days.

Postfix on archive files are '-%Y-%m-%d.tar.gz'
"""

##
## Hva som gjenstår
##
## - testing. Test alle funksjonene
## - commit
## - lag sch_jobs på uio


import getopt
import sys
import os
import time
import re
import tempfile
import shutil
import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory

tar_cmd = '/bin/tar --files-from %s --remove-files -czf %s'
logger = Factory.get_logger("cronjob")


def find_files(name_pattern, min_age, file_type):
    """
    Find all files matching name_pattern that are older than min_age
    """
    matches = []
    pos = name_pattern.rfind("/")
    dirname = name_pattern[:pos]
    regexp = re.compile(name_pattern[pos+1:])
    # min_age, in seconds
    time_threshold = time.time() - min_age*3600*24
    try:
        for name in os.listdir(dirname):
            file_path = os.path.join(dirname, name)
            if file_type == 'dir' and not os.path.isdir(file_path):
                continue
            if file_type == 'file' and not os.path.isfile(file_path):
                continue
            if regexp.match(name):
                mtime = os.stat(file_path).st_mtime
                # If the files last modification time is less than min_age it's a match
                if mtime < time_threshold:
                    matches.append(file_path)
        logger.debug("Found %d files with pattern %s older than %s days in dir %s" % (
            len(matches), name_pattern[pos+1:], min_age, dirname))
    except OSError, e:
        logger.error("Error finding files with pattern %s: %s" % (name_pattern, e))
    return matches


def delete_files(name_pattern='', file_type='file', min_age=0, dryrun=False):
    """
    Delete all files matching name_pattern that are older than min_age
    """
    # Find files matching pattern and age threashold
    for tmp in find_files(name_pattern, min_age, file_type):
        if not dryrun:
            logger.info("Unlink file: %s" % tmp)
            if file_type == 'file':
                os.unlink(tmp)
            else:
                shutil.rmtree(tmp)


def archive_files(name_pattern='', archive_name='', file_type='file',
                  archive_age=0, min_age=0, dryrun=False):
    """
    Archive all files that match name_pattern and are older than
    archive_age. Any such files are tared and zipped into one file
    with name archive_name+postfix.
    """
    if not (name_pattern or archive_name):
        logger.warning("Both name_pattern and archive_name must be given")

    # Check if old archives should be deleted
    if min_age > 0:
        # FIXME: pattern is postfix dependent
        archive_pattern = archive_name + '-\d+-\d+-\d+.*\.tar\.gz'
        logger.info("Delete archives of type %s older than %d days" % (
            archive_pattern, min_age))
        delete_files(archive_pattern, file_type, min_age, dryrun=dryrun)

    # Check if new files should be archived
    files_to_archive = find_files(name_pattern, archive_age, file_type)
    if not files_to_archive:
        return
    # Create filename of archive file, first postfix
    time_threshold = time.time() - archive_age*3600*24
    postfix = '-' + time.strftime('%Y-%m-%d', time.localtime(time_threshold))
    # create a temporary file for tar command which list files to archive 
    tempfile.tempdir = '/tmp/'
    tmp_os_handle, tmp_name = tempfile.mkstemp('.filelist')
    outfile = open(tmp_name, 'w')
    for f in files_to_archive:
        outfile.write(f+"\n")
    outfile.close()
    # If a file with the same name exists we add a counter
    count = 0
    format = "%(archive_name)s%(postfix)s.tar.gz"
    while True:
        if count:
            format = "%(archive_name)s%(postfix)s--%(count)d.tar.gz"
        tar_name = format % {
            'archive_name': archive_name,
            'postfix': postfix,
            'count': count}
        if not os.path.exists(tar_name):
            break
        count += 1
    logger.debug("tar %s -> %s" % (str(files_to_archive), tar_name))
    if not dryrun:
        if os.path.exists(tar_name):
            logger.error("%s exists" % tar_name)
        else:
            cmd = tar_cmd % (tmp_name, tar_name)
            # TBD use something else than os.system?
            ret = os.system(cmd)
            if ret != 0:
                logger.error("tar failed (%s): %s" % (cmd, ret))
            if file_type == 'dir':
                # tar won't delete directories used as argument
                for f in files_to_archive:
                    os.rmdir(f)
    os.unlink(tmp_name)


def usage(exitcode=0):
    print __doc__
    sys.exit(exitcode)


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', [
            'help', 'archive', 'delete', 'read-config', 'dryrun',
            'name-pattern=', 'filetype=', 'archive-name=', 'archive-age=',
            'min-age='])
    except getopt.GetoptError:
        usage(1)
    if not opts:
        usage(1)

    archive_mode = False
    delete_mode = False
    read_config = False
    dryrun = False
    name_pattern = None
    archive_name = None
    file_type = 'file'
    archive_age = 0
    min_age = 0
    
    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('--archive',):
            archive_mode = True
        elif opt in ('--delete',):
            delete_mode = True
        elif opt in ('--read-config',):
            read_config = True
        elif opt in ('--dryrun',):
            dryrun = True
        elif opt in ('--name-pattern',):
            name_pattern = val
        elif opt in ('--filetype',):
            file_type = val
        elif opt in ('--archive-name',):
            archive_name = val
        elif opt in ('--archive-age',):
            archive_age = int(val)
        elif opt in ('--min-age',):
            min_age = int(val)

    # read options from cereconf or cmd line?
    if read_config:
        if archive_mode:
            try:
                archive_actions = getattr(cereconf, 'ARCHIVE_FILES') 
                logger.info("Archive mode, reading ARCHIVE_FILES from cereconf")
            except AttributeError:
                usage(1)
        if delete_mode:
            try:
                delete_actions = getattr(cereconf, 'DELETE_FILES') 
                logger.info("Delete mode, reading DELETE_FILES from cereconf")
            except AttributeError:
                usage(1)
    elif name_pattern and delete_mode:
        delete_actions = [(name_pattern, min_age)]        
    elif name_pattern and archive_name and archive_mode:
        tmp = {'name_pattern': name_pattern, 'archive_name': archive_name,
               'file_type': file_type, 'archive_age': archive_age,
               'min_age': min_age}
        archive_actions = [tmp]
    else:
        usage()

    if dryrun:
        logger.info('DRYRUN: no actions will be performed')

    if delete_mode:
        for d in delete_actions:
            d['dryrun'] = dryrun
            delete_files(**d)

    if archive_mode:
        for a in archive_actions:
            a['dryrun'] = dryrun
            archive_files(**a)

        
if __name__ == '__main__':
    main()

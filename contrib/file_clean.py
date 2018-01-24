#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Configurable cleaning and archiving script.

The scripts have two main functions, archiving and deleting. Old
archives can also be deleted. Options can be given as command line
options or in a config file.

Options:

--archive      : archive mode
--delete       : delete mode
--read-config  : read options from config file.
--dryrun       : just report what script would do
--name-pattern : The given pattern is the pattern of the file that
                 should be archived or deleted. Format is a python
                 regexp.
--dirname      : the directory where to look for files matching
                 name-pattern.
--filetype     : file type ('file' || 'dir')
--archive-name : name of archive file
--archive-age  : archive all files older than the given number of days.
                 If not given, archive all files that match
                 name-pattern.
--no-delete    : Don't delete files that are archived
--min-age      : If given, delete files older than the given number of days. 

If --read-config and --archive is given, try to read the following
data-structure from config file:

  ARCHIVE_FILES = [
      {'name_pattern' : <string>,   # mandatory
       'dirname'      : <string>,   # mandatory
       'archive_name' : <string>,   # mandatory
       'file_type'    : <string>,   # default: 'file'
       'archive_age'  : <int>,      # default: 0
       'no_delete'    : <boolean>   # default: False
       'min_age'      : <int>},     # optional
      ...]

If --read-config and --delete is given, try to read the following
data-structure from config file:

  DELETE_FILES = [
      {'name_pattern' : <string>,   # mandatory
       'dirname'      : <string>,   # mandatory
       'file_type'    : <string>,   # default: 'file'
       'min_age'      : <int>},     # optional
      ...]

If name_pattern, archive_name, archive_age or min_age is given by
command line options, either --archive or --delete but not both must
be given.

Postfix on archive files are '-%Y-%m-%d.tar.gz'
"""

##
## TODO: 
##
##  * tar command should not be hardwired into the code like this.
##    It's a bit of a pain to fix, though.
##
##  * os.system should be replaced by something better. The new
##    subprocess module (from 2.4) is preferrable, but we must wait
##    til we no longer support version < 2.4.
##

import getopt
import sys
import os
import time
import re
import tempfile
import shutil
import cerebrum_path
from Cerebrum.Utils import Factory

logger = Factory.get_logger("cronjob")
postfix_re = '-\d+-\d+-\d+.*\.tar\.gz'


def find_files(name_pattern, dirname, file_type='file', min_age=0):
    """
    Find all files in dirname matching name_pattern that are older
    than min_age. Note that search is not recursive.
    Return as a list of relative paths.

    @param name_pattern: name pattern (python regexp) of files to delete.
    @type  name_pattern: string
    @param dirname: Directory where to look for files matching name pattern.
    @type  dirname: string
    @param file_type: file_type must be file or directory.
    @type  file_type: string 
    @param min_age: Files to delete must be older than min_age.
    @type  min_age: int
    @return: Return files matching given criterias as a list of paths.
    """
    matches = []
    # min_age, in seconds
    time_threshold = time.time() - min_age*3600*24
    for name in os.listdir(dirname):
        try:
            file_path = os.path.join(dirname, name)
            if file_type == 'dir' and not os.path.isdir(file_path):
                continue
            if file_type == 'file' and not os.path.isfile(file_path):
                continue
            if re.match(name_pattern, name):
                mtime = os.stat(file_path).st_mtime
                # If the files last modification time is less than
                # min_age it's a match
                if mtime < time_threshold:
                    matches.append(name)
        except OSError:
            # TBD: error or exception?
            logger.ecxeption("Error listing files in %s" % dirname)
    logger.debug("Found %d files in %s with pattern %s older than %s days" % (
            len(matches), dirname, name_pattern, min_age))
    return matches


def delete_files(name_pattern='', dirname='', file_type='file',
                 min_age=0, dryrun=False):
    """
    Delete all files of type file_type in dirname matching
    name_pattern that are older than min_age. dirname must be an absolute path

    @param name_pattern: name pattern (python regexp) of files to delete.
    @type  name_pattern: string
    @param dirname: Directory where to look for files matching name pattern.
    @type  dirname: string
    @param file_type: file_type must be file or directory.
    @type  file_type: string 
    @param min_age: Files to delete must be older than min_age.
    @type  min_age: int
    @param dryrun: delete or not?
    @type  dryrun: bool
    """
    # Sanity checks
    assert os.path.isdir(dirname), "%s is not a directory" % dirname
    assert os.path.isabs(dirname), "%s is not an absolute path" % dirname
    # Find files matching pattern and age threashold
    for name in find_files(name_pattern, dirname, file_type, min_age):
        if not dryrun:
            try:
                file_path = os.path.join(dirname, name)
                logger.info("Unlink file: %s" % file_path)
                if file_type == 'file':
                    os.unlink(file_path)
                else:
                    shutil.rmtree(file_path)
            except:
                logger.exception("Couldn't delete %s" % file_path)


def archive_files(name_pattern='', dirname='', archive_name='',
                  file_type='file', archive_age=0, min_age=0,
                  no_delete=False, dryrun=False):
    """
    Archive all files in dirname that match name_pattern and are
    older than archive_age. Any such files are tared and zipped into
    one file with name archive_name+postfix. 

    @param name_pattern: name pattern (python regexp) of files to delete.
    @type  name_pattern: string
    @param dirname: Directory where to look for files matching name pattern.
    @type  dirname: string
    @param archivename: name of archive file as a path
    @type  archivename: string
    @param file_type: file_type must be file or directory.
    @type  file_type: string 
    @param archive_age: Files to archive must be older than archive_age.
    @type  archive_age: int
    @param min_age: If no_delete is False delete archives older than min_age.
    @type  min_age: int
    @param no_delete: delete old archives or not?
    @type  no_delete: bool
    @param dryrun: delete or not?
    @type  dryrun: bool
    """
    # Sanity checks
    assert os.path.isdir(dirname), "%s is not a directory" % dirname
    assert os.path.isabs(dirname), "%s is not an absolute path" % dirname
    if not (name_pattern or archive_name):
        logger.warning("name_pattern and archive_name must be given")
        return
    
    # Check if old archives should be deleted
    if min_age > 0:
        archive_pattern = os.path.basename(archive_name) + postfix_re
        logger.info("Delete archives of type %s older than %d days" % (
            archive_pattern, min_age))
        # Archives made by this script are files. Thus file_type == 'file'
        delete_files(archive_pattern, os.path.dirname(archive_name), 'file',
                     min_age, dryrun=dryrun)
    # Check if new files should be archived
    files_to_archive = find_files(name_pattern, dirname, file_type, archive_age)
    if not files_to_archive:
        return
    # Set tar command
    tar_cmd = '/bin/tar --files-from %s --remove-files -czf %s'
    if no_delete:
        tar_cmd = '/bin/tar --files-from %s -czf %s'
        
    # Create filename of archive file, first postfix
    time_threshold = time.time() - archive_age*3600*24
    postfix = '-' + time.strftime('%Y-%m-%d', time.localtime(time_threshold))
    # Create a temporary file for tar command which list files to archive
    tempfile.tempdir = dirname
    tmp_os_handle, tmp_name = tempfile.mkstemp('.filelist')
    outfile = open(tmp_name, 'w')
    for f in files_to_archive:
        outfile.write(f+"\n")
    outfile.close()
    # Change dir to dirname to be able to remove files in tmp_name
    # after archiving
    os.chdir(dirname)
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
            if file_type == 'dir' and no_delete is False:
                # tar won't delete directories used as argument
                for f in files_to_archive:
                    try:
                        old_dir = os.path.join(dirname, f)
                        shutil.rmtree(old_dir)
                    except:
                        logger.exception("Couldn't delete %s" % old_dir)
    os.unlink(tmp_name)


def usage(exitcode=0):
    print __doc__
    sys.exit(exitcode)


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', [
            'help', 'archive', 'delete', 'read-config', 'dryrun',
            'name-pattern=', 'dirname=', 'filetype=', 'archive-name=',
            'archive-age=', 'min-age=', 'no-delete'])
    except getopt.GetoptError:
        usage(1)
    if not opts:
        usage(1)

    archive_mode = False
    delete_mode = False
    read_config = False
    no_delete = False
    dryrun = False
    name_pattern = None
    archive_name = None
    dirname = None
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
        elif opt in ('--dirname',):
            dirname = val
        elif opt in ('--filetype',):
            file_type = val
        elif opt in ('--archive-name',):
            archive_name = val
        elif opt in ('--archive-age',):
            archive_age = int(val)
        elif opt in ('--min-age',):
            min_age = int(val)
        elif opt in ('--no-delete',):
            no_delete = True

    # read options from config file or cmd line?
    if read_config:
        import file_clean_conf
        if archive_mode:
            try:
                archive_actions = file_clean_conf.ARCHIVE_FILES
                logger.info("Archive mode, reading ARCHIVE_FILES from config file")
            except AttributeError:
                usage(1)
        if delete_mode:
            try:
                delete_actions = file_clean_conf.DELETE_FILES
                logger.info("Delete mode, reading DELETE_FILES from config file")
            except AttributeError:
                usage(1)
    elif name_pattern and dirname and delete_mode:
        tmp = {'name_pattern': name_pattern, 'dirname': dirname,
               'file_type': file_type, 'min_age': min_age,}
        delete_actions = [tmp]
    elif name_pattern and dirname and archive_name and archive_mode:
        tmp = {'name_pattern': name_pattern, 'archive_name': archive_name,
               'dirname': dirname, 'file_type': file_type,
               'archive_age': archive_age, 'min_age': min_age,
               'no_delete': no_delete}
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

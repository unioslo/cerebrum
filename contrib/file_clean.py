#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

"""
Configurable cleaning or archiving script.

The script tries to read configuration from cereconf. Configurations
in cereconf.py must be given on the format:

  CLEAN_FILES = [
      {'name_regexp': <string>,     # mandatory
       'archive_dir': <string>,     # mandatory
       'file_type': <string>,       # default: 'file'
       'archive_age': <int>,        # default: 0
       'archive_name': <string>,    # optional
       'max_archive_age': <int>}]   # optional


All files/dirs (depending on file_type) that matches name_regexp older
than archive_age are moved to a archive_name-<timestamp>.tar.gz with
timestamp equal the date reflected by archive_age.

If archive_name is not set, the file/dir is deleted without being
archived.  If max_archive_age is not None, any archive older than
max_archive_age will be deleted.

Age is given in days.
"""


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


class FilterSpec(object):
    def __init__(self, name_regexp, archive_dir, file_type='file',
                 archive_age=0, archive_name=None, max_archive_age=None):
        self.name_regexp = name_regexp
        self.file_type = file_type
        self.archive_dir = archive_dir
        self.archive_age = archive_age
        self.archive_name = archive_name
        self.max_archive_age = max_archive_age


    def process_filter(self, dryrun=False):
        # Check for obsolete archives
        if self.archive_name and self.max_archive_age:
            regexp = re.compile(r"%s-\d+.*.tar.gz" % self.archive_name)
            time_threshold = time.time() - self.max_archive_age*3600*24
            for name in os.listdir(self.archive_dir):
                if regexp.match(name):
                    mtime = os.stat("%s/%s" % (self.archive_dir, name))[8]
                    if mtime < time_threshold:
                        tmp = os.path.join(self.archive_dir, name)
                        logger.debug("Unlink archive: %s" % tmp)
                        if not dryrun:
                            os.unlink(tmp)
                    
        # Find files matching filter
        matches = []
        pos = self.name_regexp.rfind("/")
        dirname = self.name_regexp[:pos]
        regexp = re.compile(self.name_regexp[pos+1:])
        logger.debug("Process dir='%s', re='%s', age=%s, t=%s, an=%s" % (
            dirname, self.name_regexp[pos+1:], self.archive_age,
            self.file_type, self.archive_name))
        time_threshold = time.time() - self.archive_age*3600*24
        min_age = time.time()
        for name in os.listdir(dirname):
            if self.file_type == 'dir' and not os.path.isdir(
                "%s/%s" % (dirname, name)):
                continue
            if self.file_type == 'file' and not os.path.isfile(
                "%s/%s" % (dirname, name)):
                continue
            if regexp.match(name):
                mtime = os.stat("%s/%s" % (dirname, name))[8]
                if mtime < time_threshold:
                    matches.append(name)
                    if mtime < min_age:
                        min_age = mtime

        # Process files that matched filter
        if not matches:
            return

        if not self.archive_name:
            for m in matches:
                tmp = os.path.join(dirname, m)
                logger.debug("Unlink match: %s" % tmp)
                if not dryrun:
                    if self.file_type == 'file':
                        os.unlink(tmp)
                    else:
                        shutil.rmtree(tmp)
        else:
            tmp_name = tempfile.mkstemp('.filelist')[1]
            outfile = open(tmp_name, 'w')
            for m in matches:
                outfile.write(m+"\n")
            outfile.close()
            os.chdir(dirname)
            count = 0
            date = time.strftime('%Y-%m-%d', time.localtime(time_threshold))
            format = "%(name)s-%(date)s.tar.gz"
            while True:
                if count:
                    format = "%(name)s-%(date)s--%(count)d.tar.gz"
                tar_name = os.path.join(self.archive_dir, format % {
                    'name': self.archive_name,
                    'date': date,
                    'count': count})
                if not os.path.exists(tar_name):
                    break
                count += 1
            logger.debug("tar %s -> %s.  mtime=%s" % (str(matches), tar_name, min_age))
            if not dryrun:
                if os.path.exists(tar_name):
                    logger.error("%s exists" % tar_name)
                else:
                    cmd = tar_cmd % (tmp_name, tar_name)
                    ret = os.system(cmd)
                    if ret != 0:
                        logger.error("tar failed (%s): %s" % (cmd, ret))
                    if self.file_type == 'dir':
                        # tar won't delete directories used as argument
                        for m in matches:
                            os.rmdir(m)
            os.unlink(tmp_name)


def remove_logs(dryrun=False):
    try:
        for file_spec in mycereconf.CLEAN_FILES:
            fs = FilterSpec(**file_spec)
            fs.process_filter(dryrun=dryrun)
    except AttributeError, e:
        print "Files to clean not specified in cereconf: %s" % e


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', [
            'help', 'remove-files', 'report-changes'])
    except getopt.GetoptError:
        usage(1)
    if not opts:
        usage(1)

    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('--remove-files',):
            remove_logs(dryrun=False)
        elif opt in ('--report-changes',):
            remove_logs(dryrun=True)


def usage(exitcode=0):
    print """Usage: [options]

    --remove-files   : actually remove/archive the files
    --report-changes : report what --remove-files would have done

    Cerebrum produces a number of temporary files, logg-files etc. in
    various locations.  This script removes/archives these files.
    """
    sys.exit(exitcode)


if __name__ == '__main__':
    main()

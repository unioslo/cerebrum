#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2009 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

# $Id$

import sys
import getopt
import os

from xml.dom import minidom

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory

progname = __file__.split("/")[-1]

__doc__ = """
Usage: %s [options]
   --studconfig-file -s  XML-file containing autostud-configuration
   --help -h             Prints this message and quits

'--studconfig-file' is mandatory

Based on the autostud configuration-file, this program makes sure that
all the disks that are designated as student disks, and only those,
are tagged as such in Cerebrum.

""" % progname

__version__ = "$Revision$"
# $URL$


logger = Factory.get_logger("cronjob")

db = Factory.get('Database')()
db.cl_init(change_program=progname[:16])
constants = Factory.get('Constants')(db)


def parse_studconfig_file(config_file):
    """Parses the studconfig-file, looking for studentdisk definitions.

    There are two places that contain this information

    * In ``studconfig.disk_oversikt.diskdef``-elements, within the
      ``path``-attribute => fully qualified disks.      
    * In ``studconfig.disk_oversikt.diskdef``-elements, within the
      ``prefix``-attribute => prefixes that can match any number of
      studentdisks.

    @param config_file:
      Filename of the config-file that is to be parsed
    @type config_file:
      string
      
    @return:
      A tuple, containing two lists:
      * All disks defined with full paths
      * All prefixes that match can studentdisks
    @rtype:
      tuple
      
    """
    disks = []
    disk_prefixes = []
    
    logger.info("Parsing studconfig-file: '%s'" % config_file)
    xmldoc = minidom.parse(config_file)
    
    disksets = xmldoc.getElementsByTagName('disk_oversikt')
    for set in disksets:        
        diskdefs = set.getElementsByTagName('diskdef')
        for diskdef in diskdefs:
            if u'path' in diskdef.attributes.keys():
                path = diskdef.attributes['path'].value
                logger.debug("Found disk: '%s'" % path)
                disks.append(path)
                
            if u'prefix' in diskdef.attributes.keys():
                prefix = diskdef.attributes['prefix'].value
                logger.debug("Found prefix: '%s'" % prefix)
                disk_prefixes.append(prefix)

    logger.info("Parsing done; found %s fully qualifed disks and %s prefixes" %
                (len(disks), len(disk_prefixes)))
    return (disks, disk_prefixes)


def retrieve_all_disks_from_DB():
    """Returns a dict containing all disks in DB.

    @return:
      A dictionary containing all disks registered in Cerebrum.
      Keys = disk paths, e.g. '/uio/aristoteles/s14'
      Values = disk entity IDs (ints)
    @rtype:
      dictionary
    
    """
    all_disks = {}
    disk = Factory.get("Disk")(db)
    all_disk_rows = disk.search()
    for disk_row in all_disk_rows:
        # We just need the path and the entity ID of the disk; no need
        # to keep more info than that.
        all_disks[disk_row['path']] = disk_row['disk_id']

    logger.info("DB-search done; found %s disks" % len(all_disks))
    return all_disks
                    

def is_student_disk(disk_path, stud_disks, stud_disk_prefixes):
    """Check if the given disk should be designated as a student-disk.

    If the disk is either defined fully in the file OR starts with any
    of the prefixes given, it should be considered as a astudentdisk;
    otherwise, it shouldn't.

    @param disk_path:
      Full path of the disk to be checked
    @type disk_path:
      string

    @param stud_disks:
      Studentdisks defined by fully qualified paths
    @type stud_disks:
      list
      
    @param stud_disk_prefixes:
      Studentdisks defined by the prefixes of such disks
    @type stud_disk_prefixes:
      list
      
    @return:
      Whether or not the disk in question should be considered a studentdisk
    @rtype:
      boolean

    """
    if disk_path in stud_disks:
        logger.debug("'%s' found as student-disk" % disk_path)
        return True
        
    for prefix in stud_disk_prefixes:
        if disk_path.startswith(prefix):
            logger.debug("'%s' starts with '%s' => studentdisk" %
                         (disk_path, prefix))
            return True

    return False


def ensure_tagged(disk_id):
    """Makes sure that the disk in question is tagged.

    @param disk_id:
      Entity ID of the disk that is to be processed
    @type disk_id:
      int
      
    """
    disk = Factory.get("Disk")(db)
    disk.find(disk_id)
    if not disk.get_trait(constants.trait_student_disk):
        logger.info("Disk '%s' (%s) not tagged => tagging" % (disk.path, disk_id))
        disk.populate_trait(constants.trait_student_disk)
        disk.write_db()
    else:
        logger.debug("Disk '%s' (%s) already tagged, as it should be" %
                     (disk.path, disk_id))
    

def ensure_untagged(disk_id):
    """Makes sure that the disk in question is not tagged.

    @param disk_id:
      Entity ID of the disk that is to be processed
    @type disk_id:
      int
      
    """
    disk = Factory.get("Disk")(db)
    disk.find(disk_id)
    if disk.get_trait(constants.trait_student_disk):
        logger.info("Disk '%s' (%s) tagged => untagging" % (disk.path, disk_id))
        disk.delete_trait(constants.trait_student_disk)
        disk.write_db()
    else:
        logger.debug("Disk '%s' (%s) is not tagged, as it shouldn't be" %
                     (disk.path, disk_id))


def usage(message=None):
    """Gives user info on how to use the program and its options.

    @param message:
      Extra message to supply to user before rest of help-text is given.
    @type message:
      string

    """
    if message is not None:
        print >>sys.stderr, "\n%s" % message

    print >>sys.stderr, __doc__


def main(argv=None):
    """Main processing hub for program.

    @param argv:
      Substitute for sys.argv if wanted; see main help for options
      that can/should be given.
    @type argv:
      list

    @return:
      value that program should exit with
    @rtype:
      int    

    """
    if argv is None:
        argv = sys.argv

    ##################################################################
    ### Read options
    options = {"studconfig-file": None}

    try:
        opts, args = getopt.getopt(argv[1:], "hs:",
                                   ["help", "studconfig-file="])
    except getopt.GetoptError, error:
        usage(message=error.msg)
        return 1

    for opt, val in opts:
        if opt in ('-h', '--help',):
            usage()
            return 0
        if opt in ('-s', '--studconfig-file',):
            options["studconfig-file"] = val

    if options["studconfig-file"] is None:
        usage("Must supply a file containing info about " +
              "student-disks via '--studconfig-file'")
        return 1

    if not os.path.exists(options["studconfig-file"]):
        usage("Unable to find configfile '%s'" % options["studconfig-file"])
        return 2

    ##################################################################
    ### Compile lists of disks in file and in DB
    stud_disks, stud_disk_prefixes = parse_studconfig_file(options["studconfig-file"])
    db_disks = retrieve_all_disks_from_DB()

    ##################################################################
    ### Do basic sanity-check comparisons config.file <=> DB
    all_paths = db_disks.keys()
    for stud_disk in stud_disks:
        # Check if disk with this full name exists in Cerebrum
        if not stud_disk in all_paths:
            logger.error("Disk '%s' listed in file, but does not exist in Cerebrum" % stud_disk)

    for prefix in stud_disk_prefixes:
        # Check if any disk in Cerebrum matches this prefix
        in_use = False
        for path in all_paths:
            if path.startswith(prefix):
                in_use = True
        if not in_use:
            # No disks start with this prefix => outdated definition?
            logger.error("Prefix '%s' does not match any disk in Cerebrum" % prefix)

    ##################################################################
    ### Process disks, tagging/untagging as necessary
    total_student_disks = 0
    for disk_path, disk_id in db_disks.items():
        if is_student_disk(disk_path, stud_disks, stud_disk_prefixes):
            total_student_disks += 1
            ensure_tagged(disk_id)
        else:
            ensure_untagged(disk_id)
            
    logger.info("A total of %s disks are now tagged as studentdisks" % total_student_disks)

    ##################################################################
    ### All done! Close of properly
    db.commit()
    return 0
    

if __name__ == "__main__":
    logger.info("Starting program '%s'" % progname)
    return_value = main()
    logger.info("Program '%s' finished" % progname)
    sys.exit(return_value)

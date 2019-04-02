#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

# input: file with list of person_ids to remove cim_spread for, 
# each id should be on a separate line.

#
# Generic imports
#
import getopt
import sys
import os

#
# Cerebrum imports
#
import cerebrum_path
import cereconf
from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum.Utils import Factory

#
# global variables
#
db = Factory.get('Database')()
p = Factory.get('Person')(db)
# logger=Factory.get_logger('cronjob')

db.cl_init(change_program='delete_cim_spread')

progname = __file__.split("/")[-1]
__doc__ = """
usage: %s <-h | -f filename | -d >

Script for deleting cim_spread for a list of persons.
List of persons is given as a file with person_ids, one id per line.

options:
    [-h] | [--help]                     - this text
    [-f filename] | [--file filename]   - delete cim_spread for all ids in the given filename
    [-d] | [--dryrun]                   - dryrun, don't commit to database.

""" % (progname)


def usage(exit_code=0, msg = None):
    if msg:
        print msg
    print __doc__
    sys.exit(exit_code)
    
def main():
    global filename, id_to_delete

    try:
        opts,args = getopt.getopt(sys.argv[1:], 'hf:d', ['help','file=','dryrun'])
        if opts == []:
            usage(1)
    except getopt.GetoptError as e:
        usage(1, e.msg)

    filename = None
    id_to_delete = None
    dryrun = False
    for opt,val in opts:
        if opt in ('-h', '--help'):
            usage()
        if opt in ('-f', '--file'):
            filename = val
        if opt in ('-d', '--dryrun'):
            dryrun = True

    if filename == None:
        usage(0, "Missing filename argument.")

    if (os.path.exists(filename) != True):
        print "File \'%s\' seems to be missing" % filename 
        return

    # read file
    with open(filename, 'r') as fh:
        ids = fh.readlines()

    for person_id in ids:
        person_id = person_id.strip()

        p.clear()
        p.find(person_id)
        print "Deleting spread for:", person_id
        p.delete_spread(732)

    if dryrun:
        db.rollback()
        print "All changes rolled back"
    else:
        db.commit()
        print "Committed all changes"

if __name__ == '__main__':
    main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2011 University of Oslo, Norway
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

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory

progname = __file__.split("/")[-1]

__doc__ = """
Usage: %s [options]

   --aff, -a          Comma-seperated list of the affiliations to include
   --students         Alias for adding the following affiliations:
                         'STUDENT/aktiv', 'STUDENT/drgrad' and 'STUDENT/evu'
   --file, -f FILE    Where to generate the exported output. Default: STDOUT
   --help             Prints this message and quits

This script generates a list of the primary useraccounts of all people
with at least one of affiliations designated by --aff

""" % progname

__version__ = "$Revision$"
# $URL$

logger = Factory.get_logger("console")

db = Factory.get('Database')()
pe  = Factory.get('Person')(db)
co  = Factory.get('Constants')(db)
ac  = Factory.get('Account')(db)

options = {"aff": [],
           "output": sys.stdout}

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
    try:
        opts, args = getopt.getopt(argv[1:],
                                   "ha:f:",
                                   ["help", "aff=",
                                    "file=", "students"])
    except getopt.GetoptError, error:
        usage(message=error.msg)
        return 1

    output_stream = options["output"]

    for opt, val in opts:
        if opt in ('-h', '--help',):
            usage()
            return 0
        if opt in ('-a', '--aff',):
            options['aff'] += val.split(',')
        if opt in ('--students'):
            options['aff'] += ['STUDENT/aktiv', 'STUDENT/drgrad', 'STUDENT/evu']
        if opt in ('-f', '--file',):
            options["output"] = val

    if options["output"] != sys.stdout:
        output_stream = open(options["output"], "w")

    if not options['aff']:
        usage(message="Did you really want to do this without supplying any affiliations?")
        return 2

    # First, gather a list with all persons with the given affiliations
    person_rows = []
    for aff_status in options['aff']:
        logger.info("Prosessing people with aff '%s'" % aff_status)

        # If no status is given, make sure it is set to None in
        # further processing
        padded_aff_status = aff_status.split('/') + [None]
        (aff, status) = padded_aff_status[0:2]
        
        aff_const = co.PersonAffiliation(aff)
        if status is not None:
            status_const = co.PersonAffStatus(aff, status)
        else:
            status_const = None

        result = pe.list_affiliations(affiliation=aff_const, status=status_const)
        logger.info("Found '%s' people with aff '%s'" % (len(result), aff_status))
        person_rows = person_rows + result

    # ..then retrieve the primary accounty for each of them
    no_primary_account = 0
    all_accounts = set() # using set() to not worry about duplicates
    for row in person_rows:
        pe.clear()
        pe.find(row['person_id'])
        primary_account_id = pe.get_primary_account()
        if primary_account_id is None:
            logger.debug("Person '%s' has no valid primary account" % pe.entity_id)
            no_primary_account += 1
            continue
        ac.clear()
        ac.find(primary_account_id)
        all_accounts.add(ac.account_name)

    logger.info("Found a total of %s " % len(all_accounts) +
                "individuals with valid primary accounts")
    logger.info("Found a total of %s " % no_primary_account +
                "individuals without valid primary accounts")

    
    sorted_accounts = list(all_accounts)
    sorted_accounts.sort()

    for account in sorted_accounts:
        output_stream.write(account + "\n")

    if output_stream != sys.stdout:
        output_stream.close()

    return 0


if __name__ == "__main__":
    logger.info("Starting program '%s'" % progname)
    return_value = main()
    logger.info("Program '%s' finished" % progname)
    sys.exit(return_value)

#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

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
import re

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory, sendmail
from Cerebrum.modules.dns.Subnet import Subnet
from Cerebrum.modules.bofhd.errors import CerebrumError

progname = __file__.split("/")[-1]

__doc__ = """
Usage: %s [options]
   --datafile, -d   File containing info about subnets
   --vlanfile, -v   File containing info about VLANs
   --force, -f      Force import to make non-erronous changes,
                    even if other parts of the import fail
   --help, -h       Prints this message and quits

'--datafile' must be specified

This program loads data for subnets from given datafile, adding info
about VLANs where available.

""" % progname

__version__ = "$Revision$"
# $URL$


logger = Factory.get_logger("console")

db = Factory.get('Database')()
db.cl_init(change_program=progname[:16])


def add_subnet(subnet, description, vlan, perform_checks= True):
    s = Subnet(db)
    s.clear()
    s.populate(subnet, description, vlan=vlan)
    try:
        s.write_db(perform_checks=perform_checks)
    except db.DatabaseError, m:
        raise CerebrumError, "Database error: %s" % m


def parse_vlan_file(filename):
    subnet_to_vlan = {}
    logger.info("Parsing VLAN-file '%s'" % filename)
    infile = open(filename)

    matcher = re.compile(r'(\d+)\s+([1234567890./]+)') # r'(\d+)\s+((\d+){4}/\d{2})'
    for line in infile:
        result = matcher.match(line)
        if result:
            vlan_ID = result.group(1)
            subnet = result.group(2)
            logger.debug("Found: VLAN: '%s'; Subnet: '%s'" % (vlan_ID, subnet))
            subnet_to_vlan[subnet] = vlan_ID

    infile.close()
    logger.info("Done parsing VLAN-file '%s'; %i VLANs found" %
                (filename, len(subnet_to_vlan)))
    return subnet_to_vlan
    
    
def parse_data_file(filename, subnet_to_vlan):
    subnets_in_file = {}
    logger.info("Parsing data-file '%s'" % filename)
    infile = open(filename)
    matcher = re.compile(r'([1234567890./]+)\s+(.*)')
    for line in infile:
        if line.startswith('#') or line.rstrip() == '':
            continue
        result = matcher.match(line)
        if result:
            subnet = result.group(1)
            desc = result.group(2).rstrip()
            vlan = subnet_to_vlan.get(subnet, None)
            
            logger.debug("Found: Subnet: '%s'; VLAN: '%s'; "
                         "Desc:'%s'" % (subnet, vlan, desc))

            subnets_in_file[subnet] = (subnet, desc, vlan)
        else:
            logger.warning("Unknown format for line: '%s'" % line)
    
    infile.close()
    logger.info("Done parsing data-file '%s'" % filename)
    return subnets_in_file
    

def compare_file_to_db(subnets_in_file, force):
    errors = []
    changes = []
    subnets_to_add = []
    perform_checks = not force
        
    s = Subnet(db)
    subnets_in_db = s.search()
    
    for row in subnets_in_db:
        subnet_ID = "%s/%s" % (row['subnet_ip'], row['subnet_mask'])

        if subnet_ID in subnets_in_file:
            # Subnet is in file; nothing should be done with it
            logger.debug("Subnet '%s' in both DB and file; leaving it alone" % subnet_ID)
            del subnets_in_file[subnet_ID]
        else:
            # Subnet is in DB, but not in file; try to remove it from DB
            try:
                logger.info("Deleting subnet '%s'" % subnet_ID)
                s.clear()
                s.find(subnet_ID)
                s.delete(perform_checks=perform_checks)
                changes.append("Deleted subnet '%s'" % subnet_ID)
            except CerebrumError, ce:
                logger.error(ce.message)
                errors.append(ce.message)

    # What is left in subnets_in_file now are subnets that should be added
    for new_subnet in subnets_in_file:
        try:
            subnet, description, vlan = subnets_in_file[new_subnet]
            logger.info("Adding subnet '%s' (%s)" % (subnet, description))
            add_subnet(subnet, description, vlan, perform_checks=perform_checks)
            changes.append("Added subnet '%s'" % subnet)
        except CerebrumError, ce:
            logger.error(ce.message)
            errors.append(ce.message)    

    return changes, errors


def usage(message=None):
    """Gives user info on how to use the program and its options."""
    if message is not None:
        print >>sys.stderr, "\n%s" % message

    print >>sys.stderr, __doc__


def main(argv=None):
    """Main processing hub for program."""
    if argv is None:
        argv = sys.argv

    # Default values for command-line options
    options = {"vlanfile": None,
               "datafile": None,
               "force": False,
               "status_recipients": None,
               "error_recipients": None,
               "mail-from": None,
               "mail-cc": None}
    
    ######################################################################
    ### Option-gathering
    try:
        opts, args = getopt.getopt(argv[1:],
                                   "hd:v:fs:e:",
                                   ["help", "datafile=",
                                    "vlanfile=", "force",
                                    "status_recipients=", "error_recipients=",
                                    "mail-from=", "mail-cc="])
    except getopt.GetoptError, error:
        usage(message=error.msg)
        return 1

    for opt, val in opts:
        if opt in ('-h', '--help',):
            usage()
            return 0
        if opt in ('-f', '--force',):
            options["force"] = True
        if opt in ('-v', '--vlanfile',):
            options["vlanfile"] = val
        if opt in ('-d', '--datafile',):
            options["datafile"] = val
        if opt in ('-s', '--status_recipients',):
            options["status_recipients"] = val
        if opt in ('-e', '--error_recipients',):
            options["error_recipients"] = val
        if opt in ('--mail-from',):
            options["mail-from"] = val
        if opt in ('--mail-cc',):
            options["mail-cc"] = val

    logger.debug("VLAN-file: '%s'" % options["vlanfile"])
    logger.debug("Datafile: '%s'" % options["datafile"])

    if not options["datafile"]:
        usage("Error: need datafile specified.")
        return 2

    ######################################################################
    ### Data-processing
    if options["vlanfile"]:
        subnet_to_vlan = parse_vlan_file(options["vlanfile"])
    else:
        subnet_to_vlan = {}        

    subnets_in_file = parse_data_file(options["datafile"], subnet_to_vlan)

    (changes, errors) = compare_file_to_db(subnets_in_file, options["force"])

    ######################################################################
    ### Feedback to interested parties
    if errors:
        mail_to = options["error_recipients"]
        subject = "Errors from subnet-import"
        mail_body = "The following errors were encountered during the import:\n\n"
        mail_body += "\n\n".join(errors)
        
        if options["force"]:
            mail_body +=  "\n\nImport forced - non-erronous changes made anyway."
            mail_body +=  "\nThe following changes were made:\n%s\n" % "\n".join(changes)
            
            logger.info("Force-committing non-erronous changes to database.")
            sendmail(mail_to, options["mail-from"], subject, mail_body, cc=options["mail-cc"])
            db.commit()            
            return 0
        
        else:
            mail_body +=  "\n\nImport not completed - no changes made."
            mail_body +=  "Fix the above problems, then rerun the import.\n"
            logger.error("Errors encountered. No changes made by import.")
            db.rollback()
            sendmail(mail_to, options["mail-from"], subject, mail_body, cc=options["mail-cc"])
            return 3
    else:
        mail_to = options["status_recipients"]
        subject = "Status from subnet-import"
        mail_body =  "Subnet-import completed without problems\n"
        if changes:
            mail_body +=  "The following changes were made:\n%s\n" % "\n".join(changes)
            logger.info("Committing all changes to database.")
            db.commit()
        else:
            mail_body +=  "No changes needed to be done\n"

        sendmail(mail_to, options["mail-from"], subject, mail_body, cc=options["mail-cc"])
        return 0
            

if __name__ == "__main__":
    logger.info("Starting program '%s'" % progname)
    return_value = main()
    logger.info("Program '%s' finished" % progname)
    sys.exit(return_value)

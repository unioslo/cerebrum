#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
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

"""
process_students (or possibly other programs) quarantine student
accounts which no longer should have permission to IT services. But,
some of the persons owning these accounts might also have other
affiliations and so it would be rather rude to quarantine their
accounts. This script removes the quarantine for such accounts.

"""

import os
import sys
import getopt

import cerebrum_path
from Cerebrum import Errors
from Cerebrum.Utils import Factory

db = Factory.get('Database')()
pe = Factory.get("Person")(db)
ac = Factory.get("Account")(db)
co = Factory.get("Constants")(db)
logger = Factory.get_logger("console")
db.cl_init(change_program="studsplat_revisor")


def usage(exitcode=0):
    print """Usage: %s [options]
    --infile         : Mandatory. Contains data about quarantined accounts
    --nosplat-file   : Accounts that should be unsplatted
    --studsplat-file : Out file containing splatted student accounts
    --unsplat        : Unsplat accounts?

    The infile should have the following format: <account id> <fnr>
    
    """ % sys.argv[0].split('/')[-1]
    sys.exit(exitcode)


def person_has_sap_aff(fnr):
    pe.clear()
    pe.find_by_external_id(co.externalid_fodselsnr, fnr)
    for row in pe.list_affiliations(person_id=pe.entity_id,
                                    source_system=co.system_sap):
        if row['affiliation'] in (co.affiliation_ansatt,
                                  co.affiliation_tilknyttet,
                                  co.affiliation_manuell):
            return True
    return False


def unsplat_account(account_id):
    ac.clear()
    ac.find(account_id)
    logger.debug("Unsplat user %s..." % ac.account_name)
    if ac.get_entity_quarantine(type=co.quarantine_auto_inaktiv):
        ac.delete_entity_quarantine(type=co.quarantine_auto_inaktiv)
        logger.info("Deleted quarantine %s for %s" % (co.quarantine_auto_inaktiv,
                                                      ac.account_name))

def check_users(acc_fnrs):
    "acc_fnrs is a list of account_id, fnr pairs"
    no_sap_affs = []
    logger.info("Investigating affiliations for %d qurantined accounts" %
                len(acc_fnrs))
    for account_id, fnr in acc_fnrs:
        try:
            if person_has_sap_aff(fnr):
                unsplat_account(account_id)
            else:
                no_sap_affs.append(account_id)
        except Errors.NotFoundError:
            logger.warn("Couldn't find person with fnr " + fnr)
            
    return no_sap_affs


def write_file(out_file, output_type, accounts):
    outf = file(out_file, 'w')
    for acc_id in accounts:
        try:
            ac.clear()
            ac.find(acc_id)            
            if output_type == 'email-addr':
                outf.write(ac.get_primary_mailaddress() + os.linesep)
            else:
                outf.write(ac.account_name + os.linesep)
        except Errors.NotFoundError:
            logger.warn("Couldn't find account " + acc_id)
    outf.close()
    logger.info("Wrote %ss to %s" % (output_type, out_file))


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   "di:s:e",
                                   ['dryrun',
                                    'infile=',
                                    'studsplat-file=',
                                    'output-emailaddr'])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    dryrun = False
    infile = None
    out_studsplat_file = None
    output_type = 'account'
    for option, value in opts:
        if option in ('-d', '--dryrun',):
            dryrun = True
        elif option in ('-i', '--infile',):
            infile = value
        elif option in ('-s', '--studsplat-file',):
            out_studsplat_file = value
        elif option in ('-e', '--output-emailaddr',):
            output_type = 'email-addr'

    try:
        f = file(infile)
        acc_fnrs = [x.split() for x in f.readlines()]
        f.close()
    except:
        usage(1)

    no_aff = check_users(acc_fnrs)
    logger.debug("Number of splatted students: %d " % len(no_aff))
    write_file(out_studsplat_file, output_type, no_aff)
    
    if dryrun:
        db.rollback()
        logger.info("DRYRUN: Roll back changes")
    else:
        db.commit()
        logger.info("Committing changes")

        
if __name__ == '__main__':
    main()

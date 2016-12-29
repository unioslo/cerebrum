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
accounts.

This script removes the quarantine for such accounts. In addition
student affiliation can be removed.

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
logger = Factory.get_logger("cronjob")
db.cl_init(change_program="studsplat_revisor")


def usage(exitcode=0):
    print """Usage: %s [options]
    --infile <file> : Mandatory. Contains data about quarantined accounts
    --studsplat-file <file> : Outfile containing splatted student accounts
    --remove-affiliation : remove student affiliation for splatted accounts?
    --output-email-addr : Output email-addrs in addition to account
                          names for splatted accounts
    --dryrun : don't perform any changes
    

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


def remove_quarantine(account_id, quarantine_type=co.quarantine_auto_inaktiv):
    ac.clear()
    try:
        ac.find(account_id)
        if ac.get_entity_quarantine(qtype=quarantine_type):
            ac.delete_entity_quarantine(quarantine_type)
            ac.write_db()
            logger.debug("Deleted quarantine %s for %s" % (quarantine_type,
                                                           ac.account_name))
    except Errors.NotFoundError:
            logger.warn("Couldn't Delete quarantine %s for %s" % (
                quarantine_type, account_id))


def remove_affiliation(account_id, affiliation=co.affiliation_student):
    affs = ac.list_accounts_by_type(account_id=account_id,
                                    affiliation=affiliation)
    for row in affs:
        try:
            ac.clear()
            ac.find(account_id)
            ac.del_account_type(row['ou_id'], affiliation)
            ac.write_db()
            logger.debug("Remove affiliation %s for account %s" % (
                affiliation, ac.account_name))
        except Errors.NotFoundError:
            logger.warn("Couldn't remove affiliation %s for account %s" % (
                affiliation, account_id))


def check_users(acc_fnrs):
    "acc_fnrs is a list of account_id, fnr pairs"
    has_sap_aff = []
    no_sap_affs = []
    logger.info("Investigating affiliations for %d qurantined accounts" %
                len(acc_fnrs))
    for account_id, fnr in acc_fnrs:
        try:
            if person_has_sap_aff(fnr):
                has_sap_aff.append(account_id)
            else:
                no_sap_affs.append(account_id)
        except Errors.NotFoundError:
            logger.warn("Couldn't find person with fnr " + fnr)
            
    return has_sap_aff, no_sap_affs


def write_file(out_file, output_type, accounts):
    outf = file(out_file, 'w')
    for acc_id in accounts:
        try:
            ac.clear()
            ac.find(acc_id)
            out_txt = ac.account_name
            if output_type == 'email-addrs':
                out_txt += ";" + ac.get_primary_mailaddress()
            outf.write(out_txt + os.linesep)
        except Errors.NotFoundError:
            logger.warn("Couldn't find account " + acc_id)
    outf.close()
    logger.info("Wrote splatted accounts to %s" % out_file)


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   "di:rs:e",
                                   ['dryrun',
                                    'infile=',
                                    'remove-stud-aff',
                                    'studsplat-file=',
                                    'output-emailaddr'])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    dryrun = False
    infile = None
    remove_stud_aff = False
    out_studsplat_file = None
    output_type = 'accounts'
    for option, value in opts:
        if option in ('-d', '--dryrun',):
            dryrun = True
        elif option in ('-i', '--infile',):
            infile = value
        elif option in ('-r', '--remove-stud-aff',):
            remove_stud_aff = True
        elif option in ('-s', '--studsplat-file',):
            out_studsplat_file = value
        elif option in ('-e', '--output-emailaddr',):
            output_type = 'email-addrs'

    try:
        f = file(infile)
        acc_fnrs = [x.split() for x in f.readlines()]
        f.close()
    except:
        usage(1)

    # Check all splatted accounts
    has_sap_aff, no_sap_aff = check_users(acc_fnrs)
    logger.info("Number of accounts to unsplat: %d " % len(has_sap_aff))

    # Remove quarantine for SAP persons 
    for account_id in has_sap_aff:
        remove_quarantine(account_id)
    
    # Remove student affiliation?
    if remove_stud_aff:
        for account_id in has_sap_aff:
            remove_affiliation(account_id, affiliation=co.affiliation_student)
            
    logger.info("Number of splatted students: %d " % len(no_sap_aff))
    write_file(out_studsplat_file, output_type, no_sap_aff)
    
    if dryrun:
        db.rollback()
        logger.info("DRYRUN: Roll back changes")
    else:
        db.commit()
        logger.info("Committing changes")

        
if __name__ == '__main__':
    main()

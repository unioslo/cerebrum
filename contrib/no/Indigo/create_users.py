#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2006 University of Oslo, Norway
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

## Process changelog entries, create user for persons registered
## by ABC-import 

import sys, os, getopt, time, string, pickle, re

import cerebrum_path
import cereconf
from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import CLHandler
from Cerebrum.Constants import _SpreadCode

def build_account(person_id):
    fname = None
    lname = None
    uname = None
    person.clear()
    try:
        person.find(person_id)
    except Errors.NotFoundError:
        logger.error("Could not find person %s.", person_id)
        return None

    person_aff = person.get_affiliations()

    acc_id = None
    acc_id = account.list_accounts_by_owner_id(person_id)
    
    if acc_id == []:
        fname = person.get_name(constants.system_cached, constants.name_first)
        lname = person.get_name(constants.system_cached, constants.name_last)
        unames = account.suggest_unames(constants.account_namespace, fname, lname)

        if unames[0] == None:
            logger.error('Could not generate user name for %s.', person_id)
            return None
        account.clear()
        account.populate(unames[0], constants.entity_person, person_id,
                         None, default_creator_id, default_expire_date)
        pwd =  account.make_passwd(unames[0])
        account.write_db()
        account.set_password(pwd)

        for s in cereconf.BOFHD_NEW_USER_SPREADS:
            account.add_spread(constants.Spread(s))
        account.write_db()

        if person_aff:
            for row in person_aff:
                account.set_account_type(row['ou_id'], row['affiliation'])
        account.write_db()
        return account.entity_id
        
def main():
    global db, constants, logger, person, account
    global default_creator_id, default_expire_date

    db = Factory.get('Database')()
    db.cl_init(change_program='auto_create')
    acc = Factory.get('Account')(db)
    constants = Factory.get('Constants')(db)
    clconstants = Factory.get('CLConstants')(db)
    cl_handler = CLHandler.CLHandler(db)
    logger = Factory.get_logger('cronjob')
    person = Factory.get('Person')(db)
    account = Factory.get('Account')(db)
    
    acc.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    default_creator_id = acc.entity_id
    default_expire_date = None

    cl_events = []
    new_acc_id = None
    
    try:
        cl_events = cl_handler.get_events('auto_create',
                                          (clconstants.person_create,))
        if cl_events == []:
            logger.info("Nothing to do.")
            sys.exit(0)
            
        for event in cl_events:
            if event['change_type_id'] == clconstants.person_create:
                new_acc_id = build_account(event['subject_entity'])
                if new_acc_id == None:
                    logger.error('Could not create an account for %s',
                                 event['subject_entity'])
                    continue
                cl_handler.confirm_event(event)
    except TypeError, e:
        logger.warn("No such event, %s" % e)
        return None
    cl_handler.commit_confirmations()
    
if __name__ == '__main__':
    main()

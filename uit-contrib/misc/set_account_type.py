#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2002, 2003 University of Oslo, Norway
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
This script sets account_type for all accounts missing entries in
this table. The script will try to set account_type according to the
person_affiliation_source. if person_affiliation_source only contains
expired entries, a non-expired entry will be selected. The script will
make sure that at least 1 of student/employee affiliation is created
for each account.
"""


import argparse
import sys

import Cerebrum.logutils

from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import add_commit_args

progname = __file__.split("/")[-1]
db = Factory.get('Database')()
const = Factory.get('Constants')(db)
person = Factory.get('Person')(db)
account = Factory.get('Account')(db)
db.cl_init(change_program=progname)


# return a list of tuple [(owner_id, account_id),...]
# of all accounts missing account_type
def process_accounts(accounts):
    account_list = []
    counter = 0
    for single_account in accounts:
        counter = counter + 1
        account.clear()
        account.find(single_account['account_id'])
        # only collect accounts whos owner is a person
        if account.owner_type == const.entity_person:
            types = account.get_account_types(filter_expired=False)
            if len(types) == 0:
                # this account does not have account_type. collect it
                new_tuple = (single_account['owner_id'],
                             single_account['account_id'])
                # print new_tuple
                account_list.append(new_tuple)
        # write some  feedback to the user
        if(counter % 100) == 0:
            sys.stdout.write(".")
            sys.stdout.flush()
    # return complete list to caller
    return account_list


# set account type for accounts that have none
# The function will try to set account type to reflect any active affiliations.
# is the account owner have none active affiliations, the function will try to
# set account type based on expired ones. An error message is returned to the
# user if the owner have no affiliations at all.
def set_account_type(info_list):
    counter = 0
    error_list = []
    success_list = []
    # get active affiliations, set account type based on these
    for entry in info_list:
        # print "set account type for account:%s" % entry[1]
        person.clear()
        person.find(entry[0])
        account.clear()
        account.find(entry[1])
        affs = person.get_affiliations(include_deleted=True)
        if len(affs) == 0:
            single_error = ("can't set account type for account:{}, owner:{} "
                            "has no affiliations").format(entry[1], entry[0])
            error_list.append(single_error)

        else:
            # find active affiliations
            have_valid_aff = False
            for aff in affs:
                if aff['deleted_date'] is None:
                    # has active affiliation. set account type based on this.
                    ou_id = aff['ou_id']
                    affiliation = aff['affiliation']
                    account.set_account_type(ou_id, affiliation)
                    s = "account:{}, added account_type:{} - {}".format(
                        entry[1], affiliation, ou_id)
                    success_list.append(s)
                    have_valid_aff = True
            if not have_valid_aff:
                # user does not have any valid affiliations.
                # set account type based on expired affiliations
                for aff in affs:
                    ou_id = aff['ou_id']
                    affiliation = aff['affiliation']
                    account.set_account_type(ou_id, affiliation)
                    s = "account:{}, added account_type:{} - {}".format(
                        entry[1], affiliation, ou_id)
                    success_list.append(s)
        # write some  feedback to the user
        counter += 1
        if(counter % 100) == 0:
            sys.stdout.write(".")
            sys.stdout.flush()
    for single_error in error_list:
        print "%s" % single_error
    for success in success_list:
        print "%s" % success


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)

    # get list of all accounts in the database
    print "getting accounts..."
    all_accounts = account.list(filter_expired=False, fetchall=True)

    # get list of all accounts missing account_type
    print "getting accounts missing type..."
    accounts_missing_type = process_accounts(all_accounts)

    # set account type for accounts that have none
    print "setting account type..."
    set_account_type(accounts_missing_type)

    # commit or rollback
    if args.commit:
        db.commit()
        print "commit"
    else:
        db.rollback()
        print "rollback"


if __name__ == '__main__':
    main()

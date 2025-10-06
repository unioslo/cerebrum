#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2023 University of Oslo, Norway
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
Script producing csv of system users. Ref CRB-4037.
Output is produced so that IT-sikkerhet gets an overview and control of the existing system acounts.
The columns of the csv file is as follows: 
account_name:string owner_group:string creator_name:string
created_at:date quarantine_type:list spreads:list 
"""

import argparse
import csv
import logging

import cereconf
import Cerebrum.Errors
import Cerebrum.logutils
import Cerebrum.logutils.options

from Cerebrum.modules.audit.auditdb import AuditLogAccessor
from Cerebrum.modules.audit.formatter import (
    AuditRecordFormatter,
    AuditRecordProcessor,
)

from Cerebrum.Utils import Factory

logger = logging.getLogger(__name__)
AC_ID_TO_NAME = {}
GR_ID_TO_NAME = {}

def get_owner_name(gr, owner_id):
    if owner_id not in GR_ID_TO_NAME:
        gr.clear()
        try:
            gr.find(owner_id)
        except Cerebrum.Errors.NotFoundError:
            logger.error("Could not find owner_id %d", owner_id)
        GR_ID_TO_NAME[owner_id] = str(gr.group_name)
    return GR_ID_TO_NAME[owner_id]


def get_creator_name(ac, creator_id):
    if creator_id not in AC_ID_TO_NAME:
        ac.clear()
        try:
            ac.find(creator_id)
        except Cerebrum.Errors.NotFoundError:
            logger.error("Could not find creator_id %d", creator_id)
        AC_ID_TO_NAME[creator_id] = str(ac.get_account_name())
    return AC_ID_TO_NAME[creator_id]


def get_system_groups(gr, account_id):
    # Per IT security routine, all system accounts should be a member of
    # one, and only one, of these two groups. Many older accounts are not.
    memberships = ''
    for group in ('uio-system-interactive', 'uio-system-noninteractive'):
        gr.clear()
        gr.find_by_name(group)
        if gr.has_member(account_id):
            if not memberships:
                memberships = group
            else:
                # This shouldn't be the case for any accounts
                # but if it is, let's return them as a list
                memberships = [memberships, group]
    return memberships


def get_last_audit_log_entry(account_id, ala, arp):
    # Return the last entry in the audit log for this account

    # We want everything, both direct log entries for this account and
    # any group membership changes
    records = list(ala.search(**{'entities': account_id}))
    records += list(ala.search(**{'targets': account_id}))

    last_record = arp(sorted(records, key=lambda r: r.timestamp)[-1])
    try:
        last_timestamp = last_record.timestamp.strftime("%Y-%m-%d")
    except AttributeError as e:
        # Some timestamps are strings...
        last_timestamp = last_record.timestamp.split(' ')[0]

    last_operator = last_record.metadata['operator_name']
    if last_operator == cereconf.INITIAL_ACCOUNTNAME:
        # If bootstrap_account is the operator, add the change_program as well
        last_operator += ' ({})'.format(last_record.metadata['change_program'])

    return (last_timestamp, last_operator, str(last_record.change_type))



def get_account_info(ac, co, gr, ala, arp):
    ret_acc = {}

    ret_acc['account_name'] = ac.get_account_name()
    ret_acc['created_at'] = ac.created_at.strftime("%Y-%m-%d")
    ret_acc['spreads'] = [str(co.human2constant(spread['spread'])) for spread in ac.get_spread()] or ''
    ret_acc['owner_name'] = get_owner_name(gr, ac.owner_id)

    active_quarantines = ac.get_entity_quarantine(only_active=True)
    ret_acc['quarantine_type'] = [str(co.human2constant(quar['quarantine_type'])) for quar in active_quarantines] or ''
    try:
        ret_acc['quarantined_since'] = min(quar['start_date'] for quar in active_quarantines)
    except ValueError:
        ret_acc['quarantined_since'] = ''

    ret_acc['system_groups'] = get_system_groups(gr, ac.entity_id)

    ret_acc['last_timestamp'], ret_acc['last_operator'], ret_acc['last_change'] = get_last_audit_log_entry(ac.entity_id, ala, arp)

    ret_acc['contactinfo'] = ', '.join([contactinfo['contact_value'] for contactinfo in ac.get_contact_info(type=co.contact_email)])

    # NOTE: Do this last, as it re-uses `ac` and thus overwrites the dynamic Account object...
    ret_acc['creator_name'] = get_creator_name(ac, ac.creator_id)

    return (ret_acc['account_name'], ret_acc['owner_name'], ret_acc['creator_name'],
            ret_acc['created_at'], ret_acc['quarantine_type'], ret_acc['quarantined_since'],
            ret_acc['system_groups'], ret_acc['spreads'], ret_acc['contactinfo'],
            ret_acc['last_timestamp'], ret_acc['last_operator'], ret_acc['last_change'])


def generate_csv(db, output_file):
    ac = Factory.get('Account')(db)
    co = Factory.get('Constants')(db)
    gr = Factory.get('Group')(db)
    ala = AuditLogAccessor(db)
    arp = AuditRecordProcessor()

    logger.info("Fetching system accounts")
    system_accounts = ac.search(owner_type=co.entity_group)
    logger.info("Found %d system accounts", len(system_accounts))
    with open(output_file, "w") as stream:
        writer = csv.writer(stream)
        writer.writerow(("account name", "owner group", "creator", "created",
                         "quarantines", "quarantined since", "member of", "spreads", "contactinfo",
                         "last changed", "changed by", "last change"))
        for system_account in system_accounts:
            logger.info("Handling system account with id: %d", system_account['account_id'])
            ac.clear()
            ac.find(system_account['account_id'])
            account_row = get_account_info(ac, co, gr, ala, arp)

            writer.writerow(account_row)
        logger.info("Finished handling system accounts")
    logger.info("Closed file")


def main(inargs=None):
    db = Factory.get('Database')()
    parser = argparse.ArgumentParser(
        description="Script outputting a csv containing information of all systemuser",
    )
    parser.add_argument(
        '-o', '--output_file',
        required=True,
        help='Where to write csv output of system accounts',
        metavar='<filename>'
    )
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    filename = args.output_file
    generate_csv(db, filename)

    logger.info("Finished generating csv")


if __name__ == '__main__':
    main()

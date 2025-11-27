#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2023-2025 University of Oslo, Norway
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
Generate a report of system accounts.

System accounts are all non-personal user accounts.  The report is intended for
IT-sikkerhet (ref CRB-4037), to review active system accounts in Cerebrum.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import logging

import six

import cereconf
import Cerebrum.Errors
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.modules.audit.auditdb import AuditLogAccessor
from Cerebrum.utils import csvutils
from Cerebrum.utils import date_compat
from Cerebrum.utils import file_stream


logger = logging.getLogger(__name__)


def format_date(date_like):
    date = date_compat.get_date(date_like)
    if date:
        return date.isoformat()
    else:
        return ""


def format_list(values):
    return ", ".join(
        v if isinstance(v, six.text_type) else repr(v)
        for v in (values or [])
    )


def get_group_by_name(db, group_name):
    gr = Factory.get("Group")(db)
    gr.find_by_name(group_name)
    return gr


class NameCache(object):

    def __init__(self, db):
        self.db = db
        self.group_names = {}
        self.account_names = {}

    def get_group_name(self, group_id):
        if group_id not in self.group_names:
            gr = Factory.get("Group")(self.db)
            try:
                gr.find(group_id)
                self.group_names[group_id] = gr.group_name
            except Cerebrum.Errors.NotFoundError:
                logger.warning("No group id: %d", group_id)
                self.group_names[group_id] = None
        return self.group_names[group_id]

    def get_account_name(self, account_id):
        if account_id not in self.account_names:
            ac = Factory.get("Account")(self.db)
            try:
                ac.find(account_id)
                self.account_names[account_id] = ac.account_name
            except Cerebrum.Errors.NotFoundError:
                logger.warning("No account id: %d", account_id)
                self.account_names[account_id] = None
        return self.account_names[account_id]


class RecordFetcher(object):

    # All system accounts should be a member of *one* of these groups
    system_groups = ('uio-system-interactive', 'uio-system-noninteractive')

    def __init__(self, db):
        self.db = db
        self.names = NameCache(db)
        self.auditlog = AuditLogAccessor(db)
        self._system_groups = [
            get_group_by_name(db, name)
            for name in self.system_groups]

    def get_memberships(self, account_id):
        """ Get account memberships in system groups. """
        return [gr.group_name for gr in self._system_groups
                if gr.has_member(account_id)]

    def get_last_audit_record(self, entity_id):
        """ Get the latest audit log record for an entity. """
        search = self.auditlog.search
        records = sorted(
            list(search(entities=entity_id, descending=True, limit=1))
            + list(search(targets=entity_id, descending=True, limit=1)),
            key=lambda r: r.timestamp,
        )
        return records[-1] if records else None
        audit_at, audit_by, audit_type = None

    def get_account_row(self, account_id):
        ac = Factory.get("Account")(self.db)
        co = ac.const
        ac.find(account_id)

        owner_name = self.names.get_group_name(ac.owner_id)
        creator_name = self.names.get_account_name(ac.creator_id)

        active_quarantines = ac.get_entity_quarantine(only_active=True)
        quarantines = [six.text_type(co.Quarantine(row['quarantine_type']))
                       for row in active_quarantines]
        quarantined_at = (min(row['start_date'] for row in active_quarantines)
                          if active_quarantines else None)

        system_groups = self.get_memberships(ac.entity_id)

        spreads = [six.text_type(co.Spread(spread['spread']))
                   for spread in ac.get_spread()]

        contactinfo = [row['contact_value']
                       for row in ac.get_contact_info(type=co.contact_email)]

        # Find changes related to this accountany group membership changes
        record = self.get_last_audit_record(ac.entity_id)
        if record:
            audit_at = record.timestamp
            operator_name = record.metadata['operator_name']
            if operator_name == cereconf.INITIAL_ACCOUNTNAME:
                change_program = record.metadata['change_program']
                audit_by = "{} ({})".format(operator_name, change_program)
            else:
                audit_by = operator_name
            audit_type = six.text_type(record.change_type)
        else:
            audit_at = audit_by = audit_type = None

        return {
            F_ACCOUNT_NAME: ac.account_name,
            F_ACCOUNT_OWNER: owner_name or "",
            F_CREATOR_NAME: creator_name or "",
            F_CREATED_AT: format_date(ac.created_at),
            F_QUARANTINES: format_list(quarantines),
            F_QUARANTINED_AT: format_date(quarantined_at),
            F_MEMBERSHIPS: format_list(system_groups),
            F_SPREADS: format_list(spreads),
            F_CONTACTS: format_list(contactinfo),
            F_AUDITLOG_AT: format_date(audit_at),
            F_AUDITLOG_BY: audit_by or "",
            F_AUDITLOG_TYPE: audit_type or "",
        }


# CSV Fields

F_ACCOUNT_NAME = "account name"
F_ACCOUNT_OWNER = "owner group"
F_CREATOR_NAME = "creator"
F_CREATED_AT = "created"
F_QUARANTINES = "quarantines"
F_QUARANTINED_AT = "quarantined since"
F_MEMBERSHIPS = "member of"
F_SPREADS = "spreads"
F_CONTACTS = "contactinfo"
F_AUDITLOG_AT = "last changed"
F_AUDITLOG_BY = "changed by"
F_AUDITLOG_TYPE = "last change"


CSV_FIELDS = (
    F_ACCOUNT_NAME,
    F_ACCOUNT_OWNER,
    F_CREATOR_NAME,
    F_CREATED_AT,
    F_QUARANTINES,
    F_QUARANTINED_AT,
    F_MEMBERSHIPS,
    F_SPREADS,
    F_CONTACTS,
    F_AUDITLOG_AT,
    F_AUDITLOG_BY,
    F_AUDITLOG_TYPE,
)


def generate_records(db):
    ac = Factory.get('Account')(db)
    records = RecordFetcher(db)
    logger.debug("Fetching system accounts...")
    system_accounts = ac.search(owner_type=ac.const.entity_group)
    logger.info("Found %d system accounts", len(system_accounts))

    logger.debug("Fetching account details...")
    for i, row in enumerate(system_accounts, 1):
        yield records.get_account_row(row['account_id'])
        if not (i % 100):
            logger.debug("processed %d accounts...", i)
    logger.info("Finished generating records")


def write_records(records, filename):
    logger.debug("Writing to %s", filename)
    count = 0
    with file_stream.get_output_context(filename, encoding="utf-8") as f:
        writer = csvutils.UnicodeDictWriter(f, CSV_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow(record)
            count += 1
    logger.debug("Wrote %d account records", count)
    logger.info("Wrote CSV report to %s", repr(f))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate a system users CSV report",
    )
    parser.add_argument(
        "-o", "--output-file", "--output_file",
        required=True,
        help="Write CSV report to %(metavar)s",
        metavar="<filename>"
    )
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(argv)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    write_records(
        generate_records(Factory.get('Database')()),
        args.output_file,
    )

    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()

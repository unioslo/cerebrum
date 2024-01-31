#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2020-2023 University of Oslo, Norway
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
"""This is a bofhd module for commands required by WOFH/brukerinfo."""

import datetime
from six import text_type

from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.group.memberships import GroupMemberships
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.cmd_param import (Command, AccountName)
from Cerebrum.utils import date_compat


class BofhdWofhCommands(BofhdCommonMethods):

    all_commands = {}
    hidden_commands = {}
    authz = BofhdAuth

    #
    # wofh all_account_memberships
    #
    hidden_commands['wofh_all_group_memberships'] = Command(
        ('wofh', 'all_group_memberships'),
        AccountName()
    )

    def wofh_all_group_memberships(self, operator, account_name):
        """
        Hidden command used by brukerinfo/WOFH.

        Returns all groups associated with an account. If a account is the
        primary we add any person groups as if primary account was a member.
        """
        account = self._get_entity('account', account_name)
        member_id = [account.entity_id]

        if account.owner_type == self.const.entity_person:
            person = Utils.Factory.get('Person')(self.db)
            person.clear()
            person.find(account.owner_id)
            if account.entity_id == person.get_primary_account():
                # Found primary account, add person memberships.
                member_id.append(person.entity_id)

        group_memberships = GroupMemberships(self.db)
        return [
            {'entity_id': row['group_id'],
             'group': row['name'],
             'description': row['description'],
             'expire_date': row['expire_date'],
             'group_type': text_type(self.const.GroupType(row['group_type']))
             }
            for row in group_memberships.get_groups(
                member_id)]

    #
    # wofh guests
    #
    hidden_commands['wofh_get_guests'] = Command(
        ('wofh', 'get_guests')
    )

    def wofh_get_guests(self, operator):
        """
        Hidden command used by brukerinfo/WOFH.

        Returns a list of "guests" at the operators departments.
        """
        person = Utils.Factory.get('Person')(self.db)
        account = Utils.Factory.get('Account')(self.db)
        ou = Utils.Factory.get('OU')(self.db)

        try:
            person.find(operator.get_owner_id())
        except Errors.NotFoundError:
            # Operator is not a person.
            return None

        # Get all OUs where the operator is employed.
        ou_ids = []
        for aff in person.get_affiliations():
            if (self.const.PersonAffiliation(aff['affiliation'])
                    == self.const.affiliation_ansatt):
                ou_ids.append(aff['ou_id'])

        guests = []
        for ou_id in ou_ids:
            affs = person.list_affiliations(
                affiliation=self.const.affiliation_tilknyttet,
                ou_id=ou_id,
                include_deleted=True)

            ou.clear()
            ou.find(ou_id)
            stedkode = ou.get_stedkode()
            for aff in affs:
                guest = {}
                guest['unit'] = stedkode
                # Check if deleted_date is
                deleted_date = date_compat.get_date(aff['deleted_date'])
                cutoff = datetime.date.today() - datetime.timedelta(days=30)
                if (deleted_date and deleted_date < cutoff):
                    # Skip old deleted affiliations
                    continue

                person.clear()
                account.clear()
                try:
                    person.find(aff['person_id'])
                except Errors.NotFoundError:
                    # Person missing, db inconsistency.. Skipping.
                    continue
                try:
                    account.find(person.get_primary_account())
                    guest['uname'] = account.account_name
                except Errors.NotFoundError:
                    guest['uname'] = ''

                if deleted_date:
                    guest['deleted_date'] = deleted_date.isoformat()
                else:
                    guest['deleted_date'] = ''
                create_date = date_compat.get_date(aff['create_date'])
                guest['create_date'] = create_date.isoformat()
                names = person.get_names(variant=self.const.name_full)
                if names and len(names) > 0:
                    guest['name'] = names[0]['name']
                else:
                    guest['name'] = affs['person_id']

                # Same guest at a different unit is ok,
                # else keep freshest account only.
                if not guests:
                    guests.append(guest)
                else:
                    counter = 0
                    for present in guests:
                        if (guest['uname'] == present['uname']
                                and guest['unit'] == present['unit']):
                            if guest['create_date'] > present['create_date']:
                                guests[counter] = guest
                            break
                        counter += 1
                    if counter == len(guests):
                        guests.append(guest)
        return guests

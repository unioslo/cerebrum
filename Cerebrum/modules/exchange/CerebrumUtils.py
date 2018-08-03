#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2018 University of Oslo, Norway
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
"""Utility functions used by ExchangeEventHandler.

This file consists mainly of badly refactored code."""

from __future__ import unicode_literals

import logging
import pickle

from six import text_type

from Cerebrum.Utils import Factory
from Cerebrum.utils import json
from Cerebrum.modules.Email import EmailDomain
from Cerebrum.modules.Email import EmailQuota
from Cerebrum.modules.Email import EmailForward
from Cerebrum.modules.exchange.ExchangeGroups import DistributionGroup
from Cerebrum import Errors

# TODO: Catch all possible errors here. Raise something useful, so
# the integration won't crash, and can requeue the event (or something)

logger = logging.getLogger(__name__)


class CerebrumUtils(object):
    """Utility-class containing often used functions for Exchange."""
    def __init__(self):
        """Initialize the Utils."""
        self.db = Factory.get('Database')(client_encoding='UTF-8')
        self.en = Factory.get('Entity')(self.db)
        self.ac = Factory.get('Account')(self.db)
        self.pe = Factory.get('Person')(self.db)
        self.gr = Factory.get('Group')(self.db)
        self.co = Factory.get('Constants')(self.db)
        self.ed = EmailDomain(self.db)
        self.eq = EmailQuota(self.db)
        self.ef = EmailForward(self.db)
        self.et = Factory.get('EmailTarget')(self.db)
        self.dg = DistributionGroup(self.db)

####
# Person related methods
####
    def get_person_accounts(self, person_id, spread=None):
        """Return a list of account information.

        :type person_id: int
        :param person_id: The person id to look up by.

        :rtype: list
        :return: A list of (account_id, username) tuples."""
        ret = [(x['account_id'], x['name']) for x in
               self.ac.search(owner_id=person_id,
                              owner_type=self.co.entity_person,
                              spread=self.co.spread_exchange_account)]
        self.db.rollback()
        return ret

    def get_person_names(self, account_id=None, person_id=None):
        """Return a persons names.

        :type account_id: int
        :param account_id: The user to look up names by.

        :type person_id: int
        :param person_id: The person to look up names by.

        :rtype: tuple
        :return: (first_name, last_name, full name).
        """

        # TODO: search_name_with_language?
        if account_id:
            self.ac.clear()
            self.ac.find(account_id)
            self.pe.clear()
            self.pe.find(self.ac.owner_id)
        elif person_id:
            self.pe.clear()
            self.pe.find(person_id)
        else:
            raise AssertionError('Called w/o person or account id')

        ret = (self.pe.get_name(self.co.system_cached, self.co.name_first),
               self.pe.get_name(self.co.system_cached, self.co.name_last),
               self.pe.get_name(self.co.system_cached, self.co.name_full,))
        self.db.rollback()
        return ret

    def get_person_membership_groupnames(self, person_id):
        """List all the groups the person is a member of.

        :type person_id: int
        :param person_id: The persons entity_id.

        :rtype: list
        :return: list(string) of groupnames."""
        ret = [x['group_name'] for x in self.gr.search_members(
            member_id=person_id, indirect_members=True)]
        self.db.rollback()
        return ret

    def is_electronic_reserved(self, person_id=None, account_id=None):
        """Check if a person has reserved themself from listing.

        :type person_id: int
        :param person_id: The persons entity_id.

        :type account_id: int
        :param account_id: The accounts entity_id.

        :rtype: bool
        :return: True if reserved, False otherwise."""
        if person_id:
            self.pe.clear()
            self.pe.find(person_id)
            ret = self.pe.has_e_reservation()
        elif account_id:
            self.ac.clear()
            self.ac.find(account_id)
            ret = self.ac.owner_has_ereservation()
        # TODO: This is sane?
        else:
            ret = True
        self.db.rollback()
        return ret

####
# Account related methods
####

    def get_account_mailaddrs(self, account_id):
        """Collect mailaddresses of an account.

        :type account_id: int
        :param account_id: The account_id representing the object.

        :rtype: list
        :return: A list of addresses."""
        self.et.clear()
        self.et.find_by_target_entity(account_id)
        addrs = ['%s@%s' % (x['local_part'], x['domain'])
                 for x in self.et.get_addresses()]
        self.db.rollback()
        return addrs

    def get_account_forwards(self, account_id):
        """Collect an accounts forward addresses.

        :param int account_id: The account_id representing the object.
        :return: A list of forward addresses."""
        self.ef.clear()
        self.ef.find_by_target_entity(account_id)
        r = []
        for fwd in self.ef.get_forward():
            # Need to do keys() for now, db_row is stupid.
            if 'enable' in fwd.keys() and fwd['enable'] == 'T':
                r.append(fwd['forward_to'])
        self.db.rollback()
        return r

    def get_account_local_delivery(self, account_id):
        """Check if this account should have local delivery.

        :param int account_id: The account_id representing the object.
        :rtype: bool
        :return: Local delivery on or off."""
        self.ef.clear()
        self.ef.find_by_target_entity(account_id)
        return self.ef.local_delivery

    def get_account_name(self, account_id):
        """Return information about the account.

        :type account_id: int
        :param acccount_id: The accounts entity id.

        :rtype: string
        :return: The accounts name."""
        self.ac.clear()
        self.ac.find(account_id)
        ret = self.ac.account_name
        self.db.rollback()
        return ret

    def get_account_owner_info(self, account_id):
        """Return the type and id of the accounts owner.

        :type account_id: int
        :param acccount_id: The accounts entity id.

        :rtype: tuple
        :return: (entity_type, entity_id)."""
        self.ac.clear()
        self.ac.find(account_id)
        ret = (self.ac.owner_type, self.ac.owner_id)
        self.db.rollback()
        return ret

    def get_account_spreads(self, account_id):
        """Return the accounts spread codes.

        :type account_id: int
        :param acccount_id: The accounts entity id.

        :rtype: list
        :return: A list of the accounts spread codes."""
        self.ac.clear()
        self.ac.find(account_id)
        ret = [x['spread'] for x in self.ac.get_spread()]
        self.db.rollback()
        return ret

    def get_account_primary_email(self, account_id):
        """Return the accounts primary address.

        :type account_id: int
        :param acccount_id: The accounts entity id.

        :rtype: str
        :return: The accounts primary email-address."""
        self.ac.clear()
        self.ac.find(account_id)
        ret = self.ac.get_primary_mailaddress()
        self.db.rollback()
        return ret

    def get_account_id(self, uname):
        """Get an accounts entity id.

        :type uname: str
        :param uname: The users name.

        :rtype: int
        :return: The entity id of the account."""
        self.ac.clear()
        self.ac.find_by_name(uname)
        ret = self.ac.entity_id
        self.db.rollback()
        return ret

    def get_primary_account(self, person_id):
        """Get a persons primary account.

        :type person_id: int
        :param person_id: The persons entity id.

        :rtype: int
        :return: The primary accounts entity_id or None if no primary."""
        self.pe.clear()
        self.pe.find(person_id)
        ret = self.pe.get_primary_account()
        self.db.rollback()
        return ret

    def get_account_group_memberships(self, uname, group_spread):
        """Get a list of group names, which the user (and users owner, if
        person), is a member of.

        :type uname: string
        :param uname: The accounts name.

        :type group_spread: _SpreadCode
        :param group_spread: Spread to filter groups by.

        :rtype: list(tuple)
        :return: A list of tuples contining group-name and -id."""
        self.ac.clear()
        self.ac.find_by_name(uname)

        groups = []

        # Fetch the groups the person is a member of
        if self.ac.owner_type == self.co.entity_person:
            for group in self.gr.search(member_id=self.ac.owner_id,
                                        spread=group_spread,
                                        indirect_members=True):
                groups.append((group['name'], group['group_id']))

        # Fetch the groups the account is a member of
        for group in self.gr.search(member_id=self.ac.entity_id,
                                    spread=group_spread,
                                    indirect_members=True):
            groups.append((group['name'], group['group_id']))

        self.db.rollback()
        return groups

####
# Group related methods
####

    def construct_group_names(self, uname, gname):
        """Construct Exchange related group names.

        :param str uname: The users username.
        :param str gname: The owning groups groupname.

        :rtype: tuple(str)
        :return: A tuple consisting of FirstName, LastName and DisplayName."""
        fn = uname
        ln = '(owner: %s)' % gname
        dn = '%s (owner: %s)' % (uname, gname)
        return (fn, ln, dn)

    def get_group_information(self, group_id):
        """Get a groups name and description.

        :type group_id: int
        :param group_id: The groups entity id.

        :rtype: tuple
        :return: The groups name and description."""
        # This function is kinda generic. We don't care
        # (yet) if it's a distribution or security group.
        r = self.gr.search(group_id=group_id)[0]
        ret = (r['name'], r['description'])
        self.db.rollback()
        return ret

    def get_group_id(self, group_name):
        """Get a groups entity_id.

        :type group_name: str
        :param group_name: The groups name.

        :rtype: int
        :return: The groups entity_id."""
        self.gr.clear()
        self.gr.find_by_name(group_name)
        ret = self.gr.entity_id
        self.db.rollback()
        return ret

    def get_group_spreads(self, group_id):
        """Return the groupss spread codes.

        :type group_id: int
        :param group_id: The accounts entity id.

        :rtype: list
        :return: A list of the accounts spread codes."""
        self.gr.clear()
        self.gr.find(group_id)
        ret = [x['spread'] for x in self.gr.get_spread()]
        self.db.rollback()
        return ret

    def get_group_members(self, group_id, spread=None, filter_spread=None):
        """Collect a list of the usernames of all users in a group.

        :type group_id: int
        :param group_id: The groups entity_id.

        :type spread: _SpreadCode
        :param spread: The spread to filter by.

        :type filter_spread: _SpreadCode
        :param filter_spread: A spread that the user must also have.

        :rtype: list
        :return: A list of usernames who are members of group_id."""
        found_accounts = []
        r = []
        for x in self.gr.search_members(group_id=group_id,
                                        indirect_members=True,
                                        member_spread=spread,
                                        member_type=self.co.entity_account):
            if x['member_id'] not in found_accounts:
                if filter_spread in self.get_account_spreads(x['member_id']):
                    r.append({'name': self.get_account_name(x['member_id']),
                              'account_id': x['member_id']})
                    found_accounts.append(x['member_id'])

        spreads = []
        if spread:
            spreads += [int(spread)]
        if filter_spread:
            spreads += [int(filter_spread)]

        for x in self.gr.search_members(group_id=group_id,
                                        indirect_members=True,
                                        member_type=self.co.entity_person):
            self.pe.clear()
            self.pe.find(x['member_id'])
            aid = self.pe.get_primary_account()
            if aid:
                self.ac.clear()
                self.ac.find(aid)
                if self.ac.entity_id not in found_accounts:
                    # If/elif used to allow usage without filter and
                    # filter_spread params
                    if spreads and \
                        set(spreads).issubset(
                            set([x['spread'] for x in self.ac.get_spread()])):
                        r.append({'name': self.ac.account_name,
                                  'account_id': self.ac.entity_id})
                        found_accounts.append(self.ac.entity_id)
                    elif not spreads:
                        r.append({'name': self.ac.account_name,
                                  'account_id': self.ac.entity_id})
                        found_accounts.append(self.ac.entity_id)
        self.db.rollback()
        return r

    def get_parent_groups(self, id, spread=None, name_prefix=None):
        """Return all groups that the group is an indirect member of. Filter
        by spread and the start of the group name.

        :type id: int
        :param id: The entity_id.

        :type spread: _SpreadCode
        :param _SpreadCode: The spread code to filter by, default is None.

        :type name_prefix: str
        :param name_prefix: Check if the group starts with this, default None.

        :rtype: list
        :return: A list of appropriate groups."""
        if name_prefix:
            np = '%s%%' % name_prefix
        else:
            np = None
        groups = []
        for group in self.gr.search(member_id=id, indirect_members=True,
                                    spread=spread, name=np):
            groups.append(group['name'])
        self.db.rollback()
        return groups

####
# Other utility methods
####

    def load_params(self, event):
        """Get the change params of an event.

        :type event: dbrow
        :param event: The db row returned by Change- or EventLog.

        :rtype: dict or None
        :return: The change params."""
        params = event['change_params']
        if params is None:
            return params
        return json.loads(params)

    def get_entity_type(self, entity_id):
        """Fetch the entity type code of an entity.

        :type entity_id: int
        :param entity_id: The entity id.

        :rtype: long
        :return: The entity type code."""
        self.en.clear()
        self.en.find(entity_id)
        ret = self.en.entity_type
        self.db.rollback()
        return ret

    def log_event(self, event, trigger):
        """Utility method used to create an event only in the EventLog.

        :type event: dict
        :param event: Dict representing an event (as returned from get_event).

        :param trigger: str or list or tuple
        :param trigger: The change type code we want to associate with the
            event. Only the first value will be used."""
        if isinstance(trigger, (list, tuple)):
            trigger = trigger[0]
        trigger = trigger.split(':')
        ct = self.co.ChangeType(trigger[0], trigger[1])

        params = self.load_params(event)

        self.db.log_change(event['subject_entity'],
                           int(ct),
                           event['dest_entity'],
                           change_params=params,
                           skip_change=True,
                           skip_publish=True)
        self.db.commit()

    def log_event_receipt(self, event, trigger):
        """Log the "receipt" of a completed event in ChangeLog.

        :type event: dict
        :param event: Dict representing an event (as returned from get_event).

        :param trigger: str or list or tuple
        :param trigger: The change type code we want to associate with the
            event. Only the first value will be used."""
        # TODO: Set change_program from a sensible source to something smart
        if isinstance(trigger, (list, tuple)):
            trigger = trigger[0]
        trigger = trigger.split(':')
        ct = self.co.ChangeType(trigger[0], trigger[1])
        parm = {'change_program': 'ExchangeIntegration',
                'skip_event': True,
                'skip_publish': True}

        # Only log params if they actually contain something.
        param = self.load_params(event)
        if param:
            parm['change_params'] = param

        self.db.log_change(event['subject_entity'],
                           int(ct),
                           event['dest_entity'],
                           **parm)
        self.db.commit()

####
# Email* utility methods
####

    def get_email_target_info(self, target_id=None, target_entity=None):
        """Return the entity_type and entity_id of the entity the EmailTarget
        points at. Look up by _either_ target_id or target_entity.

        :type target_id: int
        :param target_id: The EmailTargets id.

        :type target_entity: int
        :param target_entity: The targets target entity id.

        :rtype: typle
        :return: (entity_id, target_entity_id, target_entity_type, hard_quota,
            soft_quota)."""
        self.et.clear()
        self.eq.clear()
        if target_id:
            self.et.find(target_id)
            try:
                self.eq.find(target_id)
            except Errors.NotFoundError:
                self.eq.clear()
        elif target_entity:
            self.et.find_by_target_entity(target_entity)
            try:
                self.eq.find(self.et.entity_id)
            except Errors.NotFoundError:
                self.eq.clear()
        else:
            self.db.rollback()
            raise Errors.ProgrammingError(
                'Must define either target_id og target_entity')
        ret = (self.et.entity_id,
               self.et.email_target_entity_id,
               self.et.email_target_entity_type,
               self.eq.get_quota_hard(),
               self.eq.get_quota_soft())
        self.db.rollback()
        return ret

    def get_email_domain_info(self, email_domain_id=None,
                              email_domain_name=None):
        """Return info about an EmailDomain.

        :type email_domain_id: int
        :param email_domain_id: The email domains id.

        :rtype: dict
        :return: {name: EmailDomain name, id: EmailDomain id}."""
        self.ed.clear()
        if email_domain_id:
            self.ed.find(email_domain_id)
        elif email_domain_name:
            self.ed.find_by_domain(email_domain_name)
        ret = {'name': self.ed.email_domain_name, 'id': self.ed.entity_id}
        self.db.rollback()
        return ret

####
# *Group utility methods
####

    def get_distgroup_attributes_and_targetdata(self, subj_id):
        """Collect DistributionGroup specific information.

        :type subj_id: int
        :param subj_id: The entity-id of the DistributionGroup.

        :rtype: dict
        :return: A dict with DistributionGroup-specific data."""
        # TODO: This might crash if someone where to add a spread, on a group
        # which is not a DistributionGroup in Cerebrum
        self.dg.clear()
        self.dg.find(subj_id)
        rl = True if self.dg.roomlist == 'T' else False
        ret = self.dg.get_distgroup_attributes_and_targetdata(roomlist=rl)
        self.db.rollback()
        return ret

    def get_distgroup_displayname(self, subj_id):
        """Get DisplayName for a DistributionGroup.

        :type subj_id: int
        :param subj_id: The DistributionGroups entity-id.

        @rtype: Cerebrum.extlib.db_row.row
        @return: Rows as returned by Entity.search_name_with_language()."""
        self.dg.clear()
        self.dg.find(subj_id)
        ret = self.dg.search_name_with_language(
            entity_id=subj_id,
            name_variant=self.co.dl_group_displ_name,
            name_language=self.co.language_nb)
        self.db.rollback()
        return ret

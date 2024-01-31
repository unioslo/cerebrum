# -*- encoding: utf-8 -*-
#
# Copyright 2013-2023 University of Oslo, Norway
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
This file contains workflows and common operations related to virthome
accounts and groups. It's a generalization of some of the bofhd-commands, so
that they can be used by other applications.

NOTICE: The classes here won't check permissions, that needs to be done by the
the caller!

TODO: This is the new home for all virthome-related bofh-commands. All changes
should be done here, and called from bofhd_virthome_cmds. This class should
stay genereic enough to be used outside of bofhd.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    # TODO: unicode_literals,
)

import datetime
import re
import sys

import six

import cereconf

from Cerebrum.Errors import CerebrumError, NotFoundError
from Cerebrum.Utils import Factory
from Cerebrum.group.GroupRoles import GroupRoles
from Cerebrum.modules.bofhd.auth import BofhdAuthOpTarget, BofhdAuthRole
from Cerebrum.modules.virthome import VirtAccount
from Cerebrum.utils import date_compat


class VirthomeBase(object):
    """
    Common business logic for virthome/webid.

    The outer access layer: Methods here are workflows such as creating
    accounts, creating groups, disabling groups, creating events...
    This is the only class that _should_ be imported (visible) to other
    modules.
    """

    def __init__(self, db):
        """ NOTE: This class does not commit any changes to the db. That must
        be done from the calling environment.

        @type db: Cerebrum.database.Database
        @param db: A database connection.
        """
        self.db = db
        self.co = Factory.get('Constants')(db)
        self.clconst = Factory.get('CLConstants')(db)

        self.account_class = Factory.get('Account')
        self.group_class = Factory.get('Group')

        self.vhutils = VirthomeUtils(db)

    def group_create(self, group_name, description, creator, owner,
                     url=None, forward=None):
        """
        This method creates a new VirtHome group.

        NOTE: Some group name formats are reserved for specific applications!
        This method WILL allow creation of reserved group names.

        :param str group_name: the name of the new group
        :param str description: the group description
        :param Account creator: the creator of this group
        :param Account owner: the owner of this group
        :param str url: url associated with the group
        :param str forward: url to an external app that uses this group
        """
        gr = self.group_class(self.db)

        if self.vhutils.group_exists(group_name):
            raise CerebrumError("Group name '%s' already exists" % group_name)

        # TODO/TBD: Verify owner.np_type is FEDaccount? Must it be?

        try:
            gr.populate(creator.entity_id, group_name, description)
            gr.write_db()
            gr.set_group_resource(url)
        except (ValueError, AssertionError):
            raise CerebrumError(str(sys.exc_info()[1]))

        forward = self.vhutils.whitelist_url(forward)
        if forward:
            gr.populate_trait(self.co.trait_group_forward, strval=forward)

        for spread in getattr(cereconf, "BOFHD_NEW_GROUP_SPREADS", ()):
            gr.add_spread(self.co.human2constant(spread, self.co.Spread))

        gr.write_db()
        roles = GroupRoles(self.db)
        roles.add_admin_to_group(owner.entity_id, gr.entity_id)
        return gr

    def group_invite_user(self, inviter, group, email, timeout=3):
        """
        This method sets up an event that will allow a user to join a group.

        :type inviter: self.account_class
        :param inviter: The account that is setting up the invitation

        :type group: self.group_class
        :param group_name: The group that should be joined

        :type email: str
        :param : The email adrress of the user that is invited

        :type timeout: int
        :param timeout: The number of days until the confirmation key expires.

        :rtype: dict
        :return:
            A dictionary with the following keys:

             confirmation_key
                <str> The code that is used to confirm the invitation

             match_user <str>
                A username, if a user exists with that email-address

             match_user_email
                An e-mailaddress. Not sure why?
        """
        ac = self.account_class(self.db)

        assert hasattr(inviter, 'entity_id')
        assert hasattr(group, 'entity_id')

        timeout = datetime.timedelta(days=int(timeout))
        max_timeout = date_compat.get_timedelta(cereconf.MAX_INVITE_PERIOD)

        if timeout.days < 1:
            raise CerebrumError('Timeout too short (%d)' % timeout.days)
        if (timeout > max_timeout):
            raise CerebrumError("Timeout too long (%d)" % timeout.days)

        ret = {
            'confirmation_key': self.vhutils.setup_event_request(
                group.entity_id,
                self.clconst.va_group_invitation,
                params={
                    'inviter_id': inviter.entity_id,
                    'group_id': group.entity_id,
                    'invitee_mail': email,
                    'timeout': timeout.days,
                },
                change_by=inviter.entity_id,
            )}

        # check if e-mail matches a valid username
        try:
            ac.find_by_name(email)
            ret['match_user'] = ac.account_name
            if ac.np_type in (self.co.fedaccount_type,
                              self.co.virtaccount_type):
                ret['match_user_email'] = ac.get_email_address()
        except NotFoundError:
            pass

        return ret

    def group_disable(self, group):
        """This method removes all members and auth data related to a group,
        effectively disabling it without actually 'nuking' it.

        :param Group group_name: the group that should be disabled

        :returns str: name of the group that was disabled
        """
        assert hasattr(group, 'entity_id')

        # Yank all the spreads
        for row in group.get_spread():
            group.delete_spread(row["spread"])

        # Remove all members
        for membership in group.search_members(group_id=group.entity_id,
                                               member_filter_expired=False):
            group.remove_member(membership["member_id"])

        group.write_db()

        # Clean up the permissions (granted ON the group and TO the group)
        self.vhutils.remove_auth_targets(group.entity_id)
        self.vhutils.remove_auth_roles(group.entity_id)
        return group.group_name


class VirthomeUtils(object):
    """ Helper methods related to virthome """

    def __init__(self, db):
        self.db = db
        self.co = Factory.get('Constants')(db)
        self.clconst = Factory.get('CLConstants')(db)

        self.group_class = Factory.get('Group')
        self.account_class = Factory.get('Account')

        # Or compile on each call to
        self.url_whitelist = [re.compile(r)
                              for r in cereconf.FORWARD_URL_WHITELIST]

    def group_exists(self, name):
        """
        This method simply tests if a group name exists in the database

        :param str name: Name of the group to look for

        :returns bool: True if the group exists, otherwise False
        """
        group = self.group_class(self.db)
        try:
            group.find_by_name(name)
            return True
        except NotFoundError:
            pass
        return False

    def list_group_members(self, group, indirect_members=False):
        """
        This methid lists members of a group.

        It does NOT include operators or moderators, unless they are also
        members.

        :type group: Cerebrum.Group
        :param group: The group to list members of

        :type indirect: bool
        :param indirect: If we should include indirect members
        """
        ac = self.account_class(self.db)
        gr = self.group_class(self.db)

        assert hasattr(group, 'entity_id')

        result = list()
        for x in group.search_members(group_id=group.entity_id,
                                      indirect_members=indirect_members):
            owner_name = None
            member_name = None
            email_address = None
            member_type = self.co.EntityType(x['member_type'])
            if member_type == self.co.entity_account:
                ac.clear()
                ac.find(x['member_id'])
                if ac.np_type in (self.co.fedaccount_type,
                                  self.co.virtaccount_type):
                    member_name = ac.account_name
                    owner_name = ac.get_owner_name(self.co.human_full_name)
                    email_address = ac.get_email_address()
            elif member_type == self.co.entity_group:
                gr.clear()
                gr.find(x['member_id'])
                member_name = gr.group_name
            result.append({
                'member_id': x['member_id'],
                'member_type': str(member_type),
                'member_name': member_name,
                'owner_name': owner_name,
                'email_address': email_address,
            })

        result.sort(lambda x, y: cmp(x['member_name'], y['member_name']))
        return result

    def list_group_memberships(self, account, indirect_members=False,
                               realm=None):
        """
        This method lists groups that an account is member of.

        :type account: Cerebrum.Account
        :param account:
            The account we're looking up memberships for

        :type indirect_members: bool
        :param indirect_members:
            Whether indirect members should be included

        :type realm: str or NoneType
        :param realm:
            Filter groups by realm.

            A realm of 'webid.uio.no' will only return groups on the format
            '*@webid.uio.no'. No filtering for empty string or None.

        :rtype: list
        :return:
            A list with dictionaries, one dict per group membership.

            Contain keys 'group_id', 'name', 'description', 'visibility',
            'creator_id', 'created_at', 'expire_date'
        """
        gr = self.group_class(self.db)
        assert hasattr(account, 'entity_id')

        result = list()
        for group in gr.search(member_id=account.entity_id,
                               indirect_members=indirect_members):
            if realm and not self.in_realm(group['name'], realm):
                continue
            gr.clear()
            gr.find(group['group_id'])
            tmp = dict(group)
            # Fetch url
            resource = gr.get_contact_info(self.co.system_virthome,
                                           self.co.virthome_group_url)
            if resource:
                tmp['url'] = resource[0]['contact_value']
            result.append(tmp)
        return result

    def get_trait_val(self, entity, trait_const, val='strval'):
        """
        Get the trait value of type L{val} of L{entity} that is of type
        L{trait_const}.

        @type entity: Cerebrum.Entity
        @param entity: The entity which trait is being looked up

        @type trait_const: _EntityTraitCode
        @param trait_const: The type of trait to load

        @rtype: str
        @return: The L{val} of the trait, if it exists. None if the L{entity}
                 doesn't have a trait of type L{trait_const}, or the trait
                 doesn't have a value L{val}
        """
        assert hasattr(entity, 'entity_id') and hasattr(entity, 'get_trait')
        try:
            trait = entity.get_trait(trait_const)
            return trait.get(val, None)
        except AttributeError:
            pass
        return None

    def whitelist_url(self, url):
        """
        This is a 'last stand' for forward urls.

        The URL must match at least one of the whitelist regular expressions if
        we're to store it as a forward url.

        :param str url: The URL to whitelist

        :returns str : The whitelisted url, or None if the L{url} didn't pass.
        """
        if not url:
            return None

        for r in self.url_whitelist:
            if r.match(url):
                return url

        return None

    # Changelog/event/invitation related methods

    def setup_event_request(self, issuer_id, event_type, params=None,
                            change_by=None):
        """
        Perform the necessary magic when creating a pending confirmation event.

        This method will create the required changelog entry with the event.

        :type issuer_id: int
        :param issuer_id:
            The C{entity_id} of the event creator/inviter

        :type event_type: Constants._ChangeTypeCode
        :param event_type:
            The changelog type that should be used to store this event.

        :type params: obj
        :param params:
            An object containing other arbitrary information that relates to
            the L{event_type}.

        :rtype: str
        :return:
            The confirmation key, or ID, of the newly created event.
        """
        return self.db.log_pending_change(
            subject_entity=issuer_id,
            change_type_id=event_type,
            destination_entity=None,
            change_params=params,
            # From CIS, we don't have the
            # change_by parameter set up, should
            # set this in the request
            change_by=change_by,
        )

    # Account related methods

    def account_exists(self, account_name):
        """
        Check that L{account_name} is available in Cerebrum/Virthome.

        Names are case sensitive, but there should not exist two accounts with
        same name in lowercase, due to LDAP, so we have to check this too.

        (The combination if this call and account.write_db() is in no way
        atomic, but checking for availability lets us produce more meaningful
        error messages in (hopefully) most cases).

        :param str account_name: The account name to check

        :returns bool:
            True if account_name is available for use, False otherwise.
        """
        # Does not matter which one.
        ac = self.account_class(self.db)
        return not ac.uname_is_available(account_name)

    def assign_default_user_spreads(self, account):
        """
        Assign all the default spreads for freshly created users.

        :type account: Cerebrum.Account
        :param account: The account object that should receive default spreads
        """
        for spread in getattr(cereconf, "BOFHD_NEW_USER_SPREADS", ()):
            tmp = self.co.human2constant(spread, self.co.Spread)
            if not account.has_spread(tmp):
                account.add_spread(tmp)

    def create_account(self, account_type, account_name, email, expire_date,
                       human_first_name, human_last_name,
                       with_confirmation=True):
        """
        Create an account of the specified type.

        This is a convenience function to avoid duplicating some of the work.

        :type account_type: subclass of BaseVirtHomeAccount
        :param account_type: The account class type to use.

        :param str account_name: Account name to give the new account

        :param str email: The email address of the account owner

        :param expire_date: The expire date for the account

        :param str human_first_name: The first name(s) of the account owner

        :param str human_last_name: The last name(s) of the account owner

        :param bool with_confirmation:
            Controls whether a confirmation request should be issued for this
            account.

            In some situations it makes no sense to confirm anything.

            NOTE: The caller must dispatch any confirmation mail. This controls
            whether a confirmation event/code should be created and returned.

        :rtype: tuple <BaseVirtHomeAccount, str>
        :return:
            The newly created account, and the confirmation key needed to
            confirm the given email address.

            NOTE: If with_confirmation was False, the confirmation key will be
            empty.
        """
        assert issubclass(account_type, VirtAccount.BaseVirtHomeAccount)

        # Creation can still fail later, but hopefully this captures most
        # situations and produces a sensible account_name.
        if self.account_exists(account_name):
            raise CerebrumError("Account '%s' already exists"
                                % (account_name,))

        expire_date = date_compat.get_date(expire_date)
        account = account_type(self.db)
        account.populate(email, account_name, human_first_name,
                         human_last_name, expire_date)
        account.write_db()
        # Never exported to ldap:
        account.populate_trait(self.co.trait_user_retained, numval=0)
        account.write_db()

        self.assign_default_user_spreads(account)

        magic_key = ""
        if with_confirmation:
            magic_key = self.setup_event_request(
                account.entity_id,
                self.clconst.va_pending_create)

        return account, magic_key

    def create_fedaccount(self, account_name, email, expire_date=None,
                          human_first_name=None, human_last_name=None):
        """
        Simple shortcut to create a FEDAccount.

        This is create_account with default values:

            account_type=FEDAccount
            with_confirmation=False

        :param str account_name:
            Desired FEDAccount name. If unavailable, we'll encounter an error.

        :param str email:
            The FEDAccount owner's e-mail address.

        :param expire_date:
            Expiration date for the FEDAccount we are about to create.

        :param str human_first_name:
            The first name(s) of the account owner

        :param str human_last_name:
            The last name(s) of the account owner

        :rtype: int
        :return:
            The entity id of the new account
        """
        expire_date = date_compat.get_date(expire_date)
        account, confirmation_key = self.create_account(
            VirtAccount.FEDAccount,
            account_name,
            email,
            expire_date,
            human_first_name,
            human_last_name,
            with_confirmation=False,
        )
        return account.entity_id

    # BofhdAuth-related methods

    def find_or_create_op_target(self, entity_id, target_type):
        """
        Find or create an auth target for a given entity.

        Finds an op-target of type L{target_type} that points to L{entity_id}.
        If no targets exist, one will be created.
        """
        aot = BofhdAuthOpTarget(self.db)
        op_targets = list(aot.list(entity_id=entity_id,
                                   target_type=target_type))

        # No target exists, create one
        if not op_targets:
            aot.populate(entity_id, target_type)
            aot.write_db()
            return aot

        # This method will never create more than one:
        assert len(op_targets) == 1

        # ... and never populates attr:
        assert op_targets[0]['attr'] is None

        # Target exists, return it
        aot.find(op_targets[0]['op_target_id'])
        return aot

    def remove_auth_targets(self, entity_id, target_type=None):
        """
        Remove auth target for a given entity.

        This method will remove authorization targets of type L{target_type}
        that points to the L{entity_id}.  If L{target_type} is None, all
        targets regardless of type will be removed.

        :type entity_id: int
        :param entity_id: The entity_id of an object.

        :type target_type: str
        :param target_type: The target type of the authorization target
        """
        ar = BofhdAuthRole(self.db)
        aot = BofhdAuthOpTarget(self.db)

        for target in aot.list(entity_id=entity_id, target_type=target_type):
            aot.clear()
            aot.find(target['op_target_id'])

            # Before the target is removed, we must remove all roles that
            # grants access to the target.
            for role in ar.list(op_target_id=target["op_target_id"]):
                ar.revoke_auth(role['entity_id'], role['op_set_id'],
                               target['op_target_id'])
            aot.delete()

    def remove_auth_roles(self, entity_id):
        """
        Remove auth roles for a given entity.

        This method will remove all authorization roles that has been given
        to an entity. It will also remove any remaining authorization targets
        that no longer have auth roles pointing to it as a result.

        :type entity_id: int
        :param entity_id: The entity_id of an object.
        """
        ar = BofhdAuthRole(self.db)
        aot = BofhdAuthOpTarget(self.db)

        # Remove all auth-roles the entity have over other targets
        for target in ar.list(entity_ids=entity_id):
            ar.revoke_auth(entity_id, target['op_set_id'],
                           target['op_target_id'])

            # Remove auth-target if there aren't any more auth-roles pointing
            # to it
            remaining = ar.list(op_target_id=target['op_target_id'])
            if len(remaining) == 0:
                aot.clear()
                aot.find(target['op_target_id'])
                aot.delete()

    def list_group_admins(self, group):
        """
        List admins of C{group}.

        :type group: Cerebrum.Group
        :param group: A populated group object to list 'admins' for.

        @rtype: list
        @return: A list of dictionaries with keys:
                 ['account_id', 'account_name', 'owner_name', 'email_address',
                  'group_id', 'group_name', 'description']
        """
        ret = []
        ac = self.account_class(self.db)
        roles = GroupRoles(self.db)
        for admin in roles.search_admins(
                group_id=group.entity_id,
                admin_type=self.co.entity_account):
            ac.clear()
            ac.find(admin['admin_id'])
            ret.append({
                'account_id': ac.entity_id,
                'account_name': ac.get_account_name(),
                'owner_name': ac.get_owner_name(self.co.human_full_name),
                'email_address': ac.get_email_address(),
                'group_id': group.entity_id,
                'group_name': group.group_name,
                'description': group.description,
            })
        return ret

    def list_group_moderators(self, group):
        """
        List moderators of C{group}.

        :type group: Cerebrum.Group
        :param group: A populated group object to list 'admins' for.

        :rtype: list
        :return:
            A list of dictionaries with keys:

            ['account_id', 'account_name', 'owner_name', 'email_address',
             'group_id', 'group_name', 'description']
        """
        ret = []
        ac = self.account_class(self.db)
        roles = GroupRoles(self.db)
        for mod in roles.search_moderators(
                group_id=group.entity_id,
                moderator_type=self.co.entity_account):
            ac.clear()
            ac.find(mod['moderator_id'])
            ret.append({
                'account_id': ac.entity_id,
                'account_name': ac.get_account_name(),
                'owner_name': ac.get_owner_name(self.co.human_full_name),
                'email_address': ac.get_email_address(),
                'group_id': group.entity_id,
                'group_name': group.group_name,
                'description': group.description,
            })
        return ret

    def list_groups_admined(self, account):
        """
        List groups that C{account} is an admin for

        :type account: Cerebrum.Account
        :param account: A populated account object to list 'groups' for.

        :rtype: list
        :return:
            A list of dictionaries with keys:

            ['group_id', 'group_name', 'url', 'description', 'account_id',
             'account_name']
        """
        ret = []
        gr = self.group_class(self.db)
        assert hasattr(account, 'entity_id')

        for group in gr.search(admin_id=account.entity_id):
            gr.clear()
            gr.find(group['group_id'])
            ret.append({
                'group_id': gr.entity_id,
                'group_name': gr.group_name,
                'url': gr.get_contact_info(self.co.virthome_group_url),
                'description': group.description,
                'account_id': account.entity_id,
                'account_name': account.get_account_name(),
            })
        return ret

    def list_groups_moderated(self, account):
        """
        List groups moderated by C{account}

        :type account: Cerebrum.Account
        :param account: A populated account object to list 'groups' for.

        :rtype: list
        :return:
            A list of dictionaries with keys:

            ['group_id', 'group_name', 'url', 'description', 'account_id',
             'account_name']
        """
        ret = []
        gr = self.group_class(self.db)
        assert hasattr(account, 'entity_id')

        for group in gr.search(moderator_id=account.entity_id):
            gr.clear()
            gr.find(group['group_id'])
            ret.append({
                'group_id': gr.entity_id,
                'group_name': gr.group_name,
                'url': gr.get_contact_info(self.co.virthome_group_url),
                'description': group.description,
                'account_id': account.entity_id,
                'account_name': account.get_account_name(),
            })
        return ret

    # Realm-related functions

    def in_realm(self, name, realm, strict=True):
        """
        Check if the given L{name} is in the realm L{realm}

        :type name: str
        :param name: The name (account name group name)

        :type realm: str
        :param realm: The realm, e.g. 'webid.uio.no'

        :type strict: bool
        :param strict:
            If False, we consider 'some.sub.realm' as being in the realm
            'realm'. Otherwise, the realm must be an exact match.

        :rtype: bool
        :return: True if the name is within the realm, false if not.
        """
        assert isinstance(name, (str, six.text_type)), 'Invalid name'
        assert not self.illegal_realm(realm), 'Invalid realm'

        # We know the realm only contains :alnum: and periods.
        # Should be safe to do:
        regex_realm = realm.replace('.', r'\.')
        regex = re.compile(r'^(.+)@((.+\.)?%s)$' % regex_realm)
        # Groups: 1: <name>, 2: <matched realm> (3: <subrealm.>)

        match = regex.match(name)
        if not match:
            return False
        assert isinstance(match.group(1), (str, six.text_type))
        assert isinstance(match.group(2), (str, six.text_type))

        if not strict:
            return not self.illegal_realm(match.group(2))

        return match.group(2) == realm

    def illegal_realm(self, realm):
        """
        Simple test to see if a realm is an acceptable realm name

        :rtype: bool
        :return: If the given realm name is an illegal realm name
        """
        assert isinstance(realm, (str, six.text_type))
        legal = re.compile(r'^[0-9a-z]+(\.[0-9a-z]+)*$')
        return not bool(legal.match(realm))

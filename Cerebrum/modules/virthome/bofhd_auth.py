#!/usr/bin/env python
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

"""Authentication/permission checking module for VirtHome's bofhd extensions.

This module contains the code necessary to support permission checks for
virthome bofhd operations.
"""

import cereconf

from Cerebrum.Constants import Constants
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd import auth
from Cerebrum.modules.bofhd.errors import PermissionDenied
from Cerebrum import Errors
from Cerebrum.Utils import argument_to_sql




class BofhdVirtHomeAuth(auth.BofhdAuth):
    """This class defines a number of permission check/authorisation methods
    used by the bofhd framework in VirtHome.
    """

    def __init__(self, database):
        super(BofhdVirtHomeAuth, self).__init__(database)
    # end __init__



    def get_permission_holders_on_groups(self, op_set_id, group_id=None, account_id=None):
        """Collect all account-with-permissions-on-group satisfying certain criteria.

        The idea is to figure out who has permission set represented by
        opset_id on which group, in order to answer questions like 'List all
        moderators of this group' or 'which groups do I own?'. The method is
        generalised to accept multiple account_ids/group_ids/op_set_ids.

        @type op_set_id: int or a non-empty sequence thereof.
        FIXME: Should the interface be nicer and allow BofhdAuthOpSet
        instances?
        FIXME: BofhdAuthRole.list() could be (should be?) fixed to perform
        this task.

        @type group_id: int or a non-empty sequence thereof.

        @type account_id: int or a non-empty sequence thereof

        @return:
          An iterable over db-rows with entity_ids of the permission
          holders. (FIXME: do we want entity_types to go with entity_ids?)
        """

        assert not (group_id and account_id), "Cannot specify both"

        binds = {"target_type": self.const.auth_target_type_group,
                 "domain": self.const.group_namespace,
                 "domain2": self.const.account_namespace,}
        where = [argument_to_sql(op_set_id, "ar.op_set_id", binds, int),]
        if group_id is not None:
            where.append(argument_to_sql(group_id, "aot.entity_id", binds, int))
        elif account_id is not None:
            where.append(argument_to_sql(account_id, "ar.entity_id", binds, int))

        query = ("""
        SELECT DISTINCT ar.entity_id as account_id,
                        aot.entity_id as group_id,
                        en.entity_name as group_name,
                        en2.entity_name as account_name,
                        gi.description
        FROM [:table schema=cerebrum name=auth_role] ar
        JOIN [:table schema=cerebrum name=auth_op_target] aot
          ON ar.op_target_id = aot.op_target_id AND
             aot.target_type = :target_type AND""" + 

        " AND ".join(where) + 

        """
        JOIN [:table schema=cerebrum name=group_info] gi
          ON aot.entity_id = gi.group_id
        LEFT OUTER JOIN [:table schema=cerebrum name=entity_name] en
          ON en.entity_id = aot.entity_id AND
             en.value_domain = :domain
        LEFT OUTER JOIN [:table schema=cerebrum name=entity_name] en2
           ON en2.entity_id = ar.entity_id AND
              en2.value_domain = :domain2
        """)
        return list(x.dict()
                    for x in self.query(query, binds,))
    # end _get_permission_holders_on_group
        

    def _get_account(self, account_id):
        account = Factory.get("Account")(self._db)
        try:
            account.find(int(account_id))
            return account
        except Errors.NotFoundError:
            return None
    # end _get_account


    def _get_group(self, ident):
        group = Factory.get("Group")(self._db)
        try:
            if ((isinstance(ident, str) and ident.isdigit()) or
                isinstance(ident, (int, long))):
                group.find(int(ident))
            else:
                group.find_by_name(ident)
            return group
        except Errors.NotFoundError:
            return None
    # end _get_group


    def is_feideuser(self, operator_id):
        """Does operator_id belong to a FEDAccount?
        """

        acc = self._get_account(operator_id)
        return (acc is not None) and acc.np_type == self.const.fedaccount_type
    # end is_feideuser


    def is_localuser(self, operator_id):
        """Does operator_id belong to a VirtAccount?
        """

        acc = self._get_account(operator_id)
        return (acc is not None) and acc.np_type == self.const.virtaccount_type
    # end is_feideuser


    def is_sudoer(self, operator_id):
        """Can operator_id change identity to another user?
        """

        group = self._get_group(cereconf.BOFHD_SUDOERS_GROUP)
        return group.has_member(operator_id)
    # end is_sudoer


    def can_confirm(self, account_id):
        """Can account_id confirm an operation on a virthome account?

        (Operation may be e-mail verification, e-mail change, etc.)

        FIXME: We need to decide who could issue virtaccount confirmation
        requests. Since a confirmation requires possession of a unique random
        ID, there is no point in restricting this command -- worse case
        scenario a garbage id is fed to bofhd, no big deal.

        However, it is entirely possible that we want to restrict confirmation
        to some specific web-app-special-system-account.
        """

        # everyone can confirm virtaccount operations.
        return True
    # end can_create_virtaccount


    def can_create_fedaccount(self, account_id):
        """Can account_id create a fedaccount?

        @type account_id: int
        @param account_id
          Account id of the account that we want to check fedaccount creation
          permissions. 
        """

        # Superusers only can do that.
        if self.is_superuser(account_id):
            return True

        # Allow webapp to do this.
        if self.is_sudoer(account_id):
            return True

        raise PermissionDenied("id=%s cannot create FEDAccounts" % str(account_id))
    # end can_create_fedaccount



    def can_su(self, account_id, target_id):
        """Can account_id change identity (i.e. UNIX su) to target_id?
        """

        if ((self.is_sudoer(account_id) or self.is_superuser(account_id)) and
            # don't want to allow su to superuser (i.e. this means that
            # superusers WILL NOT BE able to login via web interface)
            not self.is_superuser(target_id)):
            return True

        raise PermissionDenied("id=%s cannot run 'su'" % str(account_id))
    # end can_su



    def can_nuke_virtaccount(self, account_id, victim_id):
        """Can account_id delete victim_id?
        """

        acc = self._get_account(account_id)
        victim = self._get_account(victim_id)
        assert victim.np_type == self.const.virtaccount_type

        # We allow self-deletion.
        if (self.is_superuser(acc.entity_id) or
            acc.entity_id == victim.entity_id):
            return True

        raise PermissionDenied("%s (id=%s) cannot delete %s (id=%s)" %
                               (acc.account_name, acc.entity_id, 
                                victim.account_name, victim.entity_id))
    # end can_nuke_virtaccount


    def can_nuke_fedaccount(self, account_id, victim_id):
        """Can account_id delete victim_id?
        """

        acc = self._get_account(account_id)
        victim = self._get_account(victim_id)
        assert victim.np_type == self.const.fedaccount_type

        # We allow self-deletion and superuser.
        if (self.is_superuser(acc.entity_id) or
            acc.entity_id == victim.entity_id):
            return True

        raise PermissionDenied("%s (id=%s) cannot delete %s (id=%s)" %
                               (acc.account_name, acc.entity_id,
                                victim.account_name, victim.entity_id))
    # end can_nuke_virtaccount



    def can_view_user(self, account_id, victim_id):
        """Can account_id view victim_id's info?
        """

        if (self.is_superuser(account_id) or
            self.is_sudoer(account_id) or
            account_id == victim_id):
            return True
        
        raise PermissionDenied("Operation not allowed")
    # end can_view_user

    

    def can_create_group(self, account_id, query_run_any=False):
        if self.is_superuser(account_id) or self.is_feideuser(account_id):
            return True

        raise PermissionDenied("Operation not allowed")
    # end can_create_group



    def can_own_group(self, account_id):
        if self.is_superuser(account_id) or self.is_feideuser(account_id):
            return True

        raise PermissionDenied("Operation not allowed")
    # end can_own_group
    


    def can_moderate_group(self, account_id):
        """Can an account be a group moderator?

        @type account_id: int
        @param account_id
          Account id of the account that we want to check moderator
          permissions for.
        """
        if self.is_superuser(account_id):
            return True

        account = Factory.get("Account")(self._db)
        try:
            account.find(account_id)
            if account.np_type != self.const.fedaccount_type:
                raise PermissionDenied("Account %s (id=%s) cannot moderate "
                                       "VirtGroups" %
                                       (account.account_name, account_id))
            return True
        except Errors.NotFoundError:
            # non-existing accounts cannot do anything :)
            raise PermissionDenied("id=%s cannot moderate VirtGroups" %
                                   account_id)

        # NOTREACHED
        assert False
    # end can_moderate_group



    def can_change_moderators(self, account_id, group_id):
        """Can an account change (add/remove) moderators from a group?

        Group owners and moderators are allowed to alter moderator lists.
        """

        return self.can_add_to_group(account_id, group_id)
    # end can_change_moderators


    def can_change_admins(self, account_id, group_id):
        """Can an account change group_id's owner?

        Group owners are allowed to change owners.
        """

        # can_delete_group() is available for owners only.
        return self.can_force_delete_group(account_id, group_id)
    # end can_change_moderators



    def can_change_description(self, account_id, group_id):
        """Can an account change group_id's description?

        Group owners are allowed to change description.
        """

        # can_delete_group() is available for owners only.
        return self.can_force_delete_group(account_id, group_id)
    # end can_change_moderators



    def can_change_resource(self, account_id, group_id):
        """Can an account change group_id's resources (url, etc)?

        Group owners are allowed to do that.
        """
        
        return self.can_force_delete_group(account_id, group_id)
    # end can_change_url
    

    def can_manipulate_spread(self, account_id, entity_id):
        """Can an account change entity_id's spreads?

        FIXME: Whom do we want to have this permission?
        """

        if self.is_superuser(account_id):
            return True

        raise PermissionDenied("Command restricted to superusers")
    # end can_manipulate_spread
    

    def can_view_spreads(self, account_id, entity_id):
        """Can an account see entity_id's spreads?

        FIXME: Same as for L{can_manipulate_spreads}
        """

        if (self.is_superuser(account_id) or
            int(account_id) == int(entity_id)):
            return True

        raise PermissionDenied("Not allowed to view spreads of id=%s" %
                               entity_id)
    # end can_view_spreads


    def can_view_requests(self, account_id):
        """Can an account access pending confirmation requests?
        """

        if (self.is_superuser(account_id) or
            self.is_sudoer(account_id)):
            return True

        raise PermissionDenied("Not allowed to view requests")
    # end can_view_requests
        


    def can_force_delete_group(self, account_id, group_id):
        if self.is_superuser(account_id):
            return True

        if self._has_target_permissions(account_id,
                                        self.const.auth_create_group,
                                        self.const.auth_target_type_group,
                                        group_id, None):
            return True

        account = self._get_account(account_id)
        group = self._get_group(group_id)
        raise PermissionDenied("Account %s (id=%s) cannot delete "
                               "group %s (id=%s)" %
                               (account and account.account_name or "N/A",
                                account_id,
                                group and group.group_name or "N/A",
                                group_id))
    # end can_delete_group


    def can_add_to_group(self, account_id, group_id):
        if self.is_superuser(account_id):
            return True
        if self._is_admin_or_moderator(account_id, group_id):
            return True
        if self._has_target_permissions(account_id,
                                        self.const.auth_alter_group_membership,
                                        self.const.auth_target_type_group,
                                        group_id, None):
            return True

        account = self._get_account(account_id)
        group = self._get_group(group_id)
        raise PermissionDenied("Account %s (id=%s) cannot add members for "
                               "group %s (id=%s)" %
                               (account and account.account_name or "N/A",
                                account_id,
                                group and group.group_name or "N/A",
                                group_id))
    # end can_add_to_group


    def can_remove_from_group(self, operator_id, group_id, target_id):
        if self.is_superuser(operator_id):
            return True
        if self._is_admin_or_moderator(operator_id, group_id):
            return True
        # We allow a user to remove him/herself from a group.
        if operator_id == target_id:
            return True
        # TODO: Decide if we want to keep special permissions through opsets
        if self._has_target_permissions(operator_id,
                                        self.const.auth_alter_group_membership,
                                        self.const.auth_target_type_group,
                                        group_id, None):
            return True

        
        account = self._get_account(operator_id)
        group = self._get_group(group_id)
        raise PermissionDenied("Account %s (id=%s) cannot remove members from "
                               "group %s (id=%s)" %
                               (account and account.account_name or "N/A",
                                operator_id,
                                group and group.group_name or "N/A",
                                group_id))
    # end can_remove_from_group

    

    def can_show_quarantines(self, operator_id, entity_id):
        """Can operator see entity's quarantines?
        """

        if self.is_superuser(operator_id):
            return True

        if operator_id == entity_id:
            return True

        raise PermissionDenied("Account %s cannot see id=%s's quarantines" %
                               (operator_id, entity_id))
    # end can_show_quarantines



    def can_manipulate_quarantines(self, operator_id, victim_id):
        """Check whether operator can add/remove quarantines on victim.
        """

        if self.is_superuser(operator_id):
            return True

        raise PermissionDenied("Account %s can't manipulate id=%s's quarantines"%
                               (operator_id, victim_id))
    # end can_manipulate_quarantines



    def can_show_traits(self, operator_id, entity_id):
        """Check whether operator can see entity_id's traits.
        """

        if self.is_superuser(operator_id):
            return True

        if operator_id == entity_id:
            return True

        raise PermissionDenied("Account %s cannot see id=%s's quarantines" %
                               (operator_id, entity_id))
    # end can_show_quarantines


    def can_manipulate_traits(self, operator_id, victim_id):
        if self.is_superuser(operator_id):
            return True

        raise PermissionDenied("Account %s can't manipulate id=%s's traits" %
                               (operator_id, victim_id))
    # end can_manipulate_traits
# end class BofhdAuth

# -*- coding: utf-8 -*-
#
# Copyright 2003-2021 University of Oslo, Norway
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
""" Site specific auth.py for UiO. """
import six

import cereconf

from Cerebrum.Errors import NotFoundError
from Cerebrum.Utils import Factory
from Cerebrum.modules.EntityTrait import EntityTrait
from Cerebrum.modules.apikeys import bofhd_apikey_cmds
from Cerebrum.modules.audit import bofhd_history_cmds
from Cerebrum.modules.bofhd import bofhd_access
from Cerebrum.modules.bofhd import bofhd_external_id
from Cerebrum.modules.bofhd import bofhd_group_roles
from Cerebrum.modules.bofhd import bofhd_ou_cmds
from Cerebrum.modules.bofhd import bofhd_user_create_unpersonal
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_contact_info import BofhdContactAuth
from Cerebrum.modules.bofhd.bofhd_email import BofhdEmailAuth
from Cerebrum.modules.bofhd.errors import PermissionDenied
from Cerebrum.modules.bofhd_requests.bofhd_requests_auth import RequestsAuth
from Cerebrum.modules.otp import bofhd_otp_cmds
from Cerebrum.modules.ou_disk_mapping import bofhd_cmds
from Cerebrum.modules.trait import bofhd_trait_cmds


class ContactAuthMixin(BofhdContactAuth):
    """ uio specific contact auth. """

    def can_get_contact_info(self, operator,
                             entity=None,
                             contact_type=None,
                             query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return True
        if (hasattr(cereconf, 'BOFHD_VOIP_ADMINS')
                and self.is_group_member(operator, cereconf.BOFHD_VOIP_ADMINS)
                and not self._is_group_expired(cereconf.BOFHD_VOIP_ADMINS)):
            return True
        return super(ContactAuthMixin, self).can_get_contact_info(
            operator,
            entity=entity,
            contact_type=contact_type,
            query_run_any=query_run_any)


class UioAuth(ContactAuthMixin, BofhdAuth):
    """Defines methods that are used by bofhd to determine wheter
    an operator is allowed to perform a given action.

    This class only contains special cases for UiO.
    """

    # Temporary owner group is specified in trait_uio_guest_owner trait,
    # and members of owner groups should be allowed to change password
    # for their guest users
    def _is_guest_owner(self, operator, account):
        """ Return if the operator is the owner of *guest* account. """
        owner_uio = owner_personal = None

        # Personal guest account owner
        if hasattr(self.const, 'trait_guest_owner'):
            owner_personal = account.get_trait(
                getattr(self.const, 'trait_guest_owner'))
        if owner_personal:
            if operator == owner_personal['target_id']:
                return True

        # Old uio guest account owner
        if hasattr(self.const, 'trait_uio_guest_owner'):
            owner_uio = account.get_trait(
                getattr(self.const, 'trait_uio_guest_owner'))
        if owner_uio:
            grp = Factory.get("Group")(self._db)
            try:
                grp.find(owner_uio['target_id'])
            except NotFoundError:
                return False
            return (self.is_group_member(operator, grp.group_name) and not
                    self._is_group_expired(grp.group_name))
        return False

    def _is_important_account(self, operator, account):
        """If an account is considered important."""
        # Accounts owned by a group, i.e. system account
        # has_privileged_access_to_account_or_person() will allow this if
        # operator is a group member
        if account.owner_type == self.const.entity_group:
            return True
        # Tagged sysadmin accounts
        if account.get_trait(self.const.trait_sysadm_account):
            return True
        return super(UioAuth, self)._is_important_account(operator, account)

    def can_set_password(self, operator, account=None,
                         query_run_any=False):
        if query_run_any:
            return True
        if self._is_guest_owner(operator, account):
            return True
        return super(UioAuth, self).can_set_password(operator, account,
                                                     query_run_any)

    def can_clear_name(self, operator, person=None, source_system=None,
                       query_run_any=False):
        """If operator is allowed to remove a person's name from a given source
        system."""
        if query_run_any:
            return True
        if self.is_superuser(operator, query_run_any):
            return True
        if self.is_postmaster(operator, query_run_any):
            return True
        if source_system == self.const.system_override:
            # Operator can only clear their own override names.
            account = Factory.get('Account')(self._db)
            account.find(operator)
            if person.entity_id != account.owner_id:
                raise PermissionDenied(
                    'Cannot clear override for other persons')
            return True
        raise PermissionDenied('Not allowed to clear name')

    def can_create_sysadm(self, operator, query_run_any=False):
        """Allow sysadmins to create sysadmin accounts.

        Note that we don't check for OU or disk or anything. This is to avoid
        edge cases that requires manual work, and no security benefits. If one
        sysadmin creates a sysadmin account on a different OU, there is most
        likely a reason for that.

        """
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(operator,
                                              self.const.auth_create_user):
            return True
        if query_run_any:
            return False
        raise PermissionDenied('Not allowed to create sysadmin accounts')

    def can_add_affiliation(self, operator, person=None, ou=None, aff=None,
                            aff_status=None, query_run_any=False):
        # Restrict affiliation types
        if not query_run_any and aff in (
                self.const.affiliation_ansatt,
                self.const.affiliation_student):
            raise PermissionDenied(
                "Affiliations STUDENT/ANSATT can only be set by "
                "automatic imports")
        return super(UioAuth, self).can_add_affiliation(
            operator, person=person, ou=ou, aff=aff, aff_status=aff_status,
            query_run_any=query_run_any)

    def can_create_group(self, operator, groupname=None, query_run_any=False):
        """If an account should be allowed to create a group.

        We allow accounts with the operation `create_group` access, if the
        groupname matches the given operation's whitelist. Superusers are
        always allowed access.

        Access could be checked based on the groupname format, depending on how
        the OpSet is defined.

        :param int operator: The operator's `entity_id`.
        :param str groupname:
            The requested groupname of the group we want to create. Note that
            this auth module does not check if this group already exists or
            not. The access control only validates the group name in this case.
        :param bool query_run_any:
            If True, we only check if the account has access to the operation,
            *somewhere*.
        :rtype: bool
        :returns:
            `True` if the account is allowed access. If, *and only if*, the
            parameter `query_run_any` is True, we return `False` if the
            operator does not have access.
        :raise PermissionDenied:
            If the account is not allowed access for the operation. This will
            not be raised if `query_run_any` is set to `True`.

        """
        if query_run_any and self._is_admin_or_moderator(operator):
            return True
        return super(UioAuth, self).can_create_group(operator, groupname,
                                                     query_run_any)

    def can_alter_group(self, operator, group=None, query_run_any=False):
        """Checks if the operator has permission to add/remove group members
        for the given group.

        @type operator: int
        @param operator: The entity_id of the user performing the operation.

        @type group: An entity of EntityType Group
        @param group: The group to add/remove members to/from.

        @type query_run_any: True or False
        @param query_run_any: Check if the operator has permission *somewhere*

        @return: True or False
        """
        if self.is_superuser(operator):
            return True
        if query_run_any and self._is_admin(operator):
            return True
        if group and self._is_admin(operator, group.entity_id):
            return True
        return super(UioAuth, self).can_alter_group(operator, group,
                                                    query_run_any)

    def can_delete_group(self, operator, group=None, query_run_any=False):
        """
        Check if operator is allowed to delete a group.

        Group deletion is done by setting the expire date to today.
        """
        if self.is_superuser(operator):
            return True
        if query_run_any and self._is_admin_or_moderator(operator):
            return True
        if group and self._is_admin_or_moderator(operator, group.entity_id):
            return True
        return super(UioAuth, self).can_delete_group(operator, group,
                                                     query_run_any)

    def can_show_history(self, operator, entity=None, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any and self._is_admin(operator):
            return True
        if entity and self._is_admin(operator, entity.entity_id):
            return True
        return super(UioAuth, self).can_show_history(operator, entity,
                                                     query_run_any)

    def can_search_group(self, operator, filter="", query_run_any=False):
        if query_run_any and self._is_admin_or_moderator(operator):
            return True
        return super(UioAuth, self).can_search_group(operator, filter,
                                                     query_run_any)

    def can_add_spread(self, operator, entity=None, spread=None,
                       query_run_any=False):
        """Each spread that an operator may modify is stored in
        auth_op_attrs as the code_str value."""
        if query_run_any and self._is_admin_or_moderator(operator):
            return True
        if entity and entity.entity_type == self.const.entity_group:
            if spread is not None:
                spread = six.text_type(self.const.Spread(spread))
            if self._is_admin(operator, entity.entity_id):
                if spread in (str(self.const.spread_uio_nis_ng),
                              str(self.const.spread_uio_ad_group),
                              str(self.const.spread_ldap_group)):
                    return True
            if self._is_admin_or_moderator(operator, entity.entity_id):
                if spread in (str(self.const.spread_uio_nis_ng),
                              str(self.const.spread_uio_nis_fg),
                              str(self.const.spread_ifi_nis_fg),
                              str(self.const.spread_ifi_nis_ng),
                              str(self.const.spread_hpc_nis_fg),
                              str(self.const.spread_uio_ad_group),
                              str(self.const.spread_ldap_group)):
                    return True
        return super(UioAuth, self).can_add_spread(operator, entity,
                                                   spread, query_run_any)


class ContactAuth(UioAuth):
    pass


class EmailAuth(UioAuth, BofhdEmailAuth):
    """UiO specific auth for email * commands"""

    def can_email_address_delete(self, operator_id,
                                 account=None,
                                 domain=None,
                                 query_run_any=False):
        """Checks if the operator can delete an address in a given domain.

        Superusers and postmasters are always allowed, but normal users are
        also allowed to delete their own addresses if it is not registered to
        one of their users' active affiliations' OU.
        """
        if self.is_superuser(operator_id):
            return True
        if query_run_any:
            return True
        try:
            return self._is_local_postmaster(
                operator_id, self.const.auth_email_delete, account, domain,
                query_run_any)
        except PermissionDenied:
            pass
        if operator_id != account.entity_id:
            raise PermissionDenied("Can only change e-mail addresses that "
                                   "belongs to your account")
        if domain.entity_id in account.get_prospect_maildomains():
            raise PermissionDenied(
                "Can't delete e-mail addresses from domains the account is "
                "affiliated with")
        return True

    def can_email_forward_info(self, operator, query_run_any=False):
        """Allow access to superusers, postmasters and CERT."""
        if self.is_superuser(operator):
            return True
        if self.is_postmaster(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator,
                self.const.auth_email_forward_info):
            return True
        if query_run_any:
            return False
        raise PermissionDenied('Restricted access')

    def can_email_mod_name(self, operator, person=None, firstname=None,
                           lastname=None, query_run_any=False):
        """If someone is allowed to modify a person's name. """
        if self.is_superuser(operator, query_run_any):
            return True
        if self.is_postmaster(operator, query_run_any):
            return True
        if query_run_any:
            return True

        # Operator can only modify name if owner
        account = Factory.get('Account')(self._db)
        account.find(operator)
        if person.entity_id != account.owner_id:
            raise PermissionDenied('Cannot modify name for other persons')

        all_names = person.get_names()

        # Last name must match one of the registered last names
        last_names = [x['name'] for x in all_names
                      if x['name_variant'] == self.const.name_last]
        if lastname not in last_names:
            raise PermissionDenied("Invalid family name")

        # All parts of the given name must exist somewhere
        first_names = sum([x['name'].split(' ') for x in all_names
                           if x['name_variant'] == self.const.name_first], [])
        for name in firstname.split(' '):
            if name not in first_names:
                raise PermissionDenied('Invalid given name: {}'.format(name))
        return True

    def can_email_move(self, operator, account=None, query_run_any=False):
        if self.is_postmaster(operator, query_run_any):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")


class BofhdRequestsAuth(UioAuth, RequestsAuth):
    pass


class AccessAuth(UioAuth, bofhd_access.BofhdAccessAuth):
    pass


class ApiKeyAuth(UioAuth, bofhd_apikey_cmds.BofhdApiKeyAuth):
    pass


class ExtidAuth(UioAuth, bofhd_external_id.BofhdExtidAuth):
    pass


class PasswordIssuesAuth(UioAuth):
    pass


class CreateUnpersonalAuth(UioAuth,
                           bofhd_user_create_unpersonal.BofhdUnpersonalAuth):
    pass


class OUDiskMappingAuth(UioAuth, bofhd_cmds.BofhdOUDiskMappingAuth):
    pass


class GroupRoleAuth(UioAuth, bofhd_group_roles.BofhdGroupRoleAuth):
    pass


class HistoryAuth(UioAuth, bofhd_history_cmds.BofhdHistoryAuth):
    pass


class OuAuth(UioAuth, bofhd_ou_cmds.OuAuth):
    pass


class OtpAuth(UioAuth, bofhd_otp_cmds.OtpAuth):

    def _owns_important_account(self, person):
        account = Factory.get('Account')(self._db)
        et = EntityTrait(self._db)
        trait = self.const.trait_important_account
        for row in account.search(owner_id=int(person.entity_id)):
            if et.list_traits(code=trait, entity_id=row['account_id'],
                              fetchall=True):
                return True
        return False

    def _is_otp_protected(self, person):
        if self._owns_important_account(person):
            return True
        else:
            return super(OtpAuth, self)._is_otp_protected(person)


class TraitAuth(UioAuth, bofhd_trait_cmds.TraitAuth):

    def can_set_trait(self, operator, trait=None, ety=None, target=None,
                      query_run_any=False):
        if query_run_any:
            return True

        if self.is_superuser(operator):
            return True

        # users can set some of their own traits
        if ety and trait in (self.const.trait_reservation_sms_password,):
            if ety.entity_id == operator:
                return True

        # persons can set some of their own traits
        if ety and trait in (self.const.trait_primary_aff,):
            account = Factory.get('Account')(self._db)
            account.find(operator)
            if ety.entity_id == account.owner_id:
                return True

        # permission can be given via opsets
        if trait and self._has_target_permissions(
                operator=operator, operation=self.const.auth_set_trait,
                target_type=self.const.auth_target_type_host,
                target_id=ety.entity_id, victim_id=ety.entity_id,
                operation_attr=str(trait)):
            return True

        raise PermissionDenied("Not allowed to set trait")

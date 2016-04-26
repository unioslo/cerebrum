# -*- coding: utf-8 -*-

# Copyright 2006-2016 University of Oslo, Norway
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
u""" HiNe bohfd module. """

import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum import Utils

from Cerebrum.modules.bofhd import cmd_param
from Cerebrum.modules.bofhd import bofhd_core_help
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.pwcheck.checker import (check_password,
                                              PasswordNotGoodEnough,
                                              RigidPasswordNotGoodEnough,
                                              PhrasePasswordNotGoodEnough)

from Cerebrum.modules.bofhd.bofhd_utils import copy_func, copy_command
from Cerebrum.modules.no.uio.bofhd_uio_cmds import BofhdExtension as UiOBofhdExtension


def format_day(field):
    fmt = "yyyy-MM-dd"                  # 10 characters wide
    return ":".join((field, "date", fmt))


uio_helpers = [
    '_convert_ticks_to_timestamp',
    '_entity_info',
    '_fetch_member_names',
    '_find_persons',
    '_format_changelog_entry',
    '_format_from_cl',
    '_format_ou_name',
    '_get_access_id',
    '_get_access_id_disk',
    '_get_access_id_global_group',
    '_get_access_id_global_ou',
    '_get_access_id_group',
    '_get_access_id_ou',
    '_get_affiliation_statusid',
    '_get_affiliationid',
    '_get_auth_op_target',
    '_get_cached_passwords',
    '_get_constant',
    '_get_disk',
    '_get_group_opcode',
    '_get_opset',
    '_grant_auth',
    '_group_add',
    '_group_add_entity',
    '_group_count_memberships',
    '_group_remove',
    '_group_remove_entity',
    '_is_yes',
    '_list_access',
    '_manipulate_access',
    '_parse_date',
    '_parse_date_from_to',
    '_remove_auth_role',
    '_remove_auth_target',
    '_revoke_auth',
    '_today',
    '_validate_access',
    '_validate_access_disk',
    '_validate_access_global_group',
    '_validate_access_global_ou',
    '_validate_access_group',
    '_validate_access_ou',
    'user_set_owner_prompt_func',
]

copy_uio = [
    'access_disk',
    'access_global_group',
    'access_global_ou',
    'access_grant',
    'access_group',
    'access_list',
    'access_list_opsets',
    'access_ou',
    'access_revoke',
    'access_show_opset',
    'access_user',
    'entity_history',
    'group_add',
    'group_add_entity',
    'group_delete',
    'group_gadd',
    'group_gremove',
    'group_info',
    'group_list',
    'group_list_expanded',
    'group_memberships',
    'group_remove',
    'group_remove_entity',
    'group_search',
    'group_set_description',
    'misc_affiliations',
    'misc_clear_passwords',
    'misc_list_passwords',
    'misc_verify_password',
    'ou_info',
    'ou_search',
    'ou_tree',
    'person_accounts',
    'person_affiliation_add',
    'person_affiliation_remove',
    'person_create',
    'person_find',
    'person_info',
    'person_list_user_priorities',
    'person_set_name',
    'person_set_user_priority',
    'quarantine_disable',
    'quarantine_list',
    'quarantine_remove',
    'quarantine_set',
    'quarantine_show',
    'spread_add',
    'spread_list',
    'spread_remove',
    'trait_info',
    'trait_list',
    'trait_remove',
    'trait_set',
    'user_affiliation_add',
    'user_affiliation_remove',
    'user_find',
    'user_history',
    'user_info',
    'user_password',
    'user_reserve_personal',
    'user_set_expire',
    'user_set_owner',
]


@copy_command(
    UiOBofhdExtension,
    'all_commands', 'all_commands',
    commands=copy_uio)
@copy_func(
    UiOBofhdExtension,
    methods=uio_helpers + copy_uio)
class BofhdExtension(BofhdCommonMethods):

    OU_class = Utils.Factory.get('OU')
    Account_class = Factory.get('Account')
    Group_class = Factory.get('Group')

    external_id_mappings = {}
    all_commands = {}
    hidden_commands = {}
    parent_commands = True
    authz = BofhdAuth

    def __init__(self, *args, **kwargs):
        super(BofhdExtension, self).__init__(*args, **kwargs)
        self.external_id_mappings['fnr'] = self.const.externalid_fodselsnr

    @classmethod
    def get_help_strings(cls):
        return bofhd_core_help.get_help_strings()

    #
    # misc check_password
    #
    all_commands['misc_check_password'] = cmd_param.Command(
        ("misc", "check_password"),
        cmd_param.AccountPassword())

    def misc_check_password(self, operator, password):
        ac = self.Account_class(self.db)
        try:
            check_password(password, ac, structured=False)
        except RigidPasswordNotGoodEnough as e:
            raise CerebrumError('Bad password: {err_msg}'.format(
                err_msg=str(e).decode('utf-8').encode('latin-1')))
        except PhrasePasswordNotGoodEnough as e:
            raise CerebrumError('Bad passphrase: {err_msg}'.format(
                err_msg=str(e).decode('utf-8').encode('latin-1')))
        except PasswordNotGoodEnough as e:
            raise CerebrumError('Bad password: {err_msg}'.format(err_msg=e))
        crypt = ac.encrypt_password(
            self.const.Authentication("crypt3-DES"), password)
        md5 = ac.encrypt_password(
            self.const.Authentication("MD5-crypt"), password)
        sha256 = ac.encrypt_password(
            self.const.auth_type_sha256_crypt, password)
        sha512 = ac.encrypt_password(
            self.const.auth_type_sha512_crypt, password)
        return ("OK.\n  crypt3-DES:   %s\n  MD5-crypt:    %s\n"
                "  SHA256-crypt: %s\n  SHA512-crypt: %s") % (
                    crypt, md5, sha256, sha512)

    def _person_affiliation_add_helper(
            self, operator, person, ou, aff, aff_status):
        """Helper-function for adding an affiliation to a person with
        permission checking.  person is expected to be a person
        object, while ou, aff and aff_status should be the textual
        representation from the client"""
        aff = self._get_affiliationid(aff)
        aff_status = self._get_affiliation_statusid(aff, aff_status)
        ou = self._get_ou(stedkode=ou)

        # Assert that the person already have the affiliation
        has_aff = False
        for a in person.get_affiliations():
            if a['ou_id'] == ou.entity_id and a['affiliation'] == aff:
                if a['status'] == aff_status:
                    has_aff = True
                elif a['source_system'] == self.const.system_manual:
                    raise CerebrumError("Person has conflicting aff_status "
                                        "for this OU/affiliation combination")
        if not has_aff:
            self.ba.can_add_affiliation(operator.get_entity_id(),
                                        person, ou, aff, aff_status)
            person.add_affiliation(ou.entity_id, aff,
                                   self.const.system_manual,
                                   aff_status)
            person.write_db()
        return ou, aff, aff_status

    #
    # access list_alterable [group/maildom/host/disk] [username]
    # This command is for listing out what groups an account is a moderator of
    # in Brukerinfo.
    #
    hidden_commands['access_list_alterable'] = cmd_param.Command(
        ('access', 'list_alterable'),
        cmd_param.SimpleString(optional=True),
        cmd_param.AccountName(optional=True),
        fs=cmd_param.FormatSuggestion(
            "%10d %15s     %s",
            ("entity_id", "entity_type", "entity_name")))

    def access_list_alterable(
            self, operator, target_type='group', access_holder=None):
        """List entities that access_holder can moderate."""

        if access_holder is None:
            account_id = operator.get_entity_id()
        else:
            account = self._get_account(access_holder, actype="PosixUser")
            account_id = account.entity_id

        if not (account_id == operator.get_entity_id()
                or self.ba.is_superuser(operator.get_entity_id())):
            raise PermissionDenied(
                "You do not have permission for this operation")

        result = list()
        matches = self.ba.list_alterable_entities(account_id, target_type)
        if len(matches) > cereconf.BOFHD_MAX_MATCHES_ACCESS:
            raise CerebrumError("More than %d (%d) matches. Refusing to return"
                                " result" % (cereconf.BOFHD_MAX_MATCHES_ACCESS,
                                             len(matches)))
        for row in matches:
            entity = self._get_entity(ident=row["entity_id"])
            etype = str(self.const.EntityType(entity.entity_type))
            ename = self._get_entity_name(entity.entity_id, entity.entity_type)
            tmp = {"entity_id": row["entity_id"],
                   "entity_type": etype,
                   "entity_name": ename, }
            if entity.entity_type == self.const.entity_group:
                tmp["description"] = entity.description

            result.append(tmp)
        return result

    #
    # get_constant_description <const class> [?]
    #
    hidden_commands['get_constant_description'] = cmd_param.Command(
        ("misc", "get_constant_description"),
        cmd_param.SimpleString(),   # constant class
        cmd_param.SimpleString(optional=True),
        fs=cmd_param.FormatSuggestion("%-15s %s", ("code_str", "description")))

    def get_constant_description(self, operator, code_cls, code_str=None):
        """Fetch constant descriptions.

        There are no permissions checks for this method -- it can be called by
        anyone without any restrictions.

        @type code_cls: basestring
        @param code_cls:
          Class (name) for the constants to fetch.

        @type code_str: basestring or None
        @param code_str:
          code_str for the specific constant to fetch. If None is specified,
          *all* constants of the given type are retrieved.

        @rtype: dict or a sequence of dicts
        @return:
          Description of the specified constants. Each dict has 'code' and
          'description' keys.
        """

        if not hasattr(self.const, code_cls):
            raise CerebrumError("%s is not a constant type" % code_cls)

        kls = getattr(self.const, code_cls)
        if not issubclass(kls, self.const.CerebrumCode):
            raise CerebrumError("%s is not a valid constant class" % code_cls)

        if code_str is not None:
            c = self._get_constant(kls, code_str)
            return {"code": int(c),
                    "code_str": str(c),
                    "description": c.description}

        # Fetch all of the constants of the specified type
        return [{"code": int(x),
                 "code_str": str(x),
                 "description": x.description}
                for x in self.const.fetch_constants(kls)]

    def _person_create_externalid_helper(self, person):
        person.affect_external_id(self.const.system_manual,
                                  self.const.externalid_fodselsnr)

    #
    # email info [username]
    #
    all_commands['email_info'] = cmd_param.Command(
        ("email", "info"),
        cmd_param.AccountName(help_ref="account_name", repeat=True),
        perm_filter='can_email_info',
        fs=cmd_param.FormatSuggestion([
            ("Type:             %s", ("target_type",)),
            ("Account:          %s", ("account",)),
            ("Primary address:  %s", ("def_addr",)),
        ]))

    def email_info(self, operator, uname):
        """ email info for an account. """
        acc = self._get_account(uname)
        ret = []
        ret += [{'target_type': "Account", }, ]
        ret.append({'def_addr': acc.get_primary_mailaddress()})
        return ret

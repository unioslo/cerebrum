# -*- coding: utf-8 -*-
#
# Copyright 2006-2018 University of Oslo, Norway
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
""" NMH bofhd module. """
import mx

from Cerebrum import database
from Cerebrum import Utils
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd import bofhd_contact_info
from Cerebrum.modules.bofhd import bofhd_core_help
from Cerebrum.modules.bofhd import bofhd_email
from Cerebrum.modules.bofhd import cmd_param
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.bofhd_user_create import BofhdUserCreateMethod
from Cerebrum.modules.bofhd.bofhd_utils import copy_func, copy_command
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.access_FS import make_fs
from Cerebrum.modules.no.uio.bofhd_uio_cmds import BofhdExtension as cmd_base
from Cerebrum.modules.bofhd import bofhd_access


def format_day(field):
    fmt = "yyyy-MM-dd"                  # 10 characters wide
    return ":".join((field, "date", fmt))


class NmhAuth(bofhd_contact_info.BofhdContactAuth, BofhdAuth):
    """ NMH specific auth.

    Inherits from BofhdContactAuth as a hack, to make can_get_contact_info
    available to 'person_info'.
    """
    pass


class NmhContactAuth(NmhAuth):
    """ NMH specific contact info auth. """
    pass


class NmhEmailAuth(NmhAuth, bofhd_email.BofhdEmailAuth):
    """ NMH specific email auth. """
    pass


class NmhAccessAuth(NmhAuth, bofhd_access.BofhdAccessAuth):
    """Nmh specific authentication checks

    Used for overriding default behavior or Nmh specific behavior

    """
    pass


uio_helpers = [
    '_assert_group_deletable',
    '_entity_info',
    '_fetch_member_names',
    '_format_changelog_entry',
    '_format_from_cl',
    '_get_affiliation_statusid',
    '_get_affiliationid',
    '_get_cached_passwords',
    '_get_group_opcode',
    '_get_posix_account',
    '_group_add',
    '_group_add_entity',
    '_group_count_memberships',
    '_group_remove',
    '_group_remove_entity',
    '_person_affiliation_add_helper',
    '_remove_auth_role',
    '_remove_auth_target',
    'user_set_owner_prompt_func',
]

uio_commands = [
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
    'group_memberships_expanded',
    'group_remove',
    'group_remove_entity',
    'group_search',
    'group_set_description',
    'misc_affiliations',
    'misc_check_password',
    'misc_clear_passwords',
    'misc_list_passwords',
    'misc_verify_password',
    'ou_info',
    'ou_search',
    'ou_tree',
    'person_accounts',
    'person_affiliation_add',
    'person_affiliation_remove',
    'person_clear_id',
    'person_clear_name',
    'person_create',
    'person_find',
    'person_get_id',
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
    'user_affiliation_add',
    'user_affiliation_remove',
    'user_find',
    'user_history',
    'user_info',
    'user_password',
    'user_set_expire',
    'user_set_owner',
]


@copy_command(
    cmd_base,
    'all_commands', 'all_commands',
    commands=uio_commands)
@copy_func(
    BofhdUserCreateMethod,
    methods=['_user_create_set_account_type'])
@copy_func(
    cmd_base,
    methods=uio_helpers + uio_commands)
class BofhdExtension(BofhdCommonMethods):

    OU_class = Utils.Factory.get('OU')
    Account_class = Factory.get('Account')
    Group_class = Factory.get('Group')

    all_commands = {}
    parent_commands = True
    external_id_mappings = {}
    authz = NmhAuth

    @classmethod
    def get_help_strings(cls):
        return (bofhd_core_help.group_help,
                bofhd_core_help.command_help,
                bofhd_core_help.arg_help)

    #
    # person student_info
    #
    all_commands['person_student_info'] = cmd_param.Command(
        ("person", "student_info"),
        cmd_param.PersonId(),
        fs=cmd_param.FormatSuggestion(
            [("Studieprogrammer: %s, %s, %s, %s, tildelt=%s->%s privatist: %s",
              ("studprogkode",
               "studieretningkode",
               "studierettstatkode",
               "studentstatkode",
               format_day("dato_tildelt"),
               format_day("dato_gyldig_til"),
               "privatist")
              ),
             ("Eksamensmeldinger: %s (%s), %s",
              ("ekskode", "programmer", format_day("dato"))),
             ("Utd. plan: %s, %s, %d, %s",
              ("studieprogramkode",
               "terminkode_bekreft",
               "arstall_bekreft",
               format_day("dato_bekreftet"))),
             ("Semesterreg: %s, %s, FS bet. reg: %s, endret: %s",
              ("regformkode",
               "betformkode",
               format_day("dato_endring"),
               format_day("dato_regform_endret"))),
             ]
        ),
        perm_filter='can_get_student_info')

    def person_student_info(self, operator, person_id):
        person = self._get_person(*self._map_person_id(person_id))
        self.ba.can_get_student_info(operator.get_entity_id(), person)
        fnr = person.get_external_id(id_type=self.const.externalid_fodselsnr,
                                     source_system=self.const.system_fs)
        if not fnr:
            raise CerebrumError("No matching fnr from FS")
        fodselsdato, pnum = fodselsnr.del_fnr(fnr[0]['external_id'])
        ret = []
        try:
            fs_db = make_fs()
        except database.DatabaseError, e:
            self.logger.warn("Can't connect to FS (%s)" % e)
            raise CerebrumError("Can't connect to FS, try later")

        har_opptak = set()
        for row in fs_db.student.get_studierett(fodselsdato, pnum):
            har_opptak.add(row['studieprogramkode'])
            ret.append(
                {
                    'studprogkode': row['studieprogramkode'],
                    'studierettstatkode': row['studierettstatkode'],
                    'studentstatkode': row['studentstatkode'],
                    'studieretningkode': row['studieretningkode'],
                    'dato_tildelt': self._ticks_to_date(
                        row['dato_studierett_tildelt']),
                    'dato_gyldig_til': self._ticks_to_date(
                        row['dato_studierett_gyldig_til']),
                    'privatist': row['status_privatist'],
                }
            )

        for row in fs_db.student.get_eksamensmeldinger(fodselsdato, pnum):
            programmer = []
            for row2 in fs_db.info.get_emne_i_studieprogram(row['emnekode']):
                if row2['studieprogramkode'] in har_opptak:
                    programmer.append(row2['studieprogramkode'])
            ret.append(
                {
                    'ekskode': row['emnekode'],
                    'programmer': ",".join(programmer),
                    'dato': self._ticks_to_date(row['dato_opprettet']),
                }
            )

        for row in fs_db.student.get_utdanningsplan(fodselsdato, pnum):
            ret.append(
                {
                    'studieprogramkode': row['studieprogramkode'],
                    'terminkode_bekreft': row['terminkode_bekreft'],
                    'arstall_bekreft': row['arstall_bekreft'],
                    'dato_bekreftet': self._ticks_to_date(
                        row['dato_bekreftet']),
                }
            )

        for row in fs_db.student.get_semreg(fodselsdato, pnum):
            ret.append(
                {
                    'regformkode': row['regformkode'],
                    'betformkode': row['betformkode'],
                    'dato_endring': self._ticks_to_date(row['dato_endring']),
                    'dato_regform_endret': self._ticks_to_date(
                        row['dato_regform_endret']),
                }
            )
        return ret

    #
    # user delete
    #
    all_commands['user_delete'] = cmd_param.Command(
        ("user", "delete"),
        cmd_param.AccountName(),
        perm_filter='can_delete_user')

    def user_delete(self, operator, accountname):
        account = self._get_account(accountname)
        self.ba.can_delete_user(operator.get_entity_id(), account)
        if account.is_deleted():
            raise CerebrumError("User is already deleted")
        account.expire_date = mx.DateTime.now()
        for s in account.get_spread():
            account.delete_spread(int(s['spread']))
        account.write_db()
        return "User %s queued for deletion immediately" % account.account_name


class ContactCommands(bofhd_contact_info.BofhdContactCommands):
    authz = NmhContactAuth


@copy_command(
    bofhd_email.BofhdEmailCommands,
    'all_commands', 'all_commands',
    commands=['email_mod_name', ])
class EmailCommands(bofhd_email.BofhdEmailCommands):
    """ NMH specific email commands and overloads. """

    all_commands = {}
    hidden_commands = {}
    parent_commands = False  # copied with copy_command
    omit_parent_commands = set()
    authz = NmhEmailAuth


class NmhAccessCommands(bofhd_access.BofhdAccessCommands):
    """This is the place for Nmh specific bofhd access * commands

    """
    authz = NmhAccessAuth

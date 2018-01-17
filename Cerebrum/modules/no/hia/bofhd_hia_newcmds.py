#!/usr/bin/env python
# encoding: utf-8
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
""" Bofhd for UiA. """

from mx import DateTime

import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum import Database

from Cerebrum.modules import Email
from Cerebrum.modules import Note
from Cerebrum.modules.bofhd import cmd_param
from Cerebrum.modules.no.hia import bofhd_hia_help
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.bofhd_email import BofhdEmailMixin
from Cerebrum.modules.bofhd.bofhd_email_list import BofhdEmailSympaMixin
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.modules.bofhd.auth import BofhdAuthOpSet, BofhdAuthOpTarget, \
    BofhdAuthRole
from Cerebrum.modules.no.hia.bofhd_uia_auth import BofhdAuth
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.hia.access_FS import FS

from Cerebrum.modules.bofhd.bofhd_utils import copy_func, copy_command
from Cerebrum.modules.no.uio.bofhd_uio_cmds import BofhdExtension as UiOBofhdExtension
from Cerebrum.modules.bofhd.bofhd_user_create import BofhdUserCreateMethod


def format_day(field):
    fmt = "yyyy-MM-dd"                  # 10 characters wide
    return ":".join((field, "date", fmt))


def date_to_string(date):
    """Takes a DateTime-object and formats a standard ISO-datestring
    from it.

    Custom-made for our purposes, since the standard XMLRPC-libraries
    restrict formatting to years after 1899, and we see years prior to
    that.

    """
    if not date:
        return "<not set>"

    return "%04i-%02i-%02i" % (date.year, date.month, date.day)


# Helper methods from bofhd_uio_cmd
uio_helpers = [
    '_convert_ticks_to_timestamp',
    '_entity_info',
    '_fetch_member_names',
    '_format_changelog_entry',
    '_format_from_cl',
    '_get_access_id',
    '_get_access_id_disk',
    '_get_access_id_global_group',
    '_get_access_id_global_ou',
    '_get_access_id_group',
    '_get_access_id_host',
    '_get_access_id_ou',
    '_get_affiliation_statusid',
    '_get_affiliationid',
    '_get_auth_op_target',
    '_get_cached_passwords',
    '_get_disk',
    '_get_group_opcode',
    '_get_host',
    '_get_opset',
    '_get_posix_account',
    '_get_shell',
    '_grant_auth',
    '_group_add',
    '_group_add_entity',
    '_group_count_memberships',
    '_group_remove',
    '_group_remove_entity',
    '_is_yes',
    '_list_access',
    '_lookup_old_uid',
    '_manipulate_access',
    '_parse_date',
    '_person_affiliation_add_helper',
    '_person_create_externalid_helper',
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

# Methods and commands from bofhd_uio_cmd
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
    'group_def',
    'group_delete',
    'group_demote_posix',
    'group_gadd',
    'group_gremove',
    'group_info',
    'group_list',
    'group_list_expanded',
    'group_memberships',
    'group_padd',
    'group_personal',
    'group_promote_posix',
    'group_remove',
    'group_remove_entity',
    'group_search',
    'group_set_description',
    'group_set_expire',
    'group_set_visibility',
    'misc_affiliations',
    'misc_cancel_request',
    'misc_check_password',
    'misc_clear_passwords',
    'misc_list_passwords',
    'misc_list_requests',
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
    'person_list_user_priorities',
    'person_set_bdate',
    'person_set_id',
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
    'user_demote_posix',
    'user_find',
    'user_gecos',
    'user_history',
    'user_password',
    'user_reserve_personal',
    'user_create_unpersonal',
    'user_set_disk_status',
    'user_set_expire',
    'user_set_np_type',
    'user_set_owner',
    'user_shell',
]

copy_uio_hidden = [
    'access_list_alterable',
    'group_multi_add',
    'person_name_suggestions',
    'get_constant_description',
]

# Decide which email mixins to use
email_mixin_commands = [
    'email_add_address',
    'email_add_domain_affiliation',
    'email_add_filter',
    'email_add_forward',
    'email_add_tripnote',
    'email_create_domain',
    'email_create_forward',
    'email_domain_configuration',
    'email_domain_info',
    'email_forward',
    'email_info',
    'email_list_tripnotes',
    'email_local_delivery',
    'email_mod_name',
    'email_quota',
    'email_reassign_address',
    'email_remove_address',
    'email_remove_domain_affiliation',
    'email_remove_filter',
    'email_remove_forward',
    'email_remove_tripnote',
    'email_set_primary_address',
    'email_spam_action',
    'email_spam_level',
    'email_tripnote',
    'email_update',
]

# Decide which sympa list commands to use
email_sympa_mixin_commands = [
    'sympa_create_list',
    'sympa_create_list_alias',
    'sympa_create_list_in_cerebrum',
    'sympa_remove_list',
    'sympa_remove_list_alias',
]


@copy_command(
    BofhdEmailMixin,
    'default_email_commands', 'all_commands',
    commands=email_mixin_commands)
@copy_command(
    BofhdEmailSympaMixin,
    'default_sympa_commands', 'all_commands',
    commands=email_sympa_mixin_commands)
@copy_command(
    UiOBofhdExtension,
    'hidden_commands', 'hidden_commands',
    commands=copy_uio_hidden)
@copy_command(
    UiOBofhdExtension,
    'all_commands', 'all_commands',
    commands=copy_uio)
@copy_func(
    UiOBofhdExtension,
    methods=uio_helpers + copy_uio + copy_uio_hidden)
@copy_func(
    BofhdUserCreateMethod,
    methods=['_user_create_set_account_type']
)
class BofhdExtension(
        BofhdCommonMethods,
        BofhdEmailMixin,
        BofhdEmailSympaMixin):
    """ The main UiA BofhdExtension. """

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
        return bofhd_hia_help.get_help_strings()

    # helpers needed for spread_add, cannot be copied in the usual way
    #
    def _spread_sync_group(self, account, group=None):
        """Make sure the group has the NIS spreads corresponding to
        the NIS spreads of the account.  The account and group
        arguments may be passed as Entity objects.  If group is None,
        the group with the same name as account is modified, if it
        exists."""

        if account.np_type or account.owner_type == self.const.entity_group:
            return

        if group is None:
            name = account.get_name(self.const.account_namespace)
            try:
                group = self._get_group(name)
            except CerebrumError:
                return

        # FIXME: Identifying personal groups is not a very precise
        # process.  One alternative would be to use the description:
        #
        # if not group.description.startswith('Personal file group for '):
        #     return
        #
        # The alternative is to use the bofhd_auth tables to see if
        # the account has the 'Group-owner' op_set for this group, and
        # this is implemented below.

        op_set = BofhdAuthOpSet(self.db)
        op_set.find_by_name(cereconf.BOFHD_AUTH_GROUPMODERATOR)

        baot = BofhdAuthOpTarget(self.db)
        targets = baot.list(entity_id=group.entity_id)
        if len(targets) == 0:
            return
        bar = BofhdAuthRole(self.db)
        is_moderator = False
        for auth in bar.list(op_target_id=targets[0]['op_target_id']):
            if (auth['entity_id'] == account.entity_id
                    and auth['op_set_id'] == op_set.op_set_id):
                is_moderator = True
        if not is_moderator:
            return

        mapping = { int(self.const.spread_nis_user):
                    int(self.const.spread_nis_fg),
                    int(self.const.spread_ans_nis_user):
                    int(self.const.spread_ans_nis_fg) }
        wanted = []
        for r in account.get_spread():
            spread = int(r['spread'])
            if spread in mapping:
                wanted.append(mapping[spread])
        for r in group.get_spread():
            spread = int(r['spread'])
            if spread not in mapping.values():
                pass
            elif spread in wanted:
                wanted.remove(spread)
            else:
                group.delete_spread(spread)
        for spread in wanted:
            group.add_spread(spread)

    def _email_info_detail(self, acc):
        info = []
        eq = Email.EmailQuota(self.db)
        try:
            eq.find_by_target_entity(acc.entity_id)
            et = Email.EmailTarget(self.db)
            et.find_by_target_entity(acc.entity_id)
            es = Email.EmailServer(self.db)
            es.find(et.email_server_id)
            used = 'N/A'
            limit = None
            homemdb = None
            tmp = acc.get_trait(self.const.trait_exchange_mdb)
            if tmp != None:
                homemdb = tmp['strval']
            else:
                homemdb = 'N/A'
            info.append({'quota_hard': eq.email_quota_hard,
                         'quota_soft': eq.email_quota_soft,
                         'quota_used': used})
            info.append({'dis_quota_hard': eq.email_quota_hard,
                         'dis_quota_soft': eq.email_quota_soft})
            # should not be shown for accounts without exchange-spread, needs fixin', Jazz 2011-02-21
            info.append({'homemdb': homemdb})
        except Errors.NotFoundError:
            pass
        return info

    def _append_entity_notes(self, info_list, operator, entity_id):
        """Helper for adding entity notes to the output of info commands,
        if present and viewable for the operator."""
        try:
            self.ba.can_show_notes(operator.get_entity_id())

            enote = Note.EntityNote(self.db)
            enote.find(entity_id)

            for n in enote.get_notes():
                info_list.append({
                    'note_id':
                    n['note_id'],
                    'note_subject':
                    n['subject'] if len(n['subject']) > 0 else '<not set>',
                    'note_description':
                    n['description'] if len(n['description']) > 0
                    else '<not set>'
                })
        except:
            pass

    #
    # email migrate
    # will be used for migretion of mail accounts from IMAP to Exchange
    #
    all_commands['email_exchange_migrate'] = cmd_param.Command(
        ("email", "exchange_migrate"),
        cmd_param.AccountName(help_ref="account_name", repeat=True),
        perm_filter='can_email_move')

    def email_exchange_migrate(self, operator, uname):
        acc = self._get_account(uname)
        self.ba.can_email_move(operator.get_entity_id(), acc)
        # raise error if no e-mail account exist in IMAP
        if (not acc.has_spread(self.const.spread_hia_email) or
                not acc.has_spread(self.const.spread_exchange_acc_old)):
            raise CerebrumError("No mail spread to migrate from for %s" % uname)
        et = Email.EmailTarget(self.db)
        et.find_by_target_entity(acc.entity_id)
        # raise error if e-mail target is deleted
        if et.email_target_type == self.const.email_target_deleted:
            raise CerebrumError("Cannot migrate deleted e-mail target for account %s", uname)
        # assign new e-mail server
        es = Email.EmailServer(self.db)
        # only one exchange server is in use at UiA
        es.find_by_name('exchkrs01.uia.no')
        et.email_server_id = es.entity_id
        et.write_db()
        # remove IMAP- and old Exchange-spread
        acc.delete_spread(self.const.spread_hia_email)
        acc.delete_spread(self.const.spread_exchange_acc_old)
        acc.write_db()
        # add exchange-spread
        if not acc.has_spread(self.const.spread_exchange_account):
            acc.add_spread(self.const.spread_exchange_account)
            acc.write_db()
        return "OK, migrating %s to Exchange" % (uname)

    #
    # email move
    #
    all_commands['email_move'] = cmd_param.Command(
        ("email", "move"),
        cmd_param.AccountName(help_ref="account_name", repeat=True),
        cmd_param.SimpleString(help_ref='string_email_host'),
        perm_filter='can_email_move')

    def email_move(self, operator, uname, server):
        acc = self._get_account(uname)
        self.ba.can_email_move(operator.get_entity_id(), acc)
        et = Email.EmailTarget(self.db)
        et.find_by_target_entity(acc.entity_id)
        old_server = et.email_server_id
        es = Email.EmailServer(self.db)
        es.find_by_name(server)
        et.email_server_id = es.entity_id
        et.write_db()
        return "OK, updated e-mail server for %s (to %s)" % (uname, server)

    #
    # person info <persin-id>
    #
    all_commands['person_info'] = cmd_param.Command(
        ("person", "info"),
        cmd_param.PersonId(help_ref="id:target:person"),
        fs=cmd_param.FormatSuggestion([
            ("Name:          %s\n" +
             "Entity-id:     %i\n" +
             "Birth:         %s\n" +
             "Affiliations:  %s [from %s], last seen: %s", ("name",
                                                            "entity_id",
                                                            "birth",
                                                            "affiliation_1",
                                                            "source_system_1",
                                                            "last_seen_1")),
            ("               %s [from %s], last seen: %s", ("affiliation",
                                                            "source_system",
                                                            "last_seen")),
            ("Names:         %s [from %s]", ("names", "name_src")),
            ("Fnr:           %s [from %s]", ("fnr", "fnr_src")),
            ("External id:   %s [from %s]", ("extid", "extid_src")),
            ("Mobile:        %s [from %s]", ("mobile", "mobile_src")),
            ("Telephone:     %s [from %s]", ("phone", "phone_src")),
            ("Address:       %s", ("address_line_1",)),
            ("               %s", ("address_line",)),
            ("               %s %s", ("address_zip", "address_city")),
            ("               %s [from %s]", ("address_country",
                                             'address_source')),
            ("Office:        %s Room: %s [from %s]", ("office_code",
                                                      "office_room",
                                                      "office_source")),
            ("Contact:       %s: %s [from %s]", ("contact_type", "contact",
                                                 "contact_src")),
            ("Note:          (#%d) %s: %s", ('note_id',
                                             'note_subject',
                                             'note_description')),
            ("Title:         %s [from %s]", ("employment_title",
                                             "source_system")),
            ("Primary account: %s [%s]", ("prim_acc", 'prim_acc_status')),
            ("Primary email: %s", ("prim_email",))
        ]))

    def person_info(self, operator, person_id):
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        try:
            p_name = person.get_name(self.const.system_cached,
                                     getattr(self.const,
                                             cereconf.DEFAULT_GECOS_NAME))
            p_name = p_name + ' [from Cached]'
        except Errors.NotFoundError:
            raise CerebrumError("No name is registered for this person")

        data = [{'name': p_name,
                 'entity_id': person.entity_id,
                 'birth': date_to_string(person.birth_date),
                 'entity_id': person.entity_id}]

        affiliations = []
        sources = []
        last_seen = []

        for row in person.get_affiliations():
            ou = self._get_ou(ou_id=row['ou_id'])
            affiliations.append("%s@%s" % (
                self.const.PersonAffStatus(row['status']),
                self._format_ou_name(ou),
            ))
            sources.append(
                str(self.const.AuthoritativeSystem(row['source_system']))
            )
            last_seen.append(row['last_date'].date)

        for ss in cereconf.SYSTEM_LOOKUP_ORDER:
            ss = getattr(self.const, ss)
            person_name = ""
            for type in [self.const.name_first, self.const.name_last]:
                try:
                    person_name += person.get_name(ss, type) + ' '
                except Errors.NotFoundError:
                    continue
            if person_name:
                data.append({'names': person_name,
                             'name_src': str(
                                 self.const.AuthoritativeSystem(ss))
                             })
        if affiliations:
            data[0]['affiliation_1'] = affiliations[0]
            data[0]['source_system_1'] = sources[0]
            data[0]['last_seen_1'] = last_seen[0]
        else:
            data[0]['affiliation_1'] = "<none>"
            data[0]['source_system_1'] = "<nowhere>"
            data[0]['last_seen_1'] = "<never>"
        for i in range(1, len(affiliations)):
            data.append({'affiliation': affiliations[i],
                         'source_system': sources[i],
                         'last_seen': last_seen[i],
                         })
        account = self.Account_class(self.db)
        account_ids = [int(r['account_id'])
                       for r in account.list_accounts_by_owner_id(
                           person.entity_id)]
        if (self.ba.is_superuser(operator.get_entity_id()) or
                operator.get_entity_id() in account_ids):
            # Show fnr
            for row in person.get_external_id(
                    id_type=self.const.externalid_fodselsnr):
                data.append({'fnr': row['external_id'],
                             'fnr_src': str(self.const.AuthoritativeSystem(
                                            row['source_system']))})

        # Show contact info, like address and mobile number, and also external
        # ids from FS and SAP.
        # Can only be shown by those that can set passwords for one of the
        # person's accounts.
        can_show_contact_info = False
        for a in account_ids:
            try:
                self.ba.can_set_password(operator.get_entity_id(),
                                         self._get_account(a, idtype='id'))
                can_show_contact_info = True
                break
            except PermissionDenied:
                pass
        if can_show_contact_info:
            for source, kind in ((self.const.system_sap,
                                  self.const.address_post),
                                 (self.const.system_fs,
                                  self.const.address_post),
                                 (self.const.system_sap,
                                  self.const.address_post_private),
                                 (self.const.system_fs,
                                  self.const.address_post_private)):
                address = person.get_entity_address(source=source,
                                                    type=kind)
                if address:
                    address = address[0]
                    break
                address = None
            if address:
                try:
                    for nr, line in enumerate(
                            address['address_text'].split("\n")):
                        if nr is 0:
                            data.append({'address_line_1': line})
                        else:
                            data.append({'address_line': line})
                except AttributeError:
                    data.append({'address_line_1': ''})
                data.append({'address_zip':  str(address['postal_number']),
                             'address_city': address['city']})
                address_country = ''
                if address['country']:
                    country_codes = dict((c['code'], c['country']) for c in
                                         person.list_country_codes())
                    if address['country'] in country_codes:
                        address_country = str(
                            country_codes[address['country']]
                        )
                data.append({'address_country': address_country,
                             'address_source':
                             str(self.const.AuthoritativeSystem(
                                 address['source_system']))}
                            )
            # External ids from FS and SAP
            for extid in (self.const.externalid_sap_ansattnr,
                          self.const.externalid_studentnr):
                for row in person.get_external_id(id_type=extid):
                    data.append({'extid': row['external_id'],
                                 'extid_src': str(
                                     self.const.AuthoritativeSystem(
                                         row['source_system']))})

            # Show telephone numbers
            for row in person.get_contact_info():
                if (row['contact_type']
                    not in (self.const.contact_phone,
                            self.const.contact_mobile_phone,
                            self.const.contact_phone_private,
                            self.const.contact_private_mobile)):
                    continue

                # Get string values of row['source_system'] and
                # row['contact_type']to avoid insanely long
                # lines that breaks PEP-8 standards
                source_system_string = str(self.const.AuthoritativeSystem(
                                           row['source_system']))
                contact_type_string = str(self.const.ContactInfo(
                                          row['contact_type']))

                # Skip phone, private phone and private mobile values from SAP
                if (source_system_string == str(self.const.system_sap) and
                    row['contact_type'] in (self.const.contact_phone_private,
                                            self.const.contact_private_mobile,
                                            self.const.contact_phone)):
                    continue

                data.append({'contact': row['contact_value'],
                             'contact_src': source_system_string,
                             'contact_type': contact_type_string})

            # Office addresses
            for row in person.get_contact_info(self.const.system_sap,
                                               self.const.contact_office):

                source_system_string = str(self.const.AuthoritativeSystem(
                                           row['source_system']))

                # TODO: add office address here too?
                data.append({'office_code': row['contact_value'],
                             'office_room': row['contact_alias'],
                             'office_source': source_system_string})

        # Append entity notes to data
        self._append_entity_notes(data, operator, person.entity_id)

        # Add job title from SAP
        try:
            employment = person.search_employment(
                person_id=person.entity_id, main_employment=True).next()
            data.append({
                'employment_title': str(employment['description']),
                'source_system': str(self.const.AuthoritativeSystem(
                    employment['source_system']))})
        except:
            pass

        # Get primary account
        acc_id = person.get_primary_account()
        if acc_id:
            account.find(acc_id)
            data.append({'prim_acc': account.account_name,
                         'prim_acc_status': 'Active'})
        else:
            # Accounts deleted or expired
            accounts = account.get_account_types(owner_id=person.entity_id,
                                                filter_expired=False)
            if accounts:
                account.clear()
                account.find(accounts[0]['account_id'])
                data.append({'prim_acc': account.account_name,
                             'prim_acc_status':
                                'Expired %s' % account.expire_date.date})
            else:
                data.append({'prim_acc': None,
                             'prim_acc_status': 'none found'})
        # Fetch primary email
        if acc_id:
            data.append({'prim_email': account.get_primary_mailaddress()})
        else:
            data.append({'prim_email': None})
        return data

    #
    # person student_info
    #
    all_commands['person_student_info'] = cmd_param.Command(
        ("person", "student_info"),
        cmd_param.PersonId(),
        fs=cmd_param.FormatSuggestion([
            ("Studieprogrammer: %s, %s, %s, tildelt=%s->%s privatist: %s",
             ("studprogkode", "studierettstatkode", "status", format_day("dato_studierett_tildelt"),
              format_day("dato_studierett_gyldig_til"), "privatist")),
            ("Eksamensmeldinger: %s (%s), %s",
             ("ekskode", "programmer", format_day("dato"))),
            ("Utd. plan: %s, %s, %d, %s",
             ("studieprogramkode", "terminkode_bekreft", "arstall_bekreft",
              format_day("dato_bekreftet"))),
            ("Semesterreg: %s, %s, betalt: %s, endret: %s",
             ("regformkode", "betformkode", format_day("dato_betaling"),
              format_day("dato_regform_endret"))),
            ("Kull: %s, (%s)", ("kullkode", "status_aktiv"))
        ]),
        perm_filter='can_get_student_info')

    def person_student_info(self, operator, person_id):
        person = self._get_person(*self._map_person_id(person_id))
        self.ba.can_get_student_info(operator.get_entity_id(), person)
        fnr = person.get_external_id(id_type=self.const.externalid_fodselsnr,
                                     source_system=self.const.system_fs)
        if not fnr:
            raise CerebrumError("No matching fnr from FS")
        fodselsdato, pnum = fodselsnr.del_fnr(fnr[0]['external_id'])
        har_opptak = {}
        ret = []
        db = Database.connect(user="I0201_cerebrum", service="FSUIA.uio.no",
                              DB_driver='cx_Oracle')
        fs = FS(db)
        for row in fs.student.get_studierett(fodselsdato, pnum):
            har_opptak["%s" % row['studieprogramkode']] = \
                              row['status_privatist']
            ret.append({'studprogkode': row['studieprogramkode'],
                        'studierettstatkode': row['studierettstatkode'],
                        'status': row['studentstatkode'],
                        'dato_studierett_tildelt': DateTime.DateTimeFromTicks(row['dato_studierett_tildelt']),
                        'dato_studierett_gyldig_til': DateTime.DateTimeFromTicks(row['dato_studierett_gyldig_til']),
                        'privatist': row['status_privatist']})

        for row in fs.student.get_eksamensmeldinger(fodselsdato, pnum):
            programmer = []
            for row2 in fs.info.get_emne_i_studieprogram(row['emnekode']):
                if har_opptak.has_key("%s" % row2['studieprogramkode']):
                    programmer.append(row2['studieprogramkode'])
            ret.append({'ekskode': row['emnekode'],
                        'programmer': ",".join(programmer),
                        'dato': DateTime.DateTimeFromTicks(row['dato_opprettet'])})

        for row in fs.student.get_utdanningsplan(fodselsdato, pnum):
            ret.append({'studieprogramkode': row['studieprogramkode'],
                        'terminkode_bekreft': row['terminkode_bekreft'],
                        'arstall_bekreft': row['arstall_bekreft'],
                        'dato_bekreftet': DateTime.DateTimeFromTicks(row['dato_bekreftet'])})

        for row in fs.student.get_semreg(fodselsdato, pnum):
            ret.append({'regformkode': row['regformkode'],
                        'betformkode': row['betformkode'],
                        'dato_betaling': DateTime.DateTimeFromTicks(row['dato_betaling']),
                        'dato_regform_endret': DateTime.DateTimeFromTicks(row['dato_regform_endret'])})

        for row in fs.student.get_student_kull(fodselsdato, pnum):
            ret.append({'kullkode': "%s-%s-%s" % (row['studieprogramkode'], row['terminkode_kull'], row['arstall_kull']),
                'status_aktiv': row['status_aktiv']})

        db.close()
        return ret

    #
    # person clear_address
    #
    all_commands['person_clear_address'] = cmd_param.Command(
        ("person", "clear_address"),
        cmd_param.PersonId(),
        cmd_param.SourceSystem(help_ref="source_system"),
        cmd_param.AddressType(),
        perm_filter='is_superuser')

    def person_clear_address(self, operator, person_id, source_system,
                             addresstype):
        """Deleting a person's address from a given source system. Useful in
        cases where the person has an old address from a source system he no
        longer is exported from, i.e. no affiliations."""
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        person = self.util.get_target(person_id, restrict_to="Person")
        ss = self.const.AuthoritativeSystem(source_system)
        try:
            int(ss)
        except Errors.NotFoundError:
            raise CerebrumError("No such source system")

        addresstype = self.const.Address(addresstype)
        try:
            int(addresstype)
        except Errors.NotFoundError:
            raise CerebrumError("No such address type")

        # check if address exists
        if not person.get_entity_address(source=ss, type=addresstype):
            raise CerebrumError("Person has no such address")
        try:
            person.delete_entity_address(source_type=ss, a_type=addresstype)
            self.db.log_change(person.entity_id,
                               self.const.entity_addr_del,
                               None,
                               change_params={'subject': person.entity_id})
            person.write_db()
        except:
            raise CerebrumError("Could not delete address %s:%s for %s" %
                                (source_system, addresstype, person_id))
        return "Address deleted"

    #
    # user home_create (set extra home per spread for a given account)
    #
    all_commands['user_home_create'] = cmd_param.Command(
        ("user", "home_create"),
        cmd_param.AccountName(),
        cmd_param.Spread(),
        cmd_param.DiskId(),
        perm_filter='can_create_user')

    def user_home_create(self, operator, accountname, spread, disk):
        account = self._get_account(accountname)
        disk_id, home = self._get_disk(disk)[1:3]
        homedir_id = None
        home_spread = False
        for s in cereconf.HOME_SPREADS:
            if spread == str(getattr(self.const, s)):
                home_spread = True
                break
        if home is not None:
            if home[0] == ':':
                home = home[1:]
            else:
                raise CerebrumError("Invalid disk")
        self.ba.can_create_user(operator.get_entity_id(), account)
        is_posix = False
        try:
            self._get_account(accountname, actype="PosixUser")
            is_posix = True
        except CerebrumError:
            pass
        if not is_posix:
            raise CerebrumError("This user is not a posix user. Please use 'user promote_posix' first.")
        if not home_spread:
            raise CerebrumError("Cannot assign home in a non-home spread!")
        if account.has_spread(int(self._get_constant(self.const.Spread, spread))):
            try:
                if account.get_home(int(self._get_constant(self.const.Spread, spread))):
                    return "User already has a home in spread %s, use user move" % spread
            except:
                homedir_id = account.set_homedir(disk_id=disk_id, home=home,
                                                 status=self.const.home_status_not_created)

        else:
            account.add_spread(self._get_constant(self.const.Spread, spread))
            homedir_id = account.set_homedir(disk_id=disk_id, home=home,
                                             status=self.const.home_status_not_created)
        account.set_home(int(self._get_constant(self.const.Spread, spread)), homedir_id)
        account.write_db()
        return "Home made for %s in spread %s" % (accountname, spread)

    #
    # user info
    #
    all_commands['user_info'] = cmd_param.Command(
        ("user", "info"),
        cmd_param.AccountName(),
        fs=cmd_param.FormatSuggestion([
            ("Username:      %s\n"
             "Spreads:       %s\n"
             "Affiliations:  %s\n"
             "Expire:        %s\n"
             "Home:          %s\n"
             "Entity id:     %i\n"
             "Owner id:      %i (%s: %s)",
             ("username", "spread", "affiliations",
              format_day("expire"),
              "home", "entity_id", "owner_id",
              "owner_type", "owner_desc")),
            ("Contact:       %s: %s [from %s]",
             ("contact_type", "contact_value", "contact_src")),
            ("UID:           %i\n" +
             "Default fg:    %i=%s\n" +
             "Gecos:         %s\n" +
             "Shell:         %s",
             ('uid', 'dfg_posix_gid', 'dfg_name', 'gecos',
              'shell')),
            ("Quarantined:   %s",
             ("quarantined",)),
            ("Note:          (#%d) %s: %s",
             ('note_id', 'note_subject', 'note_description'))
        ]))

    def user_info(self, operator, accountname):
        is_posix = False
        try:
            account = self._get_account(accountname, actype="PosixUser")
            is_posix = True
        except CerebrumError:
            account = self._get_account(accountname)
        if account.is_deleted() and not self.ba.is_superuser(operator.get_entity_id()):
            raise CerebrumError("User is deleted")
        affiliations = []
        for row in account.get_account_types(filter_expired=False):
            ou = self._get_ou(ou_id=row['ou_id'])
            affiliations.append("%s@%s" %
                                (self.const.PersonAffiliation(row['affiliation']),
                                 self._format_ou_name(ou)))
        tmp = {'disk_id': None, 'home': None, 'status': None,
               'homedir_id': None}
        hm = []
        # fixme: UiA does not user home_status as per today. this should
        # probably be fixed
        # home_status = None
        home = None
        for spread in cereconf.HOME_SPREADS:
            try:
                tmp = account.get_home(getattr(self.const, spread))
                if tmp['disk_id'] or tmp['home']:
                    tmp_home = account.resolve_homedir(disk_id=tmp['disk_id'],
                                                       home=tmp['home'])
                # home_status = str(self.const.AccountHomeStatus(tmp['status']))
                hm.append("%s (%s)" % (tmp_home, str(getattr(self.const, spread))))
            except Errors.NotFoundError:
                pass
        home = ("\n" + (" " * 15)).join([x for x in hm])
        ret = [{'entity_id': account.entity_id,
                'username': account.account_name,
                'spread': ",".join([str(self.const.Spread(a['spread']))
                                    for a in account.get_spread()]),
                'affiliations': (",\n" + (" " * 15)).join(affiliations),
                'expire': account.expire_date,
                'home': home,
                'owner_id': account.owner_id,
                'owner_type': str(self.const.EntityType(account.owner_type))
                }]
        if account.owner_type == self.const.entity_person:
            person = self._get_person('entity_id', account.owner_id)
            try:
                p_name = person.get_name(self.const.system_cached,
                                         getattr(self.const,
                                                 cereconf.DEFAULT_GECOS_NAME))
            except Errors.NotFoundError:
                p_name = '<none>'
            ret[0]['owner_desc'] = p_name
        else:
            grp = self._get_group(account.owner_id, idtype='id')
            ret[0]['owner_desc'] = grp.group_name

        if is_posix:
            group = self._get_group(account.gid_id, idtype='id', grtype='PosixGroup')
            ret.append({
                'uid': account.posix_uid,
                'dfg_posix_gid': group.posix_gid,
                'dfg_name': group.group_name,
                'gecos': account.gecos,
                'shell': str(self.const.PosixShell(account.shell))})

        # Contact info
        for row in account.get_contact_info():
                                    #type=self.const.contact_mobile_phone):
            ret.append({'contact_type': str(self.const.ContactInfo(
                                                        row['contact_type'])),
                        'contact_value': row['contact_value'],
                        'contact_src': str(self.const.AuthoritativeSystem(
                                                        row['source_system']))})

        # TODO: Return more info about account
        quarantined = None
        now = DateTime.now()
        for q in account.get_entity_quarantine():
            if q['start_date'] <= now:
                if (q['end_date'] is not None
                        and q['end_date'] < now):
                    quarantined = 'expired'
                elif (q['disable_until'] is not None
                        and q['disable_until'] > now):
                    quarantined = 'disabled'
                else:
                    quarantined = 'active'
                    break
            else:
                quarantined = 'pending'
        if quarantined:
            ret.append({'quarantined': quarantined})

        # Append entity notes
        self._append_entity_notes(ret, operator, account.entity_id)

        return ret

    #
    # user promote_posix
    #
    all_commands['user_promote_posix'] = cmd_param.Command(
        ('user', 'promote_posix'),
        cmd_param.AccountName(),
        cmd_param.GroupName(),
        cmd_param.PosixShell(default="bash"),
        cmd_param.DiskId(),
        perm_filter='can_create_user')

    def user_promote_posix(self, operator, accountname, dfg=None, shell=None,
                           home=None):
        is_posix = False
        try:
            self._get_account(accountname, actype="PosixUser")
            is_posix = True
        except CerebrumError:
            pass
        if is_posix:
            raise CerebrumError("%s is already a PosixUser" % accountname)
        account = self._get_account(accountname)
        pu = Utils.Factory.get('PosixUser')(self.db)
        old_uid = self._lookup_old_uid(account.entity_id)
        if old_uid is None:
            uid = pu.get_free_uid()
        else:
            uid = old_uid
        group = self._get_group(dfg, grtype='PosixGroup')
        shell = self._get_shell(shell)
        if not home:
            raise CerebrumError("home cannot be empty")
        elif home[0] != ':':  # Hardcoded path
            disk_id, home = self._get_disk(home)[1:3]
        else:
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise PermissionDenied("only superusers may use hardcoded path")
            disk_id, home = None, home[1:]
        if account.owner_type == self.const.entity_person:
            person = self._get_person("entity_id", account.owner_id)
        else:
            person = None
        self.ba.can_create_user(operator.get_entity_id(), person, disk_id)
        pu.populate(uid, group.entity_id, None, shell, parent=account,
                    creator_id=operator.get_entity_id())
        pu.write_db()

        default_home_spread = self._get_constant(self.const.Spread,
                                                 cereconf.DEFAULT_HOME_SPREAD,
                                                 "spread")
        if not pu.has_spread(default_home_spread):
            pu.add_spread(default_home_spread)

        homedir_id = pu.set_homedir(
            disk_id=disk_id, home=home,
            status=self.const.home_status_not_created)
        pu.set_home(default_home_spread, homedir_id)
        if old_uid is None:
            tmp = ', new uid=%i' % uid
        else:
            tmp = ', reused old uid=%i' % old_uid
        return "OK, promoted %s to posix user%s" % (accountname, tmp)

    #
    # user delete <username>
    #
    all_commands['user_delete'] = cmd_param.Command(
        ("user", "delete"),
        cmd_param.AccountName(),
        perm_filter='can_delete_user')

    def user_delete(self, operator, accountname):
        # TODO: How do we delete accounts?
        account = self._get_account(accountname)
        self.ba.can_delete_user(operator.get_entity_id(), account)
        if account.is_deleted():
            raise CerebrumError("User is already deleted")
        blockers = account.get_delete_blockers(ignore_group_memberships=True)
        if blockers:
            return('There are still references to account that has to be '
                   'cleaned up:\n * ' + '\n * '.join(blockers))
        br = BofhdRequests(self.db, self.const)
        br.add_request(operator.get_entity_id(), br.now,
                       self.const.bofh_delete_user,
                       account.entity_id, None,
                       state_data=None)
        return "User %s queued for deletion at 17:15" % account.account_name

    # user_create_prompt_fun_helper
    #
    def _user_create_prompt_func_helper(self, ac_type, session, *args):
        """A prompt_func on the command level should return
        {'prompt': message_string, 'map': dict_mapping}
        - prompt is simply shown.
        - map (optional) maps the user-entered value to a value that
          is returned to the server, typically when user selects from
          a list."""
        all_args = list(args[:])

        if not all_args:
            return {'prompt': "Person identification",
                    'help_ref': "user_create_person_id"}
        arg = all_args.pop(0)
        if arg.startswith("group:"):
            group_owner = True
        else:
            group_owner = False
        if not all_args or group_owner:
            if group_owner:
                group = self._get_group(arg.split(":")[1])
                if all_args:
                    all_args.insert(0, group.entity_id)
                else:
                    all_args = [group.entity_id]
            else:
                c = self._find_persons(arg)
                map = [(("%-8s %s", "Id", "Name"), None)]
                for i in range(len(c)):
                    person = self._get_person("entity_id", c[i]['person_id'])
                    map.append((
                        ("%8i %s", int(c[i]['person_id']),
                         person.get_name(self.const.system_cached, self.const.name_full)),
                        int(c[i]['person_id'])))
                if not len(map) > 1:
                    raise CerebrumError, "No persons matched"
                return {'prompt': "Choose person from list",
                        'map': map,
                        'help_ref': 'user_create_select_person'}
        owner_id = all_args.pop(0)
        if not group_owner:
            person = self._get_person("entity_id", owner_id)
            existing_accounts = []
            account = self.Account_class(self.db)
            for r in account.list_accounts_by_owner_id(person.entity_id):
                account = self._get_account(r['account_id'], idtype='id')
                if account.expire_date:
                    exp = account.expire_date.strftime('%Y-%m-%d')
                else:
                    exp = '<not set>'
                existing_accounts.append("%-10s %s" % (account.account_name,
                                                       exp))
            if existing_accounts:
                existing_accounts = "Existing accounts:\n%-10s %s\n%s\n" % (
                    "uname", "expire", "\n".join(existing_accounts))
            else:
                existing_accounts = ''
            if existing_accounts:
                if not all_args:
                    return {'prompt': "%sContinue? (y/n)" % existing_accounts}
                yes_no = all_args.pop(0)
                if not yes_no == 'y':
                    raise CerebrumError, "Command aborted at user request"
            if not all_args:
                map = [(("%-8s %s", "Num", "Affiliation"), None)]
                for aff in person.get_affiliations():
                    ou = self._get_ou(ou_id=aff['ou_id'])
                    name = "%s@%s" % (
                        self.const.PersonAffStatus(aff['status']),
                        self._format_ou_name(ou))
                    map.append((("%s", name),
                                {'ou_id': int(aff['ou_id']), 'aff': int(aff['affiliation'])}))
                if not len(map) > 1:
                    raise CerebrumError(
                        "Person has no affiliations. Try person affiliation_add")
                return {'prompt': "Choose affiliation from list", 'map': map}
            affiliation = all_args.pop(0)
        else:
            if not all_args:
                return {'prompt': "Enter np_type",
                        'help_ref': 'string_np_type'}
            np_type = all_args.pop(0)
        if ac_type == 'PosixUser':
            if not all_args:
                return {'prompt': "Shell", 'default': 'bash'}
            shell = all_args.pop(0)
            if not all_args:
                return {'prompt': 'E-mail spread',
                        'help_ref': 'string_spread',
                        'default': 'acc@office365'}
            email_spread = all_args.pop(0)
        if not all_args:
            ret = {'prompt': "Username", 'last_arg': True}
            posix_user = Factory.get('PosixUser')(self.db)
            if not group_owner:
                try:
                    person = self._get_person("entity_id", owner_id)
                    fname, lname = [
                        person.get_name(self.const.system_cached, v)
                        for v in (self.const.name_first, self.const.name_last) ]
                    sugg = posix_user.suggest_unames(self.const.account_namespace, fname, lname)
                    if sugg:
                        ret['default'] = sugg[0]
                except ValueError:
                    pass    # Failed to generate a default username
            return ret
        if len(all_args) == 1:
            return {'last_arg': True}
        raise CerebrumError, "Too many arguments"

    # user_create_prompt_func
    #
    def user_create_prompt_func(self, session, *args):
        return self._user_create_prompt_func_helper('PosixUser', session, *args)

    # user_create_basic_prompt_func
    #
    def user_create_basic_prompt_func(self, session, *args):
        return self._user_create_prompt_func_helper('Account', session, *args)

    #
    # user create
    #
    all_commands['user_create'] = cmd_param.Command(
        ('user', 'create'),
        prompt_func=user_create_prompt_func,
        fs=cmd_param.FormatSuggestion("Created uid=%i", ("uid",)),
        perm_filter='can_create_user')

    def user_create(self, operator, *args):
        if args[0].startswith('group:'):
            group_id, np_type, shell, email_spread, uname = args
            owner_type = self.const.entity_group
            owner_id = self._get_group(group_id.split(":")[1]).entity_id
            np_type = self._get_constant(self.const.Account, np_type,
                                         "account type")
        else:
            if len(args) == 6:
                idtype, person_id, affiliation, shell, email_spread, uname = args
            else:
                idtype, person_id, yes_no, affiliation, shell, email_spread, uname = args
            owner_type = self.const.entity_person
            owner_id = self._get_person("entity_id", person_id).entity_id
            np_type = None

        # Only superusers should be allowed to create users with
        # capital letters in their ids, and even then, just for system
        # users
        if uname != uname.lower():
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise CerebrumError(
                    "Account names cannot contain capital letters")
            else:
                if owner_type != self.const.entity_group:
                    raise CerebrumError(
                        "Personal account names cannot contain capital letters")

        filegroup = 'ansatt'
        group = self._get_group(filegroup, grtype="PosixGroup")
        posix_user = Factory.get('PosixUser')(self.db)
        uid = posix_user.get_free_uid()
        shell = self._get_shell(shell)
        path = '/hia/ravn/u4'
        disk_id, home = self._get_disk(path)[1:3]
        posix_user.clear()
        gecos = None
        expire_date = None
        self.ba.can_create_user(operator.get_entity_id(), owner_id, disk_id)

        posix_user.populate(uid, group.entity_id, gecos, shell, name=uname,
                            owner_type=owner_type, owner_id=owner_id,
                            np_type=np_type, creator_id=operator.get_entity_id(),
                            expire_date=expire_date)
        try:
            posix_user.write_db()
            for spread in cereconf.BOFHD_NEW_USER_SPREADS:
                posix_user.add_spread(self.const.Spread(spread))
            homedir_id = posix_user.set_homedir(
                disk_id=disk_id, home=home,
                status=self.const.home_status_not_created)
            posix_user.set_home(self.const.spread_nis_user, homedir_id)
            # For correct ordering of ChangeLog events, new users
            # should be signalled as "exported to" a certain system
            # before the new user's password is set.  Such systems are
            # flawed, and should be fixed.
            passwd = posix_user.make_passwd(uname)
            posix_user.set_password(passwd)
            if email_spread:
                if not int(self.const.Spread(email_spread)) in [
                        int(self.const.spread_exchange_account),
                        int(self.const.spread_exchange_acc_old),
                        int(self.const.spread_uia_office_365),
                        int(self.const.spread_uia_forward),
                        int(self.const.spread_hia_email)]:
                    raise CerebrumError(
                        "Not an e-mail spread: {!r}!".format(email_spread))
            try:
                posix_user.add_spread(self.const.Spread(email_spread))
            except Errors.NotFoundError:
                raise CerebrumError("No such spread {!r}".format(email_spread))
            # And, to write the new password to the database, we have
            # to .write_db() one more time...
            posix_user.write_db()
            if posix_user.owner_type == self.const.entity_person:
                ou_id, affiliation = affiliation['ou_id'], affiliation['aff']
                self._user_create_set_account_type(posix_user, owner_id,
                                                   ou_id, affiliation)
        except self.db.DatabaseError, m:
            raise CerebrumError("Database error: {!s}".format(m))
        operator.store_state(
            "new_account_passwd", {'account_id': int(posix_user.entity_id),
                                   'password': passwd})
        self._add_radiusans_spread(int(posix_user.entity_id), operator)

        return "Ok, create %s" % {'uid': uid}

    # helper func, set radius-ans spread for employees
    def _add_radiusans_spread(self, acc_id, operator):
        acc = Utils.Factory.get('Account')(self.db)
        acc.clear()
        acc.find(acc_id)
        if (acc.is_employee() or acc.is_affiliate()
                or self._person_is_employee_or_affiliate(acc.owner_id,
                                                         operator)):
            if not acc.has_spread(self.const.spread_ans_radius_user):
                acc.add_spread(self.const.spread_ans_radius_user)
                acc.write_db()

    # helper func, check if a person is a registered employee or affiliate
    def _person_is_employee_or_affiliate(self, person_id, operator):
        person = Utils.Factory.get('Person')(self.db)
        person.clear()
        try:
            person.find(person_id)
        except Errors.NotFoundError:
            # non-personal accounts cannot be assigned radiusans spread
            return False
        for row in person.get_affiliations():
            if int(row['affiliation']) in (
                    int(self.const.affiliation_ansatt),
                    int(self.const.affiliation_tilknyttet)):
                return True
        return False

    #
    # user move
    #
    all_commands['user_move_nofile'] = cmd_param.Command(
        ("user", "move_nofile"),
        cmd_param.AccountName(help_ref="account_name", repeat=False),
        cmd_param.Spread(),
        cmd_param.DiskId(),
        perm_filter='is_superuser')

    def user_move_nofile(self, operator, accountname, spread, path):
        account = self._get_account(accountname)
        move_ok = False
        if account.is_expired():
            raise CerebrumError(
                "Account {!r} has expired".format(account.account_name))
        spread = int(self._get_constant(self.const.Spread, spread))
        tmp_s = []
        for r in account.get_spread():
            tmp_s.append(int(r['spread']))
        if spread in tmp_s:
            move_ok = True
        if not move_ok:
            raise CerebrumError(
                "You can not move a user that does not have"
                " homedir in the given spread. Use home_create.")
        disk_id = self._get_disk(path)[1]
        if disk_id is None:
            raise CerebrumError("Bad destination disk")
        ah = account.get_home(spread)
        account.set_homedir(current_id=ah['homedir_id'],
                            disk_id=disk_id)
        account.set_home(spread, ah['homedir_id'])
        account.write_db()
        return "Ok, user %s moved." % accountname

    #
    # user migrate_exchange
    #
    all_commands['user_migrate_exchange'] = cmd_param.Command(
        ("user", "migrate_exchange"),
        cmd_param.AccountName(help_ref="account_name", repeat=True),
        cmd_param.SimpleString(help_ref='string_mdb'),
        perm_filter='is_superuser')

    def user_migrate_exchange(self, operator, uname, mdb):
        account = self._get_account(uname)
        if account.is_expired():
            raise CerebrumError(
                "Account {!s} has expired".format(account.account_name))
        # Check given mdb
        mdb = mdb.strip()
        if mdb not in cereconf.EXCHANGE_HOMEMDB_VALID:
            raise CerebrumError("Unvalid mdb")
        # Set new mdb value
        account.populate_trait(self.const.trait_exchange_mdb, strval=mdb)
        # Mark that account is being migrated
        account.populate_trait(self.const.trait_exchange_under_migration)
        account.write_db()
        return "OK, mdb stored for user %s" % uname

    #
    # user migrate_exchange_finished
    #
    all_commands['user_migrate_exchange_finished'] = cmd_param.Command(
        ("user", "migrate_exchange_finished"),
        cmd_param.AccountName(help_ref="account_name", repeat=True),
        perm_filter='is_superuser')

    def user_migrate_exchange_finished(self, operator, uname):
        account = self._get_account(uname)
        if account.is_expired():
            raise CerebrumError(
                "Account {!r} has expired".format(account.account_name))
        # Account migration is finished
        account.delete_trait(self.const.trait_exchange_under_migration)
        # Mark that account now is migrated to new exchange server
        account.populate_trait(self.const.trait_exchange_migrated)
        account.write_db()
        return "OK, deleted trait for user %s" % uname

    #
    # group multi_remove
    #
    all_commands['group_multi_remove'] = cmd_param.Command(
        ("group", "multi_remove"),
        cmd_param.MemberType(help_ref='member_type', default='account'),
        cmd_param.MemberName(help_ref="member_name_src", repeat=True),
        cmd_param.GroupName(help_ref="group_name_dest", repeat=True),
        perm_filter='can_alter_group')

    def group_multi_remove(self, operator, member_type, src_name, dest_group):
        """ Remove a person, account or group from a given group. """
        if member_type not in ('group', 'account', 'person'):
            return 'Unknown member_type "%s"' % (member_type)
        return self._group_remove(operator, src_name, dest_group,
                                  member_type=member_type)

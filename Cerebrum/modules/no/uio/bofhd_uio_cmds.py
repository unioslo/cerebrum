# -*- coding: utf-8 -*-
#
# Copyright 2002-2024 University of Oslo, Norway
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

import collections
import datetime
import errno
import imaplib
import re
import select

import six
from six import string_types, text_type

import cereconf
from Cerebrum import Entity
from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum import database
from Cerebrum.group.GroupRoles import GroupRoles
from Cerebrum.Constants import _LanguageCode, _GroupTypeCode
from Cerebrum.modules import Email
from Cerebrum.modules.AccountPolicy import AccountPolicy
from Cerebrum.modules.apikeys import bofhd_apikey_cmds
from Cerebrum.modules.audit import bofhd_history_cmds
from Cerebrum.modules.bofhd import bofhd_core_help
from Cerebrum.modules.bofhd import bofhd_external_id
from Cerebrum.modules.bofhd import bofhd_group_roles
from Cerebrum.modules.bofhd import bofhd_misc_sms
from Cerebrum.modules.bofhd import bofhd_ou_cmds
from Cerebrum.modules.bofhd import bofhd_perm_cmds
from Cerebrum.modules.bofhd import bofhd_quarantines
from Cerebrum.modules.bofhd import parsers
from Cerebrum.modules.bofhd.auth import (BofhdAuthOpTarget,
                                         BofhdAuthRole)
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.bofhd_user_create import BofhdUserCreateMethod
from Cerebrum.modules.bofhd.bofhd_utils import (
    copy_func,
    date_to_string,
    default_format_day,
    exc_to_text,
    get_quarantine_status,
)
from Cerebrum.modules.bofhd.cmd_param import (
    AccountName,
    AccountPassword,
    Affiliation,
    AffiliationStatus,
    Command,
    Date,
    DiskId,
    EmailAddress,
    EntityType,
    ExternalIdType,
    FormatSuggestion,
    GroupName,
    GroupVisibility,
    Id,
    Integer,
    MemberName,
    MemberType,
    MoveType,
    OU,
    PersonId,
    PersonName,
    PersonSearchType,
    PosixGecos,
    PosixShell,
    SimpleString,
    SourceSystem,
    Spread,
    UserSearchType,
    YesNo,
)
from Cerebrum.modules.bofhd import bofhd_email
from Cerebrum.modules.bofhd.bofhd_contact_info import BofhdContactCommands
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd_requests import bofhd_requests_cmds
from Cerebrum.modules.bofhd_requests.request import BofhdRequests
from Cerebrum.modules.bofhd.help import Help, merge_help_strings
from Cerebrum.modules.bofhd import bofhd_access
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.disk_quota import DiskQuota
from Cerebrum.modules.no.uio.access_FS import FS
from Cerebrum.modules.no.uio import bofhd_pw_issues
from Cerebrum.modules.bofhd import bofhd_user_create_unpersonal
from Cerebrum.modules.no.uio import bofhd_auth
from Cerebrum.modules.no.uio import sysadm_utils
from Cerebrum.modules.otp import bofhd_otp_cmds
from Cerebrum.modules.ou_disk_mapping import bofhd_cmds
from Cerebrum.modules.pwcheck.checker import (
    check_password,
    PasswordNotGoodEnough,
    PhrasePasswordNotGoodEnough,
    RigidPasswordNotGoodEnough,
)
from Cerebrum.modules.pwcheck.history import (
    PasswordHistory,
    check_password_history,
)
from Cerebrum.modules.trait import bofhd_trait_cmds
from Cerebrum.utils import date_compat
from Cerebrum.utils.email import mail_template, sendmail
from Cerebrum.utils import json


format_day = default_format_day  # 10 characters wide


class TimeoutException(Exception):
    pass


class ConnectException(Exception):
    pass


@copy_func(
    BofhdUserCreateMethod,
    methods=[
        '_user_create_basic',
        '_user_create_set_account_type',
        '_user_password',
    ]
)
class BofhdExtension(BofhdCommonMethods):

    all_commands = {}
    hidden_commands = {}
    omit_parent_commands = {'user_create'}
    parent_commands = True

    authz = bofhd_auth.UioAuth
    external_id_mappings = {}

    def __init__(self, *args, **kwargs):
        super(BofhdExtension, self).__init__(*args, **kwargs)
        self.external_id_mappings['fnr'] = self.const.externalid_fodselsnr
        self.external_id_mappings['passnr'] = self.const.externalid_pass_number
        # exchange-relatert-jazz
        # currently valid language variants for UiO-Cerebrum
        # although these codes are used for distribution groups
        # they are not directly related to them. maybe these should be
        # put in a cereconf-variable somewhere in the future? (Jazz, 2013-12)
        self.language_codes = ['nb', 'nn', 'en']

        # TODO: Wait until needed / fix on import?
        # TODO: Is this still needed?
        self.fixup_imaplib()

    @property
    def name_codes(self):
        # TODO: Do we really need this cache?
        try:
            return self.__name_codes
        except AttributeError:
            self.__name_codes = dict()
            person = Utils.Factory.get('Person')(self.db)
            for t in person.list_person_name_codes():
                self.__name_codes[int(t['code'])] = t['description']
            return self.__name_codes

    @property
    def change_type2details(self):
        # TODO: Do we really need this cache?
        try:
            return self.__ct2details
        except AttributeError:
            self.__ct2details = dict()
            for r in self.db.get_changetypes():
                self.__ct2details[int(r['change_type_id'])] = [
                    r['category'], r['type'], r['msg_string']]
            return self.__ct2details

    def fixup_imaplib(self):
        def nonblocking_open(self, host=None, port=None):
            import socket
            # Perhaps using **kwargs is cleaner, but this works, too.
            if host is None:
                if not hasattr(self, "host"):
                    self.host = ''
            else:
                self.host = host
            if port is None:
                if not hasattr(self, "port"):
                    self.port = 143
            else:
                self.port = port

            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setblocking(False)
            err = self.sock.connect_ex((self.host, self.port))
            # I don't think connect_ex() can ever return success immediately,
            # it has to wait for a roundtrip.
            assert err
            if err != errno.EINPROGRESS:
                raise ConnectException(errno.errorcode[err])

            ignore, wset, ignore = select.select([], [self.sock], [], 1.0)
            if not wset:
                raise TimeoutException
            err = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if err == 0:
                self.sock.setblocking(True)
                self.file = self.sock.makefile('rb')
                return
            raise ConnectException(errno.errorcode[err])
        setattr(imaplib.IMAP4, 'open', nonblocking_open)

    @classmethod
    def get_help_strings(cls):
        return bofhd_core_help.get_help_strings()

    def _email_create_forward_target(self, localaddr, remoteaddr):
        """Helper method for creating a forward target.

        No auth is checked here.
        """
        # TODO: Does this belong in EmailCommands?
        lp, dom = bofhd_email.split_address(localaddr)
        ea = Email.EmailAddress(self.db)
        ed = Email.EmailDomain(self.db)

        if not ea.validate_localpart(lp):
            raise CerebrumError("Invalid localpart %r" % lp)

        try:
            ed.find_by_domain(dom)
        except Errors.NotFoundError:
            raise CerebrumError("Unknown e-mail domain %r" % dom)

        try:
            ea.find_by_local_part_and_domain(lp, ed.entity_id)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError("Address %r already exists" % localaddr)
        et = Email.EmailTarget(self.db)
        et.populate(self.const.email_target_forward)
        et.write_db()
        ea.clear()
        ea.populate(lp, ed.entity_id, et.entity_id)
        ea.write_db()
        epat = Email.EmailPrimaryAddressTarget(self.db)
        epat.populate(ea.entity_id, parent=et)
        epat.write_db()
        ef = Email.EmailForward(self.db)
        ef.find(et.entity_id)
        addr = bofhd_email.check_email_address(remoteaddr)
        try:
            ef.add_forward(addr)
        except Errors.TooManyRowsError:
            raise CerebrumError("Forward address added already (%s)" % addr)

        # Default spam and filter settings
        spam = getattr(cereconf, 'EMAIL_DEFAULT_SPAM_SETTINGS',
                       {}).get(text_type(self.const.email_target_forward))
        filter_ = getattr(cereconf, 'EMAIL_DEFAULT_FILTER',
                          {}).get(text_type(self.const.email_target_forward))

        if spam:
            spam_level, spam_action = (
                int(self.const.EmailSpamLevel(spam[0])),
                int(self.const.EmailSpamAction(spam[1])))
            esf = Email.EmailSpamFilter(self.db)
            esf.populate(spam_level, spam_action, parent=et)
            esf.write_db()

        if filter_:
            filter_code = int(self.const.EmailTargetFilter(filter_))
            etf = Email.EmailTargetFilter(self.db)
            etf.populate(filter_code, parent=et)
            etf.write_db()

        return ef

    #
    # entity info
    #
    # Not callable from cli clients
    #
    all_commands['entity_info'] = None

    def entity_info(self, operator, entity_id):
        """Returns basic information on the given entity id"""
        entity = self._get_entity(ident=entity_id)
        return self._entity_info(entity)

    def _entity_info(self, entity):
        co = self.const
        result = {
            'type': text_type(co.EntityType(entity.entity_type)),
            'entity_id': entity.entity_id,
        }
        if entity.entity_type in (co.entity_group, co.entity_account):
            result['creator_id'] = entity.creator_id
            result['create_date'] = entity.created_at
            result['expire_date'] = entity.expire_date
            # FIXME: Should be a list instead of a string, but text
            # clients doesn't know how to view such a list
            result['spread'] = ", ".join([text_type(co.Spread(r['spread']))
                                          for r in entity.get_spread()])
        if entity.entity_type == co.entity_group:
            result['name'] = entity.group_name
            result['group_type'] = text_type(co.GroupType(entity.group_type))
            result['description'] = entity.description
            result['visibility'] = entity.visibility
            try:
                result['gid'] = entity.posix_gid
            except AttributeError:
                pass
        elif entity.entity_type == co.entity_account:
            result['name'] = entity.account_name
            result['owner_id'] = entity.owner_id
        elif entity.entity_type == co.entity_person:
            result['name'] = entity.get_name(
                co.system_cached,
                getattr(co, cereconf.DEFAULT_GECOS_NAME))
            result['export_id'] = entity.export_id
            result['birthdate'] = entity.birth_date
            result['description'] = entity.description
            result['gender'] = text_type(co.Gender(entity.gender))
            # make boolean
            result['deceased'] = entity.deceased_date
            names = []
            for name in entity.get_names():
                source_system = text_type(
                    co.AuthoritativeSystem(name.source_system))
                name_variant = text_type(co.PersonName(name.name_variant))
                names.append((source_system, name_variant, name.name))
            result['names'] = names
            affiliations = []
            for row in entity.get_affiliations():
                affiliations.append({
                    'ou': row['ou_id'],
                    'affiliation': text_type(
                        co.PersonAffiliation(row['affiliation'])),
                    'status': text_type(co.PersonAffStatus(row['status'])),
                    'source_system': text_type(
                        co.AuthoritativeSystem(row['source_system'])),
                })
            result['affiliations'] = affiliations
        elif entity.entity_type == co.entity_ou:
            for attr in ('name', 'acronym', 'short_name', 'display_name',
                         'sort_name'):
                result[attr] = getattr(entity, attr)
        return result

    def _viewable_external_ids(self, operator, entity):
        """Get external ids of entity that operator has permission to view"""
        data = []
        try:
            for row in entity.get_external_id():
                try:
                    extid_type = str(self.const.EntityExternalId(row[0]))
                    self.ba.can_get_external_id(
                        operator, entity,
                        extid_type=extid_type,
                        source_sys=row['source_system'])
                except PermissionDenied:
                    pass
                else:
                    data.append(dict(row))
        except PermissionDenied:
            pass
        return data

    #
    # entity accounts ...
    #
    all_commands['entity_accounts'] = Command(
        ("entity", "accounts"),
        EntityType(default="person"),
        Id(),
        fs=FormatSuggestion(
            "%7i %-10s %s", ("account_id", "name", format_day("expire")),
            hdr="%7s %-10s %s" % ("Id", "Name", "Expire")
        ))

    def entity_accounts(self, operator, entity_type, id):
        entity = self._get_entity(entity_type, id)
        account = self.Account_class(self.db)
        ret = []
        for r in account.list_accounts_by_owner_id(entity.entity_id,
                                                   entity.entity_type,
                                                   filter_expired=False):
            account = self._get_account(r['account_id'], idtype='id')

            ret.append({'account_id': r['account_id'],
                        'name': account.account_name,
                        'expire': account.expire_date})
        return ret

    #
    # entity history
    #
    all_commands['entity_history'] = Command(
        ("entity", "history"),
        Id(help_ref="id:target:account"),
        YesNo(help_ref='yes_no_all_op', optional=True, default="yes"),
        Integer(optional=True, help_ref="limit_number_of_results"),
        fs=FormatSuggestion(
            "%s [%s]: %s", ("timestamp", "change_by", "message")),
        perm_filter='can_show_history')

    def entity_history(self, operator, entity, any_entity="yes",
                       limit_number_of_results=0):
        ent = self.util.get_target(entity, restrict_to=[])
        self.ba.can_show_history(operator.get_entity_id(), ent)
        ret = []

        try:
            num = int(limit_number_of_results)
        except ValueError:
            raise CerebrumError('Illegal range limit, must be an integer: '
                                '{}'.format(limit_number_of_results))

        if self._get_boolean(any_entity):
            kw = {'any_entity': ent.entity_id}
        else:
            kw = {'subject_entity': ent.entity_id}
        rows = list(self.db.get_log_events(0, **kw))

        for r in rows[-num:]:
            ret.append(self._format_changelog_entry(r))
        return ret

    # FIXME - group_multi_add should later be renamed to group_add, when
    # there's enough time. group_padd and group_gadd should be removed as soon
    # as the other institutions doesn't depend on them any more.

    #
    # group multi_add
    #
    # jokim 2008-12-02 TBD: won't let it be used by jbofh, only wofh for now
    #
    hidden_commands['group_multi_add'] = Command(
        ('group', 'multi_add'),
        MemberType(help_ref='member_type', default='account'),
        MemberName(help_ref='member_name_src', repeat=True),
        GroupName(help_ref='group_name_dest', repeat=True),
        perm_filter='can_alter_group')

    def group_multi_add(self, operator, member_type, src_name, dest_group):
        """Adds a person, account or group to a given group."""
        if member_type not in ('group', 'account', 'person', ):
            raise CerebrumError("Unknown member_type: %r" % member_type)

        return self._group_add(operator, src_name, dest_group,
                               member_type=member_type)

    #
    # group add
    #
    all_commands['group_add'] = Command(
        ("group", "add"),
        AccountName(help_ref="account_name_src", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        perm_filter='can_alter_group')

    def group_add(self, operator, src_name, dest_group):
        return self._group_add(operator, src_name, dest_group,
                               member_type="account")

    #
    # group padd - add person to group
    #
    all_commands['group_padd'] = Command(
        ("group", "padd"),
        PersonId(help_ref="id:target:person", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        perm_filter='can_alter_group')

    def group_padd(self, operator, src_name, dest_group):
        return self._group_add(operator, src_name, dest_group,
                               member_type="person")

    #
    # group gadd
    #
    all_commands['group_gadd'] = Command(
        ("group", "gadd"),
        GroupName(help_ref="group_name_src", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        perm_filter='can_alter_group')

    def group_gadd(self, operator, src_name, dest_group):
        return self._group_add(operator, src_name, dest_group,
                               member_type="group")

    def _group_add(self, operator, src_name, dest_group, member_type=None):
        """Let src_group(s) join dest_group(s)

        :param operator: operator in bofh session
        :param src_name: str name of source group
        :param dest_group: str name of destination group
        :param member_type: str type of member
        :return:
        """
        if member_type == "group":
            src_entity = self._get_group(src_name)
        elif member_type == "account":
            src_entity = self._get_account(src_name)
        elif member_type == "person":
            try:
                src_entity = self.util.get_target(src_name,
                                                  restrict_to=['Person'])
            except Errors.TooManyRowsError:
                raise CerebrumError("Unexpectedly found more than one person")
        else:
            raise CerebrumError("Unknown member_type: %r" % member_type)
        return self._group_add_entity(operator, src_entity, dest_group)

    def _group_add_entity(self, operator, src_entity, dest_group):
        group_d = self._get_group(dest_group)
        if not operator or not self.ba.is_superuser(operator.get_entity_id()):
            self._raise_PermissionDenied_if_not_manual_group(group_d)
        if operator:
            self.ba.can_alter_group(operator.get_entity_id(), group_d)
        src_name = self._get_name_from_object(src_entity)
        # Make the error message for the most common operator error
        # more friendly.  Don't treat this as an error, useful if the
        # operator has specified more than one entity.
        if group_d.has_member(src_entity.entity_id):
            return "%s is already a member of %s" % (src_name, dest_group)
        # Make sure that the src_entity does not have group_d as a
        # member already, to avoid a recursion well at export
        if src_entity.entity_type == self.const.entity_group:
            for row in src_entity.search_members(
                    member_id=group_d.entity_id,
                    member_type=self.const.entity_group,
                    indirect_members=True,
                    member_filter_expired=False):
                if row['group_id'] == src_entity.entity_id:
                    raise CerebrumError("Recursive memberships are not allowed"
                                        " (%s is member of %s)" %
                                        (dest_group, src_name))
        # This can still fail, e.g., if the entity is a member with a
        # different operation.
        if self._is_perishable_manual_group(group_d):
            group_d.set_default_expire_date()
            group_d.write_db()
        try:
            group_d.add_member(src_entity.entity_id)
        except self.db.DatabaseError as m:
            raise CerebrumError("Database error: %s" % m)
        # Warn the user about NFS filegroup limitations.
        nis_warning = ''
        for spread_name in cereconf.NIS_SPREADS:
            fg_spread = getattr(self.const, spread_name)
            for row in group_d.get_spread():
                if row['spread'] == fg_spread:
                    count = self._group_count_memberships(src_entity.entity_id,
                                                          fg_spread)
                    if count > 16:
                        nis_warning = (
                            'OK, added {source_name} to {group}\n'
                            'WARNING: {source_name} is now a member of '
                            '{amount_groups} NIS groups with spread {spread}.'
                            '\nActual membership lookups in NIS may not work '
                            'as expected if a user is member of more than 16 '
                            'NIS groups.'.format(source_name=src_name,
                                                 amount_groups=count,
                                                 spread=fg_spread,
                                                 group=dest_group))
        if nis_warning:
            return nis_warning
        return u"OK, added '{member}' to '{group}'".format(
            member=src_name,
            group=dest_group)

    def _group_count_memberships(self, entity_id, spread):
        """Count how many groups of a given spread have entity_id as a member,
        either directly or indirectly."""

        gr = Utils.Factory.get("Group")(self.db)
        groups = list(gr.search(member_id=entity_id,
                                indirect_members=True,
                                spread=spread))
        return len(groups)

    #
    # group add_entity
    #
    all_commands['group_add_entity'] = None

    def group_add_entity(self, operator, src_entity_id, dest_group_id):
        """Adds a entity to a group.

        Both the source entity and the group should be entity IDs
        """
        # tell _group_find later on that dest_group is a entity id
        dest_group = 'id:%s' % dest_group_id
        src_entity = self._get_entity(ident=src_entity_id)
        if src_entity.entity_type not in (self.const.entity_account,
                                          self.const.entity_group):
            raise CerebrumError("Entity %s is not a legal type "
                                "to become group member" % src_entity_id)
        return self._group_add_entity(operator, src_entity, dest_group)

    #
    # group exchange_create
    #
    all_commands['group_exchange_create'] = Command(
        ("group", "exchange_create"),
        GroupName(help_ref="group_name_new"),
        YesNo(help_ref='yes_no_from_existing', default='No'),
        SimpleString(help_ref="string_dl_desc"),
        SimpleString(help_ref="group_disp_name", optional=True, default=''),
        fs=FormatSuggestion("Group created, internal id: %i", ("group_id",)),
        perm_filter='is_postmaster')

    def group_exchange_create(self, operator,
                              groupname, from_existing,
                              description, displayname=''):
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to group')
        existing_group = False
        dl_group = Utils.Factory.get("DistributionGroup")(self.db)
        std_values = dl_group.ret_standard_attr_values(room=False)
        # although cerebrum supports different visibility levels
        # all groups are created visibile for all, and that vis
        # type is hardcoded. if the situation should change group
        # vis may be made into a parameter
        group_vis = self.const.group_visibility_all
        # display name language is standard for dist groups
        disp_name_language = dl_group.ret_standard_language()
        disp_name_variant = self.const.dl_group_displ_name
        # managedby = cereconf.DISTGROUP_DEFAULT_ADMIN
        grp = Utils.Factory.get("Group")(self.db)
        try:
            grp.find_by_name(groupname)
            existing_group = True
        except Errors.NotFoundError:
            # nothing to do, inconsistencies are dealt with
            # further down
            pass
        if not displayname:
            displayname = groupname
        if existing_group and not self._get_boolean(from_existing):
            return ('You choose not to create Exchange group from the '
                    'existing group %s' % groupname)
        try:
            if not existing_group:
                # one could imagine making a helper function in the future
                # _make_dl_group_new, as the functionality is required
                # both here and for the roomlist creation (Jazz, 2013-12)
                dl_group.new(
                    creator_id=operator.get_entity_id(),
                    visibility=group_vis,
                    name=groupname,
                    description=description,
                    group_type=self.const.group_type_manual,
                    roomlist=std_values['roomlist'],
                    hidden=std_values['hidden'])
            else:
                dl_group.populate(roomlist=std_values['roomlist'],
                                  hidden=std_values['hidden'],
                                  parent=grp)
            if self._is_perishable_manual_group(dl_group):
                dl_group.set_default_expire_date()
            dl_group.write_db()
        except self.db.DatabaseError as m:
            raise CerebrumError("Database error: %s" % exc_to_text(m))
        self._set_display_name(groupname, displayname,
                               disp_name_variant, disp_name_language)
        dl_group.create_distgroup_mailtarget()
        dl_group.add_spread(self.const.Spread(cereconf.EXCHANGE_GROUP_SPREAD))
        dl_group.write_db()
        return "Created Exchange group %s" % groupname

    #
    # group exchange_info <group>
    #
    all_commands['group_exchange_info'] = Command(
        ("group", "exchange_info"),
        GroupName(help_ref="id:gid:name"),
        fs=FormatSuggestion([
            ("Name:         %s\n"
             "Spreads:      %s\n"
             "Description:  %s\n"
             "Expire:       %s\n"
             "Entity id:    %i", ("name", "spread", "description",
                                  format_day("expire_date"), "entity_id")),
            ("Admin:        %s %s", ('admin_type', 'admin')),
            ("Gid:          %i", ('gid',)),
            ("Members:      %s", ("members",)),
            ("DisplayName:  %s", ('displayname',)),
            ("Roomlist:     %s", ('roomlist',)),
            ("Hidden:       %s", ('hidden',)),
            ("PrimaryAddr:  %s", ('primary',)),
            ("Aliases:      %s", ('aliases_1',)),
            ("              %s", ('aliases',))
        ]))

    def group_exchange_info(self, operator, groupname):
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to group')

        co = self.const
        grp = self._get_group(groupname, grtype="DistributionGroup")
        gr_info = self._entity_info(grp)
        roles = GroupRoles(self.db)

        # Don't stop! Never give up!
        # We just delete stuff, thats faster to implement than fixing stuff.
        del gr_info['create_date']
        del gr_info['visibility']
        del gr_info['creator_id']
        del gr_info['type']
        ret = [gr_info, ]

        # find admins
        for row in roles.search_admins(group_id=grp.entity_id):
            id = int(row['admin_id'])
            en = self._get_entity(ident=id)
            if en.entity_type == co.entity_account:
                admin = en.account_name
            elif en.entity_type == co.entity_group:
                admin = en.group_name
            else:
                admin = '#%d' % id
            ret.append({
                'admin_type': text_type(co.EntityType(en.entity_type)),
                'admin': admin,
            })

        # Member stats are a bit complex, since any entity may be a
        # member. Collect them all and sort them by members.
        members = collections.defaultdict(int)
        for row in grp.search_members(group_id=grp.entity_id):
            members[row["member_type"]] += 1

        # Produce a list of members sorted by member type
        e_type = self.const.EntityType
        entries = ["%d %s(s)" % (members[x], text_type(e_type(x)))
                   for x in sorted(members,
                                   key=lambda k: text_type(e_type(k)))]

        ret.append({"members": ", ".join(entries)})
        # Find distgroup info
        roomlist = True if grp.roomlist == 'T' else False
        dgr_info = grp.get_distgroup_attributes_and_targetdata(
                                                        roomlist=roomlist)
        del dgr_info['group_id']
        del dgr_info['name']
        del dgr_info['description']

        # Yes, I'm gonna do it!
        tmp = {}
        for attr in ['displayname', 'roomlist']:
            if attr in dgr_info:
                tmp[attr] = dgr_info[attr]
        ret.append(tmp)

        tmp = {}
        for attr in ['hidden', 'primary']:
            if attr in dgr_info:
                tmp[attr] = dgr_info[attr]
        ret.append(tmp)

        if 'aliases' in dgr_info:
            if len(dgr_info['aliases']) > 0:
                ret.append({'aliases_1': dgr_info['aliases'].pop(0)})

            for alias in dgr_info['aliases']:
                ret.append({'aliases': alias})

        return ret

    #
    # group exchange_remove <name> yes|no
    #
    all_commands['group_exchange_remove'] = Command(
        ("group", "exchange_remove"),
        GroupName(help_ref="group_name", repeat=True),
        YesNo(help_ref='yes_no_expire_group', default='No'),
        perm_filter='is_postmaster')

    def group_exchange_remove(self, operator, groupname, expire_group=False):
        # check for appropriate priviledge
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to group')
        dl_group = self._get_group(groupname, idtype='name',
                                   grtype="DistributionGroup")
        try:
            dl_group.delete_spread(
                self.const.Spread(cereconf.EXCHANGE_GROUP_SPREAD))
            dl_group.deactivate_dl_mailtarget()
            dl_group.demote_distribution()
        except Errors.NotFoundError:
            return "No Exchange group %s found" % groupname

        if self._get_boolean(expire_group):
            # set expire in 90 dates for the remaining Cerebrum-group
            dl_group.expire_date = (datetime.date.today()
                                    + datetime.timedelta(days=90))
            dl_group.write_db()
        return "Exchange group data removed for %s" % groupname

    #
    # group exchange_visibility <name> yes|no
    #
    all_commands['group_exchange_visibility'] = Command(
        ("group", "exchange_visibility"),
        GroupName(help_ref="group_name"),
        YesNo(optional=False, help_ref='yes_no_visible'),
        perm_filter='is_postmaster')

    def group_exchange_visibility(self, operator, groupname, visible):
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to group')
        dl_group = self._get_group(groupname, idtype='name',
                                   grtype="DistributionGroup")
        visible = self._get_boolean(visible)
        dl_group.set_hidden(hidden='F' if visible else 'T')
        if self._is_perishable_manual_group(dl_group):
            dl_group.set_default_expire_date()
        dl_group.write_db()
        return "OK, group {} is now {}".format(
            groupname, 'visible' if visible else 'hidden')

    #
    # group roomlist_create <name> <display-name> <description>
    #
    # create roomlists, which are a special kind of distribution group
    # no re-use of existing groups allowed
    #
    all_commands['group_roomlist_create'] = Command(
        ("group", "roomlist_create"),
        GroupName(help_ref="group_name_new"),
        SimpleString(help_ref="group_disp_name", optional=True),
        SimpleString(help_ref="string_description"),
        fs=FormatSuggestion("Group created, internal id: %i", ("group_id",)),
        perm_filter='is_postmaster')

    def group_roomlist_create(self, operator,
                              groupname, displayname, description):
        """Create a new roomlist for Exchange."""
        # check for appropriate priviledge
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to group')
        grp = Utils.Factory.get("Group")(self.db)
        try:
            grp.find_by_name(groupname)
            return "Cannot make an existing group into a roomlist"
        except Errors.NotFoundError:
            pass
        room_list = Utils.Factory.get("DistributionGroup")(self.db)
        std_values = room_list.ret_standard_attr_values(room=True)
        # although cerebrum supports different visibility levels
        # all groups are created visibile for all, and that vis
        # type is hardcoded. if the situation should change group
        # vis may be made into a parameter
        group_vis = self.const.group_visibility_all
        # the following attributes is not used and don't need to
        # be registered correctly
        # managedby is never exported to Exchange, hardcoded to
        # dl-dladmin@groups.uio.bo
        managedby = cereconf.DISTGROUP_DEFAULT_ADMIN
        # display name language is standard for dist groups
        disp_name_language = room_list.ret_standard_language()
        disp_name_variant = self.const.dl_group_displ_name
        # we could use _valid_address_exchange here in stead,
        # I'll leave as an exercise for a willing developer
        # :-) (Jazz, 2013-12)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_address(managedby)
        except Errors.NotFoundError:
            # should never happen unless default admin
            # dist group is deleted from Cerebrum
            return ('Default admin address does not exist, please contact'
                    ' cerebrum-drift@usit.uio.no for help!')
        if not displayname:
            displayname = groupname
        # using DistributionGroup.new(...)
        room_list.new(
            creator_id=operator.get_entity_id(),
            visibility=group_vis,
            name=groupname,
            description=description,
            group_type=self.const.group_type_manual,
            roomlist=std_values['roomlist'],
            hidden=std_values['hidden'],
        )
        room_list.write_db()
        room_list.add_spread(self.const.Spread(cereconf.EXCHANGE_GROUP_SPREAD))
        self._set_display_name(groupname, displayname, disp_name_variant,
                               disp_name_language)
        room_list.write_db()

        # Try to set the default group admin
        try:
            grp.clear()
            grp.find_by_name(cereconf.EXCHANGE_ROOMLIST_OWNER)
        except (Errors.NotFoundError, AttributeError):
            # If the group admin group does not exist, or is not defined,
            # we won't set a group admin.
            pass
        else:
            roles = GroupRoles(self.db)
            roles.add_admin_to_group(grp.entity_id, room_list.entity_id)

        return "Made roomlist %s" % groupname

    #
    # group create
    #
    # (all_commands is updated from BofhdCommonMethods)
    #
    def group_create(self, operator, groupname, description, admin_group=None):
        """Override group_create to double check that there doesn't exist an
        account with the same name.
        """
        ac = self.Account_class(self.db)
        try:
            ac.find_by_name(groupname)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError('An account exists with name: %s' % groupname)
        return super(BofhdExtension, self).group_create(
            operator, groupname, description, admin_group)

    #
    # group request <name> <desc> <spread> <admin-group>
    #
    # like group create, but only send request to the ones with the access to
    # the 'group create' command Currently send email to brukerreg@usit.uio.no
    #
    all_commands['group_request'] = Command(
        ("group", "request"),
        GroupName(help_ref="group_name_new"),
        SimpleString(help_ref="string_description"),
        SimpleString(help_ref="string_spread"),
        GroupName(help_ref="group_name_admin"))

    def _get_from_address(self, operator):
        fromaddr = None
        opr = operator.get_entity_id()
        acc = self.Account_class(self.db)
        acc.find(opr)

        try:
            fromaddr = acc.get_primary_mailaddress()
        except Errors.NotFoundError:
            contact_rows = acc.get_contact_info()
            for row in contact_rows:
                if row['contact_type'] == int(self.const.contact_email):
                    fromaddr = row['contact_value']

        if fromaddr is None:
            raise CerebrumError('Request failed. Operator has no mail address')
        return fromaddr

    def group_request(self, operator,
                      groupname, description, spread, admin):
        opr = operator.get_entity_id()
        acc = self.Account_class(self.db)
        acc.find(opr)
        # checking if group already exists
        try:
            self._get_group(groupname)
        except CerebrumError:
            pass
        else:
            raise CerebrumError("Group %s already exists" % (groupname))

        # checking if admin groups exist
        for admin in admin.split(' '):
            try:
                self._get_group(admin)
            except CerebrumError:
                raise CerebrumError("Admin group %s not found" % (admin))

        fromaddr = self._get_from_address(operator)

        toaddr = cereconf.GROUP_REQUESTS_SENDTO
        if spread is None:
            spread = ""
        spreadstring = "(" + spread + ")"
        spreads = []
        spreads = re.split(" ", spread)

        # TODO: Make template
        subject = "Cerebrum group create request %s" % groupname
        body = []
        body.append("Please create a new group:")
        body.append("")
        body.append("Group-name: %s." % groupname)
        body.append("Description:  %s" % description)
        body.append("Requested by: %s" % fromaddr)
        body.append("Admin: %s" % admin)
        body.append("")
        body.append("group create %s \"%s\" %s" % (groupname, description,
                                                   admin))
        for spr in spreads:
            if spr and self._get_constant(self.const.Spread, spr) in (
                    self.const.spread_uio_nis_fg,
                    self.const.spread_ifi_nis_fg,
                    self.const.spread_hpc_nis_fg):
                pg = Utils.Factory.get('PosixGroup')(self.db)
                err_str = pg.illegal_name(groupname)
                if err_str:
                    if not isinstance(err_str, string_types):  # paranoia
                        err_str = u'Illegal groupname'
                    raise CerebrumError(u'Group-name error: {err_str}'.format(
                        err_str=err_str))
                body.append("group promote_posix %s" % groupname)
        if spread:
            body.append("spread add group %s %s" % (groupname, spreadstring))
        body.append("group info %s" % groupname)
        body.append("")
        body.append("")
        sendmail(toaddr, fromaddr, subject, "\n".join(body))
        return "Request sent to %s" % toaddr

    #
    #  group def <username> <groupname>
    #
    all_commands['group_def'] = Command(
        ('group', 'def'),
        AccountName(),
        GroupName(help_ref="group_name_dest"))

    def group_def(self, operator, accountname, groupname):
        account = self._get_account(accountname, actype="PosixUser")
        grp = self._get_group(groupname, grtype="PosixGroup")
        if not self.ba.is_superuser(operator.get_entity_id()):
            self._raise_PermissionDenied_if_not_manual_group(grp)
        if self._is_perishable_manual_group(grp):
            grp.set_default_expire_date()
            grp.write_db()
        op = operator.get_entity_id()
        self.ba.can_set_default_group(op, account, grp)
        account.gid_id = grp.entity_id
        account.write_db()

        return "OK, set default-group for '%s' to '%s'" % (
            accountname, groupname)

    #
    # group delete <groupname>
    #
    all_commands['group_delete'] = Command(
        ("group", "delete"),
        GroupName(),
        YesNo(help_ref="yes_no_force", optional=True, default="No"),
        perm_filter='can_delete_group')

    def group_delete(self, operator, groupname, force=False):

        grp = self._get_group(groupname)
        if not self.ba.is_superuser(operator.get_entity_id()):
            self._raise_PermissionDenied_if_not_manual_group(grp)
        if force:
            # Force deletes the group directly. Expire date etc is not used.
            self.ba.can_force_delete_group(operator.get_entity_id(), grp)
            self._assert_group_deletable(grp)

            # Exchange-relatert-jazz
            # It should not be possible to remove distribution groups via
            # bofh, as that would "orphan" e-mail target. If need be such
            # groups should be nuked using a cerebrum-side script.
            if grp.has_extension('DistributionGroup'):
                raise CerebrumError(
                    'Cannot delete distribution groups, use "group'
                    ' exchange_remove" to deactivate %s' % groupname)
            elif grp.has_extension('PosixGroup'):
                raise CerebrumError(
                    'Cannot delete posix groups, use "group demote_posix %s"'
                    ' before deleting.' % groupname)
            elif grp.get_extensions():
                raise CerebrumError(
                    'Cannot delete group %s, is type %r' % (
                        groupname, grp.get_extensions()))

            self._remove_auth_target("group", grp.entity_id)
            self._remove_auth_role(grp.entity_id)
            try:
                grp.delete()
            except self.db.DatabaseError as msg:
                if re.search("group_member_exists", exc_to_text(msg)):
                    raise CerebrumError(
                        ("Group is member of groups.  "
                         "Use 'group memberships group %s'") % grp.group_name)
                elif re.search("account_info_owner", exc_to_text(msg)):
                    raise CerebrumError(
                        ("Group is owner of an account.  "
                         "Use 'entity accounts group %s'") % grp.group_name)
                raise

            return u'OK, deleted group "{0}"'.format(groupname)
        else:
            # Normal delete. Set the expire date to today.
            self.ba.can_delete_group(operator.get_entity_id(), grp)
            self._assert_group_deletable(grp)
            # Set the groups expire date to today.

            # If expire date exists and today is same or past expire date
            expire_date = date_compat.get_date(grp.expire_date)
            today = datetime.date.today()
            if expire_date and expire_date <= today:
                raise CerebrumError('Group already expired')
            else:
                grp.expire_date = today
                grp.write_db()
                return u'OK, set expire-date for {0} to {1}'.format(
                    groupname,
                    today.isoformat())

    def _assert_group_deletable(self, grp):
        """
        Trows an exception if group is not deletable.

        The following groups are not deletable:
        - BOFHD superuser group
        - Personal file groups
        """
        if grp.get_trait(self.const.trait_personal_dfg):
            raise CerebrumError('Cannot delete personal file group')
        elif grp.group_name == cereconf.BOFHD_SUPERUSER_GROUP:
            raise CerebrumError("Can't delete superuser group")
        elif grp.group_name == cereconf.INITIAL_GROUPNAME:
            raise CerebrumError("Can't delete bofhd initial group")
    #
    # group multi_remove
    #
    # jokim 2008-12-02 TBD: removed from jbofh, but not wofh
    #
    hidden_commands['group_multi_remove'] = Command(
        ("group", "multi_remove"),
        MemberType(help_ref='member_type', default='account'),
        MemberName(help_ref="member_name_src", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        perm_filter='can_alter_group')

    def group_multi_remove(self, operator, member_type, src_name, dest_group):
        """Removes a person, account or group from a given group."""
        # If int in any of the names we assume the user intended to write an
        # entity id and prefix it with id: for them
        if isinstance(src_name, int):
            src_name = 'id:' + text_type(src_name)
        if isinstance(dest_group, int):
            dest_group = 'id:' + text_type(dest_group)
        if member_type not in ('group', 'account', 'person', ):
            return 'Unknown member_type "%s"' % (member_type)
        self.ba.can_alter_group(operator.get_entity_id(),
                                self._get_group(dest_group))
        return self._group_remove(operator, src_name, dest_group,
                                  member_type=member_type)

    # FIXME - group_remove and group_gremove is now handled by
    # group_multi_remove(membertype='group'...), and should be removed as soon
    # as the other institutions has updated their dependency.
    # group_multi_remove should then be renamed to group_remove.

    #
    # group remove <username> <groupname>
    #
    all_commands['group_remove'] = Command(
        ("group", "remove"),
        AccountName(help_ref="account_name_member", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True))

    def group_remove(self, operator, src_name, dest_group):
        try:
            # First, check if this is a user we can set the password
            # for; if so, we should be allowed to remove this user
            # from groups, e.g. if we have LITA rights for the account
            account = self._get_account(src_name)
            self.ba.can_set_password(operator.get_entity_id(), account)
        except PermissionDenied:
            # If that fails; check if we have rights pertaining to the
            # group in question
            group = self._get_group(dest_group)
            self.ba.can_alter_group(operator.get_entity_id(), group)
        return self._group_remove(operator, src_name, dest_group,
                                  member_type="account")

    #
    # group gremove
    #
    all_commands['group_gremove'] = Command(
        ("group", "gremove"),
        GroupName(help_ref="group_name_src", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        perm_filter='can_alter_group')

    def group_gremove(self, operator, src_name, dest_group):
        self.ba.can_alter_group(operator.get_entity_id(),
                                self._get_group(dest_group))
        return self._group_remove(operator, src_name, dest_group,
                                  member_type="group")

    #
    # group premove
    #
    all_commands['group_premove'] = Command(
        ("group", "premove"),
        MemberName(help_ref='member_name_src', repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        perm_filter='can_alter_group')

    def group_premove(self, operator, src_name, dest_group):
        self.ba.can_alter_group(operator.get_entity_id(),
                                self._get_group(dest_group))
        return self._group_remove(operator, src_name, dest_group,
                                  member_type="person")

    def _group_remove(self, operator, src_name, dest_group, member_type=None):
        """Remove src_group(s) from given dest_group(s)

        Both src_name and dest_group can be in the formats group_name,
        name:group_name, and id:entity_id.

        :param operator: operator in bofh session
        :param src_name: str name of source group.
        :param dest_group: str name of destination group
        :param member_type: str type of member
        :return:
        """
        if member_type == "group":
            src_entity = self._get_group(src_name)
        elif member_type == "account":
            src_entity = self._get_account(src_name)
        elif member_type == "person":
            try:
                src_entity = self.util.get_target(src_name,
                                                  restrict_to=['Person'])
            except Errors.TooManyRowsError:
                raise CerebrumError("Unexpectedly found more than one person")
        else:
            raise CerebrumError("Unknown member_type: %r" % member_type)
        group_d = self._get_group(dest_group)
        return self._group_remove_entity(operator, src_entity, group_d)

    def _group_remove_entity(self, operator, member, group):
        member_name = self._get_name_from_object(member)
        if not self.ba.is_superuser(operator.get_entity_id()):
            self._raise_PermissionDenied_if_not_manual_group(group)
        if not group.has_member(member.entity_id):
            return ("%s isn't a member of %s" %
                    (member_name, group.group_name))
        if member.entity_type == self.const.entity_account:
            try:
                pu = Utils.Factory.get('PosixUser')(self.db)
                pu.find(member.entity_id)
                if pu.gid_id == group.entity_id:
                    raise CerebrumError("Can't remove %s from primary "
                                        "group %s" % (member_name,
                                                      group.group_name))
            except Errors.NotFoundError:
                pass
        if self._is_perishable_manual_group(group):
            group.set_default_expire_date()
            group.write_db()
        try:
            group.remove_member(member.entity_id)
        except self.db.DatabaseError as m:
            raise CerebrumError("Database error: %s" % exc_to_text(m))
        return u"OK, removed '{member}' from '{group}'".format(
            member=member_name, group=group.group_name)

    #
    # group remove_entity
    #
    all_commands['group_remove_entity'] = None

    def group_remove_entity(self, operator, member_entity, group_entity):
        group = self._get_entity(ident=group_entity)
        self.ba.can_alter_group(operator.get_entity_id(), group)
        member = self._get_entity(ident=member_entity)
        return self._group_remove_entity(operator, member, group)

    #
    # group info <groupname>
    #
    all_commands['group_info'] = Command(
        ("group", "info"),
        GroupName(help_ref="id:gid:name"),
        fs=FormatSuggestion([
            ("Name:         %s\n"
             "Type:         %s\n"
             "Spreads:      %s\n"
             "Description:  %s\n"
             "Expire:       %s\n"
             "Entity id:    %i", ("name", "group_type", "spread",
                                  "description",
                                  format_day("expire_date"), "entity_id")),
            ("Admin:        %s %s", ('admin_type', 'admin')),
            ("Moderator:    %s %s", ('mod_type', 'mod')),
            ("Gid:          %i", ('gid',)),
            ("Members:      %s", ("members",))
        ]))

    def group_info(self, operator, groupname):
        # TODO: Group visibility should probably be checked against
        # operator for a number of commands
        try:
            grp = self._get_group(groupname, grtype="PosixGroup")
        except CerebrumError:
            if groupname.startswith('gid:'):
                gid = groupname.split(':', 1)[1]
                raise CerebrumError("Could not find PosixGroup with gid=%s" %
                                    gid)
            grp = self._get_group(groupname)
        co = self.const
        ret = [self._entity_info(grp), ]
        # find admins
        roles = GroupRoles(self.db)
        for row in roles.search_admins(group_id=grp.entity_id):
            id = int(row['admin_id'])
            en = self._get_entity(ident=id)
            if en.entity_type == co.entity_account:
                admin = en.account_name
            elif en.entity_type == co.entity_group:
                admin = en.group_name
            else:
                admin = '#%d' % id
            ret.append({
                'admin_type': text_type(co.EntityType(en.entity_type)),
                'admin': admin,
            })
        # find moderators
        for row in roles.search_moderators(group_id=grp.entity_id):
            id = int(row['moderator_id'])
            en = self._get_entity(ident=id)
            if en.entity_type == co.entity_account:
                mod = en.account_name
            elif en.entity_type == co.entity_group:
                mod = en.group_name
            else:
                mod = '#%d' % id
            ret.append({
                'mod_type': text_type(co.EntityType(en.entity_type)),
                'mod': mod,
            })

        # Member stats are a bit complex, since any entity may be a
        # member. Collect them all and sort them by members.
        members = collections.defaultdict(int)
        for row in grp.search_members(group_id=grp.entity_id):
            members[row["member_type"]] += 1

        # Produce a list of members sorted by member type
        e_type = self.const.EntityType
        entries = ["%d %s(s)" % (members[x], text_type(e_type(x)))
                   for x in sorted(members,
                                   key=lambda k: text_type(e_type(k)))]

        ret.append({"members": ", ".join(entries)})
        return ret

    #
    # group list <groupname>
    #
    all_commands['group_list'] = Command(
        ("group", "list"),
        GroupName(),
        fs=FormatSuggestion(
            "%-10s %-15s %-45s %-10s",
            ("type", "user_name", "full_name", "expired"),
            hdr="%-10s %-15s %-45s %-10s" %
            ("Type", "Username", "Fullname", "Expired")
        ))

    def group_list(self, operator, groupname):
        """List direct members of group"""
        group = self._get_group(groupname)
        ret = []
        today = datetime.date.today()
        members = list(group.search_members(group_id=group.entity_id,
                                            indirect_members=False,
                                            member_filter_expired=False))
        if (len(members) > cereconf.BOFHD_MAX_MATCHES and
                not self.ba.is_superuser(operator.get_entity_id())):
            raise CerebrumError("More than %d (%d) matches. Contact superuser "
                                "to get a listing for %r" %
                                (cereconf.BOFHD_MAX_MATCHES, len(members),
                                 groupname))
        ac = self.Account_class(self.db)
        pe = Utils.Factory.get('Person')(self.db)
        for x in self._fetch_member_names(members):
            member_type = self.const.EntityType(x['member_type'])
            item = {
                'id': x['member_id'],
                'type': text_type(member_type),
                'name': x['member_name'],  # Compability with brukerinfo
            }
            if member_type == self.const.entity_account:
                ac.find(x['member_id'])
                try:
                    pe.find(ac.owner_id)
                    full_name = pe.get_name(self.const.system_cached,
                                            self.const.name_full)
                except Errors.NotFoundError:
                    full_name = ''
                user_name = x['member_name']
                expire_date = date_compat.get_date(ac.expire_date)
                ac.clear()
                pe.clear()

            else:
                full_name = x['member_name']
                user_name = '<non-account>'
                expire_date = None
            item.update({
                'full_name': full_name,
                'user_name': user_name,
                'expired': None,
            })
            if expire_date and expire_date < today:
                item["expired"] = "expired"
            ret.append(item)

        ret.sort(key=lambda d: (d['type'], d['user_name']))
        return ret

    def _fetch_member_names(self, iterable):
        """Locate names for elements in iterable.

        This is a convenience method. It helps us to locate names associated
        with certain member ids. For group and account members we try to fetch
        a name (there is at most one). For all other types we assume no such
        name exists.

        @type iterable: sequence (any iterable sequence) or a generator.
        @param iterable:
          A 'iterable' over db_rows that we have to map to names. Each db_row
          has a number of keys. This method examines 'member_type' and
          'member_id'. All others are ignored.

        @rtype: generator (over modified elements of L{iterable})
        @return:
          A generator over db_rows from L{iterable}. Each db_row gets an
          additional key, 'member_name' containing the name of the element or
          None, if no name can be located. The relative order of elements in
          L{iterable} is preserved. The underlying db_row objects are modified.
        """
        # TODO: hack to omit bug when inserting new key/value pairs in db_row
        for item in iterable:
            d = dict(item)
            d.update({
                'member_name': self._get_entity_name(int(item['member_id']),
                                                     int(item['member_type'])),
            })
            yield d

    #
    # group list_expanded <groupname>
    #
    all_commands['group_list_expanded'] = Command(
        ("group", "list_expanded"),
        GroupName(),
        fs=FormatSuggestion(
            "%8i %10s %30s %25s",
            ("member_id", "member_type", "member_name", "group_name"),
            hdr="%8s %10s %30s %30s" %
            ("mem_id", "mem_type", "member_name", "is a member of group_name")
        ))

    def group_list_expanded(self, operator, groupname):
        """List members of group after expansion"""
        def type2str(x):
            return text_type(self.const.EntityType(int(x)))

        group = self._get_group(groupname)
        result = list()
        all_members = list(group.search_members(group_id=group.entity_id,
                                                indirect_members=True))
        if (len(all_members) > cereconf.BOFHD_MAX_MATCHES and
                not self.ba.is_superuser(operator.get_entity_id())):
            raise CerebrumError("More than %d (%d) matches, contact superuser "
                                "to get a listing for %r" %
                                (cereconf.BOFHD_MAX_MATCHES, len(all_members),
                                 groupname))
        for member in all_members:
            member_type = member["member_type"]
            member_id = member["member_id"]
            result.append({
                "member_id": member_id,
                "member_type": type2str(member_type),
                "member_name": self._get_entity_name(int(member_id),
                                                     member_type),
                "group_name": self._get_entity_name(int(member["group_id"]),
                                                    self.const.entity_group),
            })
        return result

    #
    # group personal <uname>+
    #
    all_commands['group_personal'] = Command(
        ("group", "personal"),
        AccountName(repeat=True),
        fs=FormatSuggestion(
            "Personal group created and made primary, POSIX gid: %i\n"
            "The user may have to wait a minute, then restart bofh to access\n"
            "the 'group add' command",
            ("group_id",)
        ),
        perm_filter='can_create_personal_group',
    )

    def group_personal(self, operator, uname):
        """This is a separate command for convenience and consistency.
        A personal group is always a PosixGroup, and has the same
        spreads as the user."""
        acc = self._get_account(uname, actype="PosixUser")
        op = operator.get_entity_id()
        self.ba.can_create_personal_group(op, acc)
        # Create group
        group = self.Group_class(self.db)
        try:
            group.find_by_name(uname)
            raise CerebrumError("Group %r already exists" % uname)
        except Errors.NotFoundError:
            group.populate(
                creator_id=op,
                visibility=self.const.group_visibility_all,
                name=uname,
                description=('Personal file group for %s' % uname),
                group_type=self.const.group_type_personal,
            )
            group.write_db()
        # Promote to PosixGroup
        if not self.ba.is_superuser(operator.get_entity_id()):
            self._raise_PermissionDenied_if_not_manual_group(group)
        pg = Utils.Factory.get('PosixGroup')(self.db)
        pg.populate(parent=group)
        try:
            pg.write_db()
        except self.db.DatabaseError as m:
            raise CerebrumError("Database error: %s" % m)
        # Make the user the admin of the group so they can administer it
        roles = GroupRoles(self.db)
        roles.add_admin_to_group(acc.entity_id, group.entity_id)
        # Make user a member of his personal group
        self._group_add(None, uname, uname, member_type="account")
        # Add personal group-trait to group
        if hasattr(self.const, 'trait_personal_dfg'):
            pg.populate_trait(self.const.trait_personal_dfg,
                              target_id=acc.entity_id)
            pg.write_db()
        # Set group as primary group
        acc.gid_id = group.entity_id
        acc.write_db()
        return {'group_id': int(pg.posix_gid)}

    #
    # group posix_create <name> <description>
    #
    all_commands['group_promote_posix'] = Command(
        ("group", "promote_posix"),
        GroupName(),
        SimpleString(help_ref="string_description", optional=True),
        fs=FormatSuggestion(
            "Group promoted to PosixGroup, posix gid: %i",
            ("group_id",)),
        perm_filter='can_create_group')

    def group_promote_posix(self, operator, group, description=None):
        self.ba.can_create_group(operator.get_entity_id(),
                                 groupname=self._get_group(group).group_name)
        is_posix = False
        try:
            self._get_group(group, grtype="PosixGroup")
            is_posix = True
        except CerebrumError:
            pass
        if is_posix:
            raise CerebrumError("%s is already a PosixGroup" % group)

        group = self._get_group(group)
        if not self.ba.is_superuser(operator.get_entity_id()):
            self._raise_PermissionDenied_if_not_manual_group(group)
        if self._is_perishable_manual_group(group):
            group.set_default_expire_date()
            group.write_db()
        pg = Utils.Factory.get('PosixGroup')(self.db)
        pg.populate(parent=group)
        try:
            pg.write_db()
        except self.db.DatabaseError as m:
            raise CerebrumError("Database error: %s" % m)
        return {'group_id': int(pg.posix_gid)}

    #
    # group posix_demote <name>
    #
    all_commands['group_demote_posix'] = Command(
        ("group", "demote_posix"),
        GroupName(),
        perm_filter='can_force_delete_group')

    def group_demote_posix(self, operator, group):
        try:
            grp = self._get_group(group, grtype="PosixGroup")
        except self.db.DatabaseError as msg:
            if "posix_user_gid" in exc_to_text(msg):
                raise CerebrumError(
                    ("Assigned as primary group for posix user(s). "
                     "Use 'group list %s'") % grp.group_name)
            raise
        if not self.ba.is_superuser(operator.get_entity_id()):
            self._raise_PermissionDenied_if_not_manual_group(grp)
        if self._is_perishable_manual_group(grp):
            grp.set_default_expire_date()
            grp.write_db()
        if grp.is_user_group():
            raise CerebrumError(
                "Can't demote group because it is assigned as primary group "
                "for posix user(s).")

        self.ba.can_force_delete_group(operator.get_entity_id(), grp)
        grp.demote_posix()
        return "OK, demoted '%s'" % group

    #
    # group search
    #
    all_commands['group_search'] = Command(
        ("group", "search"),
        SimpleString(help_ref="string_group_filter"),
        fs=FormatSuggestion(
            "%8i %-16s %s", ("id", "name", "desc"),
            hdr="%8s %-16s %s" % ("Id", "Name", "Description")
        ),
        perm_filter='can_search_group')

    def group_search(self, operator, filter):
        self.ba.can_search_group(operator.get_entity_id(), filter=filter)
        group = self.Group_class(self.db)
        if filter == "":
            raise CerebrumError("No filter specified")
        filters = {'name': None,
                   'desc': None,
                   'spread': None,
                   'expired': "no"}
        rules = filter.split(",")
        for rule in rules:
            if rule.count(":"):
                filter_type, pattern = rule.split(":", 1)
            else:
                filter_type = 'name'
                pattern = rule
            if filter_type not in filters:
                raise CerebrumError("Unknown filter type: %r" % filter_type)
            filters[filter_type] = pattern
        if filters['name'] == '*' and len(rules) == 1:
            raise CerebrumError("Please provide a more specific filter")
        # remap code_str to the actual constant object (the API requires it)
        if filters['spread']:
            filters['spread'] = self._get_constant(self.const.Spread,
                                                   filters["spread"])
        filter_expired = not self._get_boolean(filters['expired'])
        ret = []
        for r in group.search(spread=filters['spread'],
                              name=filters['name'],
                              description=filters['desc'],
                              filter_expired=filter_expired):
            ret.append({
                'id': r['group_id'],
                'name': r['name'],
                'desc': r['description'],
            })
        return ret

    #
    # group set_type <name> <type>
    #
    all_commands['group_set_type'] = Command(
        ("group", "set_type"),
        GroupName(),
        SimpleString(help_ref='group_type'),
        fs=FormatSuggestion(
            "Ok, group_type='%s' for group='%s'",
            ('group_type', 'group_name'),
        ),
        perm_filter='can_set_group_type')

    def group_set_type(self, operator, group, group_type):
        grp = self._get_group(group)
        if not self.ba.is_superuser(operator.get_entity_id()):
            self._raise_PermissionDenied_if_not_manual_group(grp)
        group_type = self._get_constant(self.const.GroupType, group_type)
        self.ba.can_set_group_type(operator.get_entity_id(), grp, group_type)
        if self._is_perishable_manual_group(grp):
            grp.set_default_expire_date()
        grp.group_type = group_type
        grp.write_db()
        return {
            'group_type': str(group_type),
            'group_name': grp.group_name,
            'group_id': grp.entity_id,
        }

    #
    # group set_description <name> <desc>
    #
    all_commands['group_set_description'] = Command(
        ("group", "set_description"),
        GroupName(),
        SimpleString(help_ref="string_description"),
        perm_filter='can_alter_group')

    def group_set_description(self, operator, group, description):
        grp = self._get_group(group)
        if not self.ba.is_superuser(operator.get_entity_id()):
            self._raise_PermissionDenied_if_not_manual_group(grp)
        self.ba.can_alter_group(operator.get_entity_id(), grp)
        if self._is_perishable_manual_group(grp):
            grp.set_default_expire_date()
        grp.description = description
        grp.write_db()
        return "OK, description for group '%s' updated" % group

    #
    # group set_display_name
    #
    # exchange-relatert-jazz
    # set display name, only for distribution groups and roomlists
    # for the time being, but may be interesting to use for other
    # groups as well
    #
    all_commands['group_set_displayname'] = Command(
        ("group", 'set_display_name'),
        GroupName(help_ref="group_name"),
        SimpleString(help_ref="group_disp_name"),
        SimpleString(help_ref='display_name_language', default='nb'),
        perm_filter="is_postmaster")

    def group_set_displayname(self, operator, gname, disp_name, name_lang):
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to group')
        name_variant = self.const.dl_group_displ_name
        self._set_display_name(gname, disp_name, name_variant, name_lang)
        return "Registered display name %s for %s" % (disp_name, gname)

    # helper method, will use in distgroup_ and roomlist_create
    # as they both require sett display_name
    def _set_display_name(self, gname, disp_name, name_var, name_lang):
        # if this method is to be of generic use the name variant must
        # be made into a parameter. it may be advisable to change
        # dl_group_displ_name into a more generic group_display_name
        # value in the future
        group = self._get_group(gname, grtype="DistributionGroup")
        if name_lang in self.language_codes:
            name_lang = int(_LanguageCode(name_lang))
        else:
            return "Could not set display name, invalid language code"
        group.add_name_with_language(name_var, name_lang,
                                     disp_name)
        if self._is_perishable_manual_group(group):
            group.set_default_expire_date()
        group.write_db()

    #
    # group set_expire
    #
    all_commands['group_set_expire'] = Command(
        ("group", "set_expire"),
        GroupName(),
        # TODO: We should update the help text to include info from
        # parsers.parse_date_help_blurb
        Date(optional=True),
        perm_filter='can_delete_group',
        # TODO: Update brukerinfo to handle data structure return value
        # fs=FormatSuggestion(
        #     "OK, set expire date for group %s to %s",
        #     ('group_name', format_day('expire_date')),
        # ),
    )

    def group_set_expire(self, operator, group, _expire=None):
        grp = self._get_group(group)

        try:
            self.ba.can_delete_group(operator.get_entity_id(), grp)
        except PermissionDenied:
            raise PermissionDenied(
                "Not allowed to change expire date for group")

        is_superuser = self.ba.is_superuser(operator.get_entity_id())

        if not is_superuser:
            self._raise_PermissionDenied_if_not_manual_group(grp)

        expire = parsers.parse_date(_expire, optional=True)
        if not expire and not is_superuser:
            raise CerebrumError('Invalid date: ' + repr(_expire))

        max_delta = datetime.timedelta(days=366)
        delta = (expire - datetime.date.today()) if expire else None

        if (delta and delta > max_delta and not is_superuser):
            raise PermissionDenied('Cannot set expire date > %s days'
                                   % max_delta.days)

        if expire:
            # set the given expire date
            grp.expire_date = expire
        elif (self._is_perishable_manual_group(grp)
                and cereconf.MANUAL_GROUP_DEFAULT_LIFETIME):
            # no expire given - set default expire if configured to do so
            grp.set_default_expire_date()
        else:
            # no expire given for automatic group - set to None if superuser
            if is_superuser:
                grp.expire_date = None
            else:
                raise CerebrumError('Missing expire date')

        grp.write_db()
        return (
            u'OK, set expire date for group %(group_name)s '
            u'to %(expire_date)s'
            % {
                'group_name': grp.group_name,
                'expire_date': date_compat.get_date(grp.expire_date),
            })

    #
    # group clear_expire
    #
    all_commands['group_clear_expire'] = Command(
        ("group", "clear_expire"),
        GroupName(),
        perm_filter='is_superuser',
        fs=FormatSuggestion(
            "OK, cleared expire date for group %s", ('group_name',),
        ),
    )

    def group_clear_expire(self, operator, group):
        grp = self._get_group(group)

        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Only superuser can clear expire_date")

        if not grp.expire_date:
            raise CerebrumError("Group '%s' has no expire date" %
                                (grp.group_name,))
        grp.expire_date = None
        grp.write_db()

        return {
            'group_id': grp.entity_id,
            'group_name': grp.group_name,
            'expire_date': date_compat.get_date(grp.expire_date),
        }

    #
    # group set_visibility
    #
    all_commands['group_set_visibility'] = Command(
        ("group", "set_visibility"),
        GroupName(),
        GroupVisibility(),
        perm_filter='can_delete_group')

    def group_set_visibility(self, operator, group, visibility):
        grp = self._get_group(group)
        self.ba.can_delete_group(operator.get_entity_id(), grp)
        if not self.ba.is_superuser(operator.get_entity_id()):
            self._raise_PermissionDenied_if_not_manual_group(grp)
        if self._is_perishable_manual_group(grp):
            grp.set_default_expire_date()
        grp.visibility = self._get_constant(self.const.GroupVisibility,
                                            visibility, "visibility")
        grp.write_db()
        return "OK, set visibility for '%s'" % group

    #
    # group memberships
    #
    all_commands['group_memberships'] = Command(
        ('group', 'memberships'),
        EntityType(default="account"),
        Id(),
        YesNo(optional=True, default='no', help_ref='include_lms'),
        Spread(optional=True, help_ref='spread_filter'),
        fs=FormatSuggestion(
            "%-9s %-18s", ("memberop", "group"),
            hdr="%-9s %-18s" % ("Operation", "Group")
        ))

    def group_memberships(self, operator, entity_type,
                          id, include_lms="no", spread=None):
        group_types = self.const.fetch_constants(_GroupTypeCode)
        default_group_types = {str(x): int(x) for x in group_types}
        if not self._get_boolean(include_lms):
            default_group_types.pop("lms-group", None)  # Remove fronter-groups
        entity = self._get_entity(entity_type, id)
        group = self.Group_class(self.db)
        co = self.const
        if spread is not None:
            spread = self._get_constant(self.const.Spread, spread, "spread")
        ret = []
        for row in group.search(
                member_id=entity.entity_id, spread=spread,
                group_type=default_group_types.values()
        ):
            ret.append({
                'memberop': text_type(co.group_memberop_union),
                'entity_id': row["group_id"],
                'group': row["name"],
                'description': row["description"],
            })
        ret.sort(key=lambda d: d['group'])
        return ret

    #
    # group memberships_expanded
    #
    all_commands['group_memberships_expanded'] = Command(
        ('group', 'memberships_expanded'),
        EntityType(default="account"),
        Id(),
        Spread(optional=True, help_ref='spread_filter'),
        fs=FormatSuggestion(
            "%-50s %-20s", ("group", "sources_names_str"),
            hdr="%-50s %-20s" % ("Group", "Source group")
        ))

    def group_memberships_expanded(self, operator, entity_type, entity_id,
                                   spread=None):
        entity = self._get_entity(entity_type, entity_id)
        group = self.Group_class(self.db)
        co = self.const
        if spread is not None:
            spread = self._get_constant(self.const.Spread, spread, "spread")
        ret = []

        for row in group.search(member_id=entity.entity_id,
                                indirect_members=True):
            ret.append({
                'memberop': text_type(co.group_memberop_union),
                'entity_id': row['group_id'],
                'group': row['name'],
                'description': row['description'],
                'sources': [],
                'sources_names': [],
                'sources_names_str': '',
                'spreads': [],
                'spreads_str': ''
            })

        for membership in ret:
            group.find(membership['entity_id'])
            membership['spreads'] = [
                co.Spread(x['spread']) for x in group.get_spread()]

            # Find the source group (if any)
            for source_group in ret:
                # We skip groups where the entity is a direct member
                if group.has_member(entity.entity_id):
                    continue
                elif group.has_member(source_group['entity_id']):
                    membership['sources'].append(source_group['entity_id'])
                    membership['sources_names'].append(source_group['group'])
            group.clear()

        if spread:
            # Only select groups with spread x
            ret = [x for x in ret if spread in [co.Spread(y) for y in x[
                'spreads']]]

        for membership in ret:
            membership['sources_names_str'] = u', '.join(
                membership['sources_names'])
            membership['spreads'] = map(text_type, membership['spreads'])

        ret.sort(key=lambda d: d['group'])
        return ret

    #
    # group roles
    #
    all_commands['group_roles'] = Command(
        ('group', 'roles'),
        EntityType(default="account"),
        Id(),
        fs=FormatSuggestion(
            "%-10s %s", ("role", "group_name"),
            hdr="%-10s %s" %
            ("Role", "Group")
        )
    )

    def group_roles(self, operator, entity_type, entity_id):
        """Return a list of what groups an account or group can moderate or
        administrate.
        """
        entity = self._get_entity(entity_type, entity_id)
        group = self.Group_class(self.db)
        indirect = entity_type != 'group'
        admins = group.search(
            admin_id=entity.entity_id,
            admin_by_membership=indirect
        )
        moderators = group.search(
            moderator_id=entity.entity_id,
            moderator_by_membership=indirect
        )

        result = [{'role': 'admin', 'group_name': r['name']}
                  for r in admins]
        result += [{'role': 'moderator', 'group_name': r['name']}
                   for r in moderators]
        return result

    #
    # group list_admins <groupname>
    #
    all_commands['group_list_admins'] = Command(
        ('group', 'list_admins'),
        GroupName(),
    )

    def group_list_admins(self, operator, groupname):
        """List admins of a group by type (account or group)"""
        raise CerebrumError(
            "Deprecated; Use `group list_owners <group> admin`")

    #
    # group list_mods <groupname>
    #
    all_commands['group_list_mods'] = Command(
        ('group', 'list_mods'),
        GroupName(),
    )

    def group_list_mods(self, operator, groupname):
        """List moderators of a group by type (account or group)"""
        raise CerebrumError(
            "Deprecated; Use `group list_owners <group> moderator`")

    #
    # group accounts <groupname>
    #
    all_commands["group_accounts"] = Command(
        ("group", "accounts"),
        GroupName(),
        fs=FormatSuggestion(
            "%-8i %-30s %-25s",
            ("account_id", "account_name", "group_name"),
            hdr="%-8s %-30s %-25s" % ("id", "name", "group name"),
        ),
    )

    def group_accounts(self, operator, groupname):
        """Lists all accounts the given group owns."""
        gr = self._get_group(groupname)
        acc_type = self.const.entity_account
        accs = [a["account_id"] for a in gr.get_owned_accounts()]

        if (len(accs) > cereconf.BOFHD_MAX_MATCHES
                and not self.ba.is_superuser(operator.get_entity_id())):
            raise CerebrumError(
                "More than %d (%d) matches, contact superuser "
                "to get a listing for %r"
                % (cereconf.BOFHD_MAX_MATCHES, len(accs), gr.group_name)
            )

        result = []
        for acc in accs:
            acc_name = self._get_entity_name(acc, acc_type)
            result.append(
                {
                    "account_id": acc,
                    "account_name": acc_name,
                    "group_id": gr.entity_id,
                    "group_name": gr.group_name,
                }
            )
        return result

    #
    # misc affiliations
    #
    all_commands['misc_affiliations'] = Command(
        ("misc", "affiliations"),
        fs=FormatSuggestion(
            "%-14s %-14s %s", ('aff', 'status', 'desc'),
            hdr="%-14s %-14s %s" % ('Affiliation', 'Status', 'Description')
        ))

    def misc_affiliations(self, operator):
        tmp = {}
        duplicate_check_list = list()
        for co in self.const.fetch_constants(self.const.PersonAffStatus):
            aff = text_type(co.affiliation)
            if aff not in tmp:
                tmp[aff] = [{'aff': aff,
                             'status': '',
                             'desc': co.affiliation.description}]
            status = text_type(co._get_status())
            if (aff, status) in duplicate_check_list:
                continue
            tmp[aff].append({
                'aff': '',
                'status': status,
                'desc': co.description,
            })
            duplicate_check_list.append((aff, status))
        # fetch_constants returns a list sorted according to the name
        # of the constant.  Since the name of the constant and the
        # affiliation status usually are kept related, the list for
        # each affiliation will tend to be sorted as well.  Not so for
        # the affiliations themselves.
        keys = tmp.keys()
        keys.sort()
        ret = []
        for k in keys:
            for r in tmp[k]:
                ret.append(r)
        return ret

    #
    # misc check_password <password>
    #
    all_commands['misc_check_password'] = Command(
        ("misc", "check_password"),
        AccountPassword(),
        fs=FormatSuggestion([
            ("%s", ('password_ok', )),
        ])
    )

    def misc_check_password(self, operator, password):
        ac = self.Account_class(self.db)
        try:
            check_password(password, ac, structured=False)
        except RigidPasswordNotGoodEnough as e:
            raise CerebrumError("Bad password: {}".format(e))
        except PhrasePasswordNotGoodEnough as e:
            raise CerebrumError("Bad passphrase: {}".format(e))
        except PasswordNotGoodEnough as e:
            raise CerebrumError("Bad password: {}".format(e))
        return {"password_ok": "Good password"}

    #
    # misc clear_passwords [uname]
    #
    all_commands['misc_clear_passwords'] = Command(
        ("misc", "clear_passwords"),
        AccountName(optional=True))

    def misc_clear_passwords(self, operator, account_name=None):
        operator.clear_state(state_types=('new_account_passwd', 'user_passwd'))
        return "OK, passwords cleared"

    #
    # misc dadd
    #
    all_commands['misc_dadd'] = Command(
        ("misc", "dadd"),
        SimpleString(help_ref='string_host'),
        DiskId(),
        perm_filter='can_create_disk')

    def misc_dadd(self, operator, hostname, diskname):
        host = self._get_host(hostname)
        self.ba.can_create_disk(operator.get_entity_id(), host)

        if not diskname.startswith("/"):
            raise CerebrumError("'%s' does not start with '/'" % diskname)

        if cereconf.VALID_DISK_TOPLEVELS is not None:
            toplevel_mountpoint = diskname.split("/")[1]
            if toplevel_mountpoint not in cereconf.VALID_DISK_TOPLEVELS:
                raise CerebrumError("'%s' is not a valid toplevel mountpoint"
                                    " for disks" % toplevel_mountpoint)

        disk = Utils.Factory.get('Disk')(self.db)
        disk.populate(host.entity_id, diskname, 'uio disk')
        try:
            disk.write_db()
        except self.db.DatabaseError as m:
            raise CerebrumError("Database error: %s" % exc_to_text(m))
        if len(diskname.split("/")) != 4:
            return "OK.  Warning: disk did not follow expected pattern."
        return "OK, added disk '%s' at %s" % (diskname, hostname)

    #
    # misc dls
    #
    # misc dls is deprecated, and can probably be removed without
    # anyone complaining much.
    #
    all_commands['misc_dls'] = Command(
        ("misc", "dls"),
        SimpleString(help_ref='string_host'),
        fs=FormatSuggestion(
            "%-8i %-8i %s", ("disk_id", "host_id", "path",),
            hdr="DiskId   HostId   Path"
        ))

    def misc_dls(self, operator, hostname):
        return self.disk_list(operator, hostname)

    #
    # disk list
    #
    all_commands['disk_list'] = Command(
        ("disk", "list"),
        SimpleString(help_ref='string_host'),
        fs=FormatSuggestion(
            "%-13s %11s  %s", ("hostname", "pretty_quota", "path",),
            hdr="Hostname    Default quota  Path"
        ))

    def disk_list(self, operator, hostname):
        host = self._get_host(hostname)
        disks = {}
        disk = Utils.Factory.get('Disk')(self.db)
        hquota = host.get_trait(self.const.trait_host_disk_quota)
        if hquota:
            hquota = hquota['numval']
        for row in disk.list(host.host_id):
            disk.clear()
            disk.find(row['disk_id'])
            dquota = disk.get_trait(self.const.trait_disk_quota)
            if dquota is None:
                def_quota = None
                pretty_quota = '<none>'
            else:
                if dquota['numval'] is None:
                    def_quota = hquota
                    if hquota is None:
                        pretty_quota = '(no default)'
                    else:
                        pretty_quota = '(%d MiB)' % def_quota
                else:
                    def_quota = dquota['numval']
                    pretty_quota = '%d MiB' % def_quota
            disks[row['disk_id']] = {'disk_id': row['disk_id'],
                                     'host_id': row['host_id'],
                                     'hostname': hostname,
                                     'def_quota': def_quota,
                                     'pretty_quota': pretty_quota,
                                     'path': row['path']}
        ret = []
        for d in sorted(disks, key=lambda k: disks[k]['path']):
            ret.append(disks[d])
        return ret

    #
    # disk quota <disk> <quota>
    #
    all_commands['disk_quota'] = Command(
        ("disk", "quota"),
        SimpleString(help_ref='string_host'),
        DiskId(),
        SimpleString(help_ref='disk_quota_set'),
        perm_filter='can_set_disk_default_quota',
    )

    def disk_quota(self, operator, hostname, diskname, quota):
        host = self._get_host(hostname)
        disk = self._get_disk(diskname, host_id=host.entity_id)[0]
        self.ba.can_set_disk_default_quota(operator.get_entity_id(),
                                           host=host, disk=disk)
        old = disk.get_trait(self.const.trait_disk_quota)
        if quota.lower() == 'none':
            if old:
                disk.delete_trait(self.const.trait_disk_quota)
            return "OK, no quotas on %s" % diskname
        elif quota.lower() == 'default':
            disk.populate_trait(self.const.trait_disk_quota,
                                numval=None)
            disk.write_db()
            return "OK, using host default on %s" % diskname
        elif quota.isdigit():
            disk.populate_trait(self.const.trait_disk_quota,
                                numval=int(quota))
            disk.write_db()
            return "OK, default quota on %s is %d" % (diskname, int(quota))
        else:
            raise CerebrumError("Invalid quota value '%s'" % quota)

    #
    # misc drem
    #
    all_commands['misc_drem'] = Command(
        ("misc", "drem"),
        SimpleString(help_ref='string_host'),
        DiskId(),
        perm_filter='can_remove_disk')

    def misc_drem(self, operator, hostname, diskname):
        host = self._get_host(hostname)
        self.ba.can_remove_disk(operator.get_entity_id(), host)
        disk = self._get_disk(diskname, host_id=host.entity_id)[0]
        # FIXME: We assume that all destination_ids are entities,
        # which would ensure that the disk_id number can't represent a
        # different kind of entity.  The database does not constrain
        # this, however.
        br = BofhdRequests(self.db, self.const)
        if br.get_requests(destination_id=disk.entity_id):
            raise CerebrumError("There are pending requests. Use "
                                "'misc list_requests disk %s' to view "
                                "them." % diskname)
        account = self.Account_class(self.db)
        for row in account.list_account_home(disk_id=disk.entity_id,
                                             filter_expired=False):
            if row['disk_id'] is None:
                continue
            if row['status'] == int(self.const.home_status_on_disk):
                raise CerebrumError("One or more users still on disk "
                                    "(e.g. %s)" % row['entity_name'])
            account.clear()
            account.find(row['account_id'])
            ah = account.get_home(row['home_spread'])
            account.set_homedir(
                current_id=ah['homedir_id'], disk_id=None,
                home=account.resolve_homedir(disk_path=row['path'],
                                             home=row['home']))
        self._remove_auth_target("disk", disk.entity_id)
        try:
            disk.delete()
        except self.db.DatabaseError as m:
            raise CerebrumError("Database error: %s" % exc_to_text(m))
        return "OK, %s deleted" % diskname

    #
    # misc hadd
    #
    all_commands['misc_hadd'] = Command(
        ("misc", "hadd"),
        SimpleString(help_ref='string_host'),
        perm_filter='can_create_host')

    def misc_hadd(self, operator, hostname):
        self.ba.can_create_host(operator.get_entity_id())
        host = Utils.Factory.get('Host')(self.db)
        host.populate(hostname, 'uio host')
        try:
            host.write_db()
        except self.db.DatabaseError as m:
            raise CerebrumError("Database error: %s" % exc_to_text(m))
        return "OK, added host '%s'" % hostname

    #
    # misc hrem
    #
    all_commands['misc_hrem'] = Command(
        ("misc", "hrem"),
        SimpleString(help_ref='string_host'),
        perm_filter='can_remove_host')

    def misc_hrem(self, operator, hostname):
        self.ba.can_remove_host(operator.get_entity_id())
        host = self._get_host(hostname)
        self._remove_auth_target("host", host.host_id)
        try:
            host.delete()
        except self.db.DatabaseError as m:
            raise CerebrumError("Database error: %s" % exc_to_text(m))
        return "OK, %s deleted" % hostname

    #
    # See hack in list_command
    #
    all_commands['host_info'] = Command(
        ("host", "info"),
        SimpleString(help_ref='string_host'),
        fs=FormatSuggestion([
            ("Hostname:              %s\n" "Description:           %s",
             ("hostname", "desc")),
            ("Default disk quota:    %d MiB", ("def_disk_quota",))
        ]),
    )

    def host_info(self, operator, hostname):
        ret = []
        host = self._get_host(hostname)
        ret = {
            'hostname': hostname,
            'desc': host.description
        }
        hquota = host.get_trait(self.const.trait_host_disk_quota)
        if hquota and hquota['numval']:
            ret['def_disk_quota'] = hquota['numval']
        return ret

    #
    # host disk_quota <host> <quota>
    #
    all_commands['host_disk_quota'] = Command(
        ("host", "disk_quota"),
        SimpleString(help_ref='string_host'),
        SimpleString(help_ref='disk_quota_set'),
        perm_filter='can_set_disk_default_quota',
    )

    def host_disk_quota(self, operator, hostname, quota):
        host = self._get_host(hostname)
        self.ba.can_set_disk_default_quota(operator.get_entity_id(),
                                           host=host)
        old = host.get_trait(self.const.trait_host_disk_quota)
        if (quota.lower() == 'none' or
                quota.lower() == 'default' or
                (quota.isdigit() and int(quota) == 0)):
            # "default" doesn't make much sense, but the help text
            # says it's a valid value.
            if old:
                # TBD: disk is not defined here, what is this supposed to do?
                # disk.delete_trait(self.const.trait_disk_quota)
                raise Exception("does this ever happen?")
            return "OK, no default quota on %s" % hostname
        elif quota.isdigit() and int(quota) > 0:
            host.populate_trait(self.const.trait_host_disk_quota,
                                numval=int(quota))
            host.write_db()
            return "OK, default quota on %s is %d" % (hostname, int(quota))
        else:
            raise CerebrumError("Invalid quota value '%s'" % quota)
        pass

    def _remove_auth_target(self, target_type, target_id):
        """This function should be used whenever a potential target
        for authorisation is deleted.
        """
        ar = BofhdAuthRole(self.db)
        aot = BofhdAuthOpTarget(self.db)
        for r in aot.list(entity_id=target_id, target_type=target_type):
            aot.clear()
            aot.find(r['op_target_id'])
            # We remove all auth_role entries first so that there
            # are no references to this op_target_id, just in case
            # someone adds a foreign key constraint later.
            for role in ar.list(op_target_id=r["op_target_id"]):
                ar.revoke_auth(role['entity_id'],
                               role['op_set_id'],
                               r['op_target_id'])
            aot.delete()

    def _remove_auth_role(self, entity_id):
        """This function should be used whenever a potentially
        authorised entity is deleted.
        """
        ar = BofhdAuthRole(self.db)
        aot = BofhdAuthOpTarget(self.db)
        for r in ar.list(entity_id):
            ar.revoke_auth(entity_id, r['op_set_id'], r['op_target_id'])
            # Also remove targets if this was the last reference from
            # auth_role.
            remaining = ar.list(op_target_id=r['op_target_id'])
            if len(remaining) == 0:
                aot.clear()
                aot.find(r['op_target_id'])
                aot.delete()

    #
    # misc list_passwords
    #
    all_commands['misc_list_passwords'] = Command(
        ("misc", "list_passwords"),
        fs=FormatSuggestion(
            "%-8s %-20s %s", ("account_id", "operation", "password"),
            hdr="%-8s %-20s %s" % ("Id", "Operation", "Password")
        ))

    def misc_list_passwords(self, operator, *args):
        u""" List passwords in cache. """
        # NOTE: We keep the *args argument for backwards compability.
        cache = self._get_cached_passwords(operator)
        if not cache:
            raise CerebrumError("No passwords in session")
        return cache

    #
    # misc reload
    #
    all_commands['misc_reload'] = Command(
        ("misc", "reload"),
        perm_filter='is_superuser')

    def misc_reload(self, operator):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        self.server.read_config()
        return "OK, server-config reloaded"

    #
    # misc verify_password
    #
    all_commands['misc_verify_password'] = Command(
        ("misc", "verify_password"),
        AccountName(),
        AccountPassword(),
        perm_filter='can_verify_password')

    def misc_verify_password(self, operator, accountname, password):
        ac = self._get_account(accountname)
        self.ba.can_verify_password(operator.get_entity_id(), ac)
        if ac.verify_auth(password):
            return 'Password is correct'
        ph = PasswordHistory(self.db)
        name = ac.account_name
        for old_password in ph.get_history(ac.entity_id):
            if check_password_history(password, [old_password['hash']], name):
                return ("The password is obsolete, it was set on %s" %
                        old_password['set_at'])
        return "Incorrect password"

    #
    # person accounts
    #
    all_commands['person_accounts'] = Command(
        ("person", "accounts"),
        PersonId(),
        fs=FormatSuggestion(
            "%9i %-10s %s", ("account_id", "name", format_day("expire")),
            hdr=("%9s %-10s %s") % ("Id", "Name", "Expire")
        ))

    def person_accounts(self, operator, id):
        person = self.util.get_target(id, restrict_to=['Person', 'Group'])
        account = self.Account_class(self.db)
        ret = []
        for r in account.list_accounts_by_owner_id(
                person.entity_id,
                owner_type=person.entity_type,
                filter_expired=False):
            account = self._get_account(r['account_id'], idtype='id')
            ret.append({
                'account_id': r['account_id'],
                'name': account.account_name,
                'expire': account.expire_date,
            })
        ret.sort(key=lambda d: d['name'])
        return ret

    #
    # person affilation_add <person> <ou> <aff> <status> [force]
    #

    def _person_affiliation_add_helper(self, operator,
                                       person, ou, aff, aff_status,
                                       force=False, check=False):
        """
        Helper-function that implements person_affiliation_add.

        This is needed because *other* commands also need to set affiliations,
        and they in turn would have to implement the same sanity checks,
        permission checks, lookups, etc...

        :param person: a cerebrum person object to add the affiliation to
        :param ou: *stedkode* for a valid org unit to affiliate
        :param aff: textual affiliation code to use
        :param aff_status: textual affiliation status code to use
        :param force:
            add affiliation even if a similar affiliation already exists from
            another source system
        :param check:
            silently ignore and do nothing if a similar affiliation already
            exists

        :raises CerebrumError:
            If a conflicting affiliation exists, or if any of the given
            affiliation parameters are invalid.

        :raises PermissionDenied:
            This function performs the required permission checks
            (can_add_affiliation), and raises PermissionDenied if required.

        :rtype: tuple
        :returns: a tuple with the (ou, aff, status) that has been added
        """
        # lookups
        aff = self._get_affiliationid(aff)
        aff_status = self._get_affiliation_statusid(aff, aff_status)
        aff_source = self.const.system_manual
        ou = self._get_ou(stedkode=ou)
        ou_str = self._format_ou_name(ou)
        force = self._get_boolean(force)

        # Check if conflicting affiliations already exists
        for a in person.get_affiliations():
            a_source = self.const.AuthoritativeSystem(a['source_system'])
            a_status = self.const.PersonAffStatus(a['status'])
            if a['ou_id'] == ou.entity_id and a['affiliation'] == aff:
                if a_status == aff_status and a_source == aff_source:
                    # AFF/status@ou from source system manual already exists
                    if check:
                        # only checking - no update needed
                        break
                    raise CerebrumError(
                        "Person already has %s@%s from %s, no update needed"
                        % (text_type(aff_status), ou_str,
                           text_type(aff_source)))
                elif a_status == aff_status:
                    # AFF/status@ou from a *different* source system
                    if check and not force:
                        # only checking - no update needed
                        break
                    if not force:
                        raise CerebrumError(
                            "Person already has %s@%s from %s, force the "
                            "operation to add duplicate, manual aff"
                            % (text_type(aff_status), ou_str,
                               text_type(a_source)))
                elif a_source == aff_source:
                    # AFF/other-status@ou from source system *manual*
                    raise CerebrumError(
                        "Person already has %s@%s from %s, which must be "
                        "removed first"
                        % (text_type(a_status), ou_str, text_type(aff_source)))
        else:
            # no conflicing affs found, let's add it if we're allowed
            self.ba.can_add_affiliation(operator.get_entity_id(),
                                        person, ou, aff, aff_status)
            person.add_affiliation(ou.entity_id, aff, aff_source, aff_status)
            person.write_db()
        return ou, aff, aff_status

    all_commands['person_affiliation_add'] = Command(
        ("person", "affiliation_add"),
        PersonId(help_ref="person_id_other"),
        OU(),
        Affiliation(),
        AffiliationStatus(),
        YesNo(help_ref="yes_no_force", optional=True, default="No"),
        perm_filter='can_add_affiliation')

    def person_affiliation_add(self, operator, person_id, ou, aff, aff_status,
                               force=False):
        try:
            person = self._get_person(*self._map_person_id(person_id))
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")

        ou, aff, aff_status = self._person_affiliation_add_helper(
            operator, person, ou, aff, aff_status, force)

        return "OK, added %s@%s to %s" % (text_type(aff_status),
                                          self._format_ou_name(ou),
                                          person.entity_id)

    #
    # person affilation_remove <person> AFFILIATION[/status] [source]
    #
    all_commands['person_affiliation_remove'] = Command(
        ("person", "affiliation_remove"),
        PersonId(),
        OU(),
        Affiliation(),
        SourceSystem(help_ref="source_system", optional=True, default=None),
        fs=FormatSuggestion(
            "OK, removed %s@%s [%s] from person id:%d",
            ('status', 'ou_name', 'source_system', 'person_id')),
        perm_filter='can_remove_affiliation',
    )

    def person_affiliation_remove(self, operator, person_id, ou, affstr,
                                  sourcestr=None):
        try:
            person = self._get_person(*self._map_person_id(person_id))
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        ou = self._get_ou(stedkode=ou)
        try:
            affiliation, status = self.const.get_affiliation(affstr)
        except Errors.NotFoundError:
            raise CerebrumError("invalid affiliation: " + repr(affstr))
        if sourcestr is None:
            source_system = None
        else:
            try:
                source_system = self.const.get_constant(
                    self.const.AuthoritativeSystem, sourcestr)
            except Errors.NotFoundError:
                raise CerebrumError("invalid source system: "
                                    + repr(sourcestr))

        target_affs = [
            dict(row)
            for row in person.list_affiliations(
                person_id=int(person.entity_id),
                ou_id=int(ou.entity_id),
                affiliation=affiliation,
                status=status,
                source_system=source_system)]

        if not target_affs:
            raise CerebrumError("No matching affiliation")

        # check if operator has access to all target_affs
        operator_id = operator.get_entity_id()
        for row in target_affs:
            self.ba.can_remove_affiliation(operator=operator_id,
                                           person=person,
                                           ou=ou,
                                           affiliation=row['affiliation'],
                                           status=row['status'],
                                           source_system=row['source_system'])

        removed = []
        for row in target_affs:
            person.delete_affiliation(row['ou_id'],
                                      row['affiliation'],
                                      row['source_system'])
            removed.append({
                'person_id': int(row['person_id']),
                'ou_id': int(ou.entity_id),
                'ou_name': self._format_ou_name(ou),
                'affiliation': six.text_type(
                    self.const.PersonAffiliation(row['affiliation'])),
                'status': six.text_type(
                    self.const.PersonAffStatus(row['status'])),
                'source_system': six.text_type(
                    self.const.AuthoritativeSystem(row['source_system'])),
            })

        return removed

    #
    # person set_bdate
    #
    all_commands['person_set_bdate'] = Command(
        ("person", "set_bdate"),
        PersonId(help_ref="id:target:person"),
        # TODO: We should update the help text to include info from
        # parsers.parse_date_help_blurb
        Date(help_ref='date_birth'),
        perm_filter='can_set_person_info',
    )

    def person_set_bdate(self, operator, person_id, bdate):
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        self.ba.can_set_person_info(operator.get_entity_id(),
                                    person=person)
        bdate = parsers.parse_date(bdate)
        if bdate > datetime.date.today():
            raise CerebrumError("Please check the date of birth, "
                                "cannot register date_of_birth > now")
        person.birth_date = bdate
        person.write_db()
        return "OK, set birth date for '%s' = '%s'" % (person_id, bdate)

    # person set_name
    all_commands['person_set_name'] = Command(
        ("person", "set_name"), PersonId(help_ref="person_id_other"),
        PersonName(help_ref="person_name_first"),
        PersonName(help_ref="person_name_last"),
        fs=FormatSuggestion("Name altered for: %i", ("person_id",)),
        perm_filter='can_set_person_info')

    def person_set_name(self, operator, person_id, first_name, last_name):
        person = self._get_person(*self._map_person_id(person_id))
        self.ba.can_set_person_info(operator.get_entity_id(),
                                    person=person)

        if last_name == "":
            raise CerebrumError("Last name is required.")

        if first_name == "":
            full_name = last_name
        else:
            full_name = " ".join((first_name, last_name))

        person.affect_names(self.const.system_manual,
                            self.const.name_first,
                            self.const.name_last,
                            self.const.name_full)

        # If first_name is an empty string, it should remain unpopulated.
        # Since it is tagged as an affected name_variant above, this will
        # trigger the original name_variant-row in the db to be deleted when
        # running write_db.
        if first_name != "":
            person.populate_name(self.const.name_first, first_name)

        person.populate_name(self.const.name_last, last_name)
        person.populate_name(self.const.name_full, full_name)

        try:
            person.write_db()
        except self.db.DatabaseError as m:
            raise CerebrumError("Database error: %s" % exc_to_text(m))

        return {'person_id': person.entity_id}

    #
    # person name_suggestions
    #
    hidden_commands['person_name_suggestions'] = Command(
        ('person', 'name_suggestions'),
        PersonId(help_ref='person_id_other'))

    def person_name_suggestions(self, operator, person_id):
        """Return a list of names that the user can choose for himself. Each
        name could generate a different primary e-mail address, so this is also
        returned.

        The name varieties are generated:

        - The primary family name is used as a basis for all varieties.

        - All given names are then added in front of the family name. If the
          given name contains several names, all of these are added as a
          variety, e.g:

            family: Doe, given: John Robert
            varieties: John Doe, John Robert Doe, Robert Doe
        """
        person = self._get_person(*self._map_person_id(person_id))
        account = self._get_account(operator.get_entity_id(), idtype='id')
        if not (self.ba.is_superuser(operator.get_entity_id()) or
                account.owner_id == person.entity_id):
            raise CerebrumError('You can only get your own names')

        # get primary last name to use for basis
        last_name = None
        for sys in cereconf.SYSTEM_LOOKUP_ORDER:
            try:
                last_name = person.get_name(getattr(self.const, sys),
                                            self.const.name_last)
                if last_name:
                    break
            except Errors.NotFoundError:
                pass
        if not last_name:
            raise CerebrumError('Found no family name for person')

        def name_combinations(names):
            """Return all different combinations of given names, while keeping
            the order intact."""
            ret = []
            for i in range(len(names)):
                ret.append([names[i]])
                ret.extend([names[i]] + nxt
                           for nxt in name_combinations(names[i+1:]))
            return ret

        names = set()
        for sys in cereconf.SYSTEM_LOOKUP_ORDER:
            try:
                name = person.get_name(getattr(self.const, sys),
                                       self.const.name_first)
            except Errors.NotFoundError:
                continue
            names.update((tuple(n) + (last_name,))
                         for n in name_combinations(name.split(' ')))
        account.clear()

        uidaddr = True
        # TODO: what if person has no primary account?
        try:
            account.find(person.get_primary_account())
            ed = Email.EmailDomain(self.db)
            ed.find(account.get_primary_maildomain())
            domain = ed.email_domain_name
            uidaddr = not any(
                int(c['category']) == self.const.email_domain_category_cnaddr
                for c in ed.get_categories())
        except Errors.NotFoundError:
            domain = 'ulrik.uio.no'
        if uidaddr:
            return [(n, '%s@%s' % (account.account_name, domain))
                    for n in names]
        return [
            (n, '%s@%s' % (account.get_email_cn_given_local_part(' '.join(n)),
                           domain))
            for n in names]

    #
    # person create
    #
    all_commands['person_create'] = Command(
        ("person", "create"),
        PersonId(),
        Date(help_ref='date_birth'),
        PersonName(help_ref='person_name_first'),
        PersonName(help_ref='person_name_last'),
        OU(),
        Affiliation(),
        AffiliationStatus(),
        fs=FormatSuggestion("Created: %i", ("person_id",)),
        perm_filter='can_create_person')

    def person_create(self, operator,
                      person_id, bdate, person_name_first, person_name_last,
                      ou, affiliation, aff_status):
        stedkode = ou
        try:
            ou = self._get_ou(stedkode=ou)
        except Errors.NotFoundError:
            raise CerebrumError("Unknown OU (%s)" % ou)
        try:
            aff = self._get_affiliationid(affiliation)
        except Errors.NotFoundError:
            raise CerebrumError("Unknown affiliation type (%s)" % affiliation)
        self.ba.can_create_person(operator.get_entity_id(), ou, aff)
        person = Utils.Factory.get('Person')(self.db)
        person.clear()

        bdate = parsers.parse_date(bdate, optional=True)
        if bdate and bdate > datetime.date.today():
            raise CerebrumError("Please check the date of birth, "
                                "cannot register date_of_birth > now")
        if person_id:
            id_type, id = self._map_person_id(person_id)
        else:
            id_type = None
        gender = self.const.gender_unknown
        if id_type is not None and id:
            if id_type == self.const.externalid_fodselsnr:
                try:
                    if fodselsnr.er_mann(id):
                        gender = self.const.gender_male
                    else:
                        gender = self.const.gender_female
                except fodselsnr.InvalidFnrError as msg:
                    raise CerebrumError("Invalid birth-no: %s" %
                                        exc_to_text(msg))
                try:
                    person.find_by_external_id(self.const.externalid_fodselsnr,
                                               id)
                    raise CerebrumError("A person with that fnr exists")
                except Errors.TooManyRowsError:
                    raise CerebrumError("A person with that fnr exists")
                except Errors.NotFoundError:
                    pass
                person.clear()
                self._person_create_externalid_helper(person)
                person.populate_external_id(self.const.system_manual,
                                            self.const.externalid_fodselsnr,
                                            id)
            if id_type == self.const.externalid_pass_number:
                try:
                    person.find_by_external_id(
                        self.const.externalid_pass_number,
                        id)
                    raise CerebrumError("A person with that passnr exists")
                except Errors.TooManyRowsError:
                    raise CerebrumError("A person with that passnr exists")
                except Errors.NotFoundError:
                    pass
                person.clear()
                self._person_create_externalid_helper(person)
                person.populate_external_id(self.const.system_manual,
                                            self.const.externalid_pass_number,
                                            id)
        person.populate(bdate, gender, description='Manually created')
        person.affect_names(self.const.system_manual,
                            self.const.name_first,
                            self.const.name_last)
        person.populate_name(self.const.name_first, person_name_first)
        person.populate_name(self.const.name_last, person_name_last)
        person.write_db()
        self._person_affiliation_add_helper(operator, person, stedkode,
                                            text_type(aff), aff_status)
        return {'person_id': person.entity_id}

    def _person_create_externalid_helper(self, person):
        person.affect_external_id(self.const.system_manual,
                                  self.const.externalid_fodselsnr)

    #
    # person find
    #
    all_commands['person_find'] = Command(
        ("person", "find"),
        PersonSearchType(),
        SimpleString(),
        SimpleString(optional=True, help_ref="affiliation_optional"),
        fs=FormatSuggestion(
            "%7i   %10s   %-12s  %s",
            ('id', 'birth', 'account', 'name'),
            hdr="%7s   %10s   %-12s  %s" %
            ('Id', 'Birth', 'Account', 'Name')
        ),
        perm_filter='can_view_person')

    def person_find(self, operator, search_type, value, filter=None):
        self.ba.can_view_person(operator.get_entity_id(), person=None)
        # TODO: Need API support for this
        matches = []
        idcol = 'person_id'
        if filter is not None:
            try:
                filter = int(self.const.PersonAffiliation(filter))
            except Errors.NotFoundError:
                raise CerebrumError("Invalid affiliation %r (perhaps you "
                                    "need to quote the arguments?)" % filter)
        person = Utils.Factory.get('Person')(self.db)
        person.clear()
        extids = {
            'passnr': 'externalid_pass_number',
            'studnr': 'externalid_studentnr',
            'sapnr':  'externalid_sap_ansattnr',
            'dfo_pid':  'externalid_dfo_pid',
            # fnr is excluded on purpose, to avoid exploitations
        }
        search_type = search_type.lower()
        if search_type == 'name':
            if filter is not None:
                raise CerebrumError("Can't filter by affiliation "
                                    "for search type 'name'")
            if len(value.strip(" \t%_*?")) < 3:
                raise CerebrumError("You must specify at least three "
                                    "letters of the name")
            matches = person.search_person_names(
                name=value,
                name_variant=self.const.name_full,
                source_system=self.const.system_cached,
                exact_match=False,
                case_sensitive=(value != value.lower()))
        elif search_type in extids:
            idtype = getattr(self.const, extids[search_type], None)
            if idtype:
                matches = person.search_external_ids(
                    id_type=idtype,
                    external_id=value,
                    fetchall=False)
                idcol = 'entity_id'
            else:
                raise CerebrumError("Unknown search type (%s)" % search_type)
        elif search_type == 'date':
            date_of_birth = parsers.parse_date(value)
            matches = person.find_persons_by_bdate(date_of_birth)
        elif search_type == 'stedkode':
            ou = self._get_ou(stedkode=value)
            matches = person.list_affiliations(ou_id=ou.entity_id,
                                               affiliation=filter)
        elif search_type == 'ou':
            if not value.isdigit():
                raise CerebrumError("Expected OU as entity id. Got: {}"
                                    .format(value))
            else:
                ou = self._get_ou(ou_id=value)
            matches = person.list_affiliations(ou_id=ou.entity_id,
                                               affiliation=filter)
        else:
            raise CerebrumError("Unknown search type (%s)" % search_type)
        ret = []
        seen = {}
        acc = self.Account_class(self.db)
        # matches may be an iterator, so force it into a list so we
        # can count the entries.
        matches = list(matches)
        if len(matches) > cereconf.BOFHD_MAX_MATCHES:
            raise CerebrumError("More than %d (%d) matches, please narrow "
                                "search criteria" %
                                (cereconf.BOFHD_MAX_MATCHES, len(matches)))
        for row in matches:
            # We potentially get multiple rows for a person when
            # s/he has more than one source system or affiliation.
            p_id = row[idcol]
            if p_id in seen:
                continue
            seen[p_id] = True
            person.clear()
            person.find(p_id)
            if 'name' in row:
                pname = row['name']
            else:
                try:
                    pname = person.get_name(
                        self.const.system_cached,
                        getattr(self.const, cereconf.DEFAULT_GECOS_NAME))
                except Errors.NotFoundError:
                    # Oh well, we don't know person's name
                    pname = '<none>'

            # Person.get_primary_account will not return expired
            # users.  Account.get_account_types will return the
            # accounts ordered by priority, but the highest priority
            # might be expired.
            account_name = "<none>"
            for row in acc.get_account_types(owner_id=p_id,
                                             filter_expired=False):
                acc.clear()
                acc.find(row['account_id'])
                account_name = acc.account_name
                if not acc.is_expired():
                    break

            # Ideally we'd fetch the authoritative last name, but
            # it's a lot of work.  We cheat and use the last word
            # of the name, which should work for 99.9% of the users.
            ret.append({
                'id': p_id,
                'birth': date_to_string(person.birth_date),
                'export_id': person.export_id,
                'account': account_name,
                'name': pname,
                'lastname': pname.split(" ")[-1],
            })
        ret.sort(key=lambda d: (d['lastname'], d['name']))
        return ret

    #
    # person info
    #
    all_commands['person_info'] = Command(
        ("person", "info"),
        PersonId(help_ref="id:target:person"),
        fs=FormatSuggestion([
            ("Name:          %s\n"
             "Entity-id:     %i\n"
             "Birth:         %s\n"
             "Spreads:       %s", ("name", "entity_id", "birth", "spreads")),
            ("Affiliations:  %s [from %s]", ("affiliation_1",
                                             "source_system_1")),
            ("               %s [from %s]", ("affiliation", "source_system")),
            ("Names:         %s [from %s]", ("names", "name_src")),
            ("Contact:       %s: %s [from %s]", ("contact_type", "contact",
                                                 "contact_src")),
            ("External id:   %s [from %s]", ("extid", "extid_src"))
        ]),
        perm_filter='can_view_person')

    def person_info(self, operator, person_id):
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        self.ba.can_view_person(operator.get_entity_id(), person)
        try:
            p_name = person.get_name(
                self.const.system_cached,
                getattr(self.const, cereconf.DEFAULT_GECOS_NAME))
            p_name = p_name + ' [from Cached]'
        except Errors.NotFoundError:
            p_name = None
        data = [{
            'name': p_name,
            'entity_id': person.entity_id,
            'birth': date_to_string(person.birth_date),
            'spreads': ", ".join([text_type(self.const.Spread(x['spread']))
                                  for x in person.get_spread()]),
        }]
        affiliations = []
        sources = []
        for row in person.get_affiliations():
            ou = self._get_ou(ou_id=row['ou_id'])
            affiliations.append("%s@%s" % (
                text_type(self.const.PersonAffStatus(row['status'])),
                self._format_ou_name(ou)))
            sources.append(
                text_type(
                    self.const.AuthoritativeSystem(row['source_system'])))
        for ss in cereconf.SYSTEM_LOOKUP_ORDER:
            ss = getattr(self.const, ss)
            person_name = ""
            for t in [self.const.name_first, self.const.name_last]:
                try:
                    person_name += person.get_name(ss, t) + ' '
                except Errors.NotFoundError:
                    continue
            if person_name:
                data.append({
                    'names': person_name,
                    'name_src': text_type(self.const.AuthoritativeSystem(ss)),
                })
        if affiliations:
            data[0]['affiliation_1'] = affiliations[0]
            data[0]['source_system_1'] = sources[0]
        else:
            data[0]['affiliation_1'] = "<none>"
            data[0]['source_system_1'] = "<nowhere>"
        for i in range(1, len(affiliations)):
            data.append({'affiliation': affiliations[i],
                         'source_system': sources[i]})

        # Add external ids
        viewable_external_ids = self._viewable_external_ids(operator, person)
        for ext_id in viewable_external_ids:
            data.append(
                {
                    'extid': text_type(self.const.EntityExternalId(
                        ext_id['id_type'])),
                    'extid_src': text_type(self.const.AuthoritativeSystem(
                        ext_id['source_system']))
                }
            )

        # Show contact info, if permission checks are implemented
        if hasattr(self.ba, 'can_get_contact_info'):
            # Hacky - not all deployments have all contact types...
            wants = set(
                getattr(self.const, attr)
                for attr in (
                    'contact_phone',
                    'contact_voip_extension',
                    'contact_mobile_phone',
                    'contact_phone_private',
                    'contact_private_mobile',
                ) if hasattr(self.const, attr))

            for row in person.get_contact_info():
                contact_type = self.const.ContactInfo(row['contact_type'])
                if contact_type not in wants:
                    continue
                try:
                    if self.ba.can_get_contact_info(
                            operator.get_entity_id(),
                            entity=person,
                            contact_type=contact_type):
                        data.append({
                            'contact': row['contact_value'],
                            'contact_src': text_type(
                                self.const.AuthoritativeSystem(
                                    row['source_system'])),
                            'contact_type': text_type(contact_type),
                        })
                except PermissionDenied:
                    continue
        return data

    # person get_id
    all_commands['person_get_id'] = Command(
        ("person", "get_id"),
        PersonId(help_ref="person_id"),
        ExternalIdType(),
        SourceSystem(help_ref="source_system"),
        fs=FormatSuggestion([
            ("ID %s for person %s (entity_id: %d) in %s: %s",
             ("ext_id_type", "person_name", "person_id",
              "source_system", "ext_id_value"))
        ]))

    def person_get_id(self, operator, person_id, ext_id_type, source_system):
        """
        Returns an external id value for a person according to the specified
        source system. The command/function only returns one ID instead of all
        IDs for a person entity in order to limit the exposure of sensitive
        personal info to the bare minimum.
        """
        ext_id_const = self._get_constant(self.const.EntityExternalId,
                                          ext_id_type, 'external id')
        ss_const = self._get_constant(self.const.AuthoritativeSystem,
                                      source_system, 'source system')
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        self.ba.can_get_external_id(
            operator, person, ext_id_type, source_system)
        external_id_list = person.get_external_id(
            id_type=ext_id_const,
            source_system=ss_const)
        if external_id_list:
            ext_id_value = external_id_list[0]['external_id']
            return [{
                "ext_id_type": text_type(ext_id_const),
                "person_name": text_type(person),
                "person_id": person.entity_id,
                "source_system": text_type(ss_const),
                "ext_id_value": ext_id_value,
            }]
        else:
            raise CerebrumError(
                "Could not find id %s for person entity %d in system %s" %
                (text_type(ext_id_const), person.entity_id,
                 text_type(source_system)))

    #
    # person set_id
    #
    all_commands['person_set_id'] = Command(
        ("person", "set_id"),
        PersonId(help_ref="person_id:current"),
        PersonId(help_ref="person_id:new"),
        SourceSystem(help_ref="source_system"))

    def person_set_id(self, operator, current_id, new_id, source_system):
        person = self._get_person(*self._map_person_id(current_id))
        idtype, id = self._map_person_id(new_id)
        self.ba.can_set_person_id(operator.get_entity_id(), person, idtype)
        if not source_system:
            ss = self.const.system_manual
        else:
            ss = int(self.const.AuthoritativeSystem(source_system))
        person.affect_external_id(ss, idtype)
        person.populate_external_id(ss, idtype, id)
        person.write_db()
        return "OK, set '%s' as new id for '%s'" % (new_id, current_id)

    #
    # person clear_id
    #
    all_commands['person_clear_id'] = Command(
        ("person", "clear_id"),
        PersonId(),
        SourceSystem(help_ref="source_system"),
        ExternalIdType(),
        perm_filter='is_superuser')

    def person_clear_id(self, operator, person_id, source_system, idtype):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        person = self.util.get_target(person_id, restrict_to="Person")
        ss = self.const.AuthoritativeSystem(source_system)
        try:
            int(ss)
        except Errors.NotFoundError:
            raise CerebrumError("No such source system")

        idtype = self.const.EntityExternalId(idtype)
        try:
            int(idtype)
        except Errors.NotFoundError:
            raise CerebrumError("No such external id")

        try:
            person._delete_external_id(ss, idtype)
        except Exception:
            raise CerebrumError("Could not delete id %s:%s for %s" %
                                (text_type(idtype), text_type(ss), person_id))
        return "OK"

    #
    # person clear_name
    #
    all_commands['person_clear_name'] = Command(
        ("person", "clear_name"),
        PersonId(help_ref="person_id_other"),
        SourceSystem(help_ref="source_system"),
        perm_filter='can_clear_name')

    def person_clear_name(self, operator, person_id, source_system):
        person = self.util.get_target(person_id, restrict_to="Person")
        ss = self.const.AuthoritativeSystem(source_system)
        try:
            int(ss)
        except Errors.NotFoundError:
            raise CerebrumError("No such source system")
        self.ba.can_clear_name(operator.get_entity_id(), person=person,
                               source_system=ss)
        removed = False
        for variant in (self.const.name_first, self.const.name_last,
                        self.const.name_full):
            try:
                person.get_name(ss, variant)
            except Errors.NotFoundError:
                continue
            try:
                person._delete_name(ss, variant)
            except Exception:
                raise CerebrumError("Could not delete %s from %s" %
                                    (text_type(variant).lower(),
                                     text_type(ss)))
            removed = True
        person._update_cached_names()
        if not removed:
            return ("No name to remove for %s from %s" %
                    (person_id, text_type(ss)))
        return "Removed name for %s from %s" % (person_id, text_type(ss))

    #
    # person student_info
    #
    all_commands['person_student_info'] = Command(
        ("person", "student_info"),
        PersonId(),
        fs=FormatSuggestion([
            ("Studieprogrammer: %s, %s, %s, %s, tildelt=%s->%s privatist: %s",
             ("studprogkode", "studieretningkode", "studierettstatkode",
              "studentstatkode", format_day("dato_tildelt"),
              format_day("dato_gyldig_til"), "privatist")),
            ("Eksamensmeldinger: %s (%s), %s",
             ("ekskode", "programmer", format_day("dato"))),
            ("Underv.meld: %s, %s",
             ("undvkode", format_day("dato"))),
            ("Utd. plan: %s, %s, %d, %s",
             ("studieprogramkode", "terminkode_bekreft", "arstall_bekreft",
              format_day("dato_bekreftet"))),
            ("Semesterregistrert: %s - %s, %s, %d, registrert: %s, endret: %s",
             ("regstatus", "regformkode", "terminkode", "arstall",
              format_day("dato_endring"), format_day("dato_regform_endret"))),
            ("Semesterbetaling: %s - %s, %s, %d, betalt: %s",
             ("betstatus", "betformkode", "terminkode", "arstall",
              format_day('dato_betaling'))),
            ("Registrert med status_dod: %s",
             ("status_dod",)),
        ]),
        perm_filter='can_get_student_info')

    def person_student_info(self, operator, person_id):
        person_exists = False
        person = None
        try:
            person = self._get_person(*self._map_person_id(person_id))
            person_exists = True
        except CerebrumError as e:
            # Check if person exists in FS, but is not imported yet, e.g.
            # emnestudents. These should only be listed with limited
            # information.
            if person_id and len(person_id) == 11 and person_id.isdigit():
                try:
                    person_id = fodselsnr.personnr_ok(person_id)
                except Exception:
                    raise e
                self.logger.debug('Unknown person %r, asking FS directly',
                                  person_id)
                self.ba.can_get_student_info(operator.get_entity_id(), None)
                fodselsdato, pnum = person_id[:6], person_id[6:]
            else:
                raise e
        else:
            self.ba.can_get_student_info(operator.get_entity_id(), person)
            fnr = person.get_external_id(
                id_type=self.const.externalid_fodselsnr,
                source_system=self.const.system_fs)
            if not fnr:
                raise CerebrumError("No matching fnr from FS")
            fodselsdato, pnum = fodselsnr.del_fnr(fnr[0]['external_id'])
        ret = []
        try:
            db = database.connect(user=cereconf.FS_USER,
                                  service=cereconf.FS_DATABASE_NAME,
                                  DB_driver=cereconf.DB_DRIVER_ORACLE)
        except database.DatabaseError as e:
            self.logger.warn("Can't connect to FS (%s)", text_type(e))
            raise CerebrumError("Can't connect to FS, try later")
        fs = FS(db)
        for row in fs.student.get_undervisningsmelding(fodselsdato, pnum):
            ret.append({
                'undvkode': row['emnekode'],
                'dato': row['dato_endring'],
            })

        har_opptak = set()
        if person_exists:
            for row in fs.student.get_studierett(fodselsdato, pnum):
                har_opptak.add(row['studieprogramkode'])
                ret.append({
                    'studprogkode': row['studieprogramkode'],
                    'studierettstatkode': row['studierettstatkode'],
                    'studentstatkode': row['studentstatkode'],
                    'studieretningkode': row['studieretningkode'],
                    'dato_tildelt': row['dato_studierett_tildelt'],
                    'dato_gyldig_til': row['dato_studierett_gyldig_til'],
                    'privatist': row['status_privatist'],
                })

            for row in fs.student.get_eksamensmeldinger(fodselsdato, pnum):
                programmer = []
                for row2 in fs.info.get_emne_i_studieprogram(row['emnekode']):
                    if row2['studieprogramkode'] in har_opptak:
                        programmer.append(row2['studieprogramkode'])
                ret.append({
                    'ekskode': row['emnekode'],
                    'programmer': ",".join(programmer),
                    'dato': row['dato_opprettet'],
                })

            for row in fs.student.get_utdanningsplan(fodselsdato, pnum):
                ret.append({
                    'studieprogramkode': row['studieprogramkode'],
                    'terminkode_bekreft': row['terminkode_bekreft'],
                    'arstall_bekreft': row['arstall_bekreft'],
                    'dato_bekreftet': row['dato_bekreftet'],
                })

            def _ok_or_not(input):
                """Helper function for proper feedback of status."""
                if not input or input == 'N':
                    return 'Nei'
                if input == 'J':
                    return 'Ja'
                return input

            semregs = tuple(fs.student.get_semreg(fodselsdato, pnum,
                                                  only_valid=False))
            for row in semregs:
                ret.append({
                    'regstatus': _ok_or_not(row['status_reg_ok']),
                    'regformkode': row['regformkode'],
                    'dato_endring': row['dato_endring'],
                    'dato_regform_endret': row['dato_regform_endret'],
                    'arstall': row['arstall'],
                    'terminkode': row['terminkode'],
                })
                ret.append({
                    'betstatus': _ok_or_not(row['status_bet_ok']),
                    'betformkode': row['betformkode'],
                    'dato_betaling': row['dato_betaling'],
                    'arstall': row['arstall'],
                    'terminkode': row['terminkode'],
                })
            # The semreg and sembet lines should always be sent, to make it
            # easier for the IT staff to see if a student have paid or not.
            if not semregs:
                ret.append({
                    'regstatus': 'Nei',
                    'regformkode': None,
                    'dato_endring': None,
                    'dato_regform_endret': None,
                    'arstall': fs.student.year,
                    'terminkode': fs.student.semester,
                })
                ret.append({
                    'betstatus': 'Nei',
                    'betformkode': None,
                    'dato_betaling': None,
                    'arstall': fs.student.year,
                    'terminkode': fs.student.semester,
                })

            # Check if anything is registered for next semester
            semreg_next_sem = tuple(fs.student.get_semreg(
                fodselsdato, pnum, only_valid=False, semester='next'))
            for row in semreg_next_sem:
                ret.append({
                    'regstatus': _ok_or_not(row['status_reg_ok']),
                    'regformkode': row['regformkode'],
                    'dato_endring': row['dato_endring'],
                    'dato_regform_endret': row['dato_regform_endret'],
                    'arstall': row['arstall'],
                    'terminkode': row['terminkode'],
                })
                ret.append({
                    'betstatus': _ok_or_not(row['status_bet_ok']),
                    'betformkode': row['betformkode'],
                    'dato_betaling': row['dato_betaling'],
                    'arstall': row['arstall'],
                    'terminkode': row['terminkode'],
                })

            if not semreg_next_sem:
                ret.append({
                    'regstatus': 'Nei',
                    'regformkode': None,
                    'dato_endring': None,
                    'dato_regform_endret': None,
                    'arstall': fs.student.next_semester_year,
                    'terminkode': fs.student.next_semester,
                })
                ret.append({
                    'betstatus': 'Nei',
                    'betformkode': None,
                    'dato_betaling': None,
                    'arstall': fs.student.next_semester_year,
                    'terminkode': fs.student.next_semester,
                })

        db.close()
        return ret

    #
    # person user_priority
    #
    all_commands['person_set_user_priority'] = Command(
        ("person", "set_user_priority"),
        AccountName(),
        SimpleString(help_ref='string_old_priority'),
        SimpleString(help_ref='string_new_priority'))

    def person_set_user_priority(self, operator,
                                 account_name, old_priority, new_priority):
        account = self._get_account(account_name)
        if not account.owner_type == self.const.entity_person:
            raise CerebrumError("Not a personal account")
        self.ba.can_set_person_user_priority(operator.get_entity_id(), account)
        try:
            old_priority = int(old_priority)
            new_priority = int(new_priority)
        except (ValueError, TypeError):
            raise CerebrumError("priority must be a number")
        ou = None
        affiliation = None
        for row in account.get_account_types(filter_expired=False):
            if row['priority'] == old_priority:
                ou = row['ou_id']
                affiliation = row['affiliation']
        if ou is None:
            raise CerebrumError("Must specify an existing priority")
        account.set_account_type(ou, affiliation, new_priority)
        account.write_db()
        return "OK, set priority=%i for %s" % (new_priority, account_name)

    #
    # person list_user_priorities
    #
    all_commands['person_list_user_priorities'] = Command(
        ("person", "list_user_priorities"),
        PersonId(),
        fs=FormatSuggestion(
            "%8s %8i %30s %15s",
            ('uname', 'priority', 'affiliation', 'status'),
            hdr="%8s %8s %30s %15s" %
            ("Uname", "Priority", "Affiliation", "Status")
        ))

    def person_list_user_priorities(self, operator, person_id):
        ac = Utils.Factory.get('Account')(self.db)
        person = self._get_person(*self._map_person_id(person_id))
        ret = []
        for row in ac.get_account_types(all_persons_types=True,
                                        owner_id=person.entity_id,
                                        filter_expired=False):
            ac2 = self._get_account(row['account_id'], idtype='id')
            if ac2.is_expired() or ac2.is_deleted():
                status = "Expired"
            else:
                status = "Active"
            ou = self._get_ou(ou_id=row['ou_id'])
            ret.append({
                'uname': ac2.account_name,
                'priority': row['priority'],
                'affiliation': '%s@%s' % (
                    text_type(
                        self.const.PersonAffiliation(row['affiliation'])),
                    self._format_ou_name(ou)),
                'status': status,
            })
        return ret

    def _get_posix_account(self, account_id):
        """Helper function to try getting a PosixUser-object from an
        Account-id. Ideally this should be doable from self._get_entity,
        and it would probably be reasonable to make PosixUser the default
        object type to return if the PosixUser-module is used in an instance.

        @param account_id: int
        @return: a PosixUser object or None
        """
        try:
            pu = Utils.Factory.get('PosixUser')(self.db)
        except ValueError:
            return None
        else:
            try:
                pu.find(account_id)
            except Errors.NotFoundError:
                return None
            else:
                return pu

    #
    # spread add
    #
    all_commands['spread_add'] = Command(
        ("spread", "add"),
        EntityType(default='account'),
        Id(),
        Spread(),
        perm_filter='can_add_spread')

    def spread_add(self, operator, entity_type, id, spread):
        entity = self._get_entity(entity_type, id)
        spread = self._get_constant(self.const.Spread, spread, "spread")
        self.ba.can_add_spread(operator.get_entity_id(), entity, spread)

        if entity.entity_type != spread.entity_type:
            raise CerebrumError(
                "Spread '%s' is restricted to '%s', selected entity is '%s'" %
                (text_type(spread),
                 text_type(self.const.EntityType(spread.entity_type)),
                 text_type(self.const.EntityType(entity.entity_type))))
        # exchange-relatert-jazz
        # NB! no checks are implemented in the group-mixin
        # as we want to let other clients handle these spreads
        # in different manner if needed
        # dissallow spread-setting for distribution groups
        if (cereconf.EXCHANGE_GROUP_SPREAD and
                text_type(spread) == cereconf.EXCHANGE_GROUP_SPREAD):
            raise CerebrumError("Please create distribution group via "
                                "'group exchange_create'")
        if entity_type == 'account':
            pu = self._get_posix_account(entity.entity_id)
            entity = pu if pu is not None else entity
        if entity.has_spread(spread):
            raise CerebrumError("entity id=%s already has spread=%s" %
                                (id, text_type(spread)))
        try:
            entity.add_spread(spread)
        except (Errors.RequiresPosixError, self.db.IntegrityError) as e:
            raise CerebrumError(exc_to_text(e))
        entity.write_db()
        if hasattr(self.const, 'spread_uio_nis_fg'):
            if (entity_type == 'group' and
                    spread == self.const.spread_uio_nis_fg):
                ad_spread = self.const.spread_uio_ad_group
                if not entity.has_spread(ad_spread):
                    entity.add_spread(ad_spread)
                    entity.write_db()
        return "OK, added spread %s for %s" % (
            text_type(spread), self._get_name_from_object(entity))

    #
    # spread list
    #
    all_commands['spread_list'] = Command(
        ("spread", "list"),
        fs=FormatSuggestion(
            "%-14s %s", ('name', 'desc'),
            hdr="%-14s %s" % ('Name', 'Description')
        ))

    def spread_list(self, operator):
        """
        List out all available spreads.
        """
        ret = []
        spr = Entity.EntitySpread(self.db)
        autospreads = [self.const.human2constant(x, self.const.Spread)
                       for x in getattr(cereconf, 'GROUP_REQUESTS_AUTOSPREADS',
                                        ())]
        for s in spr.list_spreads():
            ret.append({
                'name': s['spread'],
                'desc': s['description'],
                'type': s['entity_type_str'],
                'type_id': s['entity_type'],
                'spread_code': s['spread_code'],
                # int() since boolean doesn't work for brukerinfo:
                'auto': int(s['spread_code'] in autospreads),
            })
        return ret

    #
    # spread remove
    #
    all_commands['spread_remove'] = Command(
        ("spread", "remove"),
        EntityType(default='account'),
        Id(),
        Spread(),
        perm_filter='can_add_spread')

    def spread_remove(self, operator, entity_type, id, spread):
        entity = self._get_entity(entity_type, id)
        spread = self._get_constant(self.const.Spread, spread, "spread")
        self.ba.can_add_spread(operator.get_entity_id(), entity, spread)
        # exchange-relatert-jazz
        # make sure that if anyone uses spread remove instead of
        # group exchange_remove the appropriate clean-up is still
        # done
        if (entity_type == 'group' and
                entity.has_spread(cereconf.EXCHANGE_GROUP_SPREAD)):
            raise CerebrumError(
                "Cannot remove spread from distribution groups")
        if entity_type == 'account':
            pu = self._get_posix_account(entity.entity_id)
            entity = pu if pu is not None else entity
        if entity.has_spread(spread):
            entity.delete_spread(spread)
        else:
            txt = "Entity '%s' does not have spread '%s'" % (id,
                                                             text_type(spread))
            raise CerebrumError(txt)
        return "OK, removed spread %s from %s" % (
            text_type(spread), self._get_name_from_object(entity))

    #
    # user affiliation_add
    #
    all_commands['user_affiliation_add'] = Command(
        ("user", "affiliation_add"),
        AccountName(help_ref='account_name_id_uid'),
        OU(),
        Affiliation(),
        AffiliationStatus(),
        perm_filter='can_add_account_type')

    def user_affiliation_add(self, operator, accountname, ou, aff, aff_status):
        account = self._get_account(accountname)
        person = self._get_person('entity_id', account.owner_id)
        ou, aff, aff_status = self._person_affiliation_add_helper(
            operator, person, ou, aff, aff_status, check=True)
        self.ba.can_add_account_type(operator.get_entity_id(), account,
                                     ou, aff, aff_status)
        account.set_account_type(ou.entity_id, aff)

        # When adding an affiliation manually, make sure the user gets
        # the e-mail addresses associated with it automatically.  To
        # achieve this, we temporarily change the priority to 1 and
        # call write_db.  This will displace an existing priority 1 if
        # there is one, but it's not worthwhile to do this perfectly.
        for row in account.get_account_types(filter_expired=False):
            if row['ou_id'] == ou.entity_id and row['affiliation'] == aff:
                priority = row['priority']
                break
        account.set_account_type(ou.entity_id, aff, 1)
        account.write_db()
        account.set_account_type(ou.entity_id, aff, priority)
        account.write_db()
        return "OK, added %s@%s to %s" % (text_type(aff),
                                          self._format_ou_name(ou),
                                          accountname)

    #
    # user affiliation_remove
    #
    all_commands['user_affiliation_remove'] = Command(
        ("user", "affiliation_remove"),
        AccountName(),
        OU(),
        Affiliation(),
        perm_filter='can_remove_account_type')

    def user_affiliation_remove(self, operator, accountname, ou, aff):
        account = self._get_account(accountname)
        aff = self._get_affiliationid(aff)
        ou = self._get_ou(stedkode=ou)
        self.ba.can_remove_account_type(operator.get_entity_id(),
                                        account, ou, aff)
        account.del_account_type(ou.entity_id, aff)
        account.write_db()
        return "OK, removed %s@%s from %s" % (text_type(aff),
                                              self._format_ou_name(ou),
                                              accountname)

    def _user_create_prompt_func(self, session, *args):
        """A prompt_func on the command level should return
        {'prompt': message_string, 'map': dict_mapping}
        - prompt is simply shown.
        - map (optional) maps the user-entered value to a value that
          is returned to the server, typically when user selects from
          a list."""
        all_args = list(args[:])

        if not all_args:
            return {'prompt': 'Person identification',
                    'help_ref': 'user_create_person_id'}
        arg = all_args.pop(0)
        if not all_args:
            c = self._find_persons(arg)
            person_map = [(('%-8s %s', 'Id', 'Name'), None)]
            for i in range(len(c)):
                person = self._get_person('entity_id', c[i]['person_id'])
                person_map.append((
                    ('%8i %s', int(c[i]['person_id']),
                     person.get_name(self.const.system_cached,
                                     self.const.name_full)),
                    int(c[i]['person_id'])))
            if not len(person_map) > 1:
                raise CerebrumError('No persons matched')
            return {'prompt': 'Choose person from list',
                    'map': person_map,
                    'help_ref': 'user_create_select_person'}
        owner_id = all_args.pop(0)
        person = self._get_person('entity_id', owner_id)
        existing_accounts = []
        account = self.Account_class(self.db)
        for r in account.list_accounts_by_owner_id(person.entity_id):
            account = self._get_account(r['account_id'], idtype='id')
            expire_date = date_compat.get_date(account.expire_date)
            if expire_date:
                exp = expire_date.isoformat()
            else:
                exp = '<not set>'
            existing_accounts.append('%-10s %s' % (account.account_name, exp))
        if existing_accounts:
            existing_accounts = 'Existing accounts:\n%-10s %s\n%s\n' % (
                'uname', 'expire', '\n'.join(existing_accounts))
        else:
            existing_accounts = ''
        if existing_accounts:
            if not all_args:
                return {'prompt': '%sContinue? (y/n)' % existing_accounts}
            yes_no = all_args.pop(0)
            if not yes_no == 'y':
                raise CerebrumError('Command aborted at user request')
        if not all_args:
            aff_map = [(('%-8s %s', 'Num', 'Affiliation'), None)]
            for aff in person.get_affiliations():
                ou = self._get_ou(ou_id=aff['ou_id'])
                name = '%s@%s' % (
                    text_type(self.const.PersonAffStatus(aff['status'])),
                    self._format_ou_name(ou))
                aff_map.append((('%s', name),
                                {'ou_id': int(aff['ou_id']),
                                 'affiliation': int(aff['affiliation'])}))
            if not len(aff_map) > 1:
                raise CerebrumError('Person has no affiliations.')
            return {'prompt': 'Choose affiliation from list', 'map': aff_map}
        all_args.pop(0)  # affiliation =
        if not all_args:
            return {'prompt': 'Shell', 'default': 'bash'}
        all_args.pop(0)  # shell =
        if not all_args:
            return {'prompt': 'Disk', 'help_ref': 'disk'}
        all_args.pop(0)  # disk =
        if not all_args:
            ret = {'prompt': 'Username', 'last_arg': True}
            posix_user = Utils.Factory.get('PosixUser')(self.db)
            try:
                person = self._get_person('entity_id', owner_id)
                sugg = posix_user.suggest_unames(
                    person)
                if sugg:
                    ret['default'] = sugg[0]
            except ValueError:
                pass    # Failed to generate a default username
            return ret
        if len(all_args) == 1:
            return {'last_arg': True}
        raise CerebrumError('Too many arguments')

    #
    # user create_personal
    #
    all_commands['user_create_personal'] = Command(
        ('user', 'create_personal'),
        prompt_func=_user_create_prompt_func,
        fs=FormatSuggestion("Created uid=%i", ("uid",)),
        perm_filter='can_create_user')

    def user_create_personal(self, operator, *args):
        if len(args) == 6:
            idtype, person_id, affiliation, shell, home, uname = args
        else:
            idtype, person_id, yes_no, affiliation, shell, home, uname = args

        owner = self._get_person('entity_id', person_id)

        # Only superusers should be allowed to create users with
        # capital letters in their ids, and even then, just for system
        # users
        if uname != uname.lower():
            sup_user_p = self.ba.is_superuser(operator.get_entity_id())
            if not sup_user_p:
                raise CerebrumError('Personal account names cannot contain '
                                    'capital letters')

        if home[0] != ':':  # Hardcoded path
            disk_id, home = self._get_disk(home)[1:3]
        else:
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise PermissionDenied(
                    'Only superusers may use hardcoded path')
            disk_id, home = None, home[1:]
        if uname.endswith('-drift'):
            raise CerebrumError('Users ending with -drift should be created '
                                'with user create_sysadm')
        self.ba.can_create_user(operator.get_entity_id(),
                                owner.entity_id,
                                disk_id)

        account_policy = AccountPolicy(self.db)
        spreads = (int(self.const.Spread(s)) for s in
                   cereconf.BOFHD_NEW_USER_SPREADS)
        disk = {'disk_id': disk_id,
                'home': home}
        if cereconf.DEFAULT_HOME_SPREAD:
            disk['home_spread'] = int(
                self.const.Spread(cereconf.DEFAULT_HOME_SPREAD))
        try:
            account = account_policy.create_personal_account(
                owner,
                [affiliation],
                [disk],
                None,
                operator.get_entity_id(),
                uname=uname,
                spreads=spreads,
                make_posix_user=True,
                gid=None,
                shell=self._get_shell(shell),
            )
        except Errors.InvalidAccountCreationArgument as e:
            raise CerebrumError(e)

        passwd = account.make_passwd(uname)
        account.set_password(passwd)
        account.write_db()
        operator.store_state('new_account_passwd',
                             {'account_id': int(account.entity_id),
                              'password': passwd})
        return {'uid': account.posix_uid}

    #
    # user reserve_personal
    all_commands['user_reserve_personal'] = Command(
        ('user', 'reserve_personal'),
        PersonId(),
        AccountName(),
        fs=FormatSuggestion('Created account_id=%i', ('account_id',)),
        perm_filter='is_superuser')

    def user_reserve_personal(self, operator, person_id, uname):
        person = self._get_person(*self._map_person_id(person_id))
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied('Only superusers may reserve users')
        account = self._user_create_basic(operator, person, uname)
        self._user_password(operator, account)
        return {'account_id': int(account.entity_id)}

    #
    # user create_sysadm
    #
    all_commands['user_create_sysadm'] = Command(
        ("user", "create_sysadm"),
        AccountName(),
        OU(optional=True),
        YesNo(help_ref="yes_no_force", optional=True, default="No"),
        fs=FormatSuggestion('OK, created %s', ('accountname',)),
        perm_filter='can_create_sysadm')

    def user_create_sysadm(self, operator,
                           accountname, stedkode=None, force=False):
        """ Create a sysadm account with the given account name.

        :param str accountname:
            Account to be created. Must include a hyphen and end with one of
            *sysadm_utils.VALID_SYSADM_SUFFIXES*.

        :param str stedkode:
            Optional stedkode to place the sysadm account. Only used if a
            person have multiple valid affiliations.
        """
        self.ba.can_create_sysadm(operator.get_entity_id())

        require_aff_status = (
            self.const.affiliation_status_ansatt_tekadm,
            self.const.affiliation_status_ansatt_vitenskapelig,
            self.const.affiliation_manuell_ekstern,
            self.const.affiliation_tilknyttet_ekst_partner,
        )
        require_aff_str = ', '.join(text_type(aff_status)
                                    for aff_status in require_aff_status)

        target_name, _, suffix = accountname.partition('-')
        # TODO: we should probably deprecate the <uid>-null and <uid>-adm
        # suffixes
        if suffix not in sysadm_utils.VALID_SYSADM_SUFFIXES:
            raise CerebrumError(
                'Username "%s" does not have one of these suffixes: %s' %
                (accountname, ', '.join(sysadm_utils.VALID_SYSADM_SUFFIXES)))

        # Funky... better solutions?
        target_acc = self._get_account(target_name)
        if target_acc.owner_type != self.const.entity_person:
            raise CerebrumError('Can only create personal sysadm accounts')

        if not self._get_boolean(force):
            # Assert that the owner_id doesn't have any other sysadm_acocunts
            ac = self.Account_class(self.db)
            name_pattern = '*-{}'.format(suffix)
            existing = list(ac.search(name=name_pattern,
                                      owner_id=target_acc.owner_id))
            if existing:
                self.logger.debug("Existing accounts: %s", repr(existing))
                raise CerebrumError(
                    'Person already has a sysadm account: {} (need to '
                    'force)'.format(existing[0]['name']))

        # Find and set account_type for the new sysadm account
        if stedkode:
            ou_id = self._get_ou(stedkode=stedkode).entity_id
        else:
            ou_id = None
        valid_affs = set(
            (row['affiliation'], row['ou_id'])
            for row in self.Person_class(self.db).list_affiliations(
                person_id=target_acc.owner_id,
                status=require_aff_status,
                ou_id=ou_id))
        if not valid_affs:
            msg = 'Person has no valid %s affiliation' % (require_aff_str,)
            if stedkode:
                msg += ' @ ' + stedkode
            raise CerebrumError(msg)
        elif len(valid_affs) > 1:
            raise CerebrumError('More than than one %s affiliation, '
                                'add stedkode as argument'
                                % (require_aff_str,))
        ac_type_aff, ac_type_ou = valid_affs.pop()

        # Required info collected and validated - let's create the account
        sysadm_acc = sysadm_utils.create_sysadm_account(
            self.db, target_acc, suffix, operator.get_entity_id())

        # extra stuff that we only do in bofhd
        self._user_password(operator, sysadm_acc)
        self._user_create_set_account_type(sysadm_acc,
                                           target_acc.owner_id,
                                           ac_type_ou, ac_type_aff,
                                           priority=900)
        return {'accountname': sysadm_acc.account_name}

    def _check_for_pipe_run_as(self, account_id):
        et = Email.EmailTarget(self.db)
        try:
            et.clear()
            et.find_by_email_target_attrs(
                target_type=self.const.email_target_pipe,
                using_uid=account_id)
        except Errors.NotFoundError:
            return False
        except Errors.TooManyRowsError:
            return True
        return True

    #
    # user delete
    #
    all_commands['user_delete'] = Command(
        ("user", "delete"),
        AccountName(help_ref='account_name_id_uid'),
        perm_filter='can_delete_user')

    def user_delete(self, operator, accountname):
        # TODO: How do we delete accounts?
        account = self._get_account(accountname)
        self.ba.can_delete_user(operator.get_entity_id(), account)
        if account.is_deleted():
            raise CerebrumError("User is already deleted")
        if self._check_for_pipe_run_as(account.entity_id):
            raise CerebrumError("User is associated with an e-mail pipe "
                                "and cannot be deleted until the pipe is "
                                "removed. Please notify postmaster if you "
                                "are not able to remove the pipe yourself.")

        # Here we'll register a bofhd_reguest to archive the content of the
        # users home directory.
        br = BofhdRequests(self.db, self.const)
        br.add_request(operator.get_entity_id(), br.now,
                       self.const.bofh_delete_user,
                       account.entity_id, None,
                       state_data=int(self.const.spread_uio_nis_user))
        return "User %s queued for deletion immediately" % account.account_name

    #
    # user set_disk_quota
    # TODO: Why don't we use the disk_quota module here?
    # TODO: We should probably just remove the disk quota module and all
    #       related functionality
    #
    all_commands['user_set_disk_quota'] = Command(
        ("user", "set_disk_quota"),
        AccountName(help_ref='account_name_id_uid'),
        Integer(help_ref="disk_quota_size"),
        Date(help_ref="disk_quota_expire_date"),
        SimpleString(help_ref="string_why"),
        perm_filter='can_set_disk_quota',
    )

    def user_set_disk_quota(self, operator, accountname, size, date, why):
        account = self._get_account(accountname)
        exp_date = parsers.parse_date(date)
        why = why.strip()
        if len(why) < 3:
            raise CerebrumError("Why cannot be blank")
        unlimited = forever = False
        if (exp_date - datetime.date.today()).days > 185:
            forever = True
        try:
            size = int(size)
        except ValueError:
            raise CerebrumError("Expected int as size")
        if size > 1024 or size < 0:    # "unlimited" for perm-check = +1024M
            unlimited = True
        self.ba.can_set_disk_quota(operator.get_entity_id(), account,
                                   unlimited=unlimited, forever=forever)
        home = account.get_home(self.const.spread_uio_nis_user)
        if size < 0:
            # unlimited disk quota
            size = None
        dq = DiskQuota(self.db)
        dq.set_quota(home['homedir_id'], override_quota=size,
                     override_expiration=exp_date, description=why)
        return "OK, quota overridden for %s" % accountname

    #
    # user gecos
    #
    all_commands['user_gecos'] = Command(
        ("user", "gecos"),
        AccountName(help_ref='account_name_id_uid'),
        PosixGecos(),
        perm_filter='can_set_gecos')

    def user_gecos(self, operator, accountname, gecos):
        account = self._get_account(accountname, actype="PosixUser")
        # Set gecos to NULL if user requests a whitespace-only string.
        self.ba.can_set_gecos(operator.get_entity_id(), account)
        # TBD: Should we allow 8-bit characters?
        try:
            gecos.encode("ascii")
        except UnicodeError:
            raise CerebrumError("GECOS can only contain US-ASCII.")
        account.gecos = gecos.strip() or None
        account.write_db()
        # TBD: As the 'gecos' attribute lives in class PosixUser,
        # which is ahead of AccountEmailMixin in the MRO of 'account',
        # the write_db() method of AccountEmailMixin will receive a
        # "no updates happened" from its call to superclasses'
        # write_db().  Is there a better way to solve this kind of
        # problem than by adding explicit calls to one if the mixin's
        # methods?  The following call will break if anyone tries this
        # code with an Email-less cereconf.CLASS_ACCOUNT.
        account.update_email_addresses()
        return "OK, set gecos for %s to '%s'" % (accountname, gecos)

    #
    # user history
    #
    all_commands['user_history'] = Command(
        ("user", "history"),
        AccountName(help_ref='account_name_id'),
        fs=FormatSuggestion(
            "%s [%s]: %s", ("timestamp", "change_by", "message")),
        perm_filter='can_show_history')

    def user_history(self, operator, accountname):
        return self.entity_history(operator, accountname)

    #
    # user info
    #
    all_commands['user_info'] = Command(
        ("user", "info"),
        AccountName(help_ref='account_name_id_uid'),
        fs=FormatSuggestion([
            ("Username:      %s\n"
             "Spreads:       %s\n"
             "Affiliations:  %s\n"
             "Expire:        %s\n"
             "Home:          %s (status: %s)\n"
             "Entity id:     %i\n"
             "Owner id:      %i (%s: %s)",
             ("username", "spread", "affiliations", format_day("expire"),
              "home", "home_status", "entity_id", "owner_id", "owner_type",
              "owner_desc")),
            ("Disk quota:    %s MiB", ("disk_quota",)),
            ("DQ override:   %s MiB (until %s: %s)",
             ("dq_override", format_day("dq_expire"), "dq_why")),
            ("UID:           %i\n"
             "Default fg:    %i=%s\n"
             "Gecos:         %s\n"
             "Shell:         %s",
             ('uid', 'dfg_posix_gid', 'dfg_name', 'gecos',
              'shell')),
            ("Quarantined:   %s", ("quarantined",))
        ]),
        perm_filter='can_view_user')

    def user_info(self, operator, accountname):
        is_posix = False
        try:
            account = self._get_account(accountname, actype="PosixUser")
            is_posix = True
        except CerebrumError:
            account = self._get_account(accountname)
        self.ba.can_view_user(operator.get_entity_id(), account)
        if (account.is_deleted() and
                not self.ba.is_superuser(operator.get_entity_id())):
            raise CerebrumError("User '{}' is deleted".format(
                account.account_name))
        affiliations = []
        for row in account.get_account_types(filter_expired=False):
            ou = self._get_ou(ou_id=row['ou_id'])
            affiliations.append(
                "%s@%s" %
                (text_type(self.const.PersonAffiliation(row['affiliation'])),
                 self._format_ou_name(ou)))
        tmp = {
            'disk_id': None,
            'home': None,
            'status': None,
            'homedir_id': None,
        }
        home_status = None
        spread = 'spread_uio_nis_user'
        if spread in cereconf.HOME_SPREADS:
            try:
                tmp = account.get_home(getattr(self.const, spread))
                home_status = self.const.AccountHomeStatus(tmp['status'])
            except Errors.NotFoundError:
                pass

        ret = {
            'entity_id': account.entity_id,
            'username': account.account_name,
            'spread': ",".join([text_type(self.const.Spread(a['spread']))
                                for a in account.get_spread()]),
            'affiliations': (",\n" + (" " * 15)).join(affiliations),
            'expire': account.expire_date,
            'home_status': text_type(home_status),
            'owner_id': account.owner_id,
            'owner_type': text_type(self.const.EntityType(account.owner_type)),
        }
        try:
            self.ba.can_show_disk_quota(operator.get_entity_id(), account)
            can_see_quota = True
        except PermissionDenied:
            can_see_quota = False
        if tmp['disk_id'] and can_see_quota:
            disk = Utils.Factory.get("Disk")(self.db)
            disk.find(tmp['disk_id'])
            has_quota = disk.has_quota()
            def_quota = disk.get_default_quota()
            try:
                dq = DiskQuota(self.db)
                dq_row = dq.get_quota(tmp['homedir_id'])
                if has_quota and dq_row['quota'] is not None:
                    ret['disk_quota'] = str(int(dq_row['quota']))
                # Only display recent quotas
                dq_expire = date_compat.get_date(dq_row['override_expiration'])
                days_left = ((dq_expire or datetime.date.min)
                             - datetime.date.today()).days
                if days_left > -30:
                    ret['dq_override'] = dq_row['override_quota']
                    if dq_row['override_quota'] is not None:
                        ret['dq_override'] = str(int(dq_row['override_quota']))
                    ret['dq_expire'] = dq_expire
                    ret['dq_why'] = dq_row['description']
                    if days_left < 0:
                        ret['dq_why'] += " [INACTIVE]"
            except Errors.NotFoundError:
                if def_quota:
                    ret['disk_quota'] = "(%s)" % def_quota

        if account.owner_type == self.const.entity_person:
            person = self._get_person('entity_id', account.owner_id)
            try:
                p_name = person.get_name(self.const.system_cached,
                                         getattr(self.const,
                                                 cereconf.DEFAULT_GECOS_NAME))
            except Errors.NotFoundError:
                p_name = '<none>'
            ret['owner_desc'] = p_name
        else:
            grp = self._get_group(account.owner_id, idtype='id')
            ret['owner_desc'] = grp.group_name

        # home is not mandatory for some of the instances that "copy"
        # this user_info-method
        if tmp['disk_id'] or tmp['home']:
            ret['home'] = account.resolve_homedir(disk_id=tmp['disk_id'],
                                                  home=tmp['home'])
        else:
            ret['home'] = None
        if is_posix:
            group = self._get_group(account.gid_id,
                                    idtype='id',
                                    grtype='PosixGroup')
            ret['uid'] = account.posix_uid
            ret['dfg_posix_gid'] = group.posix_gid
            ret['dfg_name'] = group.group_name
            ret['gecos'] = account.gecos
            ret['shell'] = text_type(self.const.PosixShell(account.shell))
        # TODO: Return more info about account
        quarantined = get_quarantine_status(account)
        if quarantined:
            ret['quarantined'] = quarantined
        return ret

    def _get_cached_passwords(self, operator):
        ret = []
        for r in operator.get_state():
            # state_type, entity_id, state_data, set_time
            if r['state_type'] in ('new_account_passwd', 'user_passwd'):
                if r['state_data'] is None:
                    continue
                ret.append({
                    'account_id': self._get_entity_name(
                        r['state_data']['account_id'],
                        self.const.entity_account),
                    'password': r['state_data']['password'],
                    'operation': r['state_type'],
                })
        return ret

    #
    # user find
    #
    all_commands['user_find'] = Command(
        ("user", "find"),
        UserSearchType(),
        SimpleString(),
        YesNo(optional=True, default='n', help_ref='yes_no_include_expired'),
        SimpleString(optional=True, help_ref="affiliation_optional"),
        fs=FormatSuggestion(
            "%7i   %-12s %s", ('entity_id', 'username', format_day("expire")),
            hdr="%7s   %-10s   %-12s" % ('Id', 'Username', 'Expire date')),
        perm_filter='can_view_user')

    def user_find(self, operator, search_type, value,
                  include_expired="no", aff_filter=None):
        self.ba.can_view_user(operator.get_entity_id(), account=None)
        acc = self.Account_class(self.db)
        if aff_filter is not None:
            try:
                aff_filter = int(self.const.PersonAffiliation(aff_filter))
            except Errors.NotFoundError:
                raise CerebrumError("Invalid affiliation %r" % aff_filter)
        filter_expired = not self._get_boolean(include_expired)

        if search_type == 'stedkode':
            ou = self._get_ou(stedkode=value)
            rows = acc.list_accounts_by_type(ou_id=ou.entity_id,
                                             affiliation=aff_filter,
                                             filter_expired=filter_expired)
        elif search_type == 'host':
            # FIXME: filtering on affiliation is not implemented
            host = self._get_host(value)
            rows = acc.list_account_home(host_id=int(host.entity_id),
                                         filter_expired=filter_expired)
        elif search_type == 'disk':
            # FIXME: filtering on affiliation is not implemented
            disk = self._get_disk(value)[0]
            rows = acc.list_account_home(disk_id=int(disk.entity_id),
                                         filter_expired=filter_expired)
        else:
            raise CerebrumError("Unknown search type (%r)" % search_type)
        seen = {}
        ret = []
        for r in rows:
            a = int(r['account_id'])
            if a in seen:
                continue
            seen[a] = True
            acc.clear()
            acc.find(a)
            ret.append({
                'entity_id': a,
                'expire': acc.expire_date,
                'username': acc.account_name,
            })
        ret.sort(key=lambda d: d['username'])
        return ret

    #
    # user move prompt
    #
    def user_move_prompt_func(self, session, *args):
        """ user move prompt helper

        Base command:
          user move <move-type> <account-name>
        Variants
          user move immediate           <account-name> <disk-id>
          user move batch               <account-name> <disk-id>
          user move nofile              <account-name> <disk-id>
          user move hard_nofile         <account-name> <disk-id>
          user move student             <account-name>
          user move student_immediate   <account-name>
          user move give                <account-name> <group-name> <reason>
          user move request             <account-name> <disk-id> <reason>
          user move confirm             <account-name>
          user move cancel              <account-name>
        """
        help_struct = Help([self, ], logger=self.logger)
        all_args = list(args)
        if not all_args:
            return MoveType().get_struct(help_struct)
        move_type = all_args.pop(0)
        if not all_args:
            return AccountName(
                help_ref='account_name_id_uid').get_struct(help_struct)
        # pop account name
        all_args.pop(0)
        if move_type in ("immediate", "batch", "nofile", "hard_nofile"):
            # move_type needs disk-id
            if not all_args:
                r = DiskId().get_struct(help_struct)
                r['last_arg'] = True
                return r
            return {'last_arg': True}
        elif move_type in ("student", "student_immediate", "confirm",
                           "cancel"):
            # move_type doesnt need more args
            return {'last_arg': True}
        elif move_type in ("request",):
            # move_type needs disk-id and reason
            if not all_args:
                return DiskId().get_struct(help_struct)
            # pop disk id
            all_args.pop(0)
            if not all_args:
                r = SimpleString(help_ref="string_why").get_struct(help_struct)
                r['last_arg'] = True
                return r
            return {'last_arg': True}
        elif move_type in ("give",):
            # move_type needs group-name and reason
            if not all_args:
                return GroupName().get_struct(help_struct)
            # pop group-name
            all_args.pop(0)
            if not all_args:
                r = SimpleString(help_ref="string_why").get_struct(help_struct)
                r['last_arg'] = True
                return r
            return {'last_arg': True}
        raise CerebrumError("Bad user_move command (%r)" % move_type)

    #
    # user move <move-type> <account-name> [opts]
    #
    all_commands['user_move'] = Command(
        ("user", "move"),
        prompt_func=user_move_prompt_func,
        perm_filter='can_move_user')

    def user_move(self, operator, move_type, accountname, *args):
        # now strip all str / unicode arguments in order to please CRB-2172
        def strip_arg(arg):
            if isinstance(arg, string_types):
                return arg.strip()
            return arg
        args = tuple(map(strip_arg, args))
        self.logger.debug('user_move: after stripping args ({args})'.format(
            args=args))
        account = self._get_account(accountname)

        def account_error(reason):
            return "Cannot move {!r}, {!s}".format(account.account_name,
                                                   reason)

        request_reason_max_len = 80

        def _check_reason(reason):
            if len(reason) > request_reason_max_len:
                raise CerebrumError(
                    "Too long explanation, "
                    "maximum length is {:d}".format(request_reason_max_len))

        if account.is_expired():
            raise CerebrumError(account_error("account is expired"))
        br = BofhdRequests(self.db, self.const)
        batch_time_str = br.batch_time.strftime("%Y-%m-%dT%H:%M:%S")
        spread = int(self.const.spread_uio_nis_user)
        if move_type in ("immediate", "batch", "student", "student_immediate",
                         "request", "give"):
            try:
                ah = account.get_home(spread)
            except Errors.NotFoundError:
                raise CerebrumError(account_error("account has no home"))
        if move_type in ("immediate", "batch", "nofile"):
            message = ""
            disk, disk_id = self._get_disk(args[0])[:2]
            if disk_id is None:
                raise CerebrumError(account_error("bad destination disk"))
            self.ba.can_move_user(operator.get_entity_id(), account, disk_id)

            for r in account.get_spread():
                if (r['spread'] == self.const.spread_ifi_nis_user and
                        not re.match(r'^/ifi/', args[0])):
                    message += ("WARNING: moving user with %s-spread to "
                                "a non-Ifi disk.\n" %
                                text_type(self.const.spread_ifi_nis_user))
                    break

            # Let's check the disk quota settings.  We only give a an
            # information message, the actual change happens when
            # set_homedir is done.
            has_dest_quota = disk.has_quota()
            default_dest_quota = disk.get_default_quota()
            current_quota = None
            dq = DiskQuota(self.db)
            try:
                ah = account.get_home(spread)
            except Errors.NotFoundError:
                raise CerebrumError(account_error("account has no home"))
            try:
                dq_row = dq.get_quota(ah['homedir_id'])
            except Errors.NotFoundError:
                pass
            else:
                current_quota = dq_row['quota']
                if dq_row['quota'] is not None:
                    current_quota = dq_row['quota']

                dq_expire = date_compat.get_date(dq_row['override_expiration'])
                days_left = ((dq_expire or datetime.date.min)
                             - datetime.date.today()).days
                if days_left > 0 and dq_row['override_quota'] is not None:
                    current_quota = dq_row['override_quota']

            if current_quota is None:
                # this is OK
                pass
            elif not has_dest_quota:
                message += ("Destination disk has no quota, so the current "
                            "quota (%d) will be cleared.\n" % current_quota)
            elif current_quota <= default_dest_quota:
                message += ("Current quota (%d) is smaller or equal to the "
                            "default at destination (%d), so it will be "
                            "removed.\n") % (current_quota, default_dest_quota)

            if move_type == "immediate":
                br.add_request(operator.get_entity_id(), br.now,
                               self.const.bofh_move_user_now,
                               account.entity_id, disk_id, state_data=spread)
                message += "Command queued for immediate execution."
            elif move_type == "batch":
                br.add_request(operator.get_entity_id(), br.batch_time,
                               self.const.bofh_move_user,
                               account.entity_id, disk_id, state_data=spread)
                message += ("Move queued for execution at %s."
                            % (batch_time_str,))
                # mail user about the awaiting move operation
                new_homedir = disk.path + '/' + account.account_name
                try:
                    mail_template(
                        account.get_primary_mailaddress(),
                        cereconf.USER_BATCH_MOVE_WARNING,
                        substitute={'USER': account.account_name,
                                    'TO_DISK': new_homedir})
                except Exception as e:
                    self.logger.info("Sending mail failed: %r", e)
            elif move_type == "nofile":
                ah = account.get_home(spread)
                account.set_homedir(current_id=ah['homedir_id'],
                                    disk_id=disk_id)
                account.write_db()
                message += "User moved."
            return message
        elif move_type in ("hard_nofile",):
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise PermissionDenied("only superusers may use hard_nofile")
            ah = account.get_home(spread)
            try:
                account.set_homedir(current_id=ah['homedir_id'], home=args[0])
            except ValueError as e:
                raise CerebrumError(e)
            return "OK, user moved to hardcoded homedir"
        elif move_type in (
                "student", "student_immediate", "confirm", "cancel"):
            self.ba.can_give_user(operator.get_entity_id(), account)
            if move_type == "student":
                br.add_request(operator.get_entity_id(), br.batch_time,
                               self.const.bofh_move_student,
                               account.entity_id, None, state_data=spread)
                return ("student-move queued for execution at %s"
                        % (batch_time_str,))
            elif move_type == "student_immediate":
                br.add_request(operator.get_entity_id(), br.now,
                               self.const.bofh_move_student,
                               account.entity_id, None, state_data=spread)
                return "student-move queued for immediate execution"
            elif move_type == "confirm":
                r = br.get_requests(entity_id=account.entity_id,
                                    operation=self.const.bofh_move_request)
                if not r:
                    raise CerebrumError("No matching request found")
                br.delete_request(account.entity_id,
                                  operation=self.const.bofh_move_request)
                # Flag as authenticated
                br.add_request(operator.get_entity_id(), br.batch_time,
                               self.const.bofh_move_user,
                               account.entity_id, r[0]['destination_id'],
                               state_data=spread)
                return ("move queued for execution at %s"
                        % (batch_time_str,))
            elif move_type == "cancel":
                # TBD: Should superuser delete other request types as well?
                count = 0
                for tmp in br.get_requests(entity_id=account.entity_id):
                    if tmp['operation'] in (
                            self.const.bofh_move_student,
                            self.const.bofh_move_user,
                            self.const.bofh_move_give,
                            self.const.bofh_move_request,
                            self.const.bofh_move_user_now):
                        count += 1
                        br.delete_request(request_id=tmp['request_id'])
                return "OK, %i bofhd requests deleted" % count
        elif move_type in ("request",):
            disk = args[0]
            why = args[1]
            disk_id = self._get_disk(disk)[1]
            _check_reason(why)
            self.ba.can_receive_user(
                operator.get_entity_id(), account, disk_id)
            br.add_request(operator.get_entity_id(), br.now,
                           self.const.bofh_move_request,
                           account.entity_id, disk_id, why)
            return "OK, request registered"
        elif move_type in ("give",):
            self.ba.can_give_user(operator.get_entity_id(), account)
            group = args[0]
            why = args[1]
            group = self._get_group(group)
            _check_reason(why)
            br.add_request(operator.get_entity_id(), br.now,
                           self.const.bofh_move_give,
                           account.entity_id, group.entity_id, why)
            return "OK, 'give' registered"

    #
    # user password
    #
    all_commands['user_password'] = Command(
        ('user', 'password'),
        AccountName(help_ref='account_name_id_uid'),
        AccountPassword(optional=True))

    def user_password(self, operator, accountname, password=None):
        account = self._get_account(accountname)
        self.ba.can_set_password(operator.get_entity_id(), account)
        if password is None:
            password = account.make_passwd(accountname)
        else:
            # this is a bit complicated, but the point is that
            # superusers are allowed to *specify* passwords for other
            # users if cereconf.BOFHD_SU_CAN_SPECIFY_PASSWORDS=True
            # otherwise superusers may change passwords by assigning
            # automatic passwords only.
            if self.ba.is_superuser(operator.get_entity_id()):
                if (operator.get_entity_id() != account.entity_id and
                        not cereconf.BOFHD_SU_CAN_SPECIFY_PASSWORDS):
                    raise CerebrumError("Superuser cannot specify passwords "
                                        "for other users")
            elif operator.get_entity_id() != account.entity_id:
                raise CerebrumError(
                    "Cannot specify password for another user.")
            try:
                check_password(password, account, structured=False)
            except RigidPasswordNotGoodEnough as e:
                raise CerebrumError("Bad password: {}".format(e))
            except PhrasePasswordNotGoodEnough as e:
                raise CerebrumError("Bad passphrase: {}".format(e))
            except PasswordNotGoodEnough as e:
                raise CerebrumError("Bad password: {}".format(e))
        account.set_password(password)
        account.write_db()
        operator.store_state("user_passwd",
                             {'account_id': int(account.entity_id),
                              'password': password})
        # Remove "weak password" quarantine
        for r in account.get_entity_quarantine():
            if r['quarantine_type'] == self.const.quarantine_autopassord:
                account.delete_entity_quarantine(
                    self.const.quarantine_autopassord)

            if r['quarantine_type'] == self.const.quarantine_svakt_passord:
                account.delete_entity_quarantine(
                    self.const.quarantine_svakt_passord)

        if account.is_deleted():
            return "OK.  Warning: user is deleted"
        elif account.is_expired():
            return "OK.  Warning: user is expired"
        elif account.get_entity_quarantine(only_active=True):
            return "OK.  Warning: user has an active quarantine"
        return ("Password altered. Please use misc list_passwords to view the "
                "new password, or misc print_passwords to print password "
                "letters.")

    #
    # user promote_posix
    #
    all_commands['user_promote_posix'] = Command(
        ('user', 'promote_posix'),
        AccountName(help_ref='account_name_id'),
        PosixShell(default="bash"),
        DiskId(),
        perm_filter='can_create_user')

    def user_promote_posix(self, operator, accountname, shell=None, home=None):
        # Verify that account name is legal
        pu = Utils.Factory.get('PosixUser')(self.db)
        illegal_name = pu.illegal_name(accountname)
        if illegal_name:
            raise CerebrumError("Illegal account name given. Account name " +
                                illegal_name)

        is_posix = False
        try:
            self._get_account(accountname, actype="PosixUser")
            is_posix = True
        except CerebrumError:
            pass
        if is_posix:
            raise CerebrumError("%s is already a PosixUser" % accountname)
        account = self._get_account(accountname)
        old_uid = self._lookup_old_uid(account.entity_id)
        if old_uid is None:
            uid = pu.get_free_uid()
        else:
            uid = old_uid
        shell = self._get_shell(shell)
        if not home:
            raise CerebrumError("home cannot be empty")
        elif home[0] != ':':  # Hardcoded path
            disk_id, home = self._get_disk(home)[1:3]
        else:
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise PermissionDenied("only superusers may use hardcoded"
                                       " path")
            disk_id, home = None, home[1:]
        if account.owner_type == self.const.entity_person:
            person = self._get_person("entity_id", account.owner_id)
        else:
            person = None
        self.ba.can_create_user(operator.get_entity_id(), person, disk_id)

        pu.populate(uid, None, None, shell,
                    parent=account, creator_id=operator.get_entity_id())
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
    # user demote_posix
    #
    all_commands['user_demote_posix'] = Command(
        ('user', 'demote_posix'),
        AccountName(help_ref='account_name_id_uid'),
        perm_filter='can_create_user')

    def user_demote_posix(self, operator, accountname):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("currently limited to superusers")
        user = self._get_account(accountname, actype="PosixUser")
        user.delete_posixuser()
        return "OK, %s was demoted" % accountname

    def user_restore_handle(self, operator, ac, home, disk_id, aff_ou=None):
        """ Common method for user restore and user restore unpersonal.
        """
        accountname = ac.account_name
        # We demote posix
        try:
            pu = self._get_account(accountname, actype='PosixUser')
        except CerebrumError:
            pu = Utils.Factory.get('PosixUser')(self.db)
        else:
            pu.delete_posixuser()
            pu = Utils.Factory.get('PosixUser')(self.db)

        # We remove all old group memberships, except the personal group, which
        # should have its expire date removed
        grp = self.Group_class(self.db)
        for row in grp.search(member_id=ac.entity_id, filter_expired=False):
            grp.clear()
            grp.find(row['group_id'])
            if grp.get_trait('personal_group'):
                grp.expire_date = None
            else:
                grp.remove_member(ac.entity_id)
            grp.write_db()

        # Automatic selection of affiliation. This could be used if the user
        # should not choose affiliations.
        # # Sort affiliations according to creation date (newest first), and
        # # try to save it for later. If there exists no affiliations, we'll
        # # raise an error, since we'll need an affiliation to copy from the
        # # person to the account.
        # try:
        #     tmp = sorted(pe.get_affiliations(),
        #                  key=lambda i: i['create_date'], reverse=True)[0]
        #     ou, aff = tmp['ou_id'], tmp['affiliation']
        # except IndexError:
        #     raise CerebrumError('Person must have an affiliation')

        if ac.owner_type == self.const.entity_person:
            # When using user_restore on a personal account
            # we remove all (the old) affiliations on the account
            for row in ac.get_account_types(filter_expired=False):
                ac.del_account_type(row['ou_id'], row['affiliation'])

            # We set the affiliation selected by the operator.
            self._user_create_set_account_type(ac,
                                               ac.owner_id,
                                               aff_ou['ou_id'],
                                               aff_ou['aff'])

        # And promote posix
        old_uid = self._lookup_old_uid(ac.entity_id)
        if old_uid is None:
            uid = pu.get_free_uid()
        else:
            uid = old_uid

        shell = self.const.posix_shell_bash

        # Populate the posix user, and write it to the database
        pu.populate(uid, None, None, shell, parent=ac,
                    creator_id=operator.get_entity_id())
        try:
            pu.write_db()
        except self.db.IntegrityError as e:
            self.logger.debug("IntegrityError (user_restore): %r", e)
            self.db.rollback()
            raise CerebrumError('Please contact brukerreg in order to restore')

        # Unset the expire date
        ac.expire_date = None

        # Add them spreads
        for s in cereconf.BOFHD_NEW_USER_SPREADS:
            if not pu.has_spread(self.const.Spread(s)):
                pu.add_spread(self.const.Spread(s))

        # And remove them quarantines (except those defined in cereconf)
        for q in ac.get_entity_quarantine():
            if (text_type(self.const.Quarantine(q['quarantine_type']))
                    not in cereconf.BOFHD_RESTORE_USER_SAVE_QUARANTINES):
                ac.delete_entity_quarantine(q['quarantine_type'])

        # We set the new homedir
        default_home_spread = self._get_constant(self.const.Spread,
                                                 cereconf.DEFAULT_HOME_SPREAD,
                                                 'spread')

        homedir_id = pu.set_homedir(
            disk_id=disk_id, home=home,
            status=self.const.home_status_not_created)
        pu.set_home(default_home_spread, homedir_id)

        # We'll set a new password and store it for printing
        passwd = ac.make_passwd(ac.account_name)
        ac.set_password(passwd)

        operator.store_state('new_account_passwd',
                             {'account_id': int(ac.entity_id),
                              'password': passwd})

        # We'll need to write to the db, in order to store stuff.
        try:
            ac.write_db()
        except self.db.IntegrityError as e:
            self.logger.debug("IntegrityError (user_restore): %r", e)
            self.db.rollback()
            raise CerebrumError('Please contact brukerreg in order to restore')

        # Return string with some info
        if ac.get_entity_quarantine():
            note = '\nNotice: Account is quarantined!'
        else:
            note = ''

        if old_uid is None:
            tmp = ', new uid=%i' % uid
        else:
            tmp = ', reused old uid=%i' % old_uid

        return ('OK, promoted %s to posix user%s.\n'
                'Password altered. Use misc list_password to print or view '
                'the new password.%s' % (accountname, tmp, note))

    def user_restore_prompt_func(self, session, *args):
        '''Helper function for user_restore. Will display a prompt that
        asks which affiliation should be used, and more..'''

        all_args = list(args[:])

        # Get the account name
        if not all_args:
            return {'prompt': 'Account name',
                    'help_ref': 'account_name_id_uid'}
        arg = all_args.pop(0)
        ac = self._get_account(arg)

        if ac.owner_type != self.const.entity_person:
            raise CerebrumError('Owner of entity is not a person. '
                                'Please contact IT support to restore %s'
                                % ac.get_account_name())

        # Print a list of affiliations registred on the accounts owner (person)
        # Prompts user to select one of these. Checks if the input is sane.
        if not all_args:
            person = self._get_person('entity_id', ac.owner_id)
            map = [(('%-8s %s', 'Num', 'Affiliation'), None)]
            for aff in person.get_affiliations():
                ou = self._get_ou(ou_id=aff['ou_id'])
                name = '%s@%s' % (
                    text_type(self.const.PersonAffStatus(aff['status'])),
                    self._format_ou_name(ou))
                map.append((('%s', name), {'ou_id': int(aff['ou_id']),
                                           'aff': int(aff['affiliation'])}))
            if not len(map) > 1:
                raise CerebrumError('Person has no affiliations.')
            return {'prompt': 'Choose affiliation from list', 'map': map}
        arg = all_args.pop(0)
        if isinstance(arg, type({})) and 'aff' in arg and 'ou_id' in arg:
            ou = arg['ou_id']
            aff = arg['aff']
        else:
            raise CerebrumError('Invalid affiliation')

        # Gets the disk the user will reside on
        if not all_args:
            return {
                'prompt': 'Disk',
                'help_ref': 'disk',
                'last_arg': True,
            }
        arg = all_args.pop(0)
        # TODO: are we checking if the arg is valid here?
        self._get_disk(arg)

        # Finishes off
        if len(all_args) == 0:
            return {'last_arg': True}

        # We'll raise an error, if there is too many arguments:
        raise CerebrumError('Too many arguments')

    #
    # user restore
    #
    all_commands['user_restore'] = Command(
        ('user', 'restore'),
        prompt_func=user_restore_prompt_func,
        perm_filter='can_create_user')

    def user_restore(self, operator, accountname, aff_ou, home):
        ac = self._get_account(accountname)
        # Check if the account is deleted or reserved
        if not ac.is_deleted() and not ac.is_reserved():
            raise CerebrumError('Please contact brukerreg to restore %r' %
                                accountname)

        # Checking to see if the home path is hardcoded.
        # Raises CerebrumError if the disk does not exist.
        if not home:
            raise CerebrumError('Home must be specified')
        elif home[0] != ':':  # Hardcoded path
            disk_id, home = self._get_disk(home)[1:3]
        else:
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise PermissionDenied('Only superusers may use hardcoded'
                                       ' path')
            disk_id, home = None, home[1:]

        # Check if the operator can alter the user
        if not self.ba.can_create_user(operator.get_entity_id(), ac, disk_id):
            raise PermissionDenied('User restore is limited')

        return self.user_restore_handle(operator, ac, home, disk_id, aff_ou)

    def user_restore_unpersonal_prompt_func(self, session, *args):
        '''Helper function for user_restore_unpersonal. Will display a
        prompt that asks which disk should be used. Only works if the
        owner of the user is a group. '''

        all_args = list(args[:])

        # Get the account name
        if not all_args:
            return {'prompt': 'Account name',
                    'help_ref': 'account_name_id_uid'}
        arg = all_args.pop(0)
        ac = self._get_account(arg)

        if ac.owner_type != self.const.entity_group:
            raise CerebrumError('Owner of entity is a person. '
                                'Please use user restore instead to restore %s'
                                % ac.get_account_name())

        # Gets the disk the user will reside on
        if not all_args:
            return {
                'prompt': 'Disk',
                'help_ref': 'disk',
                'last_arg': True,
            }

        arg = all_args.pop(0)
        # TODO: are we checking if the arg is valid here?
        self._get_disk(arg)

        # Finishes off
        if len(all_args) == 0:
            return {'last_arg': True}

        # We'll raise an error, if there is too many arguments:
        raise CerebrumError('Too many arguments')

    #
    # user restore_unpersonal
    #
    all_commands['user_restore_unpersonal'] = Command(
        ('user', 'restore_unpersonal'),
        prompt_func=user_restore_unpersonal_prompt_func,
        perm_filter='is_superuser')

    def user_restore_unpersonal(self, operator, accountname, home):
        ac = self._get_account(accountname)

        # Check if the account is deleted or reserved
        if not ac.is_deleted() and not ac.is_reserved():
            raise CerebrumError('Please contact brukerreg to restore %r' %
                                accountname)

        # Checking to see if the home path is hardcoded.
        # Raises CerebrumError if the disk does not exist.
        if not home:
            raise CerebrumError('Home must be specified')
        elif home[0] != ':':  # Hardcoded path
            disk_id, home = self._get_disk(home)[1:3]
        else:
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise PermissionDenied('Only superusers may use hardcoded'
                                       ' path')
            disk_id, home = None, home[1:]

        # Check if the operator can alter the user
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied('User restore_unpersonal is limited to'
                                   ' superusers.')

        return self.user_restore_handle(operator, ac, home, disk_id)

    #
    # user set_disk_status
    #
    all_commands['user_set_disk_status'] = Command(
        ('user', 'set_disk_status'),
        AccountName(help_ref='account_name_id_uid'),
        SimpleString(help_ref='string_disk_status'),
        perm_filter='can_create_disk')

    def user_set_disk_status(self, operator, accountname, status):
        try:
            status = self.const.AccountHomeStatus(status)
            int(status)
        except Errors.NotFoundError:
            raise CerebrumError("Unknown status")
        account = self._get_account(accountname)
        # this is not exactly right, we should probably
        # implement a can_set_disk_status-function, but no
        # appropriate criteria is readily available for this
        # right now
        self.ba.can_create_disk(operator.get_entity_id(), query_run_any=True)
        ah = account.get_home(self.const.spread_uio_nis_user)
        account.set_homedir(current_id=ah['homedir_id'], status=status)
        return "OK, set home-status for %s to %s" % (accountname,
                                                     text_type(status))

    #
    # user set_expire
    #
    all_commands['user_set_expire'] = Command(
        ('user', 'set_expire'),
        AccountName(help_ref='account_name_id_uid'),
        # TODO: We should update the help text to include info from
        # parsers.parse_date_help_blurb
        Date(),
        # TODO: isn't this now just is_superuser?
        perm_filter='can_delete_user',
    )

    def user_set_expire(self, operator, accountname, date):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        account = self._get_account(accountname)
        # self.ba.can_delete_user(operator.get_entity_id(), account)
        expire_date = parsers.parse_date(date, optional=True)
        account.expire_date = expire_date
        account.write_db()
        return "OK, set expire-date for %s to %s" % (accountname,
                                                     str(expire_date))

    #
    # user set_np_type
    #
    all_commands['user_set_np_type'] = Command(
        ('user', 'set_np_type'),
        AccountName(help_ref='account_name_id_uid'),
        SimpleString(help_ref="string_np_type"),
        perm_filter='can_delete_user')

    def user_set_np_type(self, operator, accountname, np_type):
        account = self._get_account(accountname)
        self.ba.can_delete_user(operator.get_entity_id(), account)
        account.np_type = self._get_constant(self.const.Account, np_type,
                                             "account type")
        account.write_db()
        return "OK, set np-type for %s to %s" % (accountname,
                                                 text_type(account.np_type))

    def user_set_owner_prompt_func(self, session, *args):
        all_args = list(args[:])
        if not all_args:
            return {'prompt': 'Account name',
                    'help_ref': 'account_name_id_uid'}

        all_args.pop(0)
        if not all_args:
            return {'prompt': 'Entity type (group/person)',
                    'default': 'person'}
        entity_type = all_args.pop(0)
        if not all_args:
            return {'prompt': 'Id of the type specified above',
                    'help_ref': 'user_set_owner_group_person'}
        id = all_args.pop(0)
        if entity_type == 'person':
            if not all_args:
                person = self._get_person(*self._map_person_id(id))
                map = [(("%-8s %s", "Num", "Affiliation"), None)]
                for aff in person.get_affiliations():
                    ou = self._get_ou(ou_id=aff['ou_id'])
                    name = "%s@%s" % (
                        text_type(self.const.PersonAffStatus(aff['status'])),
                        self._format_ou_name(ou))
                    map.append((("%s", name),
                                {'ou_id': int(aff['ou_id']),
                                 'aff': int(aff['affiliation'])}))
                if not len(map) > 1:
                    raise CerebrumError(
                        "Person has no affiliations.")
                return {'prompt': "Choose affiliation from list", 'map': map,
                        'last_arg': True}
        else:
            if not all_args:
                return {'prompt': "Enter np_type",
                        'help_ref': 'string_np_type',
                        'last_arg': True}
            all_args.pop(0)
        raise CerebrumError("Client called prompt func with too many "
                            "arguments")

    #
    # user set_owner
    #
    all_commands['user_set_owner'] = Command(
        ("user", "set_owner"),
        prompt_func=user_set_owner_prompt_func,
        perm_filter='is_superuser')

    def user_set_owner(self, operator, *args):
        if args[1] == 'person':
            accountname, entity_type, id, affiliation = args
            new_owner = self._get_person(*self._map_person_id(id))
        else:
            accountname, entity_type, id, np_type = args
            new_owner = self._get_entity(entity_type, id)
            np_type = self._get_constant(self.const.Account, np_type,
                                         "account type")

        account = self._get_account(accountname)
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("only superusers may assign account"
                                   " ownership")
        new_owner = self._get_entity(entity_type, id)
        if account.owner_type == self.const.entity_person:
            for row in account.get_account_types(filter_expired=False):
                account.del_account_type(row['ou_id'], row['affiliation'])
        account.owner_type = new_owner.entity_type
        account.owner_id = new_owner.entity_id
        if args[1] == 'group':
            account.np_type = np_type
        account.write_db()
        if new_owner.entity_type == self.const.entity_person:
            ou_id, affiliation = affiliation['ou_id'], affiliation['aff']
            self._user_create_set_account_type(account, account.owner_id,
                                               ou_id, affiliation)
        return "OK, set owner of %s to %s" % (
            accountname, self._get_name_from_object(new_owner))

    #
    # user shell
    #
    all_commands['user_shell'] = Command(
        ("user", "shell"),
        AccountName(help_ref='account_name_id_uid'),
        PosixShell(default="bash")
    )

    def user_shell(self, operator, accountname, shell=None):
        account = self._get_account(accountname, actype="PosixUser")
        shell = self._get_shell(shell)
        self.ba.can_set_shell(operator.get_entity_id(), account, shell)
        account.shell = shell
        account.write_db()
        return "OK, set shell for %s to %s" % (accountname, text_type(shell))

    #
    # get_persdata
    #
    all_commands['get_persdata'] = None

    def get_persdata(self, operator, uname):
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        ac = self._get_account(uname)
        person_id = "entity_id:%i" % ac.owner_id
        person = self._get_person(*self._map_person_id(person_id))
        ret = {
            'is_personal': len(ac.get_account_types()),
            'fnr': [
                {'id': r['external_id'],
                 'source': text_type(
                     self.const.AuthoritativeSystem(r['source_system']))}
                for r in person.get_external_id(
                        id_type=self.const.externalid_fodselsnr)]}
        ac_types = ac.get_account_types(all_persons_types=True)
        if ret['is_personal']:
            ac_types.sort(lambda x, y: int(x['priority']-y['priority']))
            for at in ac_types:
                ac2 = self._get_account(at['account_id'], idtype='id')
                aff2 = self.const.PersonAffiliation(at['affiliation'])
                ret.setdefault('users', []).append(
                    (ac2.account_name, '%s@ulrik.uio.no' % ac2.account_name,
                     at['priority'], at['ou_id'], text_type(aff2)))
            # TODO: kall ac.list_accounts_by_owner_id(ac.owner_id) for
            # å hente ikke-personlige konti?
        ret['home'] = ac.resolve_homedir(disk_id=ac.disk_id, home=ac.home)
        ret['navn'] = {'cached': person.get_name(
            self.const.system_cached, self.const.name_full)}
        for key, variant in (("work_title", self.const.work_title),
                             ("personal_title", self.const.personal_title)):
            try:
                ret[key] = person.get_name_with_language(
                                      name_variant=variant,
                                      name_language=self.const.language_nb)
            except (Errors.NotFoundError, Errors.TooManyRowsError):
                pass
        return ret

    def _get_account(self, id, idtype=None, actype="Account"):
        if actype == 'Account':
            account = self.Account_class(self.db)
        elif actype == 'PosixUser':
            account = Utils.Factory.get('PosixUser')(self.db)
        account.clear()
        try:
            if idtype is None:
                if id.find(":") != -1:
                    idtype, id = id.split(":", 1)
                    if len(id) == 0:
                        raise CerebrumError("Must specify id")
                else:
                    idtype = 'name'
            if idtype == 'name':
                account.find_by_name(id, self.const.account_namespace)
            elif idtype == 'id':
                if isinstance(id, str) and not id.isdigit():
                    raise CerebrumError("Entity id must be a number")
                account.find(id)
            elif idtype == 'uid':
                if isinstance(id, str) and not id.isdigit():
                    raise CerebrumError('uid must be a number')
                if actype != 'PosixUser':
                    account = Utils.Factory.get('PosixUser')(self.db)
                    account.clear()
                account.find_by_uid(id)
            else:
                raise CerebrumError("unknown idtype: %r" % idtype)
        except Errors.NotFoundError:
            raise CerebrumError("Could not find %r with %s=%r" %
                                (actype, idtype, id))
        return account

    def _get_shell(self, shell):
        return self._get_constant(self.const.PosixShell, shell, "shell")

    def _get_group_opcode(self, operator):
        if operator is None:
            return self.const.group_memberop_union
        if operator == 'union':
            return self.const.group_memberop_union
        if operator == 'intersection':
            return self.const.group_memberop_intersection
        if operator == 'difference':
            return self.const.group_memberop_difference
        raise CerebrumError("unknown group opcode: %s" % operator)

    def _get_entity(self, idtype=None, ident=None):
        if ident is None:
            raise CerebrumError("Invalid id")
        if idtype == 'account':
            return self._get_account(ident)
        if idtype == 'person':
            return self._get_person(*self._map_person_id(ident))
        if idtype == 'group':
            return self._get_group(ident)
        if idtype == 'stedkode':
            return self._get_ou(stedkode=ident)
        if idtype == 'host':
            return self._get_host(ident)
        if idtype is None:
            try:
                int(ident)
            except ValueError:
                raise CerebrumError("Expected int as id")
            ety = Entity.Entity(self.db)
            return ety.get_subclassed_object(ident)
        raise CerebrumError("Invalid idtype")

    # The next two functions require all affiliations to be in upper case,
    # and all affiliation statuses to be in lower case.  If this changes,
    # the user will have to type exact case.
    def _get_affiliationid(self, code_str):
        try:
            c = self.const.PersonAffiliation(code_str.upper())
            # force a database lookup to see if it's a valid code
            int(c)
            return c
        except Errors.NotFoundError:
            raise CerebrumError("Unknown affiliation")

    def _get_affiliation_statusid(self, affiliation, code_str):
        try:
            c = self.const.PersonAffStatus(affiliation, code_str.lower())
            int(c)
            return c
        except Errors.NotFoundError:
            raise CerebrumError("Unknown affiliation status")

    #
    # misc get_constant_description
    #
    hidden_commands['get_constant_description'] = Command(
        ("misc", "get_constant_description"),
        SimpleString(),   # constant class
        SimpleString(optional=True),
        fs=FormatSuggestion(
            "%-15s %s", ("code_str", "description")
        ))

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
                    "code_str": text_type(c),
                    "description": c.description}

        # Fetch all of the constants of the specified type
        return [
            {
                "code": int(x),
                "code_str": text_type(x),
                "description": x.description,
            }
            for x in self.const.fetch_constants(kls)
        ]

    def _format_from_cl(self, format, val):
        def _get_code(get, code, fallback=None):
            def f(get, code, fallback):
                try:
                    return (1, text_type(get(code)))
                except Errors.NotFoundError:
                    if fallback:
                        return (2, fallback)
                    else:
                        return (2, text_type(code))
            if not isinstance(get, (tuple, list)):
                get = [get]
            return sorted([f(c, code, fallback) for c in get])[0][1]

        if val is None:
            return ''

        if format == 'affiliation':
            return _get_code(self.const.PersonAffiliation, val)
        elif format == 'disk':
            disk = Utils.Factory.get('Disk')(self.db)
            try:
                disk.find(val)
                return disk.path
            except Errors.NotFoundError:
                return "deleted_disk:%s" % val
        elif format == 'date':
            return val.date
        elif format == 'timestamp':
            return text_type(val)
        elif format == 'entity':
            return self._get_entity_name(int(val))
        elif format == 'extid':
            return _get_code(self.const.EntityExternalId, val)
        elif format == 'homedir':
            return 'homedir_id:%s' % val
        elif format == 'id_type':
            return _get_code(self.clconst.ChangeType, val)
        elif format == 'home_status':
            return _get_code(self.const.AccountHomeStatus, val)
        elif format == 'int':
            return text_type(val)
        elif format == 'name_variant':
            # Name variants are stored in two separate code-tables; if
            # one doesn't work, try the other
            return _get_code((self.const.PersonName,
                              self.const.EntityNameCode), val)
        elif format == 'ou':
            ou = self._get_ou(ou_id=val)
            return self._format_ou_name(ou)
        elif format == 'quarantine_type':
            return _get_code(self.const.Quarantine, val)
        elif format == 'source_system':
            return _get_code(self.const.AuthoritativeSystem, val)
        elif format == 'spread_code':
            return _get_code(self.const.Spread, val)
        elif format == 'string':
            return text_type(val)
        elif format == 'trait':
            # Trait has been deleted from the DB, so we can't know which it
            # was. Therefore we return '<unknown>'
            return _get_code(self.const.EntityTrait, val, '<unknown>')
        elif format == 'value_domain':
            return _get_code(self.const.ValueDomain, val)
        elif format == 'rolle_type':
            return _get_code(self.const.EphorteRole, val)
        elif format == 'perm_type':
            return _get_code(self.const.EphortePermission, val)
        elif format == 'bool':
            if val == 'T':
                return repr(True)
            elif val == 'F':
                return repr(False)
            else:
                return repr(bool(val))
        else:
            self.logger.warn("bad cl format: %s", repr((format, val)))
            return ''

    def _format_changelog_entry(self, row):
        dest = row['dest_entity']
        if dest is not None:
            try:
                dest = self._get_entity_name(dest)
            except Errors.NotFoundError:
                dest = repr(dest)

        this_cl_const = self.clconst.ChangeType(row['change_type_id'])
        if this_cl_const.msg_string is None:
            self.logger.warn('Formatting of change log entry of type %s '
                             'failed, no description defined in change type',
                             text_type(this_cl_const))
            msg = '{}, subject {}, destination {}'.format(
                text_type(this_cl_const),
                self._get_entity_name(row['subject_entity']),
                dest)
        else:
            msg = this_cl_const.msg_string % {
                'subject': self._get_entity_name(row['subject_entity']),
                'dest': dest}

        # Append information from change_params to the string.  See
        # _ChangeTypeCode.__doc__
        if row['change_params']:
            try:
                params = json.loads(row['change_params'])
            except TypeError:
                self.logger.error("Bogus change_param in change_id=%s,"
                                  " row: %r", row['change_id'], row)
                raise
        else:
            params = {}

        if this_cl_const.format:
            for f in this_cl_const.format:
                repl = {}
                for part in re.findall(r'%\([^\)]+\)s', f):
                    fmt_type, key = part[2:-2].split(':')
                    try:
                        _kk = '%%(%s:%s)s' % (fmt_type, key)
                        repl[_kk] = self._format_from_cl(fmt_type,
                                                         params.get(key, None))
                    except Exception:
                        self.logger.warn("Failed applying %s to %s"
                                         " for change-id: %d",
                                         part,
                                         repr(params.get(key)),
                                         row['change_id'])
                if [x for x in repl.values() if x]:
                    for k, v in repl.items():
                        f = f.replace(k, v)
                    msg += ", " + f
        by = row['change_program'] or self._get_entity_name(row['change_by'])
        return {'timestamp': row['tstamp'],
                'change_by': by,
                'message': msg}

    def _lookup_old_uid(self, account_id):
        uid = None
        for r in self.db.get_log_events(0,
                                        subject_entity=account_id,
                                        types=[self.clconst.posix_demote]):
            uid = json.loads(r['change_params'])['uid']
        return uid


class ContactCommands(BofhdContactCommands):
    """ entity_contactinfo_* commands with custom uio auth. """
    authz = bofhd_auth.ContactAuth


class EmailCommands(bofhd_email.BofhdEmailCommands):
    """ UiO specific email commands and overloads. """

    all_commands = {}
    hidden_commands = {}
    omit_parent_commands = set()
    parent_commands = True
    authz = bofhd_auth.EmailAuth

    @classmethod
    def get_help_strings(cls):
        email_cmds = {
            'email': {
                'email_forward_info':
                    "Show information about an address that is forwarded to",
                'email_move':
                    "Move a user's e-mail to another server",
                'email_show_reservation_status':
                    "Show reservation status for an account",
            }
        }
        return merge_help_strings(
            super(EmailCommands, cls).get_help_strings(),
            ({}, email_cmds, {}))

    def __email_forward_destination_allowed(self, account, address):
        """ Check if the forward is compilant with Norwegian law"""
        person = Utils.Factory.get('Person')(self.db)
        if (account.owner_type == self.const.entity_person and
                person.list_affiliations(
                    person_id=account.owner_id,
                    affiliation=self.const.affiliation_ansatt)):
            try:
                self._get_email_domain_from_str(address.split('@')[-1])
            except CerebrumError:
                return False
        return True

    def _get_email_target_and_address(self, address):
        # Support DistributionGroup email target lookup
        try:
            return super(EmailCommands,
                         self)._get_email_target_and_address(address)
        except CerebrumError as e:
            # Not found, maybe distribution group?
            try:
                dlgroup = Utils.Factory.get("DistributionGroup")(self.db)
                dlgroup.find_by_name(address)
                et = Email.EmailTarget(self.db)
                et.find_by_target_entity(dlgroup.entity_id)
                epa = Email.EmailPrimaryAddressTarget(self.db)
                epa.find(et.entity_id)
                ea = Email.EmailAddress(self.db)
                ea.find(epa.email_primaddr_id)
                return et, ea
            except Errors.NotFoundError:
                raise e

    def _get_email_target_and_dlgroup(self, address):
        """Returns a tuple consisting of the email target associated
        with address and the account if the target type is user.  If
        there is no at-sign in address, assume it is an account name.
        Raises CerebrumError if address is unknown."""
        et, ea = self._get_email_target_and_address(address)
        grp = None
        # what will happen if the target was a dl_group but is now
        # deleted? it's possible that we should have created a new
        # target_type = dlgroup_deleted, but it seemed redundant earlier
        # now, i'm not so sure (Jazz, 2013-12(
        if et.email_target_type in (self.const.email_target_dl_group,
                                    self.const.email_target_deleted):
            grp = self._get_group(et.email_target_entity_id,
                                  idtype='id',
                                  grtype="DistributionGroup")
        return et, grp

    def _email_info_detail(self, acc):
        info = []
        eq = Email.EmailQuota(self.db)
        try:
            eq.find_by_target_entity(acc.entity_id)
            et = Email.EmailTarget(self.db)
            et.find_by_target_entity(acc.entity_id)
            es = Email.EmailServer(self.db)
            es.find(et.email_server_id)

            info.append({'dis_quota_hard': eq.email_quota_hard,
                         'dis_quota_soft': eq.email_quota_soft})
        except Errors.NotFoundError:
            pass
        return info

    def _email_info_dlgroup(self, groupname):
        et, dl_group = self._get_email_target_and_dlgroup(groupname)
        ret = []
        # we need to make the return value conform with the
        # client requeirements
        tmpret = dl_group.get_distgroup_attributes_and_targetdata()
        for x in tmpret:
            if tmpret[x] == 'T':
                ret.append({x: 'Yes'})
                continue
            elif tmpret[x] == 'F':
                ret.append({x: 'No'})
                continue
            ret.append({x: tmpret[x]})
        return ret

    #
    # email forward_add <account>+ <address>+
    #
    def email_forward_add(self, operator, uname, address):
        """Add an email-forward to a email-target asociated with an account."""
        # Override email_forward_add with check for employee email addr
        et, acc = self._get_email_target_and_account(uname)
        if acc and not self.__email_forward_destination_allowed(acc, address):
            raise CerebrumError("Employees cannot forward e-mail to"
                                " external addresses")
        return super(EmailCommands, self).email_forward_add(operator,
                                                            uname,
                                                            address)

    #
    # email forward_info
    #
    all_commands['email_forward_info'] = Command(
        ('email', 'forward_info'),
        EmailAddress(),
        fs=FormatSuggestion([('%s', ('id', ))]),
        perm_filter='can_email_forward_info',
    )

    def email_forward_info(self, operator, forward_to):
        """List owners of email forwards."""
        self.ba.can_email_forward_info(operator.get_entity_id())
        ef = Email.EmailForward(self.db)
        et = Email.EmailTarget(self.db)
        ac = Utils.Factory.get('Account')(self.db)
        ret = []

        # Different output format for different input.
        def rfun(r):
            return (r if '%' not in forward_to
                    else '%-12s %s' % (r, fwd['forward_to']))

        for fwd in ef.search(forward_to):
            try:
                et.clear()
                ac.clear()
                et.find(fwd['target_id'])
                ac.find(et.email_target_entity_id)
                ret.append({'id': rfun(ac.account_name)})
            except Errors.NotFoundError:
                ret.append({'id': rfun('id:%s' % et.entity_id)})
        return ret

    #
    # email show_reservation_status
    #
    all_commands['email_show_reservation_status'] = Command(
        ('email', 'show_reservation_status'),
        AccountName(),
        fs=FormatSuggestion([("%-9s %s", ("uname", "hide"))]),
        perm_filter='is_postmaster')

    def email_show_reservation_status(self, operator, uname):
        """Display reservation status for a person."""
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('Access to this command is restricted')
        hidden = True
        account = self._get_account(uname)
        if account.owner_type == self.const.entity_person:
            person = self._get_person('entity_id', account.owner_id)
            randsone_group = self._get_group("randsone-aktivt-samtykke")

            if person.has_e_reservation():
                hidden = True
            elif person.get_primary_account() != account.entity_id:
                hidden = True
            else:
                hidden = False

            if hidden:
                members = randsone_group.search_members(
                    group_id=randsone_group.entity_id, indirect_members=True)
                for member in members:
                    if member['member_id'] == person.entity_id:
                        hidden = False
        return {
            'uname': uname,
            'hide': 'hidden' if hidden else 'visible',
        }

    #
    # email move
    #
    all_commands['email_move'] = Command(
        ("email", "move"),
        AccountName(help_ref="account_name", repeat=True),
        SimpleString(help_ref='string_email_host'),
        perm_filter='can_email_move')

    def email_move(self, operator, uname, server):
        acc = self._get_account(uname)
        self.ba.can_email_move(operator.get_entity_id(), acc)
        et = Email.EmailTarget(self.db)
        et.find_by_target_entity(acc.entity_id)
        old_server = et.email_server_id
        es = Email.EmailServer(self.db)
        try:
            es.find_by_name(server)
        except Errors.NotFoundError:
            raise CerebrumError("%r is not registered as an e-mail server" %
                                server)
        if old_server == es.entity_id:
            raise CerebrumError("User is already at %s" % server)

        et.email_server_id = es.entity_id
        et.write_db()
        return "OK, updated e-mail server for %s (to %s)" % (uname, server)


class AccessCommands(bofhd_access.BofhdAccessCommands):
    authz = bofhd_auth.AccessAuth


class ApiKeyCommands(bofhd_apikey_cmds.BofhdApiKeyCommands):
    authz = bofhd_auth.ApiKeyAuth


class BofhdRequestCommands(bofhd_requests_cmds.BofhdExtension):
    authz = bofhd_auth.BofhdRequestsAuth


class CreateUnpersonalCommands(bofhd_user_create_unpersonal.BofhdExtension):
    authz = bofhd_auth.CreateUnpersonalAuth


class ExtidCommands(bofhd_external_id.BofhdExtidCommands):
    authz = bofhd_auth.ExtidAuth


class GroupRoleCommands(bofhd_group_roles.BofhdGroupRoleCommands):
    authz = bofhd_auth.GroupRoleAuth


class HistoryCommands(bofhd_history_cmds.BofhdHistoryCmds):
    authz = bofhd_auth.HistoryAuth


class OUDiskMappingCommands(bofhd_cmds.BofhdOUDiskMappingCommands):
    authz = bofhd_auth.OUDiskMappingAuth


class OtpCommands(bofhd_otp_cmds.OtpCommands):
    authz = bofhd_auth.OtpAuth


class OuCommands(bofhd_ou_cmds.OuCommands):
    authz = bofhd_auth.OuAuth


class PasswordIssuesCommands(bofhd_pw_issues.BofhdExtension):
    authz = bofhd_auth.PasswordIssuesAuth


class PermCommands(bofhd_perm_cmds.BofhdPermCommands):
    authz = bofhd_auth.PermAuth

    def _find_target_ids(self, entity):
        """ Find all targets that cause "ownership" of entity. """
        target_ids = super(PermCommands, self)._find_target_ids(entity)

        aot = bofhd_auth.BofhdAuthOpTarget(self.db)

        # uio-specific disk ownership:
        # Anyone who has privileged access to a disk also has privileged
        # acccess to accounts with homedirs there
        if entity.entity_type == self.const.entity_account:
            disk = Utils.Factory.get('Disk')(self.db)
            try:
                tmp = entity.get_home(self.const.spread_uio_nis_user)
                disk.find(tmp['disk_id'])
            except Errors.NotFoundError:
                self.logger.warn("Unknown disk for account_id=%r",
                                 entity.entity_id)
                return target_ids

            for r in aot.list(target_type='global_host'):
                target_ids.add(r['op_target_id'])

            for r in aot.list(target_type='disk',
                              entity_id=int(disk.entity_id)):
                target_ids.add(r['op_target_id'])

            for r in aot.list(target_type='host', entity_id=int(disk.host_id)):
                if (not r['attr'] or re.match(r['attr'],
                                              disk.path.split("/")[-1])):
                    target_ids.add(r['op_target_id'])
        return target_ids


class QuarantineCommands(bofhd_quarantines.BofhdQuarantineCommands):
    authz = bofhd_auth.QuarantineAuth


class SmsCommands(bofhd_misc_sms.BofhdSmsCommands):
    authz = bofhd_auth.SmsAuth


class TraitCommands(bofhd_trait_cmds.TraitCommands):
    authz = bofhd_auth.TraitAuth

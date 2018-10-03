# -*- coding: utf-8 -*-
#
# Copyright 2002-2018 University of Oslo, Norway
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
"""This class contains the bofh-functions needed by the indigo web interface,
but some commands are also available for jbofh. To avoid code-duplication we
re-use a number of commands from the uio-module.

To modify permissions, temporary start a separate bofhd with the normal
bofhd_uio_cmds so that the perm commands are available.

"""
import imaplib
import socket

import mx
from six import text_type

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils import json
from Cerebrum.modules import Email
from Cerebrum.modules.bofhd import bofhd_contact_info
from Cerebrum.modules.bofhd import bofhd_email
from Cerebrum.modules.bofhd import cmd_param
from Cerebrum.modules.bofhd.auth import (BofhdAuth, BofhdAuthRole,
                                         BofhdAuthOpSet, BofhdAuthOpTarget)
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.bofhd_utils import copy_func, copy_command
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.no.Indigo import bofhd_go_help
from Cerebrum.modules.bofhd.bofhd_contact_info import (
    BofhdContactAuth,
    BofhdContactCommands,
)
from Cerebrum.modules.no.uio.bofhd_uio_cmds import BofhdExtension as base
from Cerebrum.modules.no.uio.bofhd_uio_cmds import ConnectException
from Cerebrum.modules.no.uio.bofhd_uio_cmds import TimeoutException


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


class IndigoAuth(BofhdAuth):
    """ Indigo specific auth. """
    pass


class IndigoContactAuth(IndigoAuth, bofhd_contact_info.BofhdContactAuth):
    """ Indigo specific contact info auth. """
    pass


class IndigoEmailAuth(IndigoAuth, bofhd_email.BofhdEmailAuth):
    """ Indigo specific email auth. """
    pass


# Helper methods from uio
copy_helpers = [
    '_get_disk',
    '_entity_info',
    '_fetch_member_names',
    '_get_cached_passwords',
    '_get_group_opcode',
    '_group_add_entity',
    '_group_count_memberships'
]

# Methods and command definitions from uio
copy_uio = [
    'person_list_user_priorities',
    'group_memberships',
    'group_search',
    'group_list',
    'misc_list_passwords',
    'group_add_entity',
    'group_remove_entity',
    'user_password',
    'spread_add',
    'misc_clear_passwords',
    'person_set_user_priority',
    'trait_info',
    'trait_list',
    'trait_set',
    'trait_remove',
]


@copy_command(
    base,
    'all_commands', 'all_commands',
    commands=['person_find', ])
@copy_command(
    base,
    'all_commands', 'all_commands',
    commands=copy_uio)
@copy_func(
    base,
    methods=copy_uio)
@copy_func(
    base,
    methods=copy_helpers)
class BofhdExtension(BofhdCommonMethods):

    external_id_mappings = {}
    all_commands = {}
    parent_commands = True
    authz = BofhdAuth

    def __init__(self, *args, **kwargs):
        super(BofhdExtension, self).__init__(*args, **kwargs)
        self.external_id_mappings['fnr'] = self.const.externalid_fodselsnr

        # Quick fix to replace the `person_find_uio` hack
        self.__uio_impl = base(*args, **kwargs)

    @property
    def person(self):
        try:
            return self.__person
        except AttributeError:
            self.__person = Factory.get('Person')(self.db)
            return self.__person

    @property
    def ou(self):
        try:
            return self.__ou
        except AttributeError:
            self.__ou = Factory.get('OU')(self.db)
            return self.__ou

    @staticmethod
    def get_help_strings():
        return (bofhd_go_help.group_help,
                bofhd_go_help.command_help,
                bofhd_go_help.arg_help)

    # IVR 2007-03-12 We override UiO's behaviour (since there are no
    # PosixUsers in Indigo by default). Ideally, UiO's bofhd should be split
    # into manageable units that can be plugged in on demand
    all_commands['_group_remove_entity'] = None

    def _group_remove_entity(self, operator, member, group):
        self.ba.can_alter_group(operator.get_entity_id(), group)
        member_name = self._get_name_from_object(member)
        if not group.has_member(member.entity_id):
            return ("%s isn't a member of %s" %
                    (member_name, group.group_name))
        try:
            group.remove_member(member.entity_id)
        except self.db.DatabaseError as m:
            raise CerebrumError("Database error: %s" % m)
        return "OK, removed '%s' from '%s'" % (member_name, group.group_name)

    #
    # group info
    #
    all_commands['group_info'] = cmd_param.Command(
        ("group", "info"),
        cmd_param.GroupName(help_ref="id:gid:name"),
        fs=cmd_param.FormatSuggestion(
            [("Name:         %s\n"
              "Spreads:      %s\n"
              "Description:  %s\n"
              "Expire:       %s\n"
              "Entity id:    %i",
              ("name",
               "spread",
               "description",
               format_day("expire_date"),
               "entity_id")),
             ("Moderator:    %s %s (%s)", ('owner_type', 'owner', 'opset')),
             ("Gid:          %i", ('gid',)),
             ("Members:      %s", ("members",))]))

    def group_info(self, operator, groupname):
        grp = self._get_group(groupname)
        co = self.const
        ret = [self._entity_info(grp), ]
        # find owners
        aot = BofhdAuthOpTarget(self.db)
        targets = []
        for row in aot.list(target_type='group', entity_id=grp.entity_id):
            targets.append(int(row['op_target_id']))
        ar = BofhdAuthRole(self.db)
        aos = BofhdAuthOpSet(self.db)
        for row in ar.list_owners(targets):
            aos.clear()
            aos.find(row['op_set_id'])
            id = int(row['entity_id'])
            en = self._get_entity(ident=id)
            if en.entity_type == co.entity_account:
                owner = en.account_name
            elif en.entity_type == co.entity_group:
                owner = en.group_name
            else:
                owner = '#%d' % id
            ret.append({
                'owner_type': text_type(co.EntityType(en.entity_type)),
                'owner': owner,
                'opset': aos.name,
            })

        # Count group members of different types
        members = list(grp.search_members(group_id=grp.entity_id))
        tmp = {}
        for ret_pfix, entity_type in (
                ('c_group', int(co.entity_group)),
                ('c_account', int(co.entity_account))):
            tmp[ret_pfix] = len([x for x in members
                                 if int(x["member_type"]) == entity_type])
        ret.append(tmp)
        return ret

    #
    # group user
    #
    all_commands['group_user'] = cmd_param.Command(
        ('group', 'user'),
        cmd_param.AccountName(),
        fs=cmd_param.FormatSuggestion(
            "%-9s %-18s", ("memberop", "group")))

    def group_user(self, operator, accountname):
        return self.group_memberships(operator, 'account', accountname)

    #
    # get_auth_level
    #
    all_commands['get_auth_level'] = None

    def get_auth_level(self, operator):
        if self.ba.is_superuser(operator.get_entity_id()):
            return cereconf.INDIGO_AUTH_LEVEL['super']

        if self.ba.is_schoolit(operator.get_entity_id(), True):
            return cereconf.INDIGO_AUTH_LEVEL['schoolit']

        return cereconf.INDIGO_AUTH_LEVEL['other']

    #
    # list_defined_spreads
    #
    all_commands['list_defined_spreads'] = None

    def list_defined_spreads(self, operator):
        return [{
            'code_str': text_type(y),
            'desc': y.description,
            'entity_type': text_type(self.const.EntityType(y.entity_type)),
        } for y in self.const.fetch_constants(self.const.Spread)]

    #
    # get_entity_spreads
    #
    all_commands['get_entity_spreads'] = None

    def get_entity_spreads(self, operator, entity_id):
        entity = self._get_entity(ident=int(entity_id))
        to_spread = self.const.Spread
        return [
            {
                'spread': text_type(to_spread(row['spread'])),
                'spread_desc': to_spread(row['spread']).description,
            }
            for row in entity.get_spread()
        ]

    #
    # get_default_email
    #
    all_commands['get_default_email'] = None

    def get_default_email(self, operator, entity_id):
        account = self._get_account(entity_id)
        try:
            return account.get_primary_mailaddress()
        except Errors.NotFoundError:
            return "No e-mail addresse available for %s" % account.account_name

    #
    # get_create_date
    #
    all_commands['get_create_date'] = None

    def get_create_date(self, operator, entity_id):
        account = self._get_account(entity_id)
        return account.created_at

    #
    # user_get_pwd
    #
    all_commands['user_get_pwd'] = None

    def user_get_pwd(self, operator, id):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        account = self._get_account(int(id), 'id')
        pwd = account.get_account_authentication(
            self.const.auth_type_plaintext)
        return {'password': pwd,
                'uname': account.account_name}

    #
    # list_active
    #
    all_commands['list_active'] = None

    def list_active(self, operator):
        active = list()
        # IVR 2007-03-11 fetch the source system, which determines people that
        # are considered 'active'.
        source = int(getattr(self.const, cereconf.INDIGO_ACTIVE_SOURCE_SYSTEM))
        for row in self.person.list_affiliations(source_system=source):
            active.append(row['person_id'])
        return active

    #
    # user info [username]
    #
    all_commands['user_info'] = cmd_param.Command(
        ("user", "info"),
        cmd_param.AccountName(),
        fs=cmd_param.FormatSuggestion(
            "Entity id:      %d\n"
            "Owner id:       %d\n"
            "Owner type:     %d\n",
            ("entity_id", "owner_id", "owner_type")))

    def user_info(self, operator, entity_id):
        """ Account info. """
        account = self._get_account(entity_id)
        return {'entity_id': account.entity_id,
                'owner_id': account.owner_id,
                'owner_type': account.owner_type}

    #
    # person_info <id>
    #
    all_commands['person_info'] = cmd_param.Command(
        ("person", "info"),
        cmd_param.PersonId(help_ref="id:target:person"),
        fs=cmd_param.FormatSuggestion([
            ("Name:          %s\n"
             "Entity-id:     %i\n"
             "Export-id:     %s\n"
             "Birth:         %s",
             ("name", "entity_id", "export_id", "birth")),
            ("Affiliation:   %s@%s (%i) [from %s]",
             ("affiliation", "aff_sted_desc", "ou_id", "source_system")),
            ("Fnr:           %s [from %s]",
             ("fnr", "fnr_src")),
        ]))

    def person_info(self, operator, person_id):
        """ Person info for Cweb. """
        try:
            person = self._get_person(*self._map_person_id(person_id))
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        data = [{'name': person.get_name(self.const.system_cached,
                                         getattr(self.const,
                                                 cereconf.DEFAULT_GECOS_NAME)),
                 'export_id': person.export_id,
                 'birth': person.birth_date,
                 'entity_id': person.entity_id}]

        for row in person.get_affiliations():
            ou = self._get_ou(ou_id=row['ou_id'])
            data.append(
                {'aff_sted_desc': ou.get_name_with_language(
                    name_variant=self.const.ou_name,
                    name_language=self.const.language_nb,
                    default=""),
                 'aff_type': text_type(
                     self.const.PersonAffiliation(row['affiliation'])),
                 'aff_status': text_type(
                     self.const.PersonAffStatus(row['status'])),
                 'ou_id': row['ou_id'],
                 'affiliation': text_type(
                     self.const.PersonAffStatus(row['status'])),
                 'source_system': text_type(
                     self.const.AuthoritativeSystem(row['source_system'])), })

        account = self.Account_class(self.db)
        account_ids = [int(r['account_id']) for r in
                       account.list_accounts_by_owner_id(person.entity_id)]
        if (self.ba.is_schoolit(operator.get_entity_id(), True)
                or operator.get_entity_id() in account_ids):
            for row in person.get_external_id(
                    id_type=self.const.externalid_fodselsnr):
                data.append({
                    'fnr': row['external_id'],
                    'fnr_src': text_type(
                        self.const.AuthoritativeSystem(row['source_system'])),
                })
        return data

    #
    # person_find
    #
    all_commands['person_find'] = None

    def person_find(self, operator, search_type, value, filter=None):
        """Indigo-specific wrapper and filter around UiO's open person_find."""

        if not self.ba.is_schoolit(operator.get_entity_id(), True):
            raise PermissionDenied("Limited to school IT and superusers")

        results = self.__uio_impl.person_find(operator,
                                              search_type,
                                              value,
                                              filter)
        return self._filter_resultset_by_operator(operator, results, "id")

    #
    # person_accounts
    #
    all_commands['person_accounts'] = None

    def person_accounts(self, operator, id):
        """person_accounts with restrictions for Indigo.

        This is a copy of UiO's method, except for result
        filtering/permission check.
        """

        person = self.util.get_target(id, restrict_to=['Person', 'Group'])
        if not (self.ba.is_schoolit(operator.get_entity_id(), True) or
                operator.get_owner_id() == person.entity_id):
            raise PermissionDenied("Limited to school IT and superusers")

        if not self._operator_sees_person(operator, person.entity_id):
            return []

        account = self.Account_class(self.db)
        ret = []
        for r in account.list_accounts_by_owner_id(
                person.entity_id,
                owner_type=person.entity_type,
                filter_expired=False):
            account = self._get_account(r['account_id'], idtype='id')

            ret.append({'account_id': r['account_id'],
                        'name': account.account_name,
                        'expire': account.expire_date})
        ret.sort(lambda a, b: cmp(a['name'], b['name']))
        return ret

    #
    # user_create
    #
    all_commands['user_create'] = None

    def user_create(self, operator, uname, owner_id):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        account = self.Account_class(self.db)
        entity = self._get_entity(ident=int(owner_id))
        if entity.entity_type == int(self.const.entity_person):
            np_type = None
        else:
            # TODO: What value?  Or drop-down?
            np_type = self.const.account_program

        account.populate(uname, entity.entity_type, owner_id, np_type,
                         operator.get_entity_id(), None)
        passwd = account.make_passwd(uname)
        account.set_password(passwd)
        account.write_db()
        operator.store_state("new_account_passwd", {
            'account_id': int(account.entity_id),
            'password': passwd})
        return "Ok, user created"

    #
    # user_suggest_name
    #
    all_commands['user_suggest_uname'] = None

    def user_suggest_uname(self, operator, owner_id):
        person = self._get_person("entity_id", owner_id)
        fname, lname = [person.get_name(self.const.system_cached, v)
                        for v in (self.const.name_first, self.const.name_last)]
        account = self.Account_class(self.db)
        return account.suggest_unames(self.const.account_namespace,
                                      fname, lname)

    #
    # user_find
    #
    all_commands['user_find'] = None

    def user_find(self, operator, search_type, search_value):
        "Locate users whose unames loosely matches 'search_value'."

        if not self.ba.is_schoolit(operator.get_entity_id(), True):
            raise PermissionDenied("Limited to superusers and school IT"
                                   " admins")

        if search_type != 'uname':
            raise CerebrumError("Unknown search type (%s)" % search_type)

        if len(search_value.strip(" \t%_*?")) < 3:
            raise CerebrumError("You must specify at least three non-wildcard"
                                " letters")

        # if there are no wildcards in the pattern, add them
        if not [wildcard for wildcard in "_%?*" if wildcard in search_value]:
            search_value = '*' + search_value.replace(' ', '*') + '*'

        account = Factory.get("Account")(self.db)
        matches = list(
            account.search(name=search_value,
                           owner_type=int(self.const.entity_person)))
        # prepare the return value
        ret = list()
        seen = dict()
        if len(matches) > 250:
            raise CerebrumError("More than 250 (%d) matches, please narrow "
                                "search criteria" % len(matches))

        for row in matches:
            account_id = row['account_id']
            if account_id in seen:
                continue

            seen[account_id] = True
            account.clear()
            account.find(account_id)
            person = self._get_person("entity_id", int(account.owner_id))
            owner_name = person.get_name(self.const.system_cached,
                                         getattr(self.const,
                                                 cereconf.DEFAULT_GECOS_NAME))
            ret.append({'account_id': account_id,
                        'name': row['name'],
                        'owner_id': account.owner_id,
                        'owner_name': owner_name,
                        'birth': person.birth_date})

        # school lita can see their own schools only!
        ret = self._filter_resultset_by_operator(operator, ret, "owner_id")

        ret.sort(lambda a, b: cmp(a["name"], b["name"]))
        return ret

    def _operator_sees_person(self, operator, person_id):
        """Decide if operator can obtain information about person_id.

        Superusers can see information about everyone. People can see their
        own information as well.

        Additionally, school IT may see everyone who is affiliated with an OU
        that they have permissions for.
        """

        # superusers and own information
        if (self.ba.is_superuser(operator.get_entity_id(), True)
                or operator.get_owner_id() == person_id):
            return True

        # non-LITAs cannot see anyone else
        if not self.ba.is_schoolit(operator.get_entity_id(), True):
            return False

        # ... but LITAs can
        operators_ou = set(self._operators_ou(operator))
        targets_ou = set([x['ou_id'] for x in
                          self.person.list_affiliations(
                              person_id=int(person_id))])
        return bool(operators_ou.intersection(targets_ou))

    def _operator_sees_ou(self, operator, ou_id):
        """Decide if operator can obtain information about ou_id.

        Superusers can see information about anything. School IT can only see
        info about the schools where they have school IT permissions.
        """

        if self.ba.is_superuser(operator.get_entity_id(), True):
            return True

        if not self.ba.is_schoolit(operator.get_entity_id(), True):
            return False

        operators_ou = set(self._operators_ou(operator))
        return int(ou_id) in operators_ou

    def _filter_resultset_by_operator(self, operator, results, person_key):
        """Remove elements from results to which operator has no access.

        In general, a school lita should not 'see' any results outside of his
        school. This means that the list of users and people returned to
        him/her has to be filtered.

        operator    operator (person_id)
        results     a sequency of dictionary-like objects where each object
                    represents a database row. These are to be filtered.
        person_key  name of the key in each element of results that
                    designates the owner.

        Caveats:
        * This method is quite costly. It gets more so, the larger the schools
          are.
        * This method will not help with group filtering.
        """

        # never filter superusers' results
        if self.ba.is_superuser(operator.get_entity_id(), True):
            return results

        # The operation is performed in three steps:
        # 1) fetch all OUs where that the operator can "see".
        # 2) fetch all people affiliated with OUs in #1
        # 3) intersect results with #2

        # Find operator's OUs
        operators_ou = self._operators_ou(operator)

        # Find all people affiliated with operator's OUs
        operators_people = set([x['person_id'] for x in
                                self.person.list_affiliations(
                                    ou_id=operators_ou)])
        # Filter the results...
        filtered_set = list()
        for element in results:
            if element[person_key] in operators_people:
                filtered_set.append(element)

        return type(results)(filtered_set)

    def _operators_ou(self, operator):
        """Return a sequence of OUs that operator can 'see'.

        Superusers see everything.
        School IT see only the OUs where they have privileges.
        Everyone else sees nothing.
        """

        def grab_all_ous():
            return [int(x['ou_id']) for x in
                    self.ou.search(filter_quarantined=False)]

        if self.ba.is_superuser(operator.get_entity_id(), True):
            return grab_all_ous()

        if not self.ba.is_schoolit(operator.get_entity_id(), True):
            return []

        group = self.Group_class(self.db)
        # fetch all groups where operator is a member
        op_groups = [x['group_id'] for x in
                     group.search(member_id=operator.get_entity_id(),
                                  indirect_members=False)]
        # fetch all permissions that these groups have
        op_targets = [x['op_target_id'] for x in
                      BofhdAuthRole(self.db).list(entity_ids=op_groups)]

        # Now, finally, the permissions:
        result = list()
        for permission in BofhdAuthOpTarget(self.db).list(
                target_id=op_targets,
                target_type=self.const.auth_target_type_ou,):
            if permission["entity_id"] is not None:
                result.append(int(permission["entity_id"]))
            else:
                # AHA! We have a general OU permission. Grab them all!
                return grab_all_ous()

        return result

    #
    # misc history <num-days>
    #
    all_commands['misc_history'] = cmd_param.Command(
        ('misc', 'history'),
        cmd_param.SimpleString())

    def misc_history(self, operator, days):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")

        types = (self.clconst.account_create, self.clconst.account_password,
                 self.clconst.ou_create, self.clconst.person_create)
        sdate = mx.DateTime.now() - mx.DateTime.oneDay * int(days)
        # Collect in a dict to remove duplicates etc.
        tmp = {}
        for r in self.db.get_log_events(sdate=sdate, types=types):
            tmp.setdefault(int(r['subject_entity']),
                           {})[int(r['change_type_id'])] = r

        ret = []
        for entity_id, changes in tmp.items():
            if (int(self.clconst.account_password) in changes
                    and int(self.clconst.account_create) not in changes):
                # TBD: naa er det OK aa vise passordet?
                del(changes[int(self.clconst.account_password)])

            for k, v in changes.items():
                change_type = self.clconst.ChangeType(int(k))
                params = ''
                if k == self.const.account_password:
                    if v['change_params']:
                        params = json.loads(v['change_params'])
                        params = params.get('password', '')
                tmp = {
                    'tstamp': v['tstamp'],
                    # 'change_type': str(cl),
                    'change_type': text_type(change_type),
                    'misc': params,
                }
                entity = self._get_entity(ident=int(v['subject_entity']))
                if entity.entity_type == int(self.const.entity_person):
                    person = self._get_person("entity_id", entity.entity_id)
                    name = person.get_name(self.const.system_cached,
                                           self.const.name_full)
                    tmp['person_id'] = int(person.entity_id)
                elif entity.entity_type == int(self.const.entity_account):
                    account = self.Account_class(self.db)
                    account.find(entity.entity_id)
                    name = account.account_name
                    tmp['person_id'] = int(account.owner_id)
                else:
                    self.ou.clear()
                    self.ou.find(entity.entity_id)
                    name = self.ou.get_name_with_language(
                        name_variant=self.const.ou_name,
                        name_language=self.const.language_nb,
                        default="")
                tmp['name'] = name
                ret.append(tmp)
        return ret

    #
    # find_school <name>
    #
    all_commands['find_school'] = None

    def find_school(self, operator, name):

        if not self.ba.is_schoolit(operator.get_entity_id(), True):
            raise PermissionDenied("Currently limited to superusers and"
                                   " school IT")

        # name could be an acronym or a "regular" name
        result = set()
        for name_variant in (self.const.ou_name, self.const.ou_name_acronym):
            result.update(r["entity_id"]
                          for r in
                          self.ou.search_name_with_language(
                              entity_type=self.const.entity_ou,
                              name_variant=name_variant,
                              name=name,
                              name_language=self.const.language_nb,
                              exact_match=False))

        if len(result) == 0:
            raise CerebrumError("Could not find school matching %s" % name)
        elif len(result) > 1:
            raise CerebrumError("Found several schools with matching names")

        # Now there is just one left. But can the operator see it?
        ou_id = result.pop()
        # filter the results for school IT
        if not self._operator_sees_ou(operator, ou_id):
            raise CerebrumError("School information is unavailable for this"
                                " user")
        else:
            return ou_id

    #
    # get_password_information <entity_id>
    #
    all_commands["get_password_information"] = None

    def get_password_information(self, operator, entity_id):
        """Retrieve information about password changes for entity_id.

        This function helps implement a command in Giske's cweb.
        """

        self.logger.debug("Processing for id=%s", entity_id)
        entity_id = int(entity_id)
        result = {}
        for row in operator.get_state():
            if row["state_data"] is None:
                continue
            if entity_id != row["state_data"]["account_id"]:
                continue
            if row["state_type"] not in ("new_account_passwd", "user_passwd"):
                continue

            result = {
                "account_id": entity_id,
                "uname": self._get_entity_name(entity_id,
                                               self.const.entity_account),
                "password": row["state_data"]["password"],
            }
            account = self._get_entity(ident=entity_id)
            owner = self._get_entity(ident=account.owner_id)
            result["name"] = self._get_entity_name(owner.entity_id,
                                                   owner.entity_type)
            if owner.entity_type == self.const.entity_person:
                result["birth_date"] = owner.birth_date
                # Main affiliation points to school.
                affs = account.list_accounts_by_type(
                    primary_only=True,
                    person_id=owner.entity_id,
                    account_id=account.entity_id)
                if affs:
                    ou = self._get_entity(ident=affs[0]["ou_id"])
                    ou_name = ou.get_name_with_language(
                        name_variant=self.const.ou_name,
                        name_language=self.const.language_nb,
                        default="")
                    result["institution_name"] = ou_name
                else:
                    result["institution_name"] = "n/a"
            else:
                result["birth_date"] = "n/a"
                result["institution_name"] = "n/a"
        return result

    @classmethod
    def get_format_suggestion(cls, cmd):
        return cls.all_commands[cmd].get_fs()

    def _format_ou_name(self, ou):
        binds = {"name_language": self.const.language_nb,
                 "default": ""}
        return (
            ou.get_name_with_language(name_variant=self.const.ou_name_short,
                                      **binds)
            or ou.get_name_with_language(name_variant=self.const.ou_name,
                                         **binds))

    def _email_info_detail(self, acc):
        """ Get quotas from Cerebrum, and usage from Cyrus. """
        # NOTE: Very similar to hiof and uio

        info = []
        eq = Email.EmailQuota(self.db)

        # Get quota and usage
        try:
            eq.find_by_target_entity(acc.entity_id)
            et = Email.EmailTarget(self.db)
            et.find_by_target_entity(acc.entity_id)
            es = Email.EmailServer(self.db)
            es.find(et.email_server_id)

            if es.email_server_type == self.const.email_server_type_cyrus:
                used = 'N/A'
                limit = None
                pw = self.db._read_password(cereconf.CYRUS_HOST,
                                            cereconf.CYRUS_ADMIN)
                try:
                    cyrus = imaplib.IMAP4(es.name)
                    # IVR 2007-08-29 If the server is too busy, we do not want
                    # to lock the entire bofhd.
                    # 5 seconds should be enough
                    cyrus.socket().settimeout(5)
                    cyrus.login(cereconf.CYRUS_ADMIN, pw)
                    res, quotas = cyrus.getquota("user." + acc.account_name)
                    cyrus.socket().settimeout(None)
                    if res == "OK":
                        for line in quotas:
                            try:
                                folder, qtype, qused, qlimit = line.split()
                                if qtype == "(STORAGE":
                                    used = str(int(qused)/1024)
                                    limit = int(qlimit.rstrip(")"))/1024
                            except ValueError:
                                # line.split fails e.g. because quota isn't set
                                # on server
                                folder, junk = line.split()
                                self.logger.warning(
                                    "No IMAP quota set for '%s'" %
                                    acc.account_name)
                                used = "N/A"
                                limit = None
                except (TimeoutException, socket.error):
                    used = 'DOWN'
                except ConnectException as e:
                    used = text_type(e)
                except imaplib.IMAP4.error:
                    used = 'DOWN'
                info.append({'quota_hard': eq.email_quota_hard,
                             'quota_soft': eq.email_quota_soft,
                             'quota_used': used})
                if limit is not None and limit != eq.email_quota_hard:
                    info.append({'quota_server': limit})
            else:
                # Just get quotas
                info.append({'dis_quota_hard': eq.email_quota_hard,
                             'dis_quota_soft': eq.email_quota_soft})
        except Errors.NotFoundError:
            pass
        return info

    # Commands for Exchange migration:

    #
    # user migrate_exchange [username] [mdb]
    #
    all_commands['user_migrate_exchange'] = cmd_param.Command(
        ("user", "migrate_exchange"),
        cmd_param.AccountName(help_ref="account_name", repeat=False),
        cmd_param.SimpleString(help_ref='string_mdb'),
        perm_filter='is_superuser')

    def user_migrate_exchange(self, operator, uname, mdb):
        """Tagging a user as under migration, and setting the new MDB.

        The new MDB value should not be used until the user is tagged as
        successfully migrated.

        """
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        account = self._get_account(uname)
        # TODO: check the new MDB value?

        # Set new mdb value
        account.populate_trait(self.const.trait_homedb_info, strval=mdb)
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
        """Tagging a user as migrated to a newer Exchange version."""
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        account = self._get_account(uname)
        if not account.get_trait(self.const.trait_exchange_under_migration):
            raise CerebrumError("Account %s not under migration" % uname)
        # Mark that account is successfully migrated to new exchange server
        account.populate_trait(self.const.trait_exchange_migrated)
        account.write_db()
        # Remove trait for being under migration
        account.delete_trait(self.const.trait_exchange_under_migration)
        account.write_db()
        return "OK, deleted trait for user %s" % uname


class ContactCommands(bofhd_contact_info.BofhdContactCommands):
    authz = IndigoContactAuth


@copy_command(
    bofhd_email.BofhdEmailCommands,
    'all_commands', 'all_commands',
    commands=[
        'email_address_add',
        'email_address_remove',
        'email_info',
    ]
)
class EmailCommands(bofhd_email.BofhdEmailCommands):
    """ Indigo specific email commands and overloads. """

    all_commands = {}
    hidden_commands = {}
    parent_commands = False  # copied with copy_command
    omit_parent_commands = set()
    authz = IndigoEmailAuth

# -*- coding: iso-8859-1 -*-

# Copyright 2002-2007 University of Oslo, Norway
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

import cereconf

import mx
import pickle
import re

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum import Constants
from Cerebrum import Utils
from Cerebrum import Cache
from Cerebrum import Errors
from Cerebrum.modules import Email
from Cerebrum.modules.bofhd.cmd_param import *
from Cerebrum.Constants import _CerebrumCode
from Cerebrum.modules.bofhd.auth import BofhdAuth, BofhdAuthRole, \
                                        BofhdAuthOpSet, BofhdAuthOpTarget
from Cerebrum.modules.bofhd.utils import _AuthRoleOpCode
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.extlib.sets import Set as set
from Cerebrum.modules.no.Indigo import bofhd_go_help


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


class BofhdExtension(BofhdCommonMethods):
    Account_class = Factory.get('Account')
    Group_class = Factory.get('Group')
    OU_class = Factory.get('OU')
    all_commands = {}

    copy_commands = (
        '_get_account', '_get_person', '_get_disk',
        '_get_group', '_map_person_id', '_parse_date', '_get_entity',
        'group_user', 'person_list_user_priorities',
        'group_memberships', 'group_search',
        '_entity_info', 'num2str', 'group_list',
        '_fetch_member_names', 'misc_list_passwords',
        '_get_cached_passwords',
        '_get_entity_spreads',
        'group_add_entity', 'group_remove_entity', 'user_password',
        '_get_group_opcode', '_get_name_from_object',
        '_group_add_entity', '_group_count_memberships',
        'spread_add', '_get_constant',
        'misc_clear_passwords', 'person_set_user_priority',
        'email_add_address', 'email_remove_address',
        'email_info', '_email_info_basic', '_email_info_account', 
        '_email_info_spam', '_email_info_forwarding', '_email_info_filters',

        'trait_info', 'trait_list', 'trait_set', 'trait_remove',

        '_get_address', '_remove_email_address', '_split_email_address', 
        '_get_email_domain', )

    def __new__(cls, *arg, **karg):
        # A bit hackish.  A better fix is to split bofhd_uio_cmds.py
        # into seperate classes.
        from Cerebrum.modules.no.uio.bofhd_uio_cmds import BofhdExtension as \
             UiOBofhdExtension

        for func in BofhdExtension.copy_commands:
            setattr(cls, func, UiOBofhdExtension.__dict__.get(func))
            if func[0] != '_' and func not in ('num2str',):
                BofhdExtension.all_commands[func] = UiOBofhdExtension.all_commands[func]

        # we'll need to call these from our own wrappers. Basically,
        # an UiO command is *almost* what we need.
        for func in ('person_find',):
            setattr(cls, func + "_uio", UiOBofhdExtension.__dict__.get(func))

        x = object.__new__(cls)
        return x

    def __init__(self, server, default_zone='uio'):
        super(BofhdExtension, self).__init__(server)
        self.server = server
        self.logger = server.logger
        self.db = server.db
        self.util = server.util
        self.const = Factory.get('Constants')(self.db)
        self.person = Factory.get('Person')(self.db)
        self.ou = Factory.get('OU')(self.db)
        self.ba = BofhdAuth(self.db)

        # From uio
        self.num2const = {}
        self.str2const = {}
        for c in dir(self.const):
            tmp = getattr(self.const, c)
            if isinstance(tmp, _CerebrumCode):
                self.num2const[int(tmp)] = tmp
                self.str2const[str(tmp)] = tmp
        self._cached_client_commands = Cache.Cache(mixins=[Cache.cache_mru,
                                                           Cache.cache_slots,
                                                           Cache.cache_timeout],
                                                   size=500,
                                                   timeout=60*60)
        # Copy in all defined commands from the superclass that is not defined
        # in this class.
        for key, cmd in super(BofhdExtension, self).all_commands.iteritems():
            if not self.all_commands.has_key(key):
                self.all_commands[key] = cmd


    def get_help_strings(self):
        return (bofhd_go_help.group_help,
                bofhd_go_help.command_help,
                bofhd_go_help.arg_help)
    
    def get_commands(self, account_id):
        try:
            return self._cached_client_commands[int(account_id)]
        except KeyError:
            pass
        commands = {}
        for k in self.all_commands.keys():
            tmp = self.all_commands[k]
            if tmp is not None:
                if tmp.perm_filter:
                    if not getattr(self.ba, tmp.perm_filter)(account_id, query_run_any=True):
                        continue
                commands[k] = tmp.get_struct(self)
        self._cached_client_commands[int(account_id)] = commands
        return commands

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
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return "OK, removed '%s' from '%s'" % (member_name, group.group_name)

    # group info
    all_commands['group_info'] = Command(
        ("group", "info"), GroupName(help_ref="id:gid:name"),
        fs=FormatSuggestion([("Name:         %s\n" +
                              "Spreads:      %s\n" +
                              "Description:  %s\n" +
                              "Expire:       %s\n" +
                              "Entity id:    %i""",
                              ("name", "spread", "description",
                               format_day("expire_date"),
                               "entity_id")),
                             ("Moderator:    %s %s (%s)",
                              ('owner_type', 'owner', 'opset')),
                             ("Gid:          %i",
                              ('gid',)),
                             ("Members:      %s", ("members",))]))
    def group_info(self, operator, groupname):
        grp = self._get_group(groupname)
        co = self.const
        ret = [ self._entity_info(grp) ]
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
            ret.append({'owner_type': str(co.EntityType(en.entity_type)),
                        'owner': owner,
                        'opset': aos.name})

        # Count group members of different types
        members = list(grp.search_members(group_id=grp.entity_id))
        tmp = {}
        for ret_pfix, entity_type in (
            ('c_group', int(self.const.entity_group)),
            ('c_account', int(self.const.entity_account))):
            tmp[ret_pfix] = len([x for x in members
                                 if int(x["member_type"]) == entity_type])
        ret.append(tmp)
        return ret

    all_commands['get_auth_level'] = None
    def get_auth_level(self, operator):
        if self.ba.is_superuser(operator.get_entity_id()):
            return cereconf.BOFHD_AUTH_LEVEL['super']

        if self.ba.is_schoolit(operator.get_entity_id(), True):
            return cereconf.BOFHD_AUTH_LEVEL['schoolit']

        return cereconf.BOFHD_AUTH_LEVEL['other']

    all_commands['list_defined_spreads'] = None
    def list_defined_spreads(self, operator):
        return [{'code_str': str(y),
                 'desc': y._get_description(),
                 'entity_type': str(self.const.EntityType(y.entity_type))}
                for y in self.const.fetch_constants(self.const.Spread)]

    all_commands['get_entity_spreads'] = None
    def get_entity_spreads(self, operator, entity_id):
        entity = self._get_entity(ident=int(entity_id))
        return [{'spread': str(self.const.Spread(int(row['spread']))),
                 'spread_desc': self.const.Spread(int(row['spread']))._get_description()}
                for row in entity.get_spread()]

    all_commands['get_default_email'] = None
    def get_default_email(self, operator, entity_id):
        account = self._get_account(entity_id)
        try:
            primary_email_address = account.get_primary_mailaddress()
        except Errors.NotFoundError:
            primary_email_address = "No e-mail addresse available for %s" % account.account_name
        return primary_email_address

    all_commands['get_create_date'] = None
    def get_create_date(self, operator, entity_id):
        account = self._get_account(entity_id)
        return account.create_date

    all_commands['user_get_pwd'] = None
    def user_get_pwd(self, operator, id):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        account = self._get_account(int(id),'id')
        pwd = account.get_account_authentication(self.const.auth_type_plaintext)
        return {'password': pwd,
                'uname': account.account_name}

    all_commands['list_active'] = None
    def list_active(self, operator):
        active = list()
        # IVR 2007-03-11 fetch the source system, which determines people that
        # are considered 'active'.
        source = int(getattr(self.const, cereconf.CWEB_ACTIVE_SOURCE_SYSTEM))
        for row in self.person.list_affiliations(source_system=source):
            active.append(row['person_id'])
        return active

    all_commands['user_info'] = Command(
        ("user", "info"), AccountName(),
        fs=FormatSuggestion("Entity id:      %d\n" +
                            "Owner id:       %d\n" +
                            "Owner type:     %d\n",
                            ("entity_id", "owner_id", "owner_type")))
    def user_info(self, operator, entity_id):
        account = self._get_account(entity_id)
        return {'entity_id': account.entity_id,
                'owner_id': account.owner_id,
                'owner_type': account.owner_type}

    all_commands['person_info'] = Command(
        ("person", "info"), PersonId(help_ref="id:target:person"),
        fs=FormatSuggestion([
        ("Name:          %s\n" +
         "Entity-id:     %i\n" +
         "Birth:         %s\n" +
         "Spreads:       %s\n" +
         "Affiliations:  %s [from %s]",
         ("name", "entity_id", "birth", "spreads",
          "affiliation_1", "source_system_1")),
        ("               %s [from %s]",
         ("affiliation", "source_system")),
        ("Names:         %s[from %s]",
         ("names", "name_src")),
        ("Fnr:           %s [from %s]",
         ("fnr", "fnr_src")),
        ("Contact:       %s: %s [from %s]",
         ("contact_type", "contact", "contact_src")),
        ("External id:   %s [from %s]",
         ("extid", "extid_src"))
        ]))
    def person_info(self, operator, person_id):
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
            data.append({'aff_sted_desc': ou.get_name_with_language(
                                                 name_variant=self.const.ou_name,
                                                 name_language=self.const.language_nb,
                                                 default=""),
                         'aff_type': str(self.const.PersonAffiliation(row['affiliation'])),
                         'aff_status': str(self.const.PersonAffStatus(row['status'])),
                         'ou_id': row['ou_id'],
                         'affiliation':
                           str(self.const.PersonAffStatus(row['status'])),
                         'source_system':
                           str(self.const.AuthoritativeSystem(row['source_system'])),})
        
        account = self.Account_class(self.db)
        account_ids = [int(r['account_id'])
                       for r in account.list_accounts_by_owner_id(person.entity_id)]
        if (self.ba.is_schoolit(operator.get_entity_id(), True) or
            operator.get_entity_id() in account_ids):
            for row in person.get_external_id(id_type=self.const.externalid_fodselsnr):
                data.append({'fnr': row['external_id'],
                             'fnr_src': str(
                    self.const.AuthoritativeSystem(row['source_system']))})
        return data


    all_commands['person_find'] = None
    def person_find(self, operator, search_type, value, filter=None):
        """Indigo-specific wrapper and filter around UiO's open person_find."""

        if not self.ba.is_schoolit(operator.get_entity_id(), True):
            raise PermissionDenied("Limited to school IT and superusers")

        results = self.person_find_uio(operator, search_type, value, filter)
        return self._filter_resultset_by_operator(operator, results, "id")
    # end person_find


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
        for r in account.list_accounts_by_owner_id(person.entity_id,
                                                   owner_type=person.entity_type,
                                                   filter_expired=False):
            account = self._get_account(r['account_id'], idtype='id')

            ret.append({'account_id': r['account_id'],
                        'name': account.account_name,
                        'expire': account.expire_date})
        ret.sort(lambda a,b: cmp(a['name'], b['name']))
        return ret
    # end person_accounts

    all_commands['user_create'] = None
        # TODO: Consider if they should have this command through jbofh too:
        # Command( ("user", "create"), AccountName(), PersonId('entity_id'))
    def user_create(self, operator, uname, owner_id):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        account = self.Account_class(self.db)
        entity = self._get_entity(ident=int(owner_id))
        if entity.entity_type == int(self.const.entity_person):
            np_type=None
        else:
            np_type = self.const.account_program  # TODO: What value?  Or drop-down?

        account.populate(uname, entity.entity_type, owner_id, np_type,
                         operator.get_entity_id(), None)
        passwd = account.make_passwd(uname)
        account.set_password(passwd)
        account.write_db()
        operator.store_state("new_account_passwd", {
            'account_id': int(account.entity_id),
            'password': passwd})
        return "Ok, user created"

    all_commands['user_suggest_uname'] = None
    def user_suggest_uname(self, operator, owner_id):
        person = self._get_person("entity_id", owner_id)
        fname, lname = [person.get_name(self.const.system_cached, v)
                        for v in (self.const.name_first, self.const.name_last) ]
        account = self.Account_class(self.db)
        return account.suggest_unames(self.const.account_namespace, fname, lname)


    all_commands['user_find'] = None
    def user_find(self, operator, search_type, search_value):
        "Locate users whose unames loosely matches 'search_value'."

        if not self.ba.is_schoolit(operator.get_entity_id(), True):
            raise PermissionDenied("Limited to superusers and school IT admins")

        if search_type != 'uname':
            raise CerebrumError("Unknown search type (%s)" % search_type)

        if len(search_value.strip(" \t%_*?")) < 3:
            raise CerebrumError("You must specify at least three non-wildcard letters")

        # if there are no wildcards in the pattern, add them
        if not [wildcard for wildcard in "_%?*" if wildcard in search_value]:
            search_value = '*' + search_value.replace(' ', '*') + '*'

        account = Factory.get("Account")(self.db)
        matches = list(account.search(name=search_value,
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
    # end user_find


    def _operator_sees_person(self, operator, person_id):
        """Decide if operator can obtain information about person_id.

        Superusers can see information about everyone. People can see their
        own information as well.

        Additionally, school IT may see everyone who is affiliated with an OU
        that they have permissions for.
        """

        # superusers and own information
        if (self.ba.is_superuser(operator.get_entity_id(), True) or
            operator.get_owner_id() == person_id):
            return True

        # non-LITAs cannot see anyone else
        if not self.ba.is_schoolit(operator.get_entity_id(), True):
            return False

        # ... but LITAs can
        operators_ou = set(self._operators_ou(operator))
        targets_ou = set([x['ou_id'] for x in
                         self.person.list_affiliations(person_id=int(person_id))])
        
        return bool(operators_ou.intersection(targets_ou))
    # end _operator_sees_person


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
    # end _operator_sees_ou
        

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
        * This method is quite costly. It gets more so, the larger the schools are.
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
    # end _filter_resultset_by_operator


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
    # end _operators_ou


    all_commands['misc_history'] = None
    def misc_history(self, operator, days):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")

        types = (self.const.account_create, self.const.account_password,
                 self.const.ou_create, self.const.person_create)
        sdate = mx.DateTime.now() - mx.DateTime.oneDay * int(days)
        # Collect in a dict to remove duplicates etc.
        tmp = {}
        for r in self.db.get_log_events(sdate=sdate, types=types):
            tmp.setdefault(int(r['subject_entity']), {})[int(r['change_type_id'])] = r

        ret = []
        for entity_id, changes in tmp.items():
            if (changes.has_key(int(self.const.account_password)) and not
                changes.has_key(int(self.const.account_create))):
                # TBD: når er det OK å vise passordet?
                del(changes[int(self.const.account_password)])
            
            for k, v in changes.items():
                cl = self.num2const[int(k)]
                params = ''
                if k == int(self.const.account_password):
                    if v['change_params']:
                        params = pickle.loads(v['change_params'])
                        params = params.get('password', '')
                tmp = {
                    'tstamp': v['tstamp'],
                    'change_type': str(cl),
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
                    name = ou.get_name_with_language(
                        name_variant=self.const.ou_name,
                        name_language=self.const.language_nb,
                        default="")
                tmp['name'] = name
                ret.append(tmp)
        return ret

    all_commands['find_school'] = None
    def find_school(self, operator, name):

        if not self.ba.is_schoolit(operator.get_entity_id(), True):
            raise PermissionDenied("Currently limited to superusers and school IT")

        # name could be an acronym or a "regular" name
        result = set()
        for name_variant in (self.const.ou_name, self.const.ou_name_acronym):
            result.update(r["entity_id"]
                          for r in
                          self.ou.search_name_with_language(entity_type=self.const.entity_ou,
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
            raise CerebrumError("School information is unavailable for this user")
        else:
            return ou_id
    # end find_school

    
    all_commands["get_password_information"] = None
    def get_password_information(self, operator, entity_id):
        """Retrieve information about password changes for entity_id.

        This function helps implement a command in Giske's cweb.
        """

        self.logger.debug("Processing for id=%s", entity_id)
        entity_id = int(entity_id)
        result = {}
        for row in operator.get_state():

            if entity_id != row["state_data"]["account_id"]:
                continue
            if row["state_type"] not in ("new_account_passwd", "user_passwd"):
                continue

            result = {"account_id": entity_id,
                      "uname": self._get_entity_name(entity_id,
                                                     self.const.entity_account),
                      "password": row["state_data"]["password"]}
            account = self._get_entity(ident=entity_id)
            owner = self._get_entity(ident=account.owner_id)
            result["name"] = self._get_entity_name(owner.entity_id,
                                                   owner.entity_type)
            if owner.entity_type == self.const.entity_person:
                result["birth_date"] = owner.birth_date
                # Main affiliation points to school.
                affs = account.list_accounts_by_type(primary_only=True,
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
    # end get_password_information


    def get_format_suggestion(self, cmd):
        return self.all_commands[cmd].get_fs()

    def _format_ou_name(self, ou):
        binds = {"name_language": self.const.language_nb,
                 "default": ""}
        return (ou.get_name_with_language(name_variant=self.const.ou_name_short,
                                          **binds) or 
                ou.get_name_with_language(name_variant=self.const.ou_name,
                                          **binds))
    # end _format_ou_name

    
    # this is stripped down version of UiO's, without ldap-functionality.
    def _email_info_detail(self, acc):
        info = []
        eq = Email.EmailQuota(self.db)
        try:
            eq.find_by_target_entity(acc.entity_id)
            et = Email.EmailTarget(self.db)
            et.find_by_target_entity(acc.entity_id)
            es = Email.EmailServer(self.db)
            es.find(et.email_server_id)
            if es.email_server_type == self.const.email_server_type_cyrus:
                pw = self.db._read_password(cereconf.CYRUS_HOST,
                                            cereconf.CYRUS_ADMIN)
                used = 'N/A'; limit = None
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
                                # line.split fails e.g. because quota isn't set on server
                                folder, junk = line.split()
                                self.logger.warning("No IMAP quota set for '%s'" % acc.account_name)
                                used = "N/A"
                                limit = None
                except (TimeoutException, socket.error):
                    used = 'DOWN'
                except ConnectException, e:
                    used = str(e)
                except imaplib.IMAP4.error, e:
                    used = 'DOWN'
                info.append({'quota_hard': eq.email_quota_hard,
                             'quota_soft': eq.email_quota_soft,
                             'quota_used': used})
                if limit is not None and limit != eq.email_quota_hard:
                    info.append({'quota_server': limit})
            else:
                info.append({'dis_quota_hard': eq.email_quota_hard,
                             'dis_quota_soft': eq.email_quota_soft})
        except Errors.NotFoundError:
            pass

        return info

    # helpers needed for email_info, cannot be copied in the usual way
    #
    def __get_email_target_and_account(self, address):
        """Returns a tuple consisting of the email target associated
        with address and the account if the target type is user.  If
        there is no at-sign in address, assume it is an account name.
        Raises CerebrumError if address is unknown."""
        et, ea = self.__get_email_target_and_address(address)
        acc = None
        if et.email_target_type in (self.const.email_target_account,
                                    self.const.email_target_deleted):
            acc = self._get_account(et.email_target_entity_id, idtype='id')
        return et, acc

    def __get_email_target_and_address(self, address):
        """Returns a tuple consisting of the email target associated
        with address and the address object.  If there is no at-sign
        in address, assume it is an account name and return primary
        address.  Raises CerebrumError if address is unknown.
        """
        et = Email.EmailTarget(self.db)
        ea = Email.EmailAddress(self.db)
        if address.count('@') == 0:
            acc = self.Account_class(self.db)
            try:
                acc.find_by_name(address)
                # FIXME: We can't use Account.get_primary_mailaddress
                # since it rewrites special domains.
                et = Email.EmailTarget(self.db)
                et.find_by_target_entity(acc.entity_id)
                epa = Email.EmailPrimaryAddressTarget(self.db)
                epa.find(et.entity_id)
                ea.find(epa.email_primaddr_id)
            except Errors.NotFoundError:
                raise CerebrumError, ("No such address: '%s'" % address)
        elif address.count('@') == 1:
            try:
                ea.find_by_address(address)
                et.find(ea.email_addr_target_id)
            except Errors.NotFoundError:
                raise CerebrumError, "No such address: '%s'" % address
        else:
            raise CerebrumError, "Malformed e-mail address (%s)" % address
        return et, ea

    def __get_address(self, etarget):
        """The argument can be
        - EmailPrimaryAddressTarget
        - EmailAddress
        - EmailTarget (look up primary address and return that, throw
        exception if there is no primary address)
        - integer (use as entity_id and look up that target's
        primary address)
        The return value is a text string containing the e-mail
        address.  Special domain names are not rewritten."""
        ea = Email.EmailAddress(self.db)
        if isinstance(etarget, (int, long, float)):
            epat = Email.EmailPrimaryAddressTarget(self.db)
            # may throw exception, let caller handle it
            epat.find(etarget)
            ea.find(epat.email_primaddr_id)
        elif isinstance(etarget, Email.EmailTarget):
            epat = Email.EmailPrimaryAddressTarget(self.db)
            epat.find(etarget.entity_id)
            ea.find(epat.email_primaddr_id)
        elif isinstance(etarget, Email.EmailPrimaryAddressTarget):
            ea.find(etarget.email_primaddr_id)
        elif isinstance(etarget, Email.EmailAddress):
            ea = etarget
        else:
            raise ValueError, "Unknown argument (%s)" % repr(etarget)
        ed = Email.EmailDomain(self.db)
        ed.find(ea.email_addr_domain_id)
        return ("%s@%s" % (ea.email_addr_local_part,
                           ed.email_domain_name))

    def __get_valid_email_addrs(self, et, special=False, sort=False):
        """Return a list of all valid e-mail addresses for the given
        EmailTarget.  Keep special domain names intact if special is
        True, otherwise re-write them into real domain names."""
        addrs = [(r['local_part'], r['domain'])       
                 for r in et.get_addresses(special=special)]
        if sort:
            addrs.sort(lambda x,y: cmp(x[1], y[1]) or cmp(x[0],y[0]))
        return ["%s@%s" % a for a in addrs]


    # Commands for Exchange migration:

    all_commands['user_migrate_exchange'] = Command(
        ("user", "migrate_exchange"), 
        AccountName(help_ref="account_name", repeat=False),
        SimpleString(help_ref='string_mdb'),        
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

    all_commands['user_migrate_exchange_finished'] = Command(
        ("user", "migrate_exchange_finished"), 
        AccountName(help_ref="account_name", repeat=True),
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


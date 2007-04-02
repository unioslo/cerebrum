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
from Cerebrum.modules.bofhd.cmd_param import Parameter,Command,FormatSuggestion,GroupName,GroupOperation
from Cerebrum.Constants import _CerebrumCode
from Cerebrum.modules.bofhd.auth import BofhdAuth, BofhdAuthRole, \
                                        BofhdAuthOpSet, BofhdAuthOpTarget
from Cerebrum.modules.bofhd.utils import _AuthRoleOpCode
from Cerebrum.extlib.sets import Set as set


def format_day(field):
    fmt = "yyyy-MM-dd"                  # 10 characters wide
    return ":".join((field, "date", fmt))

"""This class contains the bofh-functions needed by the indigo
www-interface.  To avoid code-duplication we re-use a number of
commands from the uio-module.  Currently none of these commands are
available to the standard command-line based bofh client.

To modify permissions, temporary start a separate bofhd with the
normal bofhd_uio_cmds so that the perm commands are available.
"""

class BofhdExtension(object):
    OU_class = Utils.Factory.get('OU')
    Account_class = Factory.get('Account')
    Group_class = Factory.get('Group')
    all_commands = {}

    copy_commands = (
        '_get_account', '_get_ou', '_get_person',
        '_get_disk', '_get_group', '_map_person_id', '_parse_date',
        '_get_entity', 'group_user', 'person_list_user_priorities',
        'group_memberships', 'group_search',
        '_get_boolean', '_entity_info', 'num2str',
        'group_list', 'misc_list_passwords', '_get_cached_passwords',
        '_get_entity_name', 'group_add_entity',
        'group_remove_entity', 'user_password',
        '_get_group_opcode', '_get_name_from_object',
        '_group_add_entity', '_group_count_memberships',
        'group_create', 'spread_add', '_get_constant',
        'misc_clear_passwords', 'person_set_user_priority',)

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
        self.server = server
        self.logger = server.logger
        self.db = server.db
        self.util = server.util
        self.const = Factory.get('Constants')(self.db)
        self.person = Factory.get('Person')(self.db)
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


    def get_help_strings(self):
        group_help = {
            }
        command_help = {
            }
        arg_help = {
            }
        return (group_help, command_help,
                arg_help)
    
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
    def _group_remove_entity(self, operator, member, group, group_operation):
        group_operation = self._get_group_opcode(group_operation)
        self.ba.can_alter_group(operator.get_entity_id(), group)
        member_name = self._get_name_from_object(member)
        if not group.has_member(member.entity_id, member.entity_type,
                                group_operation):
            return ("%s isn't a member of %s" %
                    (member_name, group.group_name))
        try:
            group.remove_member(member.entity_id, group_operation)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return "OK, removed '%s' from '%s'" % (member_name, group.group_name)

    all_commands['group_info'] = None
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
            en = self._get_entity(id=id)
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
        u, i, d = grp.list_members()

        for members, op in ((u, 'u'), (i, 'i'), (d, 'd')):
            tmp = {}
            for ret_pfix, entity_type in (
                ('c_group_', int(co.entity_group)),
                ('c_account_', int(co.entity_account))):
                tmp[ret_pfix+op] = len(
                    [x for x in members if int(x[0]) == entity_type])
                if [x for x in tmp.values() if x > 0]:
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
        entity = self._get_entity(id=int(entity_id))
        return [{'spread': str(self.const.Spread(int(row['spread']))),
                 'spread_desc': self.const.Spread(int(row['spread']))._get_description()}
                for row in entity.get_spread()]

    all_commands['get_default_email'] = None
    def get_default_email(self, operator, entity_id):
        account = self._get_account(entity_id)
        return account.get_primary_mailaddress()

    all_commands['user_get_pwd'] = None
    def user_get_pwd(self, operator, id):
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
        
    all_commands['user_info'] = None
    def user_info(self, operator, entity_id):
        account = self._get_account(entity_id)
        return {'entity_id': account.entity_id,
                'owner_id': account.owner_id,
                'owner_type': account.owner_type}

    all_commands['person_info'] = None
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
            data.append({'aff_sted_desc': ou.name,
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
    def user_create(self, operator, uname, owner_id):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        account = self.Account_class(self.db)
        entity = self._get_entity(id=int(owner_id))
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
            ret.append({'account_id': account_id,
                        'name': row['name'],
                        'owner_id': account.owner_id})

        # school lita can see their own schools only!
        ret = self._filter_resultset_by_operator(operator, ret, "owner_id")

        ret.sort(lambda a, b: cmp(a["name"], b["name"]))
        return ret
    # end user_find


    def _operator_sees_person(self, operator, person_id):
        """Decide if operator can obtain information about person_id.

        This is a complement to _filter_resultset_by_operator. except that it
        should be more lightlweight. An operator can 'see' a person_id, if the
        operator and person_id share at least one ou_id in their affiliations
        (i.e. they both happen to be associated with the same OU). 
        """

            # superusers see everyone
        if (self.ba.is_superuser(operator.get_entity_id(), True) or
            # operators see themselves
            operator.get_owner_id() == person_id): 
            return True

        operators_ou = set([x['ou_id'] for x in
                            self.person.list_affiliations(
                                person_id=operator.get_owner_id())])
        targets_ou = set([x['ou_id'] for x in
                          self.person.list_affiliations(person_id=int(person_id))])

        return bool(operators_ou.intersection(targets_ou))
    # end _operator_sees_person


    def _filter_resultset_by_operator(self, operator, results, person_key):
        """Remove elements from results to which operator has no access.

        In general, a school lita should not 'see' any results outside of his
        school. This means that the list of users and people returned to
        him/her has to be filtered. 

        operator	operator (person_id)
        results		a sequency of dictionary-like objects where each object
                        represents a database row. These are to be filtered.
        person_key	name of the key in each element of results that
                        designates the owner.

        Caveats:
        * This method is quite costly. It gets more so, the larger the schools are.
        * This method will not help with group filtering.
        """

        # never filter superusers' results
        if self.ba.is_superuser(operator.get_entity_id(), True):
            return results
        
        # The operation is performed in three steps:
        # 1) fetch all OUs where the operator has an affiliation.
        # 2) fetch all people affiliated with OUs in #1
        # 3) intersect results with #2

        # Find operator's OUs
        operators_ou = [x['ou_id'] for x in
                        self.person.list_affiliations(
                            person_id=operator.get_owner_id())]
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
                entity = self._get_entity(id=int(v['subject_entity']))
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
                    ou = self.OU_class(self.db)
                    ou.find(entity.entity_id)
                    name = ou.name
                tmp['name'] = name
                ret.append(tmp)
        return ret

    all_commands['find_school'] = None
    def find_school(self, operator, ou_name):

        if not self.ba.is_schoolit(operator.get_entity_id(), True):
            raise PermissionDenied("Currently limited to superusers and school IT")
        
        ou_n = ou_name.lower()
        ou = self.OU_class(self.db)
        all_ou = ou.list_all(filter_quarantined=True)
        ou_list = []
        for o in all_ou:
            ou.clear()
            ou.find(o['ou_id'])
            tmp = ou.name.lower()
            if re.match('.*' +  ou_n + '.*', tmp):
                ou_list.append(ou.entity_id)

        # filter the results for school IT
        if not self.ba.is_superuser(operator.get_entity_id(), True):
            ou_list = [x['ou_id'] for x in self.person.list_affiliations(
                                               person_id=operator.get_owner_id())
                       if x['ou_id'] in ou_list]
        
        if len(ou_list) == 0:
            raise CerebrumError("Could not find school %s" % ou_name)
        elif len(ou_list) > 1:
            raise CerebrumError("Found several schools with matching names.")
        else:
            return ou_list[0]

    def get_format_suggestion(self, cmd):
        return self.all_commands[cmd].get_fs()

    def _format_ou_name(self, ou):
        return ou.short_name or ou.name

# arch-tag: d1ad56e6-7155-11da-87dd-ea237fa9df60

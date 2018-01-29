# -*- coding: utf-8 -*-
#
# Copyright 2011-2016 University of Oslo, Norway
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
u""" TODO """

from mx import DateTime

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import NotSet

# Imports from the DNS module:
from Cerebrum.modules.dns import DnsOwner, IP_NUMBER, DNS_OWNER
from Cerebrum.modules.dns.CNameRecord import CNameRecord
from Cerebrum.modules.dns.Utils import Find

from Cerebrum.modules.hostpolicy.PolicyComponent import PolicyComponent, Role, Atom

# Import for bofhd
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.cmd_param import *
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.dns.bofhd_dns_cmds import HostId, DnsBofhdAuth, format_day


class HostPolicyBofhdAuth(DnsBofhdAuth):
    """Specialized bofhd-auth for the Hostpolicy bofhd-extension.

    Though a module of its own, Hostpolicy-commands use the same access groups
    as the DNS-module (on which it depends anyway), so the same mechanisms used
    there are also used here.
    """
    pass

# Define cmd_params for the HostPolicy module
# The Parameters are used to make an explanation for each parameter at input in
# jbofh.


class AtomId(Parameter):
    _type = 'atom'
    _help_ref = 'atom_id'


class AtomName(Parameter):
    _type = 'name'  # TODO: find out what _type means - are they used to anythin?
    _help_ref = 'atom_name'


class RoleId(Parameter):
    _type = 'role'
    _help_ref = 'role_id'


class RoleName(Parameter):
    _type = 'name'
    _help_ref = 'role_name'


class PolicyId(Parameter):
    _type = 'policy'
    _help_ref = 'policy_id'


class PolicyName(Parameter):
    _type = 'name'
    _help_ref = 'policy_name'


class FoundationDate(Parameter):
    _type = 'date'
    _help_ref = 'foundation_date'


class Filter(Parameter):
    _type = 'filter'
    _help_ref = 'component_filter'


class HostPolicyBofhdExtension(BofhdCommandBase):
    u"""Class with commands for manipulating host policies. """

    all_commands = {}
    authz = HostPolicyBofhdAuth

    def __init__(self, *args, **kwargs):
        super(HostPolicyBofhdExtension, self).__init__(*args, **kwargs)
        # TODO: don't know where to get the zone setting from
        self.default_zone = self.const.DnsZone(
            getattr(cereconf, 'DNS_DEFAULT_ZONE', 'uio'))

    @classmethod
    def get_help_strings(cls):
        """Help strings are used by jbofh to give users explanations for groups
        of commands, commands and all command arguments (parameters). The
        arg_help's keys are referencing to either Parameters' _help_ref (TODO:
        or its _type in addition?)"""
        group_help = {
            'policy': 'Commands for handling host policies',
            # don't know if the group 'host' is required here, but it's defined
            # in bofhd_core_help and bofhd_dns_cmds, and it works without it.
            }

        command_help = {
            'policy': {
                'policy_atom_create': 'Create a new atom',
                'policy_atom_delete': 'Delete an atom',
                'policy_rename': 'Rename an existing policy',
                'policy_role_create': 'Create a new role',
                'policy_role_delete': 'Delete a role',
                'policy_add_member': 'Make a role/atom a member of a role',
                'policy_remove_member': 'Remove a role membership',
                'policy_list_members': 'List all members of a role',
                'policy_has_member': 'List all roles that has given policy as member (its parents)',
                'policy_list_hosts': 'List all hosts with the given policy (atom/role)', 
                'policy_list_atoms': 'List all atoms by given filters',
                'policy_list_roles': 'List all roles by given filters',
                'policy_info': 'Show info about a policy, i.e. an atom or a role',
                'policy_set_description': 'Update the description of an existing policy',
                'policy_set_foundation': 'Update the foundation data of an existing policy',
                },
            'host': {
                'host_policy_add': 'Give a host a policy (atom/role)',
                'host_policy_remove': 'Remove a policy from a host',
                'host_policy_list': 'List all policies associated with a host',
                },
            }

        arg_help = {
            'atom_id':
            ['atom', 'Atom',
             """The name or entity_id of an atom"""],
            'atom_name':
            ['atom_name', 'Atom name',
             """The name of the atom"""],
            'role_id':
            ['role', 'Role',
             """The name or entity_id of a role"""],
            'role_source':
            ['source_role', 'Source role',
             """The name or entity_id of an existing role to be used as source."""],
            'role_name':
            ['role_name', 'Role name',
             """The name of the role"""],
            'policy_id': 
            ['policy', 'Policy',
             """The name or entity_id of a policy, i.e. a role or an atom"""],
            'policy_name':
            ['policy_name', 'Policy name',
             """The name of the policy"""],
            'policy_target':
            ['target_policy', 'Target policy',
             """The policy (atom/role) to be used as the target of a relationship."""],
            'foundation_date':
            ['date', 'Foundation date',
             """The date of the foundation of the atom/role."""],
            'component_filter':
            ['filter', 'Search filter',
            """A comma separated list of filters. The types:

 'name'         - The name of the policy
 'desc'         - The description of the policy
 'foundation'   - The foundation of the policy
 'date'         - The 'foundation date' of the policy
 'create'       - The date the policy were created in bofh

The filters are specified on the form 'type:value'. If you don't specify the
type, 'name' is assumed. The string types handles wildcard search (* and ?).

Example:
  server*,desc:*test* - All policies with names starting with server, and that
                        have 'test' in their description.

The dates filters expects strings on the form YYYY-MM-DD--YYYY-MM-DD, which
specifies the start and end date. If only a specific date is given - on the
format YYYY-MM-DD - only policies with that specific date is returned. The
start or end dates could be blank, to filter out older or newer policies.

Example:
  date:--2011-12-31 - All policies "founded" before the year 2012.

  date:2011-12-31-- - All policies "founded" in the year 2012 and later on.

  date:2011-12-24   - All policies "founded" on 24th of December 2011.

  create:2012-01-01--2012-01-31 - All policies created in January 2012.
            """],
            'description':
            ['description', 'Description',
             """A description of what the atom/role is"""],
            'foundation':
            ['foundation', 'Foundation (url)',
             """An url to the foundation of the atom/role?"""],
            }
        return (group_help, command_help,
                arg_help)

    def _get_component(self, comp_id, comp_class=PolicyComponent):
        """Helper method for getting a policy, or a given subtype."""
        comp = comp_class(self.db)
        try:
            if type(comp_id) == int or comp_id.isdigit():
                comp.find(comp_id)
            else:
                comp.find_by_name(comp_id)
        except Errors.NotFoundError:
            if comp_class == Atom:
                raise CerebrumError("Couldn't find atom with id=%s" % comp_id)
            elif comp_class == Role:
                raise CerebrumError("Couldn't find role with id=%s" % comp_id)
            raise CerebrumError("Couldn't find policy with id=%s" % comp_id)
        return comp

    def _get_atom(self, atom_id):
        """Helper method for getting an atom."""
        return self._get_component(atom_id, Atom)

    def _get_role(self, role_id):
        """Helper method for getting a role."""
        return self._get_component(role_id, Role)

    def _get_host(self, host_id):
        """Helper method for getting the DnsOwner for the given host ID, which
        can either be an IP address, an A record or a CName alias."""
        finder = Find(self.db, self.default_zone)

        tmp = host_id.split(".")
        if host_id.find(":") == -1 and tmp[-1].isdigit():
            # host_id is an IP
            owner_id = finder.find_target_by_parsing(host_id, IP_NUMBER)
        else:
            owner_id = finder.find_target_by_parsing(host_id, DNS_OWNER)

        # Check if it is a Cname, if so: update the owner_id
        try:           
            cname_record = CNameRecord(self.db)
            cname_record.find_by_cname_owner_id(owner_id)
            owner_id = cname_record.target_owner_id
        except Errors.NotFoundError:
            pass

        dns_owner = DnsOwner.DnsOwner(self.db)
        try:
            dns_owner.find(owner_id)
        except Errors.NotFoundError:
            raise CerebrumError('Unknown host: %s' % host_id)
        return dns_owner

    def _check_if_unused(self, comp):
        """Check if component is unused, i.e. not in any relationship or used as
        a policy for hosts. If it is in use, a CerebrumError is raised, telling
        where it is in use. Note that only one of the types of "usage" is
        explained."""
        tmp = tuple(row['dns_owner_name'] for row in
                    comp.search_hostpolicies(policy_id=comp.entity_id))
        if tmp:
            raise CerebrumError("Policy is in use as policy for: %s" %
                                ', '.join(tmp))
        tmp = tuple(row['source_name'] for row in 
                    comp.search_relations(target_id=comp.entity_id))
        if tmp:
            raise CerebrumError("Policy is used as target for: %s" %
                                ', '.join(tmp))
        tmp = tuple(row['target_name'] for row in 
                    comp.search_relations(source_id=comp.entity_id))
        if tmp:
            raise CerebrumError("Policy is used as source for: %s" %
                                ', '.join(tmp))

    def _parse_filters(self, input, filters, default_filter=NotSet,
                       default_value=NotSet, separator=',', type_sep=':'):
        """Parse an input string with different filters and return a dict with
        the different filters set, according to the set options. CerebrumErrors
        are raise in case of invalid input, with explanations to what have
        failed.

        The input string must define filters on the form:

            name1:pattern1,name2:pattern2,...

        the filters are separated by L{separator} (default: ','), and each
        filter has a name and a value, separated by L{type_sep} (default: ':').

        The L{filters} is the dict that defines the available filters. Errors
        are raised if the input contains other types of filters. Example of
        filters:

            'name':     str
            'desc':     str
            'spread':   _is_spread_valid
            'expired':  _parse_date

        The filters' values are callbacks to a method that should validate and
        might reformat the input before it's returned. If a callback raises an
        error, a CerebrumError is given back to the user.

        If an input filter does not specify its filter type, the one defined in
        L{default_filter} is used - which should match a key in L{filters}.

        If L{default_value} is set, this value will be put in all defined
        filters that aren't specified in the input."""
        if default_filter is not NotSet and not filters.has_key(default_filter):
            raise RuntimeError('Default filter not specified in the filters')
        if not input or input == "":
            raise CerebrumError("No filter specified")
        patterns = {}
        for rule in input.split(separator):
            rule = rule.strip()
            if rule.find(":") != -1:
                type, pattern = rule.split(type_sep, 1)
            elif default_filter is not NotSet:
                # the first defined filter is the default one
                type = default_filter
                pattern = rule
            else:
                raise CerebrumError('Filter type not specified for: %s' % rule)
            type, pattern = type.strip(), pattern.strip()
            if type not in filters:
                raise CerebrumError("Unknown filter type: %s" % type)

            if filters[type] is None:
                patterns[type] = pattern
            else: # call callback function:
                # Callbacks should only raise CerebrumErrors, which can be
                # raised directly. Everything else is bugs and should be raised.
                patterns[type] = filters[type](pattern)
        # fill in with default values
        if default_value is not NotSet:
            for f in filters:
                if not patterns.has_key(f):
                    patterns[f] = default_value
        return patterns

    def _parse_create_date_range(self, date, separator='--'):
        """Parse a string with a date range and return a tuple of length two
        with DateTime objects, or None, if range is missing. The format has the
        form:

            YYYY-MM-DD--YYYY-MM-DD

        where the end date is optional, and would then default to None.
        
        The main difference between this method and bofhd_uio_cmds' method
        _parse_date_from_to is that if only only one date is given, this is
        considered the start date and not the end date. In addition we differ
        between not set dates and dates that is explicitly set to None.

        Dates that have not been specified are set to NotSet, but dates that
        have explicitly set to nothing returns None. Examples:

            YYYY-MM-DD              returns (<start>, NotSet)
            YYYY-MM-DD--            returns (<start>, None)
            --YYYY-MM-DD            returns (None,    <end>)
            YYYY-MM-DD--YYYY-MM-DD  returns (<start>, <end>)
            '' (empty string)       returns (NotSet, NotSet)
        """
        date_start = date_end = NotSet
        if date:
            tmp = date.split(separator)
            if len(tmp) == 2:
                date_start = date_end = None
                if tmp[0]: # string could start with the separator
                    date_start = self._parse_date(tmp[0])
                if tmp[1]: # string could end with separator
                    date_end = self._parse_date(tmp[1])
            elif len(tmp) == 1:
                date_start = self._parse_date(date)
            else:
                raise CerebrumError("Incorrect date specification: %s." % date)
        return (date_start, date_end)

    @staticmethod
    def _parse_date(date):
        """Convert a written date into DateTime object.  Possible
        syntaxes are:

            YYYY-MM-DD       (2005-04-03)
            YYYY-MM-DDTHH:MM (2005-04-03T02:01)
            THH:MM           (T02:01)

        Time of day defaults to midnight.  If date is unspecified, the
        resulting time is between now and 24 hour into future.

        """
        if not date:
            # TBD: Is this correct behaviour?  mx.DateTime.DateTime
            # objects allow comparison to None, although that is
            # hardly what we expect/want.
            return None
        if isinstance(date, DateTime.DateTimeType):
            # Why not just return date?  Answer: We do some sanity
            # checks below.
            date = date.Format("%Y-%m-%dT%H:%M")
        if date.count('T') == 1:
            date, time = date.split('T')
            try:
                hour, min = [int(x) for x in time.split(':')]
            except ValueError:
                raise CerebrumError("Time of day must be on format HH:MM")
            if date == '':
                now = DateTime.now()
                target = DateTime.Date(now.year, now.month, now.day, hour, min)
                if target < now:
                    target += DateTime.DateTimeDelta(1)
                date = target.Format("%Y-%m-%d")
        else:
            hour = min = 0
        try:
            y, m, d = [int(x) for x in date.split('-')]
        except ValueError:
            raise CerebrumError("Dates must be on format YYYY-MM-DD")
        # TODO: this should be a proper delta, but rather than using
        # pgSQL specific code, wait until Python has standardised on a
        # Date-type.
        if y > 2050:
            raise CerebrumError("Too far into the future: %s" % date)
        if y < 1800:
            raise CerebrumError("Too long ago: %s" % date)
        try:
            return DateTime.Date(y, m, d, hour, min)
        except:
            raise CerebrumError("Illegal date: %s" % date)

    # TODO: we miss functionality for setting mutex relationships

    all_commands['policy_atom_create'] = Command(
            ('policy', 'atom_create'),
            AtomName(), SimpleString(help_ref='description'),
            SimpleString(help_ref='foundation'), FoundationDate(optional=True),
            perm_filter='is_dns_superuser')
    def policy_atom_create(self, operator, name, description, foundation,
                        foundation_date=None):
        """Adds a new atom and its data. Its can only consist of lowercased,
        alpha numrice characters and -."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        atom = Atom(self.db)
        # validate data
        tmp = atom.illegal_attr(description)
        if tmp:
            raise CerebrumError('Illegal description: %s' % tmp)
        tmp = atom.illegal_attr(foundation)
        if tmp:
            raise CerebrumError('Illegal foundation: %s' % tmp)
        foundation_date = self._parse_date(foundation_date)

        # check that name isn't already in use
        try:
            comp = self._get_component(name)
        except CerebrumError:
            pass
        else:
            raise CerebrumError('A policy already exists with name: %s' % name)
        atom.populate(name, description, foundation, foundation_date)
        atom.write_db()
        return "New atom %s created" % atom.component_name

    all_commands['policy_atom_delete'] = Command(
            ('policy', 'atom_delete'),
            AtomId(),
            perm_filter='is_dns_superuser')
    def policy_atom_delete(self, operator, atom_id):
        """Try to delete an atom if it hasn't been used in any policy or
        relationship."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        atom = self._get_atom(atom_id)
        self._check_if_unused(atom) # will raise CerebrumError

        name = atom.component_name
        atom.delete()
        atom.write_db()
        return "Atom %s deleted" % name

    all_commands['policy_role_create'] = Command(
            ('policy', 'role_create'),
            RoleName(), SimpleString(help_ref='description'),
            SimpleString(help_ref='foundation'), FoundationDate(optional=True),
            perm_filter='is_dns_superuser')
    def policy_role_create(self, operator, name, description, foundation,
                        foundation_date=None):
        """Adds a new role and its data. Its can only consist of lowercased,
        alpha numrice characters and -."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        role = Role(self.db)
        # validate data
        tmp = role.illegal_attr(description)
        if tmp:
            raise CerebrumError('Illegal description: %s' % tmp)
        tmp = role.illegal_attr(foundation)
        if tmp:
            raise CerebrumError('Illegal foundation: %s' % tmp)
        foundation_date = self._parse_date(foundation_date)

        # check that name isn't already in use
        try:
            comp = self._get_component(name)
        except CerebrumError:
            pass
        else:
            raise CerebrumError('A policy already exists with name: %s' % name)
        role.populate(name, description, foundation, foundation_date)
        role.write_db()
        return "New role %s created" % role.component_name
    
    all_commands['policy_role_delete'] = Command(
            ('policy', 'role_delete'), RoleId(),
            perm_filter='is_dns_superuser')
    def policy_role_delete(self, operator, role_id):
        """Try to delete a given role if it's not in any relationship, or is in
        any policy."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        role = self._get_role(role_id)
        # Check if policy is in use anywhere. The method will raise
        # CerebrumErrors if that's the case:
        self._check_if_unused(role)

        name = role.component_name
        role.delete()
        role.write_db()
        return "Role %s deleted" % name

    all_commands['policy_rename'] = Command(
            ('policy', 'rename'), PolicyId(), PolicyName(),
            perm_filter='is_dns_superuser')
    def policy_rename(self, operator, policy_id, name):
        """Rename an existing policy, if the name is not already taken."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        policy = self._get_component(policy_id)

        # check if name is already taken
        try:
            self._get_component(name)
            raise CerebrumError('New name %s is in use' % name)
        except CerebrumError:
            pass
        old_name = policy.component_name
        policy.component_name = name
        policy.write_db()
        return "Policy %s renamed to %s" % (old_name, name)

    all_commands['policy_set_description'] = Command(
            ('policy', 'set_description'), PolicyId(),
            SimpleString(help_ref='description'),
            perm_filter='is_dns_superuser')
    def policy_set_description(self, operator, policy_id, description):
        """Update the description of an existing policy."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        policy = self._get_component(policy_id)
        policy.description = description
        policy.write_db()
        return "Description updated for %s" % policy.component_name

    all_commands['policy_set_foundation'] = Command(
            ('policy', 'set_foundation'), PolicyId(),
            SimpleString(help_ref='foundation'), FoundationDate(optional=True),
            perm_filter='is_dns_superuser')
    def policy_set_foundation(self, operator, policy_id, foundation, date=None):
        """Update the foundation data of an existing policy."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        policy = self._get_component(policy_id)
        policy.foundation = foundation
        if date:
            policy.foundation_date = self._parse_date(date)
        policy.write_db()
        return "Foundation updated for %s" % policy.component_name

    all_commands['policy_add_member'] = Command(
            ('policy', 'add_member'),
            RoleId(help_ref='role_source'), PolicyId(help_ref='policy_target'),
            perm_filter='is_dns_superuser')
    def policy_add_member(self, operator, role_id, member_id):
        """Try to add a given policy as a member of a role."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        try:
            role = self._get_role(role_id)
        except CerebrumError, e:
            # check if it is an atom, and give better feedback
            try:
                atom = self._get_atom(role_id)
            except CerebrumError:
                raise e
            raise CerebrumError("Atoms can't have members")
        member = self._get_component(member_id)

        if role.entity_id == member.entity_id:
            raise CerebrumError("Can't add a role to itself")
        # Check if already a member
        for row in role.search_relations(source_id=role.entity_id,
                            relationship_code=self.const.hostpolicy_contains,
                            indirect_relations=True):
            if row['target_id'] == member.entity_id:
                raise CerebrumError("%s already member of %s (through %s)" %
                                    (member.component_name, role.component_name,
                                     row['source_name']))
        try:
            role.add_relationship(self.const.hostpolicy_contains, member.entity_id)
        except Errors.ProgrammingError, e:
            # The relationship were not accepted, give the user an explanation
            # of why.

            # TODO: need to check for mutex relationships!

            # Check if member is source in the relationship
            for row in role.search_relations(source_id=member.entity_id,
                                relationship_code=self.const.hostpolicy_contains,
                                indirect_relations=True):
                if row['target_id'] == role.entity_id:
                    raise CerebrumError("%s is already a parent for %s (through %s)" %
                                        (member.component_name, role.component_name,
                                         row['source_name']))

            # if we got here, we weren't able to explain what is wrong
            self.logger.warn("Unhandled bad relationship: %s" % e)
            raise CerebrumError('The membership was not allowed due to constraints')
        role.write_db()
        return "Policy %s is now member of role %s" % (member.component_name,
                                                       role.component_name)

    all_commands['policy_remove_member'] = Command(
            ('policy', 'remove_member'),
            RoleId(), PolicyId(),
            perm_filter='is_dns_superuser')
    def policy_remove_member(self, operator, role_id, member_id):
        """Try to remove a given member from a given role."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        role = self._get_role(role_id)
        member = self._get_component(member_id)

        # check if relationship do exists:
        rel = role.search_relations(source_id=role.entity_id,
                        target_id=member.entity_id,
                        relationship_code=self.const.hostpolicy_contains)
        if not tuple(rel):
            raise CerebrumError('%s is not a member of %s' % (
                        member.component_name, role.component_name))

        role.remove_relationship(self.const.hostpolicy_contains, member.entity_id)
        role.write_db()
        return "Policy %s no longer member of %s" % (member.component_name, 
                                                        role.component_name)

    all_commands['policy_list_members'] = Command(
            ('policy', 'list_members'),
            RoleId(),
            perm_filter='is_dns_superuser',
            fs=FormatSuggestion('%s %s', ('mem_type', 'mem_name'), 
                hdr='Name'))
    def policy_list_members(self, operator, role_id):
        """List out all members of a given role."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        role = self._get_role(role_id)

        def _get_members(roleid, increment=0):
            """Get all direct and indirect members of a given role and return
            them as list of strings. The hierarchy is presented by a space
            increment in the strings, e.g. when listing the role "server":

                database-server
                  postgres-server
                  test-server
                web-server
                  production-server
                    vortex-server
                      caching-server
                    apache-server
                  test-server
            """
            # TODO: there's probably a quicker solution to left padding:
            inc = ''.join(' ' for i in range(increment))
            members = tuple(row for row in role.search_relations(roleid,
                              relationship_code=self.const.hostpolicy_contains))
            ret = []
            for row in sorted(members, key=lambda r: r['target_name']):
                type = 'A'
                if row['target_entity_type'] == self.const.entity_hostpolicy_role:
                    type = 'R'
                ret.append({'mem_name': row['target_name'],
                            'mem_type': '%s%s' % (inc, type)})
                if row['target_entity_type'] == self.const.entity_hostpolicy_role:
                    ret.extend(_get_members(row['target_id'], increment+2))
            return ret
        return _get_members(role.entity_id)

    all_commands['host_policy_add'] = Command(
            ('host', 'policy_add'),
            HostId(), PolicyId(),
            perm_filter='is_dns_superuser')
    def host_policy_add(self, operator, dns_owner_id, comp_id):
        """Give a host - dns owner - a policy, i.e. a role/atom."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        host = self._get_host(dns_owner_id)
        policy = self._get_component(comp_id)

        # Do not allow atoms directly on hosts
        if policy.entity_type == self.const.entity_hostpolicy_atom:
            raise CerebrumError('Atoms can not be assigned directly to hosts')

        # check if host already has the policy as direct relation
        for row in policy.search_hostpolicies(policy_id=policy.entity_id,
                                            dns_owner_id=host.entity_id):
            raise CerebrumError('Host %s already has policy %s' %
                                (host.name, policy.component_name))
        # Check if host already has the policy indirectly. Not sure if this
        # should be a part of the API, as it's not directly an error, but more
        # of a way of holding the structure somewhat tidy. Note that one could
        # add a role which have sub roles that is already given to the host,
        # without getting an error for that.
        # TODO: this could be swapped with setting indirect_relations to True?
        def check_member_loop(role_id, check_id):
            """Find a given check_id in the members of a role, and then
            raise a CerebrumError with an explanation for this. Works
            recursively."""
            for row in policy.search_relations(source_id=role_id,
                             relationship_code=self.const.hostpolicy_contains):
                if row['target_id'] == check_id:
                    raise CerebrumError('%s is a member of the role %s '
                            '(direct or indirect) - host already has the role'
                            % (row['target_name'], row['source_name']))
                if row['target_entity_type'] == self.const.entity_hostpolicy_role:
                    check_member_loop(row['target_id'], check_id)

        if policy.entity_type == self.const.entity_hostpolicy_role:
            for row in policy.search_hostpolicies(dns_owner_id=host.entity_id):
                check_member_loop(row['policy_id'], policy.entity_id)

        # TODO: mutex should be checked here

        policy.add_to_host(host.entity_id)
        return "Policy %s added to host %s" % (policy.component_name,
                                               host.name)

    all_commands['host_policy_remove'] = Command(
            ('host', 'policy_remove'),
            HostId(), PolicyId(),
            perm_filter='is_dns_superuser')
    def host_policy_remove(self, operator, dns_owner_id, comp_id):
        """Remove a given policy from a given host."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        host = self._get_host(dns_owner_id)
        policy = self._get_component(comp_id)
        # check that the policy is actually given to the host:
        if not tuple(policy.search_hostpolicies(policy_id=policy.entity_id,
                                              dns_owner_id=host.entity_id)):
            raise CerebrumError("Host %s doesn't have policy %s" %
                                (host.name, policy.component_name))
        policy.remove_from_host(host.entity_id)
        return "Policy %s removed from host %s" % (policy.component_name,
                                                   host.name)

    all_commands['host_policy_list'] = Command(
            ('host', 'policy_list'),
            HostId(),
            fs=FormatSuggestion('%-20s %-40s', ('policy_name', 'desc'),
                hdr='%-20s %-40s' % ('Policy:', 'Description:')),
            perm_filter='is_dns_superuser')
    def host_policy_list(self, operator, dns_owner_id):
        """List all roles/atoms associated to a given host."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        host = self._get_host(dns_owner_id)
        policy = PolicyComponent(self.db)
        ret = []
        for row in policy.search_hostpolicies(dns_owner_id=host.entity_id):
            policy.clear()
            policy.find(row['policy_id'])
            ret.append({'policy_name': row['policy_name'], 
                        'desc': policy.description})
        return sorted(ret, key=lambda r: r['policy_name'])

    all_commands['policy_list_hosts'] = Command(
            ('policy', 'list_hosts'),
            PolicyId(),
            fs=FormatSuggestion('%s', ('host_or_policy',)),
            perm_filter='is_dns_superuser')
    def policy_list_hosts(self, operator, component_id):
        """List all hosts that has a given policy (role/atom)."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        comp = self._get_component(component_id)
        def _get_hosts(policyid, increment=0, already_hosts=[],
                       already_policies=[]):
            """Recursive function for getting all hosts at the given policy and
            its parent policies. Returned as a list of strings, where each
            recursion pads its strings with spaces.

            Note that both policies and hosts are returned, as one needs to see
            what subpolicy a host is targeted through.

                jbofh> polic list_hosts server
                
                  master-server.uio.no.
                  usit-master.uio.no.
                  crond_running
                    usit-worker-server.uio.no.
                  sharedhost
                    login.uio.no.
                    login.ifi.uio.no.
                    selinux-sharedhosts
                      usit-login.uio.no.
                      logon-test.uio.no.
                    usertestservers
                      test-login.uio.no.
                  abc-server
                    abc-test-server
                      abc-test-server-external
                        abcexttests.uio.no.

            One can differ between hosts and policies in that all hosts are
            returned by their FQDN.

            TBD: Now hosts are only returned through the first found relation,
            even though it can be related to a policy in many, many ways. Not
            decided if all relations should be shown for a host.

            The L{already_policies} contains the policies already listed, to
            avoid listing the same policy twice. The L{already_hosts} contains
            hosts already listed, to avoid listing the same host twice.
            """
            # TODO: there's probably a quicker solution to left padding:
            inc = ''.join(' ' for i in range(increment))

            # get this policy's hosts
            ret = []
            for row in comp.search_hostpolicies(policy_id=policyid):
                h_id = row['dns_owner_id']
                if h_id in already_hosts:
                    continue
                already_hosts.append(h_id)
                ret.append({'host_or_policy': '%s%s' % (inc,
                                                        row['dns_owner_name'])})

            # get parent policies if they have hosts related to them
            parent = tuple(row for row in comp.search_relations(target_id=policyid,
                             relationship_code=self.const.hostpolicy_contains)
                             if row['source_id'] not in already_policies)
            for row in sorted(parent, key=lambda r: r['source_name']):
                already_policies.append(row['source_id'])
                subs = _get_hosts(row['source_id'], increment+2, already_hosts,
                                  already_policies)
                if subs:
                    ret.append({'host_or_policy': '%s%s' % (inc, row['source_name'])})
                    ret.extend(subs)
            return sorted(ret)
        return sorted(_get_hosts(comp.entity_id))

    all_commands['policy_has_member'] = Command(
            ('policy', 'has_member'),
            PolicyId(),
            fs=FormatSuggestion('%-20s', ('policy_name',),
                                hdr='%-20s' % ('Policy',)),
            perm_filter='is_dns_superuser')
    def policy_has_member(self, operator, component_id):
        """List all hosts and/or roles that is related to the given
        component."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        comp = self._get_component(component_id)

        def _get_parents(policyid, increment=0, already_processed=[]):
            """Get all direct and indirect parents of a given policy and return
            them as list of strings. The hierarchy is presented by a space
            increment in the strings, e.g. when listing the policy
            "abc_test_server":

                test_servers
                  server
                    machine
                abc_environment
                  usit_env
                    unix_any

            We could have used search_relations with indirect_relations=True,
            but then we couldn't see the hierarchy.

            The L{already_processed} contains the policies already listed, to
            avoid listing policies twice.
            """
            # TODO: there's probably a quicker solution to left padding:
            inc = ''.join(' ' for i in range(increment))
            parents = tuple(row for row in
                    comp.search_relations(target_id=policyid,
                              relationship_code=self.const.hostpolicy_contains))
            ret = []
            for row in sorted(parents, key=lambda r: r['source_name']):
                ret.append({'policy_name': '%s%s' % (inc, row['source_name'])})
                if row['source_id'] not in already_processed:
                    ret.extend(_get_parents(row['source_id'], increment+2,
                                            already_processed))
                already_processed.append(row['source_id'])
            return ret
        return _get_parents(comp.entity_id, 0, [])

    all_commands['policy_list_atoms'] = Command(
            ('policy', 'list_atoms'),
            Filter(),
            fs=FormatSuggestion('%-20s %-30s', ('name', 'desc'),
                hdr='%-20s %-30s' % ('Name', 'Description'))
            )
    def policy_list_atoms(self, operator, filter):
        """Return a list of atoms that match the given filters."""
        # This method is available for everyone
        atom = Atom(self.db)
        filters = self._parse_filters(filter, {'name': None,
                                               'date': self._parse_create_date_range,
                                               'create': self._parse_create_date_range,
                                               'desc': None,
                                               'foundation': None,},
                                      default_filter='name', default_value=None)
        date_start = date_end = None
        if filters['date']:
            date_start, date_end = filters['date']
            if date_end is NotSet: # only the specific date should be used
                date_end = date_start
        create_start = create_end = None
        if filters['create']:
            create_start, create_end = filters['create']
            if create_end is NotSet: # only the specific date should be used
                create_end = create_start
        ret = []
        for row in atom.search(name=filters['name'],
                               description=filters['desc'],
                               create_start = create_start,
                               create_end = create_end,
                               foundation_start = date_start,
                               foundation_end = date_end,
                               foundation=filters['foundation']):
            ret.append({'name': row['name'], 'desc': row['description']})
        return sorted(ret, key=lambda r: r['name'])

    all_commands['policy_list_roles'] = Command(
            ('policy', 'list_roles'),
            Filter(),
            fs=FormatSuggestion('%-20s %-30s', ('name', 'desc'),
                hdr='%-20s %-30s' % ('Name', 'Description'))
            )
    def policy_list_roles(self, operator, filter):
        """Return a list of roles that match the given filters."""
        # This method is available for everyone
        role = Role(self.db)
        filters = self._parse_filters(filter, {'name': str,
                                               'date': self._parse_create_date_range,
                                               'create': self._parse_create_date_range,
                                               'desc': str,
                                               'foundation': str,},
                                      default_filter='name', default_value=None)
        date_start = date_end = None
        if filters['date']:
            date_start, date_end = filters['date']
            if date_end is NotSet: # only the specific date should be used
                date_end = date_start
        create_start = create_end = None
        if filters['create']:
            create_start, create_end = filters['create']
            if create_end is NotSet: # only the specific date should be used
                create_end = create_start
        ret = []
        for row in role.search(name=filters['name'],
                               description=filters['desc'],
                               create_start = create_start,
                               create_end = create_end,
                               foundation_start = date_start,
                               foundation_end = date_end,
                               foundation=filters['foundation']):
            ret.append({'name': row['name'], 'desc': row['description']})
        return sorted(ret, key=lambda r: r['name'])

    all_commands['policy_info'] = Command(
            ('policy', 'info'),
            RoleId(),
            fs=FormatSuggestion([
                ('Name:             %-30s', ('name',)),
                ('Created:          %s%-30s', ('dummy2', format_day('create_date'),)),
                ('Description:      %-30s', ('desc',)),
                ('Foundation:       %-30s', ('foundation',)),
                ('Foundation date:  %s%-30s', ('dummy', format_day('foundation_date'),)),
                ('Type:             %-30s', ('type',)),
                ('Relation:         %s (%s)', ('target_rel_name', 'target_rel_type'),
                    ('Direct relationships where this role is target:')),
                ('Relation:         %s (%s)', ('rel_name', 'rel_type'),
                    ('Direct relationships where this role is source:')),
                ]))
    def policy_info(self, operator, policy_id):
        """Return information about a policy component."""
        # This method is available for everyone
        comp = self._get_component(policy_id)
        ret = [{'name': comp.component_name},
               {'type': str(self.const.EntityType(comp.entity_type))},
               {'desc': comp.description},
               {'foundation': comp.foundation},
               # format_day doesn't work as first argument, so put in an empty
               # dummy
               {'dummy': '', 'foundation_date': comp.foundation_date},
               {'dummy2': '', 'create_date': comp.created_at},
               ]
        # check what this component is in relationship with
        for row in comp.search_relations(target_id=comp.entity_id):
            ret.append({'target_rel_name': row['source_name'],
                        'target_rel_type': row['relationship_str']})
        # if this is a role, add direct relationships where this is the source
        if comp.entity_type == self.const.entity_hostpolicy_role:
            for row in comp.search_relations(source_id=comp.entity_id):
                ret.append({'rel_name': row['target_name'],
                            'rel_type': row['relationship_str']})
        return ret

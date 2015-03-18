#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013, 2014 University of Oslo, Norway
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
"""This is the bofhd functionality that is available for the TSD project.

Many of the commands are simply copied from UiO's command base and renamed for
the project, while other commands are changed to comply with the project.

Idealistically, we would move the basic commands into a super class, so we could
instead use inheritance, but unfortunately we don't have that much time.

Note that there are different bofhd extensions. One is for administrative tasks,
i.e. the superusers in TSD, and one is for the end users. End users are
communicating with bofhd through a web site, so that bofhd should only be
reachable from the web host.


NOTE:

Using the @superuser decorator instead of calling self.ba.is_superuser(userid)
is only used in this file so far, so if you are an experienced bofhd developer,
ba.is_superuser is not missing, it's still here, but in a different form.


"""

from mx import DateTime

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum import Constants
from Cerebrum import Utils
from Cerebrum import Cache
from Cerebrum import Errors
from Cerebrum.modules import EntityTrait
from Cerebrum.modules.bofhd import cmd_param as cmd
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules import dns
from Cerebrum.modules.dns import Subnet
from Cerebrum.modules.dns import IPv6Subnet
from Cerebrum.modules import PasswordChecker
from Cerebrum.Constants import _CerebrumCode

from Cerebrum.modules.tsd.bofhd_auth import TSDBofhdAuth
from Cerebrum.modules.tsd import bofhd_help
from Cerebrum.modules.tsd import Gateway

from functools import wraps


def format_day(field):
    return field + "date:yyyy-MM-dd"


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


class ProjectID(cmd.Parameter):
    """Bofhd Parameter for specifying a project ID."""
    _type = 'projectID'
    _help_ref = 'project_id'


class ProjectName(cmd.Parameter):
    """Bofhd Parameter for specifying a project name."""
    _type = 'projectName'
    _help_ref = 'project_name'


class ProjectLongName(cmd.Parameter):
    """Bofhd Parameter for specifying a project's long (full) name."""
    _type = 'projectLongName'
    _help_ref = 'project_longname'


class ProjectShortName(cmd.Parameter):
    """Bofhd Parameter for specifying a project's short name."""
    _type = 'projectShortName'
    _help_ref = 'project_shortname'


class GroupDescription(cmd.SimpleString):  # SimpleString inherits from cmd.Parameter
    """Bofhd Parameter for specifying a group description."""
    _type_ = 'groupDescription'
    _help_ref_ = 'group_description'

    def __init__(self, help_ref="string_description"):
        super(GroupDescription, self).__init__(help_ref=help_ref)


class ProjectStatusFilter(cmd.Parameter):
    """Bofhd Parameter for filtering on projects' status.

    A project could have status not-approved, frozen or active. More status
    types are probably needed in the future.
    """
    _type = 'projectStatusFilter'
    _help_ref = 'project_statusfilter'


class SubnetParam(cmd.Parameter):
    """A subnet, e.g. 10.0.0.0/16"""
    _type = 'subnet'
    _help_ref = 'subnet'


class SubnetSearchType(cmd.Parameter):
    """A subnet search type."""
    _type = 'searchType'
    _help_ref = 'subnet_search_type'


class VLANParam(cmd.Parameter):
    """A VLAN number"""
    _type = 'vlan'
    _help_ref = 'vlan'

class VMType(cmd.Parameter):
    """Bofhd Parameter for specifying projects' VM-type."""
    _type = 'vmType'
    _help_ref = 'vm_type'


class TSDBofhdExtension(BofhdCommonMethods):

    """Superclass for common functionality for TSD's bofhd servers."""

    def __init__(self, server):
        super(TSDBofhdExtension, self).__init__(server)
        self.ba = TSDBofhdAuth(self.db)
        # From uio
        self.num2const = {}
        self.str2const = {}
        self.external_id_mappings = {}
        self.external_id_mappings['fnr'] = self.const.externalid_fodselsnr
        for c in dir(self.const):
            tmp = getattr(self.const, c)
            if isinstance(tmp, _CerebrumCode):
                self.num2const[int(tmp)] = tmp
                self.str2const[str(tmp)] = tmp
        self._cached_client_commands = Cache.Cache(mixins=[Cache.cache_mru,
                                                           Cache.cache_slots,
                                                           Cache.cache_timeout],
                                                   size=500,
                                                   timeout=60 * 60)
        # Copy in all defined commands from the superclass that is not defined
        # in this class.
        for key, command in super(TSDBofhdExtension, self).all_commands.iteritems():
            if not key in self.all_commands:
                self.all_commands[key] = command
        self.util = server.util
        # The client talking with the TSD gateway
        self.gateway = Gateway.GatewayClient(logger=self.logger)  # TODO: dryrun?

    def get_help_strings(self):
        """Return all help messages for TSD."""
        return (bofhd_help.group_help, bofhd_help.command_help,
                bofhd_help.arg_help)

    def _get_entity(self, entity_type=None, ident=None):
        """Return a suitable entity subclass for the specified entity_id.

        Overridden to be able to return TSD projects by their project ID or
        entity_id.

        """
        if ident and entity_type == 'project':
            return self._get_project(ident)
        if ident and entity_type == 'host':
            return self._get_host(ident)
        return super(TSDBofhdExtension, self)._get_entity(entity_type, ident)

    def _get_project(self, projectid):
        """Return a project's OU by its name, if found. We identify project's by
        their acronym name, which is not handled uniquely in the database, so we
        could be up for integrity errors, e.g. if two projects are called the
        same. This should be handled by TSD's OU class.

        @type projectid: string or integer
        @param projectid: The project id or the entity_id of the project. Must
            match one and only one OU.

        @raise CerebrumError: If no project OU with the given acronym name was
            found, or if more than one project OU was found.

        """
        ou = self.OU_class(self.db)
        try:
            ou.find_by_tsd_projectid(projectid)
            return ou
        except Errors.NotFoundError:
            pass
        if projectid.isdigit():
            try:
                ou.find(projectid)
                return ou
            except Errors.NotFoundError:
                pass
        raise CerebrumError("Could not find project: %s" % projectid)

    def _get_host(self, host_id):
        """Helper method for getting the DnsOwner for the given host ID.

        The given L{host_id} could be an IP or IPv6 address or a CName alias.

        @rtype: Cerebrum.modules.dns.DnsOwner/DnsOwner
        @return: An instance of the matching DnsOwner.

        """
        finder = dns.Utils.Find(self.db,
                                self.const.DnsZone(getattr(cereconf, 'DNS_DEFAULT_ZONE', 'uio')))
        if ':' not in host_id and host_id.split('.')[-1].isdigit():
            # host_id is an IP
            owner_id = finder.find_target_by_parsing(host_id, dns.IP_NUMBER)
        else:
            owner_id = finder.find_target_by_parsing(host_id, dns.DNS_OWNER)

        # Check if it is a Cname, if so: go to the cname's owner_id
        try:
            cname_record = dns.CNameRecord.CNameRecord(self.db)
            cname_record.find_by_cname_owner_id(owner_id)
        except Errors.NotFoundError:
            pass
        else:
            owner_id = cname_record.target_owner_id

        dns_owner = dns.DnsOwner.DnsOwner(self.db)
        try:
            dns_owner.find(owner_id)
        except Errors.NotFoundError:
            raise CerebrumError('Unknown host: %s' % host_id)
        return dns_owner

    def _get_ou(self, ou_id=None, stedkode=None):
        """Override to change the use of L{stedkode} to check the acronym.

        In TSD, we do not use L{stedkode}, but we do have some unique IDs stored
        as acronyms. To avoid having to change too much, we just override the
        stedkode reference so we don't have to override each method that fetches
        an OU by its stedkode.

        """
        if ou_id is not None:
            return super(TSDBofhdExtension, self)._get_ou(ou_id, stedkode)
        return self._get_project(stedkode)

    def _format_ou_name(self, ou, include_short_name=True):
        """Return a human readable name for a given OU (project).

        We have project ID, which is used internally, and projectname, that is
        used externally in Nettskjema. Example on output:

                p25
                p01 (tsd)
                p14 (cancer2)
                p02 (<Not Set>)

        @type ou: OU
        @param ou: The given OU (project) to return the name for.

        @type include_short_name: bool
        @param include_short_name: If a short name of the OU should be returned
            as well. If False, only the project ID is returned.

        @rtype: string
        @return: The human readable string that identifies the OU.

        """
        if not include_short_name:
            return ou.get_project_id()
        name = '<Not Set>'
        try:
            name = ou.get_project_name()
        except Errors.CerebrumError, e:
            self.logger.warn("get_project_name failed: %s", e)
        return "%s (%s)" % (ou.get_project_id(), name)

    # misc list_passwords
    def misc_list_passwords_prompt_func(self, session, *args):
        """  - Går inn i "vis-info-om-oppdaterte-brukere-modus":
  1 Skriv ut passordark
  1.1 Lister ut templates, ber bofh'er om å velge en
  1.1.[0] Spesifiser skriver (for template der dette tillates valgt av
          bofh'er)
  1.1.1 Lister ut alle aktuelle brukernavn, ber bofh'er velge hvilke
        som skal skrives ut ('*' for alle).
  1.1.2 (skriv ut ark/brev)
  2 List brukernavn/passord til skjerm
  """
        all_args = list(args[:])
        if not all_args:
            return {'prompt': "Velg#",
                    'map': [(("Alternativer",), None),
                            (("List brukernavn/passord til skjerm",), "skjerm")]}
        arg = all_args.pop(0)
        if(arg == "skjerm"):
            return {'last_arg': True}
        if not all_args:
            map = [(("Alternativer",), None)]
            n = 1
            for t in self._map_template():
                map.append(((t,), n))
                n += 1
            return {'prompt': "Velg template #", 'map': map,
                    'help_ref': 'print_select_template'}
        arg = all_args.pop(0)
        tpl_lang, tpl_name, tpl_type = self._map_template(arg)
        if not tpl_lang.endswith("letter"):
            default_printer = session.get_state(state_type='default_printer')
            if default_printer:
                default_printer = default_printer[0]['state_data']
            if not all_args:
                ret = {'prompt': 'Oppgi skrivernavn'}
                if default_printer:
                    ret['default'] = default_printer
                return ret
            skriver = all_args.pop(0)
            if skriver != default_printer:
                session.clear_state(state_types=['default_printer'])
                session.store_state('default_printer', skriver)
                self.db.commit()
        if not all_args:
            n = 1
            map = [(("%8s %s", "uname", "operation"), None)]
            for row in self._get_cached_passwords(session):
                map.append((("%-12s %s", row['account_id'], row['operation']), n))
                n += 1
            if n == 1:
                raise CerebrumError("no users")
            return {'prompt': 'Velg bruker(e)', 'last_arg': True,
                    'map': map, 'raw': True,
                    'help_ref': 'print_select_range',
                    'default': str(n-1)}


def superuser(fn):
    """Decorator for checking that methods are being executed as operator.
    The first argument of the decorated function must be "self" and the second must be "operator".
    If operator is not superuser a CerebrumError will be raised.
    """
    # The functools.wraps decorator ensures that the docstring and function name of the wrapped
    # function is not lost, but passed on.
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if len(args) < 2:
            raise CerebrumError('Decorated functions must have self and operator as the first '
                                'arguments')
        self = args[0]
        operator = args[1]
        userid = operator.get_entity_id()
        if not self.ba.is_superuser(userid):
            raise CerebrumError('Only superuser is allowed to do this!')
        else:
            self.logger.debug2("OK, current user is superuser.")
            return fn(*args, **kwargs)
    return wrapper


class _Project:
    """Helper class for project information that has an entity_id, name and a list of
    quarantine types.

    Since the coupling of projects and quarantines are encapsulated here, there is less to keep
    track of and less room for potential bugs.

    First and foremost it avoids code duplication for bofhd functions that list projects.


    Examples:

    Filtering by certain quarantines can look a bit like this:

        filtered_projects = [project for project in project_list if project.has_quarantine(q)]


    Returning the filtered/sorted data can look a bit like this:

        return [project.as_dict(['entity_id', 'name']) for project in filtered_projects]

    """

    def __init__(self, const, entity_id, name, pid=None):
        """Initialize the _Project object with an entity_id and a name.
        Quarantines are added with the add_quarantine method.
        """
        # The const object, used for converting quaratines to strings
        self.const = const
        # The entity_id, as a number
        self.id = entity_id
        # The project name, as a string
        self.name = name
        # Quarantines, stores as id's to quarantine types
        self.quarantines = []
        # Project ID
        self.pid = pid

    def add_quarantine(self, quarantine_type):
        """Add a quarantine to the list of quarantines."""
        self.quarantines.append(int(quarantine_type))

    def has_quarantine(self, quarantine_type):
        """Check if this project has the given quarantine type."""
        return int(quarantine_type) in self.quarantines

    def quarantine_string(self):
        """Convert the list of quarantine identifiers to a string using const.Quarantine."""
        return ", ".join(map(str, map(self.const.Quarantine, self.quarantines)))

    def as_dict(self, keynames):
        """Takes a list of key names, like ['entity_id', 'names'] and returns a dictionary."""
        d = {}
        for key in keynames:
            # both 'id' and 'entity_id' are allowed
            if key in ["id", "entity_id"]:
                d[key] = str(self.id)
            elif key == "quars":
                d['quars'] = self.quarantine_string()
            else:
                d[key] = str(getattr(self, key))
        return d


class _Projects:
    """Helper class for making it easy to search, filter, sort and return project data."""

    def __init__(self, logger, const, ou, exact_match=False, filter=None):
        """Make self.projects a list of _Project objects which each contain
        entity_id, name and a list of quarantine types.
        """
        # A dictionary that maps entity_ids to _Project objects
        self.projects = {}
        self.filter = filter
        self._fix_filter()

        # Perform the queries
        project_structs = ou.search_tsd_projects(name=self.filter)
        quarantine_structs = ou.list_entity_quarantines(entity_types=const.entity_ou,
                                                        only_active=True)

        # TODO: Would like to have this in the OUTSDMixin, to be used other
        # places:
        project_ids = ou.search_external_ids(entity_type=const.entity_ou,
                                             id_type=const.externalid_project_id)

        # Fill in a dictionary of Project objects.
        # Projects is a dictionary on the form {entity_id: project_object}
        self.projects = dict((p['entity_id'], _Project(const, p['entity_id'], p['name']))
                             for p in project_structs)

        # Fill in with project IDs:
        for row in ou.search_external_ids(entity_type=const.entity_ou,
                                          id_type=const.externalid_project_id):
            if row['entity_id'] in self.projects:
                self.projects[row['entity_id']].pid = row['external_id']

        # Fill in the quarantine information into the Project objects
        for quarantine_struct in quarantine_structs:
            quarantine_entity_id = quarantine_struct['entity_id']
            if quarantine_entity_id in self.projects:
                project = self.projects[quarantine_entity_id]
                quarantine_type = quarantine_struct['quarantine_type']
                project.add_quarantine(quarantine_type)

    def _fix_filter(self):
        """Massage the filter string so that also searches for 'ø*' is possible.
        Also uses * instead of an empty filter.
        """
        if self.filter is None:
            # Don't do anything
            return
        try:
            if self.filter:
                self.filter.encode('ascii')
        except UnicodeDecodeError:
            if self.filter:
                self.filter = self.filter.decode("iso-8859-1").upper().encode("iso-8859-1")
        if not self.filter:
            # List everything if no filter is specified
            self.filter = "*"
        self.filter = str(self.filter)

    def set_project_list(self, project_list):
        """Takes a list of _project objects and returns a dictionary on the form
        {'entity_id':_project_object}.
        """
        self.projects = dict([(project.id, project) for project in project_list])

    def filter_by_quarantine(self, quarantine_type):
        """Filter out projects that does not have the given quarantine_type."""
        filtered = [p for p in self.projects.values() if p.has_quarantine(quarantine_type)]
        self.set_project_list(filtered)

    def results_sorted_by_name(self, keynames):
        """Returns the results as a dictionary, where the projects are sorted by name."""
        names_and_keys = [(project.name, project.id) for project in self.projects.values()]
        sorted_keys = [name_and_key[1] for name_and_key in sorted(names_and_keys)]
        return [self.projects[key].as_dict(keynames) for key in sorted_keys]

    def results_sorted_by_pid(self, keynames):
        """Returns the results as a dictionary, where the projects are sorted by name."""
        pids_and_keys = [(project.pid, project.id) for project in self.projects.values()]
        # TODO: numerical sort instead of alphabetic
        sorted_keys = [name_and_key[1] for name_and_key in sorted(pids_and_keys)]
        return [self.projects[key].as_dict(keynames) for key in sorted_keys]

    def results(self, keynames):
        """Return the results as a list of dictionaries, which is what bofhd expects."""
        return [project.as_dict(keynames) for project in self.projects.values()]


class AdministrationBofhdExtension(TSDBofhdExtension):

    """The bofhd commands for the TSD project's system administrators.

    Here you have the commands that should be availble for the superusers

    """

    # Commands that should be publicised for an operator, e.g. in jbofh:
    all_commands = {}

    # Commands that are available, but not publicised, as they are normally
    # called through other systems, e.g. Brukerinfo. It should NOT be used as a
    # security feature - thus you have security by obscurity.
    hidden_commands = {}

    # Commands that should be copied from UiO's BofhdExtension. We don't want to
    # copy all of the commands for TSD, but tweak them a bit first.
    copy_commands = (
        # Person
        'person_create', 'person_find', 'person_info', 'person_accounts',
        'person_set_name', 'person_set_bdate', 'person_set_id',
        'person_affiliation_add', 'person_affiliation_remove',
        # User
        'user_history', 'user_info', 'user_find', 'user_set_expire',
        '_user_create_set_account_type', 'user_set_owner',
        'user_set_owner_prompt_func', 'user_affiliation_add',
        'user_affiliation_remove', 'user_demote_posix',
        # Group
        'group_info', 'group_list', 'group_list_expanded', 'group_memberships',
        'group_delete', 'group_set_description', 'group_set_expire',
        'group_search', 'group_promote_posix',  # 'group_create',
        # Quarantine
        'quarantine_disable', 'quarantine_list', 'quarantine_remove',
        'quarantine_set', 'quarantine_show',
        # OU
        'ou_search', 'ou_info', 'ou_tree',
        # TODO: find out if the remaining methods should be imported too:
        #
        # Access:
        #'access_disk', 'access_group', 'access_ou', 'access_user',
        #'access_global_group', 'access_global_ou', '_list_access',
        #'access_grant', 'access_revoke', '_manipulate_access',
        #'_get_access_id', '_validate_access', '_get_access_id_disk',
        #'_validate_access_disk', '_get_access_id_group', '_validate_access_group',
        #'_get_access_id_global_group', '_validate_access_global_group',
        #'_get_access_id_ou', '_validate_access_ou', '_get_access_id_global_ou',
        #'_validate_access_global_ou', 'access_list_opsets', 'access_show_opset',
        #'access_list', '_get_auth_op_target', '_grant_auth', '_revoke_auth',
        #'_get_opset',
        #
        # Misc
        'misc_affiliations', 'misc_clear_passwords', 'misc_verify_password',
        'misc_list_passwords',
        # Trait
        'trait_info', 'trait_list', 'trait_remove', 'trait_set', 'trait_types',
        # Spread
        'spread_list', 'spread_add', 'spread_remove',
        # Entity
        'entity_history',
        # Helper functions
        '_find_persons', '_get_disk', '_get_shell',
        '_entity_info', 'num2str', '_get_affiliationid',
        '_get_affiliation_statusid', '_parse_date', '_today',
        '_format_changelog_entry', '_format_from_cl',
        '_get_constant', '_is_yes', '_remove_auth_target', '_remove_auth_role',
        '_get_cached_passwords', '_parse_date_from_to',
        '_convert_ticks_to_timestamp', '_fetch_member_names',
        '_person_create_externalid_helper',
    )

    def __new__(cls, *arg, **karg):
        """Hackish override to copy in methods from UiO's bofhd.

        A better fix would be to split bofhd_uio_cmds.py into separate classes.

        """
        # Copy in UiO's commands defined in copy_commands:
        from Cerebrum.modules.no.uio.bofhd_uio_cmds import BofhdExtension as \
            UiOBofhdExtension
        non_all_cmds = ('num2str', 'user_set_owner_prompt_func',)
        for func in cls.copy_commands:
            setattr(cls, func, UiOBofhdExtension.__dict__.get(func))
            if func[0] != '_' and func not in non_all_cmds:
                cls.all_commands[func] = UiOBofhdExtension.all_commands[func]
        x = object.__new__(cls)
        return x

    def __init__(self, server):
        super(AdministrationBofhdExtension, self).__init__(server)

        # Copy in all defined commands from the superclass that is not defined
        # in this class.
        for key, command in super(AdministrationBofhdExtension, self).all_commands.iteritems():
            if not key in self.all_commands:
                self.all_commands[key] = command

    #
    # Project commands
    all_commands['project_create'] = cmd.Command(
        ('project', 'create'), ProjectName(), ProjectLongName(),
        ProjectShortName(), cmd.Date(help_ref='project_start_date'),
        cmd.Date(help_ref='project_end_date'), VLANParam(optional=True),
        perm_filter='is_superuser')

    @superuser
    def project_create(self, operator, projectname, longname, shortname,
                       startdate, enddate, vlan=None):
        """Create a new TSD project.

        :param BofhdSession operator:
            The operator's Session, i.e. the user which executes the command.
        :param int vlan:
            If given, sets what VLAN the project's subnet should be set in.

        """
        start = self._parse_date(startdate)
        end = self._parse_date(enddate)
        if end < DateTime.now():
            raise CerebrumError("End date of project has passed: %s" % str(end).split()[0])
        elif end < start:
            raise CerebrumError(
                "Project can not end before it has begun: from %s to %s" %
                (str(start).split()[0], str(end).split()[0]))

        ou = self.OU_class(self.db)
        try:
            pid = ou.create_project(projectname)
        except Errors.CerebrumError, e:
            raise CerebrumError(e)

        # Storing the names:
        ou.add_name_with_language(name_variant=self.const.ou_name_long,
                                  name_language=self.const.language_en,
                                  name=longname)
        if shortname:
            ou.add_name_with_language(name_variant=self.const.ou_name_short,
                                      name_language=self.const.language_en,
                                      name=shortname)
        ou.write_db()

        # Storing start date
        ou.add_entity_quarantine(qtype=self.const.quarantine_project_start,
                                 creator=operator.get_entity_id(), start=DateTime.now(),
                                 end=start, description='Initial start set by superuser')
        # Storing end date
        ou.add_entity_quarantine(qtype=self.const.quarantine_project_end,
                                 creator=operator.get_entity_id(), start=end,
                                 description='Initial end set by superuser')
        ou.write_db()
        try:
            ou.setup_project(operator.get_entity_id(), vlan)
        except Errors.CerebrumError, e:
            raise CerebrumError(e)

        return "New project created: %s" % pid

    all_commands['project_setup'] = cmd.Command(
        ('project', 'setup'), ProjectID(), VLANParam(optional=True),
        perm_filter='is_superuser')

    @superuser
    def project_setup(self, operator, project_id, vlan=None):
        """
        Run the setup procedure for a project, updating configuration to
        current settings.

        :param operator: An BofhdSession-instance of the current user session.
        :type  operator: BofhdSession
        :param project_id: Project ID for the given project.
        :type  project_id: str
        :param vlan: Sets the VLAN number to give to the project's subnets.
        :type  vlan: int

        :returns: A statement that the operation was successful.
        :rtype: str

        """

        op_id = operator.get_entity_id()
        ou = self.OU_class(self.db)

        try:
            ou.find_by_tsd_projectid(project_id)
            ou.setup_project(op_id, vlan)
        except Errors.CerebrumError, e:
            raise CerebrumError(e)

        return 'OK, project reconfigured according to current settings.'

    all_commands['project_terminate'] = cmd.Command(
        ('project', 'terminate'), ProjectID(),
        perm_filter='is_superuser')

    @superuser
    def project_terminate(self, operator, projectid):
        """Terminate a project by removed almost all of it.

        All information about the project gets deleted except its acronym, to
        avoid reuse of the ID.

        """
        project = self._get_project(projectid)
        # TODO: delete person affiliations?
        # TODO: delete accounts
        project.terminate()
        #self.gateway.delete_project(projectid)
        return "Project terminated: %s" % projectid

    all_commands['project_approve'] = cmd.Command(
        ('project', 'approve'), ProjectID(), VLANParam(optional=True),
        perm_filter='is_superuser')

    @superuser
    def project_approve(self, operator, projectid, vlan=None):
        """Approve an existing project that is not already approved. A project
        is created after we get metadata for it from the outside world, but is
        only visible inside of Cerebrum. When a superuser approves the project,
        it gets spread to AD and gets set up properly.

        """
        project = self._get_project(projectid)
        success_msg = "Project approved: %s" % (projectid)

        # Check if the project was already approved
        if not project.get_entity_quarantine(only_active=True,
                                             qtype=self.const.quarantine_not_approved):
            # raise CerebrumError('Project already approved (no not_approved quarantine)')
            return success_msg + " (already approved, not changing anything)"

        project.delete_entity_quarantine(type=self.const.quarantine_not_approved)
        project.write_db()
        try:
            project.setup_project(operator.get_entity_id(), vlan)
        except Errors.CerebrumError, e:
            raise CerebrumError(e)

        if not project.get_entity_quarantine(only_active=True):
            # Active project only if no other quarantines
            #self.gateway.create_project(projectid)
            pass

        self.logger.info(success_msg)
        return success_msg

    all_commands['project_reject'] = cmd.Command(
        ('project', 'reject'), ProjectID(),
        perm_filter='is_superuser')

    @superuser
    def project_reject(self, operator, projectid):
        """Reject a project that is not approved yet.

        All information about the project gets deleted, since it hasn't been
        exported out of Cerebrum yet.

        """
        project = self._get_project(projectid)
        if not project.get_entity_quarantine(only_active=True,
                                             qtype=self.const.quarantine_not_approved):
            raise CerebrumError('Can not reject approved projects, you may '
                                'wish to terminate it instead.')
        project.terminate()
        project.delete()
        try:
            # Double check that project doesn't exist in Gateway.
            # Will raise exception if it's okay.
            self.gateway.delete_project(projectid)
        except Exception:
            pass
        return "Project deleted: %s" % projectid

    all_commands['project_set_enddate'] = cmd.Command(
        ('project', 'set_enddate'), ProjectID(), cmd.Date(),
        perm_filter='is_superuser')

    @superuser
    def project_set_enddate(self, operator, projectid, enddate):
        """Set the end date for a project.

        """
        project = self._get_project(projectid)
        qtype = self.const.quarantine_project_end
        end = self._parse_date(enddate)
        # The quarantine needs to be removed before it could be added again
        for row in project.get_entity_quarantine(qtype):
            project.delete_entity_quarantine(qtype)
            project.write_db()
        project.add_entity_quarantine(qtype=qtype,
                                      creator=operator.get_entity_id(),
                                      description='Reset lifetime for project',
                                      start=end)
        project.write_db()
        # If set in the past, the project is now frozen
        if end < DateTime.now():
            # TODO
            #self.gateway.freeze_project(projectid)
            pass
        return "Project %s updated to end: %s" % (projectid,
                                                  date_to_string(end))

    all_commands['project_set_projectname'] = cmd.Command(
        ('project', 'set_projectname'), ProjectID(), ProjectName(),
        perm_filter='is_superuser')

    @superuser
    def project_set_projectname(self, operator, projectid, projectname):
        """Set the project name for a project."""
        ou = self._get_project(projectid)
        ou.add_name_with_language(name_variant=self.const.ou_name_acronym,
                                  name_language=self.const.language_en,
                                  name=projectname)
        ou.write_db()
        return "Project %s updated with name: %s" % (
            ou.get_project_id(), ou.get_project_name())

    all_commands['project_set_longname'] = cmd.Command(
        ('project', 'set_longname'), ProjectID(), ProjectLongName(),
        perm_filter='is_superuser')

    @superuser
    def project_set_longname(self, operator, projectid, longname):
        """Set the project name for a project."""
        ou = self._get_project(projectid)
        ou.add_name_with_language(name_variant=self.const.ou_name_long,
                                  name_language=self.const.language_en,
                                  name=longname)
        ou.write_db()
        return "Project %s updated with long name: %s" % (ou.get_project_id(),
                                                          longname)

    all_commands['project_set_shortname'] = cmd.Command(
        ('project', 'set_shortname'), ProjectID(), ProjectShortName(),
        perm_filter='is_superuser')

    @superuser
    def project_set_shortname(self, operator, projectid, shortname):
        """Set the project name for a project."""
        ou = self._get_project(projectid)
        ou.add_name_with_language(name_variant=self.const.ou_name_short,
                                  name_language=self.const.language_en,
                                  name=shortname)
        ou.write_db()
        return "Project %s updated with short name: %s" % (ou.get_project_id(),
                                                           shortname)

    all_commands['project_freeze'] = cmd.Command(
        ('project', 'freeze'), ProjectID(),
        perm_filter='is_superuser')

    @superuser
    def project_freeze(self, operator, projectid):
        """Freeze a project."""
        project = self._get_project(projectid)
        end = DateTime.now()

        # The quarantine needs to be removed before it could be added again
        qtype = self.const.quarantine_frozen
        for row in project.get_entity_quarantine(qtype):
            project.delete_entity_quarantine(qtype)
            project.write_db()
        project.add_entity_quarantine(qtype=qtype,
                                      creator=operator.get_entity_id(),
                                      description='Project freeze',
                                      start=end)
        project.write_db()
        success_msg = 'Project %s is now frozen' % projectid
        try:
            self.gateway.freeze_project(projectid)
        except Gateway.GatewayException, e:
            self.logger.warn("From GW: %s", e)
            success_msg += " (bad result from GW)"
        return success_msg

    all_commands['project_unfreeze'] = cmd.Command(
        ('project', 'unfreeze'), ProjectID(),
        perm_filter='is_superuser')

    @superuser
    def project_unfreeze(self, operator, projectid):
        """Unfreeze a project."""
        project = self._get_project(projectid)

        # Remove the quarantine
        qtype = self.const.quarantine_frozen
        for row in project.get_entity_quarantine(qtype):
            project.delete_entity_quarantine(qtype)
            project.write_db()

        success_msg = 'Project %s is now unfrozen' % projectid

        # Only unthaw projects without quarantines
        if not project.get_entity_quarantine(only_active=True):
            try:
                self.gateway.thaw_project(projectid)
            except Gateway.GatewayException, e:
                self.logger.warn("From GW: %s", e)
                success_msg += ' (bad result from GW)'
        else:
            success_msg += ' (project still with other quarantines)'
        return success_msg

    all_commands['project_list'] = cmd.Command(
        ('project', 'list'), ProjectStatusFilter(optional=True),
        fs=cmd.FormatSuggestion(
            '%-11s %-16s %-10s %s', ('pid', 'name', 'entity_id', 'quars'),
            hdr='%-11s %-16s %-10s %s' % ('Project ID', 'Name', 'Entity-Id', 'Quarantines')),
        perm_filter='is_superuser')

    @superuser
    def project_list(self, operator, filter=None):
        """List out all projects by their acronym and status."""
        projects = _Projects(self.logger, self.const, self.OU_class(self.db),
                             exact_match=False, filter=filter)
        return projects.results_sorted_by_name(['pid', 'name', 'entity_id', 'quars'])

    all_commands['project_unapproved'] = cmd.Command(
        ('project', 'unapproved'),
        fs=cmd.FormatSuggestion(
            '%-10s %-16s %-10s', ('pid', 'name', 'entity_id'),
            hdr='%-10s %-16s %-10s' % ('ProjectID', 'Name', 'Entity-Id')),
        perm_filter='is_superuser')

    @superuser
    def project_unapproved(self, operator, filter=None):
        """List all projecs with the 'not_approved' quarantine."""

        projects = _Projects(self.logger,
                             self.const,
                             self.OU_class(self.db),
                             exact_match=False,
                             filter=filter)
        projects.filter_by_quarantine(self.const.quarantine_not_approved)
        return projects.results_sorted_by_pid(['pid', 'name', 'entity_id'])

    all_commands['project_info'] = cmd.Command(
        ('project', 'info'), ProjectID(),
        fs=cmd.FormatSuggestion([(
            "Project ID:       %s\n"
            "Project name:     %s\n"
            "Entity ID:        %d\n"
            "Long name:        %s\n"
            "Short name:       %s\n"
            "Start date:       %s\n"
            "End date:         %s\n"
            "Quarantines:      %s\n"
            "Spreads:          %s",
            ('project_id', 'project_name', 'entity_id', 'long_name',
             'short_name', 'start_date', 'end_date', 'quarantines', 'spreads')),
            ('REK-number:       %s', ('rek',)),
            ('Institution:      %s', ('institution',)),
            ('VM-type:          %s', ('vm_type',)),
            ('VLAN, Subnet:     %-4s, %s', ('vlan_number', 'subnet')),
        ]),
        perm_filter='is_superuser')

    @superuser
    def project_info(self, operator, projectid):
        """Display information about a specified project using ou_info.

        The reason for the semi-sub method is to be able to specify the OU with
        the projectid instead of entity_id. This could probably be handled in
        a much better way.

        """
        project = self._get_project(projectid)
        try:
            pid = project.get_project_id()
        except Errors.NotFoundError:
            pid = '<Missing>'
        ret = {
            'project_id': pid,
            'project_name': project.get_project_name(),
            'entity_id': project.entity_id,
        }
        quars = [self.const.Quarantine(r['quarantine_type']) for r in
                 project.get_entity_quarantine(only_active=True)]
        ret['quarantines'] = ', '.join(str(q) for q in quars)
        ret['spreads'] = ', '.join(str(self.const.Spread(s['spread'])) for s in
                                   project.get_spread())
        # Start and end dates:
        ret['start_date'] = '<Not Set>'
        for row in project.get_entity_quarantine(
                self.const.quarantine_project_start):
            ret['start_date'] = date_to_string(row['end_date'])
        ret['end_date'] = '<Not Set>'
        for row in project.get_entity_quarantine(
                self.const.quarantine_project_end):
            ret['end_date'] = date_to_string(row['start_date'])
        # Names:
        ret['long_name'] = '<Not Set>'
        for row in project.search_name_with_language(entity_id=project.entity_id,
                                                     name_variant=self.const.ou_name_long):
            ret['long_name'] = row['name']
        ret['short_name'] = '<Not Set>'
        for row in project.search_name_with_language(entity_id=project.entity_id,
                                                     name_variant=self.const.ou_name_short):
            ret['short_name'] = row['name']
        ret = [ret, ]
        # REK number
        trait = project.get_trait(self.const.trait_project_rek)
        if trait:
            ret.append({'rek': trait['strval']})
        else:
            ret.append({'rek': '<Not Set>'})
        # Institution
        trait = project.get_trait(self.const.trait_project_institution)
        if trait:
            ret.append({'institution': trait['strval']})
        else:
            ret.append({'institution': '<Not Set>'})
        # VM type
        trait = project.get_trait(self.const.trait_project_vm_type)
        if trait:
            # TODO: how should we store this?
            ret.append({'vm_type': trait['strval']})
        else:
            ret.append({'vm_type': '<Not Set>'})

        # Subnets
        def _subnet_info(subnet_id):
            try:
                sub = Subnet.Subnet(self.db)
                sub.find(subnet_id)
                return {
                    'subnet': '%s/%s' % (sub.subnet_ip, sub.subnet_mask),
                    'vlan_number': str(sub.vlan_number)
                }
            except dns.Errors.SubnetError:
                sub = IPv6Subnet.IPv6Subnet(self.db)
                sub.find(subnet_id)
                compress = dns.IPv6Utils.IPv6Utils.compress
                return {
                    'subnet': '%s/%s' % (compress(sub.subnet_ip),
                                         sub.subnet_mask),
                    'vlan_number': str(sub.vlan_number)
                }

        subnets = [_subnet_info(x['entity_id']) for x in
                   project.get_project_subnets()]
        for subnet in sorted(subnets, key=lambda x: x['subnet']):
            ret.append(subnet)

        return ret

    all_commands['project_affiliate_entity'] = cmd.Command(
        ('project', 'affiliate_entity'), ProjectID(), cmd.EntityType(),
        cmd.Id(help_ref='id:target:group'), perm_filter='is_superuser')

    @superuser
    def project_affiliate_entity(self, operator, projectid, etype, ent):
        """Affiliate a given entity with a project. This is a shortcut command
        for helping the TSD-admins instead of using L{trait_set}. Some entity
        types doesn't even work with trait_set, like DnsOwners."""
        ou = self._get_project(projectid)

        # A mapping of what trait to set for what entity type:
        type2trait = {
            self.const.entity_group: self.const.trait_project_group,
            self.const.entity_dns_owner: self.const.trait_project_host,
            self.const.entity_dns_subnet: self.const.trait_project_subnet,
            self.const.entity_dns_ipv6_subnet: self.const.trait_project_subnet6,
        }

        ent = self._get_entity(entity_type=etype, ident=ent)
        if ent.entity_type in (self.const.entity_person,
                               self.const.entity_account):
            raise CerebrumError("Use 'person/user affiliation_add' for persons/users")
        try:
            trait_type = type2trait[ent.entity_type]
        except KeyError:
            raise CerebrumError("Command does not handle entity type: %s" %
                                self.const.EntityType(ent.entity_type))
        self.logger.debug("Try to affiliate %s (entity_type %s) with trait: %s",
                          ent, ent.entity_type, trait_type)
        # Forcing EntityTrait, since not all instances have this. TBD: Should
        # rather add EntityTrait to cereconf.CLASS_ENTITY instead, but don't
        # know the consequences of that.
        if not isinstance(ent, EntityTrait.EntityTrait):
            entity_id = ent.entity_id
            ent = EntityTrait.EntityTrait(self.db)
            ent.find(entity_id)
        ent.populate_trait(trait_type, target_id=ou.entity_id,
                           date=DateTime.now())
        ent.write_db()
        return "Entity affiliated with project: %s" % ou.get_project_id()

    all_commands['project_set_vm_type'] = cmd.Command(
        ('project', 'set_vm_type'), ProjectID(), VMType(),
        perm_filter='is_superuser')

    @superuser
    def project_set_vm_type(self, operator, project_id, vm_type):
        """
        Changes the type of VM-host(s) for the given project.

        :param operator: An BofhdSession-instance of the current user session.
        :type  operator: BofhdSession
        :param project_id: Project ID for the given project.
        :type  project_id: str
        :param vm_type: The new setting for VM-host(s) for the project.
        :type  vm_type: str

        :returns: A statement that the operation was successful.
        :rtype: str

        """

        project = self._get_project(project_id)
        op_id = operator.get_entity_id()

        if vm_type not in cereconf.TSD_VM_TYPES:
            raise CerebrumError("Invalid VM-type")

        project.populate_trait(code='project_vm_type', strval=vm_type)
        project.write_db()
        project.setup_project(op_id)

        return 'OK, vm_type for %s changed to %s.' % (project_id, vm_type)
    #
    # Person commands
    def _person_affiliation_add_helper(self, operator, person, ou, aff, aff_status):
        """Helper-function for adding an affiliation to a person with permission
        checking. Person is expected to be a person object, while ou, aff and
        aff_status should be the textual representation from the client.
        """
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
            self.ba.can_add_affiliation(operator.get_entity_id(), person, ou,
                                        aff, aff_status)
            person.add_affiliation(ou.entity_id, aff, self.const.system_manual,
                                   aff_status)
            person.write_db()

        return ou, aff, aff_status

    #
    # User commands

    # user_create_prompt_func_helper
    # TODO: need to remove unwanted functionality, e.g. affiliations
    def _user_create_prompt_func_helper(self, ac_type, session, *args):
        """A prompt_func on the command level should return

            {'prompt': message_string, 'map': dict_mapping}

        - prompt is simply shown.
        - map (optional) maps the user-entered value to a value that
          is returned to the server, typically when user selects from
          a list.

        """
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
                    raise CerebrumError("No persons matched")
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
                    exp = date_to_string(account.expire_date)
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
                    raise CerebrumError("Command aborted at user request")
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
            ret = {'prompt': "Username", 'last_arg': True}
            posix_user = Factory.get('PosixUser')(self.db)
            if not group_owner:
                try:
                    person = self._get_person("entity_id", owner_id)
                    fname, lname = [
                        person.get_name(self.const.system_cached, v)
                        for v in (self.const.name_first, self.const.name_last)]
                    ou = self._get_ou(ou_id=affiliation['ou_id'])
                    sugg = posix_user.suggest_unames(
                        self.const.account_namespace, fname, lname,
                        maxlen=cereconf.USERNAME_MAX_LENGTH,
                        prefix='%s-' % ou.get_project_id())
                    if sugg:
                        ret['default'] = sugg[0]
                except ValueError:
                    pass    # Failed to generate a default username
            return ret
        if len(all_args) == 1:
            return {'last_arg': True}
        raise CerebrumError("Too many arguments")

    # user_create_prompt_func
    def user_create_prompt_func(self, session, *args):
        return self._user_create_prompt_func_helper('PosixUser', session, *args)

    # user create
    all_commands['user_create'] = cmd.Command(
        ('user', 'create'), prompt_func=user_create_prompt_func,
        fs=cmd.FormatSuggestion("Created uid=%i", ("uid",)),
        perm_filter='can_create_user')

    def user_create(self, operator, *args):
        """Creating a new account."""

        # TODO: remove functionality not needed in TSD! This method is copied
        # from UiA, and needs to be modified

        if args[0].startswith('group:'):
            group_id, np_type, shell, uname = args
            owner_type = self.const.entity_group
            owner_id = self._get_group(group_id.split(":")[1]).entity_id
            np_type = self._get_constant(self.const.Account, np_type,
                                         "account type")
        else:
            if len(args) == 5:
                idtype, person_id, affiliation, shell, uname = args
            else:
                idtype, person_id, yes_no, affiliation, shell, uname = args
            owner_type = self.const.entity_person
            owner_id = self._get_person("entity_id", person_id).entity_id
            np_type = None

        # Systems in TSD does not accept accounts in uppercase - would get in
        # huge trouble!
        if uname != uname.lower():
            raise CerebrumError("Account names cannot contain capital letters")

        # TODO: Add a check for personal accounts to have the project name as a
        # prefix?
        # if owner_type == self.const.entity_person:
        #    ou_id, affiliation = affiliation['ou_id'], affiliation['aff']
        #    ou = self._get_ou(ou_id=ou_id)
        #    pid = ou.get_project_id()
        #    if not uname.startswith(pid):
        #        raise CerebrumError('Username must have projectid as prefix')

        posix_user = Factory.get('PosixUser')(self.db)
        # TODO: disk?
        uid = posix_user.get_free_uid()
        shell = self._get_shell(shell)
        posix_user.clear()
        self.ba.can_create_user(operator.get_entity_id(), owner_id, None)

        # TODO: get the project's standard dfg's entity_id and use that
        if owner_type == self.const.entity_person:
            ou_id, affiliation = affiliation['ou_id'], affiliation['aff']
            ou = self._get_ou(ou_id=ou_id)

        posix_user.populate(uid, None, None, shell, name=uname,
                            owner_type=owner_type, owner_id=owner_id,
                            np_type=np_type, creator_id=operator.get_entity_id(),
                            expire_date=None)
        try:
            posix_user.write_db()
            passwd = posix_user.make_passwd(uname)
            posix_user.set_password(passwd)
            posix_user.write_db()
            if posix_user.owner_type == self.const.entity_person:
                self._user_create_set_account_type(posix_user, owner_id,
                                                   ou_id, affiliation)
        except self.db.DatabaseError, m:
            raise CerebrumError("Database error: %s" % m)
        for spread in cereconf.BOFHD_NEW_USER_SPREADS:
            posix_user.add_spread(self.const.Spread(spread))
        operator.store_state("new_account_passwd", {'account_id': int(posix_user.entity_id),
                                                    'password': passwd})
        # Set up TSD specific functionality, if not already set
        posix_user.setup_for_project()
        return "Ok, created %s, UID: %s" % (posix_user.account_name, uid)

    # user password
    all_commands['user_password'] = cmd.Command(
        ('user', 'password'), cmd.AccountName(), cmd.AccountPassword(optional=True))

    def user_password(self, operator, accountname, password=None):
        """Set password for a user. A modified version of UiO's command."""
        account = self._get_account(accountname)
        self.ba.can_set_password(operator.get_entity_id(), account)

        # TSD specific behaviour: Raise error if user isn't approved or
        # shouldn't be in AD or the GW:
        if not account.is_approved():
            raise CerebrumError("User is not approved: %s" % accountname)

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
                raise CerebrumError("Cannot specify password for another user.")
        try:
            account.goodenough(account, password)
        except PasswordChecker.PasswordGoodEnoughException, m:
            raise CerebrumError("Bad password: %s" % m)
        ret_msg = 'Password altered'
        # Set password for all person's accounts:
        ac = Factory.get('Account')(self.db)
        for row in ac.search(owner_id=account.owner_id):
            ac.clear()
            ac.find(row['account_id'])
            ac.set_password(password)
            try:
                ac.write_db()
            except self.db.DatabaseError, m:
                raise CerebrumError("Database error: %s" % m)
            # Remove "weak password" quarantine
            for r in ac.get_entity_quarantine():
                if int(r['quarantine_type']) == self.const.quarantine_autopassord:
                    ac.delete_entity_quarantine(self.const.quarantine_autopassord)
                if int(r['quarantine_type']) == self.const.quarantine_svakt_passord:
                    ac.delete_entity_quarantine(self.const.quarantine_svakt_passord)
            ac.write_db()
            ret_msg += "\nNew password for: %s" % ac.account_name
            if ac.is_deleted():
                ret_msg += "\nWarning: user is deleted: %s" % ac.account_name
            elif ac.is_expired():
                ret_msg += "\nWarning: user is expired: %s" % ac.account_name
            elif ac.get_entity_quarantine(only_active=True):
                ret_msg += "\nWarning: user in quarantine: %s" % ac.account_name

        # Only store one of the account's password. Not necessary to store all
        # of them, as it's the same.
        operator.store_state("user_passwd", {'account_id': int(account.entity_id),
                                             'password': password})
        ret_msg += "\nPlease use misc list_password to print or view the new password."
        return ret_msg

    # user password
    all_commands['user_generate_otpkey'] = cmd.Command(
        ('user', 'generate_otpkey'), cmd.AccountName(),
        cmd.SimpleString(help_ref='otp_type', optional=True))

    def user_generate_otpkey(self, operator, accountname, otp_type=None):
        account = self._get_account(accountname)
        self.ba.can_generate_otpkey(operator.get_entity_id(), account)

        # User must be approved first, to exist in the GW
        if not account.is_approved():
            raise CerebrumError("User is not approved: %s" % accountname)

        try:
            uri = account.regenerate_otpkey(otp_type)
        except Errors.CerebrumError, e:
            raise CerebrumError("Failed generating OTP-key: %s" % e)

        # Generate a list of all the accounts for the person
        ac = Factory.get('Account')(self.db)
        ou = self.OU_class(self.db)
        ac_list = {}
        for row in account.search(owner_id=account.owner_id,
                                  spread=self.const.spread_gateway_account):
            ac.clear()
            ac.find(row['account_id'])
            actypes = ac.get_account_types()
            if len(actypes) < 1:
                continue
            if len(actypes) > 1:
                raise CerebrumError('Incorrect number of project affiliations: %s', row['name'])
            ou.clear()
            ou.find(actypes[0]['ou_id'])
            ac_list[row['name']] = ou.get_project_id()

        msg = uri + '\n'

        # Send all to gateway:
        for name, pid in ac_list.iteritems():
            try:
                self.gateway.user_otp(pid, name, uri)
            except Gateway.GatewayException, e:
                self.logger.warn("OTP failed for %s: %s", name, e)
                msg += '\nFailed updating GW for: %s' % name
            else:
                msg += '\nUpdated GW for: %s' % name
        return msg

    # user approve
    all_commands['user_approve'] = cmd.Command(
        ('user', 'approve'), cmd.AccountName(),
        perm_filter='is_superuser')

    def user_approve(self, operator, accountname):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise CerebrumError('Only superusers could approve users')

        ac = self._get_account(accountname)

        if ac.owner_type != self.const.entity_person:
            raise CerebrumError('Non-personal account, use: quarantine remove')

        rows = ac.list_accounts_by_type(
            account_id=ac.entity_id,
            affiliation=(self.const.affiliation_project,
                         self.const.affiliation_pending))
        if not rows:
            raise CerebrumError('Account not affiliated with any project')

        if len(rows) != 1:
            raise CerebrumError('Account has more than one affiliation')

        ou = self._get_ou(rows[0]['ou_id'])
        if not ou.is_approved():
            raise CerebrumError('Project not approved: %s' %
                                ou.get_project_id())

        # Update the person affiliation, if not correct:
        pe = Factory.get('Person')(self.db)
        pe.find(ac.owner_id)

        if pe.list_affiliations(pe.entity_id, ou_id=ou.entity_id,
                                affiliation=self.const.affiliation_pending):
            pe.delete_affiliation(ou.entity_id, self.const.affiliation_pending,
                                  self.const.system_nettskjema)

        if not pe.list_affiliations(pe.entity_id, ou_id=ou.entity_id,
                                    affiliation=self.const.affiliation_project):
            pe.populate_affiliation(
                source_system=self.const.system_manual,
                ou_id=ou.entity_id,
                affiliation=self.const.affiliation_project,
                status=self.const.affiliation_status_project_member)

        pe.write_db()

        # Update the account's affiliation:
        ac.del_account_type(ou.entity_id, self.const.affiliation_pending)
        ac.set_account_type(ou.entity_id, self.const.affiliation_project)
        ac.write_db()

        # Remove the quarantine, if set:
        if ac.get_entity_quarantine(self.const.quarantine_not_approved,
                                    only_active=True):
            ac.delete_entity_quarantine(self.const.quarantine_not_approved)
            ac.write_db()

        # Promote posix
        pu = Factory.get('PosixUser')(self.db)

        try:
            pu.find(ac.entity_id)
        except Errors.NotFoundError:
            pu.clear()
            uid = pu.get_free_uid()
            pu.populate(uid, None, None, self.const.posix_shell_bash, parent=ac,
                        creator_id=operator.get_entity_id())
            pu.write_db()

        return 'Approved %s for project %s' % (ac.account_name,
                                               ou.get_project_id())

    # user delete
    all_commands['user_delete'] = cmd.Command(
        ("user", "delete"), cmd.AccountName(),
        perm_filter='can_delete_user')

    def user_delete(self, operator, accountname):
        account = self._get_account(accountname)
        self.ba.can_delete_user(operator.get_entity_id(), account)
        if account.is_deleted():
            raise CerebrumError("User is already deleted")
        pu = Factory.get('PosixUser')(self.db)
        try:
            pu.find(account.entity_id)
        except Errors.NotFoundError:
            pass
        else:
            pu.delete_posixuser()
            pu.write_db()
        account.deactivate()
        account.write_db()
        return "User %s is deactivated" % account.account_name

    #
    # Group commands

    all_commands['group_create'] = cmd.Command(
        ("group", "create"),
        ProjectID(), cmd.GroupName(), GroupDescription(),
        perm_filter='is_superuser')

    @superuser
    def group_create(self, operator, project, group, description):
        """Method for creating a new group"""
        self.logger.debug2("group create start")
        ou = self._get_project(project)
        groupname = '%s-%s' % (project, group)

        # Check that no account exists with the same name. Necessary for AD:
        ac = self.Account_class(self.db)
        try:
            ac.find_by_name(groupname)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError('An account exists with name: %s' % groupname)

        self.ba.can_create_group(operator.get_entity_id())
        gr = Utils.Factory.get('PosixGroup')(self.db)
        gr.populate(creator_id=operator.get_entity_id(),
                    visibility=self.const.group_visibility_all,
                    name=groupname,
                    description=description)

        try:
            gr.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError("Database error: %s" % m)

        # Connect group to project:
        gr.populate_trait(code=self.const.trait_project_group,
                          target_id=ou.entity_id,
                          date=DateTime.now())
        gr.write_db()

        if not tuple(ou.get_entity_quarantine(only_active=True)):
            for spread in cereconf.BOFHD_NEW_GROUP_SPREADS:
                gr.add_spread(self.const.Spread(spread))
                gr.write_db()
        return "Group %s created, group_id=%s, GID=%s" % (
            gr.group_name, gr.entity_id, gr.posix_gid)

    # group add_member
    all_commands['group_add_member'] = cmd.Command(
        ("group", "add_member"),
        cmd.MemberType(), cmd.MemberName(), cmd.GroupName(),
        perm_filter='can_alter_group')

    def group_add_member(self, operator, member_type, src_name, dest_group):
        """Generic method for adding an entity to a given group.

        @type operator:
        @param operator:

        @type src_name: String
        @param src_name: The name/id of the entity to add as the member.

        @type dest_group: String
        @param dest_group: The name/id of the group the member should be added
            to.

        @type member_type: String or EntityTypeCode (CerebrumCode)
        @param member_type: The entity_type of the member.

        """
        if member_type in ("group", self.const.entity_group):
            src_entity = self._get_group(src_name)
        elif member_type in ("account", self.const.entity_account):
            src_entity = self._get_account(src_name)
        elif member_type in ("person", self.const.entity_person):
            raise CerebrumError("Can't handle persons in project groups")
        else:
            raise CerebrumError('Unknown entity type: %s' % member_type)
        dest_group = self._get_group(dest_group)
        return self._group_add_entity(operator, src_entity, dest_group)

    def _group_add_entity(self, operator, src_entity, dest_group):
        """Helper method for adding a given entity to given group.

        @type operator:
        @param operator:

        @type src_entity: Entity
        @param src_entity: The entity to add as a member.

        @type dest_group: Group
        @param dest_group: The group the member should be added to.

        """
        if operator:
            self.ba.can_alter_group(operator.get_entity_id(), dest_group)
        src_name = self._get_entity_name(src_entity.entity_id,
                                         src_entity.entity_type)
        # Make the error message for the most common operator error more
        # friendly.  Don't treat this as an error, useful if the operator has
        # specified more than one entity.
        if dest_group.has_member(src_entity.entity_id):
            return "%s is already a member of %s" % (src_name, dest_group)
        # Make sure that the src_entity does not have dest_group as a member
        # already, to avoid a recursion at export
        if src_entity.entity_type == self.const.entity_group:
            for row in src_entity.search_members(member_id=dest_group.entity_id,
                                                 member_type=self.const.entity_group,
                                                 indirect_members=True,
                                                 member_filter_expired=False):
                if row['group_id'] == src_entity.entity_id:
                    return "Recursive memberships are not allowed (%s is member of %s)" % (
                        dest_group, src_name)
        # This can still fail, e.g., if the entity is a member with a different
        # operation.
        try:
            dest_group.add_member(src_entity.entity_id)
        except self.db.DatabaseError, m:
            raise CerebrumError("Database error: %s" % m)
        # TODO: If using older versions of NIS, a user could only be a member of
        # 16 group. You might want to be warned about this - Or is this only
        # valid for UiO?
        return "OK, added %s to %s" % (src_name, dest_group.group_name)

    # group remove_member
    all_commands['group_remove_member'] = cmd.Command(
        ("group", "remove_member"),
        cmd.MemberType(), cmd.MemberName(), cmd.GroupName(),
        perm_filter='can_alter_group')

    def group_remove_member(self, operator, member_type, src_name, dest_group):
        """Remove a member from a given group.

        @type operator:
        @param operator:

        @type member_type: String or EntityTypeCode (CerebrumCode)
        @param member_type: The entity_type of the member.

        @type src_name: String
        @param src_name: The name/id of the entity to remove as member.

        @type dest_group: String
        @param dest_group: The name/id of the group the member should be removed
            from.

        """
        if member_type in ("group", self.const.entity_group):
            src_entity = self._get_group(src_name)
        elif member_type in ("account", self.const.entity_account):
            src_entity = self._get_account(src_name)
        elif member_type in ("person", self.const.entity_person):
            try:
                src_entity = self.util.get_target(src_name,
                                                  restrict_to=['Person'])
            except Errors.TooManyRowsError:
                raise CerebrumError("Unexpectedly found more than one person")
        else:
            raise CerebrumError('Unknown entity type: %s' % member_type)
        dest_group = self._get_group(dest_group)
        return self._group_remove_entity(operator, src_entity, dest_group)

    def _group_remove_entity(self, operator, member, group):
        """Helper method for removing a member from a group.

        @type operator:
        @param operator:

        @type member: Entity
        @param member: The member to remove

        @type group: Group
        @param group: The group to remove the member from.

        """
        self.ba.can_alter_group(operator.get_entity_id(), group)
        member_name = self._get_entity_name(member.entity_id,
                                            member.entity_type)
        if not group.has_member(member.entity_id):
            return ("%s isn't a member of %s" %
                    (member_name, group.group_name))
        if member.entity_type == self.const.entity_account:
            try:
                pu = Utils.Factory.get('PosixUser')(self.db)
                pu.find(member.entity_id)
                if pu.gid_id == group.entity_id:
                    raise CerebrumError("Can't remove %s from primary group %s" %
                                        (member_name, group.group_name))
            except Errors.NotFoundError:
                pass
        try:
            group.remove_member(member.entity_id)
        except self.db.DatabaseError, m:
            raise CerebrumError("Database error: %s" % m)
        return "OK, removed '%s' from '%s'" % (member_name, group.group_name)

    def _spread_sync_group(self, account, group=None):
        """Override from UiO to support personal file groups in TSD.

        This should rather be done automatically by the PosixUser mixin class
        for TSD, and UiO, but that requires some refactoring of bofhd. We don't
        know the consequences of that quite yet.

        """
        if account.np_type or account.owner_type == self.const.entity_group:
            return
        pu = Factory.get('PosixUser')(self.db)
        try:
            pu.find(account.entity_id)
        except Errors.NotFoundError:
            return
        # The PosixUser class should handle most of the functionality
        pu.write_db()

    #
    # Subnet commands

    def _get_all_subnets(self):
        """Fetch all subnets in a human-readable format.

        :rtype: list
        :returns: A list with a dictionary per subnet
        """
        ou = self.OU_class(self.db)
        # Project entity ID -> external project ID
        ent2ext = dict((x['entity_id'], x['external_id']) for x in
                       ou.list_external_ids(
                           id_type=self.const.externalid_project_id))

        # Subnet -> external project ID
        subnet2project = {}
        for row in ou.list_traits(code=(self.const.trait_project_subnet6,
                                        self.const.trait_project_subnet)):
            subnet2project[row['entity_id']] = ent2ext.get(row['target_id'])

        # IPv4
        subnet = Subnet.Subnet(self.db)
        subnets = []
        for row in subnet.search():
            subnets.append({
                'subnet': '%s/%s' % (row['subnet_ip'], row['subnet_mask']),
                'vlan_number': str(row['vlan_number']),
                'project_id': subnet2project.get(row['entity_id']),
                'description': row['description']})

        # IPv6
        subnet6 = IPv6Subnet.IPv6Subnet(self.db)
        compress = dns.IPv6Utils.IPv6Utils.compress
        for row in subnet6.search():
            subnets.append({
                'subnet': '%s/%s' % (compress(row['subnet_ip']),
                                     row['subnet_mask']),
                'vlan_number': str(row['vlan_number']),
                'project_id': subnet2project.get(row['entity_id']),
                'description': row['description']})

        return subnets

    all_commands['subnet_list'] = cmd.Command(
        ('subnet', 'list'),
        fs=cmd.FormatSuggestion([(
            '%-30s %6s %7s %s', ('subnet', 'vlan_number',
                                 'project_id', 'description',),)],
            hdr='%-30s %6s %7s %s' % ('Subnet', 'VLAN',
                                      'Project', 'Description')),
        perm_filter='is_superuser')

    @superuser
    def subnet_list(self, operator):
        """Return a list of all subnets."""
        # Sort by subnet
        return sorted(self._get_all_subnets(), key=lambda x: x['subnet'])

    all_commands['subnet_search'] = cmd.Command(
        ("subnet", "search"),
        SubnetSearchType(),
        cmd.SimpleString(),
        fs=cmd.FormatSuggestion([(
            '%-30s %6s %7s %s', ('subnet', 'vlan_number',
                                 'project_id', 'description',),)],
            hdr='%-30s %6s %7s %s' % ('Subnet', 'VLAN',
                                      'Project', 'Description')),
        perm_filter='is_superuser')

    @superuser
    def subnet_search(self, operator, search_type, pattern):
        """Wildcard search for subnets.

        :type search_type: str
        :param search_type: filter subnets by this

        :type pattern: str
        :param pattern: wildcard search pattern
        """
        from fnmatch import fnmatch

        type2key = {
            'subnet': 'subnet',
            'vlan': 'vlan_number',
            'project': 'project_id',
            'description': 'description',
        }

        if search_type not in type2key.keys():
            raise CerebrumError("Unknown search type (%s)" % search_type)

        # Fetch and filter subnets
        subnets = self._get_all_subnets()
        key = type2key[search_type]
        results = [sn for sn in subnets if fnmatch(sn[key], pattern)]

        # Sort by subnet
        return sorted(results, key=lambda x: x['subnet']) or 'No matches found'


    # subnet create
    #all_commands['subnet_create'] = cmd.Command(
    #   ("subnet", "create"),
    #   SubnetParam(), cmd.Description(), Vlan(),
    #   perm_filter='is_superuser')
    @superuser
    def subnet_create(self, operator, subnet, description, vlan):
        """Create a new subnet, if the range is not already reserved.

        TODO: Should it be possible to specify a range, or should we find one
        randomly?

        """
        subnet = Subnet.Subnet(self.db)
        subnet.populate(subnet, description=description, vlan=vlan)

        #TODO: more checks?
        subnet.write_db(perform_checks=True)
        return "Subnet created: %s" % subnet

    def add_subnet(subnet, description, vlan, perform_checks=True):
        pass


class EnduserBofhdExtension(TSDBofhdExtension):
    """The bofhd commands for the end users of TSD.

    End users are Project Administrators (PA), which should have full control of
    their project, and Project Members (PM) which have limited privileges.

    """

    all_commands = {}
    hidden_commands = {}

#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013 University of Oslo, Norway
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

import os
import traceback
from mx import DateTime

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum import Constants
from Cerebrum import Utils
from Cerebrum import Cache
from Cerebrum import Errors
# from Cerebrum.modules import Host
from Cerebrum.modules import PasswordChecker
from Cerebrum.modules.bofhd import cmd_param as cmd
from Cerebrum.modules.dns.bofhd_dns_utils import DnsBofhdUtils
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.dns import ARecord
from Cerebrum.modules.dns import AAAARecord
from Cerebrum.modules.dns import DnsOwner
from Cerebrum.modules.dns import CNameRecord
from Cerebrum.modules.dns import HostInfo
from Cerebrum.modules.dns import IPNumber
from Cerebrum.modules.dns import IPv6Number
from Cerebrum.modules.dns import Subnet
from Cerebrum.modules.dns.Subnet import SubnetError
from Cerebrum.modules.dns.IPUtils import IPCalc
from Cerebrum.modules.dns import CNameRecord
from Cerebrum.modules.dns import Utils
from Cerebrum.modules.hostpolicy.PolicyComponent import PolicyComponent
from Cerebrum.Constants import _CerebrumCode
from Cerebrum.modules import dns
from Cerebrum.modules.bofhd.utils import _AuthRoleOpCode

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
    _help_ref = 'project_name'

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


class Subnet(cmd.Parameter):

    """A subnet, e.g. 10.0.0.0/16"""
    _type = 'subnet'
    _help_ref = 'subnet'


class TSDBofhdExtension(BofhdCommandBase):

    """Superclass for common functionality for TSD's bofhd servers."""

    def __init__(self, server, default_zone='tsd.usit.no.'):
        super(TSDBofhdExtension, self).__init__(server)
        self.ba = TSDBofhdAuth(self.db)
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
                                                   timeout=60 * 60)
        # Copy in all defined commands from the superclass that is not defined
        # in this class.
        for key, cmd in super(TSDBofhdExtension, self).all_commands.iteritems():
            if not self.all_commands.has_key(key):
                self.all_commands[key] = cmd
        self.util = server.util
        # The client talking with the TSD gateway
        self.gateway = Gateway.GatewayClient(logger=self.logger)  # TODO: dryrun?

    def get_help_strings(self):
        """Return all help messages for TSD."""
        return (bofhd_help.group_help, bofhd_help.command_help,
                bofhd_help.arg_help)

    def _get_entity(self, entity_type=None, ident=None):
        """Return a suitable entity subclass for the specified entity_id.

        Overridden to be able to return TSD projects by their projectname or
        entity_id.

        """
        if ident and entity_type == 'project':
            return self._get_project(ident)
        return super(TSDBofhdExtension, self)._get_entity(entity_type, ident)

    def _get_project(self, projectname):
        """Return a project's OU by its name, if found. We identify project's by
        their acronym name, which is not handled uniquely in the database, so we
        could be up for integrity errors, e.g. if two projects are called the
        same. This should be handled by TSD's OU class.

        @type projectname: string or integer
        @param projectname: The name or the entity_id of the project. Must match
            one and only one OU.

        @raise CerebrumError: If no project OU with the given acronym name was
            found, or if more than one project OU was found.

        """
        ou = self.OU_class(self.db)
        try:
            ou.find_by_tsd_projectname(projectname)
            return ou
        except Errors.NotFoundError:
            pass
        if projectname.isdigit():
            try:
                ou.find(projectname)
                return ou
            except Errors.NotFoundError:
                pass
        raise CerebrumError("Could not find project: %s" % projectname)

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
        """Return a human readable name for a given OU."""
        acronym = ou.get_name_with_language(
            name_variant=self.const.ou_name_acronym,
            name_language=self.const.language_en)
        try:
            short_name = ou.get_name_with_language(
                name_variant=self.const.ou_name_short,
                name_language=self.const.language_en)
        except Errors.NotFoundError:
            return str(acronym)
        return "%s (%s)" % (acronym, short_name)


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
            raise CerebrumError('Only superusers are allowed to do this!')
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

    def __init__(self, const, entity_id, name):
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
        project_structs = ou.search_name_with_language(entity_type=const.entity_ou,
                                                       name_variant=const.ou_name_acronym,
                                                       exact_match=exact_match,
                                                       name=self.filter)
        quarantine_structs = ou.list_entity_quarantines(entity_types=const.entity_ou,
                                                        only_active=True)

        # Fill in a dictionary of Project objects.
        # Projects is a dictionary on the form {entity_id: project_object}
        self.projects = dict([(p['entity_id'], _Project(const, p['entity_id'], p['name']))
                              for p in project_structs])

        # Fill in the quarantine information into the Project objects
        for quarantine_struct in quarantine_structs:
            quarantine_entity_id = quarantine_struct['entity_id']
            if quarantine_entity_id in self.projects:
                project = self.projects[quarantine_entity_id]
                quarantine_type = quarantine_struct['quarantine_type']
                project.add_quarantine(quarantine_type)
            else:
                continue

    def _fix_filter(self):
        """Massage the filter string so that also searches for 'ø*' is possible.
        Also uses * instead of an empty filter.
        """
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
        """Remove projects that does not have the given quarantine_type."""
        filtered = [p for p in self.projects.values() if p.has_quarantine(quarantine_type)]
        self.set_project_list(filtered)

    def results_sorted_by_name(self, names):
        """Returns the results as a dictionary, where the projects are sorted by name."""
        names_and_keys = [(project.name, project.id) for project in self.projects.values()]
        sorted_keys = [name_and_key[1] for name_and_key in sorted(names_and_keys)]
        return [self.projects[key].as_dict(names) for key in sorted_keys]

    def results(self, names):
        """Return the results as a dictionary."""
        return [project.as_dict(names) for project in self.projects.values()]


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
        '_user_create_set_account_type',
        # Group
        'group_info', 'group_list', 'group_list_expanded', 'group_memberships',
        'group_delete', 'group_set_description', 'group_set_expire',
        'group_search',  # 'group_create',
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
        # Trait
        'trait_info', 'trait_list', 'trait_remove', 'trait_set',
        # Spread
        'spread_list', 'spread_add', 'spread_remove',
        # Entity
        'entity_history',
        # Helper functions
        '_find_persons', '_get_person', '_get_disk', '_get_group', '_get_shell',
        '_get_account', '_get_entity_name',
        '_map_person_id', '_entity_info', 'num2str', '_get_affiliationid',
        '_get_affiliation_statusid', '_parse_date', '_today',
        '_format_changelog_entry', '_format_from_cl', '_get_name_from_object',
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

    def __init__(self, server, default_zone='tsdutv.usit.no.'):
        super(AdministrationBofhdExtension, self).__init__(server)

        # Copy in all defined commands from the superclass that is not defined
        # in this class.
        for key, cmd in super(AdministrationBofhdExtension, self).all_commands.iteritems():
            if not self.all_commands.has_key(key):
                self.all_commands[key] = cmd

    #
    # Project commands
    all_commands['project_create'] = cmd.Command(
        ('project', 'create'), ProjectName(), ProjectLongName(),
        ProjectShortName(), cmd.Date(help_ref='project_start_date'),
        cmd.Date(help_ref='project_end_date'),
        perm_filter='is_superuser')

    @superuser
    def project_create(self, operator, projectname, longname, shortname,
                       startdate, enddate):
        """Create a new project."""
        start = self._parse_date(startdate)
        end = self._parse_date(enddate)
        if end < DateTime.now():
            raise CerebrumError("End date of project has passed: %s" % str(end).split()[0])
        elif end < start:
            raise CerebrumError(
                "Project can not end before it has begun: from %s to %s" %
                (str(start).split()[0], str(end).split()[0]))

        ou = self.OU_class(self.db)
        pid = ou.create_project(projectname)

        # Storing the names:
        ou.add_name_with_language(name_variant=self.const.ou_name_long,
                                  name_language=self.const.language_en,
                                  name=longname)
        if shortname:
            ou.add_name_with_language(name_variant=self.const.ou_name_long,
                                      name_language=self.const.language_en,
                                      name=shortname)
        ou.write_db()

        # Storing start date
        if start > DateTime.now():
            ou.add_entity_quarantine(type=self.const.quarantine_project_start,
                                     creator=operator.get_entity_id(), start=DateTime.now(),
                                     end=start, description='Initial start set by superuser')
            ou.write_db()
        # Storing end date
        ou.add_entity_quarantine(type=self.const.quarantine_project_end,
                                 creator=operator.get_entity_id(), start=end,
                                 description='Initial end set by superuser')
        ou.write_db()
        ou.setup_project(operator.get_entity_id())
        if not ou.get_entity_quarantine(only_active=True):
            self.gateway.create_project(projectname)
        # TODO: inform the gateway about the resources from here too, or wait
        # for the gateway sync to do that?
        return "New project created: %s" % pid

    all_commands['project_terminate'] = cmd.Command(
        ('project', 'terminate'), ProjectName(),
        perm_filter='is_superuser')

    @superuser
    def project_terminate(self, operator, project_name):
        """Terminate a project by removed almost all of it.

        All information about the project gets deleted except its acronym, to
        avoid reuse of the ID.

        """
        project = self._get_project(project_name)
        # TODO: delete person affiliations?
        # TODO: delete accounts
        project.terminate()
        self.gateway.delete_project(project_name)
        return "Project terminated: %s" % project_name

    all_commands['project_approve'] = cmd.Command(
        ('project', 'approve'), ProjectName(),
        perm_filter='is_superuser')

    @superuser
    def project_approve(self, operator, project_name):
        """Approve an existing project that is not already approved. A project
        is created after we get metadata for it from the outside world, but is
        only visible inside of Cerebrum. When a superuser approves the project,
        it gets spread to AD and gets set up properly.

        """
        project = self._get_project(project_name)
        success_msg = "Project approved: %s" % (project_name)

        # Check if the project was already approved
        if not project.get_entity_quarantine(only_active=True,
                                             type=self.const.quarantine_not_approved):
            # raise CerebrumError('Project already approved (no not_approved quarantine)')
            return success_msg + " (already approved, not changing anything)"

        project.delete_entity_quarantine(type=self.const.quarantine_not_approved)
        project.write_db()
        project.setup_project(operator.get_entity_id())
        if not project.get_entity_quarantine(only_active=True):
            # Active project only if no other quarantines
            self.gateway.create_project(project_name)

        self.logger.info(success_msg)
        return success_msg

    all_commands['project_reject'] = cmd.Command(
        ('project', 'reject'), ProjectName(),
        perm_filter='is_superuser')

    @superuser
    def project_reject(self, operator, project_name):
        """Reject a project that is not approved yet.

        All information about the project gets deleted, since it hasn't been
        exported out of Cerebrum yet.

        """
        project = self._get_project(project_name)
        if not project.get_entity_quarantine(only_active=True,
                                             type=self.const.quarantine_not_approved):
            raise CerebrumError('Can not reject approved projects, you may wish to terminate '
                                'it instead.')

        # TODO: delete person affiliations and accounts?

        project.delete()
        try:
            # Double check that project doesn't exist in Gateway.
            # Will raise exception if it's okay.
            self.gateway.delete_project(project_name)
        except Exception:
            pass
        return "Project deleted: %s" % project_name

    all_commands['project_set_enddate'] = cmd.Command(
        ('project', 'set_enddate'), ProjectName(), cmd.Date(),
        perm_filter='is_superuser')

    @superuser
    def project_set_enddate(self, operator, project_name, enddate):
        """Set the end date for a project.

        """
        project = self._get_project(project_name)
        qtype = self.const.quarantine_project_end
        end = self._parse_date(enddate)
        # The quarantine needs to be removed before it could be added again
        for row in project.get_entity_quarantine(qtype):
            project.delete_entity_quarantine(qtype)
            project.write_db()
        project.add_entity_quarantine(type=qtype,
                                      creator=operator.get_entity_id(),
                                      description='Reset lifetime for project',
                                      start=end)
        project.write_db()
        # If set in the past, the project is now frozen
        if end < DateTime.now():
            # TODO
            self.gateway.freeze_project(project_name)
        return "Project %s updated to end: %s" % (project_name,
                                                  date_to_string(end))

    all_commands['project_freeze'] = cmd.Command(
        ('project', 'freeze'), ProjectName(),
        perm_filter='is_superuser')

    @superuser
    def project_freeze(self, operator, project_name):
        """Freeze a project."""
        project = self._get_project(project_name)
        end = DateTime.now()

        # The quarantine needs to be removed before it could be added again
        qtype = self.const.quarantine_project_freeze
        for row in project.get_entity_quarantine(qtype):
            project.delete_entity_quarantine(qtype)
            project.write_db()
        project.add_entity_quarantine(type=qtype,
                                      creator=operator.get_entity_id(),
                                      description='Project freeze',
                                      start=end)
        project.write_db()
        self.gateway.freeze_project(project_name)
        return "Project %s is now frozen" % project_name

    all_commands['project_unfreeze'] = cmd.Command(
        ('project', 'unfreeze'), ProjectName(),
        perm_filter='is_superuser')

    @superuser
    def project_unfreeze(self, operator, project_name):
        """Unfreeze a project."""
        project = self._get_project(project_name)
        end = DateTime.now()

        # Remove the quarantine
        qtype = self.const.quarantine_frozen
        for row in project.get_entity_quarantine(qtype):
            project.delete_entity_quarantine(qtype)
            project.write_db()

        # Only unthaw projects without quarantines
        if not project.get_entity_quarantine(only_active=True):
            self.gateway.thaw_project(project_name)
        return "Project %s is now unfrozen" % project_name

    all_commands['project_list'] = cmd.Command(
        ('project', 'list'), ProjectStatusFilter(optional=True),
        fs=cmd.FormatSuggestion(
            '%-16s %-10s %s', ('name', 'entity_id', 'quars'),
            hdr='%-16s %-10s %s' % ('Name', 'Entity-Id', 'Quarantines')),
        perm_filter='is_superuser')

    @superuser
    def project_list(self, operator, filter=None):
        """List out all projects by their acronym and status."""

        projects = _Projects(self.logger,
                             self.const,
                             self.OU_class(self.db),
                             exact_match=False,
                             filter=filter)
        return projects.results_sorted_by_name(['name', 'entity_id', 'quars'])

    all_commands['project_unapproved'] = cmd.Command(
        ('project', 'unapproved'),
        fs=cmd.FormatSuggestion(
            '%-16s %-10s', ('name', 'entity_id'),
            hdr='%-16s %-10s' % ('Name', 'Entity-Id')),
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
        return projects.results_sorted_by_name(['name', 'entity_id'])

    all_commands['project_info'] = cmd.Command(
        ('project', 'info'), ProjectName(),
        # TODO: Now we need to copy in ou_info's FormatSuggestion if that has
        # changed!
        fs=cmd.FormatSuggestion([
            ("Stedkode:      %s\n" +
             "Entity ID:     %i\n" +
             "Name (nb):     %s\n" +
             "Name (en):     %s\n" +
             "Quarantines:   %s\n" +
             "Spreads:       %s",
             ('stedkode', 'entity_id', 'name_nb', 'name_en', 'quarantines',
              'spreads')),
            ("Contact:       (%s) %s: %s",
             ('contact_source', 'contact_type', 'contact_value')),
            ("Address:       (%s) %s: %s%s%s %s %s",
             ('address_source', 'address_type', 'address_text', 'address_po_box',
              'address_postal_number', 'address_city', 'address_country')),
            ("Email domain:  affiliation %-7s @%s",
             ('email_affiliation', 'email_domain')),
            ('Project start: %s', ('project_start',)),
            ('Project end:   %s', ('project_end',)),
            ('Quarantine:    %s', ('q_status',)),
        ]),
        perm_filter='is_superuser')

    @superuser
    def project_info(self, operator, projectname):
        """Display information about a specified project using ou_info.

        The reason for the semi-sub method is to be able to specify the OU with
        the projectname instead of entity_id. This could probably be handled in
        a much better way.

        """
        project = self._get_project(projectname)
        ret = self.ou_info(operator, 'id:%d' % project.entity_id)
        now = DateTime.now()

        # Quarantine status:
        quarantined = None
        for q in project.get_entity_quarantine(only_active=False):
            if q['start_date'] > now:
                # Ignore quarantines in the future for now, as all projects
                # should have an end quarantine
                continue
            if (q['end_date'] is not None and
                    q['end_date'] < now):
                quarantined = 'expired'
            elif (q['disable_until'] is not None and
                  q['disable_until'] > now):
                quarantined = 'disabled'
            else:
                quarantined = 'active'
                break
        if quarantined:
            ret.append({'q_status': quarantined})

        for row in project.get_entity_quarantine(
                self.const.quarantine_project_start):
            pass

        # Project start:
        for row in project.get_entity_quarantine(
                self.const.quarantine_project_start):
            ret.append({'project_start': date_to_string(row['end_date'])})
        # Project end:
        for row in project.get_entity_quarantine(
                self.const.quarantine_project_end):
            ret.append({'project_end': date_to_string(row['start_date'])})
        return ret

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
        raise CerebrumError, "Too many arguments"

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

        # Only superusers should be allowed to create users with
        # capital letters in their ids, and even then, just for system
        # users
        if uname != uname.lower():
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise CerebrumError("Account names cannot contain capital letters")
            else:
                if owner_type != self.const.entity_group:
                    raise CerebrumError("Personal account names cannot contain capital letters")

        # TODO: Add a check for personal accounts to have the project name as a
        # prefix?
        # if owner_type == self.const.entity_person:
        #    ou_id, affiliation = affiliation['ou_id'], affiliation['aff']
        #    ou = self._get_ou(ou_id=ou_id)
        #    projectname = self._format_ou_name(ou, include_short_name=False)
        #    if not uname.startswith(projectname):
        #        raise CerebrumError('Username must have projectname as prefix')

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
            projectname = self._format_ou_name(ou, include_short_name=False)
            gr = self._get_group('%s_dfg' % projectname, grtype='PosixGroup')

        posix_user.populate(uid, gr.entity_id, None, shell, name=uname,
                            owner_type=owner_type, owner_id=owner_id,
                            np_type=np_type, creator_id=operator.get_entity_id(),
                            expire_date=None)
        try:
            posix_user.write_db()
            # for spread in cereconf.BOFHD_NEW_USER_SPREADS:
            #    posix_user.add_spread(self.const.Spread(spread))
            # homedir_id = posix_user.set_homedir(
            #    disk_id=disk_id, home=home,
            #    status=self.const.home_status_not_created)
            # posix_user.set_home(self.const.spread_nis_user, homedir_id)
            # For correct ordering of ChangeLog events, new users
            # should be signalled as "exported to" a certain system
            # before the new user's password is set.  Such systems are
            # flawed, and should be fixed.
            passwd = posix_user.make_passwd(uname)
            posix_user.set_password(passwd)
            posix_user.write_db()
            if posix_user.owner_type == self.const.entity_person:
                self._user_create_set_account_type(posix_user, owner_id,
                                                   ou_id, affiliation)
        except self.db.DatabaseError, m:
            raise CerebrumError("Database error: %s" % m)
        operator.store_state("new_account_passwd", {'account_id': int(posix_user.entity_id),
                                                    'password': passwd})
        return "Ok, created %s (entity_id:%s)" % (posix_user.account_name, uid)

    # user password
    all_commands['user_set_password'] = cmd.Command(
        ('user', 'set_password'), cmd.AccountName(), cmd.AccountPassword(optional=True))

    def user_set_password(self, operator, accountname, password=None):
        """Set password for a user. Copied from UiO, but renamed for TSD."""
        return self.user_password(operator, accountname, password)

    # user password
    all_commands['user_generate_otpkey'] = cmd.Command(
        ('user', 'generate_otpkey'), cmd.AccountName())

    def user_generate_otpkey(self, operator, accountname):
        account = self._get_account(accountname)
        self.ba.can_generate_otpkey(operator.get_entity_id(), account)
        account.regenerate_otpkey()
        try:
            account.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError("Database error: %s" % m)
        # TODO: put the key in the session?
        # Remove "weak password" quarantine
        if account.is_deleted():
            return "OK.  Warning: user is deleted"
        elif account.is_expired():
            return "OK.  Warning: user is expired"
        elif account.get_entity_quarantine(only_active=True):
            return "Warning: user has an active quarantine"
        return "OTP-key regenerated."

    # user approve
    all_commands['user_approve'] = cmd.Command(
        ('user', 'approve'), cmd.AccountName(),
        perm_filter='is_superuser')

    def user_approve(self, operator, accountname):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise CerebrumError('Only superusers could approve users')
        account = self._get_account(accountname)
        if not account.get_entity_quarantine(
                type=self.const.quarantine_not_approved):
            raise CerebrumError('Account does not need approval: %s' %
                                accountname)
        account.delete_entity_quarantine(self.const.quarantine_not_approved)
        account.write_db()
        return 'Approved account: %s' % account.account_name
        # TODO: add more feedback, e.g. tell if account is expired or has other
        # quarantines?

    #
    # Group commands

    all_commands['group_create'] = cmd.Command(
        ("group", "create"),
        ProjectName(), cmd.GroupName(), GroupDescription(),
        perm_filter='is_superuser')

    @superuser
    def group_create(self, operator, project, group, description):
        """Method for creating a new group"""

        self.logger.debug2("group create start")

        ac = self.Account_class(self.db)

        try:
            ac.find_by_name(groupname)
        except Errors.NotFoundError:
            pass
        else:
            # Necessary because of AD
            raise CerebrumError('An account exists with name: %s' % groupname)

        self.ba.can_create_group(operator.get_entity_id())
        g = self.Group_class(self.db)
        g.populate(creator_id=operator.get_entity_id(),
                   visibility=self.const.group_visibility_all,
                   name=groupname, description=description)

        # TODO: Figure out how populate_trait works
        # g.populate_trait(co.

        try:
            g.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError("Database error: %s" % m)
        for spread in cereconf.BOFHD_NEW_GROUP_SPREADS:
            g.add_spread(self.const.Spread(spread))
            g.write_db()

        self.logger.debug2("group create stop")

        return {'group_id': int(g.entity_id)}

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
            try:
                src_entity = self.util.get_target(src_name,
                                                  restrict_to=['Person'])
            except Errors.TooManyRowsError:
                raise CerebrumError("Unexpectedly found more than one person")
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
                    return "Recursive memberships are not allowed (%s is member of %s)" % (dest_group, src_name)
        # This can still fail, e.g., if the entity is a member with a different
        # operation.
        try:
            dest_group.add_member(src_entity.entity_id)
        except self.db.DatabaseError, m:
            raise CerebrumError("Database error: %s" % m)
        # TODO: If using older versions of NIS, a user could only be a member of
        # 16 group. You might want to be warned about this - Or is this only
        # valid for UiO?
        return "OK, added %s to %s" % (src_name, dest_group)

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

    #
    # Subnet commands

    # TODO

    # subnet create
    # all_commands['subnet_create'] = cmd.Command(
    #    ("subnet", "create"),
    #    Subnet(), cmd.Description(), Vlan(),
    #    perm_filter='is_superuser')
    # def subnet_create(self, operator, subnet, description, vlan):
    #    """Create a new subnet, if the range is not already reserved.

    #    TODO: Should it be possible to specify a range, or should we find one
    #    randomly?

    #    """
    #    if not self.ba.is_superuser(operator.get_entity_id()):
    #        raise CerebrumError('Only superusers are allowed to do this')
    #    subnet = Subnet.Subnet(self.db)
    #    subnet.populate(subnet, description=description, vlan=vlan)
    # TODO: more checks?
    #    subnet.write_db(perform_checks=True)
    #    return "Subnet created: %s" % subnet

    # def add_subnet(subnet, description, vlan, perform_checks=True):


class EnduserBofhdExtension(TSDBofhdExtension):

    """The bofhd commands for the end users of TSD.

    End users are Project Administrators (PA), which should have full control of
    their project, and Project Members (PM) which have limited privileges.

    """

    all_commands = {}
    hidden_commands = {}

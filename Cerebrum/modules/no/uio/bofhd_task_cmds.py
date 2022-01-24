# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
"""
This module contains task-related commands for UiO.
"""
from __future__ import absolute_import, print_function, unicode_literals
import logging

import six

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.cmd_param import (
    Command,
    FormatSuggestion,
    PersonId,
    SimpleString,
)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.greg.datasource import normalize_id as _norm_greg_id
from Cerebrum.modules.greg.tasks import GregImportTasks
from Cerebrum.modules.import_utils import syncs
from Cerebrum.modules.no.dfo.datasource import normalize_id as _norm_dfo_id
from Cerebrum.modules.no.dfo.tasks import AssignmentTasks, EmployeeTasks
from Cerebrum.modules.no.uio.bofhd_auth import UioAuth
from Cerebrum.modules.tasks import bofhd_task_cmds

logger = logging.getLogger(__name__)


def _parse_dfo_pid(value):
    """ Try to parse lookup value as a DFO_PID. """
    # 'dfo_pid:<employee-number>', 'dfo:<emplyee-number>'
    if value.partition(':')[0].lower() in ('dfo', 'dfo_pid'):
        value = value.partition(':')[2]
    # <employee-number>
    return _norm_dfo_id(value)


def _parse_greg_id(value):
    """ Try to parse lookup value as a GREG_PID. """
    # 'greg:<greg-id>', 'greg_id:<greg-id>'
    if value.partition(':')[0].lower() in ('greg', 'greg_pid'):
        value = value.partition(':')[2]
    # <greg-id>
    return _norm_greg_id(value)


def find_by_dfo_pid(db, dfo_pid):
    """ Find Person-object by DFO_PID value. """
    pe = Factory.get('Person')(db)
    co = pe.const
    try:
        pe.find_by_external_id(co.externalid_dfo_pid, dfo_pid)
        return pe
    except Errors.NotFoundError:
        raise CerebrumError('Unknown employee: ' + repr(dfo_pid))


def find_by_greg_id(db, greg_id):
    """ Find Person-object by GREG_ID value. """
    pe = Factory.get('Person')(db)
    co = pe.const
    try:
        pe.find_by_external_id(co.externalid_greg_pid, greg_id)
        return pe
    except Errors.NotFoundError:
        raise CerebrumError('Unknown greg person: ' + repr(greg_id))


def find_unique_external_ids(person, source_system):
    """
    Identify external id types that are *only* registered in the given
    source system.

    :type person: Cerebrum.Person.Person
    :type source_system: Cerebrum.Constants._AutoritativeSystemCode
    """
    co = person.const

    source_map = {}
    values = {}
    for row in person.get_external_id():
        sys = co.AuthoritativeSystem(row['source_system'])
        typ = co.EntityExternalId(row['id_type'])
        val = row['external_id']
        if sys == source_system:
            values[typ] = val
        source_map.setdefault((typ, val), []).append(sys)

    duplicates = []
    for (typ, val), sources in source_map.items():
        if source_system in sources and len(sources) > 1:
            duplicates.append(typ)

    return tuple(
        (typ, values[typ])
        for typ in values
        if typ not in duplicates)


class BofhdTaskAuth(UioAuth, bofhd_task_cmds.BofhdTaskAuth):

    def can_dfo_import(self, operator,  query_run_any=False):
        """Access to list which entities has a trait."""
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_import_dfo_person)
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_import_dfo_person):
            return True
        raise PermissionDenied('No access to import queue')

    def can_greg_import(self, operator, query_run_any=False):
        """Access to list which entities has a trait."""
        if self.is_superuser(operator):
            return True
        # TODO:
        # Add auth consts for greg?  Or better, add a generic task_queue auth
        # type, and use queue/sub-queue params?
        # If so, we should add greg bofhd-auth constants, and move these checks
        # to the generic BofhdTaskAuth
        if query_run_any:
            # return self._has_operation_perm_somewhere(
            #     operator, self.const.auth_import_dfo_person)
            return False
        # if self._has_operation_perm_somewhere(
        #         operator, self.const.auth_import_dfo_person):
        #     return True
        raise PermissionDenied('No access to import queue')

    def can_clear_sap_data(self, operator, query_run_any=False):
        has_access = self.is_superuser(operator)
        if query_run_any or has_access:
            return has_access
        raise PermissionDenied('No access to clear hr data')


class BofhdTaskCommands(bofhd_task_cmds.BofhdTaskCommands):

    all_commands = {}
    authz = BofhdTaskAuth
    parent_commands = True
    omit_parent_commands = (
        # disallow task_add, as adding tasks without payload may beak
        # some imports.  Replaced by person_*_import
        'task_add',
    )

    @classmethod
    def get_help_strings(cls):
        grp_help = {}  # 'person' should already exist in parent
        cmd_help = {'person': {}}
        for name in cls.all_commands:
            if name in cmd_help['person']:
                continue
            # set command help to first line of docstring
            try:
                doc = getattr(cls, name).__doc__.lstrip()
            except AttributeError:
                continue
            first = doc.splitlines()[0].strip()
            cmd_help['person'][name] = first.rstrip('.')

        arg_help = {
            'dfo-pid': [
                'dfo-pid',
                'Enter DFØ employee identifier',
                ('Enter a valid employee number or other cerebrum person'
                 ' identifier'),
            ],
            'greg-pid': [
                'greg-pid',
                'Enter Greg person identifier',
                ('Enter a valid greg person id or other cerebrum person'
                 ' identifier'),
            ],
        }

        return merge_help_strings(
            super(BofhdTaskCommands, cls).get_help_strings(),
            (grp_help, cmd_help, arg_help))

    def _get_person(self, value):
        try:
            return self.util.get_target(value, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")

    def _get_dfo_pid(self, value):
        """
        Get DFO_PID from user argument.

        This helper function allow users to provide a DFO_PID value directly,
        or fetch a DFO_PID from an existing Person-object.
        """
        try:
            return _parse_dfo_pid(value)
        except ValueError:
            pass

        # other identifiers, e.g. <username>, person:<username>, id:<entity-id>
        try:
            pe = self._get_person(value)
            row = pe.get_external_id(source_system=pe.const.system_dfosap,
                                     id_type=pe.const.externalid_dfo_pid)
            return int(row['external_id'])
        except Exception:
            raise CerebrumError("Invalid DFO_PID: " + repr(value))

    def _get_dfo_person(self, value):
        """
        Get Person from user argument.

        This helper function allow users to look up Person-objects in Cerebrum
        in the usual ways, and additionally by providing a valid DFO_PID.
        """
        try:
            dfo_pid = _parse_dfo_pid(value)
            find_by_dfo_pid(self.db, dfo_pid)
        except ValueError:
            pass

        # other identifiers, e.g. <username>, person:<username>, id:<entity-id>
        return self._get_person(value)

    #
    # person dfo_import <employee>
    #
    all_commands['person_dfo_import'] = Command(
        ("person", "dfo_import"),
        SimpleString(help_ref='dfo-pid'),
        fs=bofhd_task_cmds.BofhdTaskCommands._add_task_fs,
        perm_filter='can_dfo_import',
    )

    def person_dfo_import(self, operator, lookup_value):
        """ Add an employee to the hr import queue. """
        self.ba.can_dfo_import(operator.get_entity_id())
        dfo_pid = self._get_dfo_pid(lookup_value)
        task = EmployeeTasks.create_manual_task(dfo_pid)
        return self._add_task(task)

    #
    # person dfo_cancel <key>
    #
    all_commands['person_dfo_cancel'] = Command(
        ("person", "dfo_cancel"),
        SimpleString(help_ref='dfo-pid'),
        fs=bofhd_task_cmds.BofhdTaskCommands._remove_task_fs,
        perm_filter='can_dfo_import',
    )

    def person_dfo_cancel(self, operator, dfo_pid):
        """ Cancel a previously added task from the hr import queue. """
        self.ba.can_dfo_import(operator.get_entity_id())

        if not dfo_pid.isdigit():
            raise CerebrumError('Invalid employee id: ' + repr(dfo_pid))

        queue = EmployeeTasks.queue
        sub = EmployeeTasks.manual_sub
        return self._remove_task(queue, sub, dfo_pid)

    #
    # person dfo_queue <employee>
    #
    all_commands['person_dfo_queue'] = Command(
        ("person", "dfo_queue"),
        SimpleString(help_ref='dfo-pid'),
        fs=bofhd_task_cmds.BofhdTaskCommands._search_tasks_list_fs,
        perm_filter='can_dfo_import',
    )

    def person_dfo_queue(self, operator, lookup_value):
        """ Show tasks in the dfo import queues. """
        self.ba.can_dfo_import(operator.get_entity_id())
        dfo_pid = self._get_dfo_pid(lookup_value)
        # include known, un-normalized keys
        params = {
            'queues': EmployeeTasks.queue,
            'keys': tuple(
                key_fmt % int(dfo_pid)
                for key_fmt in ('%d', '0%d', '%d\r', '0%d\r')
            ) + (dfo_pid,),
        }

        tasks = list(self._search_tasks(params))
        if tasks:
            return tasks
        raise CerebrumError('No dfo-import in queue for: '
                            + repr(lookup_value))

    #
    # person dfo_stats
    #
    all_commands['person_dfo_stats'] = Command(
        ("person", "dfo_stats"),
        fs=bofhd_task_cmds.BofhdTaskCommands._get_queue_stats_fs,
        perm_filter='can_dfo_import',
    )

    def person_dfo_stats(self, operator):
        """ Get task counts for the dfo import queues. """
        self.ba.can_dfo_import(operator.get_entity_id())
        results = list(self._get_queue_stats(EmployeeTasks.queue,
                                             EmployeeTasks.max_attempts))
        results.extend(self._get_queue_stats(AssignmentTasks.queue,
                                             AssignmentTasks.max_attempts))
        if results:
            return results
        raise CerebrumError('No queued dfo import tasks')

    # Greg utils

    def _get_greg_id(self, value):
        """
        Get GREG_PID from user argument.

        This helper function allow users to provide a GREG_PID value directly,
        or fetch a GREG_PID from an existing Person-object.
        """
        try:
            return _parse_greg_id(value)
        except ValueError:
            pass

        # other identifiers, e.g. <username>, person:<username>, id:<entity-id>
        try:
            pe = self._get_person(value)
            row = pe.get_external_id(source_system=pe.const.system_greg,
                                     id_type=pe.const.externalid_greg_pid)
            return int(row['external_id'])
        except Exception:
            raise CerebrumError("Invalid GREG_PID: " + repr(value))

    def _get_greg_person(self, value):
        """
        Get Person from user argument.

        This helper function allow users to look up Person-objects in Cerebrum
        in the usual ways, and additionally by providing a valid GREG_PID.
        """
        try:
            greg_id = _parse_greg_id(value)
            find_by_greg_id(self.db, greg_id)
        except ValueError:
            pass

        # other identifiers, e.g. <username>, person:<username>, id:<entity-id>
        return self._get_person(value)

    #
    # person greg_import <employee>
    #
    all_commands['person_greg_import'] = Command(
        ("person", "greg_import"),
        SimpleString(help_ref='greg-pid'),
        fs=bofhd_task_cmds.BofhdTaskCommands._add_task_fs,
        perm_filter='can_greg_import',
    )

    def person_greg_import(self, operator, lookup_value):
        """ Add a guest to the greg import queue. """
        self.ba.can_greg_import(operator.get_entity_id())
        key = self._get_greg_id(lookup_value)
        task = GregImportTasks.create_manual_task(key)
        return self._add_task(task)

    #
    # person greg_cancel <key>
    #
    all_commands['person_greg_cancel'] = Command(
        ("person", "greg_cancel"),
        SimpleString(help_ref='greg-pid'),
        fs=bofhd_task_cmds.BofhdTaskCommands._remove_task_fs,
        perm_filter='can_greg_import',
    )

    def person_greg_cancel(self, operator, greg_pid):
        """ Cancel a previously added task from the greg import queue. """
        self.ba.can_greg_import(operator.get_entity_id())

        if not greg_pid.isdigit():
            raise CerebrumError('Invalid greg id: ' + repr(greg_pid))

        queue = GregImportTasks.queue
        sub = GregImportTasks.manual_sub
        return self._remove_task(queue, sub, greg_pid)

    #
    # person greg_queue <employee>
    #
    all_commands['person_greg_queue'] = Command(
        ("person", "greg_queue"),
        SimpleString(help_ref='greg-pid'),
        fs=bofhd_task_cmds.BofhdTaskCommands._search_tasks_info_fs,
        perm_filter='can_greg_import',
    )

    def person_greg_queue(self, operator, lookup_value):
        """ Show tasks in the greg import queues. """
        self.ba.can_greg_import(operator.get_entity_id())
        params = {
            'queues': GregImportTasks.queue,
            'keys': self._get_greg_id(lookup_value),
        }
        tasks = list(self._search_tasks(params))
        if tasks:
            return tasks
        raise CerebrumError('No greg-import in queue for: '
                            + repr(lookup_value))

    #
    # person greg_stats
    #
    all_commands['person_greg_stats'] = Command(
        ("person", "greg_stats"),
        fs=bofhd_task_cmds.BofhdTaskCommands._get_queue_stats_fs,
        perm_filter='can_greg_import',
    )

    def person_greg_stats(self, operator):
        """ Get task counts for the greg import queues. """
        self.ba.can_greg_import(operator.get_entity_id())
        results = list(self._get_queue_stats(GregImportTasks.queue,
                                             GregImportTasks.max_attempts))
        if results:
            return results
        raise CerebrumError('No queued greg import tasks')

    #
    # person clear_sap_affiliations <person>
    #
    all_commands['person_clear_sap_affiliations'] = Command(
        ("person", "clear_sap_affiliations"),
        PersonId(help_ref="id:target:person"),
        fs=FormatSuggestion(
            'Removed %s @ ou_id=%d', ('affiliation', 'ou_id'),
        ),
        perm_filter='can_clear_sap_data',
    )

    def person_clear_sap_affiliations(self, operator, person_id):
        """
        Remove obsolete affiliations from SAP.

        This command removes affiliations from the SAP source system for the
        given *person_id*.
        """
        self.ba.can_clear_sap_data(operator.get_entity_id())

        person = self._get_person(person_id)
        source_system = self.const.system_sap

        aff_sync = syncs.AffiliationSync(self.db, source_system)
        added, updated, removed = aff_sync(person, ())

        if added | updated:
            raise RuntimeError('Updated aff?')

        if not removed:
            raise CerebrumError('No affiliations to remove from '
                                + six.text_type(source_system))

        return [{
            'person_id': int(person.entity_id),
            'source_system': six.text_type(source_system),
            'affiliation': six.text_type(aff),
            'ou_id': int(ou_id),
        } for ou_id, aff, _ in removed]

    #
    # person clear_sap_data <person>
    #
    all_commands['person_clear_sap_data'] = Command(
        ("person", "clear_sap_data"),
        PersonId(help_ref="id:target:person"),
        fs=FormatSuggestion(
            'Removed %s type=%s', ('category', 'type'),
        ),
        perm_filter='can_clear_sap_data',
    )

    def person_clear_sap_data(self, operator, person_id):
        """
        Remove obsolete person info from SAP.

        This command removes contact info, names, and some external ids from
        the SAP source system for a given *person_id*.

        Note:
            - Old employee ids are not removed
            - FNR and PASSNR is only removed if the same info also exists in
              other sources.
        """
        self.ba.can_clear_sap_data(operator.get_entity_id())

        person = self._get_person(person_id)
        source_system = self.const.system_sap
        removed = []

        c_sync = syncs.ContactInfoSync(self.db, source_system)
        n_sync = syncs.PersonNameSync(self.db, source_system)
        i_sync = syncs.ExternalIdSync(self.db, source_system)

        c_add, c_mod, c_rem = c_sync(person, ())
        if c_add | c_mod:
            raise RuntimeError("this shouldn't happen!")
        for c_type in c_rem:
            removed.append({
                'category': 'contact_info',
                'person_id': int(person.entity_id),
                'source_system': six.text_type(source_system),
                'type': six.text_type(c_type),
            })

        n_add, n_mod, n_rem = n_sync(person, ())
        if n_add | n_mod:
            raise RuntimeError("this shouldn't happen!")
        for n_var in n_rem:
            removed.append({
                'category': 'person_name',
                'person_id': int(person.entity_id),
                'source_system': six.text_type(source_system),
                'type': six.text_type(n_var),
            })

        keep_ids = find_unique_external_ids(person, source_system)

        i_add, i_mod, i_rem = i_sync(person, keep_ids)
        if i_add | i_mod:
            raise RuntimeError("this shouldn't happen!")
        for id_type in i_rem:
            removed.append({
                'category': 'external_id',
                'person_id': int(person.entity_id),
                'source_system': six.text_type(source_system),
                'type': six.text_type(id_type),
            })

        if not removed:
            raise CerebrumError('No person info to remove from '
                                + six.text_type(source_system))
        return removed

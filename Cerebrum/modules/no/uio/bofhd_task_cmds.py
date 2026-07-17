# -*- coding: utf-8 -*-
#
# Copyright 2021-2023 University of Oslo, Norway
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
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.cmd_param import (
    Command,
    SimpleString,
)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.greg import bofhd_greg_cmds
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


def find_by_dfo_pid(db, dfo_pid):
    """ Find Person-object by DFO_PID value. """
    pe = Factory.get('Person')(db)
    co = pe.const
    try:
        pe.find_by_external_id(co.externalid_dfo_pid, dfo_pid)
        return pe
    except Errors.NotFoundError:
        raise CerebrumError('Unknown employee: ' + repr(dfo_pid))


class BofhdTaskAuth(UioAuth,
                    bofhd_greg_cmds.BofhdGregAuth,
                    bofhd_task_cmds.BofhdTaskAuth):
    """ UiO-specific task auth. """

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


class BofhdTaskCommands(bofhd_greg_cmds.BofhdGregCommands,
                        bofhd_task_cmds.BofhdTaskCommands):
    all_commands = {}
    authz = BofhdTaskAuth
    parent_commands = True
    omit_parent_commands = (
        # disallow task_add, as adding tasks without payload may beak
        # some imports.
        # task_add is implemented through queue-specific commands, such as
        # `greg import` or `person_dfo_import`.
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

    #
    # deprecated person greg_* commands
    #
    all_commands['person_greg_import'] = Command(
        ("person", "greg_import"),
        SimpleString(),
        # this command used to be available to superusers only:
        perm_filter='is_superuser',
    )

    def person_greg_import(self, operator, lookup_value):
        """ deprecated; use `greg import`. """
        raise CerebrumError("deprecated; use `greg import %s`"
                            % (lookup_value,))

    all_commands['person_greg_cancel'] = Command(
        ("person", "greg_cancel"),
        SimpleString(),
        # this command used to be available to superusers only:
        perm_filter='is_superuser',
    )

    def person_greg_cancel(self, operator, lookup_value):
        """ deprecated; use `greg cancel`. """
        raise CerebrumError("deprecated; use `greg cancel %s`"
                            % (lookup_value,))

    all_commands['person_greg_queue'] = Command(
        ("person", "greg_queue"),
        SimpleString(),
        # this command used to be available to superusers only:
        perm_filter='is_superuser',
    )

    def person_greg_queue(self, operator, lookup_value):
        """ deprecated; use `greg tasks`. """
        raise CerebrumError("deprecated; use `greg tasks %s`"
                            % (lookup_value,))

    all_commands['person_greg_stats'] = Command(
        ("person", "greg_stats"),
        # this command used to be available to superusers only:
        perm_filter='is_superuser',
    )

    def person_greg_stats(self, operator):
        """ deprecated; use `greg stats`. """
        raise CerebrumError("deprecated; use `greg stats`")

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
This module contains Greg related bofhd commands.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import logging
import textwrap

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.cmd_param import (
    Command,
    SimpleString,
)
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.greg.datasource import normalize_id as _norm_greg_id
from Cerebrum.modules.greg.tasks import GregImportTasks
from Cerebrum.modules.tasks import bofhd_task_cmds


logger = logging.getLogger(__name__)


def _parse_greg_id(value):
    """ Try to parse lookup value as a GREG_PID. """
    # 'greg:<greg-id>', 'greg_id:<greg-id>'
    if value.partition(':')[0].lower() in ('greg', 'greg_pid'):
        value = value.partition(':')[2]
    # <greg-id>
    return _norm_greg_id(value)


def _get_shortdoc(fn):
    """ Get first line of docsting. """
    doc = (fn.__doc__ or "")
    for line in doc.splitlines():
        line = line.strip().rstrip(".")
        if line:
            return line
    return ""


def find_by_greg_id(db, greg_id):
    """ Find Person-object by GREG_ID value. """
    pe = Factory.get('Person')(db)
    co = pe.const
    try:
        pe.find_by_external_id(co.externalid_greg_pid, greg_id)
        return pe
    except Errors.NotFoundError:
        raise CerebrumError('Unknown greg person: ' + repr(greg_id))


class BofhdGregAuth(bofhd_task_cmds.BofhdTaskAuth):
    """
    Greg-related permission checks.

    These checks are mostly just proxies for other task-related permissions,
    but we might want to add overrides for greg-related tasks later.
    """

    def can_greg_queue_add(self, operator, queue=None, sub=None,
                           query_run_any=False):
        """ Access to add greg tasks. """
        return self.can_add_task(operator, queue=queue, sub=sub,
                                 query_run_any=query_run_any)

    def can_greg_queue_remove(self, operator, queue=None, sub=None, key=None,
                              query_run_any=False):
        """ Access to remove greg tasks. """
        return self.can_remove_task(operator, queue=queue, sub=sub,
                                    query_run_any=query_run_any)

    def can_greg_queue_show_tasks(self, operator, queue=None,
                                  query_run_any=False):
        """ Access to show greg tasks. """
        return self.can_inspect_tasks(operator, queue=queue,
                                      query_run_any=query_run_any)

    def can_greg_queue_show_stats(self, operator, queue=None,
                                  query_run_any=False):
        """ Access to show greg task stats. """
        return self.can_inspect_tasks(operator, queue=queue,
                                      query_run_any=query_run_any)


class BofhdGregCommands(bofhd_task_cmds.BofhdTaskCommands):
    """
    Guest system integration commands.

    Note that these commands are mostly aliases for _other_ task-commands.

    Ideally we should add support for *aliases*, where we just call another
    command (and inform the operator which command we *actually* run).  That
    would:

     - Save on the implementation cost of similar commands
     - Help educate operators on how some of the more generic commands work
     - Make *deprecating* commands easier.
    """

    all_commands = {}
    authz = BofhdGregAuth
    parent_commands = False

    # Task class - this provides us with:
    #  1. Task parameters (default queue, max attempts, ...)
    #  2. Class method for creating manual tasks.
    greg_task_cls = GregImportTasks

    @classmethod
    def get_help_strings(cls):
        return merge_help_strings(
            super(BofhdGregCommands, cls).get_help_strings(),
            (HELP_GROUPS, HELP_CMDS, HELP_ARGS),
        )

    def _get_person(self, value):
        # TODO: Better/more consistent/better documented input
        #
        # We really only need to support "id:<entity-id>", "person:<username>"
        # here.
        try:
            return self.util.get_target(value, restrict_to=["Person"])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")

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
            for row in pe.get_external_id(
                    source_system=pe.const.system_greg,
                    id_type=pe.const.externalid_greg_pid):
                return row['external_id']
        except Exception:
            pass
        raise CerebrumError("Invalid GREG_PID: " + repr(value))

    def _get_greg_person(self, value):
        """
        Get Person from user argument.

        This helper function allow users to look up Person-objects in Cerebrum
        in the usual ways, and additionally by providing a valid GREG_PID.
        """
        try:
            greg_id = _parse_greg_id(value)
            return find_by_greg_id(self.db, greg_id)
        except (ValueError, CerebrumError):
            pass

        # other identifiers, e.g. <username>, person:<username>, id:<entity-id>
        return self._get_person(value)

    #
    # greg import_manual <greg-pid>
    #
    all_commands['greg_import'] = Command(
        ("greg", "import"),
        SimpleString(help_ref="greg-pid"),
        fs=bofhd_task_cmds.BofhdTaskCommands._add_task_fs,
        perm_filter="can_greg_queue_add",
    )

    def greg_import(self, operator, lookup_value):
        """ Add a manual import task to the greg import queue. """
        key = self._get_greg_id(lookup_value)
        task = self.greg_task_cls.create_manual_task(key)
        self.ba.can_greg_queue_add(operator.get_entity_id(),
                                   queue=task.queue,
                                   sub=task.sub)
        return self._add_task(task)

    #
    # greg import_cancel <greg-pid>
    #
    all_commands['greg_cancel'] = Command(
        ("greg", "cancel"),
        SimpleString(help_ref="greg-pid"),
        fs=bofhd_task_cmds.BofhdTaskCommands._remove_task_fs,
        perm_filter="can_greg_queue_remove",
    )

    def greg_cancel(self, operator, lookup_value):
        """ Remove a manually added task from the greg import queue. """
        queue = self.greg_task_cls.queue
        sub = self.greg_task_cls.manual_sub
        self.ba.can_greg_queue_remove(operator.get_entity_id(),
                                      queue=queue,
                                      sub=sub)

        greg_pid = self._get_greg_id(lookup_value)
        return self._remove_task(queue, sub, greg_pid)

    #
    # greg_queue_show <greg-pid>
    #
    all_commands['greg_tasks'] = Command(
        ("greg", "tasks"),
        SimpleString(help_ref="greg-pid"),
        fs=bofhd_task_cmds.BofhdTaskCommands._search_tasks_info_fs,
        perm_filter="can_greg_queue_show_tasks",
    )

    def greg_tasks(self, operator, lookup_value):
        """ Show tasks for a person on the greg import queue. """
        queue = self.greg_task_cls.queue
        self.ba.can_greg_queue_show_tasks(operator.get_entity_id(),
                                          queue=queue)
        tasks = list(
            self._search_tasks({
                'queues': queue,
                'keys': self._get_greg_id(lookup_value),
            })
        )
        if tasks:
            return tasks
        raise CerebrumError("No import task in queue for: "
                            + repr(lookup_value))

    #
    # greg queue_stats
    #
    all_commands['greg_stats'] = Command(
        ("greg", "stats"),
        fs=bofhd_task_cmds.BofhdTaskCommands._get_queue_stats_fs,
        perm_filter="can_greg_queue_show_stats",
    )

    def greg_stats(self, operator):
        """ Show number of tasks on the greg import queue. """
        queue = self.greg_task_cls.queue
        self.ba.can_greg_queue_show_stats(operator.get_entity_id(),
                                          queue=queue)
        results = list(
            self._get_queue_stats(queue, self.greg_task_cls.max_attempts))
        if results:
            return results
        raise CerebrumError("No import tasks in queue")


HELP_GROUPS = {
    'greg': _get_shortdoc(BofhdGregCommands),
}

# If not given here, command help be read from command implementation
# docstrings.
HELP_CMDS = {
    'greg': {
        'greg_cancel': _get_shortdoc(BofhdGregCommands.greg_cancel),
        'greg_import': _get_shortdoc(BofhdGregCommands.greg_import),
        'greg_stats': _get_shortdoc(BofhdGregCommands.greg_stats),
        'greg_tasks': _get_shortdoc(BofhdGregCommands.greg_tasks),

    },
}

HELP_ARGS = {
    'greg-pid': [
        "greg-pid",
        "Enter Greg person identifier",
        textwrap.dedent(
            """
            Enter a valid greg person id

            Supported lookups:

            - <greg-pid>
            - greg:<greg-pid>

            Most commands also allows fetching the greg person id from a
            generic cerebrum person identifier if it exists in cerebrum, e.g.:

            - id:<person-id>
            - person:<username>
            """
        ).strip(),
    ],
}

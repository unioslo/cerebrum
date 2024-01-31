# -*- coding: utf-8 -*-
#
# Copyright 2022-2023 University of Oslo, Norway
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
This module contains generic commands for interacting with the task queues.
"""
from __future__ import absolute_import, print_function, unicode_literals

import logging

from Cerebrum import Errors
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.bofhd_utils import format_time
from Cerebrum.modules.bofhd.cmd_param import (
    Command,
    FormatSuggestion,
    SimpleString,
)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.bofhd import parsers
from Cerebrum.modules.tasks.task_models import Task
from Cerebrum.modules.tasks.task_queue import (
    TaskQueue,
    sql_search,
    sql_get_subqueue_counts,
)
from Cerebrum.utils import date as date_utils

logger = logging.getLogger(__name__)


# task-id is a special value used to communicate task queue, sub-queue, and key
# in one single argument between a bofh client and bofh server


def parse_task_id(task_id, default_sub):
    """ Parse task_id user input """
    parts = task_id.split('/')
    if len(parts) == 2:
        queue, key = parts
        sub = default_sub
    elif len(parts) == 3:
        queue, sub, key = parts
    else:
        raise CerebrumError('invalid task-id: %s'
                            ' (valid formats: q/k, q/s/k, q//k)'
                            % repr(task_id))

    queue = queue.strip()
    if not queue:
        raise CerebrumError('invalid task-id: %s (missing queue)'
                            % repr(task_id))
    key = key.strip()
    if not key:
        raise CerebrumError('invalid task-id: %s (missing key)'
                            % repr(task_id))

    logger.debug('task_id=%r -> queue=%r, sub=%r, key=%r',
                 task_id, queue, sub, key)
    return (queue, sub, key)


def format_task_id(task):
    """ Format a valid task_id user input from task info. """
    if isinstance(task, Task):
        parts = task.queue, task.sub or '', task.key
    else:
        parts = task['queue'], task['sub'] or '', task['key']
    return '/'.join(parts)


def format_queue_id(task_like):
    """ Format a queue_id (task_id without key). """
    if isinstance(task_like, Task):
        parts = task_like.queue, task_like.sub or ''
    else:
        parts = task_like['queue'], task_like['sub'] or ''
    return '/'.join(parts)


def format_task(task):
    """ Get Task dict, supplemented by task_id and queue_id. """
    if isinstance(task, Task):
        task = task.to_dict()
    else:
        task = dict(task)
    task.update({
        'task_id': format_task_id(task),
        'queue_id': format_queue_id(task),
    })
    return task


def format_queue_count(row):
    d = dict(row)
    d.update({
        'queue_id': format_queue_id(d),
    })
    return d


_task_id_help_blurb = """
task-id is a string, format: "<queue>/[<sub-queue>/]<key>"

To add or remove tasks using task-id:

   `task add foo-update//123`
   `task add foo-update/manual/123`
   `task rem foo-update//123`

Some commands allow omitting the sub-queue part:

    `task info <queue>/<key>` shows tasks from all <queue> sub-queues
    `task info <queue>//<key>` only shows tasks from the "" sub-queue
"""


class TaskSearchParams(parsers.ParamsParser):
    """ Parse task search params from user input.

    This class can convert a sequence of strings like
    `("queue:foo", "queue:bar", "max:20", "after:2022-01-21")`
    into a dict of search params for the `task_queue` module
    """

    fields = {
        'queue': 'Limit to tasks in a given queue',
        'sub': 'Limit to tasks in a given sub-queue',
        'key': 'Limit to tasks with a given key',
        'min': 'Limit to tasks with <n> or more failed attempts',
        'max': 'Limit to tasks with less than <n> failed attempts',
        'issued-before': 'Limit to tasks issued before <datetime>',
        'issued-after': 'Limit to tasks issued after <datetime>',
        'before': 'Limit to tasks that are ready (at <datetime>)',
        'after': 'Limit to tasks that are waiting (until <datetime>)'
    }
    params = {
        'queue': 'queues',
        'sub': 'subs',
        'key': 'keys',
        'min': 'min_attempts',
        'max': 'max_attempts',
        'issued-before': 'iat_before',
        'issued-after': 'iat_after',
        'before': 'nbf_before',
        'after': 'nbf_after',
    }
    parsers = {
        'min': int,
        'max': int,
        'issued-before': parsers.parse_datetime,
        'issued-after': parsers.parse_datetime,
        'before': parsers.parse_datetime,
        'after': parsers.parse_datetime,
    }
    multivalued = set(('queue', 'sub', 'key'))

    @classmethod
    def get_preset(cls, preset, queue, fail_limit):
        """ Get a named search preset. """
        filters = {'queues': queue}
        if preset == 'total':
            pass
        elif preset == 'failed':
            filters.update({
                'min_attempts': fail_limit,
            })
        elif preset == 'ready':
            filters.update({
                'nbf_before': date_utils.now(),
                'max_attempts': fail_limit,
            })
        elif preset == 'waiting':
            filters.update({
                'nbf_after': date_utils.now(),
                'max_attempts': fail_limit,
            })
        else:
            raise ValueError('Invalid preset: ' + repr(preset))
        return filters


_task_filter_parser = TaskSearchParams()
_task_filter_help_blurb = """
Each task-filter follows a format of <param>:<value>.

Example:  Find all tasks that are ready for processing in foo/ and foo/manual
          with less than 20 attempts.

    `task search queue:foo sub: sub:manual max:20 before:now`

Valid filter params:

{filters}


Valid <datetime> values:

{datetime}
""".format(
    filters='\n'.join(
        ' - {}: {}'.format(f, h)
        for f, h in _task_filter_parser.get_help()),
    datetime=parsers.parse_datetime_help_blurb,
)


class BofhdTaskAuth(BofhdAuth):
    """
    Basic, common auth implementations for task commands.

    .. note::
       To override for a given environment, you'll need to subclass both the
       auth class, and create a basic commands subclass with `authz` set to the
       custom auth class.
    """

    def _can_modify_tasks(self, operator, query_run_any=False):
        """Access to task queues."""
        if self.is_superuser(operator):
            return True
        if query_run_any:
            # not a superuser, do not show command
            return False
        raise PermissionDenied('No access to task queue')

    def can_add_task(self, operator, queue=None, sub=None,
                     query_run_any=False):
        return self._can_modify_tasks(operator, query_run_any=query_run_any)

    def can_remove_task(self, operator, queue=None, sub=None,
                        query_run_any=False):
        return self._can_modify_tasks(operator, query_run_any=query_run_any)

    def can_inspect_tasks(self, operator, queue=None, query_run_any=False):
        return self._can_modify_tasks(operator, query_run_any=query_run_any)


class BofhdTaskCommands(BofhdCommonMethods):
    """
    Commands for inspecting, and adding to/removing from the task queues.

    .. note::
       The task_add command does not allow for anything other than
       queue/sub/key to be added to a queue, and allows for all queues and
       sub-queues to be modified.

       You may want to subclass this class, and implement custom commands for
       adding to/removing from the queue.
    """

    all_commands = {}
    authz = BofhdTaskAuth

    #
    # helpers/generic functionality
    #

    def _add_task(self, task):
        """ Push a task object to its task queue.

        :param Task task: A task object to push
        :returns dict: A dict representation of the added task
        :raises CerebrumError: if the task couldn't be added
        """
        pushed_task = TaskQueue(self.db).push_task(task)
        if pushed_task is None:
            raise CerebrumError('Task already in queue')
        return format_task(pushed_task)

    # reusable format sugegstion for `_add_task()` return value
    _add_task_fs = FormatSuggestion('Task queued: %s', ('task_id',))

    def _remove_task(self, queue, sub, key):
        """ Pop a task by queue + sub + key.

        :param Task task: A task object to push
        :returns dict: A dict representation of the added task
        :raises CerebrumError: if the task couldn't be added
        """
        try:
            task = TaskQueue(self.db).pop_task(queue, sub, key)
        except Errors.NotFoundError:
            mock_id = format_task_id({'queue': queue, 'sub': sub, 'key': key})
            raise CerebrumError('No matching task: ' + mock_id)
        return format_task(task)

    # reusable format sugegstion for `_remove_task()` return value
    _remove_task_fs = FormatSuggestion('Task removed: %s', ('task_id',))

    def _search_tasks(self, filter_d, limit=50):
        """
        Search for tasks.

        :param dict filter_d: task search params (see sql_search)
        :param int limit: max number of tasks to get
        :returns generator:
            Generates matching task dicts.

            If there are more than <limit> matching tasks, the list of
            results will be truncated, and a final sentinel item
            `{'limit': <limit>}` will be included.
        """
        filter_d = dict(filter_d)
        filter_d['limit'] = limit + 1
        for i, row in enumerate(sql_search(self.db, **filter_d)):
            if i < limit:
                yield format_task(row)
            else:
                # if there are more than `limit` results, we add a
                # sentinel value to indicate that not all matches were
                # included.
                yield {'limit': limit}
                break

    # reusable format suggestion for `_search_tasks()` return values - list
    _search_tasks_list_fs = FormatSuggestion(
        [
            # Regular task entries
            ("%-48s  %8d  %-16s",
             ('task_id', 'attempts', format_time('nbf'))),
            # Allow for  special 'limit' sentinel value
            ("...\nLimited to %d results", ('limit',)),
        ],
        hdr=("%-48s  %8s  %-16s"
             % ('Task id', 'Attempts', 'Not before')),
    )

    # reusable format suggestion for `_search_tasks()` return values - detailed
    _search_tasks_info_fs = FormatSuggestion([
            # Normal output
            ('\n'.join((
                    'Task id:       %s',
                    'Attempts:      %d',
                    'Not before:    %s',
                    'Issued at:     %s',
                    'Reason:        %s',
                    'Payload:       %s',
                    '',
                )),
             ('task_id', 'attempts', format_time('nbf'), format_time('iat'),
              'reason', 'payload')),
            # Allow for a special 'limit' sentinel value.  This value should
            # never appear when using this format
            ("...\nLimited to %d results", ('limit',)),
    ])

    def _get_queue_counts(self, filter_d):
        """
        Get number of matching tasks by queue/subqueue.

        :param dict filter_d: see _search_tasks()
        :returns generator:
            Generates task counts by sub-queue.

            E.g.: {'queue_id': 'foo/', 'queue': 'foo', 'sub': '', 'num': 3}
        """
        for r in sql_get_subqueue_counts(self.db, **filter_d):
            yield format_queue_count(r)

    # reusable format sugegstion for `_get_queue_counts()` return values
    _get_queue_counts_fs = FormatSuggestion(
        "%-32s  %d", ('queue_id', 'num'),
        hdr="%-32s  %s" % ('Queue/Sub-queue', 'Count'))

    def _get_queue_stats(self, queue, max_attempts, by_sub=True):
        """
        Fetch (sub)queue stats for a given queue.

        :param str queue: the queue to get stats for
        :param int max_attempts: fail limit for the queue
        :param bool by_sub: get results for each sub-queue
        :returns generator:
            Generates dict objects with stats for sub-queues of a given queue

            E.g.:

                {'queue_id': 'foo/', 'queue': 'foo', 'sub': '',
                 'ready': 0, 'waiting': 24, 'failed': 7, 'total': 31}
        """
        template = {'ready': 0, 'waiting': 0, 'failed': 0, 'total': 0}
        by_key = {}
        for preset in template:
            filters = TaskSearchParams.get_preset(preset, queue, max_attempts)
            for d in self._get_queue_counts(filters):
                if by_sub:
                    key = (d['queue'], d['sub'])
                else:
                    key = (d['queue'],)
                    d['queue_id'] = d['queue']
                num = d.pop('num')
                if key not in by_key:
                    by_key[key] = dict(template)
                    by_key[key].update(d)
                by_key[key][preset] += num

        for key in sorted(by_key):
            yield by_key[key]

    # reusable format suggestion for `_get_queue_stats()` results
    _get_queue_stats_fs = FormatSuggestion(
        "%-32s  %7d  %7d  %7d  %7d",
        ('queue_id', 'ready', 'waiting', 'failed', 'total'),
        hdr=("%-32s  %7s  %7s  %7s  %7s"
             % ('Queue/Sub-queue', 'Ready', 'Waiting', 'Failed',  'Total')),
    )

    @classmethod
    def get_help_strings(cls):
        grp_help = {
            'task': 'Task queue commands',
        }
        cmd_help = {
            'task': {
                'task_add': 'queue a new task',
                'task_remove': 'cancel a queued task',
                'task_search': 'search for tasks across queues',
                'task_info': 'show a given task(s)',
                'task_count': 'count tasks in one or more (sub)queues',

            },
        }
        arg_help = {
            'task-id': [
                'task-id',
                'Enter a task-id',
                _task_id_help_blurb,
            ],
            'task-queue': [
                'task-queue',
                'Enter a queue name',
                'Enter the name of a queue',
            ],
            'task-filter': [
                'task-filter',
                'Enter a task search filter',
                _task_filter_help_blurb,
            ],
        }
        return merge_help_strings(
            get_help_strings(),
            (grp_help, cmd_help, arg_help),
        )

    #
    # task info <task-id>
    #
    all_commands['task_info'] = Command(
        ("task", "info"),
        SimpleString(help_ref='task-id'),
        fs=_search_tasks_info_fs,
        perm_filter='can_inspect_tasks',
    )

    def task_info(self, operator, task_id):
        queue, sub, key = parse_task_id(task_id, None)
        self.ba.can_inspect_tasks(operator.get_entity_id())
        tasks = list(self._search_tasks({'queues': queue, 'subs': sub,
                                         'keys': key}))
        if tasks:
            return tasks
        raise CerebrumError('No queued task matching: ' + repr(task_id))

    #
    # task add <task-id>
    #
    all_commands['task_add'] = Command(
        ("task", "add"),
        SimpleString(help_ref='task-id'),
        fs=_add_task_fs,
        perm_filter='can_add_task',
    )

    def task_add(self, operator, task_id):
        queue, sub, key = parse_task_id(task_id, None)
        if sub is None:
            raise CerebrumError('Invalid task-id: %s'
                                ' (must include sub-queue to add task)'
                                % repr(task_id))
        self.ba.can_add_task(operator.get_entity_id(), queue=queue, sub=sub)
        task = Task(queue=queue, key=key, sub=sub)
        return self._add_task(task)

    #
    # task remove <task-id>
    #
    all_commands['task_remove'] = Command(
        ("task", "remove"),
        SimpleString(help_ref='task-id'),
        fs=_remove_task_fs,
        perm_filter='can_remove_task',
    )

    def task_remove(self, operator, task_id):
        """ Cancel a previously added import task from the hr import queue. """
        queue, sub, key = parse_task_id(task_id, None)
        if sub is None:
            raise CerebrumError('Invalid task-id: %s'
                                ' (must include sub-queue to remove task)'
                                % repr(task_id))
        self.ba.can_remove_task(operator.get_entity_id(), queue=queue, sub=sub)
        return self._remove_task(queue, sub, key)

    #
    # task search [filter...]
    #
    all_commands['task_search'] = Command(
        ("task", "search"),
        SimpleString(help_ref='task-filter', optional=True, repeat=True),
        fs=_search_tasks_list_fs,
        perm_filter='can_inspect_tasks',
    )

    def task_search(self, operator, *search_filters):
        self.ba.can_inspect_tasks(operator.get_entity_id())
        filters = _task_filter_parser.parse_items(search_filters)
        results = list(self._search_tasks(filters))
        if results:
            return results
        raise CerebrumError('No matching tasks (filters: %r)'
                            % (tuple(filters.keys()),))

    #
    # task count [filter...]
    #
    all_commands['task_count'] = Command(
        ("task", "count"),
        SimpleString(help_ref='task-filter', optional=True, repeat=True),
        fs=_get_queue_counts_fs,
        perm_filter='can_inspect_tasks',
    )

    def task_count(self, operator, *search_filters):
        self.ba.can_inspect_tasks(operator.get_entity_id())
        filters = _task_filter_parser.parse_items(search_filters)
        results = list(self._get_queue_counts(filters))
        if results:
            return results
        raise CerebrumError('No matching tasks (filters: %r)'
                            % (tuple(filters.keys()),))

    #
    # Example stats for a specific queue (with a fail_limit)
    #
    # Typically implemented in subclasses, with constraints from a TaskHandler
    #
    # all_commands['example_queue_stats'] = Command(
    #     ("example", "queue_stats"),
    #     fs=_get_queue_stats_fs,
    #     perm_filter='can_inspect_tasks',
    # )
    #
    # def example_queue_stats(self, operator):
    #     self.ba.can_inspect_tasks(operator.get_entity_id())
    #     queue = 'my_queue'
    #     limit = 20
    #     results = self._get_queue_stats(queue, limit)
    #     if results:
    #         return results
    #     raise CerebrumError('No tasks in the queue')

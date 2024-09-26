# -*- coding: utf-8 -*-
#
# Copyright 2021-2024 University of Oslo, Norway
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
Models for tasks in the task queue.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import six

from Cerebrum.utils.date import now
from Cerebrum.utils.reprutils import ReprFieldMixin


class _CompareAttrs(object):
    """ Attribute-based equality checks. """

    compare_attrs = ()

    def __eq__(self, other):
        attrs = self.compare_attrs
        if not attrs:
            # it is an error to use _CompareAttrs without setting the
            # compare_attrs class attribute
            raise NotImplementedError("no compare_attrs in "
                                      + repr(type(self)))
        if all(hasattr(other, attr) for attr in attrs):
            return all(getattr(self, attr) == getattr(other, attr)
                       for attr in attrs)
        return NotImplemented

    def __ne__(self, other):
        eq = self.__eq__(other)
        if eq is NotImplemented:
            return NotImplemented
        return not eq


class Task(_CompareAttrs, ReprFieldMixin):
    """ A single item on the queue.  """
    repr_id = False
    repr_module = False
    repr_fields = ("queue", "sub", "key")
    compare_attrs = ("queue", "sub", "key", "nbf", "iat",
                     "attempts", "reason", "payload")

    def __init__(self, queue, key, sub=None, nbf=None, iat=None, attempts=None,
                 reason=None, payload=None):
        self.queue = queue
        self.sub = sub or ""
        self.key = key
        self.nbf = nbf
        self.iat = iat
        self.attempts = attempts
        self.reason = reason
        self.payload = payload

    def to_dict(self):
        """ Format object as a dict. """
        d = {
            'queue': self.queue,
            'sub': self.sub,
            'key': self.key,
        }
        d.update({
            k: getattr(self, k)
            for k in ('attempts', 'nbf', 'iat', 'reason')
            if getattr(self, k) is not None
        })
        if self.payload:
            d['payload'] = self.payload.to_dict()
        return d

    @classmethod
    def from_dict(cls, d):
        """ Build object from a dict-like object. """
        if d.get('payload'):
            payload = Payload.from_dict(d['payload'])
        else:
            payload = None

        record = cls(
            queue=d['queue'],
            sub=d['sub'],
            key=d['key'],
            attempts=d.get('attempts'),
            nbf=d.get('nbf'),
            iat=d.get('iat'),
            payload=payload,
            reason=d.get('reason'),
        )
        return record


class Payload(_CompareAttrs, ReprFieldMixin):
    """
    Payload for a Task.

    Items in the task queue may contain a payload json blob.

    This json blob typically contains serialized parameters for the
    queued task.  In order to support *altering* the data format of the
    payload, for a given queue/task type, each payload will be identified by a
    format and a version.
    """
    default_version = 1
    repr_fields = ("format", "version")
    compare_attrs = ("format", "version", "data")

    def __init__(self, fmt, data, version=default_version):
        self.format = fmt
        self.data = data
        self.version = version

    def to_dict(self):
        d = {
            'format': self.format,
            'version': self.version,
            'data': self.data,
        }
        return d

    @classmethod
    def from_dict(cls, d):
        fmt = six.text_type(d['format'])
        version = int(d['version'])
        data = dict(d['data'])

        obj = cls(fmt, data, version=version)
        return obj


def db_row_to_task(row, allow_empty=False):
    if allow_empty and not row:
        return None
    return Task.from_dict(dict(row))


def copy_task(task_like):
    """ Create a copy of a task or payload object.

    :type task_like: Task, Payload
    :returns: a copy of the object
    """
    return type(task_like).from_dict(task_like.to_dict())


def merge_tasks(new_task, old_task=None, _now=None):
    """
    Update *new_task* with info from *old_task*.

    Whenever an *old_task* already exists in the queue and we get *another*
    *new_task* where ``old_task.nbf < new_task.nbf``, we *usually* want to keep
    the task with the older *nbf*.

    This helper function merges these two tasks and returns an object that can
    be pushed to the queue.

    Example:

    ::

        old_task = TaskQueue(db).get_task(...)
        new_task = merge_tasks(Task(...), old_task)
        TaskQueue(db).push_task(new_task)

    """
    _now = _now or now()
    if not old_task:
        # no old task to update
        return new_task

    old_key = tuple(six.text_type(getattr(old_task, field))
                    for field in ('queue', 'sub', 'key'))
    new_key = tuple(six.text_type(getattr(new_task, field))
                    for field in ('queue', 'sub', 'key'))

    if old_key != new_key:
        raise ValueError('cannot merge different tasks: %s, %s'
                         % (repr(old_task), repr(new_task)))

    if old_task.nbf < (new_task.nbf or _now):
        # old (existing task in queue) is due for processing before our new
        # task, i.e. we should update/reset attempts in the old task
        new_task = copy_task(new_task)
        new_task.nbf = old_task.nbf
        new_task.reason = old_task.reason
    else:
        # old (existing task in queue) is due for processing after our new
        # task, i.e. we should replace the old task entirely.
        pass
    return new_task


def parse_task_id(task_id, require_sub=True, default_sub=None):
    """
    Parse a *task-id*.

    :param str task_id:
        A string with format "<queue>/<sub>/<key>"

    :param bool require_sub:
        Only accept the default format (<queue>/<sub>/<key>).

        If set to ``False``, the special format, "<queue>/<key>" is accepted,
        and will return *default_sub* as the sub-queue value.

    :param str default_sub:
        Default <sub> for the special "<queue>/<key>" format.

    :rtype tuple:
        A tuple with the <queue>, <sub>, and <key> values.
    """
    if require_sub:
        valid_formats = "q/s/k, q//k"
    else:
        valid_formats = "q/k, q/s/k, q//k"

    parts = task_id.split('/')
    if len(parts) == 2 and not require_sub:
        queue, key = parts
        sub = default_sub
    elif len(parts) == 3:
        queue, sub, key = parts
    else:
        raise ValueError(
            "invalid task-id: %s (valid formats: %s)"
            % (repr(task_id), valid_formats))

    queue = queue.strip()
    if not queue:
        raise ValueError("invalid task-id: %s (missing queue)"
                         % repr(task_id))
    key = key.strip()
    if not key:
        raise ValueError("invalid task-id: %s (missing key)"
                         % repr(task_id))
    return (queue, sub, key)


def format_task_id(task_like):
    """ Format a valid task-id from task info. """
    if isinstance(task_like, Task):
        parts = task_like.queue, task_like.sub or "", task_like.key
    else:
        parts = task_like['queue'], task_like['sub'] or "", task_like['key']
    return '/'.join(parts)


def format_queue_id(task_like):
    """ Format a queue-id (task-id without key). """
    if isinstance(task_like, Task):
        parts = task_like.queue, task_like.sub or ""
    else:
        parts = task_like['queue'], task_like['sub'] or ""
    return '/'.join(parts)

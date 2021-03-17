# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
import six

from Cerebrum.utils.reprutils import ReprFieldMixin


class Task(ReprFieldMixin):
    """ A single item on the queue.  """

    repr_fields = ('queue', 'key')

    def __init__(self, queue, key, nbf=None, iat=None, attempts=0,
                 reason=None, payload=None):
        self.queue = queue
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
            'key': self.key,
        }
        d.update({
            k: getattr(self, k)
            for k in ('attempts', 'nbf', 'iat', 'reason')
            if getattr(self, k)
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
            key=d['key'],
            attempts=int(d.get('attempts') or 0),
            nbf=d.get('nbf'),
            iat=d.get('iat'),
            payload=payload,
            reason=d.get('reason'),
        )
        return record


class Payload(ReprFieldMixin):
    """
    Payload for a Task.

    Items in the task queue may contain a payload json blob.

    This json blob typically contains serialized parameters for the
    queued task.  In order to support *altering* the data format of the
    payload, for a given queue/task type, each payload will be identified by a
    format and a version.
    """
    default_version = 1
    repr_fields = ('format', 'version')

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

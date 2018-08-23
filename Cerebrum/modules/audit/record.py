#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2018 University of Oslo, Norway
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
""" Object representation of records in the database. """

import six


class AuditRecord(object):

    def __init__(
            self,
            change_type,
            operator,
            entity,
            target=None,
            metadata=None,
            params=None,
    ):
        self.change_type = change_type
        self.operator_id = operator
        self.entity_id = entity
        self.target_id = target
        self.metadata = metadata
        self.params = params

    def __repr__(self):
        # TODO: make the _ChangeTypeCode repr better?
        return '<%s[] change=%s for=%r>' % (
            self.__class__.__name__,
            six.text_type(self.change_type),
            self.entity_id)

    def to_dict(self):
        d = {
            'change_type': self.change_type,
            'operator': self.operator_id,
            'entity': self.entity_id,
            'target': self.target_id,
            'metadata': self.metadata,
            'params': self.params,
        }
        return d

    @classmethod
    def from_dict(cls, d):
        """ Build an AuditRecord object from a dict-like object.

        This can be used e.g. to make AuditRecord objects from db_row objects.
        This is also the only way to properly populate the timestamp and
        record_id fields -- these fields should *always* come from a database,
        and not be constructed in any other way.
        """
        change_type = d['change_type']
        # TODO: assert _ChangeTypeCode?

        entity = int(d['entity'])
        operator = int(d['operator'])
        target = d.get('target', None)
        if target is not None:
            target = int(target)
        metadata = d.get('metadata', None)
        params = d.get('params', None)
        record = cls(change_type, operator, entity,
                     target=target, metadata=metadata, params=params)
        return record


class DbAuditRecord(AuditRecord):

    def __init__(self, record_id, timestamp, *args, **kwargs):
        self.__record_id = record_id
        self.__timestamp = timestamp
        super(DbAuditRecord, self).__init__(*args, **kwargs)

    def __repr__(self):
        return '<%s[%r] change=%s for=%r at=%r>' % (
            self.__class__.__name__,
            self.record_id,
            six.text_type(self.change_type),
            self.entity_id,
            self.timestamp.strftime('%Y-%m-%d %H:%M:%S %z'))

    @property
    def record_id(self):
        return self.__record_id

    @property
    def timestamp(self):
        return self.__timestamp

    def to_dict(self):
        d = super(DbAuditRecord, self).to_dict()
        d.update({
            'timestamp': self.timestamp,
            'record_id': self.record_id,
        })
        return d

    @classmethod
    def from_dict(cls, d):
        record_id = int(d['record_id'])
        timestamp = d['timestamp']
        change_type = d['change_type']
        # TODO: assert _ChangeTypeCode?

        entity = int(d['entity'])
        operator = int(d['operator'])
        target = d.get('target', None)
        if target is not None:
            target = int(target)
        metadata = d.get('metadata', None)
        params = d.get('params', None)
        record = cls(record_id, timestamp, change_type, operator, entity,
                     target=target, metadata=metadata, params=params)
        return record

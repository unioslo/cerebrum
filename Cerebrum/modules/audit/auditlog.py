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
""" CLDatabase integration for audit log records. """
import collections
import logging
import re

import six

import cereconf
import Cerebrum.Errors
from Cerebrum.ChangeLog import ChangeLog
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Entity import Entity, EntityName
from Cerebrum.Utils import Factory

from .auditdb import AuditLogAccessor
from .record import AuditRecord


logger = logging.getLogger(__name__)
ENTITY_TYPE_NAMESPACE = getattr(cereconf, 'ENTITY_TYPE_NAMESPACE', dict())


class AuditLog(ChangeLog):
    # TODO: The ChangeLog design is kind of broken -- there is no actual
    # `execute` or `query` finction until we get a database object mixed in
    # somehow.  I.e.  This object actually depends on Cerebrum.CLDatabase
    #
    # How should that be solved?  Should we inherit from CLDatabase and use
    # `cerebrum.CLASS_DATABASE `?  If so, this should also apply to all current
    # ChangeLog implementations, as they all use the database api...

    def cl_init(self, change_by=None, change_program=None, **kw):
        super(AuditLog, self).cl_init(**kw)
        # TODO: Enforce that change_by is set?
        self.change_by = change_by
        self.change_program = change_program
        self.records = []

    @property
    def initial_account_id(self):
        if not hasattr(self, '_default_op'):
            account = Factory.get('Account')(self)
            account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
            self._default_op = account
        return self._default_op.entity_id

    def log_change(self,
                   subject_entity,
                   change_type_id,
                   destination_entity,
                   change_params=None,
                   change_by=None,
                   change_program=None,
                   skip_audit=False,
                   **kw):
        super(AuditLog, self).log_change(
            subject_entity,
            change_type_id,
            destination_entity,
            change_params=change_params,
            change_by=change_by,
            change_program=change_program,
            **kw)

        if skip_audit:
            return

        change_program = change_program or self.change_program
        if not change_by and change_program:
            change_by = self.initial_account_id
        elif not change_by:
            raise ValueError("No operator given, and no change_program set")

        builder = AuditRecordBuilder(self)
        record = builder(
            subject_entity,
            change_type_id,
            destination_entity,
            change_params,
            change_by,
            change_program)
        self.records.append(record)

    def write_log(self):
        super(AuditLog, self).write_log()
        accessor = AuditLogAccessor(self)
        for record in self.records:
            accessor.append(record)

    def clear_log(self):
        super(AuditLog, self).clear_log()
        self.records = []


class _ChangeTypeCallbacks(object):
    """ Register with Callback functions for _ChangeTypeCode attributes. """

    def __init__(self):
        self.callbacks = collections.OrderedDict()

    def register(self, category, change):
        """ Register an event generator for a given change type. """
        key = re.compile('^{0}:{1}$'.format(category, change))

        def wrapper(fn):
            self.callbacks[key] = fn
            return fn
        return wrapper

    def get_callback(self, category, change):
        term = '{0}:{1}'.format(category, change)
        for key in self.callbacks:
            if key.match(term):
                return self.callbacks[key]


class AuditRecordBuilder(DatabaseAccessor):
    """ Helper function to build AuditRecord objects. """

    @property
    def const(self):
        if not hasattr(self, '_const'):
            self._const = Factory.get('Constants')(self._db)
        return self._const

    @property
    def clconst(self):
        if not hasattr(self, '_clconst'):
            self._clconst = Factory.get('CLConstants')(self._db)
        return self._clconst

    def get_change_type(self, value):
        if isinstance(value, self.clconst.ChangeType):
            const = value
        else:
            const = self.clconst.ChangeType(value)
        int(const)
        return const

    def _get_type(self, e_id):
        entity = Entity(self._db)
        try:
            entity.find(e_id)
            return six.text_type(self.const.EntityType(entity.entity_type))
        except Cerebrum.Errors.NotFoundError:
            return None

    def _get_name(self, e_id, e_type):
        namespace = ENTITY_TYPE_NAMESPACE.get(six.text_type(e_type))
        if namespace is None:
            return None
        else:
            namespace = self.const.ValueDomain(namespace)
        entity = EntityName(self._db)
        try:
            entity.find(e_id)
            return entity.get_name(namespace)
        except Cerebrum.Errors.NotFoundError:
            return None

    def build_meta(self, change_type, operator_id, entity_id,
                   target_id, change_program):
        """ Build default metadata from change_log arguments.

        TODO: This is a hack -- the ChangeLog/CLDatabase API should be modified
        so that:

        1. It retains an Entity object for the current operator
        2. log_change is given Entity objects rather than entity_id and
        target_id

        That way we would be able to fetch cached info on the entities
        involved, rather than looking it up for every change.
        """
        co = self.const

        def get_type(e_id):
            entity = Entity(self._db)
            try:
                entity.find(e_id)
                return six.text_type(co.EntityType(entity.entity_type))
            except Cerebrum.Errors.NotFoundError:
                return None

        def get_name(e_id, e_type):
            namespace = ENTITY_TYPE_NAMESPACE.get(six.text_type(e_type))
            if namespace is None:
                return None
            else:
                namespace = co.ValueDomain(namespace)
            entity = EntityName(self._db)
            try:
                entity.find(e_id)
                return entity.get_name(namespace)
            except Cerebrum.Errors.NotFoundError:
                return None

        change = six.text_type(change_type)
        operator_type = self._get_type(operator_id)
        operator_name = self._get_name(operator_id, operator_type)
        entity_type = self._get_type(entity_id)
        entity_name = self._get_name(entity_id, entity_type)
        target_type = self._get_type(target_id)
        target_name = self._get_name(target_id, target_type)
        if change_program is not None:
            change_program = six.text_type(change_program)
        return {
            'change': change,
            'operator_type': operator_type,
            'operator_name': operator_name,
            'entity_type': entity_type,
            'entity_name': entity_name,
            'target_type': target_type,
            'target_name': target_name,
            'change_program': change_program,
        }

    translate_params = _ChangeTypeCallbacks()

    def build_params(self, change_type, subject_entity, destination_entity,
                     change_params):
        """ Build params for the audit log entry.
        """
        category, change = change_type.category, change_type.type
        fn = self.translate_params.get_callback(category, change)
        if fn:
            params = fn(self, subject_entity, destination_entity,
                        change_params)
            if params is not None:
                change_params = params
        return change_params

    def __call__(self,
                 subject_entity,
                 change_type_id,
                 destination_entity,
                 change_params,
                 change_by,
                 change_program):

        change_type = self.get_change_type(change_type_id)
        metadata = self.build_meta(change_type,
                                   change_by,
                                   subject_entity,
                                   destination_entity,
                                   change_program)
        params = self.build_params(change_type,
                                   subject_entity,
                                   destination_entity,
                                   change_params)
        return AuditRecord(
            change_type,
            change_by,
            subject_entity,
            target=destination_entity,
            metadata=metadata,
            params=params)

    # Examples
    # @translate_params.register('spread', 'add')
    # def spread_add(self, subject_entity, destination_entity, change_params):
    #     return change_params

    # @translate_params.register('spread', 'remove')
    # def spread_remove(self, subject_entity, destination_entity, change_params):
    #     return change_params

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
from Cerebrum.modules.Email import EmailAddress, EmailDomain

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
                   **kw):
        super(AuditLog, self).log_change(
            subject_entity,
            change_type_id,
            destination_entity,
            change_params=change_params,
            change_by=change_by,
            change_program=change_program,
            **kw)

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

    @property
    def host(self):
        if not hasattr(self, '_host'):
            self._host = Factory.get('Host')(self._db)
        return self._host

    @property
    def ea(self):
        if not hasattr(self, '_ea'):
            self._ea = EmailAddress(self._db)
        return self._ea

    @property
    def ed(self):
        if not hasattr(self, '_ed'):
            self._ed = EmailDomain(self._db)
        return self._ed

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

    def build_meta(self, change_type, operator_id, entity_id, target_id):
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
        return {
            'change': change,
            'operator_type': operator_type,
            'operator_name': operator_name,
            'entity_type': entity_type,
            'entity_name': entity_name,
            'target_type': target_type,
            'target_name': target_name,
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
                                   destination_entity)
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

    # Register translation parameters for different types of changes
    def add_str_of_int_const(self, keypairs, change_params):
        """Add the str val of a constant int to change params if possible

        Typically useful when we have been saving the int value of a constant
        and we now want to save the string as well.
        If the constant no longer exists, and we can not find what the string
        value of the constant should be, we keep.

        >>> db = Factory.get('Database')()
        >>> cp = {'foo': 1}
        >>> AuditRecordBuilder(db).add_str_of_int_const([('foo','bar')], cp)
        {'foo': 1, 'bar': u'aggressive_spam'}

        :param list keypairs: list of tuples with keypairs
        :param dict change_params: the change_param dict we want to manipulate
        :rtype: dict
        :return: the new manipulated change_params
        """
        for pair in keypairs:
            if pair[0] in change_params:
                change = self.const.human2constant(change_params[pair[0]])
                if change:
                    change_params[pair[1]] = six.text_type(change)
        return change_params

    @translate_params.register('e_account', 'create')
    @translate_params.register('e_account', 'mod')
    def account_create_mod(self, subject_entity, destination_entity,
                           change_params):
        change_params = self.add_str_of_int_const([
            ('np_type', 'np_type_str'), ('owner_type', 'owner_type_str')],
            change_params)
        return change_params

    @translate_params.register('e_account', 'home_update')
    @translate_params.register('e_account', 'home_added')
    @translate_params.register('e_account', 'home_removed')
    @translate_params.register('spread', 'add')
    @translate_params.register('spread', 'delete')
    @translate_params.register('exchange', 'acc_mbox_create')
    @translate_params.register('exchange', 'acc_mbox_delete')
    def spread_int_to_str(self, subject_entity, destination_entity,
                          change_params):
        change_params = self.add_str_of_int_const(
            [('spread', 'spread_str')],
            change_params)
        return change_params

    @translate_params.register('homedir', 'add')
    @translate_params.register('homedir', 'update')
    def status_str(self, subject_entity, destination_entity,
                   change_params):
        change_params = self.add_str_of_int_const(
            [('status', 'status_str')],
            change_params)
        return change_params

    @translate_params.register('ac_type', 'add')
    @translate_params.register('ac_type', 'del')
    def aff_to_affstr(self, subject_entity, destination_entity,
                      change_params):
        change_params = self.add_str_of_int_const(
            [('affiliation', 'aff_str')],
            change_params)
        return change_params

    @translate_params.register('disk', 'add')
    @translate_params.register('disk', 'mod')
    @translate_params.register('disk', 'del')
    def disk_add_mod_del(self, subject_entity, destination_entity,
                         change_params):
        if 'host_id' in change_params:
            self.host.clear()
            try:
                self.host.find(int(change_params['host_id']))
            except Cerebrum.Errors.NotFoundError:
                pass
            else:
                change_params['host_name'] = self.host.name
        return change_params

    @translate_params.register('ou', 'unset_parent')
    @translate_params.register('ou', 'set_parent')
    def ou_unset_parent(self, subject_entity, destination_entity,
                        change_params):
        change_params = self.add_str_of_int_const(
            [('perspective', 'perspective_str')], change_params)
        return change_params

    @translate_params.register('person', 'name_del')
    @translate_params.register('person', 'name_add')
    @translate_params.register('person', 'name_mod')
    def person_name_add_mod_del(self, subject_entity, destination_entity,
                                change_params):
        change_params = self.add_str_of_int_const(
            [('src', 'src_str'), ('name_variant', 'name_variant_str')],
            change_params)
        return change_params

    @translate_params.register('entity_name', 'add')
    @translate_params.register('entity_name', 'del')
    def entity_name_add_del(self, subject_entity, destination_entity,
                            change_params):
        change_params = self.add_str_of_int_const(
            [('domain', 'domain_str'), ('name_variant', 'name_variant_str'),
             ('name_language', 'name_language_str')],
            change_params)
        return change_params

    @translate_params.register('entity_name', 'mod')
    def entity_name_mod(self, subject_entity, destination_entity,
                        change_params):
        change_params = self.add_str_of_int_const(
            [('domain', 'domain_str')],
            change_params)
        return change_params

    @translate_params.register('entity_cinfo', 'add')
    @translate_params.register('entity_cinfo', 'del')
    def entity_cinfo_add_del(self, subject_entity, destination_entity,
                             change_params):
        change_params = self.add_str_of_int_const(
            [('type', 'type_str'), ('src', 'src_str')],
            change_params)
        return change_params

    @translate_params.register('entity', 'ext_id_del')
    @translate_params.register('entity', 'ext_id_mod')
    @translate_params.register('entity', 'ext_id_add')
    def entity_ext_id_del(self, subject_entity, destination_entity,
                          change_params):
        change_params = self.add_str_of_int_const(
            [('id_type', 'id_type_str'), ('src', 'src_str')],
            change_params)
        return change_params

    # Quarantine changes
    @translate_params.register('quarantine', 'add')
    @translate_params.register('quarantine', 'mod')
    @translate_params.register('quarantine', 'del')
    def quarantine_add_mod(self, subject_entity, destination_entity,
                           change_params):
        change_params = self.add_str_of_int_const(
            [('q_type', 'q_type_str')],
            change_params)
        return change_params

    @translate_params.register('posix', 'promote')
    def posix_promote(self, subject_entity, destination_entity, change_params):
        change_params = self.add_str_of_int_const(
            [('shell', 'shell_str')],
            change_params)
        return change_params

    @translate_params.register('email_domain', 'addcat_domain')
    @translate_params.register('email_domain', 'remcat_domain')
    def email_dom_cat_add_rem(self, subject_entity, destination_entity,
                              change_params):
        change_params = self.add_str_of_int_const(
            [('category', 'category_str')],
            change_params)
        return change_params

    @translate_params.register('email_target', 'add_target')
    @translate_params.register('email_target', 'rem_target')
    def email_target_add_rem(self, subject_entity, destination_entity,
                             change_params):
        change_params = self.add_str_of_int_const(
            [('target_type', 'target_type_str')],
            change_params)
        return change_params

    @translate_params.register('email_target', 'mod_target')
    def email_target_mod(self, subject_entity, destination_entity,
                         change_params):
        change_params = self.add_str_of_int_const(
            [('target_type', 'target_type_str')],
            change_params)
        if 'server_id' in change_params:
            self.host.clear()
            try:
                self.host.find(int(change_params['server_id']))
            except Cerebrum.Errors.NotFoundError:
                pass
            else:
                change_params['server_name'] = self.host.name
        return change_params

    @translate_params.register('email_address', 'add_address')
    @translate_params.register('email_address', 'rem_address')
    def email_address_add(self, subject_entity, destination_entity,
                          change_params):
        if 'dom_id' in change_params:
            self.ed.clear()
            try:
                self.ed.find(int(change_params['dom_id']))
            except Cerebrum.Errors.NotFoundError:
                pass
            else:
                change_params['dom_name'] = self.ed.get_domain_name()
        return change_params

    @translate_params.register('email_entity_dom', 'add_entdom')
    @translate_params.register('email_entity_dom', 'rem_entdom')
    @translate_params.register('email_entity_dom', 'mod_entdom')
    def email_entity_dom_add_rem_mod(self, subject_entity, destination_entity,
                                     change_params):
        change_params = self.add_str_of_int_const(
            [('aff', 'aff_str')],
            change_params)
        return change_params

    @translate_params.register('email_tfilter', 'add_filter')
    @translate_params.register('email_tfilter', 'rem_filter')
    def email_tfilter_add(self, subject_entity, destination_entity,
                          change_params):
        change_params = self.add_str_of_int_const(
            [('filter', 'filter_str')],
            change_params)
        return change_params

    @translate_params.register('email_sfilter', 'add_sfilter')
    @translate_params.register('email_sfilter', 'mod_sfilter')
    def email_sfilter_add(self, subject_entity, destination_entity,
                          change_params):
        change_params = self.add_str_of_int_const(
            [('level', 'level_str'), ('action', 'action_str')],
            change_params)
        return change_params

    @translate_params.register('email_primary_address', 'add_primary')
    @translate_params.register('email_primary_address', 'rem_primary')
    @translate_params.register('email_primary_address', 'mod_primary')
    @translate_params.register('exchange', 'acc_primaddr')
    def email_primary_address_add(self, subject_entity, destination_entity,
                                  change_params):
        if 'addr_id' in change_params:
            self.ea.clear()
            try:
                self.ea.find(change_params['addr_id'])
            except Cerebrum.Errors.NotFoundError:
                pass
            else:
                change_params['addr'] = self.ea.get_address()
        return change_params

    @translate_params.register('email_server', 'add_server')
    @translate_params.register('email_server', 'rem_server')
    @translate_params.register('email_server', 'mod_server')
    def email_server_add(self, subject_entity, destination_entity,
                         change_params):
        change_params = self.add_str_of_int_const(
            [('server_type', 'server_type_str')],
            change_params)
        return change_params

    @translate_params.register('trait', 'add')
    @translate_params.register('trait', 'mod')
    @translate_params.register('trait', 'del')
    def trait_mod(self, subject_entity, destination_entity,
                  change_params):
        change_params = self.add_str_of_int_const(
            [('entity_type', 'entity_type_str'), ('code', 'code_str')],
            change_params)
        return change_params

    @translate_params.register('ephorte', 'role_add')
    @translate_params.register('ephorte', 'role_rem')
    @translate_params.register('ephorte', 'role_upd')
    def ephorte_role_add(self, subject_entity, destination_entity,
                         change_params):
        change_params = self.add_str_of_int_const(
            [('arkivdel', 'arkivdel_str'), ('rolle_type', 'rolle_type_str')],
            change_params)
        return change_params

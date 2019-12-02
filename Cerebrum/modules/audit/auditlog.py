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
        change_by = change_by or self.change_by

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
        self.records = []

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

    # Register translation parameters for different types of changes
    @translate_params.register('account', 'create')
    @translate_params.register('account', 'modify')
    def account_create_mod(self, subject_entity, destination_entity,
                           change_params):
        if 'np_type' in change_params and change_params['np_type'] is not None:
            try:
                change_params.update(
                    {'np_type_str': six.text_type(
                        self.const.Account(change_params['np_type']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        if ('owner_type' in change_params and
                change_params['owner_type'] is not None):
            try:
                change_params.update(
                    {'owner_type_str': six.text_type(
                        self.const.EntityType(change_params['owner_type']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        return change_params

    @translate_params.register('account_home', 'add')
    @translate_params.register('account_home', 'remove')
    @translate_params.register('account_home', 'modify')
    @translate_params.register('spread', 'add')
    @translate_params.register('spread', 'delete')
    @translate_params.register('exchange_acc_mbox', 'create')
    @translate_params.register('exchange_acc_mbox', 'delete')
    def spread_int_to_str(self, subject_entity, destination_entity,
                          change_params):
        if 'spread' in change_params and change_params['spread'] is not None:
            try:
                change_params.update(
                    {'spread_str': six.text_type(
                        self.const.Spread(change_params['spread']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        return change_params

    @translate_params.register('homedir', 'add')
    @translate_params.register('homedir', 'modify')
    def status_str(self, subject_entity, destination_entity,
                   change_params):
        if 'status' in change_params and change_params['status'] is not None:
            try:
                change_params.update(
                    {'status_str': six.text_type(
                        self.const.AccountHomeStatus(
                            change_params['status']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        return change_params

    @translate_params.register('account_type', 'add')
    @translate_params.register('account_type', 'remove')
    def aff_to_affstr(self, subject_entity, destination_entity,
                      change_params):
        if ('affiliation' in change_params and
                change_params['affiliation'] is not None):
            try:
                change_params.update(
                    {'aff_str': six.text_type(
                        self.const.PersonAffiliation(
                            change_params['affiliation']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        return change_params

    @translate_params.register('disk', 'add')
    @translate_params.register('disk', 'remove')
    @translate_params.register('disk', 'modify')
    def disk_add_mod_del(self, subject_entity, destination_entity,
                         change_params):
        if 'host_id' in change_params and change_params['host_id'] is not None:
            self.host.clear()
            try:
                self.host.find(int(change_params['host_id']))
            except Cerebrum.Errors.NotFoundError:
                pass
            else:
                change_params['host_name'] = self.host.name
        return change_params

    @translate_params.register('ou_parent', 'clear')
    @translate_params.register('ou_parent', 'set')
    def ou_unset_parent(self, subject_entity, destination_entity,
                        change_params):
        if ('perspective' in change_params and
                change_params['perspective'] is not None):
            try:
                change_params.update(
                    {'perspective_str': six.text_type(
                        self.const.OUPerspective(
                            change_params['perspective']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        return change_params

    @translate_params.register('person_name', 'add')
    @translate_params.register('person_name', 'remove')
    @translate_params.register('person_name', 'modify')
    def person_name_add_mod_del(self, subject_entity, destination_entity,
                                change_params):
        if 'src' in change_params and change_params['src'] is not None:
            try:
                change_params.update(
                    {'src_str': six.text_type(
                        self.const.AuthoritativeSystem(
                            change_params['src']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        if ('name_variant' in change_params and
                change_params['name_variant'] is not None):
            try:
                change_params.update(
                    {'name_variant_str': six.text_type(self.const.PersonName(
                        change_params['name_variant']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        return change_params

    @translate_params.register('entity_name', 'add')
    @translate_params.register('entity_name', 'remove')
    def entity_name_add_del(self, subject_entity, destination_entity,
                            change_params):
        if 'domain' in change_params and change_params['domain'] is not None:
            try:
                change_params.update(
                    {'domain_str': six.text_type(self.const.ValueDomain(
                        change_params['domain']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        if ('name_variant' in change_params and
                change_params['name_variant'] is not None):
            try:
                change_params.update(
                    {'name_variant_str': six.text_type(
                        self.const.EntityNameCode(
                            change_params['name_variant']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        if ('name_language' in change_params and
                change_params['name_language'] is not None):
            try:
                change_params.update(
                    {'name_language_str': six.text_type(
                        self.const.LanguageCode(
                            change_params['name_language']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        return change_params

    @translate_params.register('entity_name', 'modify')
    def entity_name_mod(self, subject_entity, destination_entity,
                        change_params):
        if 'domain' in change_params and change_params['domain'] is not None:
            try:
                change_params.update(
                    {'domain_str': six.text_type(self.const.ValueDomain(
                        change_params['domain']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        return change_params

    @translate_params.register('entity_cinfo', 'add')
    @translate_params.register('entity_cinfo', 'remove')
    def entity_cinfo_add_del(self, subject_entity, destination_entity,
                             change_params):
        if 'type' in change_params and change_params['type'] is not None:
            try:
                change_params.update(
                    {'type_str': six.text_type(self.const.ContactInfo(
                        change_params['type']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        if 'src' in change_params and change_params['src'] is not None:
            try:
                change_params.update(
                    {'src_str': six.text_type(self.const.AuthoritativeSystem(
                        change_params['src']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        return change_params

    @translate_params.register('entity_external_id', 'add')
    @translate_params.register('entity_external_id', 'modify')
    @translate_params.register('entity_external_id', 'remove')
    def entity_ext_id_del(self, subject_entity, destination_entity,
                          change_params):
        if 'id_type' in change_params and change_params['id_type'] is not None:
            try:
                change_params.update(
                    {'id_type_str': six.text_type(self.const.EntityExternalId(
                        change_params['id_type']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        if 'src' in change_params and change_params['src'] is not None:
            try:
                change_params.update(
                    {'src_str': six.text_type(self.const.AuthoritativeSystem(
                        change_params['src']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        return change_params

    # Quarantine changes
    @translate_params.register('quarantine', 'add')
    @translate_params.register('quarantine', 'modify')
    @translate_params.register('quarantine', 'remove')
    def quarantine_add_mod(self, subject_entity, destination_entity,
                           change_params):
        if 'q_type' in change_params and change_params['q_type'] is not None:
            try:
                change_params.update(
                    {'q_type_str': six.text_type(self.const.Quarantine(
                        change_params['q_type']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        return change_params

    @translate_params.register('posix_user', 'create')
    def posix_promote(self, subject_entity, destination_entity, change_params):
        if 'shell' in change_params and change_params['shell'] is not None:
            try:
                change_params.update(
                    {'shell_str': six.text_type(self.const.PosixShell(
                        change_params['shell']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        return change_params

    @translate_params.register('email_domain_category', 'add')
    @translate_params.register('email_domain_category', 'remove')
    def email_dom_cat_add_rem(self, subject_entity, destination_entity,
                              change_params):
        if ('category' in change_params and
                change_params['category'] is not None):
            try:
                change_params.update(
                    {'category_str': six.text_type(
                        self.const.EmailDomainCategory(
                            change_params['category']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        return change_params

    @translate_params.register('email_target', 'add')
    @translate_params.register('email_target', 'remove')
    def email_target_add_rem(self, subject_entity, destination_entity,
                             change_params):
        if ('target_type' in change_params and
                change_params['target_type'] is not None):
            try:
                change_params.update(
                    {'target_type_str': six.text_type(self.const.EmailTarget(
                        change_params['target_type']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        return change_params

    @translate_params.register('email_target', 'modify')
    def email_target_mod(self, subject_entity, destination_entity,
                         change_params):
        if ('target_type' in change_params and
                change_params['target_type'] is not None):
            try:
                change_params.update(
                    {'target_type_str': six.text_type(self.const.EmailTarget(
                        change_params['target_type']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        if ('server_id' in change_params and
                change_params['server_id'] is not None):
            self.host.clear()
            try:
                self.host.find(int(change_params['server_id']))
            except Cerebrum.Errors.NotFoundError:
                pass
            else:
                change_params['server_name'] = self.host.name
        return change_params

    @translate_params.register('email_address', 'add')
    @translate_params.register('email_address', 'remove')
    def email_address_add(self, subject_entity, destination_entity,
                          change_params):
        if 'dom_id' in change_params and change_params['dom_id'] is not None:
            self.ed.clear()
            try:
                self.ed.find(int(change_params['dom_id']))
            except Cerebrum.Errors.NotFoundError:
                pass
            else:
                change_params['dom_name'] = self.ed.get_domain_name()
        return change_params

    @translate_params.register('email_entity_domain', 'add')
    @translate_params.register('email_entity_domain', 'remove')
    @translate_params.register('email_entity_domain', 'modify')
    def email_entity_dom_add_rem_mod(self, subject_entity, destination_entity,
                                     change_params):
        if 'aff' in change_params and change_params['aff'] is not None:
            try:
                change_params.update(
                    {'aff_str': six.text_type(self.const.PersonAffiliation(
                        change_params['aff']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        return change_params

    @translate_params.register('email_tfilter', 'add')
    @translate_params.register('email_tfilter', 'remove')
    def email_tfilter_add(self, subject_entity, destination_entity,
                          change_params):
        if 'filter' in change_params and change_params['filter'] is not None:
            try:
                change_params.update(
                    {'filter_str': six.text_type(self.const.EmailTargetFilter(
                        change_params['filter']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        return change_params

    @translate_params.register('email_sfilter', 'add')
    @translate_params.register('email_sfilter', 'modify')
    def email_sfilter_add(self, subject_entity, destination_entity,
                          change_params):
        if 'level' in change_params and change_params['level'] is not None:
            try:
                change_params.update(
                    {'level_str': six.text_type(self.const.EmailSpamLevel(
                        change_params['level']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        if 'action' in change_params and change_params['action'] is not None:
            try:
                change_params.update(
                    {'action_str': six.text_type(self.const.EmailSpamAction(
                        change_params['action']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        return change_params

    @translate_params.register('email_primary_address', 'add')
    @translate_params.register('email_primary_address', 'remove')
    @translate_params.register('email_primary_address', 'modify')
    @translate_params.register('exchange', 'acc_primaddr')
    def email_primary_address_add(self, subject_entity, destination_entity,
                                  change_params):
        if 'addr_id' in change_params and change_params['addr_id'] is not None:
            self.ea.clear()
            try:
                self.ea.find(change_params['addr_id'])
            except Cerebrum.Errors.NotFoundError:
                pass
            else:
                change_params['addr'] = self.ea.get_address()
        return change_params

    @translate_params.register('email_server', 'add')
    @translate_params.register('email_server', 'remove')
    @translate_params.register('email_server', 'modify')
    def email_server_add(self, subject_entity, destination_entity,
                         change_params):
        if ('server_type' in change_params and
                change_params['server_type'] is not None):
            try:
                change_params.update(
                    {'server_type_str': six.text_type(
                        self.const.EmailServerType(
                            change_params['server_type']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        return change_params

    @translate_params.register('entity_trait', 'add')
    @translate_params.register('entity_trait', 'remove')
    @translate_params.register('entity_trait', 'modify')
    def trait_mod(self, subject_entity, destination_entity,
                  change_params):
        if ('entity_type' in change_params and
                change_params['entity_type'] is not None):
            try:
                change_params.update(
                    {'entity_type_str': six.text_type(self.const.EntityType(
                        change_params['entity_type']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        if 'code' in change_params and change_params['code'] is not None:
            try:
                change_params.update(
                    {'code_str': six.text_type(self.const.EntityTrait(
                        change_params['code']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        return change_params

    @translate_params.register('ephorte_role', 'add')
    @translate_params.register('ephorte_role', 'remove')
    @translate_params.register('ephorte_role', 'modify')
    def ephorte_role_add(self, subject_entity, destination_entity,
                         change_params):
        if ('arkivdel' in change_params and
                change_params['arkivdel'] is not None):
            try:
                change_params.update(
                    {'arkivdel_str': six.text_type(self.const.EphorteArkivdel(
                        change_params['arkivdel']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        if ('rolle_type' in change_params and
                change_params['rolle_type'] is not None):
            try:
                change_params.update(
                    {'rolle_type_str': six.text_type(self.const.EphorteRole(
                        change_params['rolle_type']))})
            except Cerebrum.Errors.NotFoundError:
                pass
        return change_params

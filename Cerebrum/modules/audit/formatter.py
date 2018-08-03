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
""" Format audit log records.


This module contains utilities to turn a AuditRecord into a
FormattedAuditRecord.
"""
import collections
import logging
import re

import six

logger = logging.getLogger(__name__)


def _format_entity(entity_id, entity_type, entity_name):
    """ helper function to format entity_id, target_id, operator_id data. """
    if entity_id is None:
        return None

    if entity_name:
        return '%s(%r)' % (entity_name, entity_id)
    else:
        return '<no name>(%r)' % (entity_name, entity_id)


# def _format_entity(entity_id, entity_type, entity_name):
#     if entity_id is None:
#         return None

#     if entity_type:
#         entity_type = six.text_type(entity_type)
#     else:
#         entity_type = '<entity>'

#     if entity_name:
#         return '%s(id=%r, name=%s)' % (entity_type, entity_id, entity_name)
#     else:
#         return '%s(id=%r)' % (entity_type, entity_id)


def format_operator(record):
    return _format_entity(record.operator_id,
                          (record.metadata or {}).get('operator_type'),
                          (record.metadata or {}).get('operator_name'))


def format_entity(record):
    return _format_entity(record.entity_id,
                          (record.metadata or {}).get('entity_type'),
                          (record.metadata or {}).get('entity_name'))


def format_target(record):
    return _format_entity(record.target_id,
                          (record.metadata or {}).get('target_type'),
                          (record.metadata or {}).get('target_name'))


def format_timestamp(record):
    return record.timestamp.strftime('%Y-%m-%d %H:%M:%S %z')


class FormattedRecord(object):
    """ AuditRecord-like object with formatted attributes. """

    def __init__(self, record, message=None):
        self._record = record
        self.message = message

    def __repr__(self):
        return '<%s change=%s message=%r>' % (
            self.__class__.__name__,
            self.change,
            self.message)

    @property
    def timestamp(self):
        """ formatted timestamp string or None. """
        if self._record.timestamp:
            return format_timestamp(self._record)
        else:
            # TODO: Default to <now> with tz?
            return None

    @property
    def change(self):
        return six.text_type(self._record.change_type)

    @property
    def operator(self):
        """ formatted operator identifier or None. """
        return format_operator(self._record)

    @property
    def entity(self):
        """ formatted entity identifier or None. """
        return format_entity(self._record)

    @property
    def target(self):
        """ formatted target identifier or None. """
        return format_target(self._record)

    @property
    def change_program(self):
        return (self._record.metadata or {}).get('change_program')

    @property
    def change_by(self):
        """ formatted operator identifier, change_program or None. """
        return (self.operator or self.change_program)


def format_message(record):
    """ Default message formatter for records. """

    return ' '.join(
        '%s=%r' % (key, value)
        for key, value in (
                ('record', getattr(record, 'record_id', None)),
                ('params', record.params),
                ('metadata', record.metadata),
        )
        if value)


# TODO: Generalize and move somewhere else?
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


# TODO: Restructure into a series for formatters that can be chained?
class AuditRecordFormatter(object):

    custom_formatters = _ChangeTypeCallbacks()

    def _get_message(self, record):
        message = None

        def msg(method):
            try:
                return method(record)
            except Exception:
                logger.error("unable to format record_id=%r using %r",
                             record.record_id, callback,
                             exc_info=True)

        # Manual overrides for specific change_type values
        callback = self.custom_formatters.get_callback(
            record.change_type.category,
            record.change_type.type)
        if callback:
            message = msg(callback)

        # Format strings specified within change_type codes.
        fmt = getattr(record.change_type, 'format', None)
        if fmt and not message:
            message = msg(format_message_from_const)

        # Default format and fallbacks
        if not message:
            message = msg(format_message)
        if not message:
            message = msg(repr)
        if not message:
            message = '<%r id=record_id>' % (type(record).__name__,
                                             record.record_id)
        return message

    def __call__(self, record):
        return FormattedRecord(record, self._get_message(record))


# Legacy format utils
#
# TODO: All these should be removed as the database is migrated
#       Code from here on an onwards is mainly copied from the bofhd entity
#       hisotry formatting utils.

# un-peplike, but it's moved down here in order to prevent others from using
# them.
import Cerebrum.Errors
from Cerebrum.Utils import Factory


def _find_value(record, name, default=None):
    record = record.to_dict()
    params = record.pop('params', {})
    meta = record.pop('metadata', {})
    for d in [params, meta, record]:
        if name in d:
            return d[name]
    return default


def format_message_from_const(record):
    msg = []
    msg_string = getattr(record.change_type, 'msg_string')
    fmt = getattr(record.change_type, 'format', [])

    if msg_string is None:
        logger.warn('Formatting of change log entry of type %s '
                    'failed, no description defined in change type',
                    six.text_type(record.change_type))
        msg.append(six.text_type(record.change_type))
        msg_string = ('subject %(subject)s, destination %(dest)s')
    try:
        msg.append(msg_string % {
            'subject': format_entity(record),
            'dest': format_target(record),
        })
    except Exception:
        logger.warn("failed applying message %r to record %r",
                    msg_string, record.record_id, exc_info=True)

    for f in fmt:
        repl = {}
        for part in re.findall(r'%\([^\)]+\)s', f):
            fmt_type, key = part[2:-2].split(':')
            try:
                _kk = '%%(%s:%s)s' % (fmt_type, key)
                repl[_kk] = _format_from_cl(fmt_type, _find_value(record, key))
            except Exception:
                logger.warn("Failed applying %r to record %r",
                            part, repr(record), exc_info=True)
        if any(repl.values()):
            for k, v in repl.items():
                f = f.replace(k, v)
            msg.append(f)
    return ', '.join(msg)


class _ConstantFormatter(object):
    """ Turn constant intval into constant strval. """

    co_type_map = {
        'affiliation': ['PersonAffiliation'],
        'extid': ['EntityExternalId'],
        'id_type': ['ChangeType'],
        'home_status': ['AccountHomeStatus'],
        'name_variant': ['PersonName', 'EntityNameCode'],
        'quarantine_type': ['Quarantine'],
        'source_system': ['AuthoritativeSystem'],
        'spread_code': ['Spread'],
        'trait': ['EntityTrait'],
        'value_domain': ['ValueDomain'],
        'rolle_type': ['EphorteRole'],
        'perm_type': ['EphortePermission'],
    }

    def __init__(self, db=None):
        self.co = Factory.get('Constants')(db)

    def __contains__(self, co_type):
        return co_type in self.co_type_map

    def __call__(self, ident, value):
        types = [getattr(self.co, attr) for attr in self.co_type_map[ident]]

        def f(cls, code):
            try:
                return (1, six.text_type(cls(code)))
            except Cerebrum.Errors.NotFoundError:
                return (2, 'unknown %s %r' % (ident, value))

        return sorted([f(c, value) for c in types])[0][1]


class _EntityFormatter(object):
    """ turn entities and values into strings """

    en_type_map = {
        'disk': '_fmt_disk_id',
        'date': '_fmt_date',
        'timestamp': '_fmt_ts',
        'entity': '_fmt_entity',
        'ou': '_fmt_entity',
        'homedir': '_fmt_homedir',
        'int': '_fmt_str',
        'string': '_fmt_str',
        'bool': '_fmt_bool',
    }

    def __init__(self, db=None):
        if db:
            self.db = db
        else:
            self.db = Factory.get('Database')()
        self.co = Factory.get('Constants')(db)

    def __contains__(self, en_type):
        return en_type in self.en_type_map

    def __call__(self, ident, value):
        return getattr(self, self.en_type_map[ident])(value)

    def _fmt_disk_id(self, disk_id):
        disk = Factory.get('Disk')(self.db)
        try:
            disk.find(disk_id)
            return disk.path
        except Cerebrum.Errors.NotFoundError:
            return "deleted_disk:%r" % (disk_id,)

    def _fmt_date(self, value):
        return value.date

    def _fmt_ts(self, value):
        return six.text_type(value)

    def _fmt_entity(self, value):
        return 'entity_id:%r' % (value, )

    def _fmt_homedir(self, value):
        return 'homedir_id:%r' % (value, )

    def _fmt_str(self, value):
        return six.text_type(value)

    def _fmt_ou(self, value):
        return 'ou_id:%r' % (value, )

    def _fmt_bool(self, value):
        if value == 'T':
            return repr(True)
        elif value == 'F':
            return repr(False)
        else:
            return repr(bool(value))


def _format_from_cl(value_type, value):

    en_fmt = _EntityFormatter()
    co_fmt = _ConstantFormatter()

    if value is None:
        return ''

    if value_type in en_fmt:
        return en_fmt(value_type, value)
    elif value_type in co_fmt:
        return co_fmt(value_type, value)
    else:
        logger.warn("bad cl format %r: %r", value_type, value)
        return ''

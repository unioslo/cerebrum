# -*- coding: utf-8 -*-
#
# Copyright 2018-2023 University of Oslo, Norway
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
Format audit log records.

This module contains utilities to format audit records.  The process is split
into two distinct steps: processing into an intermediate data structure, and
formatting that intermediate data structure.

Preparing a :class:`.record.AuditRecord`
    A callable (default implementation in :class:`.AuditRecordProcessor`) that
    takes AuditRecord objects from the database, and turns them into
    PreparedRecord objects.

    The processor decides the overall *message*, and allows custom messages for
    individual change types.

Intermediate format (:class:`.PreparedRecord`)
    Each PreparedRecord is a seriablizable verison of the original AuditRecord.
    The PreparedRecord decides how individual fields are formatted (timestamp
    as ISO8601, subject entity strings, etc...)

Formatting a :class:`.PreparedRecord`
    A callable (default implementation in :class:`.AuditRecordFormatter`) that
    takes PreparedRecord objects and returns the final, formatted or serialized
    record.  The default just takes a format string as input, and formats it
    with fields from the PreparedRecord.

    This could be replaced to e.g. format the entire PreparedRecord dict as a
    JSON-blob.

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import collections
import logging
import re

import six

from Cerebrum.utils import date_compat

logger = logging.getLogger(__name__)


def _format_entity(entity_id, entity_type, entity_name):
    """ helper function to format entity_id, target_id, operator_id data. """
    if entity_id is None:
        return None

    if entity_name:
        return '%s(%r)' % (entity_name, entity_id)
    else:
        return '<no name>(%r)' % (entity_id)


class PreparedRecord(object):
    """
    AuditRecord-like object with formatted attributes.

    This object wraps AuditRecord objects, and presents all its attributes as
    human readable values, suitable for formatting.

    Unlike other record objects, all fields are read-only.
    """

    def __init__(self, record, message=None):
        self._record = record
        self.message = message

    def __repr__(self):
        return "<%s change=%s message=%r>" % (
            self.__class__.__name__,
            self.change_type,
            self.message,
        )

    @property
    def timestamp(self):
        """ formatted timestamp string or None. """
        if self._record.timestamp:
            return self._record.timestamp.strftime('%Y-%m-%d %H:%M:%S %z')
        else:
            return None

    @property
    def change_type(self):
        return six.text_type(self._record.change_type)

    @property
    def operator(self):
        """ formatted operator identifier or None. """
        return _format_entity(
            self._record.operator_id,
            (self._record.metadata or {}).get('operator_type'),
            (self._record.metadata or {}).get('operator_name'),
        )

    @property
    def entity(self):
        """ formatted entity identifier or None. """
        return _format_entity(
            self._record.entity_id,
            (self._record.metadata or {}).get('entity_type'),
            (self._record.metadata or {}).get('entity_name'),
        )

    @property
    def target(self):
        """ formatted target identifier or None. """
        return _format_entity(
            self._record.target_id,
            (self._record.metadata or {}).get('target_type'),
            (self._record.metadata or {}).get('target_name'),
        )

    @property
    def change_program(self):
        return (self._record.metadata or {}).get('change_program')

    @property
    def change_by(self):
        """ formatted operator identifier, change_program or None. """
        return (self.change_program or self.operator)

    def __getattr__(self, attr):
        return getattr(self._record, attr)

    def to_dict(self):
        d = self._record.to_dict()
        d.update({
            'message': self.message,
            'timestamp': self.timestamp,
            'change_type': self.change_type,
            'operator': self.operator,
            'entity': self.entity,
            'target': self.target,
            'change_program': self.change_program,
            'change_by': self.change_by,
        })
        return d


# TODO: Generalize and move somewhere else?
class _ChangeTypeCallbacks(object):
    """ Register with Callback functions for _ChangeTypeCode attributes. """

    def __init__(self):
        self.callbacks = collections.OrderedDict()

    def register(self, category, change):
        """ Register an event generator for a given change type. """
        key = re.compile(r'^{0}:{1}$'.format(category, change))

        def wrapper(fn):
            self.callbacks[key] = fn
            return fn
        return wrapper

    def get_callback(self, category, change):
        term = "{0}:{1}".format(category, change)
        for key in self.callbacks:
            if key.match(term):
                return self.callbacks[key]


class AuditRecordProcessor(object):
    """
    Process audit records into a PreparedRecord.

    The final *message* attribute will be the first message that
    exists/succeeds out of:

    1. ``custom_formatters`` callback, if it exists
    2. _LegacyMessageFormatter, which tries to format a message from the
       ``msg_string``/``format`` of the change type itself.
    3. ``format_message`` callback, which outputs the params and metadata
    4. ``repr`` of the AuditRecord
    5. The AuditRecord id
    """
    # TODO: Find *one* good way to describe how to format records

    custom_formatters = _ChangeTypeCallbacks()

    @custom_formatters.register('e_account', 'mod')
    @staticmethod
    def format_account_mod(record):
        """ temporary issue with formatting date values. """
        entity_repr = _format_entity(
            record.entity_id,
            (record.metadata or {}).get('entity_type'),
            (record.metadata or {}).get('entity_name'))
        return 'modified account %s attrs=%r' % (entity_repr,
                                                 (record.params or {}).keys())

    def _get_message(self, record):
        message = None

        def try_msg(method):
            if hasattr(method, '__func__'):
                # unbound staticmethod workaround ...
                method = getattr(method, '__func__')
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
            message = try_msg(callback)

        # Format strings specified within change_type codes.
        if (not message and
                (getattr(record.change_type, 'msg_string', None) or
                 getattr(record.change_type, 'format', None))):
            message = try_msg(_format_message_from_const)

        # Default format and fallbacks
        if not message:
            message = try_msg(format_message)
        if not message:
            message = try_msg(repr)
        if not message:
            message = "<%r id=%r>" % (type(record).__name__,
                                      record.record_id)
        return message

    def __call__(self, record):
        return PreparedRecord(record, self._get_message(record))


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


class AuditRecordFormatter(object):
    """ Format a log record string. """

    def __init__(self, fmt):
        self.fmt = fmt

    def __repr__(self):
        return '{cls.__name__}({obj.fmt!r})'.format(cls=type(self), obj=self)

    def __call__(self, record):
        data = record.to_dict()
        return self.fmt.format(**data)


#
# Legacy format utils
#
# TODO: All this should be removed.  Code from here on an onwards is mainly
#       copied from the bofhd entity hisotry formatting utils.

# These imports are un-peplike, but it's moved down here in order to prevent
# others from using them.
import Cerebrum.Errors               # noqa: E402
from Cerebrum.Utils import Factory   # noqa: E402


def _format_message_from_const(record):
    """
    Format message according to its `record.change_type`.

    This wrapper formats messages using the _LegacyMessageFormatter, in a
    separate database transaction.
    """
    # We use a new db transaction here -- we don't want formatting of cl
    # records to depend on a database -- this is just a way to handle old cruft
    db = Factory.get('Database')()
    formatter = _LegacyMessageFormatter(db)
    return formatter(record)


def _find_value(record, name, default=None):
    """
    Find a field in a record.

    Helper for the _LegacyMessageFormatter that tries to look up existing
    values in:

    1. The record itself
    2. The record params
    3. The record metadata
    """
    record = record.to_dict()
    params = record.pop('params', {})
    meta = record.pop('metadata', {})
    for d in [params, meta, record]:
        if not isinstance(d, (dict, collections.Mapping)):
            continue
        if name in d:
            return d[name]
    return default


class _LegacyMessageFormatter(object):
    """
    Legacy `user history`-like message formatter.

    This formatter tries to generate a message from the audit record
    `change_type.msg_string` and `change_type.format` values.  The idea is not
    bad, but the implementation is, as this formatter depends on the database
    to look up related entities and constant types for formatting.  This has a
    few major drawbacks:

    1. We need to query the database for each record/message, which is
       expensive.
    2. Entities must still exist in the database.
    3. Constants must still exist in the database, and carry the same meaning.

    This re-implementation does try to avoid database lookups, but will fall
    back to doing these if neccessary.
    """

    def __init__(self, db):
        self._format_entity = _EntityFormatter(db)
        self._format_const = _ConstantFormatter(db)

    def format_value(self, value_type, value):
        if value is None:
            return ''

        if value_type in self._format_entity:
            return self._format_entity(value_type, value)
        elif value_type in self._format_const:
            return self._format_const(value_type, value)
        else:
            logger.warn("bad cl format %r: %r", value_type, value)

    def __call__(self, record):
        """ Format a record. """
        msg_string = getattr(record.change_type, 'msg_string')
        fmt = getattr(record.change_type, 'format') or []
        msg = []

        if msg_string is None:
            logger.warn('Formatting of change log entry of type %s '
                        'failed, no description defined in change type',
                        six.text_type(record.change_type))
            msg.append(six.text_type(record.change_type))
            msg_string = ('subject %(subject)s, destination %(dest)s')
        try:
            msg.append(msg_string % {
                'subject': _format_entity(
                    record.entity_id,
                    (record.metadata or {}).get('entity_type'),
                    (record.metadata or {}).get('entity_name')),
                'dest': _format_entity(
                    record.target_id,
                    (record.metadata or {}).get('target_type'),
                    (record.metadata or {}).get('target_name')),
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
                    repl[_kk] = self.format_value(fmt_type,
                                                  _find_value(record, key))
                except Exception:
                    logger.warn("Failed applying %r to record %r",
                                part, repr(record), exc_info=True)
            if any(repl.values()):
                for k, v in repl.items():
                    f = f.replace(k, v)
                msg.append(f)
        return ', '.join(msg)


class _ConstantFormatter(object):
    """
    Turn constant intval into strval.

    Helper for the _LegacyMessageFormatter that translates constant intvals
    from e.g. params to constant strvals.
    """

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

    def __init__(self, db):
        self.const = Factory.get('Constants')(db)
        self.clconst = Factory.get('CLConstants')(db)

    def __contains__(self, co_type):
        return co_type in self.co_type_map

    def get_type(self, attr):
        try:
            return getattr(self.const, attr)
        except AttributeError:
            return getattr(self.clconst, attr)

    def __call__(self, ident, value):
        types = [self.get_type(attr) for attr in self.co_type_map[ident]]

        def f(cls, code):
            try:
                return (1, six.text_type(cls(code)))
            except Cerebrum.Errors.NotFoundError:
                return (2, 'unknown %s %r' % (ident, value))

        return sorted([f(c, value) for c in types])[0][1]


class _EntityFormatter(object):
    """
    Turn entities and values into strings.

    Helper for the _LegacyMessageFormatter that translates various values
    into suitable strings.
    """

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

    def __init__(self, db):
        self.db = db

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
        if isinstance(value, six.string_types):
            return value
        return six.text_type(date_compat.get_date(value))

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

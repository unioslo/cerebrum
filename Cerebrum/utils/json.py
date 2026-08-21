# encoding: utf-8
#
# Copyright 2018-2026 University of Oslo, Norway
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
JSON encoding and decoding with Cerebrum-specific type support.

Provides a :class:`JSONEncoder` for serializing Cerebrum types, dates, and sets,
and :class:`CerebrumObject` for deserializing Cerebrum types.

Cerebrum objects
    Cerebrum objects (Entity, constants) are serialized with a special JSON
    object structure.  This structure includes the internal object IDs (entity
    id or code value), as well as metadata (name, strval) for use outside of
    Cerebrum.

    When loading a JSON object with this structure, the load-functions in this
    module will try to look up the objects in the database.

    .. note::
       The object lookup (and resulting objects) use a separate database
       transaction.

Datetime
    The :class:`JSONEncoder` is able to serialize date and datetime objects
    using ISO-8601 notation.  These objects will *not* be restored on load,
    however.

Set
    The :class:`JSONEncoder` serializes ``set`` objects as a sorted list.


On Python 2, the :class:`JSONEncoder` generates text/unicode objects, rather
than bytestrings.  This means that :func:`dumps` returns unicode, and
:func:`dump` requires a *text stream* rather than a *byte stream*.


TODO
----
We should make this module a bit more flexible.  We may not always want
to serialize *constants* the way they are serialized here, but still want the
date/datetime serialization.  This module should implement a simple framework
that lets us mix-and-match serializers.

There's an issue with loading cerebrum objects (entities, constants), where we
must set up and use a global database connection to fetch the actual objects.
The design supports providing our own db connection when loading objects, but
this has two other problems:

- The database connection we provide is then set as the new, global database
  connection for future loads

- The functionality for providing a db connection or constants as keyword
  arguments *db* or *const* is broken - it won't work as the keyword arguments
  are passed on to the built-in json decoder.  The only way to actually provide
  these objects, is to give load(s) an initialized `CerebrumObject` as
  *object_hook*.

Generally, the idea of auto-loading these serialized values isn't great.
It's hard to generalize handling of missing/deprecated constants, or deleted
entities here.  It's probably _better_ to standardize on a serialized format,
and maybe implement a wrapper object that can later help look up these values,
if needed.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import datetime
import json
import json.encoder

import six

import Cerebrum.Errors as Errors
from Cerebrum import Constants
from Cerebrum.Entity import Entity
from Cerebrum.Utils import Factory
from Cerebrum.utils import date_compat
from Cerebrum.utils.date import apply_timezone


#
# JSONEncoder conversions, for dump/dumps.
#


_conversions = []


def _conv(cls):
    def reg(fun):
        _conversions.append((cls, fun))
        return fun
    return reg


@_conv(datetime.date)
def date_to_json(dt):
    """ Serialize date/datetime as ISO-8601 string. """
    if isinstance(dt, datetime.datetime) and not dt.tzinfo:
        dt = apply_timezone(dt)
    return dt.isoformat()


# Needs special handling, as we can't check the type without importing
# `mx.DateTime`
def mx_datetime_to_json(dt):
    """ Serialize mx-like datetime as ISO-8601 string. """
    if date_compat.is_mx_date(dt):
        return date_to_json(dt.pydate())
    else:
        return date_to_json(dt.pydatetime())


@_conv(Constants.Constants.CerebrumCode)
def code_to_json(code):
    """ Serialize CerebrumCode as a dict with code value and metadata. """
    return {
        '__cerebrum_object__': 'code',
        'table': code._lookup_table,
        'code': int(code),
        'str': six.text_type(code),
    }


@_conv(Entity)
def entity_to_json(entity):
    """ Serialize Entity as a dict with entity_id and metadata. """
    return {
        '__cerebrum_object__': 'entity',
        'entity_id': entity.entity_id,
        'str': six.text_type(entity),
        'entity_type': code_to_json(
            Constants.Constants.EntityType(entity.entity_type),
        ),
    }


@_conv(set)
def set_to_json(value):
    """ Serialize set as a sorted list. """
    return list(sorted(value))


class JSONEncoder(json.encoder.JSONEncoder):
    """
    Extended JSONEncoder.

    This JSONEncoder produces unicode objects, for use with text streams on
    both Python 2 and Python 3.

    Additionally, this encoder supports a couple of new objects:

    - date, datetime and mx-datetime like values
    - set
    - Cerebrum objects (Constants, Entity)

    """
    def __init__(self, ensure_ascii=False, sort_keys=True, **kw):
        """ Initialize with ensure_ascii=False and sort_keys=True. """
        super(JSONEncoder, self).__init__(ensure_ascii=False,
                                          sort_keys=True,
                                          **kw)

    def default(self, o):
        """ Encode Cerebrum types, dates, and sets. """
        for base, fun in _conversions:
            if date_compat.is_mx_datetime(o):
                # TODO: remove when egenix-mx-base is gone
                return mx_datetime_to_json(o)
            if isinstance(o, base):
                return fun(o)
        return super(JSONEncoder, self).default(o)

    def iterencode(self, *rest, **kw):
        if six.PY2:
            return self._py2_iterencode(*rest, **kw)
        # No encoding fixes needed for PY3
        return super(JSONEncoder, self).iterencode(*rest, **kw)

    def _py2_iterencode(self, *rest, **kw):
        """
        Decode iterencode output to unicode.

        PY2: JSONEncoder.iterencode encodes strings as UTF-8 bytestrings, and
        we want the output to be unicode for future compatibility.
        """
        encoding = getattr(self, "encoding", None) or "UTF-8"

        def fixer(x):
            if type(x) is bytes:
                return x.decode(encoding)
            else:
                return x

        return (fixer(x)
                for x in super(JSONEncoder, self).iterencode(*rest, **kw))


def dumps(obj, ensure_ascii=False, sort_keys=True, cls=JSONEncoder,
          *args, **kw):
    """
    Serialize *obj* to a JSON string.

    Like :func:`json.dumps`, but uses :class:`.JSONEncoder` by default.
    Returns unicode on Python 2.
    """
    return json.dumps(obj, ensure_ascii=ensure_ascii,
                      sort_keys=sort_keys, cls=cls, *args, **kw)


def dump(obj, fp, ensure_ascii=False, sort_keys=True, cls=JSONEncoder,
         *args, **kw):
    """
    Serialize *obj* as JSON to file *fp*.

    Like :func:`json.dump`, but uses :class:`.JSONEncoder` by default.
    Requires a text stream on Python 2.
    """
    return json.dump(obj, fp, ensure_ascii=ensure_ascii,
                     sort_keys=sort_keys, cls=cls, *args, **kw)


class CerebrumObject(object):
    """ Object hook for deserializing Cerebrum objects from JSON. """

    def __init__(self, db, constants):
        self.db = db
        self.const = constants

    def __call__(self, obj):
        try:
            fun = getattr(self, obj['__cerebrum_object__'])
        except AttributeError:  # no attribute for object
            raise ValueError('No handler for decoding {} as json'.format(
                obj['__cerebrum_object__']))
        except KeyError:  # no __cerebrum_object__
            return obj
        return fun(obj)

    def code(self, obj):
        """ Deserialize a CerebrumCode from JSON dict. """
        try:
            c = self.const.resolve_constant(self.db, obj['code'])
        except KeyError:
            raise ValueError('Object {} has no code'.format(obj))
        if c is None:  # code does not exist any more
            return obj['str']
        return c

    def entity(self, obj):
        """ Deserialize an Entity from JSON dict. """
        try:
            comp = Factory.type_component_map[str(obj['entity_type'])]
        except KeyError:
            comp = 'Entity'
        ret = Factory.get(comp)(self.db)
        try:
            ret.find(obj['entity_id'])
            return ret
        except Errors.NotFoundError:  # Entity deleted
            return obj


_cache_db = None
_cache_const = None


def _db_const(db=None, const=None, **kw):
    global _cache_db, _cache_const
    if db is None:
        if _cache_db is None:
            _cache_db = Factory.get('Database')()
        db = _cache_db
    if const is None:
        if _cache_const is None:
            _cache_const = Factory.get('Constants')()
        const = _cache_const
    return db, const


def load(*rest, **kw):
    """
    Deserialize JSON from a file, with Cerebrum object support.

    Like :func:`json.load`, but includes an ``object_hook`` for recreating
    Cerebrum objects (Entity, constants).
    """

    if len(rest) >= 4 or 'object_hook' in kw:
        return json.load(*rest, **kw)
    return json.load(*rest, object_hook=CerebrumObject(*_db_const(**kw)), **kw)


def loads(*rest, **kw):
    """
    Deserialize JSON from a string, with Cerebrum object support.

    Like :func:`json.loads`, but includes an ``object_hook`` for recreating
    Cerebrum objects (Entity, constants).
    """

    if len(rest) >= 4 or 'object_hook' in kw:
        return json.loads(*rest, **kw)
    return json.loads(
        *rest, object_hook=CerebrumObject(*_db_const(**kw)), **kw)

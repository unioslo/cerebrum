# encoding: utf-8
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

from __future__ import unicode_literals, absolute_import
import json
import json.encoder
import datetime
import six
from Cerebrum import Constants
from Cerebrum.Entity import Entity
from .date import apply_timezone
from mx.DateTime import DateTimeType
from Cerebrum.Utils import Factory
import Cerebrum.Errors as Errors

"""Utilities for JSON handling

Normally, standard JSON functionality should be used, but these functions
will amend standard behaviour with Cerebrum specific logic.
"""

_conversions = []


def _conv(cls):
    def reg(fun):
        _conversions.append((cls, fun))
        return fun
    return reg


@_conv(DateTimeType)
def mx_DateTime_to_json(dt):
    """ Convert mx.DateTime.DateTime object to json. """
    if dt.hour == dt.minute == 0 and dt.second == 0.0:
        return dt.pydate().isoformat()
    else:
        return apply_timezone(dt.pydatetime()).isoformat()


@_conv(datetime.datetime)
def datetime_to_json(dt):
    """ Convert datetime.datetime object to json. """
    if not dt.tzinfo:
        dt = apply_timezone(dt)
    return dt.isoformat()


@_conv(Constants.Constants.CerebrumCode)
def code_to_json(code):
    """ Convert CerebrumCode to json """
    return dict(
        __cerebrum_object__='code',
        table=code._lookup_table,
        code=int(code),
        str=six.text_type(code))


@_conv(Entity)
def entity_to_json(entity):
    """ Convert entity to json """
    return dict(
        __cerebrum_object__='entity',
        entity_id=entity.entity_id,
        str=six.text_type(entity),
        entity_type=code_to_json(Constants.Constants.EntityType(
            entity.entity_type)))


class JSONEncoder(json.encoder.JSONEncoder):
    """
    Extend JSONEncoder with:

        * mx.DateTime
        * constants
        * Entity
    """

    def __init__(self, ensure_ascii=False, sort_keys=True, **kw):
        """Construct JSONEncoder, set some other defaults"""
        super(JSONEncoder, self).__init__(ensure_ascii=False,
                                          sort_keys=True,
                                          **kw)

    def default(self, o):
        """ Handle Cerebrum cases """
        for base, fun in _conversions:
            if isinstance(o, base):
                return fun(o)
        return super(JSONEncoder, self).default(o)

    def iterencode(self, *rest, **kw):
        e = self.encoding

        def fixer(x):
            if type(x) is str:
                return x.decode(e)
            else:
                return x
        if e is None:
            e = 'UTF-8'
        return (fixer(x)
                for x in super(JSONEncoder, self).iterencode(*rest, **kw))


def dumps(obj, ensure_ascii=False, sort_keys=True, cls=JSONEncoder,
          *args, **kw):
    return json.dumps(obj, ensure_ascii=ensure_ascii,
                      sort_keys=sort_keys, cls=cls, *args, **kw)


def dump(obj, fp, ensure_ascii=False, sort_keys=True, cls=JSONEncoder,
         *args, **kw):
    return json.dump(obj, fp, ensure_ascii=ensure_ascii,
                     sort_keys=sort_keys, cls=cls, *args, **kw)


@six.python_2_unicode_compatible
class FakeConst(object):
    def __init__(self, i, s):
        self.i = i
        self.s = s

    def __str__(self):
        return self.s

    def __int__(self):
        return self.i


class CerebrumObject(object):
    """ Object hook to get back from objects to cerebrum """

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
        """ Convert constants code. """
        try:
            c = self.const.resolve_constant(self.db, obj['code'])
        except KeyError:
            raise ValueError('Object {} has no code'.format(obj))
        if c is None:  # code does not exist any more
            return obj['str']
        return c

    def entity(self, obj):
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
    """ As standard json.load, but with magic for cerebrum objects.

    :type db: Database
    :param db: Cerebrum database

    :type const: Constants
    :param const: Cerebrum constants
    """

    if len(rest) >= 4 or 'object_hook' in kw:
        return json.load(*rest, **kw)
    return json.load(*rest, object_hook=CerebrumObject(*_db_const(**kw)), **kw)


def loads(*rest, **kw):
    """ As standard json.loads, but with magic for cerebrum objects.
    :type db: Database
    :param db: Cerebrum database

    :type const: Constants
    :param const: Cerebrum constants
    """

    if len(rest) >= 4 or 'object_hook' in kw:
        return json.loads(*rest, **kw)
    return json.loads(*rest, object_hook=CerebrumObject(*_db_const(**kw)), **kw)

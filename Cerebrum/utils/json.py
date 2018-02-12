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
import six
from Cerebrum import Constants
from Cerebrum.Entity import Entity
from .date import apply_timezone
from mx.DateTime import DateTimeType

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
def mxDateTimeToJson(dt):
    """ Convert mx.DateTime.DateTime object to json. """
    if dt.hour == dt.minute == 0 and dt.second == 0.0:
        return dt.pydate().isoformat()
    else:
        return apply_timezone(dt.pydatetime()).isoformat()


@_conv(Constants.Constants.CerebrumCode)
def codetojson(code):
    """ Convert CerebrumCode to json """
    return dict(
        table=code._lookup_table,
        code=int(code),
        str=six.text_type(code))


@_conv(Entity)
def entitytojson(entity):
    """ Convert entity to json """
    return dict(
        entity_id=entity.entity_id,
        entity_type=codetojson(Constants.Constants.EntityType(
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


load, loads = json.load, json.loads

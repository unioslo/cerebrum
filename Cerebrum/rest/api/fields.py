#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016-2018 University of Oslo, Norway
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

from flask_restplus import fields as base
from werkzeug.routing import BuildError
from six import text_type

from Cerebrum.rest.api import db


# FIXME: We should not need the constant type for this to work.
# Something like co.map_const() without fetching everything from the db
# TBD: Maybe this is a bad idea, but it seems convenient.
class Constant(base.String):
    """Gets the string representation of a Cerebrum constant by code."""

    def __init__(self, ctype=None, transform=None, **kwargs):
        """
        :param str ctype:
            The constant type, e.g. 'EntityType'.
        :param callable transform:
            A callable that takes the constant strval, and returns a mapped
            value.
        """
        super(Constant, self).__init__(**kwargs)
        self._ctype = ctype
        self.transform = transform

    @property
    def ctype(self):
        return getattr(db.const, self._ctype)

    def format(self, code):
        strval = text_type(self.ctype(code)) if code else None
        if strval is not None and callable(self.transform):
            return self.transform(strval)
        return strval

    def output(self, key, obj, **kwargs):
        code = base.get_value(key if self.attribute is None
                              else self.attribute, obj)
        return self.format(code)


class DateTime(base.DateTime):
    """Converts an mx.DateTime to a Python datetime object if needed."""
    def format(self, dt):
        value = dt.pydatetime() if hasattr(dt, 'pydatetime') else dt
        if value is None:
            return None
        return super(DateTime, self).format(value)


def href(endpoint, description="URL to this resource"):
    """ Create a reference to another API resource. """
    return base.Url(
        endpoint=endpoint,
        absolute=False,
        description=description)

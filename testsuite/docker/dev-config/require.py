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

from functools import wraps
from _pytest.outcomes import Skipped
from Cerebrum.Metainfo import Metainfo
from Cerebrum.Utils import Factory

db = Factory.get('Database')()

print(db)
meta = Metainfo(db)
print(meta)
sql_modules = [item[0] for item in meta.list()]


def require(sql_module):
    def require_decorator(func):
        @wraps(func)
        def func_wrapper(*args, **kwargs):
            if sql_module not in sql_modules:
                return Skipped
            return func(*args, **kwargs)
        return func_wrapper
    return require_decorator


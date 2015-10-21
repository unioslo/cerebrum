#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2015 University of Oslo, Norway
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
"""Decorators used for registring a handler-method with event-types"""
import inspect


# TODO: Add error checking to see if _lut_type2meth is defined
# TODO: Is this thread safe?

class EventDecorator(object):
    @staticmethod
    def RegisterHandler(events=[]):
        """This function can be used as a decorator, in order to
            initialised the _lut_type2meth variable when a class is
            initialised. This allows us to pick functions to run based
            on event types.

            We need to inspect the previous stack frame in order to access
            the LUT in an easy manner."""
        def wrap(func):
            f = inspect.currentframe()
            lut = f.f_back.f_locals.get('_lut_type2meth')
            if isinstance(events, list):
                for e in events:
                    if e not in lut:
                        lut[e] = [func]
                    else:
                        lut[e].append(func)
            elif isinstance(events, str):
                if events not in lut:
                    lut[events] = [func, ]
                else:
                    lut[events].append(func)
            else:
                pass
            return func
        return wrap

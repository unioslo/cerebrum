#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2017 University of Oslo, Norway
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
from Cerebrum.modules.synctools.diff import log_diff


def equal(crb_data, ext_system_data, attrs,
          show_diff=False, entity_id=None, entity_type=None):
    """
    This is a base implementation of how comparisons
    of data from Cerebrum and an external system should take place.
    Entity data from both systems should be built into dicts with matching
    attributes, and then compared.
    Most syncs will probably however need more a granularized comparison
    logic, which should take place before preferably calling this function
    in the end.

    Compares the passed attributes on two dicts, and returns True if they
    are all equal, and False if not.
    @param crb_data: dict
    @param ext_system_data: dict
    @param attrs: list
    @param show_diff: bool
    @param entity_type: str
    @param entity_id: int or str
    @return: bool
    """
    if show_diff and entity_id is None or entity_type is None:
        raise TypeError('entity_id and entity_type must be passed when '
                        'show_diff is True.')
    is_equal = True
    for attr in attrs:
        try:
            if crb_data[attr] != ext_system_data[attr]:
                is_equal = False
                break
        except KeyError:
            is_equal = False
    if not is_equal and show_diff:
        log_diff(entity_id=entity_id,
                 entity_type=entity_type,
                 crb_data=crb_data,
                 ext_system_data=ext_system_data,
                 attrs=attrs)
    return is_equal

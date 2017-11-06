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
from Cerebrum.modules.synctools.compare import equal as base_equal


def equal(crb_data, ad_data, attrs,
          show_diff=False, entity_id=None, entity_type=None):
    """
    Compares the passed attributes on two dicts, and returns True if they
    are all equal, and False if not. If show_diff is True, it will call
    log_diff, which also needs entity_id and entity_type specified.
    @param crb_data: dict
    @param ad_data: dict
    @param attrs: list
    @param show_diff: bool
    @param entity_type: str
    @param entity_id: int or str
    @return: bool
    """
    # Some accounts exported to AD don't get homeDrives and this is done at
    # AD's own discretion, so skip the check if homeDrive in AD is None.
    if crb_data.get('homeDrive') is not None and ad_data['homeDrive'] is None:
        massaged_crb_data = dict(crb_data)
        massaged_crb_data['homeDrive'] = None
        return base_equal(massaged_crb_data, ad_data, attrs,
                          show_diff, entity_id, entity_type)
    return base_equal(crb_data, ad_data, attrs,
                      show_diff, entity_id, entity_type)


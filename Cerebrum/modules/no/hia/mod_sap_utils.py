#! /usr/bin/env python2.2
# -*- coding: iso8859-1 -*-
#
# Copyright 2003 University of Oslo, Norway
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

This module contains a collection of utilities for dealing with SAP-specific
data.

"""

import string





def sap_row_to_tuple(sap_row):
    return string.split(sap_row.strip(), ";")
# end sap_row_to_tuple


def tuple_to_sap_row(tuple):
    return string.join(map(lambda x: str(x), tuple),
                       ";")
# end tuple_to_sap_row

# arch-tag: 681c9a14-b395-4fd4-820e-3b9b0e7dd3e3

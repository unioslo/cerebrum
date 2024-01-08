# -*- coding: utf-8 -*-
#
# Copyright 2019-2023 University of Oslo, Norway
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
Rules for mapping a default disk to given affiliations.

This module provides storage for default homedir disk rules in Cerebrum.
The intended use is looking up and setting a home directory for new user
accounts during automatic account creation.

The data model supports setting a default disk for:

1. <AFFILIATION>/<status>@<ou>
2. <AFFILIATION>/<*>@<ou>
3. <*>/<*>@<ou>

When looking up the default disk for a given user account, you *should* provide
an affiliation (typically the affiliation that triggers account creation) to
find a default disk.  The *most specific* (first match from the list above)
will be used.  If no default disk can be found at the given <ou>, the process
is repeated with the parent ou, until a match can be found.
"""

__version__ = '1.0'

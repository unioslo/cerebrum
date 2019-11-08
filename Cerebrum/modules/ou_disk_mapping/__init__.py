# -*- coding: utf-8 -*-
# Copyright 2019 University of Oslo, Norway
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
Module to store OU Disk Mappings in Cerebrum.

This module provides storage for default home dir paths for OUs in Cerebrum.
One can also add paths for specific affiliations at an OU, and even for a
specific affiliation status if that is preferred.

The intended usage of the module is for settings home directories during
automatic account generation. If one wants to change the home dir of an account
afterwards that should be possible. This is just so that there is a default.
"""

__version__ = '1.0'

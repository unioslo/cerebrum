# -*- coding: utf-8 -*-
#
# Copyright 2012-2025 University of Oslo, Norway
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
Legacy module for ad attributes and other ad related constants.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from Cerebrum.modules.ad_attributes import adattr_mixins
from Cerebrum.modules.ad_attributes import adattr_constants
from . import ad_constants


class ConstantsActiveDirectory(ad_constants.AdSyncConstants,
                               adattr_constants.AdAttributeConstants):
    """
    Legacy joined constant collection for the Active Directory module.
    """


EntityADMixin = adattr_mixins.AdAttributeMixin

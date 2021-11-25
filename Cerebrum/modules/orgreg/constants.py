# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
Constants related to the Greg source system.
"""
from __future__ import unicode_literals

from Cerebrum import Constants


class OrgregConstants(Constants.Constants):

    system_orgreg = Constants._AuthoritativeSystemCode(
        'ORGREG',
        'Organization data from Orgreg'
    )

    perspective_orgreg = Constants._OUPerspectiveCode(
        'orgreg-tree',
        'Organization tree from Orgreg'
    )

    externalid_orgreg_id = Constants._EntityExternalIdCode(
        'ORGREG_OU_ID',
        Constants.Constants.entity_ou,
        'Unique ou identificator from Orgreg',
    )

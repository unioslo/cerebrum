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


class GregConstants(Constants.Constants):

    system_greg = Constants._AuthoritativeSystemCode(
        'GREG',
        'The guest registration system (Greg)',
    )

    externalid_greg_pid = Constants._EntityExternalIdCode(
        'GREG_PID',
        Constants.Constants.entity_person,
        'Unique person identificator from Greg',
    )

    # We don't actually populate GREG_OU_ID, but it can be useful to assign
    # greg ids to Cerebrum OU objects when testing.
    externalid_greg_ou_id = Constants._EntityExternalIdCode(
        'GREG_OU_ID',
        Constants.Constants.entity_ou,
        'Unique org unit identificator from Greg',
    )

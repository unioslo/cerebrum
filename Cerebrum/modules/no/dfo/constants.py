# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
Constants related to the DFØ SAP source system.

Note
----
This source system is used to differentiate from
``Cerebrum.modules.no.Constants.Constants.system_sap``, which is used to
reference *both*:

- SAPUiO - i.e. the previous HR-system used by Cerebrum.modules.no.uio
- Legacy DFØ integrations - i.e. the employee source system for e.g.
  Cerebrum.modules.no.hia, Cerebrum.modules.no.nmh
"""
from __future__ import unicode_literals

from Cerebrum import Constants


class DfoConstants(Constants.Constants):

    system_dfo_sap = Constants._AuthoritativeSystemCode(
        'DFO_SAP',
        'The DFØ-SAP source system',
    )

    externalid_dfo_pid = Constants._EntityExternalIdCode(
        'DFO_PID',
        Constants.Constants.entity_person,
        'Unique person identificator from DFØ-SAP',
    )

    externalid_dfo_ou_id = Constants._EntityExternalIdCode(
        'DFO_OU_ID',
        Constants.Constants.entity_ou,
        'Unique OU identificator from DFØ-SAP',
    )

    externalid_dfo_ou_acronym = Constants._EntityExternalIdCode(
        'DFO_OU_ACRONYM',
        Constants.Constants.entity_ou,
        'Unique OU acronym from DFØ-SAP',
    )

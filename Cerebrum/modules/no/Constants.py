# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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
Constants common for higher education institutions in Norway.
"""

from Cerebrum import Constants
from Cerebrum.Constants import _EntityExternalIdCode, \
                               _AuthoritativeSystemCode, \
                               _OUPerspectiveCode

class ConstantsCommon(Constants.Constants):

    # external id definitions (NO_NIN, norwegian national id number)
    externalid_fodselsnr = _EntityExternalIdCode('NO_BIRTHNO',
                                                 Constants.Constants.entity_person,
                                                 'Norwegian birth number')
class ConstantsHigherEdu(Constants.Constants):

    # authoritative source systems (FS = student registry, SAP = common HR-system)
    system_fs = _AuthoritativeSystemCode('FS', 'FS')
    system_sap = _AuthoritativeSystemCode('SAP', 'SAP')

    # external id definitions (student and employee id)
    externalid_studentnr = _EntityExternalIdCode('NO_STUDNO',
                                                 Constants.Constants.entity_person,
                                                 'Norwegian student number')
    externalid_sap_ansattnr = _EntityExternalIdCode('SAP_NR',
                                                    Constants.Constants.entity_person,
                                                    'SAP employee number')

    # OU-structure perspectives
    perspective_fs = _OUPerspectiveCode('FS', 'FS')
    perspective_sap = _OUPerspectiveCode('SAP', 'SAP')

# arch-tag: 4ba57e9c-75bd-40b6-8d6c-1340312241bb

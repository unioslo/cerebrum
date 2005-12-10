# -*- coding: iso-8859-1 -*-
# Copyright 2005 University of Oslo, Norway
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

from Cerebrum import Constants
from Cerebrum.Constants import _AuthoritativeSystemCode, _EntityExternalIdCode, \
     _PersonAffiliationCode, _PersonAffStatusCode, _OUPerspectiveCode

class ABCConstants(Constants.Constants):

    system_sats = _AuthoritativeSystemCode('SATS', 'SATS')
    system_ekstens = _AuthoritativeSystemCode('EKSTENS', 'EKSTENS')
    system_mstas = _AuthoritativeSystemCode('MSTAS', 'MSTAS')
    system_tpsys = _AuthoritativeSystemCode('TPSYS', 'TPSYS')

    perspective_ekstens = _OUPerspectiveCode('EKSTENS', 'EKSTENS')

    externalid_orgnr = _EntityExternalIdCode('ORGNR',
                                             Constants.Constants.entity_ou,
                                             'Organization number')
    externalid_ouid = _EntityExternalIdCode('OUID',
                                            Constants.Constants.entity_ou,
                                            'OU ID')
    externalid_vigonr = _EntityExternalIdCode('VIGONR',
                                              Constants.Constants.entity_ou,
                                              'VIGO nummer')
    externalid_skolenr = _EntityExternalIdCode('SKOLENR',
                                               Constants.Constants.entity_ou,
                                               'Skolenummer')
    externalid_elevnr = _EntityExternalIdCode('ELEVNR',
                                               Constants.Constants.entity_person,
                                              'Elevnummer')
    externalid_ansattnr = _EntityExternalIdCode('ANSATTNR',
                                                Constants.Constants.entity_person,
                                                'Ansattnummer')
    external_id_groupid = _EntityExternalIdCode('GROUPID',
                                                Constants.Constants.entity_group,
                                                'Group ID')
    affiliation_elev = _PersonAffiliationCode('ELEV',
                                              'Elev iflg. SAS')
    affiliation_status_elev_ektiv = _PersonAffStatusCode(
        affiliation_elev, 'aktiv', 'En aktiv elev')
    
# arch-tag: faf711ee-6995-11da-8ca7-a305f61092a7

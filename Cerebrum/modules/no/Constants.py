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

"""Access to Cerebrum code values.

"""

from Cerebrum import Constants
from Cerebrum.Constants import \
     _AuthoritativeSystemCode, _OUPerspectiveCode, _EntityExternalIdCode, \
     _PersonAffiliationCode, _PersonAffStatusCode

class Constants(Constants.Constants):

    # TBD: Finnes det egentlige *noen* konstanter som er "globale" for
    # hele Norge, og derfor bør ligge som attributter i denne klassen?

    system_sats_oslo_gs = _AuthoritativeSystemCode(
        'SATS/OSLO/GS',
        'Skoleetaten i Oslo sin SATS-instans for grunnskoler.')
    system_sats_oslo_vg = _AuthoritativeSystemCode(
        'SATS/OSLO/VGS',
        'Skoleetaten i Oslo sin SATS-instans for videregående skoler.')

    perspective_sats = _OUPerspectiveCode('SATS', 'SATS')

    externalid_personoid = _EntityExternalIdCode('SATS_PERSONOID',
                                                 Constants.Constants.entity_person,
                                                 'PK in SATS')

    affiliation_foresatt = _PersonAffiliationCode('FORESATT',
                                                  'Foresatt for elev')
    affiliation_status_foresatt_valid = _PersonAffStatusCode(
        affiliation_foresatt, 'VALID', 'Valid')

# arch-tag: 4ba57e9c-75bd-40b6-8d6c-1340312241bb

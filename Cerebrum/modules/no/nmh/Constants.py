# -*- coding: utf-8 -*-
#
# Copyright 2006-2018 University of Oslo, Norway
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

The Constants class defines a set of methods that should be used to
get the actual database code/code_str representing a given Entity,
Address, Gender etc. type."""
from __future__ import unicode_literals

from Cerebrum import Constants
from Cerebrum.Constants import (
    _SpreadCode,
    _PersonAffiliationCode,
    _PersonAffStatusCode,
)
from Cerebrum.modules.EntityTrait import _EntityTraitCode


class Constants(Constants.Constants):

    # employees - affiliation definition
    affiliation_ansatt = _PersonAffiliationCode('ANSATT', 'Ansatt ved NMH')
    # affiliations for employees
    affiliation_status_ansatt_ovlaerer = _PersonAffStatusCode(
        affiliation_ansatt, 'ans_ovlaerer', 'Ansatt ved NMH, øvingslærer.')

    # affiliations for others
    affiliation_manuell = _PersonAffiliationCode(
        'MANUELL',
        ('Tilknyttet NMH uten å være registrert i et av de'
         ' autoritative kildesystemene'))
    affiliation_status_manuell_inaktiv = _PersonAffStatusCode(
        affiliation_manuell, 'inaktiv',
        'Person uten ekte tilknytning til NMH. Bruk med forsiktighet!')

    # Spread definitions - user related
    spread_ad_account = _SpreadCode(
        'account@ad', Constants.Constants.entity_account,
        'Brukeren kjent i AD ved NMH')
    spread_exchange_account = _SpreadCode(
        'account@exchange', Constants.Constants.entity_account,
        'Brukeren kjent i AD ved NMH')

    # Spread definitions - group related
    spread_ad_group = _SpreadCode(
        'group@ad', Constants.Constants.entity_group,
        'Gruppe kjent i AD ved NMH')
    spread_lms_group = _SpreadCode(
        'group@lms', Constants.Constants.entity_group,
        'Gruppe kjent i LMSen til NMH')

    # Spread definitions - person relates
    spread_adgang_person = _SpreadCode(
        'person@adgang', Constants.Constants.entity_person,
        'Person kjent i adgangssystemet til NMH')

    # Traits for fagområde
    trait_fagomrade_fagfelt = _EntityTraitCode(
            'fagfelt',
            Constants.Constants.entity_person,
            'Trait registering part of fagområde: fagfelt')
    trait_fagomrade_instrument = _EntityTraitCode(
            'instrument',
            Constants.Constants.entity_person,
            'Trait registering part of fagområde: instrument')

    # Trait for fagmiljø
    trait_fagmiljo = _EntityTraitCode(
            'fagmiljo',
            Constants.Constants.entity_person,
            'Trait registering fagmiljø')

# -*- coding: iso-8859-1 -*-

# Copyright 2010 University of Oslo, Norway
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

from Cerebrum import Constants
from Cerebrum.Constants import _SpreadCode, \
                               _PersonAffiliationCode, \
                               _PersonAffStatusCode


class Constants(Constants.Constants):
    ## employees - affiliation definition
    affiliation_ansatt = _PersonAffiliationCode('ANSATT', 'Ansatt ved HiH')
    ## affiliations for employees
    # From NMH:
    #affiliation_status_ansatt_ovlaerer = _PersonAffStatusCode(
    #    affiliation_ansatt, 'ans_ovlaerer', 'Ansatt ved NMH, øvingslærer.')
    
    ## affiliations for others
    affiliation_manuell = _PersonAffiliationCode(
        'MANUELL',
        ('Tilknyttet HiH uten å være registrert i et av de'
         ' autoritative kildesystemene'))
    affiliation_status_manuell_inaktiv = _PersonAffStatusCode(
        affiliation_manuell, 'inaktiv',
        'Person uten ekte tilknytning til HiH. Bruk med forsiktighet!')

    ## Spread definitions - user related
    spread_ad_account = _SpreadCode(
        'account@ad', Constants.Constants.entity_account,
        'Brukeren kjent i hih-domenet i AD ved HiH')
    spread_ad_account_stud = _SpreadCode(
        'account@ad_stud', Constants.Constants.entity_account,
        'Brukeren kjent i stud-domentet i AD ved HiH')
    spread_exchange_account = _SpreadCode(
        'account@exchange', Constants.Constants.entity_account,
        'Brukeren kjent i AD ved HiH')

    ## Spread definitions - group related
    spread_ad_group = _SpreadCode(
        'group@ad', Constants.Constants.entity_group,
        'Gruppe kjent i hih-domenet i AD ved HiH')
    spread_ad_group_stud = _SpreadCode(
        'group@ad_stud', Constants.Constants.entity_group,
        'Gruppe kjent i stud-domenet i AD ved HiH')
    spread_lms_group = _SpreadCode(
        'group@lms', Constants.Constants.entity_group,
        'Gruppe kjent i LMSen til HiH') 
    spread_exchange_group = _SpreadCode(
        'group@exchange', Constants.Constants.entity_group,
        'Group exported to Exchange')       

    ## Spread definitions - person related
    spread_adgang_person = _SpreadCode(
        'person@adgang', Constants.Constants.entity_person,
        'Person kjent i adgangssystemet til HiH')

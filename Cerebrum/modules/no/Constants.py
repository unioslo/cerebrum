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
                               _OUPerspectiveCode, \
                               _AccountCode, \
                               _PersonNameCode, \
                               _ContactInfoCode, \
                               _CountryCode

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

class ConstantsUniversityColleges(Constants.Constants):

    ## Source systems
    system_migrate = _AuthoritativeSystemCode('MIGRATE', 'Migrate from files')
    system_override = _AuthoritativeSystemCode('Override',
                                               'Override information fetched from proper authoritative systems')
    system_manual =  _AuthoritativeSystemCode('MANUELL',
                                              'Manually added information')

    ## Non-personal account codes
    account_test = _AccountCode('testbruker', 'Testkonto')
    account_kurs = _AccountCode('kursbruker', 'Kurskonto')
    account_studorg = _AccountCode('studorgbruker','Studentorganisasjonsbruker')
    account_felles  = _AccountCode('fellesbruker','Fellesbruker')
    account_system  = _AccountCode('systembruker', 'Systembruker') 

    ## SAP-spesifikke navnekonstanter
    name_middle = _PersonNameCode('MIDDLE', 'Mellomnavn')
    name_initials = _PersonNameCode('INITIALS', 'Initialer')

    ## SAP-spesifikke kommtypekonstater
    contact_phone_cellular = _ContactInfoCode("CELLPHONE",
                                              "Mobiltelefonnr")
    contact_phone_cellular_private = _ContactInfoCode(
                                       "PRIVCELLPHONE",
                                       "Privat mobiltefonnr")
    ## Landkonstanter for SAP
    country_no = _CountryCode("NO", "Norway", "47", "Norway")
    country_gb = _CountryCode("GB", "Great Britain", "44", "Great Britain")
    country_fi = _CountryCode("FI", "Finland", "358", "Finland")
    country_se = _CountryCode("SE", "Sweden", "46", "Sweden")
    country_us = _CountryCode("US", "USA", "1", "United states of America")
    country_nl = _CountryCode("NL", "The Netherlands", "31", "The Netherlands")
    country_de = _CountryCode("DE", "Germany", "49", "Germany")
    country_au = _CountryCode("AU", "Australia", "61", "Australia")
    country_dk = _CountryCode("DK", "Denmark", "45", "Denmark")
    country_it = _CountryCode("IT", "Italy", "39", "Italy")
    country_sg = _CountryCode("SG", "Singapore", "65", "Singapore")
    country_at = _CountryCode("AT", "Austria", "43", "Austria")


# arch-tag: 4ba57e9c-75bd-40b6-8d6c-1340312241bb

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
Address, Gender etc. type.
"""
from __future__ import unicode_literals

from Cerebrum import Constants
from Cerebrum.Constants import (
    _SpreadCode,
    _PersonAffiliationCode,
    _PersonAffStatusCode,
)
from Cerebrum.modules.EntityTrait import _EntityTraitCode
from Cerebrum.modules.PosixUser import _PosixShellCode
from Cerebrum.modules.ad2.Entity import ConstantsActiveDirectory
from Cerebrum.modules.ad2.Entity import _ADAttrCode
from Cerebrum.modules.bofhd.utils import _BofhdRequestOpCode
from Cerebrum.modules.no.Constants import (
    ConstantsUniversityColleges,
    ConstantsHigherEdu,
)


class Constants(Constants.Constants):

    # Affiliations for students
    affiliation_student = ConstantsHigherEdu.affiliation_student
    affiliation_status_student_tilbud = _PersonAffStatusCode(
        affiliation_student,
        'tilbud',
        'Student, tilbud')
    affiliation_status_student_privatist = _PersonAffStatusCode(
        affiliation_student,
        'privatist',
        'Student, privatist')

    # Affiliations for associated people
    affiliation_status_tilknyttet_timelonnet = _PersonAffStatusCode(
        ConstantsUniversityColleges.affiliation_tilknyttet,
        'timelonnet',
        'Personer registrert i SAP som timelønnet')

    # Affiliations for others
    affiliation_manuell = _PersonAffiliationCode(
        'MANUELL',
        'Tilknyttet HiOf uten å være registrert i et av de'
        ' autoritative kildesystemene')
    affiliation_status_manuell_ekstern = _PersonAffStatusCode(
        affiliation_manuell,
        'ekstern',
        'Eksternt tilknyttet person, når spesifikke kategorier ikke passer')
    affiliation_status_manuell_pensjonist = _PersonAffStatusCode(
        affiliation_manuell,
        'pensjonist',
        'Pensjonist ved HiOf, ikke registrert i SAP')
    affiliation_status_manuell_gjest = _PersonAffStatusCode(
        affiliation_manuell,
        'gjest',
        'Gjesteopphold ved HiOf')

    # Posix-shell definitions
    #
    # We override the default Cerebrum paths for shells, thus this
    # file should appear before PosixUser in cereconf.CLASS_CONSTANTS
    posix_shell_bash = _PosixShellCode('bash', '/bin/bash')
    posix_shell_tcsh = _PosixShellCode('tcsh', '/bin/tcsh')
    posix_shell_csh = _PosixShellCode('csh', '/bin/csh')
    posix_shell_sh = _PosixShellCode('sh', '/bin/sh')

    # Spread definitions - user related
    spread_nis_account = _SpreadCode(
        'account@nis',
        ConstantsUniversityColleges.entity_account,
        'Account in NIS')
    spread_email_account = _SpreadCode(
        'account@imap',
        Constants.Constants.entity_account,
        'Email account at HiOf')
    spread_ad_account = _SpreadCode(
        'account@ad',
        Constants.Constants.entity_account,
        'Account included in domain in Active Directory')
    spread_ad_account_fag = _SpreadCode(
        'account@ad_fag',
        Constants.Constants.entity_account,
        'Account included in domain FAG in Active Directory')
    spread_ad_account_adm = _SpreadCode(
        'account@ad_adm',
        Constants.Constants.entity_account,
        'Account included in domain ADM in Active Directory')
    spread_ad_account_stud = _SpreadCode(
        'account@ad_stud',
        Constants.Constants.entity_account,
        'Account included in domain STUD in Active Directory')

    # Spread definitions - group related
    spread_nis_fg = _SpreadCode(
        'fgroup@nis',
        ConstantsUniversityColleges.entity_group,
        'File group in NIS')
    spread_nis_ng = _SpreadCode(
        'netgroup@nis',
        ConstantsUniversityColleges.entity_group,
        'Net group in NIS')
    spread_nis_ans_account = _SpreadCode(
        'account@nisans',
        ConstantsUniversityColleges.entity_account,
        'Account in NIS')
    spread_nis_ans_fg = _SpreadCode(
        'fgroup@nisans',
        ConstantsUniversityColleges.entity_group,
        'File group in NIS')
    spread_nis_ans_ng = _SpreadCode(
        'netgroup@nisans',
        ConstantsUniversityColleges.entity_group,
        'Net group in NIS')
    spread_ad_group = _SpreadCode(
        'group@ad', Constants.Constants.entity_group,
        'Group included in domain in Active Directory')

    # Traits
    trait_ad_homedir = _EntityTraitCode(
        'ad_homedir',
        Constants.Constants.entity_account,
        "AD homedir for account")
    trait_ad_profile_path = _EntityTraitCode(
        'ad_profile_path',
        Constants.Constants.entity_account,
        "AD profile path for account")
    trait_ad_account_ou = _EntityTraitCode(
        'ad_account_ou',
        Constants.Constants.entity_account,
        "AD OU for account")

    trait_phone_exchange = _EntityTraitCode(
        'phone_exchange',
        Constants.Constants.entity_account,
        "ID of telephone exchange, PBX")

    trait_cf_group = _EntityTraitCode(
        'cf_group',
        Constants.Constants.entity_group,
        'Trait for tagging Fronter groups')

    # BofhdRequests constants
    bofh_ad_attrs_remove = _BofhdRequestOpCode(
        "br_ad_attr_rem",
        "Remove AD attributes for a user")


class HiOfConstantsActiveDirectory(ConstantsActiveDirectory):
    """Special AD-constants for HiOf"""

    ad_attribute_title = _ADAttrCode(
        'Title',
        'Title for an account in AD',
        False)

    ad_attribute_office = _ADAttrCode(
        'Office',
        'Office for an object in AD',
        False)

    ad_attribute_department = _ADAttrCode(
        'Department',
        'Department for an object in AD',
        False)

    ad_attribute_extensionattribute1 = _ADAttrCode(
        'extensionAttribute1',
        'extensionAttribute1 for an object in AD',
        False)

    ad_attribute_extensionattribute2 = _ADAttrCode(
        'extensionAttribute2',
        'extensionAttribute2 for an object in AD',
        False)

    ad_attribute_extensionattribute3 = _ADAttrCode(
        'extensionAttribute3',
        'extensionAttribute3 for an object in AD',
        False)

    ad_attribute_extensionattribute4 = _ADAttrCode(
        'extensionAttribute4',
        'extensionAttribute4 for an object in AD',
        False)

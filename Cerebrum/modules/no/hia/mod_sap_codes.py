# -*- coding: utf-8 -*-
#
# Copyright 2003-2019 University of Oslo, Norway
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
This file provides code values to be used with HiA's SAP extension to
Cerebrum -- mod_sap.

This file is meant for any extra codes needed by the institution, or other
descriptions of the same codes for whatever reason. Make sure to link to this
file after the general codes in cereconf.CLASS_CONSTANTS.
"""

from __future__ import unicode_literals

from Cerebrum import Constants
from Cerebrum.modules.no.Constants import SAPLonnsTittelKode


class SAPConstants(Constants.Constants):
    """
    This class embodies all constants that we need to address HR-related
    tables in HiA.
    """

    # ----[ SAPLonnsTittelKode ]----------------------------------------
    sap_0830_barnehageassistent_m_barnepleierutd = SAPLonnsTittelKode(
        "20000830",
        "0830 Barnehageassistent m/barnepleierutd",
        "ØVR"
    )

    sap_0834_avdelingsleder_fysio = SAPLonnsTittelKode(
        "20000834",
        "0834 Avdelingsleder/fysio",
        "ØVR"
    )

    sap_1061_assisterende_direktor_ = SAPLonnsTittelKode(
        "20001061",
        "1061 Assisterende direktør|",
        "ØVR"
    )

    sap_1138_unge_arbeidstakere_inntil_161_2_ar = SAPLonnsTittelKode(
        "20001138",
        "1138 Unge arbeidstakere inntil 161/2 år",
        "ØVR"
    )

    sap_1203_fagarbeider_m_fagbre = SAPLonnsTittelKode(
        "20001203",
        "1203 Fagarbeider m/fagbrev",
        "ØVR"
    )

    sap_9999_dummy_stillingskode = SAPLonnsTittelKode(
        "20009999",
        "9999 Tilknyttet UiA",
        "ØVR"
    )

    sap_0000_ekstern_stillingskode = SAPLonnsTittelKode(
        "00000000",
        "0000 Tilknyttet UiA",
        "ØVR"
    )

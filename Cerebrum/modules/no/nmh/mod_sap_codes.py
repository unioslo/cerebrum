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
This file provides code values to be used with NMH's SAP extension to
Cerebrum -- mod_sap.

This file is meant for any extra codes needed by the institution, or other
descriptions of the same codes for whatever reason. Make sure to link to this
file after the general codes in cereconf.CLASS_CONSTANTS.
"""

from __future__ import unicode_literals

from Cerebrum import Constants
from Cerebrum.modules.no.Constants import SAPLonnsTittelKode


class SAPConstants(Constants.Constants):
    """This class contains all constants we need to refer to SAP-originated
    HR-data at NMH."""

    # ----[ SAPLonnsTittelKode ]----------------------------------------
    sap_1007_hogskolelaerer_ovings = SAPLonnsTittelKode(
        "20001007",
        "1007 Høgskolelærer/øvings",
        "ØVR"
    )

    # FIXME: Er dette riktig da?
    sap_0000_ekstern_stillingskode = SAPLonnsTittelKode(
        "00000000",
        "0000 Inaktiv ansatt (diverse årsaker).",
        "ØVR"
    )

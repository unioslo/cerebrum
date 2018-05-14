# -*- coding: utf-8 -*-
#
# Copyright 2003 University of Oslo, Norway
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

    sap_1009_universitetslektor = SAPLonnsTittelKode(
        "20001009",
        "1009 Universitetslektor",
        "VIT"
    )

    sap_1010_amanuensis = SAPLonnsTittelKode(
        "20001010",
        "1010 Amanuensis",
        "VIT"
    )

    sap_1011_forsteamanuensis = SAPLonnsTittelKode(
        "20001011",
        "1011 Førsteamanuensis",
        "VIT"
    )
    
    sap_1013_professor = SAPLonnsTittelKode(
        "20001013",
        "1013 Professor",
        "VIT"
    )

    sap_1017_stipendiat = SAPLonnsTittelKode(
        "20001017",
        "1017 Stipendiat",
        "VIT"
    )

    sap_1062_direktor = SAPLonnsTittelKode(
        "20001062",
        "1062 Direktør",
        "ØVR"
    )

    sap_1065_konsulent = SAPLonnsTittelKode(
        "20001065",
        "1065 Konsulent",
        "ØVR"
    )

    sap_1068_fullmektig = SAPLonnsTittelKode(
        "20001068",
        "1068 Fullmektig",
        "ØVR"
    )

    sap_1070_sekretaer = SAPLonnsTittelKode(
        "20001070",
        "1070 Sekretær",
        "ØVR"
    )

    sap_1072_arkivleder = SAPLonnsTittelKode(
        "20001072",
        "1072 Arkivleder",
        "ØVR"
    )


    sap_1077_hovedbibliotekar = SAPLonnsTittelKode(
        "20001077",
        "1077 Hovedbibliotekar",
        "ØVR"
    )

    sap_1085_avdelingsingenior = SAPLonnsTittelKode(
        "20001085",
        "1085 Avdelingsingeniør",
        "ØVR"
    )

    sap_1087_overingenior = SAPLonnsTittelKode(
        "20001087",
        "1087 Overingeniør",
        "ØVR"
    )
    
    sap_1091_tekniker = SAPLonnsTittelKode(
        "20001091",
        "1091 Tekniker",
        "ØVR"
    )

    sap_1113_prosjektleder = SAPLonnsTittelKode(
        "20001113",
        "1113 Prosjektleder",
        "ØVR"
    )

    sap_1136_driftstekniker = SAPLonnsTittelKode(
        "20001136",
        "1136 Driftstekniker",
        "ØVR"
    )        

    sap_1137_driftsleder = SAPLonnsTittelKode(
        "20001137",
        "1137 Driftsleder",
        "ØVR"
    )

    sap_1181_senioringenior = SAPLonnsTittelKode(
        "20001181",
        "1181 Senioringeniør",
        "ØVR"
    )

    sap_1198_forstelektor = SAPLonnsTittelKode(
        "20001198",
        "1198 Førstelektor",
        "VIT"
    )


    sap_1211_seksjonssjef = SAPLonnsTittelKode(
        "20001211",
        "1211 Seksjonssjef",
        "ØVR"
    )

    sap_1352_post_doktor = SAPLonnsTittelKode(
        "20001352",
        "1352 Post doktor",
        "VIT"
    )

    sap_1362_laerling = SAPLonnsTittelKode(
        "20001362",
        "1362 Lærling",
        "ØVR"
    )

    sap_1364_seniorradgiver = SAPLonnsTittelKode(
        "20001364",
        "1364 Seniorrådgiver",
        "ØVR"
    )
    
    sap_1407_avdelingsleder = SAPLonnsTittelKode(
        "20001407",
        "1407 Avdelingsleder",
        "ØVR"
    )

    sap_1408_forstekonsulent = SAPLonnsTittelKode(
        "20001408",
        "1408 Førstekonsulent",
        "ØVR"
    )

    sap_1409_sekretaer = SAPLonnsTittelKode(
        "20001409",
        "1409 Sekretær",
        "ØVR"
    )

    sap_1410_bibliotekar = SAPLonnsTittelKode(
        "20001410",
        "1410 Bibliotekar",
        "ØVR"
    )

    sap_1434_radgiver = SAPLonnsTittelKode(
        "20001434",
        "1434 Rådgiver",
        "ØVR"
    )

    sap_1515_bibliotekar = SAPLonnsTittelKode(
        "20001515",
        "1515 Bibliotekar",
        "ØVR"
    )

    sap_1532_dosent = SAPLonnsTittelKode(
        "20001532",
        "1532 Dosent",
        "VIT"
    )

    sap_1108_forsker = SAPLonnsTittelKode(
        "20001108",
        "1108 Forsker",
        "VIT"
    )

    sap_1109_forsker = SAPLonnsTittelKode(
        "20001109",
        "1109 Forsker",
        "VIT"
    )

    # NMH er blitt informert om at 9999 er veldig spesiell.
    sap_9999_dummy_stillingskode = SAPLonnsTittelKode(
        "20009999",
        "9999 Dummy stillingskode",
        "ØVR"
    )

    # FIXME: Er dette riktig da?
    sap_0000_ekstern_stillingskode = SAPLonnsTittelKode(
        "00000000",
        "0000 Inaktiv ansatt (diverse årsaker).",
        "ØVR"
    )

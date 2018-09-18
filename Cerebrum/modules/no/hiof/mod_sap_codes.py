# -*- coding: utf-8 -*-
#
# Copyright 2007-2018 University of Oslo, Norway
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
This file provides code values to be used with HiØf's SAP extension to
Cerebrum -- mod_sap.
"""
from __future__ import unicode_literals

from Cerebrum import Constants
from Cerebrum.modules.no.Constants import SAPLonnsTittelKode


class SAPConstants(Constants.Constants):
    """
    This class embodies all constants that we need to address HR-related
    tables in HiØ.
    """

    # ----[ SAPLonnsTittelKode ]----------------------------------
    sap_1004_rektor = SAPLonnsTittelKode(
        "20001004",
        "1004 Rektor",
        "ØVR"
    )

    sap_1006_edb_sjef = SAPLonnsTittelKode(
        "20001006",
        "1006 EDB-sjef",
        "ØVR"
    )

    sap_1007_hogskolelaerer_ovings = SAPLonnsTittelKode(
        "20001007",
        "1007 Høgskolelærer/øvings",
        "VIT"
    )

    sap_1008_hogskolelektor = SAPLonnsTittelKode(
        "20001008",
        "1008 Høgskolelektor",
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

    sap_1012_hogskoledosent = SAPLonnsTittelKode(
        "20001012",
        "1012 Høgskoledosent",
        "ØVR"
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

    sap_1018_vitenskapelig_assistent = SAPLonnsTittelKode(
        "20001018",
        "1018 Vitenskapelig assistent",
        "VIT"
    )

    sap_1019_vitenskapelig_assist = SAPLonnsTittelKode(
        "20001019",
        "1019 Vitenskapelig assist",
        "VIT"
    )

    sap_1020_vitenskapelig_assist = SAPLonnsTittelKode(
        "20001020",
        "1020 Vitenskapelig assist",
        "VIT"
    )

    sap_1054_kontorsjef = SAPLonnsTittelKode(
        "20001054",
        "1054 Kontorsjef",
        "ØVR"
    )

    sap_1058_administrasjonssjef = SAPLonnsTittelKode(
        "20001058",
        "1058 Administrasjonssjef",
        "ØVR"
    )

    sap_1059_underdirektor = SAPLonnsTittelKode(
        "20001059",
        "1059 Underdirektør",
        "ØVR"
    )

    sap_1060_avdelingsdirektor = SAPLonnsTittelKode(
        "20001060",
        "1060 Avdelingsdirektør",
        "ØVR"
    )

    sap_1062_direktor = SAPLonnsTittelKode(
        "20001062",
        "1062 Direktør",
        "ØVR"
    )

    sap_1063_forstesekretaer = SAPLonnsTittelKode(
        "20001063",
        "1063 Førstesekretær",
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

    sap_1069_forstefullmektig = SAPLonnsTittelKode(
        "20001069",
        "1069 Førstefullmektig",
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

    sap_1078_betjent = SAPLonnsTittelKode(
        "20001078",
        "1078 Betjent",
        "ØVR"
    )

    sap_1083_ingenior = SAPLonnsTittelKode(
        "20001083",
        "1083 Ingeniør",
        "ØVR"
    )

    sap_1084_avdelingsingenior = SAPLonnsTittelKode(
        "20001084",
        "1084 Avdelingsingeniør",
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

    sap_1088_sjefsingenior = SAPLonnsTittelKode(
        "20001088",
        "1088 Sjefsingeniør",
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

    sap_1129_renholdsbetjent = SAPLonnsTittelKode(
        "20001129",
        "1129 Renholdsbetjent",
        "ØVR"
    )

    sap_1130_renholder = SAPLonnsTittelKode(
        "20001130",
        "1130 Renholder",
        "ØVR"
    )

    sap_1132_renholdsleder = SAPLonnsTittelKode(
        "20001132",
        "1132 Renholdsleder",
        "ØVR"
    )

    sap_1136_driftstekniker = SAPLonnsTittelKode(
        "20001136",
        "1136 Driftstekniker",
        "ØVR"
    )

    sap_1181_senioringenior = SAPLonnsTittelKode(
        "20001181",
        "1181 Senioringeniør",
        "ØVR"
    )

    sap_1183_forsker = SAPLonnsTittelKode(
        "20001183",
        "1183 Forsker",
        "VIT"
    )

    sap_1198_forstelektor = SAPLonnsTittelKode(
        "20001198",
        "1198 Førstelektor",
        "VIT"
    )

    sap_1199_universitetsbibliote = SAPLonnsTittelKode(
        "20001199",
        "1199 Universitetsbibliotekar",
        "VIT"
    )

    sap_1203_fagarbeider_m_fagbre = SAPLonnsTittelKode(
        "20001203",
        "1203 Fagarbeider med fagbrev",
        "ØVR"
    )

    sap_1213_bibliotekar = SAPLonnsTittelKode(
        "20001213",
        "1213 Bibliotekar",
        "ØVR"
    )

    sap_1216_driftsoperator = SAPLonnsTittelKode(
        "20001216",
        "1216 Driftsoperatør",
        "ØVR"
    )

    sap_1275_ingenior = SAPLonnsTittelKode(
        "20001275",
        "1275 Ingeniør",
        "ØVR"
    )

    sap_1362_laerling = SAPLonnsTittelKode(
        "20001362",
        "1362 Lærling",
        "ØVR"
    )

    sap_1363_seniorkonsulent = SAPLonnsTittelKode(
        "20001363",
        "1363 Seniorkonsulent",
        "ØVR"
    )

    sap_1364_seniorradgiver = SAPLonnsTittelKode(
        "20001364",
        "1364 Seniorrådgiver",
        "ØVR"
    )

    sap_1378_stipendiat = SAPLonnsTittelKode(
        "20001378",
        "1378 Stipendiat",
        "VIT"
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

    sap_1410_bibliotekar = SAPLonnsTittelKode(
        "20001410",
        "1410 Bibliotekar",
        "ØVR"
    )

    sap_1411_avdelingsingenior = SAPLonnsTittelKode(
        "20001411",
        "1411 Avdelingsingeniør",
        "ØVR"
    )

    sap_1423_undervp = SAPLonnsTittelKode(
        "20001423",
        "1423 Underv.p u/godkj utd",
        "ØVR"
    )

    sap_1434_radgiver = SAPLonnsTittelKode(
        "20001434",
        "1434 Rådgiver",
        "ØVR"
    )

    sap_1473_studieleder = SAPLonnsTittelKode(
        "20001473",
        "1473 Studieleder",
        "ØVR"
    )

    sap_1474_dekan = SAPLonnsTittelKode(
        "20001474",
        "1474 Dekan",
        "ØVR"
    )

    sap_1475_instituttleder = SAPLonnsTittelKode(
        "20001475",
        "1475 Instituttleder",
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

    sap_9999_dummy_stillingskode = SAPLonnsTittelKode(
        "20009999",
        "9999 Dummy stillingskode",
        "ØVR"
    )

    sap_0000_ekstern_stillingskode = SAPLonnsTittelKode(
        "00000000",
        "0000 Ekstern tilsatt, ikke lønnet av HiØf",
        "ØVR"
    )

    sap_0214_rektor = SAPLonnsTittelKode(
        "20000214",
        "0214 Rektor",
        "ØVR"
    )

    sap_1409_sekretaer = SAPLonnsTittelKode(
        "20001409",
        "1409 Sekretær",
        "ØVR"
    )

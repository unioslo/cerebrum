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
This file provides code values to be used with HiA's SAP extension to
Cerebrum -- mod_sap.
"""

from __future__ import unicode_literals

from Cerebrum import Constants
from Cerebrum.modules.no.Constants import SAPLonnsTittelKode


class SAPConstants(Constants.Constants):
    """
    This class embodies all constants that we need to address HR-related
    tables in NIH.
    """

    # ----[ SAPLonnsTittelKode ]----------------------------------------
    sap_0001_statsradens_kontorsekretaer = SAPLonnsTittelKode(
        "20000001",
        "0001 Statsrådens kontorsekretær",
        "ØVR"
    )

    sap_0005_planlegger = SAPLonnsTittelKode(
        "20000005",
        "0005 Planlegger",
        "ØVR"
    )

    sap_0007_opplaeringsleder = SAPLonnsTittelKode(
        "20000007",
        "0007 Opplæringsleder",
        "ØVR"
    )

    sap_0008_byrasjef = SAPLonnsTittelKode(
        "20000008",
        "0008 Byråsjef",
        "ØVR"
    )

    sap_0012_sjefaktuar = SAPLonnsTittelKode(
        "20000012",
        "0012 Sjefaktuar",
        "ØVR"
    )

    sap_0013_spesiallege = SAPLonnsTittelKode(
        "20000013",
        "0013 Spesiallege",
        "ØVR"
    )

    sap_0024_avdelingssjef = SAPLonnsTittelKode(
        "20000024",
        "0024 Avdelingssjef",
        "ØVR"
    )

    sap_0027_fylkesskattesjef = SAPLonnsTittelKode(
        "20000027",
        "0027 Fylkesskattesjef",
        "ØVR"
    )

    sap_0030_skatterevisor = SAPLonnsTittelKode(
        "20000030",
        "0030 Skatterevisor",
        "ØVR"
    )

    sap_0034_ligningssekretaer = SAPLonnsTittelKode(
        "20000034",
        "0034 Ligningssekretær",
        "ØVR"
    )

    sap_0035_ligningssekretaer = SAPLonnsTittelKode(
        "20000035",
        "0035 Ligningssekretær",
        "ØVR"
    )

    sap_0037_ligningsrevisor = SAPLonnsTittelKode(
        "20000037",
        "0037 Ligningsrevisor",
        "ØVR"
    )

    sap_0038_kontrollsjef = SAPLonnsTittelKode(
        "20000038",
        "0038 Kontrollsjef",
        "ØVR"
    )

    sap_0039_registersjef = SAPLonnsTittelKode(
        "20000039",
        "0039 Registersjef",
        "ØVR"
    )

    sap_0040_ligningssjef = SAPLonnsTittelKode(
        "20000040",
        "0040 Ligningssjef",
        "ØVR"
    )

    sap_0042_skattefogd = SAPLonnsTittelKode(
        "20000042",
        "0042 Skattefogd",
        "ØVR"
    )

    sap_0257_advokatfullmektig = SAPLonnsTittelKode(
        "20000257",
        "0257 Advokatfullmektig",
        "ØVR"
    )

    sap_0258_advokat = SAPLonnsTittelKode(
        "20000258",
        "0258 Advokat",
        "ØVR"
    )

    sap_0400_driftsleder = SAPLonnsTittelKode(
        "20000400",
        "0400 Driftsleder",
        "ØVR"
    )

    sap_0790_bedriftssykepleier = SAPLonnsTittelKode(
        "20000790",
        "0790 Bedriftssykepleier",
        "ØVR"
    )

    sap_0791_bedriftslege = SAPLonnsTittelKode(
        "20000791",
        "0791 Bedriftslege",
        "ØVR"
    )

    sap_0792_bedriftsoverlege = SAPLonnsTittelKode(
        "20000792",
        "0792 Bedriftsoverlege",
        "ØVR"
    )

    sap_0829_barnehageassistent = SAPLonnsTittelKode(
        "20000829",
        "0829 Barnehageassistent",
        "ØVR"
    )

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

    sap_0835_instruktor_fysioterapeut = SAPLonnsTittelKode(
        "20000835",
        "0835 Instruktør/fysioterapeut",
        "ØVR"
    )

    sap_0881_forstekansilist = SAPLonnsTittelKode(
        "20000881",
        "0881 Førstekansilist",
        "ØVR"
    )

    sap_0882_ambassaderad = SAPLonnsTittelKode(
        "20000882",
        "0882 Ambassaderåd",
        "ØVR"
    )

    sap_0883_spesialrad = SAPLonnsTittelKode(
        "20000883",
        "0883 Spesialråd",
        "ØVR"
    )

    sap_0884_konsul = SAPLonnsTittelKode(
        "20000884",
        "0884 Konsul",
        "ØVR"
    )

    sap_0885_ministerrad = SAPLonnsTittelKode(
        "20000885",
        "0885 Ministerråd",
        "ØVR"
    )

    sap_0886_generalkonsul = SAPLonnsTittelKode(
        "20000886",
        "0886 Generalkonsul",
        "ØVR"
    )

    sap_0887_sendemann = SAPLonnsTittelKode(
        "20000887",
        "0887 Sendemann",
        "ØVR"
    )

    sap_0947_forskolelaerer = SAPLonnsTittelKode(
        "20000947",
        "0947 Førskolelærer",
        "ØVR"
    )

    sap_0948_styrer = SAPLonnsTittelKode(
        "20000948",
        "0948 Styrer",
        "ØVR"
    )

    sap_1003_avdelingsleder = SAPLonnsTittelKode(
        "20001003",
        "1003 Avdelingsleder",
        "ØVR"
    )

    sap_1004_rektor = SAPLonnsTittelKode(
        "20001004",
        "1004 Rektor",
        "ØVR"
    )

    sap_1005_inspektor = SAPLonnsTittelKode(
        "20001005",
        "1005 Inspektør",
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
        "ØVR"
    )

    sap_1008_hogskolelektor = SAPLonnsTittelKode(
        "20001008",
        "1008 Høgskolelektor",
        "VIT"
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

    sap_1055_personalsjef = SAPLonnsTittelKode(
        "20001055",
        "1055 Personalsjef",
        "ØVR"
    )

    sap_1056_okonomisjef = SAPLonnsTittelKode(
        "20001056",
        "1056 Økonomisjef",
        "ØVR"
    )

    sap_1057_informasjonssjef = SAPLonnsTittelKode(
        "20001057",
        "1057 Informasjonssjef",
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

    sap_1061_assisterende_direktor_ = SAPLonnsTittelKode(
        "20001061",
        "1061 Assisterende direktør|",
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

    sap_1064_konsulent = SAPLonnsTittelKode(
        "20001064",
        "1064 Konsulent",
        "ØVR"
    )

    sap_1065_konsulent = SAPLonnsTittelKode(
        "20001065",
        "1065 Konsulent",
        "ØVR"
    )

    sap_1067_forstekonsulent = SAPLonnsTittelKode(
        "20001067",
        "1067 Førstekonsulent",
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

    sap_1071_kontorleder = SAPLonnsTittelKode(
        "20001071",
        "1071 Kontorleder",
        "ØVR"
    )

    sap_1072_arkivleder = SAPLonnsTittelKode(
        "20001072",
        "1072 Arkivleder",
        "ØVR"
    )

    sap_1073_bibliotekfullmektig = SAPLonnsTittelKode(
        "20001073",
        "1073 Bibliotekfullmektig",
        "ØVR"
    )

    sap_1074_bibliotekar = SAPLonnsTittelKode(
        "20001074",
        "1074 Bibliotekar",
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

    sap_1079_forstebetjent = SAPLonnsTittelKode(
        "20001079",
        "1079 Førstebetjent",
        "ØVR"
    )

    sap_1080_sjafor = SAPLonnsTittelKode(
        "20001080",
        "1080 Sjåfør",
        "ØVR"
    )

    sap_1081_sjafor = SAPLonnsTittelKode(
        "20001081",
        "1081 Sjåfør",
        "ØVR"
    )

    sap_1082_ingenior = SAPLonnsTittelKode(
        "20001082",
        "1082 Ingeniør",
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

    sap_1089_teknisk_assistent = SAPLonnsTittelKode(
        "20001089",
        "1089 Teknisk assistent",
        "ØVR"
    )

    sap_1090_tekniker = SAPLonnsTittelKode(
        "20001090",
        "1090 Tekniker",
        "ØVR"
    )

    sap_1091_tekniker = SAPLonnsTittelKode(
        "20001091",
        "1091 Tekniker",
        "ØVR"
    )

    sap_1092_arkitekt = SAPLonnsTittelKode(
        "20001092",
        "1092 Arkitekt",
        "ØVR"
    )

    sap_1093_avdelingsarkitekt = SAPLonnsTittelKode(
        "20001093",
        "1093 Avdelingsarkitekt",
        "ØVR"
    )

    sap_1094_overarkitekt = SAPLonnsTittelKode(
        "20001094",
        "1094 Overarkitekt",
        "ØVR"
    )

    sap_1095_sjefsarkitekt = SAPLonnsTittelKode(
        "20001095",
        "1095 Sjefsarkitekt",
        "ØVR"
    )

    sap_1096_laboratorieassistent = SAPLonnsTittelKode(
        "20001096",
        "1096 Laboratorieassistent",
        "ØVR"
    )

    sap_1097_laborant = SAPLonnsTittelKode(
        "20001097",
        "1097 Laborant",
        "ØVR"
    )

    sap_1098_laborantleder = SAPLonnsTittelKode(
        "20001098",
        "1098 Laborantleder",
        "ØVR"
    )

    sap_1099_tegneassistent = SAPLonnsTittelKode(
        "20001099",
        "1099 Tegneassistent",
        "ØVR"
    )

    sap_1101_tegneleder = SAPLonnsTittelKode(
        "20001101",
        "1101 Tegneleder",
        "ØVR"
    )

    sap_1102_fotograf = SAPLonnsTittelKode(
        "20001102",
        "1102 Fotograf",
        "ØVR"
    )

    sap_1103_forstefotograf = SAPLonnsTittelKode(
        "20001103",
        "1103 Førstefotograf",
        "ØVR"
    )

    sap_1104_fotoleder = SAPLonnsTittelKode(
        "20001104",
        "1104 Fotoleder",
        "ØVR"
    )

    sap_1105_preparantassistent = SAPLonnsTittelKode(
        "20001105",
        "1105 Preparantassistent",
        "ØVR"
    )

    sap_1106_preparant = SAPLonnsTittelKode(
        "20001106",
        "1106 Preparant",
        "ØVR"
    )

    sap_1107_preparantleder = SAPLonnsTittelKode(
        "20001107",
        "1107 Preparantleder",
        "ØVR"
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

    sap_1110_forsker = SAPLonnsTittelKode(
        "20001110",
        "1110 Forsker",
        "VIT"
    )

    sap_1111_forskningssjef = SAPLonnsTittelKode(
        "20001111",
        "1111 Forskningssjef",
        "VIT"
    )

    sap_1113_prosjektleder = SAPLonnsTittelKode(
        "20001113",
        "1113 Prosjektleder",
        "ØVR"
    )

    sap_1114_utredningsleder = SAPLonnsTittelKode(
        "20001114",
        "1114 Utredningsleder",
        "ØVR"
    )

    sap_1115_hjelpearbeider = SAPLonnsTittelKode(
        "20001115",
        "1115 Hjelpearbeider",
        "ØVR"
    )

    sap_1116_spesialarbeider = SAPLonnsTittelKode(
        "20001116",
        "1116 Spesialarbeider",
        "ØVR"
    )

    sap_1117_fagarbeider = SAPLonnsTittelKode(
        "20001117",
        "1117 Fagarbeider",
        "ØVR"
    )

    sap_1118_arbeidsleder = SAPLonnsTittelKode(
        "20001118",
        "1118 Arbeidsleder",
        "ØVR"
    )

    sap_1119_formann = SAPLonnsTittelKode(
        "20001119",
        "1119 Formann",
        "ØVR"
    )

    sap_1120_mester = SAPLonnsTittelKode(
        "20001120",
        "1120 Mester",
        "ØVR"
    )

    sap_1121_kokk = SAPLonnsTittelKode(
        "20001121",
        "1121 Kokk",
        "ØVR"
    )

    sap_1122_forstekokk = SAPLonnsTittelKode(
        "20001122",
        "1122 Førstekokk",
        "ØVR"
    )

    sap_1123_assisterende_kjokkensjef = SAPLonnsTittelKode(
        "20001123",
        "1123 Assisterende kjøkkensjef",
        "ØVR"
    )

    sap_1124_kjokkensjef = SAPLonnsTittelKode(
        "20001124",
        "1124 Kjøkkensjef",
        "ØVR"
    )

    sap_1125_husholdningsassisten = SAPLonnsTittelKode(
        "20001125",
        "1125 Husholdningsassisten",
        "ØVR"
    )

    sap_1126_husholdningsbestyrer = SAPLonnsTittelKode(
        "20001126",
        "1126 Husholdningsbestyrer",
        "ØVR"
    )

    sap_1127_husholdsleder = SAPLonnsTittelKode(
        "20001127",
        "1127 Husholdsleder",
        "ØVR"
    )

    sap_1128_husokonom = SAPLonnsTittelKode(
        "20001128",
        "1128 Husøkonom",
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

    sap_1131_toyforvalter = SAPLonnsTittelKode(
        "20001131",
        "1131 Tøyforvalter",
        "ØVR"
    )

    sap_1132_renholdsleder = SAPLonnsTittelKode(
        "20001132",
        "1132 Renholdsleder",
        "ØVR"
    )

    sap_1133_sekretaer_kurator = SAPLonnsTittelKode(
        "20001133",
        "1133 Sekretær/Kurator",
        "ØVR"
    )

    sap_1134_sekretaer_kurator = SAPLonnsTittelKode(
        "20001134",
        "1134 Sekretær/Kurator",
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

    sap_1138_unge_arbeidstakere_inntil_161_2_ar = SAPLonnsTittelKode(
        "20001138",
        "1138 Unge arbeidstakere inntil 161/2 år",
        "ØVR"
    )

    sap_1152_inspektor_i_kriminalomsorg = SAPLonnsTittelKode(
        "20001152",
        "1152 Inspektør i kriminalomsorg",
        "ØVR"
    )

    sap_1173_klinisk_sosionom = SAPLonnsTittelKode(
        "20001173",
        "1173 Klinisk sosionom",
        "ØVR"
    )

    sap_1178_avd_bibliotekar = SAPLonnsTittelKode(
        "20001178",
        "1178 Avd. bibliotekar",
        "ØVR"
    )

    sap_1180_sjafor = SAPLonnsTittelKode(
        "20001180",
        "1180 Sjåfør",
        "ØVR"
    )

    sap_1181_senioringenior = SAPLonnsTittelKode(
        "20001181",
        "1181 Senioringeniør",
        "ØVR"
    )

    sap_1182_seniorarkitekt = SAPLonnsTittelKode(
        "20001182",
        "1182 Seniorarkitekt",
        "ØVR"
    )

    sap_1183_forsker = SAPLonnsTittelKode(
        "20001183",
        "1183 Forsker",
        "VIT"
    )

    sap_1184_kokk = SAPLonnsTittelKode(
        "20001184",
        "1184 Kokk",
        "ØVR"
    )

    sap_1185_spesialutdannet_sosionom = SAPLonnsTittelKode(
        "20001185",
        "1185 Spesialutdannet sosionom",
        "ØVR"
    )

    sap_1197_studiesjef = SAPLonnsTittelKode(
        "20001197",
        "1197 Studiesjef",
        "ØVR"
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
        "1203 Fagarbeider m/fagbre",
        "ØVR"
    )

    sap_1206_undervisn_leder = SAPLonnsTittelKode(
        "20001206",
        "1206 Undervisn.leder",
        "ØVR"
    )

    sap_1211_seksjonssjef = SAPLonnsTittelKode(
        "20001211",
        "1211 Seksjonssjef",
        "ØVR"
    )

    sap_1213_bibliotekar = SAPLonnsTittelKode(
        "20001213",
        "1213 Bibliotekar",
        "ØVR"
    )

    sap_1214_tegner = SAPLonnsTittelKode(
        "20001214",
        "1214 Tegner",
        "ØVR"
    )

    sap_1215_sikkerhetsbetjent = SAPLonnsTittelKode(
        "20001215",
        "1215 Sikkerhetsbetjent",
        "ØVR"
    )

    sap_1216_driftsoperator = SAPLonnsTittelKode(
        "20001216",
        "1216 Driftsoperatør",
        "ØVR"
    )

    sap_1217_underdirektor = SAPLonnsTittelKode(
        "20001217",
        "1217 Underdirektør",
        "ØVR"
    )

    sap_1218_avdelingsdirektor = SAPLonnsTittelKode(
        "20001218",
        "1218 Avdelingsdirektør",
        "ØVR"
    )

    sap_1220_spesialradgiver = SAPLonnsTittelKode(
        "20001220",
        "1220 Spesialrådgiver",
        "ØVR"
    )

    sap_1221_lovradgiver_jd = SAPLonnsTittelKode(
        "20001221",
        "1221 Lovrådgiver JD",
        "ØVR"
    )

    sap_1222_lovradgiver_fin = SAPLonnsTittelKode(
        "20001222",
        "1222 Lovrådgiver FIN",
        "ØVR"
    )

    sap_1223_skatterevisor = SAPLonnsTittelKode(
        "20001223",
        "1223 Skatterevisor",
        "ØVR"
    )

    sap_1224_spesialrevisor = SAPLonnsTittelKode(
        "20001224",
        "1224 Spesialrevisor",
        "ØVR"
    )

    sap_1257_observator_i = SAPLonnsTittelKode(
        "20001257",
        "1257 Observatør I",
        "ØVR"
    )

    sap_1258_observator_ii = SAPLonnsTittelKode(
        "20001258",
        "1258 Observatør II",
        "ØVR"
    )

    sap_1275_ingenior = SAPLonnsTittelKode(
        "20001275",
        "1275 Ingeniør",
        "ØVR"
    )

    sap_1278_ass_avdelingssjef = SAPLonnsTittelKode(
        "20001278",
        "1278 Ass. avdelingssjef",
        "ØVR"
    )

    sap_1282_bedriftsfysioterapeut = SAPLonnsTittelKode(
        "20001282",
        "1282 Bedriftsfysioterapeut",
        "ØVR"
    )

    sap_1305_sendelagsleder = SAPLonnsTittelKode(
        "20001305",
        "1305 Sendelagsleder",
        "ØVR"
    )

    sap_1306_nestleder_sendelag = SAPLonnsTittelKode(
        "20001306",
        "1306 Nestleder sendelag",
        "ØVR"
    )

    sap_1307_pedagogisk_leder = SAPLonnsTittelKode(
        "20001307",
        "1307 Pedagogisk leder",
        "ØVR"
    )

    sap_1309_avdelingsdirektor = SAPLonnsTittelKode(
        "20001309",
        "1309 Avdelingsdirektør",
        "ØVR"
    )

    sap_1310_assisterende_direktor = SAPLonnsTittelKode(
        "20001310",
        "1310 Assisterende direktør",
        "ØVR"
    )

    sap_1311_direktor = SAPLonnsTittelKode(
        "20001311",
        "1311 Direktør",
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

    sap_1365_informasjonssjef = SAPLonnsTittelKode(
        "20001365",
        "1365 Informasjonssjef",
        "ØVR"
    )

    sap_1378_stipendiat = SAPLonnsTittelKode(
        "20001378",
        "1378 Stipendiat",
        "VIT"
    )

    sap_1386_sjafor = SAPLonnsTittelKode(
        "20001386",
        "1386 Sjåfør",
        "ØVR"
    )

    sap_1387_kontor_teknisk_personale = SAPLonnsTittelKode(
        "20001387",
        "1387 Kontor/teknisk personale",
        "ØVR"
    )

    sap_1388_stabsjef = SAPLonnsTittelKode(
        "20001388",
        "1388 Stabsjef",
        "ØVR"
    )

    sap_1389_sjafor_i_regjeringens_biltjeneste = SAPLonnsTittelKode(
        "20001389",
        "1389 Sjåfør i regjeringens biltjeneste",
        "ØVR"
    )

    sap_1396_attache = SAPLonnsTittelKode(
        "20001396",
        "1396 Attaché",
        "ØVR"
    )

    sap_1399_internasjonal_radgiver = SAPLonnsTittelKode(
        "20001399",
        "1399 Internasjonal rådgiver",
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

    sap_1411_avdelingsingenior = SAPLonnsTittelKode(
        "20001411",
        "1411 Avdelingsingeniør",
        "ØVR"
    )

    sap_1412_ligningskonsulent = SAPLonnsTittelKode(
        "20001412",
        "1412 Ligningskonsulent",
        "ØVR"
    )

    sap_1413_skattejurist = SAPLonnsTittelKode(
        "20001413",
        "1413 Skattejurist",
        "ØVR"
    )

    sap_1429_aspirant = SAPLonnsTittelKode(
        "20001429",
        "1429 Aspirant",
        "ØVR"
    )

    sap_1433_seniorsekretaer = SAPLonnsTittelKode(
        "20001433",
        "1433 Seniorsekretær",
        "ØVR"
    )

    sap_1434_radgiver = SAPLonnsTittelKode(
        "20001434",
        "1434 Rådgiver",
        "ØVR"
    )

    sap_1435_inspektor_for_utenrikstjenesten = SAPLonnsTittelKode(
        "20001435",
        "1435 Inspektør for utenrikstjenesten",
        "ØVR"
    )

    sap_1436_radgiver = SAPLonnsTittelKode(
        "20001436",
        "1436 Rådgiver",
        "ØVR"
    )

    sap_1446_laerekandidat = SAPLonnsTittelKode(
        "20001446",
        "1446 Lærekandidat",
        "ØVR"
    )

    sap_1447_betjent = SAPLonnsTittelKode(
        "20001447",
        "1447 Betjent",
        "ØVR"
    )

    sap_1448_seniorradgiver = SAPLonnsTittelKode(
        "20001448",
        "1448 Seniorrådgiver",
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

    sap_9105_departementsrad_utenriksrad_ = SAPLonnsTittelKode(
        "20009105",
        "9105 Departementsråd (utenriksråd)",
        "ØVR"
    )

    sap_9106_direktor = SAPLonnsTittelKode(
        "20009106",
        "9106 Direktør",
        "ØVR"
    )

    sap_9125_skattedirektor = SAPLonnsTittelKode(
        "20009125",
        "9125 Skattedirektør",
        "ØVR"
    )

    sap_9146_ekspedisjonssjef = SAPLonnsTittelKode(
        "20009146",
        "9146 Ekspedisjonssjef",
        "ØVR"
    )

    sap_9162_sendemann = SAPLonnsTittelKode(
        "20009162",
        "9162 Sendemann",
        "ØVR"
    )

    sap_9223_ass_departementsrad_utenriksrad = SAPLonnsTittelKode(
        "20009223",
        "9223 Ass.departementsråd / utenriksråd",
        "ØVR"
    )

    sap_9999_dummy_stillingskode = SAPLonnsTittelKode(
        "20009999",
        "9999 Dummy stillingskode",
        "ØVR"
    )

    sap_0000_ekstern_stillingskode = SAPLonnsTittelKode(
        "00000000",
        "0000 Ekstern tilsatt",
        "ØVR"
    )


#! /usr/bin/env python2.2
# -*- coding: iso8859-1 -*-
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
This file provides code values to be used with UiO's HR extension to
Cerebrum -- mod_lt.
"""

from Cerebrum import Constants





class StillingsKode(Constants._CerebrumCode):
    _lookup_table = "[:table schema=cerebrum name=lt_stillingskode]"
    _lookup_category_column = "hovedkategori"
    _lookup_title_column = "tittel"

    # FIXME: _CerebrumCode-ctorer må takle å initiere seg selv fra kun
    # en numerisk 'code' (ved å hente resten fra databasen).
    def __init__(self, code, description=None, hovedkategori=None, tittel=None):
        super(StillingsKode, self).__init__(code, description)
        self.hovedkategori = hovedkategori
        self.tittel = tittel
    # end __init__

    def insert(self):
        self.sql.execute("""
          INSERT INTO %(code_table)s
            (%(code_col)s, %(str_col)s, %(desc_col)s, hovedkategori, tittel)
          VALUES
            (%(code_seq)s, :str, :desc, :hovedkategori, :tittel) """ % {
              "code_table" : self._lookup_table,
              "code_col"   : self._lookup_code_column,
              "str_col"    : self._lookup_str_column,
              "desc_col"   : self._lookup_desc_column,
              "code_seq"   : self._code_sequence
              },
              { 'str'           : self.str,
                'desc'          : self._desc,
                'hovedkategori' : self.hovedkategori,
                'tittel'        : self.tittel
              })
    # end insert
# end StillingsKode





class GjestetypeKode(Constants._CerebrumCode):
    _lookup_table = "[:table schema=cerebrum name=lt_gjestetypekode]"
    _lookup_title_column = "tittel"

    def __init__(self, code, description=None, tittel=None):
        super(GjestetypeKode, self).__init__(code, description)
        self.tittel = tittel
    # end __init__

    def insert(self):
        self.sql.execute("""
          INSERT INTO %(code_table)s
            (%(code_col)s, %(str_col)s, %(desc_col)s, tittel)
          VALUES
            (%(code_seq)s, :str, :desc, :tittel) """ % {
              "code_table" : self._lookup_table,
              "code_col"   : self._lookup_code_column,
              "str_col"    : self._lookup_str_column,
              "desc_col"   : self._lookup_desc_column,
              "code_seq"   : self._code_sequence
              },
              { 'str'           : self.str,
                'desc'          : self._desc,
                'tittel'        : self.tittel
              })
    # end insert
# end GjestetypeKode





class RolleKode(Constants._CerebrumCode):
    _lookup_table = "[:table schema=cerebrum name=lt_rollekode]"
# end RolleKode





class PermisjonsKode(Constants._CerebrumCode):
    _lookup_table = "[:table schema=cerebrum name=lt_permisjonskode]"
# end class PermisjonsKode





class Lonnsstatus(Constants._CerebrumCode):
    _lookup_table = "[:table schema=cerebrum name=lt_lonnsstatus]"
# end class Lonnsstatus





class LTConstants(Constants.Constants):
    """
    This class embodies all constants that we need to address HR-related
    tables.

    NB! Most of these are automatically generated. The information is
    probably not quite correct (but scribbling all that by hand is damn near
    impossible)
    """

    # ----[ StillingsKode ]-------------------------------------------
    lt_stilling_test = StillingsKode(
        "LT-000",
        "This is a very long description for StillingsKode",
        "VIT",
        "Testtittel StillingsKode"
        )


    lt_stillingskode_radgiver1434 = StillingsKode(
        "1434",
        "rådgiver",
        "ØVR",
        "rådgiver"
    )

    lt_stillingskode_forstekonsulent1408 = StillingsKode(
        "1408",
        "førstekonsulent",
        "ØVR",
        "førstekonsulent"
    )

    lt_stillingskode_seniorradgiver1364 = StillingsKode(
        "1364",
        "seniorrådgiver",
        "ØVR",
        "seniorrådgiver"
    )

    lt_stillingskode_seniorkonsulent1363 = StillingsKode(
        "1363",
        "seniorkonsulent",
        "ØVR",
        "seniorkonsulent"
    )

    lt_stillingskode_radgiver1277 = StillingsKode(
        "1277",
        "rådgiver",
        "ØVR",
        "rådgiver"
    )

    lt_stillingskode_radgiver1276 = StillingsKode(
        "1276",
        "rådgiver",
        "ØVR",
        "rådgiver"
    )

    lt_stillingskode_konsulent1212 = StillingsKode(
        "1212",
        "konsulent",
        "ØVR",
        "konsulent"
    )

    lt_stillingskode_utredningsleder1114 = StillingsKode(
        "1114",
        "utredningsleder",
        "ØVR",
        "utredningsleder"
    )

    lt_stillingskode_prosjektleder1113 = StillingsKode(
        "1113",
        "prosjektleder",
        "ØVR",
        "prosjektleder"
    )

    lt_stillingskode_radgiver1112 = StillingsKode(
        "1112",
        "rådgiver",
        "ØVR",
        "rådgiver"
    )

    lt_stillingskode_arkivleder1072 = StillingsKode(
        "1072",
        "arkivleder",
        "ØVR",
        "arkivleder"
    )

    lt_stillingskode_forstekonsulent1067 = StillingsKode(
        "1067",
        "førstekonsulent",
        "ØVR",
        "førstekonsulent"
    )

    lt_stillingskode_konsulent1066 = StillingsKode(
        "1066",
        "konsulent",
        "ØVR",
        "konsulent"
    )

    lt_stillingskode_konsulent1065 = StillingsKode(
        "1065",
        "konsulent",
        "ØVR",
        "konsulent"
    )

    lt_stillingskode_konsulent1064 = StillingsKode(
        "1064",
        "konsulent",
        "ØVR",
        "konsulent"
    )

    lt_stillingskode_forstesekretaer1063 = StillingsKode(
        "1063",
        "førstesekretær",
        "ØVR",
        "førstesekretær"
    )

    lt_stillingskode_instituttleder1475 = StillingsKode(
        "1475",
        "Instituttleder",
        "ØVR",
        "Instituttleder"
    )

    lt_stillingskode_dekan1474 = StillingsKode(
        "1474",
        "Dekan",
        "ØVR",
        "Dekan"
    )

    lt_stillingskode_avdelingsleder1407 = StillingsKode(
        "1407",
        "avdelingsleder",
        "ØVR",
        "avdelingsleder"
    )

    lt_stillingskode_seksjonssjef1211 = StillingsKode(
        "1211",
        "seksjonssjef",
        "ØVR",
        "seksjonssjef"
    )

    lt_stillingskode_sjefsingenior1088 = StillingsKode(
        "1088",
        "sjefsingeniør",
        "ØVR",
        "sjefsingeniør"
    )

    lt_stillingskode_underdirektor1059 = StillingsKode(
        "1059",
        "underdirektør",
        "ØVR",
        "underdirektør"
    )

    lt_stillingskode_kontorsjef1054 = StillingsKode(
        "1054",
        "kontorsjef",
        "ØVR",
        "kontorsjef"
    )

    lt_stillingskode_inspektor1005 = StillingsKode(
        "1005",
        "inspektør",
        "ØVR",
        "inspektør"
    )

    lt_stillingskode_avdelingsleder1003 = StillingsKode(
        "1003",
        "avdelingsleder",
        "ØVR",
        "avdelingsleder"
    )

    lt_stillingskode_bibliotekar1410 = StillingsKode(
        "1410",
        "bibliotekar",
        "ØVR",
        "bibliotekar"
    )

    lt_stillingskode_bibliotekar1213 = StillingsKode(
        "1213",
        "bibliotekar",
        "ØVR",
        "bibliotekar"
    )

    lt_stillingskode_avd_bibliotekar1178 = StillingsKode(
        "1178",
        "avd.bibliotekar",
        "ØVR",
        "avd.bibliotekar"
    )

    lt_stillingskode_avd_bibliotekar1172 = StillingsKode(
        "1172",
        "avd.bibliotekar",
        "ØVR",
        "avd.bibliotekar"
    )

    lt_stillingskode_hovedbibliotekar1077 = StillingsKode(
        "1077",
        "hovedbibliotekar",
        "ØVR",
        "hovedbibliotekar"
    )

    lt_stillingskode_bibliotekleder1076 = StillingsKode(
        "1076",
        "bibliotekleder",
        "ØVR",
        "bibliotekleder"
    )

    lt_stillingskode_bibliotekar1075 = StillingsKode(
        "1075",
        "bibliotekar",
        "ØVR",
        "bibliotekar"
    )

    lt_stillingskode_bibliotekar1074 = StillingsKode(
        "1074",
        "bibliotekar",
        "ØVR",
        "bibliotekar"
    )

    lt_stillingskode_bibliotekfullmektig1073 = StillingsKode(
        "1073",
        "bibliotekfullmektig",
        "ØVR",
        "bibliotekfullmektig"
    )

    lt_stillingskode_laerer_i_prof_ii8018 = StillingsKode(
        "8018",
        "lærer i prof II",
        "VIT",
        "lærer i prof II"
    )

    lt_stillingskode_laerer_i_prof_ii8017 = StillingsKode(
        "8017",
        "lærer i prof II",
        "VIT",
        "lærer i prof II"
    )

    lt_stillingskode_professor_ii8013 = StillingsKode(
        "8013",
        "professor II",
        "VIT",
        "professor II"
    )

    lt_stillingskode_professor_ii8012 = StillingsKode(
        "8012",
        "professor II",
        "VIT",
        "professor II"
    )

    lt_stillingskode_amanuensis_ii8011 = StillingsKode(
        "8011",
        "amanuensis II",
        "VIT",
        "amanuensis II"
    )

    lt_stillingskode_forsker1183 = StillingsKode(
        "1183",
        "forsker",
        "VIT",
        "forsker"
    )

    lt_stillingskode_forskningssjef1111 = StillingsKode(
        "1111",
        "forskningssjef",
        "VIT",
        "forskningssjef"
    )

    lt_stillingskode_forsker1110 = StillingsKode(
        "1110",
        "forsker",
        "VIT",
        "forsker"
    )

    lt_stillingskode_forsker1109 = StillingsKode(
        "1109",
        "forsker",
        "VIT",
        "forsker"
    )

    lt_stillingskode_forsker1108 = StillingsKode(
        "1108",
        "forsker",
        "VIT",
        "forsker"
    )

    lt_stillingskode_vit_assistent1020 = StillingsKode(
        "1020",
        "vit. assistent",
        "VIT",
        "vit. assistent"
    )

    lt_stillingskode_vit_assistent1019 = StillingsKode(
        "1019",
        "vit. assistent",
        "VIT",
        "vit. assistent"
    )

    lt_stillingskode_vit_assistent1018 = StillingsKode(
        "1018",
        "vit. assistent",
        "VIT",
        "vit. assistent"
    )

    lt_stillingskode_lektor966 = StillingsKode(
        "966",
        "lektor",
        "VIT",
        "lektor"
    )

    lt_stillingskode_lektor965 = StillingsKode(
        "965",
        "lektor",
        "VIT",
        "lektor"
    )

    lt_stillingskode_adjunkt962 = StillingsKode(
        "962",
        "adjunkt",
        "VIT",
        "adjunkt"
    )

    lt_stillingskode_laerer961 = StillingsKode(
        "961",
        "lærer",
        "VIT",
        "lærer"
    )

    lt_stillingskode_aspirant1429 = StillingsKode(
        "1429",
        "aspirant",
        "ØVR",
        "aspirant"
    )

    lt_stillingskode_laerling_reform_949745 = StillingsKode(
        "9745",
        "lærling Reform 94",
        "ØVR",
        "lærling Reform 94"
    )

    lt_stillingskode_lesesalsinspektor8032 = StillingsKode(
        "8032",
        "lesesalsinspektør",
        "ØVR",
        "lesesalsinspektør"
    )

    lt_stillingskode_lesesalsinspektor8031 = StillingsKode(
        "8031",
        "lesesalsinspektør",
        "ØVR",
        "lesesalsinspektør"
    )

    lt_stillingskode_laerling1362 = StillingsKode(
        "1362",
        "lærling",
        "ØVR",
        "lærling"
    )

    lt_stillingskode_laerling_aspirant1139 = StillingsKode(
        "1139",
        "lærling/aspirant",
        "ØVR",
        "lærling/aspirant"
    )

    lt_stillingskode_styrer948 = StillingsKode(
        "948",
        "styrer",
        "ØVR",
        "styrer"
    )

    lt_stillingskode_forskolelaerer947 = StillingsKode(
        "947",
        "førskolelærer",
        "ØVR",
        "førskolelærer"
    )

    lt_stillingskode_bhgass_m_barnepl_utd830 = StillingsKode(
        "830",
        "bhgass.m/barnepl.utd",
        "ØVR",
        "bhgass.m/barnepl.utd"
    )

    lt_stillingskode_barnehageassistent829 = StillingsKode(
        "829",
        "barnehageassistent",
        "ØVR",
        "barnehageassistent"
    )

    lt_stillingskode_barnepleier826 = StillingsKode(
        "826",
        "barnepleier",
        "ØVR",
        "barnepleier"
    )

    lt_stillingskode_kode_konvertering_pr20001 = StillingsKode(
        "1",
        "KODE KONVERTERING PR2000",
        "ØVR",
        "KODE KONVERTERING PR2000"
    )

    lt_stillingskode_hjelpearbeider1115 = StillingsKode(
        "1115",
        "hjelpearbeider",
        "ØVR",
        "hjelpearbeider"
    )

    lt_stillingskode_driftsoperator1216 = StillingsKode(
        "1216",
        "driftsoperatør",
        "ØVR",
        "driftsoperatør"
    )

    lt_stillingskode_fagarbeider_fagbrev1203 = StillingsKode(
        "1203",
        "fagarbeider /fagbrev",
        "ØVR",
        "fagarbeider /fagbrev"
    )

    lt_stillingskode_unge_arbeidstakere1138 = StillingsKode(
        "1138",
        "unge arbeidstakere",
        "ØVR",
        "unge arbeidstakere"
    )

    lt_stillingskode_driftsleder1137 = StillingsKode(
        "1137",
        "driftsleder",
        "ØVR",
        "driftsleder"
    )

    lt_stillingskode_driftstekniker1136 = StillingsKode(
        "1136",
        "driftstekniker",
        "ØVR",
        "driftstekniker"
    )

    lt_stillingskode_tekn_driftsbetjent1135 = StillingsKode(
        "1135",
        "tekn. driftsbetjent",
        "ØVR",
        "tekn. driftsbetjent"
    )

    lt_stillingskode_renholdsleder1132 = StillingsKode(
        "1132",
        "renholdsleder",
        "ØVR",
        "renholdsleder"
    )

    lt_stillingskode_renholder1130 = StillingsKode(
        "1130",
        "renholder",
        "ØVR",
        "renholder"
    )

    lt_stillingskode_renholdsbetjent1129 = StillingsKode(
        "1129",
        "renholdsbetjent",
        "ØVR",
        "renholdsbetjent"
    )

    lt_stillingskode_husokonom1128 = StillingsKode(
        "1128",
        "husøkonom",
        "ØVR",
        "husøkonom"
    )

    lt_stillingskode_formann1119 = StillingsKode(
        "1119",
        "formann",
        "ØVR",
        "formann"
    )

    lt_stillingskode_fagarbeider1117 = StillingsKode(
        "1117",
        "fagarbeider",
        "ØVR",
        "fagarbeider"
    )

    lt_stillingskode_spesialarbeider1116 = StillingsKode(
        "1116",
        "spesialarbeider",
        "ØVR",
        "spesialarbeider"
    )

    lt_stillingskode_forstebetjent1079 = StillingsKode(
        "1079",
        "førstebetjent",
        "ØVR",
        "førstebetjent"
    )

    lt_stillingskode_betjent1078 = StillingsKode(
        "1078",
        "betjent",
        "ØVR",
        "betjent"
    )

    lt_stillingskode_professor1404 = StillingsKode(
        "1404",
        "professor",
        "VIT",
        "professor"
    )

    lt_stillingskode_forstelektor1198 = StillingsKode(
        "1198",
        "førstelektor",
        "VIT",
        "førstelektor"
    )

    lt_stillingskode_professor1013 = StillingsKode(
        "1013",
        "professor",
        "VIT",
        "professor"
    )

    lt_stillingskode_forsteamanuensis1011 = StillingsKode(
        "1011",
        "førsteamanuensis",
        "VIT",
        "førsteamanuensis"
    )

    lt_stillingskode_amanuensis1010 = StillingsKode(
        "1010",
        "amanuensis",
        "VIT",
        "amanuensis"
    )

    lt_stillingskode_universitetslektor1009 = StillingsKode(
        "1009",
        "universitetslektor",
        "VIT",
        "universitetslektor"
    )

    lt_stillingskode_seniorsekretaer1433 = StillingsKode(
        "1433",
        "seniorsekretær",
        "ØVR",
        "seniorsekretær"
    )

    lt_stillingskode_sekretaer1409 = StillingsKode(
        "1409",
        "sekretær",
        "ØVR",
        "sekretær"
    )

    lt_stillingskode_sekretaer1070 = StillingsKode(
        "1070",
        "sekretær",
        "ØVR",
        "sekretær"
    )

    lt_stillingskode_forstefullmektig1069 = StillingsKode(
        "1069",
        "førstefullmektig",
        "ØVR",
        "førstefullmektig"
    )

    lt_stillingskode_fullmektig1068 = StillingsKode(
        "1068",
        "fullmektig",
        "ØVR",
        "fullmektig"
    )

    lt_stillingskode_universitetsdirektor9131 = StillingsKode(
        "9131",
        "universitetsdirektør",
        "ØVR",
        "universitetsdirektør"
    )

    lt_stillingskode_direktor1062 = StillingsKode(
        "1062",
        "direktør",
        "ØVR",
        "direktør"
    )

    lt_stillingskode_ass_direktor1061 = StillingsKode(
        "1061",
        "ass direktør",
        "ØVR",
        "ass direktør"
    )

    lt_stillingskode_avdelingsdirektor1060 = StillingsKode(
        "1060",
        "avdelingsdirektør",
        "ØVR",
        "avdelingsdirektør"
    )

    lt_stillingskode_edb_sjef1006 = StillingsKode(
        "1006",
        "EDB-sjef",
        "ØVR",
        "EDB-sjef"
    )

    lt_stillingskode_stipendiat1378 = StillingsKode(
        "1378",
        "stipendiat",
        "VIT",
        "stipendiat"
    )

    lt_stillingskode_postdoktor1352 = StillingsKode(
        "1352",
        "postdoktor",
        "VIT",
        "postdoktor"
    )

    lt_stillingskode_stipendiat1017 = StillingsKode(
        "1017",
        "stipendiat",
        "VIT",
        "stipendiat"
    )

    lt_stillingskode_instr_tannl_m_spes_utd1353 = StillingsKode(
        "1353",
        "instr.tannl. m/spes.utd",
        "VIT",
        "instr.tannl. m/spes.utd"
    )

    lt_stillingskode_avdelingstannlege1260 = StillingsKode(
        "1260",
        "avdelingstannlege",
        "VIT",
        "avdelingstannlege"
    )

    lt_stillingskode_spesialtannlege1016 = StillingsKode(
        "1016",
        "spesialtannlege",
        "VIT",
        "spesialtannlege"
    )

    lt_stillingskode_instruktortannlege1015 = StillingsKode(
        "1015",
        "instruktørtannlege",
        "VIT",
        "instruktørtannlege"
    )

    lt_stillingskode_sjefarkitekt1095 = StillingsKode(
        "1095",
        "sjefarkitekt",
        "ØVR",
        "sjefarkitekt"
    )

    lt_stillingskode_avdelingsingenior1411 = StillingsKode(
        "1411",
        "avdelingsingeniør",
        "ØVR",
        "avdelingsingeniør"
    )

    lt_stillingskode_seniorforskningstekniker1405 = StillingsKode(
        "1405",
        "seniorforskningstekniker",
        "ØVR",
        "seniorforskningstekniker"
    )

    lt_stillingskode_klinikksekretaer1379 = StillingsKode(
        "1379",
        "klinikksekretær",
        "ØVR",
        "klinikksekretær"
    )

    lt_stillingskode_spesialpsykolog1304 = StillingsKode(
        "1304",
        "spesialpsykolog",
        "ØVR",
        "spesialpsykolog"
    )

    lt_stillingskode_ingenior1275 = StillingsKode(
        "1275",
        "ingeniør",
        "ØVR",
        "ingeniør"
    )

    lt_stillingskode_seniorarkitekt1182 = StillingsKode(
        "1182",
        "seniorarkitekt",
        "ØVR",
        "seniorarkitekt"
    )

    lt_stillingskode_senioringenior1181 = StillingsKode(
        "1181",
        "senioringeniør",
        "ØVR",
        "senioringeniør"
    )

    lt_stillingskode_preparantleder1107 = StillingsKode(
        "1107",
        "preparantleder",
        "ØVR",
        "preparantleder"
    )

    lt_stillingskode_preparant1106 = StillingsKode(
        "1106",
        "preparant",
        "ØVR",
        "preparant"
    )

    lt_stillingskode_preparantassistent1105 = StillingsKode(
        "1105",
        "preparantassistent",
        "ØVR",
        "preparantassistent"
    )

    lt_stillingskode_fotoleder1104 = StillingsKode(
        "1104",
        "fotoleder",
        "ØVR",
        "fotoleder"
    )

    lt_stillingskode_forstefotograf1103 = StillingsKode(
        "1103",
        "førstefotograf",
        "ØVR",
        "førstefotograf"
    )

    lt_stillingskode_fotograf1102 = StillingsKode(
        "1102",
        "fotograf",
        "ØVR",
        "fotograf"
    )

    lt_stillingskode_laborantleder1098 = StillingsKode(
        "1098",
        "laborantleder",
        "ØVR",
        "laborantleder"
    )

    lt_stillingskode_laborant1097 = StillingsKode(
        "1097",
        "laborant",
        "ØVR",
        "laborant"
    )

    lt_stillingskode_laboratorieassistent1096 = StillingsKode(
        "1096",
        "laboratorieassistent",
        "ØVR",
        "laboratorieassistent"
    )

    lt_stillingskode_overarkitekt1094 = StillingsKode(
        "1094",
        "overarkitekt",
        "ØVR",
        "overarkitekt"
    )

    lt_stillingskode_avdelingsarkitekt1093 = StillingsKode(
        "1093",
        "avdelingsarkitekt",
        "ØVR",
        "avdelingsarkitekt"
    )

    lt_stillingskode_arkitekt1092 = StillingsKode(
        "1092",
        "arkitekt",
        "ØVR",
        "arkitekt"
    )

    lt_stillingskode_tekniker1090 = StillingsKode(
        "1090",
        "tekniker",
        "ØVR",
        "tekniker"
    )

    lt_stillingskode_teknisk_assistent1089 = StillingsKode(
        "1089",
        "teknisk assistent",
        "ØVR",
        "teknisk assistent"
    )

    lt_stillingskode_overingenior1087 = StillingsKode(
        "1087",
        "overingeniør",
        "ØVR",
        "overingeniør"
    )

    lt_stillingskode_avdelingsingenior1086 = StillingsKode(
        "1086",
        "avdelingsingeniør",
        "ØVR",
        "avdelingsingeniør"
    )

    lt_stillingskode_avdelingsingenior1085 = StillingsKode(
        "1085",
        "avdelingsingeniør",
        "ØVR",
        "avdelingsingeniør"
    )

    lt_stillingskode_avdelingsingenior1084 = StillingsKode(
        "1084",
        "avdelingsingeniør",
        "ØVR",
        "avdelingsingeniør"
    )

    lt_stillingskode_ingenior1083 = StillingsKode(
        "1083",
        "ingeniør",
        "ØVR",
        "ingeniør"
    )

    lt_stillingskode_ingenior1082 = StillingsKode(
        "1082",
        "ingeniør",
        "ØVR",
        "ingeniør"
    )

    lt_stillingskode_klinikkavd_leder1033 = StillingsKode(
        "1033",
        "klinikkavd.leder",
        "ØVR",
        "klinikkavd.leder"
    )

    lt_stillingskode_instruktortannpleier1032 = StillingsKode(
        "1032",
        "instruktørtannpleier",
        "ØVR",
        "instruktørtannpleier"
    )

    lt_stillingskode_tannpleier1031 = StillingsKode(
        "1031",
        "tannpleier",
        "ØVR",
        "tannpleier"
    )

    lt_stillingskode_klinikkfullmektig1030 = StillingsKode(
        "1030",
        "klinikkfullmektig",
        "ØVR",
        "klinikkfullmektig"
    )

    lt_stillingskode_avdelingsleder1029 = StillingsKode(
        "1029",
        "avdelingsleder",
        "ØVR",
        "avdelingsleder"
    )

    lt_stillingskode_ledende_forsk_tekniker1028 = StillingsKode(
        "1028",
        "ledende forsk.tekniker",
        "ØVR",
        "ledende forsk.tekniker"
    )

    lt_stillingskode_forskningstekniker1027 = StillingsKode(
        "1027",
        "forskningstekniker",
        "ØVR",
        "forskningstekniker"
    )

    lt_stillingskode_forskningstekniker1026 = StillingsKode(
        "1026",
        "forskningstekniker",
        "ØVR",
        "forskningstekniker"
    )

    lt_stillingskode_bioingenior845 = StillingsKode(
        "845",
        "bioingeniør",
        "ØVR",
        "bioingeniør"
    )

    lt_stillingskode_instruktor_fysioter_835 = StillingsKode(
        "835",
        "instruktør/fysioter.",
        "ØVR",
        "instruktør/fysioter."
    )

    lt_stillingskode_fysioterapeut832 = StillingsKode(
        "832",
        "fysioterapeut",
        "ØVR",
        "fysioterapeut"
    )

    lt_stillingskode_oversykepleier820 = StillingsKode(
        "820",
        "oversykepleier",
        "ØVR",
        "oversykepleier"
    )

    lt_stillingskode_spes_utd_sykepleier810 = StillingsKode(
        "810",
        "spes.utd sykepleier",
        "ØVR",
        "spes.utd sykepleier"
    )

    lt_stillingskode_sjefpsykolog796 = StillingsKode(
        "796",
        "sjefpsykolog",
        "ØVR",
        "sjefpsykolog"
    )

    lt_stillingskode_spesialpsykolog795 = StillingsKode(
        "795",
        "spesialpsykolog",
        "ØVR",
        "spesialpsykolog"
    )

    lt_stillingskode_psykolog794 = StillingsKode(
        "794",
        "psykolog",
        "ØVR",
        "psykolog"
    )

    lt_stillingskode_bedriftslege791 = StillingsKode(
        "791",
        "bedriftslege",
        "ØVR",
        "bedriftslege"
    )

    lt_stillingskode_bedriftssykepleier790 = StillingsKode(
        "790",
        "bedriftssykepleier",
        "ØVR",
        "bedriftssykepleier"
    )

    lt_stillingskode_avdelingsoverlege784 = StillingsKode(
        "784",
        "avdelingsoverlege",
        "ØVR",
        "avdelingsoverlege"
    )

    lt_stillingskode_overlege782 = StillingsKode(
        "782",
        "overlege",
        "ØVR",
        "overlege"
    )

    lt_stillingskode_radgivende_lege776 = StillingsKode(
        "776",
        "rådgivende lege",
        "ØVR",
        "rådgivende lege"
    )

    lt_stillingskode_forstebibliotekar1200 = StillingsKode(
        "1200",
        "førstebibliotekar",
        "VIT",
        "førstebibliotekar"
    )

    lt_stillingskode_univ_bibliotekar1199 = StillingsKode(
        "1199",
        "univ.bibliotekar",
        "VIT",
        "univ.bibliotekar"
    )

    lt_stillingskode_overbibliotekar1024 = StillingsKode(
        "1024",
        "overbibliotekar",
        "VIT",
        "overbibliotekar"
    )

    lt_stillingskode_ass_overbibliotekar1023 = StillingsKode(
        "1023",
        "ass overbibliotekar",
        "VIT",
        "ass overbibliotekar"
    )

    lt_stillingskode_bibliotekaspirant1021 = StillingsKode(
        "1021",
        "bibliotekaspirant",
        "VIT",
        "bibliotekaspirant"
    )

    # ----[ GjestetypeKode ]------------------------------------------
    lt_gjestekode_test = GjestetypeKode(
        "LT-000",
        "This is a very long description for GjestetypeKode",
        "test-gje"
        )

    lt_gjestetypekode_emeritus = GjestetypeKode(
        "EMERITUS",
        "Professor emeritus",
        "EMERITUS"
    )

    lt_gjestetypekode_ef_stip = GjestetypeKode(
        "EF-STIP",
        "Eksternfinansiert stipendiat",
        "EF-STIP"
    )

    lt_gjestetypekode_ef_forsker = GjestetypeKode(
        "EF-FORSKER",
        "Eksternfinansiert forsker",
        "EF-FORSKER"
    )

    lt_gjestetypekode_gj_forsker = GjestetypeKode(
        "GJ-FORSKER",
        "Gjesteforsker",
        "GJ-FORSKER"
    )

    lt_gjestetypekode_sivilarb = GjestetypeKode(
        "SIVILARB",
        "Sivilarbeider",
        "SIVILARB"
    )

    lt_gjestetypekode_ekst_kons = GjestetypeKode(
        "EKST. KONS",
        "Ekstern konsulent",
        "EKST. KONS"
    )

    lt_gjestetypekode_pcvakt = GjestetypeKode(
        "PCVAKT",
        "Pc-stue vakter ved UiO",
        "PCVAKT"
    )

    lt_gjestetypekode_pcvakt = GjestetypeKode(
        "GRP-LÆRER",
        "Gruppelærere ved UiO",
        "GRP-LÆRER"
    )

    lt_gjestetypekode_ikke_angit = GjestetypeKode(
        "IKKE ANGIT",
        "<ikke angitt>",
        "IKKE ANGIT"
    )

    lt_gjestetypekode_seniorfors = GjestetypeKode(
        "SENIORFORS",
        "Seniorforsker",
        "SENIORFORS"
    )

    lt_gjestetypekode_bilagslon = GjestetypeKode(
        "BILAGSLØN",
        "<bilagslønnet stilling>",
        "BILAGSLØN"
    )

    lt_gjestetypekode_regansv = GjestetypeKode(
        "REGANSV",
        "Registreringsansvarlig (FRIDA)",
        "REGANSV"
    )

    lt_gjestetypekode_reg_ansv = GjestetypeKode(
        "REG-ANSV",
        "Registreringsansvarlig (Frida)",
        "REG-ANSV"
    )

    # ----[ Rollekoder ]----------------------------------------------
    lt_rollekode_test = RolleKode(
        "LT-000",
        "Dette er en fjasetestekode"
    )

    lt_rollekode_xxxxxxxxxx = RolleKode(
        "XXXXXXXXXX",
        "xxxTest Beskrivelse for Ansvarsrolle"
    )

    lt_rollekode_ok_kons = RolleKode(
        "ØK-KONS",
        "Person med ansvar for økonomi ved enheter, fakultet, sentralt mm"
    )

    lt_rollekode_ok_anv = RolleKode(
        "ØK-ANV",
        "Person med ansvar for økonomi ved enheter, fakultet, sentralt mm og som har anvisningsrett."
    )

    lt_rollekode_studkons = RolleKode(
        "STUDKONS",
        "Studiekonsulent"
    )

    lt_rollekode_studveil = RolleKode(
        "STUDVEIL",
        "Studieveileder"
    )

    lt_rollekode_exkons = RolleKode(
        "EXKONS",
        "Eksamenskonsulent"
    )

    lt_rollekode_perskons = RolleKode(
        "PERSKONS",
        "Personalkonsulent"
    )

    lt_rollekode_betjent = RolleKode(
        "BETJENT",
        "Betjent"
    )

    lt_rollekode_bud = RolleKode(
        "BUD",
        "Bud"
    )

    lt_rollekode_repro = RolleKode(
        "REPRO",
        "Reprosentrelen"
    )

    lt_rollekode_lonnskons = RolleKode(
        "LØNNKONS",
        "Lønningskonsulent"
    )

    lt_rollekode_brann = RolleKode(
        "BRANN",
        "Branansvarlig"
    )

    lt_rollekode_vomb = RolleKode(
        "VOMB",
        "Verneombud"
    )

    lt_rollekode_sikkerhet = RolleKode(
        "SIKKERHET",
        "Sikkerhetsansvarlig"
    )

    lt_rollekode_grp_leder = RolleKode(
        "GRP-LEDER",
        "Gruppeleder"
    )

    lt_rollekode_sek_leder = RolleKode(
        "SEK-LEDER",
        "Seksjonsleder"
    )

    lt_rollekode_avd_leder = RolleKode(
        "AVD-LEDER",
        "Avdelingsleder"
    )

    lt_rollekode_kontorsjef = RolleKode(
        "KONTORSJEF",
        "Leder for enhet ved UiO"
    )

    lt_rollekode_assfakdir = RolleKode(
        "ASSFAKDIR",
        "Assisterende fakultetsdirektør"
    )

    lt_rollekode_fakdir = RolleKode(
        "FAKDIR",
        "Fakultetsdirektør"
    )

    lt_rollekode_fagdir = RolleKode(
        "FAGDIR",
        "Fag-direktør"
    )

    lt_rollekode_assunidir = RolleKode(
        "ASSUNIDIR",
        "Assisterende Universitetsdirektør"
    )

    lt_rollekode_unidir = RolleKode(
        "UNIDIR",
        "Universitetsdirektør"
    )

    lt_rollekode_bestyrer = RolleKode(
        "Bestyrer",
        "Bestyrer for institutt"
    )

    lt_rollekode_prodekan = RolleKode(
        "PRODEKAN",
        "Prodekanus ved et av fakultetene"
    )

    lt_rollekode_dekanus = RolleKode(
        "DEKANUS",
        "Dekanus ved et av fakultetene"
    )

    lt_rollekode_prorektor = RolleKode(
        "PROREKTOR",
        "Prorektor ved UiO"
    )

    lt_rollekode_rektor = RolleKode(
        "REKTOR",
        "Rektor ved UiO"
    )

    lt_rollekode_inststyr = RolleKode(
        "INSTSTYR",
        "Instituttstyremedlemmer"
    )

    lt_rollekode_fak_styre = RolleKode(
        "FAK-STYRE",
        "Medlemmer av Fakultetsstyre"
    )

    lt_rollekode_fak_rad = RolleKode(
        "FAK-RÅD",
        "Medlemmer av fakultetsråd"
    )

    lt_rollekode_kollegiet = RolleKode(
        "KOLLEGIET",
        "Medlemmer av Kollegiet"
    )

    lt_rollekode_kol_rad = RolleKode(
        "KOL-RÅD",
        "Valgte medlemmer av Kollegierådet"
    )

    lt_rollekode_ntl_medl = RolleKode(
        "NTL-MEDL",
        "Medlemmer av organisasjoner tilknyttet NTL"
    )

    lt_rollekode_af_medl = RolleKode(
        "AF-MEDL",
        "Medlemmer av organisasjoner tilknyttet AF"
    )

    lt_rollekode_ys_medl = RolleKode(
        "YS-MEDL",
        "Medlemmer av organisasjoner tilknyttet YS"
    )

    lt_rollekode_infokons = RolleKode(
        "INFOKONS",
        "Informasjonsanvarlig"
    )

    lt_rollekode_infoweb = RolleKode(
        "INFOWEB",
        "Ansvarlig for produksjon ov vedlikehold av web-sider"
    )

    lt_rollekode_lita = RolleKode(
        "LITA",
        "Ansvarlig for lokal brukerstøtte"
    )

    lt_rollekode_webmaster = RolleKode(
        "WEBMASTER",
        "Teknisk ansvarlig for enhets web-server"
    )

    lt_rollekode_studit = RolleKode(
        "STUDIT",
        "Ansvarlig for lokal brukerstøtte ovenfor studenter"
    )

    lt_rollekode_syseier = RolleKode(
        "SYSEIER",
        "Representerer systemeier for system ved enhet(er)"
    )

    lt_rollekode_litko = RolleKode(
        "LITKO",
        "Ansvarlig for koordinering enheters IT-arbeid"
    )

    lt_rollekode_ansatt = RolleKode(
        "ANSATT",
        "Person med fast stilling"
    )

    lt_rollekode_resepsjon = RolleKode(
        "RESEPSJON",
        "Resepsjon, ekspedisjon, sentralbord"
    )

    lt_rollekode_tekniskans = RolleKode(
        "TEKNISKANS",
        "Ansatt i teknisk stilling"
    )

    lt_rollekode_adm_ans = RolleKode(
        "ADM-ANS",
        "Ansatt i administrativ stilling"
    )

    lt_rollekode_vit_ans = RolleKode(
        "VIT-ANS",
        "Ansatt i vitenskaplig stilling"
    )

    lt_rollekode_stedopplys = RolleKode(
        "STEDOPPLYS",
        "Ansvarlig for opplysninger om stedkode"
    )

    # ----[ Permisjonskoder ]-------------------------------------------
    lt_permisjonskode_test = PermisjonsKode(
        "LT-000",
        "This is a very long description for PermisjonsKode"
        )

    lt_permisjonskode_ferie = PermisjonsKode(
        "FERIE",
        "Ferie (utenfor juni måned)"
        )

    lt_permisjonskode_forsk = PermisjonsKode(
        "FORSK",
        "Forskningstermin"
        )

    lt_permisjonskode_int = PermisjonsKode(
        "INT",
        "Internasjonalt samarbeide"
        )

    lt_permisjonskode_mili = PermisjonsKode(
        "MILI",
        "Militærtjeneste"
        )

    lt_permisjonskode_off = PermisjonsKode(
        "OFF",
        "Offentlig verv"
        )

    lt_permisjonskode_omsrg = PermisjonsKode(
        "OMSRG",
        "Omsorg"
        )

    lt_permisjonskode_org = PermisjonsKode(
        "ORG",
        "Organisasjonsarbeid"
        )

    
    lt_permisjonskode_svang = PermisjonsKode(
        "SVANG",
        "Svangerskap"
        )

    lt_permisjonskode_syk = PermisjonsKode(
        "SYK",
        "Sykdom"
        )

    lt_permisjonskode_tila = PermisjonsKode(
        "TILA",
        "Tilsatt i annen stilling (uspesifisert)"
        )

    lt_permisjonskode_tilk = PermisjonsKode(
        "TILK",
        "Tilsatt i annen stilling, kommunal"
        )

    lt_permisjonskode_tilp = PermisjonsKode(
        "TILP",
        "Tilsatt i annen stilling, privat"
        )

    lt_permisjonskode_tils = PermisjonsKode(
        "TILS",
        "Tilsatt i annen stilling i staten"
        )

    lt_permisjonskode_tilu = PermisjonsKode(
        "TILU",
        "Tilsatt i annen stilling, Univ. i Oslo"
        )

    lt_permisjonskode_ukj = PermisjonsKode(
        "UKJ",
        "Ukjent permisjonsårsak"
        )

    lt_permisjonskode_uspes = PermisjonsKode(
        "USPES",
        "Uspesifisert permisjonsårsak"
        )
    
    lt_permisjonskode_utd = PermisjonsKode(
        "UTD",
        "Utdanning"
        )

    lt_permisjonskode_velf = PermisjonsKode(
        "VELF",
        "Velferdsgrunn"
        )
 
    # ----[ Lønnsstatus ]---------------------------------------------
    lt_lonnsstatus_33 = Lonnsstatus(
        "1/3",
        "1/3 lønn"
        )

    lt_lonnsstatus_35 = Lonnsstatus(
        "35",
        "35 prosent lønn"
        )

    lt_lonnsstatus_100 = Lonnsstatus(
        "FULL",
        "Full lønn"
        )

    lt_lonnsstatus_0 = Lonnsstatus(
        "UTEN",
        "Uten lønn"
        )

    lt_lonnsstatus_80 = Lonnsstatus(
        "80",
        "80 prosent lønn"
        )
    
# end LTConstants

# arch-tag: 1ce5622c-b19f-4144-8660-be77aa81379c

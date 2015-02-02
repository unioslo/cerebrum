# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003, 2004 University of Oslo, Norway
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

"""Klasser for aksesering av FS.  Institusjons-spesifik bruk av FS bør
håndteres ved å subklasse relevante deler av denne koden.  Tilsvarende
dersom man skal ha kode for en spesifik FS-versjon.

Disse klassene er ment brukt ved å instansiere klassen FS
"""

import cerebrum_path
import cereconf
import time
import xml.sax

from Cerebrum import Database
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import access_FS

class Student40(FSObject):
    def list_tilbud(self, institutsjonsnr=0):  # GetStudinfTilbud
        """Hent personer som har fått tilbud om opptak
	Disse skal gis affiliation student med kode tilbud til
        stedskoden sp.faknr_studieansv+sp.instituttnr_studieansv+
        sp.gruppenr_studieansv. Personer som har fått tilbud om
        opptak til et studieprogram ved institusjonen vil inngå i
        denne kategorien.  Alle søkere til studierved institusjonen
	registreres i tabellen fs.soknadsalternativ og informasjon om
	noen har fått tilbud om opptak hentes også derfra (feltet
        fs.soknadsalternativ.tilbudstatkode er et godt sted å 
        begynne å lete etter personer som har fått tilbud)."""

        qry = """
        SELECT DISTINCT
              p.fodselsdato, p.personnr, p.etternavn, p.fornavn, 
              p.adrlin1_hjemsted, p.adrlin2_hjemsted,
              p.postnr_hjemsted, p.adrlin3_hjemsted, p.adresseland_hjemsted,
              p.sprakkode_malform, osp.studieprogramkode, p.kjonn,
              p.status_reserv_nettpubl
        FROM fs.soknadsalternativ sa, fs.person p, fs.opptakstudieprogram osp,
             fs.studieprogram sp
        WHERE p.fodselsdato=sa.fodselsdato AND
              p.personnr=sa.personnr AND
              sa.institusjonsnr='%s' AND 
              sa.opptakstypekode = 'NOM' AND
              sa.tilbudstatkode IN ('I', 'S') AND
              sa.studietypenr = osp.studietypenr AND
              osp.studieprogramkode = sp.studieprogramkode
              AND %s
      """ % (self.institusjonsnr, self._is_alive())
        return self.db.query(qry)

    def get_studierett(self, fnr, pnr):  # GetStudentStudierett
	"""Hent info om alle studierett en student har eller har hatt"""
        qry = """
        SELECT DISTINCT
          st.studieprogramkode, st.studierettstatkode, st.dato_tildelt,
          st.dato_gyldig_til, st.status_privatist, st.opphortstudierettstatkode
        FROM fs.studierett st, fs.person p
        WHERE st.fodselsdato=:fnr AND
              st.personnr=:pnr AND
              st.fodselsdato=p.fodselsdato AND
              st.personnr=p.personnr 
              AND %s
        """ % self._is_alive()
        return self.db.query(qry, {'fnr': fnr, 'pnr': pnr})


    def _list_opptak_query(self):
        """Hent personer med opptak til et studieprogram ved
        institusjonen og som enten har vært registrert siste året
        eller opptak efter 2003-01-01.  Henter ikke de som har
        fremtidig opptak.  Disse kommer med 14 dager før dato for
        tildelt opptak.  Med untak av de som har 'studierettstatkode'
        lik 'PRIVATIST' skal alle disse få affiliation student med
        kode 'opptak' ('privatist' for disse) til stedskoden
        sp.faknr_studieansv + sp.instituttnr_studieansv +
        sp.gruppenr_studieansv"""

        qry = """
        SELECT DISTINCT s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
               s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
               s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
               p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
               p.adresseland_hjemsted, p.status_reserv_nettpubl, 
               p.sprakkode_malform, st.studieprogramkode, st.studieretningkode,
               st.studierettstatkode, p.kjonn
        FROM fs.student s, fs.person p, fs.studierett st, fs.studieprogram sp
        WHERE  p.fodselsdato=s.fodselsdato AND
               p.personnr=s.personnr AND
               p.fodselsdato=st.fodselsdato AND
               p.personnr=st.personnr AND 
               st.studieprogramkode = sp.studieprogramkode AND
               NVL(st.dato_gyldig_til,SYSDATE) >= sysdate AND
               st.studierettstatkode IN (RELEVANTE_STUDIERETTSTATKODER) AND
               st.dato_tildelt < SYSDATE + 14 AND
               st.dato_tildelt >= to_date('2003-01-01', 'yyyy-mm-dd')
       """
        qry += """ UNION
        SELECT DISTINCT s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
               s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
               s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
               p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
               p.adresseland_hjemsted, p.status_reserv_nettpubl,
               p.sprakkode_malform, st.studieprogramkode, st.studieretningkode,
               st.studierettstatkode, p.kjonn
        FROM fs.student s, fs.person p, fs.studierett st, fs.registerkort r,
             fs.studieprogram sp
        WHERE  p.fodselsdato=s.fodselsdato AND
               p.personnr=s.personnr AND
               p.fodselsdato=st.fodselsdato AND
               p.personnr=st.personnr AND
               st.studieprogramkode = sp.studieprogramkode AND
               p.fodselsdato=r.fodselsdato AND
               p.personnr=r.personnr AND
               NVL(st.dato_gyldig_til,SYSDATE) >= sysdate AND
               st.studierettstatkode IN (RELEVANTE_STUDIERETTSTATKODER) AND
               r.arstall >= (%s - 1)
       """ % (self.year)
        return qry

    def list_opptak(self): # GetStudinfOpptak
        studierettstatkoder = """'AUTOMATISK','AVTALE','CANDMAG', 'DIVERSE',
        'EKSPRIV', 'ERASMUS', 'FJERNUND', 'GJEST', 'FULBRIGHT',
        'HOSPITANT', 'KULTURAVT', 'KVOTEPROG', 'LEONARDO', 'OVERGANG',
        'NUFU', 'SOKRATES', 'LUBECK', 'NORAD', 'ARKHANG', 'NORDPLUS',
        'ORDOPPTAK', 'EVU', 'UTLOPPTAK'"""
        qry = self._list_opptak_query().replace(
            "RELEVANTE_STUDIERETTSTATKODER", studierettstatkoder)
        return self.db.query(qry)



class Student50(FSObject):
    def list_drgrad_50(self): # GetStudinfDrgrad
	"""Henter info om aktive doktorgradsstudenter."""
        qry = """
        SELECT fodselsdato, personnr, institusjonsnr, faknr,
               instituttnr, gruppenr
        FROM fs.drgradsavtale
        WHERE dato_start <= SYSDATE AND
              NVL(DATO_BEREGNET_SLUTT, sysdate) >= SYSDATE"""
        return self.db.query(qry)

class Undervisning50(FSObject):    
    def list_ansvarlig_for_enhet_50(self, Instnr, emnekode, versjon,
                                    termk, aar, termnr): # GetAnsvUndervEnhet
        qry = """
        SELECT
          uan.fodselsdato AS fodselsdato,
          uan.personnr AS personnr
        FROM
          fs.undervisningsansvarlig uan
        WHERE
          uan.institusjonsnr = :instnr AND
          uan.emnekode       = :emnekode AND
          uan.versjonskode   = :versjon AND
          uan.terminkode     = :terminkode AND
          uan.arstall        = :arstall AND
          uan.terminnr       = :terminnr
        UNION
        SELECT
          ue.fodselsdato_Ansvarligkontakt AS fodselsdato,
          ue.personnr_Ansvarligkontakt AS personnr
        FROM
          fs.undervisningsenhet ue
        WHERE
          ue.institusjonsnr = :instnr AND
          ue.emnekode       = :emnekode AND
          ue.versjonskode   = :versjon AND
          ue.terminkode     = :terminkode AND
          ue.arstall        = :arstall AND
          ue.terminnr       = :terminnr AND
          ue.fodselsdato_Ansvarligkontakt IS NOT NULL AND
          ue.personnr_Ansvarligkontakt IS NOT NULL
        UNION
        SELECT
          ual.fodselsdato_fagansvarlig AS fodselsdato,
          ual.personnr_fagansvarlig AS personnr
        FROM
          fs.undaktivitet ua, fs.undaktivitet_lerer ual
        WHERE
          ua.institusjonsnr = :instnr AND
          ua.emnekode       = :emnekode AND
          ua.versjonskode   = :versjon AND
          ua.terminkode     = :terminkode AND
          ua.arstall        = :arstall AND
          ua.terminnr       = :terminnr AND
          ua.undformkode    = 'FOR' AND
          ua.institusjonsnr = ual.institusjonsnr AND
          ua.emnekode       = ual.emnekode AND
          ua.versjonskode   = ual.versjonskode AND
          ua.terminkode     = ual.terminkode AND
          ua.arstall        = ual.arstall AND
          ua.terminnr       = ual.terminnr AND
          ua.aktivitetkode  = ual.aktivitetkode"""

        return self.db.query(qry, {
            'instnr': Instnr,
            'emnekode': emnekode,
            'versjon': versjon,
            'terminkode': termk,
            'arstall': aar,
            'terminnr': termnr})

    def get_ansvarlig_for_enhet_50(self, Instnr, emnekode, versjon, termk,
                                   aar, termnr, aktkode):  # GetAnsvUndAktivitet
        qry = """
        SELECT
          ual.fodselsdato_fagansvarlig AS fodselsdato,
          ual.personnr_fagansvarlig AS personnr,
          ual.status_publiseres AS publiseres
        FROM
          fs.undaktivitet_lerer ual
        WHERE
          ual.institusjonsnr = :instnr AND
          ual.emnekode       = :emnekode AND
          ual.versjonskode   = :versjon AND
          ual.terminkode     = :terminkode AND
          ual.arstall        = :arstall AND
          ual.terminnr       = :terminnr AND
          ual.aktivitetkode  = :aktkode
        UNION
        SELECT
          ul.fodselsdato_underviser AS fodselsdato,
          ul.personnr_underviser AS personnr,
          ul.status_publiseres AS publiseres
        FROM
          FS.UNDERVISNING_LERER ul
        WHERE
          ul.institusjonsnr = :instnr AND
          ul.emnekode       = :emnekode AND
          ul.versjonskode   = :versjon AND
          ul.terminkode     = :terminkode AND
          ul.arstall        = :arstall AND
          ul.terminnr       = :terminnr AND
          ul.aktivitetkode  = :aktkode
        UNION
        SELECT ua.fodselsdato_fagansvarlig AS fodselsdato,
          ua.personnr_fagansvarlig AS personnr,
          ua.status_fagansvarlig_publiseres AS publiseres
        FROM fs.undaktivitet ua
        WHERE
          ua.institusjonsnr = :instnr AND
          ua.emnekode       = :emnekode AND
          ua.versjonskode   = :versjon AND
          ua.terminkode     = :terminkode AND
          ua.arstall        = :arstall AND
          ua.terminnr       = :terminnr AND
          ua.aktivitetkode  = :aktkode AND
          ua.fodselsdato_fagansvarlig IS NOT NULL AND
          ua.personnr_fagansvarlig IS NOT NULL"""

        return self.db.query(qry, {
            'instnr': Instnr,
            'emnekode': emnekode,
            'versjon': versjon,
            'terminkode': termk,
            'arstall': aar,
            'terminnr': termnr,
            'aktkode': aktkode})

class EVU50(FSObject):
    def list_aktivitet_ansv_50(self, kurs, tid, aktkode):  # GetAnsvEvuAktivitet
        qry = """
        SELECT k.fodselsdato, k.personnr
        FROM fs.kursaktivitet_fagperson k
        WHERE k.etterutdkurskode=:kurs AND
              k.kurstidsangivelsekode=:tid AND
              k.aktivitetskode=:aktkode"""
        return self.db.query(qry, {
            'kurs': kurs,
            'tid': tid,
            'aktkode': aktkode})
    
    def get_kurs_ansv_50(self, kurs, tid):  # GetAnsvEvuKurs
        qry = """
        SELECT k.fodselsdato, k.personnr
        FROM fs.kursfagansvarlig k
        WHERE k.etterutdkurskode=:kurs AND
              k.kurstidsangivelsekode=:tid"""
        return self.db.query(qry, {'kurs': kurs, 'tid': tid})
    
class EVU40(FSObject):
    def list(self): # GetStudinfEvu
    	"""Hent info om personer som er ekte EVU-studenter ved
    	UiO, dvs. er registrert i EVU-modulen i tabellen 
    	fs.deltaker"""

 	qry = """
        SELECT DISTINCT 
               p.fodselsdato, p.personnr, p.etternavn, p.fornavn,
               d.adrlin1_job, d.adrlin2_job, d.postnr_job,
               d.adrlin3_job, d.adresseland_job, d.adrlin1_hjem,
               d.adrlin2_hjem, d.postnr_hjem, d.adrlin3_hjem,
               d.adresseland_hjem, p.adrlin1_hjemsted,
               p.status_reserv_nettpubl, p.adrlin2_hjemsted,
               p.postnr_hjemsted, p.adrlin3_hjemsted,
               p.adresseland_hjemsted, d.deltakernr, d.emailadresse,
               k.etterutdkurskode, e.studieprogramkode,
               e.faknr_adm_ansvar, e.instituttnr_adm_ansvar,
               e.gruppenr_adm_ansvar
        FROM fs.deltaker d, fs.person p, fs.kursdeltakelse k,
             fs.etterutdkurs e
        WHERE p.fodselsdato=d.fodselsdato AND
              p.personnr=d.personnr AND
              d.deltakernr=k.deltakernr AND
              e.etterutdkurskode=k.etterutdkurskode AND
              NVL(e.status_nettbasert_und,'J')='J' AND
              k.kurstidsangivelsekode = e.kurstidsangivelsekode AND
              e.dato_til > SYSDATE - 180 
              AND %s
      """ % self._is_alive()
	return self.db.query(qry)

class Alumni40(FSObject):
    def list(self):  # GetAlumni
        qry = """
        SELECT DISTINCT s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
               s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
               s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
               p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
               p.adresseland_hjemsted, p.status_reserv_nettpubl, 
               p.sprakkode_malform,st.studieprogramkode, st.studierettstatkode,
               p.kjonn
        FROM fs.student s, fs.person p, fs.studierett st, fs.eksmeldinglogg el,
             fs.studieprogram sp
        WHERE  p.fodselsdato=s.fodselsdato AND
               p.personnr=s.personnr AND
               p.fodselsdato=st.fodselsdato AND
               p.personnr=st.personnr AND 
               st.studieprogramkode = sp.studieprogramkode AND
               p.fodselsdato=el.fodselsdato AND
               p.personnr=el.personnr AND
               st.opphortstudierettstatkode = 'FULLFØRT'  AND
               st.studierettstatkode IN ('AUTOMATISK', 'CANDMAG', 'DIVERSE',
               'OVERGANG', 'ORDOPPTAK')
       """
        return self.db.query(qry)

class FS(access_FS.FS):
    def __init__(self, db=None, user=None, database=None):
        super(FS, self).__init__(db=db, user=user, database=database)
    # override neccessary classes
    self.student = Student40(self.db)
    self.alumni = Alumni40(self.db)
    self.evu = EVU40(self.db)


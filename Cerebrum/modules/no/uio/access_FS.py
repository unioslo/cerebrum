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

import re
import os
import sys
import time

from Cerebrum import Database,Errors

class FSPerson(object):
    """FSPerson klassen definerer et sett med metoder som kan
    benyttes for å hente ut informasjon om personer fra FS.  De fleste
    metodene returnerer en tuple med kolonnenavn fulgt av en typle med
    dbrows."""

    def __init__(self, db):
        self.db = db
        t = time.localtime()[0:2]
        if t[1] <= 6:
            self.sem = 'V'
        else:
            self.sem = 'H'
        self.year = t[0]
        self.YY = str(t[0])[2:]

    def GetKursFagpersonundsemester(self):
        """Hent ut fagpersoner som har undervisning i inneværende
        eller forrige semester"""

        qry = """
SELECT DISTINCT
       fp.fodselsdato, fp.personnr, p.etternavn, p.fornavn,
       fp.adrlin1_arbeide, fp.adrlin2_arbeide, fp.postnr_arbeide,
       fp.adrlin3_arbeide, fp.adresseland_arbeide,
       fp.telefonnr_arbeide, fp.telefonnr_fax_arb,
       p.telefonnr_hjemsted, fp.stillingstittel_engelsk,
       r.institusjonsnr, r.faknr, r.instituttnr, r.gruppenr,
       r.status_aktiv
FROM fs.person p, fs.fagperson fp,
     fs.fagpersonundsemester r
WHERE r.fodselsdato = fp.fodselsdato AND
      r.personnr = fp.personnr AND
      fp.fodselsdato = p.fodselsdato AND
      fp.personnr = p.personnr AND
      %s
        """ % self.get_termin_aar()
        return (self._get_cols(qry), self.db.query(qry))

    def GetStudinfTilbud(self):
        """Hent personer som har fått tilbud om opptak"""
        qry = """
SELECT DISTINCT
        p.fodselsdato, p.personnr, p.etternavn, p.fornavn
FROM fs.soknadsalternativ sa, fs.person p, fs.opptakstudieprogram osp,
     fs.studieprogram sp
WHERE p.fodselsdato=sa.fodselsdato AND
      p.personnr=sa.personnr AND
      sa.tilbudstatkode IN ('I', 'S') AND
      sa.studietypenr = osp.studietypenr AND
      osp.studieprogramkode = sp.studieprogramkode
        """
        return (self._get_cols(qry), self.db.query(qry))

    def GetStudinfOpptak(self):
        """Hent personer som har opptak ved et studieprogram"""
        qry = """
SELECT s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
       s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
       s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
       p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
       p.adresseland_hjemsted, p.status_reserv_nettpubl, st.studieprogramkode,
       st.studierettstatkode
FROM fs.student s, fs.person p, fs.studierett st
WHERE  p.fodselsdato=s.fodselsdato AND
       p.personnr=s.personnr AND
       p.fodselsdato=st.fodselsdato AND
       p.personnr=st.personnr AND 
       st.studierettstatkode IN (
       'AUTOMATISK', 'AVTALE', 'CANDMAG', 'DIVERSE', 'EKSPRIV',
       'ERASMUS', 'FJERNUND', 'GJEST', 'FULBRIGHT', 'HOSPITANT',
       'KULTURAVTALE', 'KVOTEPROG', 'LEONARDO', 'OVERGANG', 'NUFU',
       'SOKRATES', 'LUBECK', 'NORAD', 'ARKHANG', 'NORDPLUS',
       'ORDOPPTAK', 'PRIVATIST', 'EVU', 'FULLFØRT')"""
        return (self._get_cols(qry), self.db.query(qry))

    def GetStudinfPerm(self):
        """Hent personer som har innvilget permisjon.  Disse vil
        alltid ha opptak, så vi henter bare noen få kolonner"""
        qry = """
SELECT  studieprogramkode, fodselsdato, personnr
FROM fs.innvilget_permisjon
WHERE dato_fra < SYSDATE AND NVL(dato_til, SYSDATE) >= SYSDATE
        """
        return (self._get_cols(qry), self.db.query(qry))

    def GetStudieproginf(self):
        qry = """
SELECT studieprogramkode, status_utdplan, faknr_studieansv,
       instituttnr_studieansv, gruppenr_studieansv
FROM fs.studieprogram"""
        return (self._get_cols(qry), self.db.query(qry))

    def GetStudinfRegkort(self):
        """Hent informasjon om semester-registrering og betaling"""
        qry = """
SELECT DISTINCT
       fodselsdato, personnr, regformkode, dato_endring, dato_opprettet
FROM fs.registerkort r
WHERE %s""" % self.get_termin_aar(only_current=1)
        return (self._get_cols(qry), self.db.query(qry))

    def GetStudinfEvu(self):
        """Hent informasjon om EVU studenter hvor kursets
        avsluttningsdato er mindre enn 6 mnd. siden"""
        qry = """
SELECT d.fodselsdato, d.personnr, p.etternavn, p.fornavn,
       d.adrlin1_hjem, d.adrlin2_hjem, d.postnr_hjem, d.adrlin3_hjem,
       d.adresseland_hjem, p.adrlin1_hjemsted, p.adrlin2_hjemsted,
       p.postnr_hjemsted, p.adrlin3_hjemsted, p.adresseland_hjemsted,
       p.status_reserv_nettpubl, ek.faknr_adm_ansvar,
       ek.instituttnr_adm_ansvar, ek.gruppenr_adm_ansvar
FROM fs.deltaker d, fs.person p, fs.kursdeltakelse kd, fs.etterutdkurs ek
WHERE  p.fodselsdato=d.fodselsdato AND
       p.personnr=d.personnr AND
       d.deltakernr=kd.deltakernr AND
       kd.etterutdkurskode = ek.etterutdkurskode AND
       kd.kurstidsangivelsekode = ek.kurstidsangivelsekode AND
       ek.dato_til > SYSDATE - 180"""
        return (self._get_cols(qry), self.db.query(qry))

    def GetStudinfNaaKlasse_obsolete(self):
        """Hent informasjon om klasser med kullkoder dette semester."""
        qry = """
SELECT s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
       s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
       s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
       p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
       p.adresseland_hjemsted, p.status_reserv_nettpubl
FROM fs.student s, fs.person p, fs.studierett st, fs.naverende_klasse kl
WHERE  p.fodselsdato=s.fodselsdato AND
       p.personnr=s.personnr AND
       p.fodselsdato=st.fodselsdato AND
       p.personnr=st.personnr AND
       st.opphortstudierettstatkode IS NULL AND
       st.status_privatist='N' AND
       kl.personnr = p.personnr AND
       kl.fodselsdato = p.fodselsdato AND
       (kl.kullkode = '%s-%s' OR kl.kullkode = '%s%s')""" % (
            self.sem, self.YY, self.sem, self.YY)
        return (self._get_cols(qry), self.db.query(qry))

    def GetStudinfStudierett_obsolete(self):
        """Hent informasjon om personer som har fått studierett siste 90 dager"""
        qry = """
SELECT s.fodselsdato, s.personnr,
       p.etternavn, p.fornavn,
       s.adrlin1_semadr,s.adrlin2_semadr,
       s.postnr_semadr, s.adrlin3_semadr,
       s.adresseland_semadr,
       p.adrlin1_hjemsted, p.adrlin2_hjemsted,
       p.postnr_hjemsted, p.adrlin3_hjemsted,
       p.adresseland_hjemsted,
       p.status_reserv_nettpubl
FROM fs.student s, fs.person p, fs.studierett st
WHERE  p.fodselsdato=s.fodselsdato and
       p.personnr=s.personnr and
       p.fodselsdato=st.fodselsdato and
       p.personnr=st.personnr and
       st.opphortstudierettstatkode is null and
       st.status_privatist='N' and
       NVL(st.dato_tildelt,SYSDATE-365) > SYSDATE - 90"""
        return (self._get_cols(qry), self.db.query(qry))

    def GetStudinfEvuKurs_obsolete(self):
        """Hent informasjon om studenter på evu-kurs der kurs starter
        om < 14 dager, eller var ferdig for < 14 dager siden"""        
        qry = """
SELECT d.fodselsdato, d.personnr,
       p.etternavn, p.fornavn,
       d.adrlin1_hjem, d.adrlin2_hjem,
       d.postnr_hjem, d.adrlin3_hjem,
       d.adresseland_hjem,
       p.adrlin1_hjemsted, p.adrlin2_hjemsted,
       p.postnr_hjemsted, p.adrlin3_hjemsted,
       p.adresseland_hjemsted,
       p.status_reserv_nettpubl
FROM fs.deltaker d, fs.person p, fs.kursdeltakelse kd, fs.etterutdkurs ek
WHERE  p.fodselsdato=d.fodselsdato and
       p.personnr=d.personnr and
       d.deltakernr=kd.deltakernr and
       kd.etterutdkurskode = ek.etterutdkurskode and
       kd.kurstidsangivelsekode = ek.kurstidsangivelsekode and
       NVL(ek.dato_fra, SYSDATE+1) < SYSDATE + 14 and
       ek.dato_til > SYSDATE - 14"""
        return (self._get_cols(qry), self.db.query(qry))

    def GetAlleEksamener_obsolete(self, fnr=None):
        fodselsdato=None
        personnr=None
        extra=""
        if fnr is not None:
            fodselsdato, personnr = fnr[:-5], fnr[-5:]
            extra=" AND p.personnr=:personnr AND p.fodselsdato=:fodselsdato "
            
        """Returner informasjon om alle eksamensmeldinger for aktive
        studenter ved UiO"""

	# Velg ut studentens eksamensmeldinger for inneværende og
	# fremtidige semestre.  Søket sjekker at studenten har
	# rett til å følge kurset, og at vedkommende er
	# semesterregistrert i inneværende semester (eller,
	# dersom fristen for semesterregistrering dette
	# semesteret ennå ikke er utløpt, hadde
	# semesterregistrert seg i forrige semester).
        qry = """
SELECT m.fodselsdato, m.personnr,
       m.emnekode, m.arstall, m.manednr,
       sprg.studienivakode,
       e.institusjonsnr_reglement, e.faknr_reglement,
       e.instituttnr_reglement, e.gruppenr_reglement, es.studieprogramkode
FROM fs.eksamensmelding m, fs.emne e, fs.studierett st,
     fs.emne_i_studieprogram es, fs.registerkort r, fs.studieprogram sprg,
     fs.person p
WHERE
  m.arstall >= :year AND
  m.fodselsdato = st.fodselsdato AND
  m.personnr = st.personnr AND
  m.fodselsdato = r.fodselsdato AND
  m.personnr = r.personnr AND
  m.fodselsdato = p.fodselsdato AND
  m.personnr = p.personnr AND
  NVL(p.status_dod, 'N') = 'N' AND
  %s %s AND 
  (st.opphortstudierettstatkode IS NULL OR
   st.dato_gyldig_til >= sysdate) AND
  st.status_privatist = 'N' AND
  m.institusjonsnr = e.institusjonsnr AND
  m.emnekode = e.emnekode AND
  m.versjonskode = e.versjonskode AND
  m.institusjonsnr = es.institusjonsnr AND
  m.emnekode = es.emnekode AND
  es.studieprogramkode = st.studieprogramkode AND
  es.studieprogramkode = sprg.studieprogramkode
UNION""" % (self.get_termin_aar(), extra)
	# Velg ut studentens avlagte UiO eksamener i inneværende
	# semester (studenten er fortsatt gyldig student ut
	# semesteret, selv om alle eksamensmeldinger har gått
	# over til å bli eksamensresultater).
	#
	# Søket sjekker _ikke_ at det finnes noen
	# semesterregistrering for inneværende registrering
	# (fordi dette skal være implisitt garantert av FS).
        qry += """
SELECT sp.fodselsdato, sp.personnr,
       sp.emnekode, sp.arstall, sp.manednr,
       sprg.studienivakode,
       e.institusjonsnr_reglement, e.faknr_reglement,
       e.instituttnr_reglement, e.gruppenr_reglement, st.studieprogramkode
FROM fs.studentseksprotokoll sp, fs.emne e, fs.studierett st,
     fs.emne_i_studieprogram es, fs.studieprogram sprg, fs.person p
WHERE
  sp.arstall >= :year AND
  sp.fodselsdato = st.fodselsdato AND
  sp.personnr = st.personnr AND
  sp.fodselsdato = p.fodselsdato AND
  sp.personnr = p.personnr %s AND 
  NVL(p.status_dod, 'N') = 'N' AND
  (st.opphortstudierettstatkode IS NULL OR
   st.DATO_GYLDIG_TIL >= sysdate) AND
  st.status_privatist = 'N' AND
  sp.emnekode = e.emnekode AND
  sp.versjonskode = e.versjonskode AND
  sp.institusjonsnr = e.institusjonsnr AND
  sp.institusjonsnr = '185' AND
  sp.emnekode = es.emnekode AND
  es.studieprogramkode = st.studieprogramkode AND
  es.studieprogramkode = sprg.studieprogramkode
ORDER BY fodselsdato, personnr"""  % extra
        return (self._get_cols(qry),
                self.db.query(qry, {'year': self.year,
                                    'fodselsdato': fodselsdato,
                                    'personnr': personnr}))

    def FinnAlleStudprogSko_obsolete(self):
        qry = """
SELECT DISTINCT
  st.fodselsdato, st.personnr, st.studieprogramkode, sprog.studienivakode,
  sprog.institusjonsnr_studieansv, sprog.faknr_studieansv,
  sprog.instituttnr_studieansv, sprog.gruppenr_studieansv
FROM
  fs.studierett st, fs.studieprogram sprog, fs.person p
WHERE
  st.fodselsdato = p.fodselsdato AND
  st.personnr = p.personnr AND
  NVL(p.status_dod, 'N') = 'N' AND
  st.opphortstudierettstatkode IS NULL AND
  st.status_privatist='N' AND
  st.studieprogramkode = sprog.studieprogramkode AND
  NVL(st.dato_tildelt,SYSDATE-365) > SYSDATE - 90
ORDER BY
  st.fodselsdato, st.personnr, sprog.studienivakode, st.studieprogramkode"""
        return (self._get_cols(qry), self.db.query(qry))

    def get_termin_aar(self, only_current=0):
        yr, mon, md = t = time.localtime()[0:3]
        if mon <= 6:
            # Months January - June == Spring semester
            current = "(r.terminkode LIKE 'V_R' AND r.arstall=%s)\n" % yr;
            if only_current or mon >= 3 or (mon == 2 and md > 15):
                return current
            return "(%s OR (r.terminkode LIKE 'H_ST' AND r.arstall=%d))\n" % (
                current, yr-1)
        # Months July - December == Autumn semester
        current = "(r.terminkode LIKE 'H_ST' AND r.arstall=%d)\n" % yr
        if only_current or mon >= 10 or (mon == 9 and md > 15):
            return current
        return "(%s OR (r.terminkode LIKE 'V_R' AND r.arstall=%d))\n" % (current, yr)

    # TODO: Belongs in a separate file, and should consider using row description
    def _get_cols(self, sql):
        sql = sql[:sql.upper().find("FROM")+4]
        m = re.compile(r'^\s*SELECT\s*(DISTINCT)?(.*)FROM', re.DOTALL | re.IGNORECASE).match(sql)
        if m == None:
            raise InternalError, "Unreconginzable SQL!"
        return [cols.strip() for cols in m.group(2).split(",")]

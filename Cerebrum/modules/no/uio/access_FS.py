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

class FS(object):
    """FS klassen definerer et sett med metoder som kan benyttes for å
    hente ut informasjon om personer og OU-er fra FS. De fleste
    metodene returnerer en tuple med kolonnenavn fulgt av en tuple med
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


    # TODO: Belongs in a separate file, and should consider using row description
    def _get_cols(self, sql):
        sql = sql[:sql.upper().find("FROM")+4]
        m = re.compile(r'^\s*SELECT\s*(DISTINCT)?(.*)FROM', re.DOTALL | re.IGNORECASE).match(sql)
        if m == None:
            raise InternalError, "Unreconginzable SQL!"
        return [cols.strip() for cols in m.group(2).split(",")]


##################################################################
# Metoder for personer:
##################################################################


    def GetKursFagpersonundsemester(self):
	"""Disse skal gis affiliation tilknyttet med kode fagperson 
        til stedskoden faknr+instituttnr+gruppenr
        Hent ut fagpersoner som har undervisning i inneværende
        eller forrige semester"""

        qry = """
SELECT DISTINCT 
      fp.fodselsdato, fp.personnr, p.etternavn, p.fornavn,
      fp.adrlin1_arbeide, fp.adrlin2_arbeide, fp.postnr_arbeide,
      fp.adrlin3_arbeide, fp.adresseland_arbeide,
      fp.telefonnr_arbeide, fp.telefonnr_fax_arb,
      p.adrlin1_hjemsted, p.adrlin2_hjemsted, p.postnr_hjemsted,
      p.adrlin3_hjemsted, p.adresseland_hjemsted, 
      p.telefonnr_hjemsted, fp.stillingstittel_engelsk, 
      r.institusjonsnr, r.faknr, r.instituttnr, r.gruppenr,
      r.status_aktiv, r.status_publiseres
FROM fs.person p, fs.fagperson fp,
     fs.fagpersonundsemester r
WHERE r.fodselsdato = fp.fodselsdato AND
      r.personnr = fp.personnr AND
      fp.fodselsdato = p.fodselsdato AND
      fp.personnr = p.personnr AND 
      %s
      %s
        """ % (self.get_termin_aar(),self.is_alive())

        return (self._get_cols(qry), self.db.query(qry))


    def GetStudinfTilbud(self, institutsjonsnr=0):
        """Hent personer som har fått tilbud om opptak
	Disse skal gis affiliation student med kode tilbud til 
        stedskoden sp.faknr_studieansv+sp.instituttnr_studieansv+
        sp.gruppenr_studieansv. Personer som har fått tilbud om 
        opptak til et studieprogram ved UiO vil inngå i denne 
        kategorien. Alle søkere til studierved UiO registreres 
        i tabellen fs.soknadsalternativ og informasjon om noen 
        har fått tilbud om opptak hentes også derfra (feltet 
        fs.soknadsalternativ.tilbudstatkode er et godt sted å 
        begynne å lete etter personer som har fått tilbud)."""

        qry = """
SELECT DISTINCT
      p.fodselsdato, p.personnr, p.etternavn, p.fornavn, 
      osp.studieprogramkode, p.adrlin1_hjemsted, p.adrlin2_hjemsted,
      p.postnr_hjemsted, p.adrlin3_hjemsted, p.adresseland_hjemsted,
      p.sprakkode_malform
FROM fs.soknadsalternativ sa, fs.person p, fs.opptakstudieprogram osp,
     fs.studieprogram sp
WHERE p.fodselsdato=sa.fodselsdato AND
      p.personnr=sa.personnr AND
      sa.institusjonsnr='%s' AND 
      sa.opptakstypekode = 'NOM' AND
      sa.tilbudstatkode IN ('I', 'S') AND
      sa.studietypenr = osp.studietypenr AND
      osp.studieprogramkode = sp.studieprogramkode
      %s
      """ % (institutsjonsnr, self.is_alive())
        return (self._get_cols(qry), self.db.query(qry))


    def GetStudinfOpptak(self):
	aar, maned = time.localtime()[0:2]
        """Hent personer med opptak til et studieprogram ved UiO
	som i løpet av de to siste år har avlagt en eksamen
	eller har vært eksamensmeldt i minst ett emne ved UiO 
	i løpet av de to siste år inngår i denne gruppen
        Disse får affiliation student med kode opptak 
        til stedskoden sp.faknr_studieansv+sp.instituttnr_studieansv+
        sp.gruppenr_studieansv""" 

        qry = """
SELECT DISTINCT s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
       s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
       s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
       p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
       p.adresseland_hjemsted, p.status_reserv_nettpubl, 
       p.sprakkode_malform,st.studieprogramkode, st.studierettstatkode
FROM fs.student s, fs.person p, fs.studierett st, fs.eksmeldinglogg el,
     fs.studieprogram sp
WHERE  p.fodselsdato=s.fodselsdato AND
       p.personnr=s.personnr AND
       p.fodselsdato=st.fodselsdato AND
       p.personnr=st.personnr AND 
       st.studieprogramkode = sp.studieprogramkode AND
       p.fodselsdato=el.fodselsdato AND
       p.personnr=el.personnr AND 
       st.studierettstatkode IN (
       'AUTOMATISK', 'AVTALE', 'CANDMAG', 'DIVERSE', 'EKSPRIV',
       'ERASMUS', 'FJERNUND', 'GJEST', 'FULBRIGHT', 'HOSPITANT',
       'KULTURAVTALE', 'KVOTEPROG', 'LEONARDO', 'OVERGANG', 'NUFU',
       'SOKRATES', 'LUBECK', 'NORAD', 'ARKHANG', 'NORDPLUS',
       'ORDOPPTAK','FULLFØRT','EVU', 'PRIVATIST') AND
       ((el.arstall = %s and el.manednr <=%s) OR
       (el.arstall = %s) OR 
       (el.arstall = %s and el.manednr >= %s))
       %s	
       """ % (aar, maned, aar-1, aar-2, maned, self.is_alive())
        # Man kan ikke sjekke el.aarstall >= i fjor ettersom tabellen
        # også inneholder fremtidige meldinger.

        return (self._get_cols(qry), self.db.query(qry))

    def GetStudinfAktiv(self):
        """Hent fødselsnummer+studieprogram for alle aktive 
        studenter. 
	Som aktive studenter regner vi alle studenter med opptak 
	til et studieprogram som samtidig har en eksamensmelding
	i et emne som kan inngå i det studieprogrammet, eller
	som har bekreftet sin utdanningsplan
	Disse får affiliation student med kode aktiv til 
        sp.faknr_studieansv+sp.instituttnr_studieansv+
        sp.gruppenr_studieansv"""

        qry = """
SELECT DISTINCT
      s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
      s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
      s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
      p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
      p.adresseland_hjemsted, p.status_reserv_nettpubl, 
      p.sprakkode_malform, sp.studieprogramkode
FROM fs.studieprogram sp, fs.studierett st, fs.student s,
     fs.registerkort r, fs.eksamensmelding em, fs.person p,
     fs.emne_i_studieprogram es
WHERE s.fodselsdato=p.fodselsdato AND
      s.personnr=p.personnr AND
      p.fodselsdato=r.fodselsdato AND
      p.personnr=r.personnr AND
      p.fodselsdato=st.fodselsdato AND
      p.personnr=st.personnr AND
      p.fodselsdato=em.fodselsdato AND
      p.personnr=em.personnr AND
      es.studieprogramkode=sp.studieprogramkode AND
      em.emnekode=es.emnekode AND
      st.status_privatist='N' AND 
      st.studieprogramkode=sp.studieprogramkode AND
      r.regformkode IN ('STUDWEB','DOKTORREG','MANUELL') AND
      (st.opphortstudierettstatkode IS NULL OR
      st.dato_gyldig_til >= sysdate) AND
      %s %s
UNION """ %(self.get_termin_aar(only_current=1),self.is_alive()) 

	qry = qry + """
SELECT DISTINCT
     s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
     s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
     s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
     p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
     p.adresseland_hjemsted, p.status_reserv_nettpubl,
     p.sprakkode_malform, sp.studieprogramkode
FROM fs.person p, fs.student s, fs.studierett st,
     fs.studprogstud_planbekreft r, fs.studieprogram sp
WHERE p.fodselsdato=s.fodselsdato AND
      p.personnr=s.personnr AND
      p.fodselsdato=st.fodselsdato AND
      p.personnr=st.personnr AND
      p.fodselsdato=r.fodselsdato AND
      p.personnr=r.personnr AND
      sp.status_utdplan='J' AND
      st.status_privatist='N' AND     
      r.studieprogramkode=st.studieprogramkode AND
      st.studieprogramkode=sp.studieprogramkode AND
      (st.opphortstudierettstatkode IS NULL OR
      st.dato_gyldig_til >= sysdate) AND
      r.dato_bekreftet < SYSDATE
      %s
      """ % (self.is_alive())   
     	return (self._get_cols(qry), self.db.query(qry))


    def GetStudinfPermisjon(self):
        """Hent personer som har innvilget permisjon.  Disse vil
        alltid ha opptak, så vi henter bare noen få kolonner.
        Disse tildeles affiliation student med kode permisjon
	til sp.faknr_studieansv, sp.instituttnr_studieansv, 
        sp.gruppenr_studieansv"""

        qry = """
SELECT  pe.studieprogramkode, pe.fodselsdato, pe.personnr,
	pe.fraverarsakkode_hovedarsak 
FROM fs.innvilget_permisjon pe, fs.person p
WHERE p.fodselsdato = pe.fodselsdato AND
      p.personnr = pe.personnr AND
      dato_fra < SYSDATE AND NVL(dato_til, SYSDATE) >= SYSDATE
      %s
        """ % self.is_alive()
        return (self._get_cols(qry), self.db.query(qry))


    def GetStudinfPrivatist(self):
	"""Hent personer som er uekte privatister ved UiO, 
        dvs. som er eksamensmeldt til et emne i et studieprogram 
        de ikke har opptak til. Disse tildeles affiliation privatist
        til stedet som eier studieprogrammet de har opptak til."""

	qry = """
SELECT s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
       s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
       s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
       p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
       p.adresseland_hjemsted, p.status_reserv_nettpubl, 
       p.sprakkode_malform, sp.studieprogramkode
FROM fs.student s, fs. person p, fs.studierett st, 
     fs.studieprogram sp, fs.registerkort r,
     fs.eksamensmelding em, fs.emne_i_studieprogram es 
WHERE s.fodselsdato=p.fodselsdato AND
      s.personnr=p.personnr AND
      p.fodselsdato=st.fodselsdato AND
      p.personnr=st.personnr AND
      p.fodselsdato=r.fodselsdato AND
      p.personnr=r.personnr AND
      p.fodselsdato=em.fodselsdato AND
      p.personnr=em.personnr AND
      st.status_privatist='J' AND
      es.studieprogramkode=sp.studieprogramkode AND
      em.emnekode <> es.emnekode AND
      st.studieprogramkode=sp.studieprogramkode AND      
      r.regformkode IN ('STUDWEB','DOKTORREG','MANUELL') AND
      (st.opphortstudierettstatkode IS NULL OR
      st.dato_gyldig_til >= sysdate) AND
      %s %s
      """ % (self.get_termin_aar(only_current=1),self.is_alive())
        return (self._get_cols(qry), self.db.query(qry))


    def GetStudinfEvu(self):
    	"""Hent info om personer som er ekte EVU-studenter ved
    	UiO, dvs. er registrert i EVU-modulen i tabellen 
    	fs.deltaker"""

 	qry = """
SELECT DISTINCT 
       p.fodselsdato, p.personnr, p.etternavn, p.fornavn,
       d.adrlin1_job, d.adrlin2_job, d.postnr_job, 
       d.adrlin3_job, d.adresseland_job, d.adrlin1_hjem, 
       d.adrlin2_hjem, d.postnr_hjem, d.adrlin3_hjem,
       d.adresseland_hjem, p.adrlin1_hjemsted, p.status_reserv_nettpubl, 
       p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
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
      %s
      """ % self.is_alive()
	return (self._get_cols(qry), self.db.query(qry))
      

    def GetStudieproginf(self):
	"""For hvert definerte studieprogram henter vi 
	informasjon om utd_plan og eier samt studieprogkode"""
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


    def GetAlleEksamener(self):
	"""Hent ut alle eksamensmeldinger i nåværende sem.
	samt fnr for oppmeldte(topics.xml)"""
	aar = time.localtime()[0:1]
	qry = """
SELECT p.fodselsdato, p.personnr, e.emnekode, e.studieprogramkode
FROM fs.person p, fs.eksamensmelding e
WHERE p.fodselsdato=e.fodselsdato AND
      p.personnr=e.personnr AND
      e.arstall=%s 
      %s
ORDER BY fodselsdato, personnr
      """ %(aar[0],self.is_alive())                            
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


    def is_alive(self):
	return "AND NVL(p.status_dod, 'N') = 'N'\n"

	
##################################################################
# Metoder for OU-er:
##################################################################


    def GetAlleOUer(self, institusjonsnr=0):
	"""Hent data om stedskoder registrert i FS"""
        qry = """
SELECT DISTINCT
  faknr, instituttnr, gruppenr, stedakronym, stednavn_bokmal,
  faknr_org_under, instituttnr_org_under, gruppenr_org_under,
  adrlin1, adrlin2, postnr, telefonnr, faxnr,
  adrlin1_besok, adrlin2_besok, postnr_besok, url,
  bibsysbeststedkode
FROM fs.sted
WHERE institusjonsnr='%s'
""" % institusjonsnr
        return (self._get_cols(qry), self.db.query(qry))
    
##################################################################
## E-post adresser i FS:
##################################################################

    def GetAllPersonsEmail(self):
        qry = """
SELECT fodselsdato, personnr, emailadresse
FROM fs.person"""
        return (self._get_cols(qry), self.db.query(qry))

    def WriteMailAddr(self, fodselsdato, personnr, email):
        self.execute("""
UPDATE fs.person
SET emailadresse=:email
WHERE fodselsdato=:fodselsdato AND personnr=:personnr""", locals())

# -*- coding: iso-8859-1 -*-
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

        # Simple SQL-parser. Read TODO above.
        #  Problem: Some statements in a SELECT ... are not colomn-names
        #  Ad.hoc solution: "TO_CHAR(e.dato_til,'YYYY-MM-DD')" becomes
        #                   "to_char_e_dato_til_YYYY-MM-DD_"
        #  Supports '... AS foo'
        ret = []
        tmp = ""
        lpar = rpar = 0
        patt = re.compile("^.*\s+AS\s+\"?([a-zA-Z0-9_]+)\"?\s*", re.IGNORECASE)
        for cols in m.group(2).split(","):
            cols = re.sub('\'', '', cols)
            cols = cols.strip()
            chars = list(cols)
            for c in chars:
                if c == '(': lpar+=1
                elif c == ')': rpar+=1
            if lpar == rpar:
                if tmp:
                    tmp = tmp + "," + cols
                else:
                    tmp = cols
                lpar = rpar = 0
                mobj = patt.match(tmp)
                if mobj:
                    ret.append(mobj.group(1))
                else:
                    ret.append(re.sub('[(),]', '_', tmp))
                tmp = ""
            else:
                if tmp:
                    tmp = tmp + "," + cols
                else:
                    tmp = cols

        return ret

        # return [ self._clean_col_name(cols) for cols in m.group(2).split(",")]

    def _clean_col_name(self, col):
        lpar = re.compile("\(")
        rpar = re.compile("\)")
        patt = re.compile("^.*\s+AS\s+\"?([a-zA-Z0-9_]+)\"?\s*")
        mobj = patt.match(col)
        if mobj:
            print "1: %s" % mobj.group(1)
            return mobj.group(1)
        print "2: %s" % col.strip()
        return col.strip()


##################################################################
# Metoder for personer:
#
# Skal hente et sett med data om personer:
#  - Fødseldato
#  - Personnr
#  - Efternavn
#  - Fornavn
#  - Tittel
#  - Adresse(r)
#  - Telefonnr/Fax
#  - Tilhørighet (Sted/Studieprogram)
#  - Status_publiseres
#  - Kjønn
#  - Status_Død
#
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
      r.status_aktiv, r.status_publiseres, p.kjonn, p.status_dod
FROM fs.person p, fs.fagperson fp,
     fs.fagpersonundsemester r
WHERE r.fodselsdato = fp.fodselsdato AND
      r.personnr = fp.personnr AND
      fp.fodselsdato = p.fodselsdato AND
      fp.personnr = p.personnr AND 
      %s
        """ % (self.get_termin_aar())

        return (self._get_cols(qry), self.db.query(qry))


    def GetStudinfTilbud(self, institutsjonsnr=0):
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
      """ % (institutsjonsnr, self.is_alive())
        return (self._get_cols(qry), self.db.query(qry))

    def _GetOpptakQuery(self):
	aar, maned = time.localtime()[0:2]
        """Hent personer med opptak til et studieprogram ved
        institusjonen og som i løpet av siste år har avlagt en eksamen
        eller har vært eksamensmeldt i minst ett emne ved
        institusjonen i løpet av siste år inngår i denne gruppen, samt
        de som har fått opptak de siste 365 dager.
        Med untak av de som har 'studierettstatkode' lik 'PRIVATIST'
        skal alle disse får affiliation student med kode 'opptak'
        ('privatist' for disse) til stedskoden sp.faknr_studieansv +
        sp.instituttnr_studieansv + sp.gruppenr_studieansv""" 

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
       st.opphortstudierettstatkode IS NULL AND
       st.studierettstatkode IN (RELEVANTE_STUDIERETTSTATKODER)
       AND
       ((((el.arstall = %s and el.manednr <=%s) OR
        (el.arstall = %s and el.manednr >= %s))) OR
       st.dato_tildelt > sysdate - 365)
       """ % (aar, maned, aar-1, maned)
        # Man kan ikke sjekke el.aarstall >= i fjor ettersom tabellen
        # også inneholder fremtidige meldinger.
        return qry
    

    def GetStudinfOpptak(self):
        studierettstatkoder = """'AUTOMATISK', 'AVTALE', 'CANDMAG',
       'DIVERSE', 'EKSPRIV', 'ERASMUS', 'FJERNUND', 'GJEST',
       'FULBRIGHT', 'HOSPITANT', 'KULTURAVTALE', 'KVOTEPROG',
       'LEONARDO', 'OVERGANG', 'NUFU', 'SOKRATES', 'LUBECK', 'NORAD',
       'ARKHANG', 'NORDPLUS', 'ORDOPPTAK', 'EVU'"""
        qry = self._GetOpptakQuery().replace("RELEVANTE_STUDIERETTSTATKODER",
                                             studierettstatkoder)
        return (self._get_cols(qry), self.db.query(qry))

    def GetAlumni(self):
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
        return (self._get_cols(qry), self.db.query(qry))

    def GetPrivatistStudieprogram(self):
        studierettstatkoder = "'PRIVATIST'"
        qry = self._GetOpptakQuery().replace("RELEVANTE_STUDIERETTSTATKODER",
                                             studierettstatkoder)
        return (self._get_cols(qry), self.db.query(qry))

    def GetStudinfAktiv(self):
        """Hent fødselsnummer+studieprogram for alle aktive 
        studenter.  Som aktive studenter regner vi alle studenter med
   	opptak til et studieprogram som samtidig har en
	eksamensmelding i et emne som kan inngå i dette
	studieprogrammet, eller som har bekreftet sin utdanningsplan
	Disse får affiliation student med kode aktiv til 
        sp.faknr_studieansv+sp.instituttnr_studieansv+
        sp.gruppenr_studieansv.  Vi har alt hentet opplysninger om
	adresse ol. efter som de har opptak.  Henter derfor kun
        fødselsnummer og studieprogram.  Medfører at du kan få med
        linjer som du ikke har personinfo for, dette vil være snakk om
        ekte-døde personer."""

        qry = """
SELECT DISTINCT
      s.fodselsdato, s.personnr, sp.studieprogramkode
FROM fs.studieprogram sp, fs.studierett st, fs.student s,
     fs.registerkort r, fs.eksamensmelding em,
     fs.emne_i_studieprogram es
WHERE s.fodselsdato=r.fodselsdato AND
      s.personnr=r.personnr AND
      s.fodselsdato=st.fodselsdato AND
      s.personnr=st.personnr AND
      s.fodselsdato=em.fodselsdato AND
      s.personnr=em.personnr AND
      es.studieprogramkode=sp.studieprogramkode AND
      em.emnekode=es.emnekode AND
      st.status_privatist='N' AND 
      st.studieprogramkode=sp.studieprogramkode AND
      r.regformkode IN ('STUDWEB','DOKTORREG','MANUELL') AND
      (st.opphortstudierettstatkode IS NULL OR
      st.dato_gyldig_til >= sysdate) AND
      %s
UNION """ %(self.get_termin_aar(only_current=1))

        qry = qry + """
SELECT DISTINCT
     s.fodselsdato, s.personnr, sp.studieprogramkode
FROM fs.student s, fs.studierett st,
     fs.studprogstud_planbekreft r, fs.studieprogram sp
WHERE s.fodselsdato=st.fodselsdato AND
      s.personnr=st.personnr AND
      s.fodselsdato=r.fodselsdato AND
      s.personnr=r.personnr AND
      sp.status_utdplan='J' AND
      st.status_privatist='N' AND     
      r.studieprogramkode=st.studieprogramkode AND
      st.studieprogramkode=sp.studieprogramkode AND
      (st.opphortstudierettstatkode IS NULL OR
      st.dato_gyldig_til >= sysdate) AND
      r.dato_bekreftet < SYSDATE
      """ 
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
      AND %s
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
       p.sprakkode_malform, p.kjonn, em.emnekode
FROM fs.student s, fs. person p, fs.registerkort r,
     fs.eksamensmelding em
WHERE s.fodselsdato=p.fodselsdato AND
      s.personnr=p.personnr AND
      p.fodselsdato=r.fodselsdato AND
      p.personnr=r.personnr AND
      p.fodselsdato=em.fodselsdato AND
      p.personnr=em.personnr AND
       %s AND %s AND
      NOT EXISTS
      (SELECT 'x' FROM fs.studierett st, fs.emne_i_studieprogram es
       WHERE p.fodselsdato=st.fodselsdato AND
             p.personnr=st.personnr AND
             es.emnekode=em.emnekode AND
             es.studieprogramkode = st.studieprogramkode AND
             (st.opphortstudierettstatkode IS NULL OR
              st.dato_gyldig_til >= SYSDATE))
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
      AND %s
      """ % self.is_alive()
	return (self._get_cols(qry), self.db.query(qry))
      

    def GetStudieproginf(self):
	"""For hvert definerte studieprogram henter vi 
	informasjon om utd_plan og eier samt studieprogkode"""
        qry = """

SELECT studieprogramkode, status_utdplan, institusjonsnr_studieansv, faknr_studieansv,
       instituttnr_studieansv, gruppenr_studieansv, studienivakode
FROM fs.studieprogram"""
        return (self._get_cols(qry), self.db.query(qry))

    def GetEmneinf(self):
	"""For hvert definerte Emne henter vi informasjon om 
           ansvarlig sted."""
        qry = """

SELECT e.emnekode, e.versjonskode, e.institusjonsnr_reglement,
       e.faknr_reglement, e.instituttnr_reglement, e.gruppenr_reglement, 
       e.studienivakode
FROM fs.emne e
WHERE e.arstall_eks_siste is NULL OR
      e.arstall_eks_siste < %s""" % self.year
        return (self._get_cols(qry), self.db.query(qry))


    def GetStudinfRegkort(self):

        """Hent informasjon om semester-registrering og betaling"""
        qry = """
SELECT DISTINCT
       fodselsdato, personnr, regformkode, dato_endring, dato_opprettet
FROM fs.registerkort r
WHERE %s""" % self.get_termin_aar(only_current=1)
        return (self._get_cols(qry), self.db.query(qry))


    def GetDod(self):
        """Henter en liste med de personer som ligger i FS og som er
           registrert som død.  Listen kan sikkert kortes ned slik at
           man ikke tar alle, men i denne omgang så gjør vi det
           slik."""
        qry = """
SELECT p.fodselsdato, p.personnr
FROM   fs.person p
WHERE  p.status_dod = 'J'"""
        return (self._get_cols(qry), self.db.query(qry))


    def GetAlleEksamener(self):
	"""Hent ut alle eksamensmeldinger i nåværende sem.
	samt fnr for oppmeldte(topics.xml)"""
        # TODO: Det er mulig denne skal splittes i to søk, ett som
        # returnerer lovlige, og et som returnerer "ulovlige"
        # eksamensmeldinger (sistnevnte er vel GetStudinfPrivatist?)
	aar = time.localtime()[0:1]
	qry = """
SELECT p.fodselsdato, p.personnr, e.emnekode, e.studieprogramkode
FROM fs.person p, fs.eksamensmelding e
WHERE p.fodselsdato=e.fodselsdato AND
      p.personnr=e.personnr AND
      e.arstall=%s 
      AND %s
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
	return "NVL(p.status_dod, 'N') = 'N'\n"

###################################################################
# Studinfo-metoder
# Hent data om eksamensmeldinger, opptak , utdanningsplan og semreg
# for en gitt person. Disse brukes til å vise studentstaus for en
# person i BOFH.
###################################################################

    def GetStudentEksamen(self,fnr,pnr):
	"""Hent alle eksamensmeldinger for en student for nåværende
           semester"""
        qry = """
SELECT DISTINCT
  em.emnekode, em.dato_opprettet
FROM fs.eksamensmelding em, fs.person p
WHERE em.fodselsdato=:fnr AND
      em.personnr=:pnr AND
      em.fodselsdato=p.fodselsdato AND
      em.personnr=p.personnr 
      AND %s
        """ % self.is_alive()
        return (self._get_cols(qry), self.db.query(qry, {'fnr': fnr, 'pnr': pnr}))

    def GetStudentStudierett(self,fnr,pnr):
	"""Hent info om alle studierett en student har eller har hatt"""
        qry = """
SELECT DISTINCT
  st.studieprogramkode, st.studierettstatkode, st.dato_tildelt,
  st.dato_gyldig_til, st.status_privatist
FROM fs.studierett st, fs.person p
WHERE st.fodselsdato=:fnr AND
      st.personnr=:pnr AND
      st.fodselsdato=p.fodselsdato AND
      st.personnr=p.personnr 
      AND %s
        """ % self.is_alive()
        return (self._get_cols(qry), self.db.query(qry, {'fnr': fnr, 'pnr': pnr}))

    def GetEmneIStudProg(self,emne):
        """Hent alle studieprogrammer et gitt emne kan inngå i."""
        qry = """
SELECT DISTINCT 
  studieprogramkode   
FROM fs.emne_i_studieprogram
WHERE emnekode = :emne
       """ 
        return (self._get_cols(qry), self.db.query(qry, {'emne': emne}))

    def GetStudentSemReg(self,fnr,pnr):
        """Hent data om semesterregistrering for student i nåværende semester."""
        qry = """
SELECT DISTINCT
  r.regformkode, r.betformkode, r.dato_betaling, r.dato_regform_endret
FROM fs.registerkort r, fs.person p
WHERE r.fodselsdato = :fnr AND
      r.personnr = :pnr AND
      %s AND
      r.fodselsdato = p.fodselsdato AND
      r.personnr = p.personnr AND
      %s
        """ %(self.get_termin_aar(only_current=1),self.is_alive())
	return (self._get_cols(qry), self.db.query(qry, {'fnr': fnr, 'pnr': pnr}))

    def GetStudentUtdPlan(self,fnr,pnr):
        """Hent opplysninger om utdanningsplan for student"""
        qry = """
SELECT DISTINCT
  utdp.studieprogramkode, utdp.terminkode_bekreft, utdp.arstall_bekreft,
  utdp.dato_bekreftet
FROM fs.studprogstud_planbekreft utdp, fs.person p
WHERE utdp.fodselsdato = :fnr AND
      utdp.personnr = :pnr AND
      utdp.fodselsdato = p.fodselsdato AND
      utdp.personnr = p.personnr AND
      %s
        """ % self.is_alive()
	return (self._get_cols(qry), self.db.query(qry, {'fnr': fnr, 'pnr': pnr}))
    
	
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


##################################################################
## Metoder for grupper:
##################################################################

    def get_curr_semester(self):
        mon = time.localtime()[1]
        # Months January - June == Spring semester
        if mon <= 6:
            return 'VÅR'
        # Months July - December == Autumn semester
        return 'HØST' 


    def GetUndervEnhetAll(self, yr=time.localtime()[0], sem=None):
        if sem == None:
            sem=self.get_curr_semester()
            
        qry = """
SELECT
  ue.institusjonsnr, ue.emnekode, ue.versjonskode, ue.terminkode,
  ue.arstall, ue.terminnr, e.institusjonsnr_kontroll, e.faknr_kontroll,
  e.instituttnr_kontroll, e.gruppenr_kontroll, e.emnenavn_bokmal
FROM
  fs.undervisningsenhet ue, fs.emne e, fs.arstermin t
WHERE
  ue.institusjonsnr = e.institusjonsnr AND
  ue.emnekode       = e.emnekode AND
  ue.versjonskode   = e.versjonskode AND
  ue.terminkode IN ('VÅR', 'HØST') AND
  ue.terminkode = t.terminkode AND
  (ue.arstall > %s OR
   (ue.arstall = %s AND
    EXISTS(SELECT 'x' FROM fs.arstermin tt
           WHERE tt.terminkode = '%s' AND
                 t.sorteringsnokkel >= tt.sorteringsnokkel)))
  """ % (yr, yr, sem)
        
        return (self._get_cols(qry), self.db.query(qry))


    def GetUndAktivitet(self, yr=time.localtime()[0], sem=None):
        if sem == None:
            sem=self.get_curr_semester()
            
        qry = """
SELECT
  ua.institusjonsnr, ua.emnekode, ua.versjonskode,
  ua.terminkode, ua.arstall, ua.terminnr, ua.aktivitetkode,
  ua.undpartilopenr, ua.disiplinkode, ua.undformkode, ua.aktivitetsnavn
FROM
  fs.undaktivitet ua
WHERE
  ua.arstall    = %s AND
  ua.terminkode = '%s' AND
  ua.undpartilopenr IS NOT NULL AND
  ua.disiplinkode IS NOT NULL AND
  ua.undformkode IS NOT NULL
  """ % (yr, sem)
        
        return (self._get_cols(qry), self.db.query(qry))

    
    def GetEvuKurs(self, date=time.localtime()):
        d = time.strftime("%Y-%m-%d", date)
        qry = """
SELECT e.etterutdkurskode, e.kurstidsangivelsekode, e.etterutdkursnavn,
       e.institusjonsnr_adm_ansvar, e.faknr_adm_ansvar, e.instituttnr_adm_ansvar,
       e.gruppenr_adm_ansvar, TO_CHAR(e.dato_til,'YYYY-MM-DD') AS dato_til
FROM fs.etterutdkurs e
WHERE NVL(TO_DATE('%s', 'YYYY-MM-DD'), SYSDATE)
        BETWEEN (e.dato_fra-14) AND (e.dato_til+14)
        """ % d
        
        return (self._get_cols(qry), self.db.query(qry))


    def GetAktivitetEvuKurs(self, kurs, tid):
        qry = """
SELECT k.etterutdkurskode, k.kurstidsangivelsekode, k.aktivitetskode,
       k.aktivitetsnavn
FROM fs.kursaktivitet k
WHERE k.etterutdkurskode='%s' AND
      k.kurstidsangivelsekode='%s'
      """ % (kurs, tid)

        return (self._get_cols(qry), self.db.query(qry)) 

    def GetAnsvEvuKurs(self, kurs, tid):
        qry = """
SELECT k.fodselsdato, k.personnr
FROM fs.kursfagansvarlig k
WHERE k.etterutdkurskode=:kurs AND
      k.kurstidsangivelsekode=:tid"""
        return (self._get_cols(qry),
                self.db.query(qry, {'kurs': kurs, 'tid': tid}))

    def GetStudEvuKurs(self, kurs, tid):
        qry = """
SELECT d.fodselsdato, d.personnr
FROM fs.deltaker d, fs.kursdeltakelse k
WHERE k.etterutdkurskode=:kurs AND
      k.kurstidsangivelsekode=:tid AND
      k.deltakernr=d.deltakernr AND
      d.fodselsdato IS NOT NULL AND
      d.personnr IS NOT NULL"""
        return (self._get_cols(qry),
                self.db.query(qry, {'kurs': kurs, 'tid': tid}))

    def GetStudUndAktivitet(self, Instnr, emnekode, versjon, termk,
                            aar, termnr, aktkode):
        qry = """
SELECT
  su.fodselsdato, su.personnr
FROM
  FS.STUDENT_PA_UNDERVISNINGSPARTI su,
  FS.undaktivitet ua
WHERE
  ua.institusjonsnr = :instnr AND
  ua.emnekode       = :emnekode AND
  ua.versjonskode   = :versjon AND
  ua.terminkode     = :terminkode AND
  ua.arstall        = :arstall AND
  ua.terminnr       = :terminnr AND
  ua.aktivitetkode  = :aktkode AND
  su.terminnr       = ua.terminnr       AND
  su.institusjonsnr = ua.institusjonsnr AND
  su.emnekode       = ua.emnekode       AND
  su.versjonskode   = ua.versjonskode   AND
  su.terminkode     = ua.terminkode     AND
  su.arstall        = ua.arstall        AND
  su.undpartilopenr = ua.undpartilopenr AND
  su.disiplinkode   = ua.disiplinkode   AND
  su.undformkode    = ua.undformkode"""

        return (self._get_cols(qry),
                self.db.query(qry, {
            'instnr': Instnr,
            'emnekode': emnekode,
            'versjon': versjon,
            'terminkode': termk,
            'arstall': aar,
            'terminnr': termnr,
            'aktkode': aktkode}))

    # GetAnsvUndervEnhet
    #
    #   Finner alle som er ansvarlige for undervisning av et gitt emne
    #
    #   Henter fra:
    #
    #          * FS.UNDERVISNINGSENHET (som inneholder samme verdi som
    #            FS.emne jmf. Geir Vangen)
    #
    #          * FS.UNDERVISNINGSANSVARLIG
    #
    #          * FS.UNDAKTIVITET_LERER (for undervisningsaktiviteter med
    #            undervisningsform `forelesning').
    #
    # Input:
    #
    #  * Institusjonsnr ('185' -> UiO)
    #  * Emnekode       (VC(12))
    #  * Versonskode    (VC(3))
    #  * Terminkode     (VC(4))
    #  * Årstall        (N(4))
    #  * Terminnr       (N(4))
    #
    # Returnerer en liste av følgende lister:
    #
    #  * Fødselsdato    (N(6))
    #  * Personnr       (N(5))
    #  * Publiseres     ('J'/'N')
    #
    # For gitt emne (se input)
    #
    def GetAnsvUndervEnhet(self, Instnr, emnekode, versjon,
                           termk, aar, termnr):
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

        return (self._get_cols(qry),
                self.db.query(qry, {
            'instnr': Instnr,
            'emnekode': emnekode,
            'versjon': versjon,
            'terminkode': termk,
            'arstall': aar,
            'terminnr': termnr}))

    def GetAnsvUndAktivitet(self, Instnr, emnekode, versjon, termk,
                            aar, termnr, aktkode):
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

        return (self._get_cols(qry),
                self.db.query(qry, {
            'instnr': Instnr,
            'emnekode': emnekode,
            'versjon': versjon,
            'terminkode': termk,
            'arstall': aar,
            'terminnr': termnr,
            'aktkode': aktkode}))

    # GetStudUndervEnhet
    #
    #   Gir en oversikt over hvilke studenter som følger et gitt emne.
    #   Lister alle som er undervisningsmeldt til et emne og/eller som er
    #   meldt til eksamen i emnet.
    #
    # Input:
    #
    #  * Institusjonsnr ('185' -> UiO)
    #  * Emnekode       (VC(12))
    #  * Versonskode    (VC(3))
    #  * Terminkode     (VC(4))
    #  * Årstall        (N(4))
    #  * Terminnr       (N(4))
    #
    # Returnerer en liste av følgende lister:
    #
    #  * Fødselsdato    (N(6))
    #  * Personnr       (N(5))
    #
    # For gitt emne (se input)
    #
    def GetStudUndervEnhet(self, Instnr, emnekode, versjon, termk, aar, termnr):
        qry = """
SELECT
  fodselsdato, personnr
FROM
  FS.UNDERVISNINGSMELDING
WHERE
  institusjonsnr = :instnr AND
  emnekode       = :emnekode AND
  versjonskode   = :versjon AND
  terminkode     = :terminkode AND
  arstall        = :arstall AND
  terminnr       = :terminnr
UNION
SELECT
  fodselsdato, personnr
FROM
  FS.EKSAMENSMELDING
WHERE
  institusjonsnr = :instnr AND
  emnekode       = :emnekode AND
  versjonskode   = :versjon AND
  arstall       >= :arstall"""
        return (self._get_cols(qry),
                self.db.query(qry, {
            'instnr': Instnr,
            'emnekode': emnekode,
            'versjon': versjon,
            'terminkode': termk,
            'arstall': aar,
            'terminnr': termnr}))

    def GetAnsvEvuAktivitet(self, kurs, tid, aktkode):
        qry = """
SELECT k.fodselsdato, k.personnr
FROM fs.kursaktivitet_fagperson k
WHERE k.etterutdkurskode=:kurs AND
      k.kurstidsangivelsekode=:tid AND
      k.aktivitetskode=:aktkode"""
        return (self._get_cols(qry),
                self.db.query(qry, {
            'kurs': kurs,
            'tid': tid,
            'aktkode': aktkode}))

    def GetStudEvuAktivitet(self, kurs, tid, aktkode):
        qry = """
SELECT d.fodselsdato, d.personnr
FROM fs.deltaker d, fs.kursaktivitet_deltaker k
WHERE k.etterutdkurskode=:kurs AND
      k.kurstidsangivelsekode=:tid AND
      k.aktivitetskode=:aktkode AND
      k.deltakernr = d.deltakernr"""
        return (self._get_cols(qry),
                self.db.query(qry, {
            'kurs': kurs,
            'tid': tid,
            'aktkode': aktkode}))

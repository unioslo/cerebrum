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

# from Cerebrum.modules.no.uio.access_FS import FS
from Cerebrum.modules.no import access_FS

class HiSTStudent(access_FS.Student):
    """FS klassen definerer et sett med metoder som kan benyttes for å
    hente ut informasjon om personer og OU-er fra FS. De fleste
    metodene returnerer en tuple med kolonnenavn fulgt av en tuple med
    dbrows."""

################################################################
#	Aktive studenter				       #
################################################################	

    def GetAktive(self):
        """Denne metoden henter data om aktive studenter ved HiST."""

        qry = """
SELECT DISTINCT
      s.fodselsdato,s.personnr,s.studentnr_tildelt,p.etternavn,p.fornavn,
      s.adrlin1_semadr,s.adrlin2_semadr,s.postnr_semadr,
      s.adrlin3_semadr,s.adresseland_semadr,p.adrlin1_hjemsted,
      p.adrlin2_hjemsted,p.postnr_hjemsted,p.adrlin3_hjemsted,
      p.adresseland_hjemsted,p.status_reserv_nettpubl,
      p.sprakkode_malform,sps.studieprogramkode,sps.studieretningkode, 
      sps.studierettstatkode,sps.studentstatkode,sps.terminkode_kull,
      kks.klassekode,sp.faknr_studieansv,
      sps.arstall_kull,p.kjonn,p.status_dod,p.telefonnr_mobil
FROM fs.kull k, fs.studieprogram sp, fs.kullklassestudent kks, fs.studieprogramstudent sps, fs.person p, fs.student s
WHERE p.fodselsdato = sps.fodselsdato AND
      p.personnr = sps.personnr AND
      p.fodselsdato = s.fodselsdato AND
      p.personnr = s.personnr AND
      %s AND
      kks.fodselsdato = p.fodselsdato AND
      kks.personnr = p.personnr AND
      kks.arstall = sps.arstall_kull AND
      kks.terminkode = sps.terminkode_kull AND
      kks.studieprogramkode = sps.studieprogramkode AND
      sp.studieprogramkode = sps.studieprogramkode AND
      k.studieprogramkode = sps.studieprogramkode AND
      k.terminkode = sps.terminkode_kull AND
      k.arstall = sps.arstall_kull AND
      NVL(k.status_aktiv,'J') = 'J' AND
      NVL(sps.dato_studierett_gyldig_til,SYSDATE)>= SYSDATE
      """ % (self.is_alive())
	return self.db.query(qry)






#################################################################
#	Privatister				    		#
#################################################################	

    def GetPrivatist(self): 
        """Her henter vi informasjon om privatister ved HiST
        Som privatist regnes alle studenter med en forekomst i 
        FS.STUDIEPROGRAMSTUDENT der dato_studierett_gyldig_til 
        er større eller lik dagens dato og studierettstatuskode   
        er PRIVATIST eller status_privatist er satt til 'J'"""
        qry = """
SELECT DISTINCT
    p.fodselsdato, p.personnr, p.etternavn,
    p.fornavn, p.kjonn, s.adrlin1_semadr,
    s.adrlin2_semadr, s.postnr_semadr, s.adrlin3_semadr,
    s.adresseland_semadr, p.adrlin1_hjemsted,
    p.sprakkode_malform,sps.studieprogramkode,   
    sps.studieretningkode, sps.status_privatist,  
    s.studentnr_tildelt, p.telefonnr_mobil
FROM fs.student s, fs.person p, fs.studieprogramstudent sps
WHERE p.fodselsdato = s.fodselsdato AND
    p.personnr = s.personnr AND
    p.fodselsdato = sps.fodselsdato AND
    p.personnr = sps.personnr AND
    (sps.studierettstatkode = 'PRIVATIST' OR
    sps.status_privatist = 'J') AND
    sps.dato_studierett_gyldig_til >= sysdate """
	return self.db.query(qry)        



    def GetDeltaker(self): 
        """Hent info om personer som er ekte EVU-studenter ved 
        HiA, dvs. er registrert i EVU-modulen i tabellen
        fs.deltaker,  Henter alle som er knyttet til kurs som
        tidligst ble avsluttet for 30 dager siden."""
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
       e.gruppenr_adm_ansvar, p.kjonn, p.status_dod, 
       p.telefonnr_mobil 
FROM fs.deltaker d, fs.person p, fs.kursdeltakelse k,
     fs.etterutdkurs e
WHERE p.fodselsdato=d.fodselsdato AND
      p.personnr=d.personnr AND
      d.deltakernr=k.deltakernr AND
      e.etterutdkurskode=k.etterutdkurskode AND 
      (NVL(e.status_kontotildeling,'J')='J' OR  
       NVL(e.status_nettbasert_und,'J')='J') AND
      k.kurstidsangivelsekode = e.kurstidsangivelsekode AND
      NVL(e.dato_til, SYSDATE) >= SYSDATE - 30"""
	return self.db.query(qry)


##################################################################
## E-post adresser i FS:
##################################################################


    def GetAllPersonsEmail(self, fetchall = False):
        return self.db.query("""
        SELECT fodselsdato, personnr, emailadresse, fornavn, etternavn
        FROM fs.person""", fetchall = fetchall)

    def WriteMailAddr(self, fodselsdato, personnr, email):
        return
        self.db.execute("""
        UPDATE fs.person
        SET emailadresse=:email
        WHERE fodselsdato=:fodselsdato AND personnr=:personnr""",
                        {'fodselsdato': fodselsdato,
                         'personnr': personnr,
                         'email': email})



##################################################################
## Brukernavn i FS:
##################################################################

    def GetAllPersonsUname(self, fetchall = False):
        return self.db.query("""
        SELECT p.fodselsdato, p.personnr, p.brukernavn, p.fornavn, p.etternavn
        FROM fs.person p""", fetchall = fetchall)
    # end GetAllPersonsUname


    def WriteUname(self, fodselsdato, personnr, uname):
        self.db.execute("""
        UPDATE fs.person
        SET brukernavn = :uname
        WHERE fodselsdato = :fodselsdato AND personnr = :personnr""",
                        {'fodselsdato': fodselsdato,
                         'personnr': personnr,
                         'uname': uname})
    # end WriteUname




################################################################
#	Studieprogrammer				       #
################################################################	

    def GetStudieproginf(self):
        """For hvert definerte studieprogram henter vi
        informasjon om utd_plan og eier samt studieprogkode. Dumpen fra
        denne (studieprog.xml) skal også brukes i forbindelse med bygging
        av rom i CF."""
        qry = """
SELECT studieprogramkode, studieprognavn, studienivakode,
       status_utdplan, institusjonsnr_studieansv,
       faknr_studieansv, instituttnr_studieansv, gruppenr_studieansv,
       status_utgatt
FROM fs.studieprogram"""
	return self.db.query(qry)

# Det er en del studenter på HiA som har opptak til inaktive studieprogrammer
# derfor må vi fjerne dette kravet fram til det er ryddet opp i dette
# Kravet burde settes inn permanent siden man bygger felles-rom for studieprogrammer
# i CF på grunnlag av disse data (det er litt dumt å bygge flere enn nødvndig
# Vi henter dog status_utgatt, det burde kunne brukes til å skille ut de programmene
# man ikke skal ha rom for.
# WHERE status_utgatt = 'N' """



##################################################################
# Emner
##################################################################
 
 
    def GetAlleEmner(self): 
        """Hent informasjon om alle emner i FS.""" 
        qry = """ 
SELECT DISTINCT
   emnekode, versjonskode, emnenavnfork, institusjonsnr_reglement,
   faknr_reglement, instituttnr_reglement, gruppenr_reglement,
   studienivakode, emnetypekode, fjernundstatkode, terminkode_und_forste,
   arstall_und_forste, terminkode_und_siste, arstall_und_siste
FROM fs.emne """
	return self.db.query(qry)        



##################################################################
# Mer studieinformasjon - testsøk for eksamensmeldinger	         #
##################################################################

    def GetAlleEksamensmeldinger(self, institusjonsnr=0):
	"""Hent data om eksamensmeldinger for alle studenter
           på HiST. Dette er en test-versjon av søket"""
	aar = time.localtime()[0:1]
	qry = """
SELECT p.fodselsdato, p.personnr, e.emnekode, e.arstall, 
       e.manednr, e.studieprogramkode
FROM fs.person p, fs.eksamensmelding e
WHERE p.fodselsdato=e.fodselsdato AND
      p.personnr=e.personnr AND
      e.arstall=%s 
      AND %s
ORDER BY fodselsdato, personnr
      """ %(aar[0],self.is_alive())                            
	return self.db.query(qry)



##################################################################
# Metoder for OU-er:
##################################################################
 
 
    def GetAlleOUer(self, institusjonsnr=0):
        """Hent data om stedskoder registrert i FS. Dumpes til fil
        på /cerebrum/dumps/FS/ou.xml""" 
        qry = """ 
SELECT DISTINCT 
   faknr, instituttnr, gruppenr, stedakronym, stednavn_bokmal,
   faknr_org_under, instituttnr_org_under, gruppenr_org_under,
   adrlin1, adrlin2, postnr, telefonnr, faxnr,
   adrlin1_besok, adrlin2_besok, postnr_besok, url, emailadresse,
   bibsysbeststedkode, stedkode_konv
FROM fs.sted  
WHERE institusjonsnr='%s'
         """ % institusjonsnr 
	return self.db.query(qry)
        


##################################################################
# Metoder brukt av bofh
##################################################################
 
    def GetStudentEksamen(self,fnr,pnr):
        """Hent alle eksamensmeldinger for en student for nåværende
        semester"""
        qry = """
SELECT DISTINCT
   em.emnekode, em.dato_opprettet, em.status_er_kandidat
FROM fs.eksamensmelding em, fs.person p
WHERE em.fodselsdato = :fnr AND
      em.personnr = :pnr AND
      em.fodselsdato = p.fodselsdato AND
      em.personnr = p.personnr AND
      em.arstall >= :year AND
      em.manednr > :mnd - 3
      AND %s 
        """ % self.is_alive()
        return (self._get_cols(qry), self.db.query(qry, {'fnr': fnr,
                                                         'pnr': pnr,
                                                         'year': self.year,
                                                         'mnd': self.mndnr}))
 
    def GetStudentStudierett(self,fnr,pnr):
        """Hent info om alle studierett en student har eller har hatt"""
        qry = """
SELECT DISTINCT
  sps.studieprogramkode, sps.studierettstatkode,
sps.dato_studierett_tildelt,
  sps.dato_studierett_gyldig_til, sps.status_privatist, sps.studentstatkode
FROM fs.studieprogramstudent sps, fs.person p
WHERE sps.fodselsdato=:fnr AND
      sps.personnr=:pnr AND
      p.fodselsdato = sps.fodselsdato AND
      p.personnr = sps.personnr AND
      %s 
        """ % self.is_alive()
        return (self._get_cols(qry), self.db.query(qry, {'fnr': fnr, 
                                                         'pnr': pnr}))


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


    def GetStudentKull(self, fnr, pnr):
        """Hent opplysninger om hvilken klasse studenten er en del av og 
        hvilken kull studentens klasse tilhører."""
        qry = """
SELECT DISTINCT
  sps.studieprogramkode, sps.terminkode_kull, sps.arstall_kull,
  k.status_aktiv
FROM fs.studieprogramstudent sps, fs.kull k, fs.person p
WHERE sps.fodselsdato = :fnr AND
      sps.personnr = :pnr AND
      p.fodselsdato = sps.fodselsdato AND
      p.personnr = sps.personnr AND
      sps.studieprogramkode = k.studieprogramkode AND
      sps.terminkode_kull = k.terminkode AND
      sps.arstall_kull = k.arstall AND
      %s 
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



##################################################################
# Hjelpemetoder  
##################################################################

    def is_alive(self):	
	return "NVL(p.status_dod, 'N') = 'N'\n"
##################################################################
# Metoder for å luke ut feil i FS  
##################################################################
    def FS_check1(self):
        """Denne metoden sjekker at en person med aktiv studeieprogram har et aktivt kull."""

        qry = """
SELECT DISTINCT sps.fodselsdato,sps.personnr,sps.studieprogramkode
FROM fs.studieprogramstudent sps
LEFT JOIN fs.kullklassestudent kks
ON ( sps.fodselsdato = kks.fodselsdato AND
    sps.personnr = kks.personnr AND
    sps.arstall_kull = kks.arstall AND
    sps.terminkode_kull = kks.terminkode AND
    kks.studieprogramkode = sps.studieprogramkode AND
    kks.status_aktiv = 'J' )
WHERE 
    (kks.personnr IS null OR kks.status_aktiv = 'N') AND
    NVL(sps.dato_studierett_gyldig_til,SYSDATE)>= SYSDATE
ORDER BY sps.studieprogramkode
    """
	return self.db.query(qry)



class FS(access_FS.FS): 
    def __init__(self, db=None, user=None, database=None): 
        super(FS, self).__init__(db=db, user=user, database=database)
 
        # Override with uio-spesific classes 
        self.student = HiSTStudent(self.db)
#        self.portal = UiOPortal(self.db)
#        self.betaling = UiOBetaling(self.db) 



# arch-tag: edebb9a0-5e67-4fb6-91a3-da5536ec4dfa

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
import time

from Cerebrum import Database
from Cerebrum import Errors

from Cerebrum.modules.no import access_FS

class UiOStudent(access_FS.Student):
    def list(self): # GetStudent_50
        """Hent personer med opptak til et studieprogram ved
        institusjonen og som enten har vært registrert siste året
        eller opptak efter 2003-01-01.  Henter ikke de som har
        fremtidig opptak.  Disse kommer med 14 dager før dato for
        tildelt opptak.  Alle disse skal ha affiliation med status
        kode 'opptak' til stedskoden sp.faknr_studieansv +
        sp.instituttnr_studieansv + sp.gruppenr_studieansv"""

        qry = """
SELECT DISTINCT s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
       s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
       s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
       p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
       p.adresseland_hjemsted, p.status_reserv_nettpubl, 
       p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
       sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
       sps.arstall_kull, p.kjonn, p.status_dod
FROM fs.student s, fs.person p, fs.studieprogramstudent sps
WHERE  p.fodselsdato=s.fodselsdato AND
       p.personnr=s.personnr AND
       p.fodselsdato=sps.fodselsdato AND
       p.personnr=sps.personnr AND
       NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
       sps.status_privatist = 'N' AND
       sps.dato_studierett_tildelt < SYSDATE + 14 AND
       sps.dato_studierett_tildelt >= to_date('2003-01-01', 'yyyy-mm-dd')
       """
        qry += """ UNION
SELECT DISTINCT s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
       s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
       s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
       p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
       p.adresseland_hjemsted, p.status_reserv_nettpubl,
       p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
       sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
       sps.arstall_kull, p.kjonn, p.status_dod
FROM fs.student s, fs.person p, fs.studieprogramstudent sps, fs.registerkort r
WHERE  p.fodselsdato=s.fodselsdato AND
       p.personnr=s.personnr AND
       p.fodselsdato=sps.fodselsdato AND
       p.personnr=sps.personnr AND
       p.fodselsdato=r.fodselsdato AND
       p.personnr=r.personnr AND
       NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
       sps.status_privatist = 'N' AND
       r.arstall >= (%s - 1)
       """ % (self.year)
        return self.db.query(qry)
    
    def list_aktiv(self):  # GetStudentAktiv_50
        """Hent fødselsnummer+studieprogram+studieretning+kull for
        alle aktive studenter.  Som aktive studenter regner vi alle
        studenter med opptak til et studieprogram som samtidig har en
        eksamensmelding eller en avlagt eksamen inneverende semester i
        et emne som kan inngå i dette studieprogrammet, eller som har
        bekreftet sin utdanningsplan.  Disse får affiliation student
        med kode aktiv til sp.faknr_studieansv +
        sp.instituttnr_studieansv + sp.gruppenr_studieansv.  Vi har
        alt hentet opplysninger om adresse ol. efter som de har
        opptak.  Henter derfor kun fødselsnummer, studieprogram,
        studieretning og kull.  Må gjøre et eget søk for å finne
        klasse for de som er registrert på slikt. """

        qry = """
SELECT DISTINCT
      s.fodselsdato, s.personnr, sp.studieprogramkode,
      sps.studieretningkode, sps.terminkode_kull, sps.arstall_kull, 
      em.emnekode, em.versjonskode
FROM fs.studieprogram sp, fs.studieprogramstudent sps, fs.student s,
     fs.registerkort r, fs.eksamensmelding em, fs.emne_i_studieprogram es
WHERE s.fodselsdato=r.fodselsdato AND
      s.personnr=r.personnr AND
      s.fodselsdato=sps.fodselsdato AND
      s.personnr=sps.personnr AND
      s.fodselsdato=em.fodselsdato AND
      s.personnr=em.personnr AND
      es.studieprogramkode=sp.studieprogramkode AND
      em.emnekode=es.emnekode AND
      sps.status_privatist='N' AND 
      sps.studieprogramkode=sp.studieprogramkode AND
      r.regformkode IN ('STUDWEB','DOKTORREG','MANUELL') AND
      NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
      %s
UNION """ %(self._get_termin_aar(only_current=1))

        qry = qry + """
SELECT DISTINCT
      s.fodselsdato, s.personnr, sp.studieprogramkode,
      sps.studieretningkode, sps.terminkode_kull, sps.arstall_kull,
      em.emnekode, em.versjonskode
FROM fs.studieprogram sp, fs.studieprogramstudent sps, fs.student s,
     fs.registerkort r, fs.eksamensmelding em
WHERE sps.studieprogramkode = 'ENKELTEMNE' AND
      s.fodselsdato=r.fodselsdato AND
      s.personnr=r.personnr AND
      s.fodselsdato=sps.fodselsdato AND
      s.personnr=sps.personnr AND
      s.fodselsdato=em.fodselsdato AND
      s.personnr=em.personnr AND
      sps.status_privatist='N' AND 
      sps.studieprogramkode=sp.studieprogramkode AND
      r.regformkode IN ('STUDWEB','DOKTORREG','MANUELL') AND
      NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
      %s
UNION """ %(self._get_termin_aar(only_current=1))

        qry = qry + """
SELECT DISTINCT
     s.fodselsdato, s.personnr, sp.studieprogramkode,
     sps.studieretningkode, sps.terminkode_kull, sps.arstall_kull,
     em.emnekode, em.versjonskode
FROM fs.student s, fs.studieprogramstudent sps, fs.eksamensmelding em, 
     fs.studprogstud_planbekreft r, fs.studieprogram sp
WHERE s.fodselsdato=sps.fodselsdato AND
      s.personnr=sps.personnr AND
      s.fodselsdato=r.fodselsdato AND
      s.personnr=r.personnr AND
      s.fodselsdato=em.fodselsdato AND
      s.personnr=em.personnr AND
      sps.studieprogramkode=sp.studieprogramkode AND
      sp.status_utdplan='J' AND
      sps.status_privatist='N' AND
      r.studieprogramkode=sps.studieprogramkode AND
      NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
      r.dato_bekreftet < SYSDATE AND
      r.arstall_bekreft = %d AND
      r.terminkode_bekreft = '%s'
UNION""" %(self.year, self.semester)

        qry = qry + """
SELECT DISTINCT sp.fodselsdato, sp.personnr, sps.studieprogramkode,
      sps.studieretningkode, sps.terminkode_kull, sps.arstall_kull,
      sp.emnekode, sp.versjonskode
FROM fs.studentseksprotokoll sp, fs.studieprogramstudent sps,
     fs.emne_i_studieprogram es
WHERE sp.arstall >= %s AND
      (%s <= 6 OR sp.manednr > 6 ) AND
      sp.fodselsdato = sps.fodselsdato AND
      sp.personnr    = sps.personnr AND
      sp.institusjonsnr = '185' AND
      sp.emnekode = es.emnekode AND
      es.studieprogramkode = sps.studieprogramkode AND
      NVL(sps.DATO_studierett_GYLDIG_TIL,SYSDATE) >= sysdate AND
      sps.status_privatist = 'N'
      """ %(self.year, self.mndnr)
     	return self.db.query(qry)

class UiOStudent40(access_FS.Student):
    def list_aktiv(self):  # GetStudinfAktiv
        """Hent fødselsnummer+studieprogram for alle aktive studenter.
        Som aktive studenter regner vi alle studenter med opptak til
        et studieprogram som samtidig har en eksamensmelding eller en
        avlagt eksamen inneverende semester i et emne som kan inngå i
        dette studieprogrammet, eller som har bekreftet sin
        utdanningsplan.  Disse får affiliation student med kode aktiv
        til sp.faknr_studieansv+sp.instituttnr_studieansv+
        sp.gruppenr_studieansv.  Vi har alt hentet opplysninger om
        adresse ol. efter som de har opptak.  Henter derfor kun
        fødselsnummer og studieprogram.  Medfører at du kan få med
        linjer som du ikke har personinfo for, dette vil være snakk om
        ekte-døde personer."""

        qry = """
SELECT DISTINCT
      s.fodselsdato, s.personnr, sp.studieprogramkode, st.studieretningkode
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
      NVL(st.dato_gyldig_til,SYSDATE) >= sysdate AND
      %s
UNION """ %(self._get_termin_aar(only_current=1))

        qry = qry + """
SELECT DISTINCT
     s.fodselsdato, s.personnr, sp.studieprogramkode, st.studieretningkode
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
      NVL(st.dato_gyldig_til,SYSDATE) >= sysdate AND
      r.dato_bekreftet < SYSDATE AND
      r.arstall_bekreft = %d AND
      r.terminkode_bekreft = '%s'
UNION""" %(self.year, self.semester)

        qry = qry + """
SELECT DISTINCT sp.fodselsdato, sp.personnr, st.studieprogramkode,
                st.studieretningkode
FROM fs.studentseksprotokoll sp, fs.studierett st,
     fs.emne_i_studieprogram es
WHERE sp.arstall >= %s AND
      (%s <= 6 OR sp.manednr > 6 ) AND
      sp.fodselsdato = st.fodselsdato AND
      sp.personnr = st.personnr AND
      sp.institusjonsnr = '185' AND
      sp.emnekode = es.emnekode AND
      es.studieprogramkode = st.studieprogramkode AND
      (st.opphortstudierettstatkode IS NULL OR
      st.DATO_GYLDIG_TIL >= sysdate) AND
      st.status_privatist = 'N'
      """ %(self.year, self.mndnr)
     	return self.db.query(qry)




class UiOPortal(access_FS.FSObject):
    def list_eksmeld(self):  # GetPortalInfo_50
        """
        Hent ut alle eksamensmeldinger i nåværende semester med all
        interessant informasjon for portaldumpgenerering.

        SQL-spørringen er dyp magi. Spørsmål rettes til baardj.
        """

        #
        # NB! Det er ikke meningen at vanlige dødelige skal kunne forstå
        # denne SQL-spørringen. Lurer du på noe, plag baardj
        # 

        # Velg ut studentens eksamensmeldinger for inneværende og
        # fremtidige semestre.  Søket sjekker at studenten har
        # rett til å følge kurset, og at vedkommende er
        # semesterregistrert i inneværende semester (eller,
        # dersom fristen for semesterregistrering dette
        # semesteret ennå ikke er utløpt, hadde
        # semesterregistrert seg i forrige semester)

        query = """
        SELECT m.fodselsdato, m.personnr,
               m.emnekode, m.arstall, m.manednr,
               sprg.studienivakode,
               e.institusjonsnr_reglement, e.faknr_reglement,
               e.instituttnr_reglement, e.gruppenr_reglement,
               es.studieprogramkode
        FROM fs.eksamensmelding m, fs.emne e, fs.studieprogramstudent sps,
             fs.emne_i_studieprogram es, fs.registerkort r,
             fs.studieprogram sprg, fs.person p
        WHERE
            m.arstall >= :aar1 AND
            m.fodselsdato = sps.fodselsdato AND
            m.personnr = sps.personnr AND
            m.fodselsdato = r.fodselsdato AND
            m.personnr = r.personnr AND
            m.fodselsdato = p.fodselsdato AND
            m.personnr = p.personnr AND
            NVL(p.status_dod, 'N') = 'N' AND
            %s AND
            NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
            sps.status_privatist = 'N' AND
            m.institusjonsnr = e.institusjonsnr AND
            m.emnekode = e.emnekode AND
            m.versjonskode = e.versjonskode AND
            m.institusjonsnr = es.institusjonsnr AND
            m.emnekode = es.emnekode AND
            es.studieprogramkode = sps.studieprogramkode AND
            es.studieprogramkode = sprg.studieprogramkode
        """ % self._get_termin_aar()

        # Velg ut studentens avlagte UiO eksamener i inneværende
        # semester (studenten er fortsatt gyldig student ut
        # semesteret, selv om alle eksamensmeldinger har gått
        # over til å bli eksamensresultater).
        #
        # Søket sjekker _ikke_ at det finnes noen
        # semesterregistrering for inneværende registrering
        # (fordi dette skal være implisitt garantert av FS)
        query += """ UNION
        SELECT sp.fodselsdato, sp.personnr,
               sp.emnekode, sp.arstall, sp.manednr,
               sprg.studienivakode,
               e.institusjonsnr_reglement, e.faknr_reglement,
               e.instituttnr_reglement, e.gruppenr_reglement,
               sps.studieprogramkode
        FROM fs.studentseksprotokoll sp, fs.emne e,
             fs.studieprogramstudent sps,
             fs.emne_i_studieprogram es, fs.studieprogram sprg, fs.person p
        WHERE
            sp.arstall >= :aar2 AND
            sp.fodselsdato = sps.fodselsdato AND
            sp.personnr = sps.personnr AND
            sp.fodselsdato = p.fodselsdato AND
            sp.personnr = p.personnr AND
            NVL(p.status_dod, 'N') = 'N' AND
            NVL(sps.DATO_studierett_GYLDIG_TIL,SYSDATE) >= sysdate AND
            sps.status_privatist = 'N' AND
            sp.emnekode = e.emnekode AND
            sp.versjonskode = e.versjonskode AND
            sp.institusjonsnr = e.institusjonsnr AND
            sp.institusjonsnr = '185' AND
            sp.emnekode = es.emnekode AND
            es.studieprogramkode = sps.studieprogramkode AND
            es.studieprogramkode = sprg.studieprogramkode
        """

        # Velg ut alle studenter som har opptak til et studieprogram
        # som krever utdanningsplan og som har bekreftet utdannings-
        # planen dette semesteret.
        #
        # NB! TO_*-konverteringene er påkrevd
        query += """ UNION
        SELECT stup.fodselsdato, stup.personnr,
               TO_CHAR(NULL) as emnekode, TO_NUMBER(NULL) as arstall,
               TO_NUMBER(NULL) as manednr,
               sprg.studienivakode,
               sprg.institusjonsnr_studieansv, sprg.faknr_studieansv,
               sprg.instituttnr_studieansv, sprg.gruppenr_studieansv,
               sps.studieprogramkode
        FROM fs.studprogstud_planbekreft stup,fs.studieprogramstudent sps,
             fs.studieprogram sprg, fs.person p
        WHERE
              stup.arstall_bekreft=:aar3 AND
              stup.terminkode_bekreft=:semester AND
              stup.fodselsdato = sps.fodselsdato AND
              stup.personnr = sps.personnr AND
              stup.fodselsdato = p.fodselsdato AND
              stup.personnr = p.personnr AND
              NVL(p.status_dod, 'N') = 'N' AND
              NVL(sps.DATO_studierett_GYLDIG_TIL, SYSDATE) >= sysdate AND
              sps.status_privatist = 'N' AND
              stup.studieprogramkode = sps.studieprogramkode AND
              stup.studieprogramkode = sprg.studieprogramkode AND
              sprg.status_utdplan = 'J'
        """

        semester = "%s" % self.semester
        # FIXME! Herregud da, hvorfor må de ha hver sitt navn?
        return self.db.query(query,
                             {"aar1" : self.year,
                              "aar2" : self.year,
                              "aar3" : self.year,
                              "semester": semester},
                             False)
    
class UiOPortal40(access_FS.FSObject):
    def list_eksmeld(self):  # GetPortalInfo
        """
        Hent ut alle eksamensmeldinger i nåværende semester med all
        interessant informasjon for portaldumpgenerering.

        SQL-spørringen er dyp magi. Spørsmål rettes til baardj.
        """

        #
        # NB! Det er ikke meningen at vanlige dødelige skal kunne forstå
        # denne SQL-spørringen. Lurer du på noe, plag baardj
        # 

        # Velg ut studentens eksamensmeldinger for inneværende og
        # fremtidige semestre.  Søket sjekker at studenten har
        # rett til å følge kurset, og at vedkommende er
        # semesterregistrert i inneværende semester (eller,
        # dersom fristen for semesterregistrering dette
        # semesteret ennå ikke er utløpt, hadde
        # semesterregistrert seg i forrige semester)

        query = """
        SELECT m.fodselsdato, m.personnr,
               m.emnekode, m.arstall, m.manednr,
               sprg.studienivakode,
               e.institusjonsnr_reglement, e.faknr_reglement,
               e.instituttnr_reglement, e.gruppenr_reglement,
               es.studieprogramkode
        FROM fs.eksamensmelding m, fs.emne e, fs.studierett st,
             fs.emne_i_studieprogram es, fs.registerkort r,
             fs.studieprogram sprg, fs.person p
        WHERE
            m.arstall >= :aar1 AND
            m.fodselsdato = st.fodselsdato AND
            m.personnr = st.personnr AND
            m.fodselsdato = r.fodselsdato AND
            m.personnr = r.personnr AND
            m.fodselsdato = p.fodselsdato AND
            m.personnr = p.personnr AND
            NVL(p.status_dod, 'N') = 'N' AND
            %s AND
            NVL(st.dato_gyldig_til,SYSDATE) >= sysdate AND
            st.status_privatist = 'N' AND
            m.institusjonsnr = e.institusjonsnr AND
            m.emnekode = e.emnekode AND
            m.versjonskode = e.versjonskode AND
            m.institusjonsnr = es.institusjonsnr AND
            m.emnekode = es.emnekode AND
            es.studieprogramkode = st.studieprogramkode AND
            es.studieprogramkode = sprg.studieprogramkode
        """ % self._get_termin_aar()

        # Velg ut studentens avlagte UiO eksamener i inneværende
        # semester (studenten er fortsatt gyldig student ut
        # semesteret, selv om alle eksamensmeldinger har gått
        # over til å bli eksamensresultater).
        #
        # Søket sjekker _ikke_ at det finnes noen
        # semesterregistrering for inneværende registrering
        # (fordi dette skal være implisitt garantert av FS)
        query += """ UNION
        SELECT sp.fodselsdato, sp.personnr,
               sp.emnekode, sp.arstall, sp.manednr,
               sprg.studienivakode,
               e.institusjonsnr_reglement, e.faknr_reglement,
               e.instituttnr_reglement, e.gruppenr_reglement,
               st.studieprogramkode
        FROM fs.studentseksprotokoll sp, fs.emne e, fs.studierett st,
             fs.emne_i_studieprogram es, fs.studieprogram sprg, fs.person p
        WHERE
            sp.arstall >= :aar2 AND
            sp.fodselsdato = st.fodselsdato AND
            sp.personnr = st.personnr AND
            sp.fodselsdato = p.fodselsdato AND
            sp.personnr = p.personnr AND
            NVL(p.status_dod, 'N') = 'N' AND
            NVL(st.DATO_GYLDIG_TIL,SYSDATE) >= sysdate AND
            st.status_privatist = 'N' AND
            sp.emnekode = e.emnekode AND
            sp.versjonskode = e.versjonskode AND
            sp.institusjonsnr = e.institusjonsnr AND
            sp.institusjonsnr = '185' AND
            sp.emnekode = es.emnekode AND
            es.studieprogramkode = st.studieprogramkode AND
            es.studieprogramkode = sprg.studieprogramkode
        """

        # Velg ut alle studenter som har opptak til et studieprogram
        # som krever utdanningsplan og som har bekreftet utdannings-
        # planen dette semesteret.
        #
        # NB! TO_*-konverteringene er påkrevd
        query += """ UNION
        SELECT stup.fodselsdato, stup.personnr,
               TO_CHAR(NULL) as emnekode, TO_NUMBER(NULL) as arstall,
               TO_NUMBER(NULL) as manednr,
               sprg.studienivakode,
               sprg.institusjonsnr_studieansv, sprg.faknr_studieansv,
               sprg.instituttnr_studieansv, sprg.gruppenr_studieansv,
               st.studieprogramkode
        FROM fs.studprogstud_planbekreft stup,fs.studierett st,
             fs.studieprogram sprg, fs.person p
        WHERE
              stup.arstall_bekreft=:aar3 AND
              stup.terminkode_bekreft=:semester AND
              stup.fodselsdato = st.fodselsdato AND
              stup.personnr = st.personnr AND
              stup.fodselsdato = p.fodselsdato AND
              stup.personnr = p.personnr AND
              NVL(p.status_dod, 'N') = 'N' AND
              NVL(st.DATO_GYLDIG_TIL, SYSDATE) >= sysdate AND
              st.status_privatist = 'N' AND
              stup.studieprogramkode = st.studieprogramkode AND
              stup.studieprogramkode = sprg.studieprogramkode AND
              sprg.status_utdplan = 'J'
        """

        semester = "%s" % self.semester
        # FIXME! Herregud da, hvorfor må de ha hver sitt navn?
        return self.db.query(query,
                             {"aar1" : self.year,
                              "aar2" : self.year,
                              "aar3" : self.year,
                              "semester": semester},
                             False)

class UiOBetaling(access_FS.FSObject):
    ################################################
    # Kopiavgift
    # Ny ordning fra høsten 2004.
    ################################################
    def list_kopiavgift_fritak(self):  # GetStudFritattKopiavg
        """Lister fødselsnummer på de som er fritatt fra å måtte
        betale kopiavgift jmf den ordningen som ble innført høsten
        2004."""

        qry ="""
        SELECT DISTINCT r.fodselsdato, r.personnr
        FROM fs.registerkort r
        WHERE r.terminkode = :semester AND
              r.arstall = :year AND
              r.betformkode IN ('FRITATT', 'EKSTERN')"""
        return self.db.query(qry, {'semester': self.semester,
                                   'year': self.year})

    def list_utskrifts_betaling(self, days_past=180): # GetUtskriftsBetaling
        """Lister fødselsnummer, betalingsinformasjon og beløp for de
        innbetalinger som er gjordt gjennom studentweben for
        utskriftssystemet. """
        
        if days_past is None:
            where = ""
        else:
            # Vi vet ikke om dato_betalt må være != null når status_betalt='J'
            where = " AND NVL(dato_betalt, [:now]) > [:now]-%i" % days_past
            
        qry = """
        SELECT frk.fodselsdato, frk.personnr, frk.fakturanr, frk.dato_betalt,
               fkd.belop, fkd.detaljlopenr, frk.kidkode
        FROM fs.fakturareskontrodetalj fkd,
             fs.fakturareskontro frk
        WHERE frk.fakturastatuskode = 'OPPGJORT' AND
              fkd.fakturanr = frk.fakturanr AND
              fkd.status_betalt = 'J' AND
              fkd.fakturadetaljtypekode = 'UTSKRIFT' AND
              frk.status_betalt = 'J' %s""" % where
        
        return self.db.query(qry)

    
    ################################################
    # Papirpenger
    # Skal avvikles i løpet av sommeren 2004
    ################################################

    def list_betalt_papiravgift(self):  # GetStudBetPapir
        """Lister ut fødselsnummer til alle de som har betalt en eller
        annen form for papirpenger. Vi henter inn de studentene som
        har fritak for betaling av semesteravgift da det er blitt
        bestemt at disse heller ikke skal betale papiravgift dette
        semesteret.  Dette er imidlertid litt problematisk siden det
        finnes flere typer studenter med slik fritak uten at man har
        full oversikt over alle studentgrupper som omfattes av
        dette"""

        qry = """
        SELECT DISTINCT r.fodselsdato, r.personnr
        FROM fs.fakturareskontrodetalj fkd,
             fs.fakturareskontro frk,
             fs.registerkort r
        WHERE
        r.TERMINKODE = :semester and  r.arstall = :year and
        r.regformkode in ('STUDWEB','MANUELL') and
        r.fodselsdato = frk.fodselsdato and
        r.personnr = frk.personnr and
        frk.status_betalt = 'J' AND
        frk.terminkode = r.terminkode AND
        frk.arstall = r.arstall AND
        frk.fakturastatuskode ='OPPGJORT' and
        fkd.fakturanr = frk.fakturanr AND
        fkd.fakturadetaljtypekode IN ('PAPIRAVG', 'KOPIAVG')"""
	qry += """ UNION
        SELECT DISTINCT r.fodselsdato, r.personnr
        FROM fs.registerkort r
        WHERE
        r.TERMINKODE = :semester and r.arstall = :year AND
        r.betformkode='FRITATT'"""

#Ved senere anledning (når studierettstatuskoder som skal brukes er bekreftet
# skal denne delen av søket også taes i bruk
#	qry += """ UNION
#	SELECT DISTINCT st.fodselsdato, st.personnr
#	FROM fs.studierett st
#	WHERE
#	st.status_privatist='N' AND
#	NVL(st.dato_gyldig_til,SYSDATE) >= sysdate AND
#	st.studierettstatkode IN ('ERASMUS','NORDPLUS',
#       'SOKRATES','NORAD','FULBRIGHT','KULTURAVT') """	

        return self.db.query(qry, {'semester': self.semester,
                                   'year': self.year})
    
class FS(access_FS.FS):
    def __init__(self, db=None, user=None, database=None):
        super(FS, self).__init__(db=db, user=user, database=database)

        # Override with uio-spesific classes
        self.student = UiOStudent(self.db)
        self.portal = UiOPortal(self.db)
        self.betaling = UiOBetaling(self.db)
        
# arch-tag: 22ae9ce8-a845-40b8-bc4d-dcb51a54ca2a

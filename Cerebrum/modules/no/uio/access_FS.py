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
        return self._list_gyldigopptak() + self._list_drgradsopptak() +  self._list_gammelopptak_semreg()

    def _list_gyldigopptak(self):
        """Alle med gyldig opptak tildelt etter 1. januar 2003 samt alle
           med opptak som blir gyldig om 14 dager"""
        qry = """
        SELECT DISTINCT
           s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
           s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
           s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
           p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
           p.adresseland_hjemsted, p.status_reserv_nettpubl, 
           p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
           sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
           sps.arstall_kull, sp.studienivakode, p.kjonn, p.status_dod
        FROM fs.student s, fs.person p, fs.studieprogramstudent sps,
           fs.studieprogram sp
        WHERE  p.fodselsdato=s.fodselsdato AND
           p.personnr=s.personnr AND
           p.fodselsdato=sps.fodselsdato AND
           p.personnr=sps.personnr AND
           sps.studieprogramkode=sp.studieprogramkode AND
           NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
           sps.status_privatist = 'N' AND
           sps.dato_studierett_tildelt < SYSDATE + 14 AND
           sps.dato_studierett_tildelt >= to_date('2003-01-01', 'yyyy-mm-dd') """
        return self.db.query(qry)
    
    def _list_drgradsopptak(self):
        """Alle drgradsstudenter med ikke utgått opptak til drgrads-studieprogram"""
        qry = """
        SELECT DISTINCT
           s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
           s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
           s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
           p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
           p.adresseland_hjemsted, p.status_reserv_nettpubl, 
           p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
           sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
           sps.arstall_kull, sp.studienivakode, p.kjonn, p.status_dod
        FROM fs.student s, fs.person p, fs.studieprogramstudent sps,
           fs.studieprogram sp
        WHERE  p.fodselsdato=s.fodselsdato AND
           p.personnr=s.personnr AND
           p.fodselsdato=sps.fodselsdato AND
           p.personnr=sps.personnr AND
           (NVL(sps.dato_beregnet_slutt, sysdate) >= SYSDATE OR
           NVL(sps.dato_planlagt_slutt, sysdate) >= SYSDATE) AND
           sps.status_privatist='N' AND
           sps.studieprogramkode=sp.studieprogramkode AND
           sp.studienivakode >= 980 """
        return self.db.query(qry)
    
    def _list_gammelopptak_semreg(self):
        """Alle med gyldig opptak som har hatt en forekomst i registerkort i løpet
           av fjoråret"""
        qry = """
        SELECT DISTINCT
           s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
           s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
           s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
           p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
           p.adresseland_hjemsted, p.status_reserv_nettpubl,
           p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
           sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
           sps.arstall_kull, sp.studienivakode, p.kjonn, p.status_dod
        FROM fs.student s, fs.person p, fs.studieprogramstudent sps,
           fs.registerkort r, fs.studieprogram sp
        WHERE  p.fodselsdato=s.fodselsdato AND
           p.personnr=s.personnr AND
           p.fodselsdato=sps.fodselsdato AND
           p.personnr=sps.personnr AND
           p.fodselsdato=r.fodselsdato AND
           p.personnr=r.personnr AND
           sps.studieprogramkode=sp.studieprogramkode AND
           NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
           sps.status_privatist = 'N' AND
           r.arstall >= (%s - 1)""" % (self.year)
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
        return self._list_aktiv_semreg() + self._list_aktiv_enkeltemne() + self._list_aktiv_avlagteksamen() + self._list_aktiv_utdplan()
    
    def _list_aktiv_semreg(self):
        """Alle semesterregistrerte som i tillegg har en eksamensmelding i et
           emne som kan inngå i et studieprogram som de har opptak til"""
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
           %s """ %(self._get_termin_aar(only_current=1))
        return self.db.query(qry)

    def _list_aktiv_enkeltemne(self):
        """Alle semesterregistrerte med gyldig opptak til studieprogrammet
           'ENKELTEMNE' som har en gyldig eksamensmelding i et emne som
           kan inngå i et vilkårlig studieprogram"""
        qry = """
        SELECT DISTINCT
           s.fodselsdato, s.personnr, sp.studieprogramkode,
           sps.studieretningkode, sps.terminkode_kull, sps.arstall_kull,
           em.emnekode, em.versjonskode
        FROM fs.studieprogram sp, fs.studieprogramstudent sps, fs.student s,
           fs.registerkort r, fs.eksamensmelding em
        WHERE sps.studieprogramkode='ENKELTEMNE' AND
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
           %s """ %(self._get_termin_aar(only_current=1))
        return self.db.query(qry)

    def _list_aktiv_utdplan(self):
        """Alle semesterregistrerte som i tillegg har bekreftet utdanningsplan
           i inneværende semester"""
        qry = """
        SELECT DISTINCT
           s.fodselsdato, s.personnr, sp.studieprogramkode,
           sps.studieretningkode, sps.terminkode_kull, sps.arstall_kull,
           'NULL' as emnekode, 'NULL' as versjonskode
        FROM fs.student s, fs.studieprogramstudent sps, fs.registerkort r,
           fs.studprogstud_planbekreft spp, fs.studieprogram sp
        WHERE s.fodselsdato=sps.fodselsdato AND
           s.personnr=sps.personnr AND
           s.fodselsdato=r.fodselsdato AND
           s.personnr=r.personnr AND
           s.fodselsdato=spp.fodselsdato AND
           s.personnr=spp.personnr AND
           sps.studieprogramkode=sp.studieprogramkode AND
           sp.status_utdplan='J' AND
           sps.status_privatist='N' AND
           spp.studieprogramkode=sps.studieprogramkode AND
           NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
           spp.dato_bekreftet < SYSDATE AND
           spp.arstall_bekreft=%d AND
           spp.terminkode_bekreft='%s' AND
           r.regformkode IN ('STUDWEB','DOKTORREG','MANUELL') AND
           %s """ %(self.year, self.semester, self._get_termin_aar(only_current=1))
        return self.db.query(qry)

    def _list_aktiv_avlagteksamen(self):
        """Alle semesterregistrerte som har avlagt eksamen i inneværende år
           Ifølge STA er dette det riktige kravet. mulig at vi ønsker å mene
           noe annet etterhvert"""
        qry = """
        SELECT DISTINCT
           sp.fodselsdato, sp.personnr, sps.studieprogramkode,
           sps.studieretningkode, sps.terminkode_kull, sps.arstall_kull,
           sp.emnekode, sp.versjonskode
        FROM fs.studentseksprotokoll sp, fs.studieprogramstudent sps,
           fs.emne_i_studieprogram es, fs.registerkort r
        WHERE sp.arstall=%s AND
           sp.fodselsdato=sps.fodselsdato AND
           sp.personnr=sps.personnr AND
           r.fodselsdato=sps.fodselsdato AND
           r.personnr=sps.personnr AND
           sp.institusjonsnr='185' AND
           sp.emnekode=es.emnekode AND
           es.studieprogramkode=sps.studieprogramkode AND
           NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
           sps.status_privatist='N' AND
           %s """ %(self.year, self._get_termin_aar(only_current=1))
     	return self.db.query(qry)

    def list_privatist_emne(self):  # GetStudentPrivatistEmne_50
        """Hent personer som er uekte privatister, dvs. som er
	eksamensmeldt til et emne i et studieprogram de ikke har
	opptak til. Disse tildeles affiliation privatist til stedet
	som eier studieprogrammet de har opptak til.  Dette blir ikke
	helt riktig efter som man kan ha opptak til studieprogramet
	'ENKELTEMNE' som betyr at man kan være ordninær student selv
	om man havner i denne gruppen som plukkes ut av dette søket"""

	qry = """
        SELECT s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
               s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
               s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
               p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
               p.adresseland_hjemsted, p.status_reserv_nettpubl, 
               p.sprakkode_malform, p.kjonn, p.status_dod, em.emnekode
        FROM fs.student s, fs. person p, fs.registerkort r,
             fs.eksamensmelding em
        WHERE s.fodselsdato=p.fodselsdato AND
              s.personnr=p.personnr AND
              p.fodselsdato=r.fodselsdato AND
              p.personnr=r.personnr AND
              p.fodselsdato=em.fodselsdato AND
              p.personnr=em.personnr AND
               %s AND
              NOT EXISTS
              (SELECT 'x' FROM fs.studieprogramstudent sps,
                               fs.emne_i_studieprogram es
               WHERE p.fodselsdato=sps.fodselsdato AND
                     p.personnr=sps.personnr AND
                     es.emnekode=em.emnekode AND
                     es.studieprogramkode = sps.studieprogramkode AND
                     NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= SYSDATE)
      """ % (self._get_termin_aar(only_current=1))
        return self.db.query(qry)
    
    def list_privatist(self): # GetStudentPrivatist_50
        """Hent personer med privatist 'opptak' til et studieprogram
        ved institusjonen og som enten har vært registrert siste året
        eller har fått privatist 'opptak' efter 2003-01-01.  Henter ikke de som
        har fremtidig opptak.  Disse kommer med 14 dager før dato for
        tildelt privatist 'opptak'.  Alle disse skal ha affiliation
        med status kode 'privatist' til stedskoden sp.faknr_studieansv
        + sp.instituttnr_studieansv + sp.gruppenr_studieansv"""

        qry = """
        SELECT DISTINCT s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
               s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
               s.adrlin3_semadr, s.adresseland_semadr,
               p.adrlin1_hjemsted, p.adrlin2_hjemsted,
               p.postnr_hjemsted, p.adrlin3_hjemsted,
               p.adresseland_hjemsted, p.status_reserv_nettpubl,
               p.sprakkode_malform, sps.studieprogramkode,
               sps.studieretningkode, sps.studierettstatkode,
               sps.studentstatkode, sps.terminkode_kull,
               sps.arstall_kull, p.kjonn, p.status_dod
        FROM fs.student s, fs.person p, fs.studieprogramstudent sps
        WHERE  p.fodselsdato=s.fodselsdato AND
               p.personnr=s.personnr AND
               p.fodselsdato=sps.fodselsdato AND
               p.personnr=sps.personnr AND
               NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
               sps.status_privatist = 'J' AND
               sps.dato_studierett_tildelt < SYSDATE + 14 AND
               sps.dato_studierett_tildelt >= to_date('2003-01-01',
                                                      'yyyy-mm-dd')
       """
        qry += """ UNION
        SELECT DISTINCT s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
               s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
               s.adrlin3_semadr, s.adresseland_semadr,
               p.adrlin1_hjemsted, p.adrlin2_hjemsted,
               p.postnr_hjemsted, p.adrlin3_hjemsted,
               p.adresseland_hjemsted, p.status_reserv_nettpubl,
               p.sprakkode_malform, sps.studieprogramkode,
               sps.studieretningkode, sps.studierettstatkode,
               sps.studentstatkode, sps.terminkode_kull,
               sps.arstall_kull, p.kjonn, p.status_dod
        FROM fs.student s, fs.person p, fs.studieprogramstudent sps,
             fs.registerkort r
        WHERE  p.fodselsdato=s.fodselsdato AND
               p.personnr=s.personnr AND
               p.fodselsdato=sps.fodselsdato AND
               p.personnr=sps.personnr AND
               p.fodselsdato=r.fodselsdato AND
               p.personnr=r.personnr AND
               NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
               sps.status_privatist = 'J' AND
               r.arstall >= (%s - 1)
               """ % (self.year)
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


class UiOBetaling(access_FS.FSObject):
    ################################################
    # Kopiavgift
    # Ny ordning fra høsten 2004.
    ################################################
    def list_kopiavgift_fritak(self):  # GetStudFritattKopiavg
        """Lister fødselsnummer på de som er fritatt fra å måtte
        betale kopiavgift jmf den ordningen som ble innført høsten
        2004.  Kun de som har registerkort med betformkode lik:
          * 'FRITATT' - Dette er innreisende utenlandsstudenter
          * 'EKSTERN' - Dette er studenter som har betalt ved andre
                        samskipnader
        """

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
    
    def list_ok_kopiavgift(self):  # GetStudBetPapir
        """Lister ut fødselsnummer til alle de som har betalt
        kopiavgiften eller har fritak fra å betale denne avgiften."""

        qry = """
        SELECT DISTINCT r.fodselsdato, r.personnr
        FROM fs.fakturareskontrodetalj fkd,
             fs.fakturareskontro frk,
             fs.registerkort r
        WHERE r.TERMINKODE = :semester AND
              r.arstall = :year AND
              r.regformkode in ('STUDWEB','MANUELL') AND
              r.fodselsdato = frk.fodselsdato AND
              r.personnr = frk.personnr AND
              frk.status_betalt = 'J' AND
              frk.terminkode = r.terminkode AND
              frk.arstall = r.arstall AND
              frk.fakturastatuskode ='OPPGJORT' AND
              fkd.fakturanr = frk.fakturanr AND
              fkd.fakturadetaljtypekode = 'KOPIAVG'
        UNION
        SELECT DISTINCT r.fodselsdato, r.personnr
        FROM fs.registerkort r
        WHERE r.TERMINKODE = :semester AND
              r.arstall = :year AND
              r.betformkode IN ('FRITATT', 'EKSTERN')"""
        return self.db.query(qry, {'semester': self.semester,
                                   'year': self.year})


class FS(access_FS.FS):
    def __init__(self, db=None, user=None, database=None):
        super(FS, self).__init__(db=db, user=user, database=database)

        # Override with uio-spesific classes
        self.student = UiOStudent(self.db)
        self.portal = UiOPortal(self.db)
        self.betaling = UiOBetaling(self.db)

    def list_dbfg_usernames(self, fetchall = False):
        """
        Get all usernames and return them as a sequence of db_rows.

        NB! This function does *not* return a 2-tuple. Only a sequence of
        all usernames (the column names can be obtains from db_row objects)
        """

        query = """
        SELECT username as username
        FROM all_users
        """
        return self.db.query(query, fetchall = fetchall)

    def list_dba_usernames(self, fetchall = False):
        """
        Get all usernames for internal statistics.
        """

        query = """
        SELECT
           lower(username) as username
        FROM
           dba_users
        WHERE
           default_tablespace = 'USERS' and account_status = 'OPEN'
        """

        return self.db.query(query, fetchall = fetchall)
    # end list_dba_usernames
        
# arch-tag: 22ae9ce8-a845-40b8-bc4d-dcb51a54ca2a

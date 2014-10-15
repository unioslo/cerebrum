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
    def list(self, **kwargs): # GetStudent_50
        """Hent personer med opptak til et studieprogram ved
        institusjonen og som enten har vært registrert siste året
        eller opptak efter 2003-01-01.  Henter ikke de som har
        fremtidig opptak.  Disse kommer med 14 dager før dato for
        tildelt opptak.  Alle disse skal ha affiliation med status
        kode 'opptak' til stedskoden sp.faknr_studieansv +
        sp.instituttnr_studieansv + sp.gruppenr_studieansv.
        """
        return self._list_gyldigopptak(**kwargs) \
               + self._list_drgradsopptak(**kwargs) \
               +  self._list_gammelopptak_semreg(**kwargs)

    def _list_gyldigopptak(self, fodselsdato=None, personnr=None):
        """Alle med gyldig opptak tildelt for 2 år eller mindre siden
        samt alle med opptak som blir gyldig om 14 dager.
        """

        extra = ""
        if fodselsdato and personnr:
            extra = "s.fodselsdato=:fodselsdato AND s.personnr=:personnr AND"

        qry = """
        SELECT DISTINCT
           s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
           s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
           s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
           p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
           p.adresseland_hjemsted, p.status_reserv_nettpubl,
           p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
           sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
           sps.arstall_kull, sp.studienivakode, p.kjonn, p.status_dod,
           s.studentnr_tildelt
        FROM fs.student s, fs.person p, fs.studieprogramstudent sps,
           fs.studieprogram sp
        WHERE  p.fodselsdato=s.fodselsdato AND
           p.personnr=s.personnr AND
           p.fodselsdato=sps.fodselsdato AND
           p.personnr=sps.personnr AND
           %s
           sps.studieprogramkode=sp.studieprogramkode AND
           NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
           sps.status_privatist = 'N' AND
           sps.dato_studierett_tildelt < SYSDATE + 14 AND           
           sps.dato_studierett_tildelt >= to_date('2003-01-01', 'yyyy-mm-dd') AND
           %s
           """ % (extra, self._is_alive())
        return self.db.query(qry, locals())

    def _list_drgradsopptak(self, fodselsdato=None, personnr=None):
        """Alle drgradsstudenter med ikke utgått opptak til drgrads-
        studieprogram.
        """

        extra = ""
        if fodselsdato and personnr:
            extra = "s.fodselsdato=:fodselsdato AND s.personnr=:personnr AND"

        qry = """
        SELECT DISTINCT
           s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
           s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
           s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
           p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
           p.adresseland_hjemsted, p.status_reserv_nettpubl,
           p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
           sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
           sps.arstall_kull, sp.studienivakode, p.kjonn, p.status_dod,
           s.studentnr_tildelt
        FROM fs.student s, fs.person p, fs.studieprogramstudent sps,
           fs.studieprogram sp
        WHERE  p.fodselsdato=s.fodselsdato AND
           p.personnr=s.personnr AND
           p.fodselsdato=sps.fodselsdato AND
           p.personnr=sps.personnr AND
           %s
           (NVL(sps.dato_beregnet_slutt, sysdate) >= SYSDATE OR
           NVL(sps.dato_planlagt_slutt, sysdate) >= SYSDATE) AND
           sps.status_privatist='N' AND
           sps.studieprogramkode=sp.studieprogramkode AND
           sp.studienivakode >= 900 AND
           %s""" % (extra, self._is_alive())
        return self.db.query(qry, locals())

    def _list_gammelopptak_semreg(self, fodselsdato=None, personnr=None):
        """Alle med gyldig opptak som har hatt en forekomst i
        registerkort i løpet av fjoråret.
        """

        extra = ""
        if fodselsdato and personnr:
            extra = "s.fodselsdato=:fodselsdato AND s.personnr=:personnr AND"

        qry = """
        SELECT DISTINCT
           s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
           s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
           s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
           p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
           p.adresseland_hjemsted, p.status_reserv_nettpubl,
           p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
           sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
           sps.arstall_kull, sp.studienivakode, p.kjonn, p.status_dod,
           s.studentnr_tildelt
        FROM fs.student s, fs.person p, fs.studieprogramstudent sps,
           fs.registerkort r, fs.studieprogram sp
        WHERE  p.fodselsdato=s.fodselsdato AND
           p.personnr=s.personnr AND
           p.fodselsdato=sps.fodselsdato AND
           p.personnr=sps.personnr AND
           p.fodselsdato=r.fodselsdato AND
           p.personnr=r.personnr AND
           %s
           sps.studieprogramkode=sp.studieprogramkode AND
           NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
           sps.status_privatist = 'N' AND
           r.arstall >= (%s - 1) AND
           %s""" % (extra, self.year, self._is_alive())
        return self.db.query(qry, locals())

    def list_aktiv(self, **kwargs):  # GetStudentAktiv_50
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
        return self._list_aktiv_semreg(**kwargs) \
               + self._list_aktiv_enkeltemne(**kwargs) \
               + self._list_aktiv_avlagteksamen(**kwargs) \
               + self._list_aktiv_utdplan(**kwargs)

    def _list_aktiv_semreg(self, fodselsdato=None, personnr=None):
        """Alle semesterregistrerte som i tillegg har en
        eksamensmelding i et emne som kan inngå i et studieprogram som
        de har opptak til.
        """

        extra = ""
        if fodselsdato and personnr:
            extra = "s.fodselsdato=:fodselsdato AND s.personnr=:personnr AND"

        qry = """
        SELECT DISTINCT
           s.fodselsdato, s.personnr, sp.studieprogramkode,
           sps.studieretningkode, sps.terminkode_kull, sps.arstall_kull,
           em.emnekode, em.versjonskode, s.studentnr_tildelt
        FROM fs.studieprogram sp, fs.studieprogramstudent sps, fs.student s,
           fs.registerkort r, fs.eksamensmelding em,
           fs.emne_i_studieprogram es, fs.person p
           
        WHERE s.fodselsdato=r.fodselsdato AND
           s.personnr=r.personnr AND
           s.fodselsdato=p.fodselsdato AND
           s.personnr=p.personnr AND
           s.fodselsdato=sps.fodselsdato AND
           s.personnr=sps.personnr AND
           s.fodselsdato=em.fodselsdato AND
           s.personnr=em.personnr AND
           %s
           es.studieprogramkode=sp.studieprogramkode AND
           em.emnekode=es.emnekode AND
           sps.status_privatist='N' AND
           sps.studieprogramkode=sp.studieprogramkode AND
           r.status_reg_ok = 'J' AND
           r.status_bet_ok = 'J' AND
           NVL(r.status_ugyldig, 'N') = 'N' AND
           NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
           %s AND
           %s""" % (extra, self._get_termin_aar(only_current=1),
                    self._is_alive())
        return self.db.query(qry, locals())

    def _list_aktiv_enkeltemne(self, fodselsdato=None, personnr=None):
        """Alle semesterregistrerte med gyldig opptak til
        studieprogrammet 'ENKELTEMNE' som har en gyldig eksamensmelding
        i et emne som kan inngå i et vilkårlig studieprogram.
        """

        extra = ""
        if fodselsdato and personnr:
            extra = "s.fodselsdato=:fodselsdato AND s.personnr=:personnr AND"

        qry = """
        SELECT DISTINCT
           s.fodselsdato, s.personnr, sp.studieprogramkode,
           sps.studieretningkode, sps.terminkode_kull, sps.arstall_kull,
           em.emnekode, em.versjonskode, s.studentnr_tildelt
        FROM fs.studieprogram sp, fs.studieprogramstudent sps, fs.student s,
           fs.registerkort r, fs.eksamensmelding em,
           fs.person p
        WHERE sps.studieprogramkode='ENKELTEMNE' AND
           s.fodselsdato=r.fodselsdato AND
           s.personnr=r.personnr AND
           s.fodselsdato=p.fodselsdato AND
           s.personnr=p.personnr AND
           s.fodselsdato=sps.fodselsdato AND
           s.personnr=sps.personnr AND
           s.fodselsdato=em.fodselsdato AND
           s.personnr=em.personnr AND
           %s
           sps.status_privatist='N' AND
           sps.studieprogramkode=sp.studieprogramkode AND
           r.status_reg_ok = 'J' AND
           r.status_bet_ok = 'J' AND
           NVL(r.status_ugyldig, 'N') = 'N' AND
           NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
           %s AND
           %s""" % (extra, self._get_termin_aar(only_current=1),
                    self._is_alive())
        return self.db.query(qry, locals())

    def _list_aktiv_utdplan(self, fodselsdato=None, personnr=None):
        """Alle semesterregistrerte som i tillegg har bekreftet
        utdanningsplan i inneværende semester.
        """

        extra = ""
        if fodselsdato and personnr:
            extra = "s.fodselsdato=:fodselsdato AND s.personnr=:personnr AND"

        qry = """
        SELECT DISTINCT
           s.fodselsdato, s.personnr, sp.studieprogramkode,
           sps.studieretningkode, sps.terminkode_kull, sps.arstall_kull,
           NULL as emnekode, NULL as versjonskode, s.studentnr_tildelt
        FROM fs.student s, fs.studieprogramstudent sps, fs.registerkort r,
           fs.studprogstud_planbekreft spp, fs.studieprogram sp,
           fs.person p
        WHERE s.fodselsdato=sps.fodselsdato AND
           s.personnr=sps.personnr AND
           s.fodselsdato=p.fodselsdato AND
           s.personnr=p.personnr AND
           s.fodselsdato=r.fodselsdato AND
           s.personnr=r.personnr AND
           s.fodselsdato=spp.fodselsdato AND
           s.personnr=spp.personnr AND
           %s
           sps.studieprogramkode=sp.studieprogramkode AND
           sp.status_utdplan='J' AND
           sps.status_privatist='N' AND
           spp.studieprogramkode=sps.studieprogramkode AND
           NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
           spp.dato_bekreftet < SYSDATE AND
           spp.arstall_bekreft=%d AND
           spp.terminkode_bekreft='%s' AND
           r.status_reg_ok = 'J' AND
           r.status_bet_ok = 'J' AND
           NVL(r.status_ugyldig, 'N') = 'N' AND
           %s AND
           %s""" % (extra, self.year, self.semester,
                    self._get_termin_aar(only_current=1), self._is_alive())
        return self.db.query(qry, locals())

    def _list_aktiv_avlagteksamen(self, fodselsdato=None, personnr=None):
        """Alle semesterregistrerte som har avlagt eksamen i inneværende
        år.  Ifølge STA er dette det riktige kravet. mulig at vi ønsker
        å mene noe annet etterhvert.
        """

        extra = ""
        if fodselsdato and personnr:
            extra = "sps.fodselsdato=:fodselsdato AND sps.personnr=:personnr AND"

        qry = """
        SELECT DISTINCT
           sp.fodselsdato, sp.personnr, sps.studieprogramkode,
           sps.studieretningkode, sps.terminkode_kull, sps.arstall_kull,
           sp.emnekode, sp.versjonskode, s.studentnr_tildelt
        FROM fs.studentseksprotokoll sp, fs.studieprogramstudent sps,
           fs.emne_i_studieprogram es, fs.registerkort r,
           fs.person p, fs.student s
        WHERE sp.arstall=%s AND
           sp.fodselsdato=sps.fodselsdato AND
           sp.personnr=sps.personnr AND
           sp.fodselsdato=p.fodselsdato AND
           sp.personnr=p.personnr AND
           s.fodselsdato=p.fodselsdato AND
           s.personnr=p.personnr AND
           r.fodselsdato=sps.fodselsdato AND
           r.personnr=sps.personnr AND
           %s
           sp.institusjonsnr='185' AND
           sp.emnekode=es.emnekode AND
           es.studieprogramkode=sps.studieprogramkode AND
           NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
           sps.status_privatist='N' AND
           %s AND
           %s
        """ % (self.year, extra, self._get_termin_aar(only_current=1),
               self._is_alive())
        return self.db.query(qry, locals())

    def list_privatist_emne(self, fodselsdato=None, personnr=None):  # GetStudentPrivatistEmne_50
        """Hent personer som er uekte privatister, dvs. som er
	eksamensmeldt til et emne i et studieprogram de ikke har
	opptak til. Disse tildeles affiliation privatist til stedet
	som eier studieprogrammet de har opptak til.  Dette blir ikke
	helt riktig efter som man kan ha opptak til studieprogramet
	'ENKELTEMNE' som betyr at man kan være ordninær student selv
	om man havner i denne gruppen som plukkes ut av dette søket.
        """

        extra = ""
        if fodselsdato and personnr:
            extra = "s.fodselsdato=:fodselsdato AND s.personnr=:personnr AND"

	qry = """
        SELECT s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
               s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
               s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
               p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
               p.adresseland_hjemsted, p.status_reserv_nettpubl,
               p.sprakkode_malform, p.kjonn, p.status_dod, em.emnekode,
               s.studentnr_tildelt
        FROM fs.student s, fs. person p, fs.registerkort r,
             fs.eksamensmelding em
        WHERE s.fodselsdato=p.fodselsdato AND
              s.personnr=p.personnr AND
              p.fodselsdato=r.fodselsdato AND
              p.personnr=r.personnr AND
              p.fodselsdato=em.fodselsdato AND
              p.personnr=em.personnr AND
              em.arstall >= %s AND
              %s
              %s AND
              NOT EXISTS
              (SELECT 'x' FROM fs.studieprogramstudent sps,
                               fs.emne_i_studieprogram es
               WHERE p.fodselsdato=sps.fodselsdato AND
                     p.personnr=sps.personnr AND
                     es.emnekode=em.emnekode AND
                     es.studieprogramkode = sps.studieprogramkode AND
                     NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= SYSDATE)
              AND
              %s
        """ % (self.year, extra, self._get_termin_aar(only_current=1),
               self._is_alive())
        return self.db.query(qry, locals())

    def list_privatist(self, fodselsdato=None, personnr=None): # GetStudentPrivatist_50
        
        """Hent personer med privatist 'opptak' til et studieprogram ved
        institusjonen og som enten har vært registrert siste året eller
        har fått privatist 'opptak' efter 2003-01-01.  Henter ikke de
        som har fremtidig opptak.  Disse kommer med 14 dager før dato
        for tildelt privatist 'opptak'.  Alle disse skal ha affiliation
        med status kode 'privatist' til stedskoden sp.faknr_studieansv +
        sp.instituttnr_studieansv + sp.gruppenr_studieansv.
        """

        extra1 = extra2 = ""
        if fodselsdato and personnr:
            # We can't use the same bind variable in two different SELECT
            # expressions.
            extra1 = "s.fodselsdato=:fodselsdato AND s.personnr=:personnr AND"
            extra2 = "s.fodselsdato=:fodselsdato2 AND s.personnr=:personnr2 AND"

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
               sps.arstall_kull, p.kjonn, p.status_dod, s.studentnr_tildelt
        FROM fs.student s, fs.person p, fs.studieprogramstudent sps
        WHERE  p.fodselsdato=s.fodselsdato AND
               p.personnr=s.personnr AND
               p.fodselsdato=sps.fodselsdato AND
               p.personnr=sps.personnr AND
               %s
               NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
               sps.status_privatist = 'J' AND
               sps.dato_studierett_tildelt < SYSDATE + 14 AND
               sps.dato_studierett_tildelt >= to_date('2003-01-01',
                                                      'yyyy-mm-dd') AND
               %s
       """ % (extra1, self._is_alive())
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
               sps.arstall_kull, p.kjonn, p.status_dod, s.studentnr_tildelt
        FROM fs.student s, fs.person p, fs.studieprogramstudent sps,
             fs.registerkort r
        WHERE  p.fodselsdato=s.fodselsdato AND
               p.personnr=s.personnr AND
               p.fodselsdato=sps.fodselsdato AND
               p.personnr=sps.personnr AND
               p.fodselsdato=r.fodselsdato AND
               p.personnr=r.personnr AND
               %s
               NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
               sps.status_privatist = 'J' AND
               r.arstall >= (%s - 1) AND
               %s
               """ % (extra2, self.year, self._is_alive())
        return self.db.query(qry, {'fodselsdato': fodselsdato,
                                   'fodselsdato2': fodselsdato,
                                   'personnr': personnr,
                                   'personnr2': personnr})


class UiOPortal(access_FS.FSObject):
    def list_eksmeld(self):  # GetPortalInfo_50
        """Hent ut alle eksamensmeldinger i nåværende semester med all
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

    def list_kopiavgift_data(self, kun_fritak=True, semreg=False, fodselsdato=None, personnr=None):
        """List alle som har betalt kopiavgift eller har fritak for
           betaling av kopiavgift. Fritak for kopiavgift betegnes ved
           at registerkortet for inneværende semester får
           betalingsformkode 'FRITATT' eller 'EKSTERN'. Hvis
           kun_fritak=True listes alle som har fritak uavhengig om de
           er semesterregistrert. Hvis semreg=True listet alle som har
           betalt kopiavgift eller har fritak for kopiavgift og som er
           semesterregistrert for inneværende semester. Erstatter
           list_kopiavgift_fritak og list_ok_kopiavgift.""" 
           
        extra1 = extra2 = extra_semreg1 = extra_semreg2 = extra_from = ""

        if fodselsdato and personnr:
            extra1 = "frk.fodselsdato=:fodselsdato AND frk.personnr=:personnr AND"
            extra2 = "r.fodselsdato=:fodselsdato2 AND r.personnr=:personnr2 AND"

        if semreg:
            extra_semreg2 = """r.status_reg_ok = 'J' AND
                               NVL(r.status_ugyldig, 'N') = 'N' AND"""
            extra_from = ", fs.registerkort r"
            extra_semreg1 = """r.terminkode = :semester3 AND
                               r.arstall = :year3 AND
                               r.status_reg_ok = 'J' AND  
                               NVL(r.status_ugyldig, 'N') = 'N'
                               AND r.fodselsdato = frk.fodselsdato AND 
                               r.personnr = frk.personnr AND"""

        qry1 = """
        SELECT DISTINCT r.fodselsdato, r.personnr
        FROM fs.registerkort r
        WHERE r.terminkode = :semester2 AND
        r.arstall = :year2 AND
        %s
        %s
        r.betformkode IN ('FRITATT', 'EKSTERN')""" % (extra_semreg2, extra2)

        if kun_fritak:
            return self.db.query(qry1, {'fodselsdato2': fodselsdato,
                                        'personnr2': personnr,
                                        'semester2': self.semester,
                                        'year2': self.year})
        qry = qry1 + """
        UNION
        SELECT DISTINCT frk.fodselsdato, frk.personnr
        FROM fs.fakturareskontrodetalj fkd,
             fs.fakturareskontro frk
             %s
        WHERE %s
             frk.status_betalt = 'J' AND
             frk.terminkode = :semester AND
             frk.arstall = :year AND
             %s 
             frk.fakturastatuskode ='OPPGJORT' AND
             fkd.fakturanr = frk.fakturanr AND
             fkd.fakturadetaljtypekode = 'KOPIAVG'""" % (extra_from, extra_semreg1, extra1)
        if semreg:
            return self.db.query(qry, {'fodselsdato': fodselsdato,
                                       'fodselsdato2': fodselsdato,
                                       'personnr': personnr,
                                       'personnr2': personnr,
                                       'semester': self.semester,
                                       'semester2': self.semester,
                                       'semester3': self.semester,
                                       'year': self.year,
                                       'year2': self.year,
                                       'year3': self.year})
        
        return self.db.query(qry, {'fodselsdato': fodselsdato,
                                   'fodselsdato2': fodselsdato,
                                   'personnr': personnr,
                                   'personnr2': personnr,
                                   'semester': self.semester,
                                   'semester2': self.semester,
                                   'year': self.year,
                                   'year2': self.year})

class UiOUndervisning(access_FS.Undervisning):

    def list_undervisningenheter(self, year=None, sem=None): # GetUndervEnhetAll
        if year is None:
            year = self.year
        if sem is None:
            sem = self.semester
        return self.db.query("""
        SELECT
          ue.institusjonsnr, ue.emnekode, ue.versjonskode, ue.terminkode,
          ue.arstall, ue.terminnr, e.institusjonsnr_kontroll,
          e.faknr_kontroll, e.instituttnr_kontroll, e.gruppenr_kontroll,
          e.emnenavn_bokmal, e.emnenavnfork, ue.status_eksport_lms
        FROM
          fs.undervisningsenhet ue, fs.emne e, fs.arstermin t
        WHERE
          ue.institusjonsnr = e.institusjonsnr AND
          ue.emnekode       = e.emnekode AND
          ue.versjonskode   = e.versjonskode AND
          ue.terminkode IN ('VÅR', 'HØST') AND
          ue.terminkode = t.terminkode AND
          (ue.arstall > :aar OR
           (ue.arstall = :aar2 AND
            EXISTS(SELECT 'x' FROM fs.arstermin tt
            WHERE tt.terminkode = :sem AND
                  t.sorteringsnokkel >= tt.sorteringsnokkel)))
          """, {'aar': year,
                'aar2': year, # db-driver bug work-around
                'sem': sem})
    
    def list_aktiviteter(self, start_aar=time.localtime()[0],
                         start_semester=None):
        if start_semester is None:
            start_semester = self.semester
            
        return self.db.query("""
        SELECT  
          ua.institusjonsnr, ua.emnekode, ua.versjonskode,
          ua.terminkode, ua.arstall, ua.terminnr, ua.aktivitetkode,
          ua.undpartilopenr, ua.disiplinkode, ua.undformkode, ua.aktivitetsnavn,
          ua.lmsrommalkode, ua.status_eksport_lms,
          e.institusjonsnr_kontroll, e.faknr_kontroll,
          e.instituttnr_kontroll, e.gruppenr_kontroll
        FROM
          fs.undaktivitet ua,
          fs.arstermin t,
          fs.emne e
        WHERE
          ua.institusjonsnr = e.institusjonsnr AND
          ua.emnekode       = e.emnekode AND
          ua.versjonskode   = e.versjonskode AND
          ua.undpartilopenr IS NOT NULL AND
          ua.disiplinkode IS NOT NULL AND
          ua.undformkode IS NOT NULL AND
          ua.terminkode IN ('VÅR', 'HØST') AND
          ua.terminkode = t.terminkode AND
          ((ua.arstall = :aar AND
            EXISTS (SELECT 'x' FROM fs.arstermin tt
                    WHERE tt.terminkode = :semester AND
                          t.sorteringsnokkel >= tt.sorteringsnokkel)) OR
           ua.arstall > :aar)""",
                             {'aar': start_aar,
                              'semester': start_semester})

    
    def list_studenter_kull(self, studieprogramkode, terminkode, arstall):
        """Hent alle studentene som er oppført på et gitt kull."""

        query = """
        SELECT DISTINCT
            fodselsdato, personnr
        FROM
            fs.studieprogramstudent
        WHERE
            studentstatkode IN ('AKTIV', 'PERMISJON') AND
            NVL(dato_studierett_gyldig_til,SYSDATE)>= SYSDATE AND
            studieprogramkode = :studieprogramkode AND
            terminkode_kull = :terminkode_kull AND
            arstall_kull = :arstall_kull
        """

        return self.db.query(query, {"studieprogramkode" : studieprogramkode,
                                     "terminkode_kull"   : terminkode,
                                     "arstall_kull"      : arstall})

    def list_studenter_alle_undenh(self):
        """Hent alle studenter på alle undenh.

        NB! Det er ca. 800'000+ rader i FSPROD i fs.undervisningsmelding.
        Dette kan koste en del minne, så 1) fetchall=True er nok dumt 2) Man
        burde bearbeide strukturen litt raskere. 

        Spørringen *er* litt annerledes enn L{list_studenter_underv_enhet},
        men baardj har foreslått denne spørringen også.
        """

        qry = """
        SELECT
          fodselsdato, personnr,
          institusjonsnr, emnekode, versjonskode, terminkode, arstall, terminnr
        FROM
          fs.undervisningsmelding
        WHERE
          terminkode in ('VÅR', 'HØST') AND
          arstall >= :aar1

        UNION

        SELECT
          fodselsdato, personnr,
          institusjonsnr, emnekode, versjonskode,
            (case when manednr <= 6 then 'VÅR'
                  when manednr >= 7 then 'HØST'
             end) as terminkode,
          arstall, 1 as terminnr
        FROM
          fs.eksamensmelding
        WHERE
          arstall >= :aar2
        """

        return self.db.query(qry, {"aar1": self.year,
                                   "aar2": self.year}, fetchall=False)
    # end list_studenter_alle_undenh


    def list_studenter_alle_undakt(self):
        """Hent alle studenter på alle undakt.

        NB! Det er ca. 500'000+ rader i FSPROD i student_pa_undervisningsparti.
        Det kan koste en del minne.
        """
        
        qry = """
        SELECT
          su.fodselsdato, su.personnr,
          ua.institusjonsnr, ua.emnekode, ua.versjonskode, ua.terminkode,
          ua.arstall, ua.terminnr, ua.aktivitetkode
        FROM
          fs.student_pa_undervisningsparti su,
          fs.undaktivitet ua
        WHERE
          su.terminnr       = ua.terminnr       AND
          su.institusjonsnr = ua.institusjonsnr AND
          su.emnekode       = ua.emnekode       AND
          su.versjonskode   = ua.versjonskode   AND
          su.terminkode     = ua.terminkode     AND
          su.arstall        = ua.arstall        AND
          su.undpartilopenr = ua.undpartilopenr AND
          su.disiplinkode   = ua.disiplinkode   AND
          su.undformkode    = ua.undformkode AND
          su.arstall >= :aar
        """

        return self.db.query(qry, {"aar": self.year}, fetchall=False)
    # end list_studenter_alle_undakt


class UiOEVU(access_FS.EVU):

    def list_kurs(self, date=time.localtime()):  # GetEvuKurs
        """Henter info om aktive EVU-kurs, der aktive er de som har
        status_aktiv satt til 'J' og som ikke er avsluttet
        (jmf. dato_til).
        """
        
        qry = """
        SELECT etterutdkurskode, kurstidsangivelsekode,
          etterutdkursnavn, etterutdkursnavnkort, emnekode,
          institusjonsnr_adm_ansvar, faknr_adm_ansvar,
          instituttnr_adm_ansvar, gruppenr_adm_ansvar,
          TO_CHAR(NVL(dato_fra, SYSDATE), 'YYYY-MM-DD') AS dato_fra,
          TO_CHAR(NVL(dato_til, SYSDATE), 'YYYY-MM-DD') AS dato_til,
          status_aktiv, status_nettbasert_und, status_eksport_lms
        FROM fs.etterutdkurs
        WHERE status_aktiv='J' AND
          NVL(dato_til, SYSDATE) >= (SYSDATE - 30)
        """
        return self.db.query(qry)
    # end list_kurs


    def get_kurs_aktivitet(self, kurs, tid): # GetAktivitetEvuKurs
        """Henter information om aktive EVU-kursaktiviteter som tilhører et
        gitt EVU-kurs.
        """
        
        qry = """
        SELECT k.etterutdkurskode, k.kurstidsangivelsekode, k.aktivitetskode,
               k.aktivitetsnavn, k.undformkode, k.status_eksport_lms
        FROM fs.kursaktivitet k
        WHERE k.etterutdkurskode='%s' AND
              k.kurstidsangivelsekode='%s'
        """ % (kurs, tid)

        return self.db.query(qry)
    # end get_kurs_aktivitet


    def list_studenter_alle_kursakt(self):
        qry = """
        SELECT
          d.fodselsdato, d.personnr,
          k.etterutdkurskode, k.kurstidsangivelsekode, k.aktivitetskode
        FROM fs.deltaker d, fs.kursaktivitet_deltaker k
        WHERE k.deltakernr = d.deltakernr
        """
        return self.db.query(qry)
    # end list_studenter_alle_kursakt
# end UiOEVU


class UiOStudieInfo(access_FS.StudieInfo):

    def list_kull(self):
        """Henter informasjon om aktive studiekull."""
        qry = """
        SELECT DISTINCT
          k.studieprogramkode, k.terminkode, k.arstall, k.studiekullnavn, 
          k.kulltrinn_start, k.terminnr_maks, k.status_generer_epost,
          s.institusjonsnr_studieansv, s.faknr_studieansv,
          s.instituttnr_studieansv, s.gruppenr_studieansv
        FROM  fs.kull k, fs.studieprogram s, fs.studieprogram
        WHERE
          k.status_aktiv = 'J' AND
          s.studieprogramkode = k.studieprogramkode AND
          /* IVR 2007-11-12: According to baardj, it makes no sense to
             register 'kull' for earlier timeframes.
             IVR 2008-05-14: A minor adjustment... */
          k.arstall >= 2002
        """
        return self.db.query(qry)
    # end list_kull
# end UiOStudieInfo


class FS(access_FS.FS):
    def __init__(self, db=None, user=None, database=None):
        super(FS, self).__init__(db=db, user=user, database=database)

        # Override with uio-spesific classes
        self.student = UiOStudent(self.db)
        self.portal = UiOPortal(self.db)
        self.betaling = UiOBetaling(self.db)
        self.undervisning = UiOUndervisning(self.db)
        self.evu = UiOEVU(self.db)
        self.info = UiOStudieInfo(self.db)

    def list_dbfg_usernames(self, fetchall = False):
        """Get all usernames and return them as a sequence of db_rows.

        NB! This function does *not* return a 2-tuple. Only a sequence of
        all usernames (the column names can be obtains from db_row objects)
        """

        query = """
        SELECT username as username
        FROM all_users
        """
        return self.db.query(query, fetchall=fetchall)

    def list_dba_usernames(self, fetchall = False):
        """Get all usernames for internal statistics."""

        query = """
        SELECT
           lower(username) as username
        FROM
           dba_users
        WHERE
           default_tablespace = 'USERS' and account_status = 'OPEN'
        """

        return self.db.query(query, fetchall=fetchall)


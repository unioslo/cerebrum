# -*- coding: utf-8 -*-
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

from __future__ import unicode_literals
import time

from Cerebrum.modules.no import access_FS


fsobject = access_FS.fsobject


@fsobject('student', '<7.8')
class HiOfStudent(access_FS.Student):
    # Vi bruker list_privatist, og list_tilbud fra no/access_FS

    def list_aktiv(self, fodselsdato=None, personnr=None):
        """ Hent opplysninger om studenter definert som aktive
        ved HiOF. En aktiv student er en student som har et gyldig
        opptak til et studieprogram der studentstatuskode er 'AKTIV'
        eller 'PERMISJON' og sluttdatoen er enten i fremtiden eller
        ikke satt."""
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
          nvl(trim(leading '0' from
                   trim(leading '+' from p.telefonlandnr_mobil)), '47')
                telefonlandnr_mobil,
          p.telefonretnnr_mobil, p.telefonnr_mobil,
          sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
          sps.arstall_kull, p.kjonn, p.status_dod,
          s.studentnr_tildelt, kks.klassekode,
          kks.status_aktiv AS status_aktiv_klasse
        FROM fs.studieprogramstudent sps, fs.person p,
             fs.student s, fs.kullklassestudent kks
        WHERE p.fodselsdato = sps.fodselsdato AND
          p.personnr = sps.personnr AND
          p.fodselsdato = s.fodselsdato AND
          p.personnr = s.personnr AND
          sps.fodselsdato = kks.fodselsdato(+) AND
          sps.personnr = kks.personnr(+) AND
          sps.studieprogramkode = kks.studieprogramkode(+) AND
          sps.terminkode_start = kks.terminkode_start(+) AND
          sps.arstall_start = kks.arstall_start(+) AND
          %s AND
          %s
          sps.studentstatkode IN ('AKTIV', 'PERMISJON', 'DELTID') AND
          NVL(sps.dato_studierett_gyldig_til,SYSDATE)>= SYSDATE
          """ % (self._is_alive(), extra)
        return self.db.query(qry, locals())

    def list_eksamensmeldinger(self):  # GetAlleEksamener
        """Hent ut alle eksamensmeldinger i nåværende sem."""

        qry = """
        SELECT p.fodselsdato, p.personnr, vm.emnekode, vm.studieprogramkode
        FROM fs.person p, fs.vurdkombmelding vm,
        fs.vurderingskombinasjon vk, fs.vurderingstid vt,
        fs.vurdkombenhet ve
        WHERE p.fodselsdato=vm.fodselsdato AND
              p.personnr=vm.personnr AND
              vm.institusjonsnr = vk.institusjonsnr AND
              vm.emnekode = vk.emnekode AND
              vm.versjonskode = vk.versjonskode AND
              vm.vurdkombkode = vk.vurdkombkode AND
              vk.vurdordningkode IS NOT NULL and
              vm.arstall = vt.arstall AND
              vm.vurdtidkode = vt.vurdtidkode AND
              ve.emnekode = vm.emnekode AND
              ve.versjonskode = vm.versjonskode AND
              ve.vurdkombkode = vm.vurdkombkode AND
              ve.vurdtidkode = vm.vurdtidkode AND
              ve.institusjonsnr = vm.institusjonsnr AND
              ve.arstall = vt. arstall AND
              ve.vurdtidkode = vt.vurdtidkode AND
              ve.arstall_reell = %s
              AND %s
        ORDER BY fodselsdato, personnr
        """ % (self.year, self._is_alive())
        return self.db.query(qry)


@fsobject('student', '>=7.8')
class HiOfStudent78(HiOfStudent, access_FS.Student78):
    # Vi bruker list_privatist, og list_tilbud fra no/access_FS

    def list_aktiv(self, fodselsdato=None, personnr=None):
        """ Hent opplysninger om studenter definert som aktive
        ved HiOF. En aktiv student er en student som har et gyldig
        opptak til et studieprogram der studentstatuskode er 'AKTIV'
        eller 'PERMISJON' og sluttdatoen er enten i fremtiden eller
        ikke satt."""
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
          pt.telefonlandnr telefonlandnr_mobil,
          '' telefonretnnr_mobil, pt.telefonnr telefonnr_mobil,
          sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
          sps.arstall_kull, p.kjonn, p.status_dod,
          s.studentnr_tildelt, kks.klassekode,
          kks.status_aktiv AS status_aktiv_klasse
        FROM fs.studieprogramstudent sps
             LEFT JOIN fs.kullklassestudent kks ON
             sps.fodselsdato = kks.fodselsdato AND
             sps.personnr = kks.personnr AND
             sps.studieprogramkode = kks.studieprogramkode AND
             sps.terminkode_start = kks.terminkode_start AND
             sps.arstall_start = kks.arstall_start,
             fs.student s, fs.person p
             LEFT JOIN fs.persontelefon pt ON
             pt.fodselsdato = p.fodselsdato AND
             pt.personnr = p.personnr AND
             pt.telefonnrtypekode = 'MOBIL'
        WHERE p.fodselsdato = sps.fodselsdato AND
          p.personnr = sps.personnr AND
          p.fodselsdato = s.fodselsdato AND
          p.personnr = s.personnr AND
          %s AND
          %s
          sps.studentstatkode IN ('AKTIV', 'PERMISJON', 'DELTID') AND
          NVL(sps.dato_studierett_gyldig_til,SYSDATE)>= SYSDATE
          """ % (self._is_alive(), extra)
        return self.db.query(qry, locals())


@fsobject('undervisning', '<7.8')
class HiOfUndervisning(access_FS.Undervisning):
    # TBD: avskaffe UiO-spesifikke søk for list_undervisningsenheter
    #      og list_studenter_underv_enhet.
    #      Prøve å lage generell list_studenter_kull.
    #      Prøve å fjerne behov for override-metoder her

    # We redefine this, as HiOf uses other dates for semesters
    def _get_termin_aar(self, only_current=0):
        """Generate an SQL query part for limiting registerkort to the current
        term and maybe also the previous term. The output from this method
        should be a part of an SQL query, and must have a reference to
        L{fs.registerkort} by the character 'r'.

        FS is working in terms and not with proper dates, so the query is
        generated differently depending on the current date:

        - From 1st of January to 15th of February: This year's 'VÅR' is
          returned. If L{only_current} is False, also last year's 'HØST' is
          included.

        - From 15th of February to 31st of July: Only this year's 'VÅR' is
          returned.

        - From 1st of August to 15th of September:
          This year's 'HØST' is returned.
          If L{only_current} is False, also this year's 'VÅR' is included.

        - From 15th of September to 31st of December: Only this year's 'HØST' is
          returned.

        @type only_current: bool
        @param only_current: If set to True, the query is limiting to only the
            current term. If False, the previous term is also included if we are
            early in the current term. This has no effect if the current date is
            more than halfway into the current term.

        @rtype: string
        @return: An SQL formatted string that should be put in a larger query.
            Example:
                (r.terminkode = 'HØST' and r.arstall = 2013)
            where 'r' refers to 'fs.registerkort r'.

        """
        if self.mndnr <= 7:
            # Months January - July == Spring semester
            current = "(r.terminkode = :spring AND r.arstall=%s)\n" % self.year
            if only_current or self.mndnr >= 3 or (self.mndnr == 2 and
                                                   self.dday > 15):
                return current
            return "(%s OR (r.terminkode = :autumn AND r.arstall=%d))\n" % (
                current, self.year-1)
        # Months August - December == Autumn semester
        current = "(r.terminkode = :autumn AND r.arstall=%d)\n" % self.year
        if only_current or self.mndnr >= 10 or (self.mndnr == 9 and
                                                self.dday > 15):
            return current
        return "(%s OR (r.terminkode = :spring AND r.arstall=%d))\n" %\
            (current, self.year)

    def _get_next_termin_aar(self):
        """henter neste semesters terminkode og årstal."""
        if self.mndnr <= 7:
            next = "(r.terminkode LIKE 'H_ST' AND r.arstall=%s)\n" % self.year
        else:
            next = "(r.terminkode LIKE 'V_R' AND r.arstall=%s)\n" %\
                (self.year + 1)
        return next

    def list_undervisningenheter(self, sem="current"):
        """Metoden som henter data om undervisningsenheter
        i nåverende (current) eller neste (next) semester. Default
        vil være nåværende semester. For hver undervisningsenhet
        henter vi institusjonsnr, emnekode, versjonskode, terminkode + årstall
        og terminnr."""
        qry = """
        SELECT DISTINCT
          r.institusjonsnr, r.emnekode, r.versjonskode, e.emnenavnfork,
          e.emnenavn_bokmal, e.faknr_kontroll, e.instituttnr_kontroll,
          e.gruppenr_kontroll, r.terminnr, r.terminkode, r.arstall,
          r.status_eksport_lms
        FROM fs.emne e, fs.undervisningsenhet r
        WHERE r.emnekode = e.emnekode AND
          r.versjonskode = e.versjonskode AND """
        if (sem == "current"):
            qry += """%s""" % self._get_termin_aar(only_current=1)
        else:
            qry += """%s""" % self._get_next_termin_aar()
        return self.db.query(qry, {'autumn': 'HØST',
                                   'spring': 'VÅR'})

    def list_aktiviteter(self):
        """Hent alle undakt for dette og neste semestre.
        """

        query = """
        SELECT
          r.institusjonsnr, r.emnekode, r.versjonskode,
          r.terminkode, r.arstall, r.terminnr, r.aktivitetkode,
          r.aktivitetsnavn, r.lmsrommalkode, r.status_eksport_lms,
          e.institusjonsnr_kontroll, e.faknr_kontroll,
          e.instituttnr_kontroll, e.gruppenr_kontroll
        FROM
          fs.undaktivitet r,
          fs.emne e
        WHERE
          r.institusjonsnr = e.institusjonsnr AND
          r.emnekode       = e.emnekode AND
          r.versjonskode   = e.versjonskode AND
          ( (%s) OR (%s) )
        """ % (self._get_termin_aar(only_current=1),
               self._get_next_termin_aar())

        return self.db.query(query, {'autumn': 'HØST',
                                     'spring': 'VÅR'})
    # end list_aktiviteter

    def list_studenter_underv_enhet(self,
                                    institusjonsnr,
                                    emnekode,
                                    versjonskode,
                                    terminkode,
                                    arstall,
                                    terminnr):
        """Finn fødselsnumrene til alle studenter på et gitt
        undervisningsenhet. Skal brukes til å generere grupper for
        adgang til CF."""
        qry = """
        SELECT DISTINCT
          fodselsdato, personnr
        FROM fs.undervisningsmelding
        WHERE
          institusjonsnr = :institusjonsnr AND
          emnekode = :emnekode AND
          versjonskode = :versjonskode AND
          terminnr = :terminnr AND
          terminkode = :terminkode AND
          arstall = :arstall """
        return self.db.query(qry, {'institusjonsnr': institusjonsnr,
                                   'emnekode': emnekode,
                                   'versjonskode': versjonskode,
                                   'terminnr': terminnr,
                                   'terminkode': terminkode,
                                   'arstall': arstall}
                             )
    # end list_studenter_underv_enhet

    def list_studenter_alle_undenh(self):
        """Hent alle studenter på alle undenh.

        Dette er potensielt *veldig* mange. Spørringen er primært myntet på
        CF-utplukk og bør således ta minst alle studenter dette og neste
        semester.
        """

        qry = """
        SELECT
          fodselsdato, personnr,
          institusjonsnr, emnekode, versjonskode, terminkode, arstall, terminnr
        FROM
          fs.undervisningsmelding
        WHERE
          terminkode in (:spring, :autumn) AND
          arstall >= :aar
        """

        return self.db.query(qry,
                             {"aar": self.year,
                              'autumn': 'HØST',
                              'spring': 'VÅR'},
                              fetchall=True)
    # end list_studenter_underv_enhet

    def list_studenter_alle_kullklasser(self):
        """Hent alle studenter fordelt på kullklasser.
        """

        query = """
        SELECT DISTINCT
            kks.fodselsdato, kks.personnr,
            kks.studieprogramkode, kks.terminkode, kks.arstall, kks.klassekode
        FROM
            fs.kullklassestudent kks,
            fs.studieprogramstudent sps,
            fs.kull k
        WHERE
            sps.fodselsdato = kks.fodselsdato AND
            sps.personnr = kks.personnr AND
            sps.studieprogramkode = kks.studieprogramkode AND
            sps.terminkode_start = kks.terminkode_start AND
            sps.arstall_start = kks.arstall_start AND
            /*
             * vi vil ha studenter knyttet til aktive kull. resten er
             * uinteressant
             */
            kks.studieprogramkode = k.studieprogramkode AND
            kks.terminkode = k.terminkode AND
            kks.arstall = k.arstall AND
            k.status_aktiv = 'J' AND
            sps.studentstatkode IN ('AKTIV', 'PERMISJON', 'DELTID')
        """

        return self.db.query(query)
    # end list_studenter_alle_kull

    def list_studenter_kull(self, studieprogramkode, terminkode, arstall):
        """Hent alle studentene som er oppført på et gitt kull."""

        query = """
        SELECT DISTINCT
            fodselsdato, personnr
        FROM
            fs.studieprogramstudent
        WHERE
            studentstatkode IN ('AKTIV', 'PERMISJON', 'DELTID') AND
            NVL(dato_studierett_gyldig_til,SYSDATE)>= SYSDATE AND
            studieprogramkode = :studieprogramkode AND
            terminkode_kull = :terminkode_kull AND
            arstall_kull = :arstall_kull
        """

        return self.db.query(query, {"studieprogramkode": studieprogramkode,
                                     "terminkode_kull": terminkode,
                                     "arstall_kull": arstall})

    def list_studenter_alle_kull(self):
        """Hent alle studenter fordelt på kull.

        Dette er noe annet enn alle studenter fordelt på kullklasser. En
        student kan gjerne være meldt opp i et kull, uten å være tilordnet en
        kullklasse (hos hiof er mesteparten av kullstudentene ikke med i en
        kullklasse).
        """

        query = """
        SELECT DISTINCT
            sps.fodselsdato, sps.personnr,
            sps.studieprogramkode, sps.terminkode_kull as terminkode,
            sps.arstall_kull as arstall
        FROM
            fs.studieprogramstudent sps,
            fs.kull k
        WHERE
            /*
             * vi vil ha studenter knyttet til aktive kull. resten er
             * uinteressant.
             */
            sps.studieprogramkode = k.studieprogramkode AND
            sps.terminkode_kull = k.terminkode AND
            sps.arstall_kull = k.arstall AND
            k.status_aktiv = 'J' AND
            sps.studentstatkode IN ('AKTIV', 'PERMISJON', 'DELTID')
        """

        return self.db.query(query)
    # end list_studenter_alle_kull


@fsobject('undervisning', '>=7.8')
class HiOfUndervisning78(HiOfUndervisning, access_FS.Undervisning78):
    pass


@fsobject('studieinfo')
class HiOfStudieInfo(access_FS.StudieInfo):

    def list_studieprogrammer(self):  # GetStudieproginf
        """For hvert definerte studieprogram henter vi
        informasjon om utd_plan og eier samt studieprogkode. Vi burde
        her ha en sjekk på om studieprogrammet er utgått, men datagrunnalget
        er for svakt. ( WHERE status_utgatt = 'N')"""
        qry = """
        SELECT studieprogramkode, status_utdplan,
               institusjonsnr_studieansv, faknr_studieansv,
               instituttnr_studieansv, gruppenr_studieansv,
               studienivakode, status_utgatt, studieprognavn,
               status_eksport_lms
        FROM fs.studieprogram"""

        return self.db.query(qry)
    # end list_studieprogrammer


@fsobject('FS')
class FS(access_FS.FS):

    def __init__(self, db=None, user=None, database=None):
        super(FS, self).__init__(db=db, user=user, database=database)

        t = time.localtime()[0:3]
        self.year = t[0]
        self.mndnr = t[1]
        self.dday = t[2]

        # Override with HiOf-spesific classes
        self.student = self._component('student')(self.db)
        self.undervisning = self._component('undervisning')(self.db)
        self.info = self._component('studieinfo')(self.db)

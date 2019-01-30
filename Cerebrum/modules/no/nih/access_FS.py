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
class NIHStudent(access_FS.Student):
    def list_aktiv(self):
        """ Hent opplysninger om studenter definert som aktive
        ved NIH. En aktiv student er en student som har et gyldig
        opptak til et studieprogram der studentstatuskode er 'AKTIV'
        eller 'PERMISJON' og sluttdatoen er enten i fremtiden eller
        ikke satt."""
        qry = """
        SELECT DISTINCT
          s.fodselsdato, s.personnr, p.dato_fodt, p.etternavn, p.fornavn,
          s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
          s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
          p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
          p.adresseland_hjemsted,
          p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
          sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
          sps.arstall_kull, p.kjonn, p.status_dod,
          nvl(trim(leading '0' from
               trim(leading '+' from p.telefonlandnr_mobil)), '47')
          telefonlandnr_mobil,
          p.telefonretnnr_mobil,
          p.telefonnr_mobil,
          s.studentnr_tildelt
        FROM fs.studieprogramstudent sps, fs.person p,
             fs.student s
        WHERE p.fodselsdato = sps.fodselsdato AND
          p.personnr = sps.personnr AND
          p.fodselsdato = s.fodselsdato AND
          p.personnr = s.personnr AND
          %s AND
          sps.status_privatist = 'N' AND
          sps.studentstatkode IN ('AKTIV', 'PERMISJON') AND
          NVL(sps.dato_studierett_gyldig_til,SYSDATE)>= SYSDATE
          """ % (self._is_alive())
        return self.db.query(qry)

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
class NIHStudent78(NIHStudent, access_FS.Student78):

    def list_aktiv(self):
        """ Hent opplysninger om studenter definert som aktive
        ved NIH. En aktiv student er en student som har et gyldig
        opptak til et studieprogram der studentstatuskode er 'AKTIV'
        eller 'PERMISJON' og sluttdatoen er enten i fremtiden eller
        ikke satt."""
        qry = """
        SELECT DISTINCT
          s.fodselsdato, s.personnr, p.dato_fodt, p.etternavn, p.fornavn,
          s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
          s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
          p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
          p.adresseland_hjemsted,
          p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
          sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
          sps.arstall_kull, p.kjonn, p.status_dod,
          pt.telefonlandnr telefonlandnr_mobil,
          pt.telefonnr telefonnr_mobil,
          s.studentnr_tildelt
        FROM fs.studieprogramstudent sps,
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
          sps.status_privatist = 'N' AND
          sps.studentstatkode IN ('AKTIV', 'PERMISJON') AND
          NVL(sps.dato_studierett_gyldig_til,SYSDATE)>= SYSDATE
          """ % (self._is_alive())
        return self.db.query(qry)


@fsobject('undervisning', '<7.8')
class NIHUndervisning(access_FS.Undervisning):
    # TBD: avskaffe UiO-spesifikke søk for list_undervisningsenheter
    # og list_studenter_underv_enhet.
    # Prøve å lage generell list_studenter_kull.
    # Prøve å fjerne behov for override-metoder her

    def list_undervisningenheter(self, sem="current"):
        """Metoden som henter data om undervisningsenheter
        i nåverende (current) eller neste (next) semester. Default
        vil være nåværende semester. For hver undervisningsenhet
        henter vi institusjonsnr, emnekode, versjonskode, terminkode + årstall,
        terminnr samt hvorvidt enheten skal eksporteres til LMS."""
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
        params = {}
        params['spring'] = 'VÅR'
        params['autumn'] = 'HØST'
        return self.db.query(qry, params)

    def list_aktiviteter(self, start_aar=time.localtime()[0],
                         start_semester=None):
        """Henter info om undervisningsaktiviteter for inneværende
        semester. For hver undervisningsaktivitet henter vi
        institusjonsnr, emnekode, versjonskode, terminkode + årstall,
        terminnr, aktivitetskode, underpartiløpenummer, disiplinkode,
        kode for undervisningsform, aktivitetsnavn samt hvorvidt
        enheten skal eksporteres til LMS."""
        if start_semester is None:
            start_semester = self.semester
        return self.db.query("""
        SELECT
          ua.institusjonsnr, ua.emnekode, ua.versjonskode,
          ua.terminkode, ua.arstall, ua.terminnr, ua.aktivitetkode,
          ua.undpartilopenr, ua.disiplinkode, ua.undformkode,
          ua.aktivitetsnavn, ua.status_eksport_lms
        FROM
          fs.undaktivitet ua,
          fs.arstermin t
        WHERE
          ua.undpartilopenr IS NOT NULL AND
          ua.disiplinkode IS NOT NULL AND
          ua.undformkode IS NOT NULL AND
          ua.terminkode IN (:spring, :autumn) AND
          ua.terminkode = t.terminkode AND
          ((ua.arstall = :aar AND
            EXISTS (SELECT 'x' FROM fs.arstermin tt
                    WHERE tt.terminkode = :semester AND
                          t.sorteringsnokkel >= tt.sorteringsnokkel)) OR
           ua.arstall > :aar)""",
                             {'aar': start_aar,
                              'semester': start_semester,
                              'autumn': 'HØST',
                              'spring': 'VÅR'})

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
            studentstatkode IN ('AKTIV', 'PERMISJON') AND
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
class NIHUndervisning78(NIHUndervisning, access_FS.Undervisning78):
    pass


@fsobject('studieinfo')
class NIHStudieInfo(access_FS.StudieInfo):

    def list_emner(self):
        """Henter informasjon om emner."""
        qry = """
        SELECT e.emnekode, e.versjonskode, e.institusjonsnr,
               e.faknr_reglement, e.instituttnr_reglement,
               e.gruppenr_reglement, e.studienivakode,
               e.emnenavn_bokmal
        FROM fs.emne e
        WHERE e.institusjonsnr = %s AND
              NVL(e.arstall_eks_siste, %s) >= %s - 1""" % (self.institusjonsnr,
                                                           self.year, self.year)
        return self.db.query(qry)


@fsobject('FS')
class FS(access_FS.FS):

    def __init__(self, db=None, user=None, database=None):
        super(FS, self).__init__(db=db, user=user, database=database)

        t = time.localtime()[0:3]
        self.year = t[0]
        self.mndnr = t[1]
        self.dday = t[2]

        # Override with nih-spesific classes
        self.student = self._component('student')(self.db)
        self.undervisning = self._component('undervisning')(self.db)
        self.info = self._component('studieinfo')(self.db)

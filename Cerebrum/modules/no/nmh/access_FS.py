#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2002-2019 University of Oslo, Norway
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
class NMHStudent(access_FS.Student):

    def list_aktiv(self):
        """ Hent opplysninger om studenter definert som aktive ved NMH.

        En aktiv student er en student som har et gyldig opptak til et
        studieprogram der sluttdatoen er enten i fremtiden eller ikke satt.
        Studentstatuskode kan vere av forskjellige typer, NMH ønsker også at
        studenter som har sluttet på et program fremdeles skal ha tilgang til
        sluttdatoen er passert. Som rutine i FS skal alltid sluttdatoen
        oppdateres når status endres, så dette gjør at de kan styre når
        studenten mister IT-tilgangen, til etter at alt er oppdatert i
        studentweb.

        """
        qry = u"""
        SELECT DISTINCT
          s.fodselsdato, s.personnr, p.dato_fodt, p.etternavn, p.fornavn,
          s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
          s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
          p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
          p.adresseland_hjemsted,
          p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
          sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
          sps.arstall_kull, p.kjonn, p.status_dod, p.telefonnr_mobil,
          s.studentnr_tildelt, p.telefonretnnr_mobil
          nvl(trim(leading '0' from
                   trim(leading '+' from p.telefonlandnr_mobil)), '47')
                telefonlandnr_mobil,
        FROM fs.studieprogramstudent sps, fs.person p,
             fs.student s
        WHERE p.fodselsdato = sps.fodselsdato AND
          p.personnr = sps.personnr AND
          p.fodselsdato = s.fodselsdato AND
          p.personnr = s.personnr AND
          %s AND
          sps.status_privatist = 'N' AND
          sps.studentstatkode IN ('AKTIV', 'PERMISJON', 'FULLFØRT',
                                  'OVERGANG', 'SLUTTET') AND
          NVL(sps.dato_studierett_gyldig_til,SYSDATE)>= SYSDATE
          """ % (self._is_alive())
        return self.db.query(qry)

    def list_eksamensmeldinger(self):  # GetAlleEksamener
        """Hent ut alle eksamensmeldinger i nÃ¥vÃ¦rende sem."""

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
class NMHStudent78(NMHStudent, access_FS.Student78):

    def list_aktiv(self):
        """ Hent opplysninger om studenter definert som aktive ved NMH.

        En aktiv student er en student som har et gyldig opptak til et
        studieprogram der sluttdatoen er enten i fremtiden eller ikke satt.
        Studentstatuskode kan vere av forskjellige typer, NMH ønsker også at
        studenter som har sluttet på et program fremdeles skal ha tilgang til
        sluttdatoen er passert. Som rutine i FS skal alltid sluttdatoen
        oppdateres når status endres, så dette gjør at de kan styre når
        studenten mister IT-tilgangen, til etter at alt er oppdatert i
        studentweb.

        """
        qry = u"""
        SELECT DISTINCT
          s.fodselsdato, s.personnr, p.dato_fodt, p.etternavn, p.fornavn,
          s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
          s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
          p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
          p.adresseland_hjemsted, 
          p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
          sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
          sps.arstall_kull, p.kjonn, p.status_dod,
          s.studentnr_tildelt,
          '' telefonretnnr_mobil,
          pt.telefonnr telefonnr_mobil,
          pt.telefonlandnr telefonlandnr_mobil
        FROM fs.studieprogramstudent sps, fs.student s,
             fs.person p LEFT JOIN fs.persontelefon pt ON
             pt.fodselsdato = p.fodselsdato AND
             pt.personnr = p.personnr AND
             pt.telefonnrtypekode = 'MOBIL'
        WHERE p.fodselsdato = sps.fodselsdato AND
          p.personnr = sps.personnr AND
          p.fodselsdato = s.fodselsdato AND
          p.personnr = s.personnr AND
          %s AND
          sps.status_privatist = 'N' AND
          sps.studentstatkode IN ('AKTIV', 'PERMISJON', 'FULLFØRT',
                                  'OVERGANG', 'SLUTTET') AND
          NVL(sps.dato_studierett_gyldig_til,SYSDATE)>= SYSDATE
          """ % (self._is_alive())
        return self.db.query(qry)


@fsobject('undervisning', '<7.8')
class NMHUndervisning(access_FS.Undervisning):
    # TBD: avskaffe UiO-spesifikke søk for list_undervisningsenheter
    # og list_studenter_underv_enhet.
    # Prøve å lage generell list_studenter_kull.
    # Prøve å fjerne behov for override-metoder her

    def list_undervisningenheter(self, sem=None):
        """Henter undervisningsenheter i nåverende (current) og/eller neste
        (next) semester. Default er både nåværende og neste semeter, så en får
        med enhetene til undervisningsaktiviteter som går over to semester.

        For hver undervisningsenhet henter vi institusjonsnr, emnekode,
        versjonskode, terminkode + årstall, terminnr samt hvorvidt enheten skal
        eksporteres til LMS."""

        qry = """
        SELECT DISTINCT
          r.institusjonsnr, r.emnekode, r.versjonskode, e.emnenavnfork,
          e.emnenavn_bokmal, e.faknr_kontroll, e.instituttnr_kontroll,
          e.gruppenr_kontroll, r.terminnr, r.terminkode, r.arstall,
          r.status_eksport_lms
        FROM
          fs.emne e, fs.undervisningsenhet r
        WHERE
          r.emnekode = e.emnekode AND
          r.versjonskode = e.versjonskode AND """
        if (sem == "current"):
            qry += """%s""" % self._get_termin_aar(only_current=1)
        elif (sem == 'next'):
            qry += """%s""" % self._get_next_termin_aar()
        else:
            qry += """(%s OR %s)""" % (self._get_termin_aar(only_current=1),
                                       self._get_next_termin_aar())
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
        return self.db.query(u"""
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

    def list_fagperson_semester(self):
        """Hent ut data om fagpersoner. NMH har et tilleggsbehov for å hente ut
        fagfelt (fagnavn_norsk) for fagpersonene.

        """
        # Note: Not all persons are registered, so we
        # run a left outer join. In addition, oracle does not allow outer joins
        # if you select from more than one table, which is why we need to
        # explicitly do a JOIN with the regular table fs.fagperson:
        qry = """
        SELECT DISTINCT
              fp.fodselsdato, fp.personnr, p.dato_fodt, p.etternavn, p.fornavn,
              fp.adrlin1_arbeide, fp.adrlin2_arbeide, fp.postnr_arbeide,
              fp.adrlin3_arbeide, fp.adresseland_arbeide,
              fp.telefonnr_arbeide, fp.telefonnr_fax_arb,
              p.adrlin1_hjemsted, p.adrlin2_hjemsted, p.postnr_hjemsted,
              p.adrlin3_hjemsted, p.adresseland_hjemsted,
              p.telefonnr_hjemsted, fp.stillingstittel_engelsk,
              fp.institusjonsnr_ansatt AS institusjonsnr,
              fp.faknr_ansatt AS faknr,
              fp.instituttnr_ansatt AS instituttnr,
              fp.gruppenr_ansatt AS gruppenr,
              fp.status_aktiv, p.status_reserv_lms AS status_publiseres,
              f.fagnavn_norsk AS fagfelt,
              p.kjonn, p.status_dod
        FROM fs.person p
             JOIN fs.fagperson fp
                ON (p.fodselsdato=fp.fodselsdato AND p.personnr=fp.personnr)
             LEFT JOIN fs.fagpersoninstrument fpi
                ON (p.fodselsdato=fpi.fodselsdato AND p.personnr=fpi.personnr)
             LEFT JOIN fs.instrument i
                ON (fpi.instrumentkode=i.instrumentkode)
             LEFT JOIN fs.fagpersonfag fpf
                ON (p.fodselsdato=fpf.fodselsdato AND p.personnr=fpf.personnr)
             LEFT JOIN fs.fag f
                ON (fpf.fagkode=f.fagkode)
        WHERE fp.status_aktiv = 'J' AND
              fp.institusjonsnr_ansatt IS NOT NULL AND
              fp.faknr_ansatt IS NOT NULL AND
              fp.instituttnr_ansatt IS NOT NULL AND
              fp.gruppenr_ansatt IS NOT NULL
        """
        return self.db.query(qry)


@fsobject('undervisning', '>=7.8')
class NMHUndervisning78(NMHUndervisning, access_FS.Undervisning78):
    def list_fagperson_semester(self):
        """Hent ut data om fagpersoner. NMH har et tilleggsbehov for å hente ut
        fagfelt (fagnavn_norsk) for fagpersonene.

        """
        # Note: Not all persons are registered, so we
        # run a left outer join. In addition, oracle does not allow outer joins
        # if you select from more than one table, which is why we need to
        # explicitly do a JOIN with the regular table fs.fagperson:
        qry = """
        SELECT DISTINCT
              fp.fodselsdato, fp.personnr, p.dato_fodt, p.etternavn, p.fornavn,
              fp.adrlin1_arbeide, fp.adrlin2_arbeide, fp.postnr_arbeide,
              fp.adrlin3_arbeide, fp.adresseland_arbeide,
              ptw.telefonnr telefonnr_arbeide,
              ptf.telefonnr telefonnr_fax_arb,
              p.adrlin1_hjemsted, p.adrlin2_hjemsted, p.postnr_hjemsted,
              p.adrlin3_hjemsted, p.adresseland_hjemsted,
              pth.telefonnr telefonnr_hjemsted, fp.stillingstittel_engelsk,
              fp.institusjonsnr_ansatt AS institusjonsnr,
              fp.faknr_ansatt AS faknr,
              fp.instituttnr_ansatt AS instituttnr,
              fp.gruppenr_ansatt AS gruppenr,
              fp.status_aktiv, p.status_reserv_lms AS status_publiseres,
              f.fagnavn_norsk AS fagfelt,
              p.kjonn, p.status_dod
        FROM fs.person p
             JOIN fs.fagperson fp
                ON (p.fodselsdato=fp.fodselsdato AND p.personnr=fp.personnr)
             LEFT JOIN fs.fagpersoninstrument fpi
                ON (p.fodselsdato=fpi.fodselsdato AND p.personnr=fpi.personnr)
             LEFT JOIN fs.instrument i
                ON (fpi.instrumentkode=i.instrumentkode)
             LEFT JOIN fs.fagpersonfag fpf
                ON (p.fodselsdato=fpf.fodselsdato AND p.personnr=fpf.personnr)
             LEFT JOIN fs.fag f
                ON (fpf.fagkode=f.fagkode)
             LEFT JOIN fs.persontelefon ptw
                ON (ptw.fodselsdato = p.fodselsdato AND
                    ptw.personnr = p.personnr AND
                    ptw.telefonnrtypekode = 'ARB')
             LEFT JOIN fs.persontelefon ptf
                ON (ptf.fodselsdato = p.fodselsdato AND
                    ptf.personnr = p.personnr AND
                    ptf.telefonnrtypekode = 'FAKS')
             LEFT JOIN fs.persontelefon pth
                ON (pth.fodselsdato = p.fodselsdato AND
                    pth.personnr = p.personnr AND
                    pth.telefonnrtypekode = 'HJEM')
        WHERE fp.status_aktiv = 'J' AND
              fp.institusjonsnr_ansatt IS NOT NULL AND
              fp.faknr_ansatt IS NOT NULL AND
              fp.instituttnr_ansatt IS NOT NULL AND
              fp.gruppenr_ansatt IS NOT NULL
        """
        return self.db.query(qry)


@fsobject('studieinfo')
class NMHStudieInfo(access_FS.StudieInfo):

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

        # Override with nmh-spesific classes
        self.student = self._component('student')(self.db)
        self.undervisning = self._component('undervisning')(self.db)
        self.info = self._component('studieinfo')(self.db)

# -*- coding: utf-8 -*-
# Copyright 2002, 2003, 2012 University of Oslo, Norway
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
class UiOStudent(access_FS.Student):

    def list(self, **kwargs):  # GetStudent_50
        """Hent personer med opptak til et studieprogram ved
        institusjonen og som enten har vært registrert siste året
        eller opptak efter 2003-01-01.  Henter ikke de som har
        fremtidig opptak.  Disse kommer med 60 dager før dato for
        tildelt opptak.  Alle disse skal ha affiliation med status
        kode 'opptak' til stedskoden sp.faknr_studieansv +
        sp.instituttnr_studieansv + sp.gruppenr_studieansv.
        """
        return self._list_gyldigopptak(**kwargs) \
            + self._list_drgradsopptak(**kwargs) \
            + self._list_gammelopptak_semreg(**kwargs)

    def _list_gyldigopptak(self, fodselsdato=None, personnr=None):
        """Alle med gyldig opptak tildelt for 2 år eller mindre siden
        samt alle med opptak som blir gyldig om 60 dager.
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
           s.studentnr_tildelt,
           nvl(trim(leading '0' from
                   trim(leading '+' from p.telefonlandnr_mobil)), '47')
                telefonlandnr_mobil,
           p.telefonretnnr_mobil, p.telefonnr_mobil,
           sps.dato_studierett_tildelt
        FROM fs.student s, fs.person p, fs.studieprogramstudent sps,
           fs.studieprogram sp
        WHERE  p.fodselsdato=s.fodselsdato AND
           p.personnr=s.personnr AND
           p.fodselsdato=sps.fodselsdato AND
           p.personnr=sps.personnr AND
           %s
           sps.studieprogramkode=sp.studieprogramkode AND
           NVL(sps.dato_studierett_gyldig_til, SYSDATE) >= SYSDATE AND
           sps.status_privatist = 'N' AND
           sps.dato_studierett_tildelt < SYSDATE + 60 AND
           sps.dato_studierett_tildelt >= to_date('2003-01-01', 'yyyy-mm-dd')
           AND %s
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
           s.studentnr_tildelt,
           nvl(trim(leading '0' from
                   trim(leading '+' from p.telefonlandnr_mobil)), '47')
                telefonlandnr_mobil,
           p.telefonretnnr_mobil, p.telefonnr_mobil,
           sps.dato_studierett_tildelt
        FROM fs.student s, fs.person p, fs.studieprogramstudent sps,
           fs.studieprogram sp
        WHERE p.fodselsdato=s.fodselsdato AND
           p.personnr=s.personnr AND
           p.fodselsdato=sps.fodselsdato AND
           p.personnr=sps.personnr AND
           %s
           NVL(sps.dato_studierett_gyldig_til, SYSDATE) >= SYSDATE AND
           sps.status_privatist='N' AND
           sps.studieprogramkode=sp.studieprogramkode AND
           sp.studienivakode in (900,980) AND
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
           s.studentnr_tildelt,
           nvl(trim(leading '0' from
                   trim(leading '+' from p.telefonlandnr_mobil)), '47')
                telefonlandnr_mobil,
           p.telefonretnnr_mobil, p.telefonnr_mobil,
           sps.dato_studierett_tildelt
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
           NVL(sps.dato_studierett_gyldig_til, SYSDATE) >= SYSDATE AND
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
            extra = "p.fodselsdato=:fodselsdato AND p.personnr=:personnr AND"

        qry = """
        SELECT DISTINCT
           p.fodselsdato, p.personnr, sp.studieprogramkode,
           sps.studieretningkode, sps.terminkode_kull, sps.arstall_kull,
           vm.emnekode, vm.versjonskode, s.studentnr_tildelt
        FROM fs.studieprogram sp, fs.studieprogramstudent sps, fs.student s,
           fs.registerkort r, fs.vurdkombmelding vm,
           fs.emne_i_studieprogram es, fs.person p
        WHERE p.fodselsdato=r.fodselsdato AND
           p.personnr=r.personnr AND
           p.fodselsdato=s.fodselsdato AND
           p.personnr=s.personnr AND
           p.fodselsdato=sps.fodselsdato AND
           p.personnr=sps.personnr AND
           p.fodselsdato=vm.fodselsdato AND
           p.personnr=vm.personnr AND
           %s
           sp.studieprogramkode=es.studieprogramkode AND
           vm.institusjonsnr=es.institusjonsnr AND
           vm.emnekode=es.emnekode AND
           vm.versjonskode=es.versjonskode AND
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
            extra = "p.fodselsdato=:fodselsdato AND p.personnr=:personnr AND"

        qry = """
        SELECT DISTINCT
           p.fodselsdato, p.personnr, sp.studieprogramkode,
           sps.studieretningkode, sps.terminkode_kull, sps.arstall_kull,
           vm.emnekode, vm.versjonskode, s.studentnr_tildelt
        FROM fs.studieprogram sp, fs.studieprogramstudent sps, fs.student s,
           fs.registerkort r, fs.vurdkombmelding vm,
           fs.person p
        WHERE sp.studieprogramkode='ENKELTEMNE' AND
           p.fodselsdato=r.fodselsdato AND
           p.personnr=r.personnr AND
           p.fodselsdato=s.fodselsdato AND
           p.personnr=s.personnr AND
           p.fodselsdato=sps.fodselsdato AND
           p.personnr=sps.personnr AND
           p.fodselsdato=vm.fodselsdato AND
           p.personnr=vm.personnr AND
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
            extra = "p.fodselsdato=:fodselsdato AND p.personnr=:personnr AND"

        qry = """
        SELECT DISTINCT
           p.fodselsdato, p.personnr, sp.studieprogramkode,
           sps.studieretningkode, sps.terminkode_kull, sps.arstall_kull,
           NULL as emnekode, NULL as versjonskode, s.studentnr_tildelt
        FROM fs.student s, fs.studieprogramstudent sps, fs.registerkort r,
           fs.studprogstud_planbekreft spp, fs.studieprogram sp,
           fs.person p
        WHERE p.fodselsdato=sps.fodselsdato AND
           p.personnr=sps.personnr AND
           p.fodselsdato=s.fodselsdato AND
           p.personnr=s.personnr AND
           p.fodselsdato=r.fodselsdato AND
           p.personnr=r.personnr AND
           p.fodselsdato=spp.fodselsdato AND
           p.personnr=spp.personnr AND
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
            extra = "p.fodselsdato=:fodselsdato AND p.personnr=:personnr AND"

        qry = """
        SELECT DISTINCT
           p.fodselsdato, p.personnr, sps.studieprogramkode,
           sps.studieretningkode, sps.terminkode_kull, sps.arstall_kull,
           svp.emnekode, svp.versjonskode, s.studentnr_tildelt
        FROM fs.studentvurdkombprotokoll svp, fs.studieprogramstudent sps,
           fs.emne_i_studieprogram es, fs.registerkort r,
           fs.person p, fs.student s,
           fs.vurderingstid vt, fs.vurdkombenhet ve
        WHERE svp.arstall=%s AND
           p.fodselsdato=sps.fodselsdato AND
           p.personnr=sps.personnr AND
           p.fodselsdato=svp.fodselsdato AND
           p.personnr=svp.personnr AND
           p.fodselsdato=s.fodselsdato AND
           p.personnr=s.personnr AND
           p.fodselsdato=r.fodselsdato AND
           p.personnr=r.personnr AND
           %s
           svp.institusjonsnr='185' AND
           svp.emnekode=es.emnekode AND
           svp.versjonskode=es.versjonskode AND
           svp.institusjonsnr = es.institusjonsnr AND
           svp.vurdtidkode=vt.vurdtidkode AND
           svp.arstall=vt.arstall AND
           svp.vurdtidkode=ve.vurdtidkode AND
           svp.arstall=ve.arstall AND
           svp.institusjonsnr=ve.institusjonsnr AND
           svp.emnekode=ve.emnekode AND
           svp.versjonskode=ve.versjonskode AND
           svp.vurdkombkode=ve.vurdkombkode AND
           es.studieprogramkode=sps.studieprogramkode AND
           NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
           sps.status_privatist='N' AND
           r.status_reg_ok = 'J' AND
           r.status_bet_ok = 'J' AND
           NVL(r.status_ugyldig, 'N') = 'N' AND
           %s AND
           %s
        """ % (self.year, extra,
               self._get_termin_aar(only_current=1),
               self._is_alive())
        return self.db.query(qry, locals())

    def list_aktiv_emnestud(self, fodselsdato=None, personnr=None):
        """Hent informasjon om personer som anses som aktive studenter på
        grunnlag av eksisterende gyldig undervisningsmelding og gyldig
        semesterkort i inneværende semester. Merk at disse ikke nødvendigvis har
        studierett på noen studieprogrammer og at det derfor må hentes ut
        personopplysninger i tillegg til opplysninger om studieaktivitet.

        """
        extra = ""
        if fodselsdato and personnr:
            extra = "p.fodselsdato=:fodselsdato AND p.personnr=:personnr AND"

        qry = """
        SELECT p.fodselsdato, p.personnr, p.etternavn, p.fornavn,
               s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
               s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
               p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
               p.adresseland_hjemsted, p.status_reserv_nettpubl,
               p.sprakkode_malform, p.kjonn, p.status_dod,
               s.studentnr_tildelt, u.emnekode, u.versjonskode,
               u.terminkode, u.arstall,
               nvl(trim(leading '0' from
                   trim(leading '+' from p.telefonlandnr_mobil)), '47')
                   telefonlandnr_mobil,
               p.telefonretnnr_mobil, p.telefonnr_mobil
        FROM fs.person p, fs.student s, fs.registerkort r,
              fs.undervisningsmelding u
        WHERE p.fodselsdato=s.fodselsdato AND
              p.personnr=s.personnr AND
              p.fodselsdato=r.fodselsdato AND
              p.personnr=r.personnr AND
              p.fodselsdato = u.fodselsdato AND
              p.personnr = u.personnr AND
              %s AND
              r.status_reg_ok = 'J' AND
              r.status_bet_ok = 'J' AND
              NVL(r.status_ugyldig, 'N') = 'N' AND
              %s AND
              %s
              u.terminkode = r.terminkode AND
              u.arstall = r.arstall AND
              NVL(u.status_opptatt, 'N') = 'J'
              """ % (self._is_alive(), self._get_termin_aar(only_current=1),
                     extra)
        return self.db.query(qry, locals())

    # GetStudentPrivatistEmne_50
    def list_privatist_emne(self, fodselsdato=None, personnr=None):
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
            extra = "p.fodselsdato=:fodselsdato AND p.personnr=:personnr AND"

        qry = """
        SELECT p.fodselsdato, p.personnr, p.etternavn, p.fornavn,
               s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
               s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
               p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
               p.adresseland_hjemsted, p.status_reserv_nettpubl,
               p.sprakkode_malform, p.kjonn, p.status_dod, ve.emnekode,
               s.studentnr_tildelt,
               nvl(trim(leading '0' from
                    trim(leading '+' from p.telefonlandnr_mobil)), '47')
                        telefonlandnr_mobil,
               p.telefonretnnr_mobil, p.telefonnr_mobil
        FROM fs.student s, fs. person p, fs.registerkort r,
             fs.vurdkombmelding vm, fs.vurderingskombinasjon vk,
             fs.vurdkombenhet ve
        WHERE p.fodselsdato=s.fodselsdato AND
              p.personnr=s.personnr AND
              p.fodselsdato=r.fodselsdato AND
              p.personnr=r.personnr AND
              p.fodselsdato=vm.fodselsdato AND
              p.personnr=vm.personnr AND
              vk.institusjonsnr = vm.institusjonsnr AND
              vk.emnekode = vm.emnekode AND
              vk.versjonskode = vm.versjonskode AND
              vk.vurdkombkode = vm.vurdkombkode AND
              vk.vurdordningkode IS NOT NULL and
              ve.emnekode = vm.emnekode AND
              ve.versjonskode = vm.versjonskode AND
              ve.vurdkombkode = vm.vurdkombkode AND
              ve.vurdtidkode = vm.vurdtidkode AND
              ve.institusjonsnr = vm.institusjonsnr AND
              ve.arstall = vm.arstall AND
              ve.vurdtidkode = vm.vurdtidkode AND
              ve.arstall >= %s AND
              ve.arstall_reell = %s AND
              %s
              %s AND
              NOT EXISTS
              (SELECT 'x' FROM fs.studieprogramstudent sps,
                               fs.emne_i_studieprogram es
               WHERE p.fodselsdato=sps.fodselsdato AND
                     p.personnr=sps.personnr AND
                     es.emnekode=vm.emnekode AND
                     es.studieprogramkode = sps.studieprogramkode AND
                     NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= SYSDATE)
              AND
              %s
        """ % (self.year, self.year, extra,
               self._get_termin_aar(only_current=1), self._is_alive())
        return self.db.query(qry, locals())

    def list_privatist(self, fodselsdato=None, personnr=None):
        # GetStudentPrivatist_50
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
               sps.arstall_kull, p.kjonn, p.status_dod, s.studentnr_tildelt,
               nvl(trim(leading '0' from
                   trim(leading '+' from p.telefonlandnr_mobil)), '47')
                        telefonlandnr_mobil,
               p.telefonretnnr_mobil, p.telefonnr_mobil
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
               sps.arstall_kull, p.kjonn, p.status_dod, s.studentnr_tildelt,
               nvl(trim(leading '0' from
                   trim(leading '+' from p.telefonlandnr_mobil)), '47')
                        telefonlandnr_mobil,
               p.telefonretnnr_mobil, p.telefonnr_mobil
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

    # New queries
    def list_new_students(self, last_updated=None):
        extra = ""
        if last_updated:
            extra = """
            AND
            (NVL(s.dato_endring, TO_DATE('1970', 'YYYY')) >= :last_updated OR
            NVL(p.dato_sist_endret, TO_DATE('1970', 'YYYY')) >= :last_updated)
            """
        qry = """
        SELECT DISTINCT
            s.studentnr_tildelt
        FROM
            fs.student s, fs.person p
        WHERE
            s.fodselsdato = p.fodselsdato AND
            s.personnr = p.personnr AND
            NVL(s.dato_opprettet, TO_DATE('1970', 'YYYY')) >= (SYSDATE - 180)
            AND NVL(p.status_dod, 'N') = 'N'
            %s
        """ % extra
        return self.db.query(qry, {'last_updated': last_updated})

    def list_gyldige_regkort(self, last_updated=None):
        extra = ""
        if last_updated:
            extra = """
            AND
            (NVL(p.dato_sist_endret, TO_DATE('1970', 'YYYY')) >= :last_updated
            OR NVL(s.dato_endring, TO_DATE('1970', 'YYYY')) >= :last_updated
            OR NVL(r.dato_endring, TO_DATE('1970', 'YYYY')) >= :last_updated)
            """
        qry = """
        SELECT DISTINCT
            s.studentnr_tildelt, r.arstall, r.terminkode
        FROM
            fs.person p, fs.student s, fs.registerkort r
        WHERE
            p.fodselsdato   = s.fodselsdato AND
            p.personnr      = s.personnr AND
            p.fodselsdato   = r.fodselsdato AND
            p.personnr      = r.personnr AND
            r.status_reg_ok = 'J' AND
            r.status_bet_ok = 'J' AND
            NVL(r.status_ugyldig, 'N') = 'N' AND
            r.arstall >= (TO_CHAR(SYSDATE, 'YYYY') - 1) AND
            NVL(p.status_dod, 'N') = 'N'
            %s
        """ % extra
        return self.db.query(qry, {'last_updated': last_updated})

    def list_studieopptak(self, last_updated=None):
        extra = ""
        if last_updated:
            extra = """
            AND
            (NVL(sps.dato_endring, TO_DATE('1970', 'YYYY')) >= :last_updated
            OR NVL(r.dato_endring, TO_DATE('1970', 'YYYY')) >= :last_updated
            OR NVL(p.dato_sist_endret, TO_DATE('1970', 'YYYY')) >= :last_updated
            OR NVL(sp.dato_sist_endret, TO_DATE('1970', 'YYYY'))>= :last_updated
            OR NVL(s.dato_endring, TO_DATE('1970', 'YYYY')) >= :last_updated)
            """
        qry = """
        SELECT DISTINCT
            s.studentnr_tildelt
            /*
            , sp.faknr_studieansv, sp.instituttnr_studieansv,
            sp.gruppenr_studieansv, sps.dato_studierett_gyldig_til
            */
        FROM
            fs.student s, fs.person p, fs.registerkort r,
            fs.studieprogramstudent sps, fs.studieprogram sp
        WHERE
            p.fodselsdato   = s.fodselsdato AND
            p.personnr      = s.personnr AND
            p.fodselsdato   = sps.fodselsdato AND
            p.personnr      = sps.personnr AND
            p.fodselsdato   = r.fodselsdato AND
            p.personnr      = r.personnr AND
            sps.studieprogramkode = sp.studieprogramkode AND
            NVL(sps.dato_studierett_gyldig_til, SYSDATE) >= SYSDATE AND
            r.status_reg_ok = 'J' AND
            r.status_bet_ok = 'J' AND
            r.arstall >= (TO_CHAR(SYSDATE, 'YYYY') - 1) AND
            /* TODO: må vi sjekke terminen også? */
            NVL(r.status_ugyldig, 'N') = 'N' AND
            NVL(p.status_dod, 'N') = 'N'
            %s
        """ % extra
        return self.db.query(qry, {'last_updated': last_updated})

    def list_tidligere_students(self, last_updated=None):
        raise NotImplementedError("Design SQL-query  before calling this.")
        # return self.db.query(qry, {'last_updated': last_updated})

    def list_drgrad_students(self, last_updated=None):
        extra = ""
        if last_updated:
            extra = """
            AND
            (NVL(p.dato_sist_endret, TO_DATE('1970', 'YYYY')) >= :last_updated
            OR NVL(s.dato_endring, TO_DATE('1970', 'YYYY')) >= :last_updated OR
            NVL(sps.dato_endring, TO_DATE('1970', 'YYYY')) >= :last_updated OR
            NVL(sp.dato_sist_endret, TO_DATE('1970', 'YYYY')) >= :last_updated)
            """
        qry = """
        SELECT DISTINCT
            s.studentnr_tildelt
            /*
            , sp.faknr_studieansv, sp.instituttnr_studieansv,
            sp.gruppenr_studieansv, sps.dato_studierett_gyldig_til
            */
        FROM
            fs.person p, fs.student s,
            fs.studieprogramstudent sps, fs.studieprogram sp
        WHERE
            p.fodselsdato = s.fodselsdato AND
            p.personnr    = s.personnr AND
            p.fodselsdato = sps.fodselsdato AND
            p.personnr    = sps.personnr AND
            sps.studieprogramkode = sp.studieprogramkode AND
            NVL(sps.dato_studierett_gyldig_til, SYSDATE) >= (SYSDATE - 365) AND
            /* TODO: er det poeng i å ta med studieprogram eit år tilbake? */
            sp.studienivakode in (900, 980) AND
            NVL(p.status_dod, 'N') = 'N'
            %s
        """ % extra
        return self.db.query(qry, {'last_updated': last_updated})

    def list_all_students_information(self, last_updated=None):
        extra = ""
        if last_updated:
            extra = """
            AND
            (NVL(p.dato_siste_endring, TO_DATE('1970', 'YYYY')) >= :last_updated
            OR NVL(s.dato_endring, TO_DATE('1970', 'YYYY')) >= :last_updated OR
            NVL(s.dato_endret_semadr, TO_DATE('1970', 'YYYY')) >= :last_updated)
            """
        qry = """
        SELECT DISTINCT
            s.studentnr_tildelt
            /*
            , s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
            s.adrlin1_semadr, s.adrlin2_semadr, s.adrlin3_semadr,
            s.postnr_semadr, s.adresseland_semadr,
            p.status_reserv_nettpubl, p.sprakkode_malform, p.kjonn,
            nvl(trim(leading '0' from
                trim(leading '+' from p.telefonlandnr_mobil)), '47')
                    telefonlandnr_mobil,
            p.status_dod, p.telefonretnnr_mobil,
            p.telefonnr_mobil
            */
        FROM
            fs.student s, fs.person p
        WHERE
            s.fodselsdato = p.fodselsdato AND
            s.personnr = p.personnr
            %s
        """ % extra
        return self.db.query(qry, {'last_updated': last_updated})

    def list_fodselsnr_changes(self, last_updated=None):
        """
        Import changes in fodselsnummere. Check how long back we want
        to look. Hardcoded to 30 days, so last_updated param is not used at all.
        """
        raise NotImplementedError("Implementation is not yet available.")
        # extra = ""
        # if last_updated:
        #    extra = """
        #    WHERE
        #        dato_foretatt > SYSDATE - 30
        #    """
        # qry = """
        # SELECT DISTINCT
        #    fodselsdato_naverende, personnr_naverende,
        #    fodselsdato_tidligere, personnr_tidligere,
        #    TO_CHAR(dato_foretatt, 'YYYY-MM-DD HH24:MI:SS') AS dato_foretatt
        # FROM
        #    fs.fnr_endring
        # %s
        # ORDER BY
        #    dato_foretatt
        # """ %extra
        # return self.db.query(qry, {'last_updated': last_updated})


@fsobject('student', '>=7.8')
class UiOStudent78(UiOStudent, access_FS.Student78):

    def list(self, **kwargs):  # GetStudent_50
        """Hent personer med opptak til et studieprogram ved
        institusjonen og som enten har vært registrert siste året
        eller opptak efter 2003-01-01.  Henter ikke de som har
        fremtidig opptak.  Disse kommer med 60 dager før dato for
        tildelt opptak.  Alle disse skal ha affiliation med status
        kode 'opptak' til stedskoden sp.faknr_studieansv +
        sp.instituttnr_studieansv + sp.gruppenr_studieansv.
        """
        return self._list_gyldigopptak(**kwargs) \
            + self._list_drgradsopptak(**kwargs) \
            + self._list_gammelopptak_semreg(**kwargs)

    def _list_gyldigopptak(self, fodselsdato=None, personnr=None):
        """Alle med gyldig opptak tildelt for 2 år eller mindre siden
        samt alle med opptak som blir gyldig om 60 dager.
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
           s.studentnr_tildelt,
           pt.telefonlandnr telefonlandnr_mobil,
           '' telefonretnnr_mobil,
           pt.telefonnr telefonnr_mobil,
           sps.dato_studierett_tildelt
        FROM fs.student s, fs.studieprogram sp, fs.studieprogramstudent sps,
           fs.person p LEFT JOIN fs.persontelefon pt ON
           pt.fodselsdato = p.fodselsdato AND
           pt.personnr = p.personnr AND
           pt.telefonnrtypekode = 'MOBIL'
        WHERE  p.fodselsdato=s.fodselsdato AND
           p.personnr=s.personnr AND
           p.fodselsdato=sps.fodselsdato AND
           p.personnr=sps.personnr AND
           %s
           sps.studieprogramkode=sp.studieprogramkode AND
           NVL(sps.dato_studierett_gyldig_til, SYSDATE) >= SYSDATE AND
           sps.status_privatist = 'N' AND
           sps.dato_studierett_tildelt < SYSDATE + 60 AND
           sps.dato_studierett_tildelt >= to_date('2003-01-01', 'yyyy-mm-dd')
           AND %s
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
           s.studentnr_tildelt,
           pt.telefonlandnr telefonlandnr_mobil, '' telefonretnnr_mobil,
           pt.telefonnr telefonnr_mobil,
           sps.dato_studierett_tildelt
        FROM fs.student s, fs.studieprogram sp, fs.studieprogramstudent sps,
           fs.person p LEFT JOIN fs.persontelefon pt ON
           pt.fodselsdato = p.fodselsdato AND
           pt.personnr = p.personnr AND
           pt.telefonnrtypekode = 'MOBIL'
        WHERE p.fodselsdato=s.fodselsdato AND
           p.personnr=s.personnr AND
           p.fodselsdato=sps.fodselsdato AND
           p.personnr=sps.personnr AND
           %s
           NVL(sps.dato_studierett_gyldig_til, SYSDATE) >= SYSDATE AND
           sps.status_privatist='N' AND
           sps.studieprogramkode=sp.studieprogramkode AND
           sp.studienivakode in (900,980) AND
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
           s.studentnr_tildelt,
           pt.telefonlandnr telefonlandnr_mobil, '' telefonretnnr_mobil,
           pt.telefonnr telefonnr_mobil,
           sps.dato_studierett_tildelt
        FROM fs.student s, fs.studieprogram sp, fs.studieprogramstudent sps,
           fs.registerkort r, fs.person p
           LEFT JOIN fs.persontelefon pt ON
           pt.fodselsdato = p.fodselsdato AND
           pt.personnr = p.personnr AND
           pt.telefonnrtypekode = 'MOBIL'
        WHERE  p.fodselsdato=s.fodselsdato AND
           p.personnr=s.personnr AND
           p.fodselsdato=sps.fodselsdato AND
           p.personnr=sps.personnr AND
           p.fodselsdato=r.fodselsdato AND
           p.personnr=r.personnr AND
           %s
           sps.studieprogramkode=sp.studieprogramkode AND
           NVL(sps.dato_studierett_gyldig_til, SYSDATE) >= SYSDATE AND
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
            extra = "p.fodselsdato=:fodselsdato AND p.personnr=:personnr AND"

        qry = """
        SELECT DISTINCT
           p.fodselsdato, p.personnr, sp.studieprogramkode,
           sps.studieretningkode, sps.terminkode_kull, sps.arstall_kull,
           vm.emnekode, vm.versjonskode, s.studentnr_tildelt
        FROM fs.studieprogram sp, fs.studieprogramstudent sps, fs.student s,
           fs.registerkort r, fs.vurdkombmelding vm,
           fs.emne_i_studieprogram es, fs.person p
        WHERE p.fodselsdato=r.fodselsdato AND
           p.personnr=r.personnr AND
           p.fodselsdato=s.fodselsdato AND
           p.personnr=s.personnr AND
           p.fodselsdato=sps.fodselsdato AND
           p.personnr=sps.personnr AND
           p.fodselsdato=vm.fodselsdato AND
           p.personnr=vm.personnr AND
           %s
           sp.studieprogramkode=es.studieprogramkode AND
           vm.institusjonsnr=es.institusjonsnr AND
           vm.emnekode=es.emnekode AND
           vm.versjonskode=es.versjonskode AND
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
            extra = "p.fodselsdato=:fodselsdato AND p.personnr=:personnr AND"

        qry = """
        SELECT DISTINCT
           p.fodselsdato, p.personnr, sp.studieprogramkode,
           sps.studieretningkode, sps.terminkode_kull, sps.arstall_kull,
           vm.emnekode, vm.versjonskode, s.studentnr_tildelt
        FROM fs.studieprogram sp, fs.studieprogramstudent sps, fs.student s,
           fs.registerkort r, fs.vurdkombmelding vm,
           fs.person p
        WHERE sp.studieprogramkode='ENKELTEMNE' AND
           p.fodselsdato=r.fodselsdato AND
           p.personnr=r.personnr AND
           p.fodselsdato=s.fodselsdato AND
           p.personnr=s.personnr AND
           p.fodselsdato=sps.fodselsdato AND
           p.personnr=sps.personnr AND
           p.fodselsdato=vm.fodselsdato AND
           p.personnr=vm.personnr AND
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
            extra = "p.fodselsdato=:fodselsdato AND p.personnr=:personnr AND"

        qry = """
        SELECT DISTINCT
           p.fodselsdato, p.personnr, sp.studieprogramkode,
           sps.studieretningkode, sps.terminkode_kull, sps.arstall_kull,
           NULL as emnekode, NULL as versjonskode, s.studentnr_tildelt
        FROM fs.student s, fs.studieprogramstudent sps, fs.registerkort r,
           fs.studprogstud_planbekreft spp, fs.studieprogram sp,
           fs.person p
        WHERE p.fodselsdato=sps.fodselsdato AND
           p.personnr=sps.personnr AND
           p.fodselsdato=s.fodselsdato AND
           p.personnr=s.personnr AND
           p.fodselsdato=r.fodselsdato AND
           p.personnr=r.personnr AND
           p.fodselsdato=spp.fodselsdato AND
           p.personnr=spp.personnr AND
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
            extra = "p.fodselsdato=:fodselsdato AND p.personnr=:personnr AND"

        qry = """
        SELECT DISTINCT
           p.fodselsdato, p.personnr, sps.studieprogramkode,
           sps.studieretningkode, sps.terminkode_kull, sps.arstall_kull,
           svp.emnekode, svp.versjonskode, s.studentnr_tildelt
        FROM fs.studentvurdkombprotokoll svp, fs.studieprogramstudent sps,
           fs.emne_i_studieprogram es, fs.registerkort r,
           fs.person p, fs.student s,
           fs.vurderingstid vt, fs.vurdkombenhet ve
        WHERE svp.arstall=%s AND
           p.fodselsdato=sps.fodselsdato AND
           p.personnr=sps.personnr AND
           p.fodselsdato=svp.fodselsdato AND
           p.personnr=svp.personnr AND
           p.fodselsdato=s.fodselsdato AND
           p.personnr=s.personnr AND
           p.fodselsdato=r.fodselsdato AND
           p.personnr=r.personnr AND
           %s
           svp.institusjonsnr='185' AND
           svp.emnekode=es.emnekode AND
           svp.versjonskode=es.versjonskode AND
           svp.institusjonsnr = es.institusjonsnr AND
           svp.vurdtidkode=vt.vurdtidkode AND
           svp.arstall=vt.arstall AND
           svp.vurdtidkode=ve.vurdtidkode AND
           svp.arstall=ve.arstall AND
           svp.institusjonsnr=ve.institusjonsnr AND
           svp.emnekode=ve.emnekode AND
           svp.versjonskode=ve.versjonskode AND
           svp.vurdkombkode=ve.vurdkombkode AND
           es.studieprogramkode=sps.studieprogramkode AND
           NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
           sps.status_privatist='N' AND
           r.status_reg_ok = 'J' AND
           r.status_bet_ok = 'J' AND
           NVL(r.status_ugyldig, 'N') = 'N' AND
           %s AND
           %s
        """ % (self.year, extra,
               self._get_termin_aar(only_current=1),
               self._is_alive())
        return self.db.query(qry, locals())

    def list_aktiv_emnestud(self, fodselsdato=None, personnr=None):
        """Hent informasjon om personer som anses som aktive studenter på
        grunnlag av eksisterende gyldig undervisningsmelding og gyldig
        semesterkort i inneværende semester. Merk at disse ikke nødvendigvis har
        studierett på noen studieprogrammer og at det derfor må hentes ut
        personopplysninger i tillegg til opplysninger om studieaktivitet.

        """
        extra = ""
        if fodselsdato and personnr:
            extra = "p.fodselsdato=:fodselsdato AND p.personnr=:personnr AND"

        qry = """
        SELECT p.fodselsdato, p.personnr, p.etternavn, p.fornavn,
               s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
               s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
               p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
               p.adresseland_hjemsted, p.status_reserv_nettpubl,
               p.sprakkode_malform, p.kjonn, p.status_dod,
               s.studentnr_tildelt, u.emnekode, u.versjonskode,
               u.terminkode, u.arstall,
               pt.telefonlandnr telefonlandnr_mobil, '' telefonretnnr_mobil,
               pt.telefonnr telefonnr_mobil
        FROM fs.student s, fs.registerkort r,
              fs.undervisningsmelding u, fs.person p
              LEFT JOIN fs.persontelefon pt ON
              pt.fodselsdato = p.fodselsdato AND
              pt.personnr = p.personnr AND
              pt.telefonnrtypekode = 'MOBIL'
        WHERE p.fodselsdato=s.fodselsdato AND
              p.personnr=s.personnr AND
              p.fodselsdato=r.fodselsdato AND
              p.personnr=r.personnr AND
              p.fodselsdato = u.fodselsdato AND
              p.personnr = u.personnr AND
              %s AND
              r.status_reg_ok = 'J' AND
              r.status_bet_ok = 'J' AND
              NVL(r.status_ugyldig, 'N') = 'N' AND
              %s AND
              %s
              u.terminkode = r.terminkode AND
              u.arstall = r.arstall AND
              NVL(u.status_opptatt, 'N') = 'J'
              """ % (self._is_alive(), self._get_termin_aar(only_current=1),
                     extra)
        return self.db.query(qry, locals())

    # GetStudentPrivatistEmne_50
    def list_privatist_emne(self, fodselsdato=None, personnr=None):
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
            extra = "p.fodselsdato=:fodselsdato AND p.personnr=:personnr AND"

        qry = """
        SELECT p.fodselsdato, p.personnr, p.etternavn, p.fornavn,
               s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
               s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
               p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
               p.adresseland_hjemsted, p.status_reserv_nettpubl,
               p.sprakkode_malform, p.kjonn, p.status_dod, ve.emnekode,
               s.studentnr_tildelt,
               pt.telefonlandnr telefonlandnr_mobil, '' telefonretnnr_mobil,
               pt.telefonnr telefonnr_mobil
        FROM fs.student s, fs.registerkort r,
             fs.vurdkombmelding vm, fs.vurderingskombinasjon vk,
             fs.vurdkombenhet ve, fs. person p LEFT JOIN fs.persontelefon pt ON
             pt.fodselsdato = p.fodselsdato AND
             pt.personnr = p.personnr AND
             pt.telefonnrtypekode = 'MOBIL'
        WHERE p.fodselsdato=s.fodselsdato AND
              p.personnr=s.personnr AND
              p.fodselsdato=r.fodselsdato AND
              p.personnr=r.personnr AND
              p.fodselsdato=vm.fodselsdato AND
              p.personnr=vm.personnr AND
              vk.institusjonsnr = vm.institusjonsnr AND
              vk.emnekode = vm.emnekode AND
              vk.versjonskode = vm.versjonskode AND
              vk.vurdkombkode = vm.vurdkombkode AND
              vk.vurdordningkode IS NOT NULL and
              ve.emnekode = vm.emnekode AND
              ve.versjonskode = vm.versjonskode AND
              ve.vurdkombkode = vm.vurdkombkode AND
              ve.vurdtidkode = vm.vurdtidkode AND
              ve.institusjonsnr = vm.institusjonsnr AND
              ve.arstall = vm.arstall AND
              ve.vurdtidkode = vm.vurdtidkode AND
              ve.arstall >= %s AND
              ve.arstall_reell = %s AND
              %s
              %s AND
              NOT EXISTS
              (SELECT 'x' FROM fs.studieprogramstudent sps,
                               fs.emne_i_studieprogram es
               WHERE p.fodselsdato=sps.fodselsdato AND
                     p.personnr=sps.personnr AND
                     es.emnekode=vm.emnekode AND
                     es.studieprogramkode = sps.studieprogramkode AND
                     NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= SYSDATE)
              AND
              %s
        """ % (self.year, self.year, extra,
               self._get_termin_aar(only_current=1), self._is_alive())
        return self.db.query(qry, locals())

    def list_privatist(self, fodselsdato=None, personnr=None):
        # GetStudentPrivatist_50
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
               sps.arstall_kull, p.kjonn, p.status_dod, s.studentnr_tildelt,
               pt.telefonlandnr telefonlandnr_mobil, '' telefonretnnr_mobil,
               pt.telefonnr telefonnr_mobil
        FROM fs.student s, fs.studieprogramstudent sps, fs.person p
             LEFT JOIN fs.persontelefon pt ON
             pt.fodselsdato = p.fodselsdato AND
             pt.personnr = p.personnr AND
             pt.telefonnrtypekode = 'MOBIL'
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
               sps.arstall_kull, p.kjonn, p.status_dod, s.studentnr_tildelt,
               pt.telefonlandnr telefonlandnr_mobil, '' telefonretnnr_mobil,
               pt.telefonnr telefonnr_mobil
        FROM fs.student s, fs.studieprogramstudent sps,
             fs.registerkort r, fs.person p
             LEFT JOIN fs.persontelefon pt ON
             pt.fodselsdato = p.fodselsdato AND
             pt.personnr = p.personnr AND
             pt.telefonnrtypekode = 'MOBIL'
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

    # New queries
    def list_new_students(self, last_updated=None):
        extra = ""
        if last_updated:
            extra = """
            AND
            (NVL(s.dato_endring, TO_DATE('1970', 'YYYY')) >= :last_updated OR
            NVL(p.dato_sist_endret, TO_DATE('1970', 'YYYY')) >= :last_updated)
            """
        qry = """
        SELECT DISTINCT
            s.studentnr_tildelt
        FROM
            fs.student s, fs.person p
        WHERE
            s.fodselsdato = p.fodselsdato AND
            s.personnr = p.personnr AND
            NVL(s.dato_opprettet, TO_DATE('1970', 'YYYY')) >= (SYSDATE - 180)
            AND NVL(p.status_dod, 'N') = 'N'
            %s
        """ % extra
        return self.db.query(qry, {'last_updated': last_updated})

    def list_gyldige_regkort(self, last_updated=None):
        extra = ""
        if last_updated:
            extra = """
            AND
            (NVL(p.dato_sist_endret, TO_DATE('1970', 'YYYY')) >= :last_updated
            OR NVL(s.dato_endring, TO_DATE('1970', 'YYYY')) >= :last_updated
            OR NVL(r.dato_endring, TO_DATE('1970', 'YYYY')) >= :last_updated)
            """
        qry = """
        SELECT DISTINCT
            s.studentnr_tildelt, r.arstall, r.terminkode
        FROM
            fs.person p, fs.student s, fs.registerkort r
        WHERE
            p.fodselsdato   = s.fodselsdato AND
            p.personnr      = s.personnr AND
            p.fodselsdato   = r.fodselsdato AND
            p.personnr      = r.personnr AND
            r.status_reg_ok = 'J' AND
            r.status_bet_ok = 'J' AND
            NVL(r.status_ugyldig, 'N') = 'N' AND
            r.arstall >= (TO_CHAR(SYSDATE, 'YYYY') - 1) AND
            NVL(p.status_dod, 'N') = 'N'
            %s
        """ % extra
        return self.db.query(qry, {'last_updated': last_updated})

    def list_studieopptak(self, last_updated=None):
        extra = ""
        if last_updated:
            extra = """
            AND
            (NVL(sps.dato_endring, TO_DATE('1970', 'YYYY')) >= :last_updated
            OR NVL(r.dato_endring, TO_DATE('1970', 'YYYY')) >= :last_updated
            OR NVL(p.dato_sist_endret, TO_DATE('1970', 'YYYY')) >= :last_updated
            OR NVL(sp.dato_sist_endret, TO_DATE('1970', 'YYYY'))>= :last_updated
            OR NVL(s.dato_endring, TO_DATE('1970', 'YYYY')) >= :last_updated)
            """
        qry = """
        SELECT DISTINCT
            s.studentnr_tildelt
            /*
            , sp.faknr_studieansv, sp.instituttnr_studieansv,
            sp.gruppenr_studieansv, sps.dato_studierett_gyldig_til
            */
        FROM
            fs.student s, fs.person p, fs.registerkort r,
            fs.studieprogramstudent sps, fs.studieprogram sp
        WHERE
            p.fodselsdato   = s.fodselsdato AND
            p.personnr      = s.personnr AND
            p.fodselsdato   = sps.fodselsdato AND
            p.personnr      = sps.personnr AND
            p.fodselsdato   = r.fodselsdato AND
            p.personnr      = r.personnr AND
            sps.studieprogramkode = sp.studieprogramkode AND
            NVL(sps.dato_studierett_gyldig_til, SYSDATE) >= SYSDATE AND
            r.status_reg_ok = 'J' AND
            r.status_bet_ok = 'J' AND
            r.arstall >= (TO_CHAR(SYSDATE, 'YYYY') - 1) AND
            /* TODO: må vi sjekke terminen også? */
            NVL(r.status_ugyldig, 'N') = 'N' AND
            NVL(p.status_dod, 'N') = 'N'
            %s
        """ % extra
        return self.db.query(qry, {'last_updated': last_updated})

    def list_tidligere_students(self, last_updated=None):
        raise NotImplementedError("Design SQL-query  before calling this.")
        # return self.db.query(qry, {'last_updated': last_updated})

    def list_drgrad_students(self, last_updated=None):
        extra = ""
        if last_updated:
            extra = """
            AND
            (NVL(p.dato_sist_endret, TO_DATE('1970', 'YYYY')) >= :last_updated
            OR NVL(s.dato_endring, TO_DATE('1970', 'YYYY')) >= :last_updated OR
            NVL(sps.dato_endring, TO_DATE('1970', 'YYYY')) >= :last_updated OR
            NVL(sp.dato_sist_endret, TO_DATE('1970', 'YYYY')) >= :last_updated)
            """
        qry = """
        SELECT DISTINCT
            s.studentnr_tildelt
            /*
            , sp.faknr_studieansv, sp.instituttnr_studieansv,
            sp.gruppenr_studieansv, sps.dato_studierett_gyldig_til
            */
        FROM
            fs.person p, fs.student s,
            fs.studieprogramstudent sps, fs.studieprogram sp
        WHERE
            p.fodselsdato = s.fodselsdato AND
            p.personnr    = s.personnr AND
            p.fodselsdato = sps.fodselsdato AND
            p.personnr    = sps.personnr AND
            sps.studieprogramkode = sp.studieprogramkode AND
            NVL(sps.dato_studierett_gyldig_til, SYSDATE) >= (SYSDATE - 365) AND
            /* TODO: er det poeng i å ta med studieprogram eit år tilbake? */
            sp.studienivakode in (900, 980) AND
            NVL(p.status_dod, 'N') = 'N'
            %s
        """ % extra
        return self.db.query(qry, {'last_updated': last_updated})

    def list_all_students_information(self, last_updated=None):
        extra = ""
        if last_updated:
            extra = """
            AND
            (NVL(p.dato_siste_endring, TO_DATE('1970', 'YYYY')) >= :last_updated
            OR NVL(s.dato_endring, TO_DATE('1970', 'YYYY')) >= :last_updated OR
            NVL(s.dato_endret_semadr, TO_DATE('1970', 'YYYY')) >= :last_updated)
            """
        qry = """
        SELECT DISTINCT
            s.studentnr_tildelt
            /*
            , s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
            s.adrlin1_semadr, s.adrlin2_semadr, s.adrlin3_semadr,
            s.postnr_semadr, s.adresseland_semadr,
            p.status_reserv_nettpubl, p.sprakkode_malform, p.kjonn,
            p.status_dod, pt.telefonlandnr telefonlandnr_mobil,
            '' telefonretnnr_mobil, pt.telefonnr telefonnr_mobil
            */
        FROM
            fs.student s, fs.person p LEFT JOIN fs.persontelefon ON
            pt.fodselsdato = p.fodselsdato AND
            pt.personnr = p.personnr AND
            pt.telefonnrtypekode = 'MOBIL'
        WHERE
            s.fodselsdato = p.fodselsdato AND
            s.personnr = p.personnr
            %s
        """ % extra
        return self.db.query(qry, {'last_updated': last_updated})

    def list_fodselsnr_changes(self, last_updated=None):
        """
        Import changes in fodselsnummere. Check how long back we want
        to look. Hardcoded to 30 days, so last_updated param is not used at all.
        """
        raise NotImplementedError("Implementation is not yet available.")
        # extra = ""
        # if last_updated:
        #    extra = """
        #    WHERE
        #        dato_foretatt > SYSDATE - 30
        #    """
        # qry = """
        # SELECT DISTINCT
        #    fodselsdato_naverende, personnr_naverende,
        #    fodselsdato_tidligere, personnr_tidligere,
        #    TO_CHAR(dato_foretatt, 'YYYY-MM-DD HH24:MI:SS') AS dato_foretatt
        # FROM
        #    fs.fnr_endring
        # %s
        # ORDER BY
        #    dato_foretatt
        # """ %extra
        # return self.db.query(qry, {'last_updated': last_updated})


@fsobject('portal')
class UiOPortal(access_FS.FSObject):
    """Denne funksjonen er ikke lenger i bruk, da portal-ting ikke er i bruk
    lenger. Dersom jobben cerebrum/contrib/no/uio/generate_portal_export.py
    skal settes i produksjon igjen, må denne funksjonen oppdateres til
    gjeldende FS versjon, med vurderingsmodul.

    """
    pass


@fsobject('betaling')
class UiOBetaling(access_FS.FSObject):
    """Kopiavgift. Ny ordning fra høsten 2004."""

    def list_utskrifts_betaling(self, days_past=180):  # GetUtskriftsBetaling
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

    def list_kopiavgift_data(self,
                             kun_fritak=True,
                             semreg=False,
                             fodselsdato=None,
                             personnr=None):
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
            extra1 = ("frk.fodselsdato=:fodselsdato AND "
                      "frk.personnr=:personnr AND")
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
        r.betformkode NOT IN ('GIRO')""" % (extra_semreg2, extra2)

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
             fkd.fakturadetaljtypekode = 'KOPIAVG'""" % (extra_from,
                                                         extra_semreg1, extra1)
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


@fsobject('undervisning', '<7.8')
class UiOUndervisning(access_FS.Undervisning):

    def list_undervisningenheter(self, year=None, sem=None):
        # GetUndervEnhetAll
        if year is None:
            year = self.prev_semester_year
        if sem is None:
            sem = self.prev_semester
        return self.db.query("""
        SELECT
          ue.institusjonsnr, ue.emnekode, ue.versjonskode, ue.terminkode,
          ue.arstall, ue.terminnr, e.institusjonsnr_kontroll,
          e.faknr_kontroll, e.instituttnr_kontroll, e.gruppenr_kontroll,
          e.emnenavn_bokmal, e.emnenavnfork, ue.status_eksport_lms,
          ue.lmsrommalkode
        FROM
          fs.undervisningsenhet ue, fs.emne e, fs.arstermin t
        WHERE
          ue.institusjonsnr = e.institusjonsnr AND
          ue.emnekode       = e.emnekode AND
          ue.versjonskode   = e.versjonskode AND
          ue.terminkode IN (:spring, :autumn) AND
          ue.terminkode = t.terminkode AND
          (ue.arstall > :aar OR
           (ue.arstall = :aar2 AND
            EXISTS(SELECT 'x' FROM fs.arstermin tt
            WHERE tt.terminkode = :sem AND
                  t.sorteringsnokkel >= tt.sorteringsnokkel)))
          """, {'aar': year,
                'aar2': year,  # db-driver bug work-around
                'sem': sem,
                'autumn': 'HØST',
                'spring': 'VÅR'})

    def list_aktiviteter(self,
                         start_aar=None,
                         start_semester=None):
        if start_aar is None:
            start_aar = self.prev_semester_year
        if start_semester is None:
            start_semester = self.prev_semester

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
        query = """
        SELECT DISTINCT
            fodselsdato, personnr, studieprogramkode, terminkode_kull,
            arstall_kull
        FROM
            fs.studieprogramstudent
        WHERE
            studentstatkode IN ('AKTIV', 'PERMISJON') AND
            NVL(dato_studierett_gyldig_til,SYSDATE)>= SYSDATE AND
            /* IVR 2007-11-12: According to baardj, it makes no sense to
               register 'kull' for earlier timeframes. */
            arstall_kull >= 2002
        """

        return self.db.query(query)
    # end list_studenter_alle_kull

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
          u.fodselsdato, u.personnr, u.institusjonsnr, u.emnekode,
          u.versjonskode, u.terminkode, u.arstall, u.terminnr
        FROM
          fs.undervisningsmelding u, fs.tilbudsstatus t
        WHERE
          u.terminkode in (:spring, :autumn) AND
          u.arstall >= :aar1 AND
          u.tilbudstatkode = t.tilbudstatkode AND
          t.status_gir_tilbud = 'J'
        UNION
        SELECT DISTINCT
          vm.fodselsdato, vm.personnr,
          vm.institusjonsnr, vm.emnekode, vm.versjonskode,
          vt.terminkode_gjelder_i AS terminkode,
          vt.arstall_gjelder_i AS arstall, 1 AS terminnr
        FROM
          fs.vurdkombmelding vm, fs.vurdkombenhet ve,
          fs.vurderingstid vt
        WHERE
          ve.institusjonsnr=vm.institusjonsnr AND
          ve.emnekode=vm.emnekode AND
          ve.versjonskode=vm.versjonskode AND
          ve.vurdkombkode=vm.vurdkombkode AND
          ve.vurdtidkode=vm.vurdtidkode AND
          ve.arstall=vm.arstall AND
          ve.arstall_reell=vt.arstall AND
          ve.vurdtidkode_reell=vt.vurdtidkode AND
          vt.arstall_gjelder_i >= :aar2
        """

        result = self.db.query(
            qry,
            {"aar1": self.prev_semester_year,
             "aar2": self.prev_semester_year,
             'autumn': 'HØST',
             'spring': 'VÅR'},
            fetchall=True
        )
        # IVR 2009-03-12 FIXME: DCOracle2 returns a float when taking a union
        # of two ints. The resons for this escape me.
        for row in result:
            row["terminnr"] = int(row["terminnr"])

        return result

    def list_studenter_alle_undakt(self):
        """Hent alle studenter på alle undakt.

        NB! Det kan være mange hundretusen rader i FSPROD i
        student_pa_undervisningsparti. Det koster da en del minne.

        Change from parent: Use year of previous semester
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

        return self.db.query(qry, {"aar": self.prev_semester_year},
                             fetchall=False)


@fsobject('undervisning', '>=7.8')
class UiOUndervisning78(UiOUndervisning, access_FS.Undervisning78):
    pass


@fsobject('evu', '<7.8')
class UiOEVU(access_FS.EVU):

    def list(self):  # GetDeltaker_50
        """Hent info om personer som er ekte EVU-studenter ved
        dvs. er registrert i EVU-modulen i tabellen
        fs.deltaker,  Henter alle som er knyttet til kurs som
        tidligst ble avsluttet for 30 dager siden."""

        qry = """
        SELECT DISTINCT
               p.fodselsdato, p.personnr, p.etternavn, p.fornavn,
               d.adrlin1_job, d.adrlin2_job, d.postnr_job,
               d.adrlin3_job, d.adresseland_job, d.adrlin1_hjem,
               d.adrlin2_hjem, d.postnr_hjem, d.adrlin3_hjem,
               d.adresseland_hjem, p.adrlin1_hjemsted,
               p.status_reserv_nettpubl, p.adrlin2_hjemsted,
               p.postnr_hjemsted, p.adrlin3_hjemsted,
               p.adresseland_hjemsted, d.deltakernr, d.emailadresse,
               k.etterutdkurskode, k.kurstidsangivelsekode,
               e.studieprogramkode, e.faknr_adm_ansvar,
               e.instituttnr_adm_ansvar, e.gruppenr_adm_ansvar,
               p.kjonn, p.status_dod,
               nvl(trim(leading '0' from
                trim(leading '+' from p.telefonlandnr_mobil)), '47')
                    telefonlandnr_mobil,
               p.telefonretnnr_mobil, p.telefonnr_mobil
        FROM fs.deltaker d, fs.person p, fs.kursdeltakelse k,
             fs.etterutdkurs e
        WHERE p.fodselsdato=d.fodselsdato AND
              p.personnr=d.personnr AND
              d.deltakernr=k.deltakernr AND
              e.etterutdkurskode=k.etterutdkurskode AND
              NVL(e.status_kontotildeling,'J')='J' AND
              k.kurstidsangivelsekode = e.kurstidsangivelsekode AND
              k.kursavbruddstatuskode IS NULL AND
              NVL(e.dato_til, SYSDATE) >= SYSDATE - 30"""
        return self.db.query(qry)

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
          status_aktiv, status_nettbasert_und, status_eksport_lms,
          lmsrommalkode
        FROM fs.etterutdkurs
        WHERE status_aktiv='J' AND
          NVL(dato_til, SYSDATE) >= (SYSDATE - 30)
        """
        return self.db.query(qry)
    # end list_kurs

    def get_kurs_aktivitet(self, kurs, tid):  # GetAktivitetEvuKurs
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

    def list_kurs_aktiviteter(self):
        """Som get_kurs_aktivitet, men lister opp alle.

        Hent alle EVU-kursaktiviteter som finnes. Vi må naturligvis følge de
        samme begrensningene som gjelder for list_kurs (derav en join).
        """

        qry = """
        SELECT k.etterutdkurskode, k.kurstidsangivelsekode, k.aktivitetskode,
               k.aktivitetsnavn, k.undformkode, k.status_eksport_lms,
               k.lmsrommalkode
        FROM fs.kursaktivitet k, fs.etterutdkurs e
        WHERE e.status_aktiv = 'J' AND
              NVL(e.dato_til, SYSDATE) >= (SYSDATE - 30) AND
              k.etterutdkurskode = e.etterutdkurskode AND
              k.kurstidsangivelsekode = e.kurstidsangivelsekode
        """

        return self.db.query(qry)
    # end list_kurs_aktiviteter

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


@fsobject('evu', '>=7.8')
class UiOEVU78(UiOEVU, access_FS.EVU78):
    def list(self):  # GetDeltaker_50
        """Hent info om personer som er ekte EVU-studenter ved
        dvs. er registrert i EVU-modulen i tabellen
        fs.deltaker,  Henter alle som er knyttet til kurs som
        tidligst ble avsluttet for 30 dager siden."""

        qry = """
        SELECT DISTINCT
               p.fodselsdato, p.personnr, p.etternavn, p.fornavn,
               d.adrlin1_job, d.adrlin2_job, d.postnr_job,
               d.adrlin3_job, d.adresseland_job, d.adrlin1_hjem,
               d.adrlin2_hjem, d.postnr_hjem, d.adrlin3_hjem,
               d.adresseland_hjem, p.adrlin1_hjemsted,
               p.status_reserv_nettpubl, p.adrlin2_hjemsted,
               p.postnr_hjemsted, p.adrlin3_hjemsted,
               p.adresseland_hjemsted, d.deltakernr, d.emailadresse,
               k.etterutdkurskode, k.kurstidsangivelsekode,
               e.studieprogramkode, e.faknr_adm_ansvar,
               e.instituttnr_adm_ansvar, e.gruppenr_adm_ansvar,
               p.kjonn, p.status_dod,
               pt.telefonlandnr telefonlandnr_mobil, '' telefonretnnr_mobil,
               pt.telefonnr telefonnr_mobil
        FROM fs.deltaker d, fs.kursdeltakelse k,
             fs.etterutdkurs e, fs.person p LEFT JOIN fs.persontelefon pt ON
             pt.fodselsdato = p.fodselsdato AND
             pt.personnr = p.personnr AND
             pt.telefonnrtypekode = 'MOBIL'
        WHERE p.fodselsdato=d.fodselsdato AND
              p.personnr=d.personnr AND
              d.deltakernr=k.deltakernr AND
              e.etterutdkurskode=k.etterutdkurskode AND
              NVL(e.status_kontotildeling,'J')='J' AND
              k.kurstidsangivelsekode = e.kurstidsangivelsekode AND
              k.kursavbruddstatuskode IS NULL AND
              NVL(e.dato_til, SYSDATE) >= SYSDATE - 30"""
        return self.db.query(qry)


@fsobject('studieinfo')
class UiOStudieInfo(access_FS.StudieInfo):

    def list_kull(self):
        """Henter informasjon om aktive studiekull."""
        qry = """
        SELECT DISTINCT
          k.studieprogramkode, k.terminkode, k.arstall, k.studiekullnavn,
          k.kulltrinn_start, k.terminnr_maks, k.status_generer_epost,
          s.institusjonsnr_studieansv, s.faknr_studieansv,
          s.instituttnr_studieansv, s.gruppenr_studieansv,
          k.lmsrommalkode
        FROM  fs.kull k, fs.studieprogram s
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


@fsobject('forkurs')
class UiOForkurs(access_FS.FSObject):
    """Class for fetching specially registred forkurs students."""
    def list(self, course_code='FORGLU'):
        """List students registred for a pre-course.

        :type course_code: str
        :param course_code: The course code to fetch students for. Default:
            'FORGLU'
        :return: A list of pre-course students
        """
        return self.db.query("""
        SELECT
            FS.VURDKOMBMELDING.FODSELSDATO,
            FS.VURDKOMBMELDING.PERSONNR,
            FS.STUDENT.STUDENTNR_TILDELT,
            FS.PERSON.FORNAVN,
            FS.PERSON.ETTERNAVN,
            FS.PERSONTELEFON.TELEFONLANDNR,
            FS.PERSONTELEFON.TELEFONNR
        FROM FS.VURDKOMBMELDING
        INNER JOIN FS.STUDENT
            ON FS.STUDENT.FODSELSDATO = FS.VURDKOMBMELDING.FODSELSDATO
                AND FS.STUDENT.PERSONNR = FS.VURDKOMBMELDING.PERSONNR
                AND FS.STUDENT.INSTITUSJONSNR_EIER = FS.VURDKOMBMELDING.INSTITUSJONSNR_EIER
        INNER JOIN FS.PERSON
            ON FS.PERSON.FODSELSDATO = FS.STUDENT.FODSELSDATO
                AND FS.PERSON.PERSONNR = FS.STUDENT.PERSONNR
                AND FS.PERSON.INSTITUSJONSNR_EIER = FS.STUDENT.INSTITUSJONSNR_EIER
        LEFT JOIN FS.PERSONTELEFON
            ON FS.PERSON.FODSELSDATO = FS.PERSONTELEFON.FODSELSDATO
                AND FS.PERSON.PERSONNR = FS.PERSONTELEFON.PERSONNR
                AND FS.PERSON.INSTITUSJONSNR_EIER = FS.PERSONTELEFON.INSTITUSJONSNR_EIER
                AND FS.PERSONTELEFON.TELEFONNRTYPEKODE LIKE 'MOBIL'
        WHERE FS.VURDKOMBMELDING.EMNEKODE LIKE '{}'""".format(course_code))


@fsobject('FS')
class FS(access_FS.FS):

    def __init__(self, db=None, user=None, database=None):
        super(FS, self).__init__(db=db, user=user, database=database)

        # Override with uio-spesific classes
        for comp in 'person student undervisning evu'.split():
            setattr(self, comp, self._component(comp)(self.db))
        # self.portal = UiOPortal(self.db)
        self.betaling = UiOBetaling(self.db)
        self.info = self._component('studieinfo')(self.db)

    def list_dbfg_usernames(self, fetchall=False):
        """Get all usernames and return them as a sequence of db_rows.

        Usernames may be prefixed with a institution specific tag, if the db has
        defined this. If defined, only usernames with the prefix are returned,
        and the prefix is stripped out.

        NB! This function does *not* return a 2-tuple. Only a sequence of
        all usernames (the column names can be obtains from db_row objects)
        """
        prefix = self.get_username_prefix()
        ret = ({'username': row['username'][len(prefix):]} for row in
               self.db.query("""
                            SELECT username as username
                            FROM all_users
                            WHERE username LIKE :prefixed
                        """, {'prefixed': '%s%%' % prefix},
                             fetchall=fetchall))
        if fetchall:
            return list(ret)
        return ret

    def list_dba_usernames(self, fetchall=False):
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

    def get_username_prefix(self):
        """Get the database' defined username prefix, or '' if not defined."""
        try:
            return self.db.query_1("SELECT brukerprefiks FROM fs.systemverdier")
        except self.db.DatabaseError:
            pass
        return ''


@fsobject('person', '<7.8')
class UiOPerson(access_FS.Person):

    def set_ansattnr(self, fnr, pnr, asn):
        """Sets the ansattnr for a person"""
        return self.db.execute("""
        UPDATE fs.person SET ansattnr=:asn WHERE fodselsdato=:fnr
        AND personnr=:pnr""", {'fnr': fnr, 'pnr': pnr, 'asn': asn})

    def get_ansattnr(self, fnr, pnr):
        """Gets the ansattnr for a person"""
        return self.db.query("""
                SELECT
                    ansattnr
                FROM
                    fs.person
                WHERE
                    fodselsdato=:fnr
                AND
                    personnr=:pnr""",
                             {'fnr': fnr, 'pnr': pnr}, fetchall=True)

    def add_person(self, fnr, pnr, fornavn, etternavn, email, kjonn,
                   birth_date, ansattnr=None):
        """Adds a person to the FS-database."""
        if ansattnr is None:
            ansattnr = 0
        return self.db.execute("""
        INSERT INTO fs.person
          (fodselsdato, personnr, fornavn, etternavn, fornavn_uppercase,
           etternavn_uppercase, emailadresse, kjonn, dato_fodt, ansattnr)
        VALUES
          (:fnr, :pnr, :fornavn, :etternavn, UPPER(:fornavn2),
          UPPER(:etternavn2), :email, :kjonn,
          TO_DATE(:birth_date, 'YYYY-MM-DD'), :ansattnr)""", {
            'fnr': fnr, 'pnr': pnr, 'fornavn': fornavn,
            'etternavn': etternavn, 'email': email,
            'kjonn': kjonn, 'birth_date': birth_date,
            'fornavn2': fornavn, 'etternavn2': etternavn,
            'ansattnr': ansattnr})

    def update_fagperson(self, fodselsdato, personnr, **rest):
        """Updates the specified columns in fagperson, when the field
        'status_ekstern' is not equal 'J'"""

        binds = {"fodselsdato": fodselsdato, "personnr": personnr, }
        names_to_set = ["%s = :%s" % (x, x) for x in rest]
        binds.update(rest)
        return self.db.execute("""
        UPDATE fs.fagperson
        SET %s
        WHERE fodselsdato = :fodselsdato AND personnr = :personnr
        AND NOT status_ekstern = 'J'
        """ % ", ".join(names_to_set), binds)


@fsobject('person', '>=7.8')
class UiOPerson78(UiOPerson, access_FS.Person78):
    pass


class FSvpd(FS):
    """Subclass of FS for handling Virtual Private Databases (VPD)."""

    def list_dba_usernames(self, fetchall=False):
        """Get all usernames for internal statistics. In VPD, a 'View' is
        created for only returning the institution's users instead of
        dba_users."""

        prefix = self.get_username_prefix()
        query = """
        SELECT
           LOWER(username) AS username
        FROM
           FS.View_FS_Bruker
        WHERE
           default_tablespace = 'USERS' AND account_status = 'OPEN'
           AND username LIKE :prefixed
        """
        ret = ({'username': row['username'][len(prefix):]} for row in
               self.db.query(query, {'prefixed': '%s%%' % prefix},
                             fetchall=fetchall))
        if fetchall:
            return list(ret)
        return ret

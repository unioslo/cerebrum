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
class HiAStudent(access_FS.Student):

    def list_aktiv(self, fodselsdato=None, personnr=None):
        """ Hent opplysninger om studenter definert som aktive
        ved HiA. En aktiv student er en student som har et gyldig
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
          sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
          sps.arstall_kull, p.kjonn, p.status_dod,
          nvl(trim(leading '0' from
                   trim(leading '+' from p.telefonlandnr_mobil)), '47')
                telefonlandnr_mobil,
          p.telefonretnnr_mobil, p.telefonnr_mobil,
          s.studentnr_tildelt
        FROM fs.studieprogramstudent sps, fs.person p,
             fs.student s
        WHERE p.fodselsdato = sps.fodselsdato AND
          p.personnr = sps.personnr AND
          p.fodselsdato = s.fodselsdato AND
          p.personnr = s.personnr AND
          %s
          %s AND
          sps.status_privatist = 'N' AND
          sps.studentstatkode IN ('AKTIV', 'PERMISJON') AND
          NVL(sps.dato_studierett_gyldig_til,SYSDATE)>= SYSDATE
          """ % (extra, self._is_alive())
        return self.db.query(qry, locals())

    def list_jasvar(self):
        """ Hent opplysninger om personer som har takket ja til
        til tilbud om studieplass ved UiA. Skal kun brukes en gang,
        høsten 2010. Jazz"""
        qry = """
        SELECT DISTINCT
          p.fodselsdato, p.personnr, p.etternavn, p.fornavn,
          p.adrlin1_hjemsted, p.adrlin2_hjemsted, p.postnr_hjemsted,
          p.adrlin3_hjemsted, p.adresseland_hjemsted,
          p.status_reserv_nettpubl, p.sprakkode_malform,
          nvl(trim(leading '0' from
                   trim(leading '+' from p.telefonlandnr_mobil)), '47')
                telefonlandnr_mobil,
          p.telefonretnnr_mobil, p.telefonnr_mobil,
          s.adrlin1_kontakt, s.adrlin2_kontakt, s.postnr_kontakt,
          s.adrlin3_kontakt, s.adresseland_kontakt,
          sp.studieprogramkode
        FROM fs.soknadsalternativ sa, fs.person p, fs.opptakstudieprogram osp,
             fs.opptakstudieprogramtermin ost, fs.soknad s, fs.studieprogram sp
        WHERE p.fodselsdato = sa.fodselsdato AND
              p.personnr = sa.personnr AND
              p.fodselsdato = s.fodselsdato AND
              p.personnr = s.personnr AND
              sa.institusjonsnr = %s AND
              sa.tilbudstatkode IN ('I', 'S') AND
              sa.svarstatkode_svar_pa_tilbud='J' AND
              sa.studietypenr = osp.studietypenr AND
              sa.institusjonsnr = osp.institusjonsnr AND
              sa.opptakstypekode = osp.opptakstypekode AND
              sa.opptakstypekode <> 'SOMMER' AND
              sa.terminkode = 'HØST' AND
              sa.arstall = 2010 AND
              osp.opptakstypekode = ost.opptakstypekode AND
              osp.studietypenr = ost.studietypenr AND
              osp.institusjonsnr = ost.institusjonsnr AND
              ost.terminkode = sa.terminkode AND
              ost.arstall = sa.arstall AND
              ost.studieprogramkode = sp.studieprogramkode AND
              %s""" % (self.institusjonsnr, self._is_alive())
        return self.db.query(qry, locals())

    def list_aktiv_deprecated(self):
        """ Hent opplysninger om studenter definert som aktive
        ved HiA. En aktiv student er enten med i et aktivt kull og
        har et gyldig studierett eller har en forekomst i registerkort
        for inneværende semester og har en gyldig studierett"""

        qry = """
        SELECT DISTINCT
          s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
          s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
          s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
          p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
          p.adresseland_hjemsted, p.status_reserv_nettpubl,
          p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
          sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
          sps.arstall_kull, p.kjonn, p.status_dod,
          nvl(trim(leading '0' from
                   trim(leading '+' from p.telefonlandnr_mobil)), '47')
                telefonlandnr_mobil,
          p.telefonretnnr_mobil, p.telefonnr_mobil,
          s.studentnr_tildelt
        FROM fs.kull k, fs.studieprogramstudent sps, fs.person p,
             fs.student s
        WHERE p.fodselsdato = sps.fodselsdato AND
          p.personnr = sps.personnr AND
          p.fodselsdato = s.fodselsdato AND
          p.personnr = s.personnr AND
          %s AND
          k.studieprogramkode = sps.studieprogramkode AND
          k.terminkode = sps.terminkode_kull AND
          k.arstall = sps.arstall_kull AND
          NVL(k.status_aktiv,'J') = 'J' AND
          NVL(sps.dato_studierett_gyldig_til,SYSDATE)>= SYSDATE
        UNION
        SELECT DISTINCT
          s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
          s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
          s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
          p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
          p.adresseland_hjemsted, p.status_reserv_nettpubl,
          p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
          sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
          sps.arstall_kull, p.kjonn, p.status_dod,
          nvl(trim(leading '0' from
                   trim(leading '+' from p.telefonlandnr_mobil)), '47')
                telefonlandnr_mobil,
          p.telefonretnnr_mobil, p.telefonnr_mobil,
          s.studentnr_tildelt
        FROM fs.registerkort r, fs.studieprogramstudent sps,
          fs.person p, fs.student s
        WHERE p.fodselsdato = sps.fodselsdato AND
          p.personnr = sps.personnr AND
          p.fodselsdato = s.fodselsdato AND
          p.personnr = s.personnr AND
          %s AND
          p.fodselsdato = r.fodselsdato AND
          p.personnr = r.personnr AND
          NVL(sps.dato_studierett_gyldig_til,SYSDATE)>= SYSDATE AND
          %s """ % (self._is_alive(), self._is_alive(),
                    self._get_termin_aar(only_current=1))
        return self.db.query(qry)


@fsobject('student', '>=7.8')
class HiAStudent78(HiAStudent, access_FS.Student78):

    def list_aktiv(self, fodselsdato=None, personnr=None):
        """ Hent opplysninger om studenter definert som aktive
        ved HiA. En aktiv student er en student som har et gyldig
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
          sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
          sps.arstall_kull, p.kjonn, p.status_dod,
          pt.telefonlandnr telefonlandnr_mobil, '' telefonretnnr_mobil,
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
          %s
          %s AND
          sps.status_privatist = 'N' AND
          sps.studentstatkode IN ('AKTIV', 'PERMISJON') AND
          NVL(sps.dato_studierett_gyldig_til,SYSDATE)>= SYSDATE
          """ % (extra, self._is_alive())
        return self.db.query(qry, locals())

    def list_jasvar(self):
        """ Hent opplysninger om personer som har takket ja til
        til tilbud om studieplass ved UiA. Skal kun brukes en gang,
        høsten 2010. Jazz"""
        qry = """
        SELECT DISTINCT
          p.fodselsdato, p.personnr, p.etternavn, p.fornavn,
          p.adrlin1_hjemsted, p.adrlin2_hjemsted, p.postnr_hjemsted,
          p.adrlin3_hjemsted, p.adresseland_hjemsted,
          p.status_reserv_nettpubl, p.sprakkode_malform,
          pt.telefonlandnr telefonlandnr_mobil, '' telefonretnnr_mobil,
          pt.telefonnr telefonnr_mobil,
          s.adrlin1_kontakt, s.adrlin2_kontakt, s.postnr_kontakt,
          s.adrlin3_kontakt, s.adresseland_kontakt,
          sp.studieprogramkode
        FROM fs.soknadsalternativ sa, fs.opptakstudieprogram osp,
             fs.opptakstudieprogramtermin ost, fs.soknad s, fs.studieprogram sp,
             fs.person p LEFT JOIN fs.persontelefon pt ON
              pt.fodselsdato = p.fodselsdato AND
              pt.personnr = p.personnr AND
              pt.telefonnrtypekode = 'MOBIL'
        WHERE p.fodselsdato = sa.fodselsdato AND
              p.personnr = sa.personnr AND
              p.fodselsdato = s.fodselsdato AND
              p.personnr = s.personnr AND
              sa.institusjonsnr = %s AND
              sa.tilbudstatkode IN ('I', 'S') AND
              sa.svarstatkode_svar_pa_tilbud='J' AND
              sa.studietypenr = osp.studietypenr AND
              sa.institusjonsnr = osp.institusjonsnr AND
              sa.opptakstypekode = osp.opptakstypekode AND
              sa.opptakstypekode <> 'SOMMER' AND
              sa.terminkode = 'HØST' AND
              sa.arstall = 2010 AND
              osp.opptakstypekode = ost.opptakstypekode AND
              osp.studietypenr = ost.studietypenr AND
              osp.institusjonsnr = ost.institusjonsnr AND
              ost.terminkode = sa.terminkode AND
              ost.arstall = sa.arstall AND
              ost.studieprogramkode = sp.studieprogramkode AND
              %s""" % (self.institusjonsnr, self._is_alive())
        return self.db.query(qry, locals())

    def list_aktiv_deprecated(self):
        """ Hent opplysninger om studenter definert som aktive
        ved HiA. En aktiv student er enten med i et aktivt kull og
        har et gyldig studierett eller har en forekomst i registerkort
        for inneværende semester og har en gyldig studierett"""

        qry = """
        SELECT DISTINCT
          s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
          s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
          s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
          p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
          p.adresseland_hjemsted, p.status_reserv_nettpubl,
          p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
          sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
          sps.arstall_kull, p.kjonn, p.status_dod,
          pt.telefonlandnr telefonlandnr_mobil, '' telefonretnnr_mobil,
          pt.telefonnr telefonnr_mobil,
          s.studentnr_tildelt
        FROM fs.kull k, fs.studieprogramstudent sps, fs.student s,
             fs.person p
             LEFT JOIN fs.persontelefon pt ON
             pt.fodselsdato = p.fodselsdato AND
             pt.personnr = p.personnr AND
             pt.telefonnrtypekode = 'MOBIL'
        WHERE p.fodselsdato = sps.fodselsdato AND
          p.personnr = sps.personnr AND
          p.fodselsdato = s.fodselsdato AND
          p.personnr = s.personnr AND
          %s AND
          k.studieprogramkode = sps.studieprogramkode AND
          k.terminkode = sps.terminkode_kull AND
          k.arstall = sps.arstall_kull AND
          NVL(k.status_aktiv,'J') = 'J' AND
          NVL(sps.dato_studierett_gyldig_til,SYSDATE)>= SYSDATE
        UNION
        SELECT DISTINCT
          s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
          s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
          s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
          p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
          p.adresseland_hjemsted, p.status_reserv_nettpubl,
          p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
          sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
          sps.arstall_kull, p.kjonn, p.status_dod,
          pt.telefonlandnr telefonlandnr_mobil, '' telefonretnnr_mobil,
          pt.telefonnr telefonnr_mobil,
          s.studentnr_tildelt
        FROM fs.registerkort r, fs.studieprogramstudent sps,
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
          p.fodselsdato = r.fodselsdato AND
          p.personnr = r.personnr AND
          NVL(sps.dato_studierett_gyldig_til,SYSDATE)>= SYSDATE AND
          %s """ % (self._is_alive(), self._is_alive(),
                    self._get_termin_aar(only_current=1))
        return self.db.query(qry)


@fsobject('undervisning', '<7.8')
class HiAUndervisning(access_FS.Undervisning):

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
            e.gruppenr_kontroll, r.terminnr, r.terminkode, r.arstall
        FROM fs.emne e, fs.undervisningsenhet r
        WHERE r.emnekode = e.emnekode AND
            r.versjonskode = e.versjonskode AND """
        if sem == "current":
            qry += """%s""" % self._get_termin_aar(only_current=1)
        else:
            qry += """%s""" % self._get_next_termin_aar()
        return self.db.query(qry)

    def list_studenter_underv_enhet(self, institusjonsnr, emnekode,
                                    versjonskode, terminkode,
                                    arstall, terminnr):
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

    def list_studenter_kull_deprecated(self, studieprogramkode,
                                       terminkode, arstall):
        """Hent alle studentene som er oppført på et gitt kull."""

        query = """
        SELECT DISTINCT
            fodselsdato, personnr
        FROM
            fs.studieprogramstudent
        WHERE
            studieprogramkode = :studieprogramkode AND
            terminkode_kull = :terminkode_kull AND
            arstall_kull = :arstall_kull
        """

        return self.db.query(query, {"studieprogramkode": studieprogramkode,
                                     "terminkode_kull": terminkode,
                                     "arstall_kull": arstall})


@fsobject('undervisning', '>=7.8')
class HiAUndervisning78(HiAUndervisning, access_FS.Undervisning78):
    pass


@fsobject('evu', '<7.8')
class HiAEVU(access_FS.EVU):

    def list_kurs(self, date=time.localtime()):  # GetEvuKurs
        d = time.strftime("%Y-%m-%d", date)
        qry = """
        SELECT DISTINCT e.etterutdkurskode, e.kurstidsangivelsekode,
          e.etterutdkursnavn, e.etterutdkursnavnkort, ee.emnekode,
          e.institusjonsnr_adm_ansvar, e.faknr_adm_ansvar,
          e.instituttnr_adm_ansvar, e.gruppenr_adm_ansvar,
          TO_CHAR(NVL(e.dato_fra, SYSDATE), 'YYYY-MM-DD') AS dato_fra,
          TO_CHAR(NVL(e.dato_til, SYSDATE), 'YYYY-MM-DD') AS dato_til,
          e.status_aktiv, e.status_nettbasert_und
        FROM fs.etterutdkurs e, fs.etterutdkursemne ee
        WHERE e.etterutdkurskode=ee.etterutdkurskode (+) AND
          e.kurstidsangivelsekode=ee.kurstidsangivelsekode (+) AND
          e.status_aktiv='J' AND
          e.status_nettbasert_und='J' AND
          NVL(TO_DATE('%s', 'YYYY-MM-DD'), SYSDATE) < (e.dato_til + 30)
        """ % d
        return self.db.query(qry)

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
               k.etterutdkurskode, e.studieprogramkode,
               e.faknr_adm_ansvar, e.instituttnr_adm_ansvar,
               e.gruppenr_adm_ansvar, p.kjonn, p.status_dod,
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
              (NVL(e.status_kontotildeling,'J')='J' OR
              NVL(e.status_nettbasert_und,'J')='J') AND
              NVL(k.svarstatkode_svar_pa_tilbud, 'N')='J' AND
              k.kurstidsangivelsekode = e.kurstidsangivelsekode AND
              NVL(e.dato_til, SYSDATE) >= SYSDATE - 30"""
        return self.db.query(qry)


@fsobject('evu', '>=7.8')
class HiAEVU78(HiAEVU, access_FS.EVU78):

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
               k.etterutdkurskode, e.studieprogramkode,
               e.faknr_adm_ansvar, e.instituttnr_adm_ansvar,
               e.gruppenr_adm_ansvar, p.kjonn, p.status_dod,
               pt.telefonlandnr telefonlandnr_mobil,
               '' telefonretnnr_mobil, pt.telefonnr telefonnr_mobil
        FROM fs.deltaker d, fs.kursdeltakelse k,
             fs.etterutdkurs e, fs.person p
             LEFT JOIN fs.persontelefon pt ON
              pt.fodselsdato = p.fodselsdato AND
              pt.personnr = p.personnr AND
              pt.telefonnrtypekode = 'MOBIL'
        WHERE p.fodselsdato=d.fodselsdato AND
              p.personnr=d.personnr AND
              d.deltakernr=k.deltakernr AND
              e.etterutdkurskode=k.etterutdkurskode AND
              (NVL(e.status_kontotildeling,'J')='J' OR
              NVL(e.status_nettbasert_und,'J')='J') AND
              NVL(k.svarstatkode_svar_pa_tilbud, 'N')='J' AND
              k.kurstidsangivelsekode = e.kurstidsangivelsekode AND
              NVL(e.dato_til, SYSDATE) >= SYSDATE - 30"""
        return self.db.query(qry)


@fsobject('FS')
class FS(access_FS.FS):

    def __init__(self, db=None, user=None, database=None):
        super(FS, self).__init__(db=db, user=user, database=database)

        t = time.localtime()[0:3]
        self.year = t[0]
        self.mndnr = t[1]
        self.dday = t[2]

        # Override with hia-spesific classes
        self.student = self._component('student')(db)
        self.undervisning = self._component('undervisning')(db)
        self.evu = self._component('evu')(db)

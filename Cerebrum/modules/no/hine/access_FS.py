# -*- coding: iso-8859-1 -*-
# Copyright 2009, 2010, 2012 University of Oslo, Norway
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

from Cerebrum.modules.no import access_FS


fsobject = access_FS.fsobject


@fsobject('student', '<7.8')
class HineStudent(access_FS.Student):

    def list_aktiv(self):
        """ Hent opplysninger om studenter definert som aktive
            ved Hine. En aktiv student er en student som har et gyldig
            opptak til et studieprogram der studentstatuskode er 'AKTIV'
            eller 'PERMISJON' og sluttdatoen er enten i fremtiden eller
            ikke satt."""
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
              s.studentnr_tildelt, p.emailadresse_privat,
              nvl(trim(leading '0' from
                   trim(leading '+' from p.telefonlandnr_mobil)), '47')
                telefonlandnr_mobil,
              p.telefonretnnr_mobil, p.telefonnr_mobil
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


@fsobject('student', '>=7.8')
class HineStudent78(HineStudent, access_FS.Student78):

    def list_aktiv(self):
        """ Hent opplysninger om studenter definert som aktive
            ved Hine. En aktiv student er en student som har et gyldig
            opptak til et studieprogram der studentstatuskode er 'AKTIV'
            eller 'PERMISJON' og sluttdatoen er enten i fremtiden eller
            ikke satt."""
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
              s.studentnr_tildelt, p.emailadresse_privat,
              pt.telefonlandnr telefonlandnr_mobil,
              '' telefonretnnr_mobil,
              pt.telefonnr telefonnr_mobil
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
              sps.studentstatkode IN ('AKTIV', 'PERMISJON') AND
              NVL(sps.dato_studierett_gyldig_til,SYSDATE)>= SYSDATE
              """ % (self._is_alive())
        return self.db.query(qry)


@fsobject('studieinfo')
class HINEStudieInfo(access_FS.StudieInfo):

    def list_ou(self, institusjonsnr=0):  # GetAlleOUer
        """Hent data om stedskoder registrert i FS"""
        qry = """
        SELECT DISTINCT
           institusjonsnr, faknr, instituttnr, gruppenr, stedakronym,
           stednavn_bokmal, faknr_org_under, instituttnr_org_under,
           gruppenr_org_under, adrlin1, adrlin2, postnr, adrlin3,
           stedkortnavn, telefonnr, faxnr, adrlin1_besok, emailadresse,
           adrlin2_besok, postnr_besok, url, bibsysbeststedkode,
           stedkode_konv
        FROM fs.sted
        WHERE institusjonsnr=%s AND
              stedkode_konv IS NOT NULL
        """ % self.institusjonsnr
        return self.db.query(qry)


@fsobject('FS')
class FS(access_FS.FS):

    def __init__(self, db=None, user=None, database=None):
        super(FS, self).__init__(db=db, user=user, database=database)

        # Override with HiNE-spesific classes
        self.info = self._component('studieinfo')(self.db)
        self.student = HineStudent('student')(self.db)

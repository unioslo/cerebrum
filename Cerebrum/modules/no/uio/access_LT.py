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

from Cerebrum import Database,Errors
from Cerebrum.modules.no import fodselsnr

class LT(object):
    """Methods for fetching person, OU and some other information from LT"""
    def __init__(self, db):
        self.db = db

    def GetSteder(self):
        "Henter informasjon om alle ikke-nedlagte steder"
        qry = """
SELECT
  fakultetnr, instituttnr, gruppenr,
  forkstednavn, NVL(stednavnfullt, stednavn) as stednavn, akronym,
  stedkortnavn_bokmal, stedkortnavn_nynorsk, stedkortnavn_engelsk,
  stedlangnavn_bokmal, stedlangnavn_nynorsk, stedlangnavn_engelsk,
  fakultetnr_for_org_sted, instituttnr_for_org_sted, gruppenr_for_org_sted,
  opprettetmerke_for_oppf_i_kat,
  telefonnr, innvalgnr, linjenr,
  stedpostboks,
  adrtypekode_besok_adr, adresselinje1_besok_adr, adresselinje2_besok_adr,
  poststednr_besok_adr, poststednavn_besok_adr, landnavn_besok_adr,
  adrtypekode_intern_adr, adresselinje1_intern_adr, adresselinje2_intern_adr,
  poststednr_intern_adr, poststednavn_intern_adr, landnavn_intern_adr,
  adrtypekode_alternativ_adr, adresselinje1_alternativ_adr,
  adresselinje2_alternativ_adr, poststednr_alternativ_adr,
  poststednavn_alternativ_adr, landnavn_alternativ_adr
FROM lt.sted
WHERE
  dato_opprettet <= SYSDATE AND dato_nedlagt > SYSDATE
ORDER BY fakultetnr, instituttnr, gruppenr"""
        r = self.db.query(qry)
        return ([x[0] for x in self.db.description], r)

    def GetStedKomm(self, fak, inst, gr):
        "Henter kontaktinformasjon for et sted"
        qry = """SELECT kommtypekode, tlfpreftegn, telefonnr, kommnrverdi
FROM lt.stedkomm
WHERE
  fakultetnr=:fak AND
  instituttnr=:inst AND
  gruppenr=:gr AND
  kommtypekode IN ('EKSTRA TLF', 'FAX', 'FAXUTLAND', 'TLF', 'TLFUTL',
                   'EPOST', 'URL')
ORDER BY tlfpreftegn"""
        return (self._get_cols(qry),
                self.db.query(qry, {'fak': fak, 'inst': inst, 'gr': gr}))

    def GetTilsettinger(self):
        "Henter alle tilsetninger med dato_til frem i tid"
        qry = """SELECT DISTINCT t.fodtdag, t.fodtmnd, t.fodtar,
               t.personnr, t.fakultetnr_utgift, t.instituttnr_utgift,
               t.gruppenr_utgift, NVL(t.stillingkodenr_beregnet_sist,
                                      s.stillingkodenr),
               t.prosent_tilsetting,
               TO_CHAR(t.dato_fra, 'YYYYMMDD'),
               TO_CHAR(t.dato_til, 'YYYYMMDD'),
               t.tilsnr
            FROM lt.tilsetting t, lt.stilling s
	    WHERE dato_fra <= SYSDATE AND
                  NVL(dato_til, SYSDATE) > SYSDATE AND
                  t.stilnr = s.stilnr"""
        return (self._get_cols(qry), self.db.query(qry))

    def GetTitler(self):
        "Hent informasjon om stillingskoder, kronologisk sortert"
        qry = """SELECT stillingkodenr, tittel, univstkatkode
        FROM lt.stillingskode ORDER BY dato_fra"""
        return (self._get_cols(qry), self.db.query(qry))

    def GetLonnsPosteringer(self, tid):
        """Hent person og sted informasjon for alle lønnsposteringer med
        relevante beløpskoder foretatt etter TID"""
        qry = """SELECT belopskodenr
        FROM lt.belkodespesielle WHERE belkodeomradekode='LT35UREG' """
        koder = [str(k['belopskodenr']) for k in self.db.query(qry)]
        qry = ("""SELECT TO_CHAR(dato_oppgjor, 'YYYYMMDD'), p.fodtdag,
               p.fodtmnd, p.fodtar, p.personnr, fakultetnr_kontering,
               instituttnr_kontering, gruppenr_kontering
            FROM lt.lonnspostering p, lt.delpostering d
	    WHERE p.posteringsnr=d.posteringsnr AND
               p.aarnr_termin=d.aarnr AND p.mndnr_termin=d.mndnr AND
               p.fodtdag=d.fodtdag AND p.fodtmnd=d.fodtmnd AND
               p.fodtar=d.fodtar AND p.personnr=d.personnr AND
               dato_oppgjor > TO_DATE(%s, 'YYYYMMDD') AND
               d.belopskodenr IN (""" % tid +", ".join(koder)+")")
        return (self._get_cols(qry), self.db.query(qry))

    def GetGjester(self):
        "Hent informasjon om gjester"
        qry = """SELECT fodtdag, fodtmnd, fodtar, personnr,
                    fakultetnr, instituttnr, gruppenr, gjestetypekode,
                    TO_CHAR(dato_fra, 'YYYYMMDD'), TO_CHAR(dato_til, 'YYYYMMDD')
                 FROM lt.gjest
                 WHERE dato_fra <= SYSDATE AND NVL(dato_til, SYSDATE) > SYSDATE"""
        return (self._get_cols(qry), self.db.query(qry))

    def GetPersonRoller(self, fodtdag, fodtmnd, fodtar, personnr):
        "Hent informasjon om hvilke roller en person har"
        qry = """SELECT
  fakultetnr, instituttnr, gruppenr, ansvarsrollekode,
  TO_CHAR(dato_fra, 'YYYYMMDD'), TO_CHAR(dato_til, 'YYYYMMDD')
FROM lt.personrolle
WHERE fodtdag=:fodtdag AND fodtmnd=:fodtmnd AND fodtar=:fodtar AND
  personnr=:personnr AND dato_fra <= SYSDATE AND NVL(dato_til,
  SYSDATE) > SYSDATE"""
        return (self._get_cols(qry), self.db.query(qry, locals()))
        
    def GetPersonInfo(self, fodtdag, fodtmnd, fodtar, personnr):
        "Hent informasjon om en bestemt person"
        qry = """SELECT
  fornavn, etternavn, navn, adrtypekode_privatadresse,
  adresselinje1_privatadresse, adresselinje2_privatadresse,
  poststednr_privatadresse, poststednavn_privatadresse,
  landnavn_privatadresse, telefonnr_privattelefon, tittel_personlig,
  fakultetnr_for_lonnsslip, instituttnr_for_lonnsslip,
  gruppenr_for_lonnsslip
FROM
  lt.person
WHERE
  fodtdag=:fodtdag AND fodtmnd=:fodtmnd AND fodtar=:fodtar AND
  personnr=:personnr"""
        return (self._get_cols(qry), self.db.query(qry, locals()))

    def GetArbTelefon(self, fodtdag, fodtmnd, fodtar, personnr):
        "Hent en persons telefon-nr"
        qry = """SELECT
  telefonnr, innvalgnr, linjenr, tlfpreftegn
FROM
  lt.arbstedtelefon
WHERE
  fodtdag=:fodtdag AND fodtmnd=:fodtmnd AND fodtar=:fodtar AND personnr=:personnr
ORDER BY tlfpreftegn"""
        return (self._get_cols(qry), self.db.query(qry, locals()))

    def GetPersKomm(self, fodtdag, fodtmnd, fodtar, personnr):
        "Hent kontakt informasjon for en person"
        qry = """SELECT
  kommtypekode, kommnrverdi, telefonnr, tlfpreftegn
FROM
  lt.perskomm
WHERE
  fodtdag=:fodtdag AND fodtmnd=:fodtmnd AND fodtar=:fodtar AND personnr=:personnr
ORDER BY tlfpreftegn"""
        return (self._get_cols(qry), self.db.query(qry, locals()))

    def GetHovedkategorier(self):
        "Hent hovedkategorier (VIT for vitenskapelig ansatt o.l.)"
        qry = "SELECT univstkatkode, hovedkatkode FROM lt.univstkategori"
        return (self._get_cols(qry), self.db.query(qry))

    def _GetAllPersonsKommType(self, kommtype):
        if kommtype not in ('UREG-EMAIL', 'UREG-USER'):
            raise ValueError, "Bad kommtype: %s" % kommtype
        fnr2komm = []
        for row in self.db.query("""
SELECT
  fodtdag, fodtmnd, fodtar, personnr, kommnrverdi, tlfpreftegn
FROM
  lt.perskomm
WHERE kommtypekode = :kommtype
UNION
SELECT
  fodtdag, fodtmnd, fodtar, personnr, NULL, 'A' AS tlfpreftegn
FROM
  lt.person p
WHERE
  NOT EXISTS (
    SELECT 'x' FROM lt.perskomm k
    WHERE k.kommtypekode = :1 AND
      p.fodtdag = k.fodtdag AND
      p.fodtmnd = k.fodtmnd AND
      p.fodtar = k.fodtar)
ORDER BY fodtdag, fodtmnd, fodtar, personnr, tlfpreftegn""", {
        'kommtype': kommtype}):
            fnr = fodselsnr.personnr_ok(
                "%02d%02s%02d%05d" % (tuple([int(row[x]) for x in (
                'fodtdag', 'fodtmnd', 'fodtar', 'personnr')])))
            fnr = fodselsnr.personnr_ok(fnr)
            if row['kommnrverdi'] is not None:
                ret.setdefault(fnr, []).append(row['kommnrverdi'])
        return fnr2komm

    def GetReservasjoner(self):
        "Finn reservasjoner i LT."
        qry = """
SELECT
  fodtdag, fodtmnd, fodtar, personnr, katalogkode, felttypekode, 
  resnivakode
FROM
  lt.reservasjon
ORDER BY fodtdag, fodtmnd, fodtar, personnr"""
        return (self._get_cols(qry), self.db.query(qry))
    
    def GetAllPersonsUregEmail(self):
        return self._GetAllPersonsKommType('UREG-EMAIL')

    def GetAllPersonsUregUser(self):
        return self._GetAllPersonsKommType('UREG-USER')

    def _DeleteKommtypeVerdi(self, fnr, kommtypekode, kommnrverdi):
        dag, maned, aar, personnr = fodselsnr.del_fnr_4(fnr)
        return self.execute("""
DELETE
  lt.perskomm
WHERE
  Fodtdag=:dag AND
  Fodtmnd=:maned AND
  Fodtar=:aar AND
  Personnr=:personnr AND
  Kommtypekode=:kommtypekode AND
  kommnrverdi=:kommverdi""", {
            'dag': dag,
            'maned': maned,
            'aar': aar,
            'personnr': personnr,
            'kommtypekode': kommtypekode,
            'kommverdi': kommnrverdi})
        
    def DeletePriUser(self, fnr, uname):
        return self._DeleteKommtypeVerdi(fnr, 'UREG-USER', uname)

    def DeletePriMailAddr(self, fnr, email):
        return self._DeleteKommtypeVerdi(fnr, 'UREG-EMAIL', email)

    def _AddKommtypeVerdi(self, fnr, kommtypekode, kommnrverdi):
        dag, maned, aar, personnr = fodselsnr.del_fnr_4(fnr)
        return self.execute("""
INSERT INTO
  lt.perskomm
     (FODTDAG, FODTMND, FODTAR, PERSONNR,
      KOMMTYPEKODE, TLFPREFTEGN, KOMMNRVERDI)
VALUES
  (:dag, :maned, :aar, :personnr, :kommtypekode, 'A', :kommverdi)""", {
            'dag': dag,
            'maned': maned,
            'aar': aar,
            'personnr': personnr,
            'kommtypekode': kommtypekode,
            'kommverdi': kommnrverdi})

    def WritePriMailAddr(self, fnr, email):
        return self._AddKommtypeVerdi(fnr, 'UREG-EMAIL', email)

    def WritePriUser(self, fnr, uname):
        return self._AddKommtypeVerdi(fnr, 'UREG-USER', uname)

    # TODO: Belongs in a separate file, and should consider using row description
    def _get_cols(self, sql):
        sql = re.sub(r"NVL\(stednavnfullt, stednavn\)", "stednavn", sql)
        sql = re.sub(r"TO_CHAR\(([^,]+),\s*'YYYYMMDD'\)", r'\1', sql)
        m = re.compile(r'^\s*SELECT\s*(DISTINCT)?(.*)FROM', re.DOTALL | re.IGNORECASE).match(sql)
        if m == None:
            raise InternalError, "Unreconginzable SQL!"
        return [cols.strip() for cols in m.group(2).split(",")]


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
    # end list_usernames



    def GetPermisjoner(self):
        """
        Returns current leaves of absence (permisjoner) for all individuals
        in LT.
        """
        query = """
                SELECT fodtdag, fodtmnd, fodtar, personnr,
                       tilsnr,
                       TO_CHAR(dato_fra, 'YYYYMMDD') as dato_fra,
                       TO_CHAR(dato_til, 'YYYYMMDD') as dato_til,
                       permarsakkode,
                       prosent_permisjon
                FROM   lt.permisjon
                WHERE  dato_fra <= SYSDATE AND
                       dato_til >= SYSDATE
                """
        return (self._get_cols(query),
                self.db.query(query, locals()))
    # end GetPermisjoner
        


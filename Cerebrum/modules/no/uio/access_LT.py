#!/usr/bin/env python2.2

import re
import os
import sys
import time

from Cerebrum import Database,Errors

class LT(object):
    """..."""

    def __init__(self, db):
        self.db = db

    def GetSteder(self):
        qry = """
SELECT
  fakultetnr, instituttnr, gruppenr,
  forkstednavn, NVL(stednavnfullt, stednavn), akronym,
  stedpostboks,
  fakultetnr_for_org_sted, instituttnr_for_org_sted, gruppenr_for_org_sted,
  opprettetmerke_for_oppf_i_kat, telefonnr,
  adrtypekode_besok_adr, adresselinje1_besok_adr, adresselinje2_besok_adr,
  poststednr_besok_adr, poststednavn_besok_adr, landnavn_besok_adr,
  adrtypekode_intern_adr, adresselinje1_intern_adr, adresselinje2_intern_adr,
  poststednr_intern_adr, poststednavn_intern_adr, landnavn_intern_adr,
  adrtypekode_alternativ_adr, adresselinje1_alternativ_adr,
  adresselinje2_alternativ_adr, poststednr_alternativ_adr,
  poststednavn_alternativ_adr, landnavn_alternativ_adr, innvalgnr, linjenr
FROM lt.sted
WHERE
  dato_nedlagt > sysdate
ORDER BY fakultetnr, instituttnr, gruppenr"""
        return (self._get_cols(qry), self.db.query(qry))

    def GetStedKomm(self, fak, inst, gr):
        qry = """SELECT kommtypekode, telefonnr, kommnrverdi
FROM lt.stedkomm
WHERE
  fakultetnr=:fak AND
  instituttnr=:inst AND
  gruppenr=:gr AND
  kommtypekode IN ('FAX', 'TLF', 'EPOST', 'TLFUTL', 'URL')
ORDER BY tlfpreftegn"""
        return (self._get_cols(qry),
                self.db.query(qry, {'fak': fak, 'inst': inst, 'gr': gr}))

    def GetTilsettinger(self):
        qry = """SELECT distinct fodtdag, fodtmnd, fodtar, personnr,
	       fakultetnr_utgift, instituttnr_utgift, gruppenr_utgift,
               stilnr, stillingkodenr_beregnet_sist, prosent_tilsetting,
               TO_CHAR(dato_fra, 'YYYYMMDD'), TO_CHAR(dato_til, 'YYYYMMDD')
            FROM lt.tilsetting
	    WHERE NVL(dato_til, SYSDATE) > SYSDATE"""
        return (self._get_cols(qry), self.db.query(qry))

    def GetTitler(self):
        # skode2tittel hash'en har bare med den nyeste
        qry = """SELECT stillingkodenr, tittel, univstkatkode
        FROM lt.stillingskode ORDER BY dato_fra"""
        return (self._get_cols(qry), self.db.query(qry))

    def GetLonnsPosteringer(self, tid):
        qry = """SELECT belopskodenr
        FROM lt.belkodespesielle WHERE belkodeomradekode='LT35UREG' """
        koder = [str(k['belopskodenr']) for k in self.db.query(qry)]

        qry = ("""SELECT TO_CHAR(dato_oppgjor, 'YYYYMMDD'), p.fodtdag, p.fodtmnd, p.fodtar, p.personnr, 
               fakultetnr_kontering, instituttnr_kontering, gruppenr_kontering 
            FROM lt.lonnspostering p, lt.delpostering d
	    WHERE p.posteringsnr=d.posteringsnr AND p.aarnr_termin=d.aarnr AND p.mndnr_termin=d.mndnr
               AND p.fodtdag=d.fodtdag AND p.fodtmnd=d.fodtmnd AND p.fodtar=d.fodtar AND p.personnr=d.personnr 
               AND dato_oppgjor > TO_DATE(%s, 'YYYYMMDD') AND (d.belopskodenr=""" % tid +
        " OR d.belopskodenr=".join(koder) + ")")
        return (self._get_cols(qry), self.db.query(qry))

    def GetPersonInfo(self, fodtdag, fodtmnd, fodtar, personnr):
        qry = """SELECT 
  navn, tittel_personlig, fakultetnr_for_lonnsslip,
  instituttnr_for_lonnsslip, gruppenr_for_lonnsslip,
  adresselinje1_privatadresse, adresselinje2_privatadresse,
  poststednr_privatadresse, poststednavn_privatadresse,
  landnavn_privatadresse, telefonnr_privattelefon
FROM 
  lt.person
WHERE
  fodtdag=:fodtdag AND fodtmnd=:fodtmnd AND fodtar=:fodtar AND personnr=:personnr"""
        return (self._get_cols(qry), self.db.query(qry, locals()))

    def GetTelefon(self, fodtdag, fodtmnd, fodtar, personnr):
        qry = """SELECT
  innvalgnr, linjenr 
FROM
  lt.arbstedtelefon
WHERE
  fodtdag=:fodtdag AND fodtmnd=:fodtmnd AND fodtar=:fodtar AND personnr=:personnr
ORDER BY tlfpreftegn"""
        return (self._get_cols(qry), self.db.query(qry, locals()))

    def GetKomm(self, fodtdag, fodtmnd, fodtar, personnr):
        qry = """SELECT
  kommtypekode, kommnrverdi, telefonnr 
FROM 
  lt.perskomm 
WHERE
  fodtdag=:fodtdag AND fodtmnd=:fodtmnd AND fodtar=:fodtar AND personnr=:personnr
ORDER BY tlfpreftegn"""
        return (self._get_cols(qry), self.db.query(qry, locals()))

    def GetHovedkategorier(self):
        qry = "SELECT univstkatkode, hovedkatkode FROM lt.univstkategori"
        return (self._get_cols(qry), self.db.query(qry))

    # TODO: Belongs in a separate file, and should consider using row description
    def _get_cols(self, sql):
        sql = re.sub(r"NVL\(stednavnfullt, stednavn\)", "stednavn", sql)
        sql = re.sub(r"TO_CHAR\(([^,]+),\s*'YYYYMMDD'\)", r'\1', sql)
        m = re.compile(r'^\s*SELECT\s*(DISTINCT)?(.*)FROM', re.DOTALL | re.IGNORECASE).match(sql)
        if m == None:
            raise InternalError, "Unreconginzable SQL!"
        return [cols.strip() for cols in m.group(2).split(",")]

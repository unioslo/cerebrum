#!/usr/bin/env python2.2

import re
import os
import sys
import time

from Cerebrum import Database,Errors

class FSPerson(object):
    """FSPerson klassen definerer et sett med metoder som kan
    benyttes for å hente ut informasjon om personer fra FS.  De fleste
    metodene returnerer en tuple med kolonnenavn fulgt av en typle med
    dbrows."""

    def __init__(self, db):
        self.db = db
        t = time.localtime()[0:2]
        if t[1] <= 6:
            self.sem = 'V'
        else:
            self.sem = 'H'
        self.YY = str(t[0])[2:]
        
    def GetKursFagpersonundsemester(self):
        qry = """
SELECT DISTINCT
       fp.fodselsdato, fp.personnr,
       p.etternavn, p.fornavn,
       fp.adrlin1_arbeide, fp.adrlin2_arbeide,
       fp.postnr_arbeide, fp.adrlin3_arbeide,
       fp.adresseland_arbeide,
       fp.telefonnr_arbeide, fp.telefonnr_fax_arb,
       p.telefonnr_hjemsted, fp.stillingstittel_engelsk,
       r.institusjonsnr, r.faknr, r.instituttnr, r.gruppenr
FROM fs.person p, fs.fagperson fp,
     fs.fagpersonundsemester r
WHERE r.fodselsdato = fp.fodselsdato and
      r.personnr = fp.personnr and
      fp.fodselsdato = p.fodselsdato and
      fp.personnr = p.personnr and
      %s
        """ % self.get_termin_aar()
        return (self._get_cols(qry), self.db.query(qry))

    def GetStudinfRegkort(self):
        qry = """SELECT DISTINCT
       r.fodselsdato, r.personnr,
       p.etternavn, p.fornavn,
       s.adrlin1_semadr,s.adrlin2_semadr,
       s.postnr_semadr, s.adrlin3_semadr,
       s.adresseland_semadr,
       p.adrlin1_hjemsted, p.adrlin2_hjemsted,
       p.postnr_hjemsted, p.adrlin3_hjemsted,
       p.adresseland_hjemsted,
       p.status_reserv_nettpubl
FROM fs.registerkort r, fs.student s, fs.person p, fs.studierett st
WHERE  r.fodselsdato=p.fodselsdato and
       p.fodselsdato=s.fodselsdato and
       r.personnr=p.personnr and
       p.personnr=s.personnr and
       r.fodselsdato=st.fodselsdato and
       r.personnr=st.personnr and
       st.opphortstudierettstatkode is null and
       st.status_privatist='N' and
       %s
    """ % self.get_termin_aar()
        return (self._get_cols(qry), self.db.query(qry))

    def GetStudinfNaaKlasse(self):
        qry = """
SELECT s.fodselsdato, s.personnr,
       p.etternavn, p.fornavn,
       s.adrlin1_semadr,s.adrlin2_semadr,
       s.postnr_semadr, s.adrlin3_semadr,
       s.adresseland_semadr,
       p.adrlin1_hjemsted, p.adrlin2_hjemsted,
       p.postnr_hjemsted, p.adrlin3_hjemsted,
       p.adresseland_hjemsted,
       p.status_reserv_nettpubl
FROM fs.student s, fs.person p, fs.studierett st, fs.naverende_klasse kl
WHERE  p.fodselsdato=s.fodselsdato and
       p.personnr=s.personnr and
       p.fodselsdato=st.fodselsdato and
       p.personnr=st.personnr and
       st.opphortstudierettstatkode is null and
       st.status_privatist='N' and
       kl.personnr = p.personnr and
       kl.fodselsdato = p.fodselsdato and
       (kl.kullkode = '%s-%s' or kl.kullkode = '%s%s')""" % (
            self.sem, self.YY, self.sem, self.YY)
        return (self._get_cols(qry), self.db.query(qry))

    def GetStudinfStudierett(self):
        qry = """
SELECT s.fodselsdato, s.personnr,
       p.etternavn, p.fornavn,
       s.adrlin1_semadr,s.adrlin2_semadr,
       s.postnr_semadr, s.adrlin3_semadr,
       s.adresseland_semadr,
       p.adrlin1_hjemsted, p.adrlin2_hjemsted,
       p.postnr_hjemsted, p.adrlin3_hjemsted,
       p.adresseland_hjemsted,
       p.status_reserv_nettpubl
FROM fs.student s, fs.person p, fs.studierett st
WHERE  p.fodselsdato=s.fodselsdato and
       p.personnr=s.personnr and
       p.fodselsdato=st.fodselsdato and
       p.personnr=st.personnr and
       st.opphortstudierettstatkode is null and
       st.status_privatist='N' and
       NVL(st.dato_tildelt,SYSDATE-365) > SYSDATE - 90"""
        return (self._get_cols(qry), self.db.query(qry))

    def GetStudinfEvuKurs(self):
        qry = """
SELECT d.fodselsdato, d.personnr,
       p.etternavn, p.fornavn,
       d.adrlin1_hjem, d.adrlin2_hjem,
       d.postnr_hjem, d.adrlin3_hjem,
       d.adresseland_hjem,
       p.adrlin1_hjemsted, p.adrlin2_hjemsted,
       p.postnr_hjemsted, p.adrlin3_hjemsted,
       p.adresseland_hjemsted,
       p.status_reserv_nettpubl
FROM fs.deltaker d, fs.person p, fs.kursdeltakelse kd, fs.etterutdkurs ek
WHERE  p.fodselsdato=d.fodselsdato and
       p.personnr=d.personnr and
       d.deltakernr=kd.deltakernr and
       kd.etterutdkurskode = ek.etterutdkurskode and
       kd.kurstidsangivelsekode = ek.kurstidsangivelsekode and
       NVL(ek.dato_fra, SYSDATE+1) < SYSDATE + 14 and
       ek.dato_til > SYSDATE - 14"""
        return (self._get_cols(qry), self.db.query(qry))
 
    def get_termin_aar(self, only_current=0):
        yr, mon, md = t = time.localtime()[0:3]
        if mon <= 6:
            # Months January - June == Spring semester
            current = "(r.terminkode LIKE 'V_R' AND r.arstall=%s)\n" % yr;
            if only_current or mon >= 3 or (mon == 2 and md > 15):
                return current
            return "(%s OR (r.terminkode LIKE 'H_ST' AND r.arstall=%d))\n" % (
                current, yr-1)
        # Months July - December == Autumn semester
        current = "(r.terminkode LIKE 'H_ST' AND r.arstall=%d)\n" % yr
        if only_current or mon >= 10 or (mon == 9 and md > 15):
            return current
        return "(%s OR (r.terminkode LIKE 'V_R' AND r.arstall=%d))\n" % (current, yr)
    
    # TODO: Belongs in a separate file, and should consider using row description
    def _get_cols(self, sql):
        m = re.compile(r'^\s*SELECT\s*(DISTINCT)?(.*)FROM', re.DOTALL | re.IGNORECASE).match(sql)
        if m == None:
            raise InternalError, "Unreconginzable SQL!"
        return [cols.strip() for cols in m.group(2).split(",")]

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

from Cerebrum.modules.no.uio.access_FS import FS

class HistFS(FS):
    """FS klassen definerer et sett med metoder som kan benyttes for å
    hente ut informasjon om personer og OU-er fra FS. De fleste
    metodene returnerer en tuple med kolonnenavn fulgt av en tuple med
    dbrows."""

################################################################
#	Aktive studenter				       #
################################################################	

    def GetHistStudent(self):
        """Denne metoden henter data om aktive studenter ved HiST."""

        qry = """
SELECT DISTINCT
      p.fodselsdato, p.personnr, p.fornavn, p.etternavn, p.kjonn,
      p.adrlin1_hjemsted, p.adrlin2_hjemsted,p.postnr_hjemsted,
      p.adrlin3_hjemsted, p.adresseland_hjemsted, s.studentnr_tildelt,
      sp.studieprogramkode, sp.faknr_studieansv, sp.instituttnr_studieansv,
      sp.gruppenr_studieansv, sk.kullkode, nk.studieretningkode
FROM fs.person p, fs.studieprogram sp, fs.naverende_klasse nk,
     fs.studierett st, fs.studiekull sk, fs.klasse kl, fs.student s
WHERE nk.studieprogramkode = sk.studieprogramkode AND
      p.fodselsdato = nk.fodselsdato AND
      p.personnr = nk.personnr AND
      p.fodselsdato=s.fodselsdato AND
      p.personnr=s.personnr AND
      p.personnr= st.personnr AND
      p.fodselsdato=st.fodselsdato AND
      st.opphortstudierettstatkode is NULL AND
      nk.kullkode = sk.kullkode AND
      sp.studieprogramkode = sk.studieprogramkode AND
      sk.status_aktiv='J' AND
      nk.studieprogramkode = kl.studieprogramkode AND
      nk.klassekode = kl.klassekode AND
      nk.studieretningkode = kl.studieretningkode AND
      nk.kullkode = kl.kullkode AND
      %s """ %(self.is_alive())
	
	return (self._get_cols(qry), self.db.query(qry))

################################################################
#	Studieprogrammer				       #
################################################################	

    def GetStudieproginf(self):
        """For hvert definerte studieprogram henter vi 
        informasjon om utd_plan og eier samt studieprogkode"""
        qry = """

SELECT studieprogramkode, faknr_studieansv,
instituttnr_studieansv, gruppenr_studieansv, studienivakode
FROM fs.studieprogram
"""

# Fjerner dette for nå. Skal tilbake når HiST har ryddet opp.
# WHERE status_utgatt = 'N'

        return (self._get_cols(qry), self.db.query(qry))


##################################################################
# Mer studieinformasjon - testsøk for eksamensmeldinger	         #
##################################################################

    def GetAlleEksamensmeldinger(self, institusjonsnr=0):
	"""Hent data om eksamensmeldinger for alle studenter
           på HiST. Dette er en test-versjon av søket"""
	aar = time.localtime()[0:1]
	qry = """
SELECT p.fodselsdato, p.personnr, e.emnekode, e.arstall, 
       e.manednr, e.studieprogramkode
FROM fs.person p, fs.eksamensmelding e
WHERE p.fodselsdato=e.fodselsdato AND
      p.personnr=e.personnr AND
      e.arstall=%s 
      AND %s
ORDER BY fodselsdato, personnr
      """ %(aar[0],self.is_alive())                            
      	return (self._get_cols(qry), self.db.query(qry))



##################################################################
# Metoder for OU-er:
##################################################################


    def GetAlleOUer(self, institusjonsnr=0):
        """Hent data om stedskoder registrert i FS"""
        qry = """
SELECT DISTINCT
   faknr, instituttnr, gruppenr, stedakronym, stednavn_bokmal,
   faknr_org_under, instituttnr_org_under, gruppenr_org_under,
   adrlin1, adrlin2, postnr, telefonnr, faxnr,
   adrlin1_besok, adrlin2_besok, postnr_besok, url,
   bibsysbeststedkode
FROM fs.sted
WHERE institusjonsnr='%s'
	 """ % institusjonsnr

##################################################################
# Hjelpemetoder  
##################################################################

    def is_alive(self):	
	return "NVL(p.status_dod, 'N') = 'N'\n"








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
      nk.kullkode = kl.kullkode"""

        return (self._get_cols(qry), self.db.query(qry))


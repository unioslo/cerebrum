# -*- coding: utf-8 -*-
#
# Copyright 2003-2022 University of Oslo, Norway
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
"""
This module contains utilities for Fronter XML generation.

NB! This module is used by other institutions as well. Be careful with
shuffling the functionality around.
"""
from __future__ import unicode_literals

import re
import six


def UE2KursID(kurstype, *rest):  # noqa: N802
    """Lag ureg2000-spesifikk 'kurs-ID' av primærnøkkelen til en
    undervisningsenhet, et EVU-kurs eller et kull.  Denne kurs-IDen forblir
    uforandret så lenge kurset pågår; den endres altså ikke når man
    f.eks. kommer til et nytt semester.

    Første argument angir hvilken type FS-entitet de resterende argumentene
    stammer fra; enten 'KURS' (for undervisningsenhet), 'EVU' (for EVU-kurs),
    eller 'KULL' (for kull).
    """

    kurstype = kurstype.lower()
    if kurstype == 'evu':
        if len(rest) != 2:
            raise ValueError(
                "ERROR: EVU-kurs skal identifiseres av 2 felter, "
                "ikke <%s>" % ">, <".join(rest))
        # EVU-kurs er greie; de identifiseres unikt ved to
        # fritekstfelter; kurskode og tidsangivelse, og er modellert i
        # FS uavhengig av semester-inndeling.
        rest = list(rest)
        rest.insert(0, kurstype)
        return fields2key(*rest)

    elif kurstype == 'kull':
        if len(rest) != 3:
            raise ValueError("ERROR: Kull skal alltid identifiseres av 3 "
                             "felter, ikke <%s>" % ">, <".join(rest))
        rest = list(rest)
        rest.insert(0, kurstype)
        return fields2key(*rest)

    elif kurstype != 'kurs':
        raise ValueError("ERROR: Ukjent kurstype <%s> (%s)" % (kurstype, rest))

    # Vi vet her at $kurstype er 'KURS', og vet dermed også hvilke
    # elementer som er med i *rest:
    if len(rest) != 6:
        raise ValueError(
            "ERROR: Undervisningsenheter skal identifiseres av 6 "
            "felter, ikke <%s>" % ">, <".join(rest))

    instnr, emnekode, versjon, termk, aar, termnr = rest
    termnr = int(termnr)
    aar = int(aar)
    tmp_termk = re.sub('[^a-zA-Z0-9]', '_', termk).lower()
    # Finn $termk og $aar for ($termnr - 1) semestere siden:
    if tmp_termk == 'h_st':
        if (termnr % 2) == 1:
            termk = 'høst'
        else:
            termk = 'vår'
        aar -= int((termnr - 1) / 2)
    elif tmp_termk == 'v_r':
        if (termnr % 2) == 1:
            termk = 'vår'
        else:
            termk = 'høst'
        aar -= int(termnr / 2)
    else:
        # Vi krysser fingrene og håper at det aldri vil benyttes andre
        # verdier for $termk enn 'vår' og 'høst', da det i så fall vil
        # bli vanskelig å vite hvilket semester det var "for 2
        # semestere siden".
        raise ValueError(
            "ERROR: Unknown terminkode <%s> for emnekode <%s>." % (termk,
                                                                   emnekode))

    # $termnr er ikke del av den returnerte strengen.  Vi har benyttet
    # $termnr for å beregne $termk og $aar ved $termnr == 1; det er
    # altså implisitt i kurs-IDen at $termnr er lik 1 (og dermed
    # unødvendig å ta med).
    return fields2key(kurstype, instnr, emnekode, versjon, termk, aar)


def fields2key(*fields):
    """Create a key for internal fronter usage.

    We have a number of entities that have to be identified. They all have
    logical 'fields' comprising their IDs. Fields are separated by ':' and are
    all lowercase. This function enforces this restriction.

    @param fields:
      An unspecified number of elements that are joined to make a key. ':' is
      the separator. __str__ is called on each key before joining. The result
      is always lowercased.
    @param fields: tuple
    """

    return (":".join([six.text_type(x) for x in fields])).lower()


def str2key(s):
    """L{fields2key}'s counterpart for strings.

    @param s:
      String containing the key
    @type s: basestring
    """

    return s.lower()


def key2fields(key):
    """The opposite operation of L{fields2key}.

    The result is lowercased.

    @param key:
      Key (constructed by L{fields2key} or L{str2key}) to convert to
      fields. ':' is the separator. The resulting fields are lowercased.
    @type key: basestring
    """
    return key.lower().split(":")

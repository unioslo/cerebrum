#!/usr/bin/env python2.2
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

import cerebrum_path

import re
import os
import sys
import getopt
import cereconf
import time
import string

from Cerebrum.modules.no.uio.access_LT import LT
from Cerebrum import Database,Errors
from Cerebrum.Utils import XMLHelper

def get_sted_info(outfile):
    f=open(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")

    cols, steder = LT.GetSteder();
    for s in steder:
        f.write(xml.xmlify_dbrow(s, xml.conv_colnames(cols), 'sted', 0) + "\n")
        cols2, komm = LT.GetStedKomm(s['fakultetnr'], s['instituttnr'], s['gruppenr'])
        for k in komm:
            f.write(xml.xmlify_dbrow(k, xml.conv_colnames(cols2), 'komm') + "\n")
        f.write("</sted>\n")
    f.write("</data>\n")

def get_person_info(outfile):
    """Henter info om alle personer i LT som er av interesse.
    Ettersom opplysningene samles fra flere datakilder, lagres de
    først i en dict persondta"""

    # Lag mapping fra stillingskodenr til titel (ala overing)
    skode2tittel = {}
    for t in LT.GetTitler()[1]:
        skode2tittel[t['stillingkodenr']] = (t['tittel'], t['univstkatkode'])

    # Lag mapping fra univstkatkode til hovedkatkode (VIT etc.)
    kate2hovedkat = {}
    for t in LT.GetHovedkategorier()[1]:
        kate2hovedkat[t['univstkatkode']] = t['hovedkatkode']

    # Hent alle aktive tilsetninger
    tilscols, tils = LT.GetTilsettinger()
    persondta = {}
    for t in tils:
        key = '-'.join(["%i" % x for x in [t['fodtdag'], t['fodtmnd'],
                                           t['fodtar'], t['personnr']]])
        if not persondta.has_key(key):
            persondta[key] = {}
        persondta[key]['tils'] = persondta[key].get('tils', []) + [t]

    # Hent alle reservasjoner
    rescols, res = LT.GetReservasjoner()
    reservasjoner = {}
    for r in res:
        key = '-'.join(["%i" % x for x in [r['fodtdag'], r['fodtmnd'],
                                           r['fodtar'], r['personnr']]])
        if not reservasjoner.has_key(key):
            reservasjoner[key] = {}
        reservasjoner[key]['res'] = reservasjoner[key].get('res', []) + [r]

    # Hent alle lønnsposteringer siste 180 dager.
    #
    # Tidligere cachet vi disse dataene slik at vi kunne søke over
    # færre dager, men det ser ikke ut til å være nødvendig da søket
    # ikke tar mer enn ca et minutt
    tid = time.strftime("%Y%m%d", time.gmtime(time.time() - (3600*24*180)))
    lonnscols, lonnspost = LT.GetLonnsPosteringer(tid)
    for lp in lonnspost:
        key = '-'.join(["%i" % x for x in [lp['fodtdag'], lp['fodtmnd'],
                                           lp['fodtar'], lp['personnr']]])
        sko = "%02d%02d%02d" % (lp['fakultetnr_kontering'],
                                lp['instituttnr_kontering'],
                                lp['gruppenr_kontering'])
        persondta.setdefault(key, {}).setdefault('bil', []).append(sko)

    gcols, gjester = LT.GetGjester()
    for g in gjester:
        key = '-'.join(["%i" % x for x in [g['fodtdag'], g['fodtmnd'],
                                           g['fodtar'], g['personnr']]])
        sko = "%02d%02d%02d" % (g['fakultetnr'],
                                g['instituttnr'],
                                g['gruppenr'])
        if not persondta.has_key(key):
            persondta[key] = {}
        # fi

        persondta[key]['gjest'] = persondta[key].get('gjest', []) + [g]
    # od

    # Skriv ut informasjon om de personer vi allerede har hentet, og
    # hent noe tillegs informasjon om de
    f=open(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")
    for p in persondta.keys():
        fodtdag, fodtmnd, fodtar, personnr = p.split('-')
        picols, pi = LT.GetPersonInfo(fodtdag, fodtmnd, fodtar, personnr)
        f.write(
            xml.xmlify_dbrow(pi[0],  xml.conv_colnames(picols), 'person', 0,
                             extra_attr={'fodtdag': fodtdag, 'fodtmnd':fodtmnd,
                                         'fodtar':fodtar, 'personnr': personnr}
                             ) + "\n")
        tlfcols, tlf = LT.GetArbTelefon(fodtdag, fodtmnd, fodtar, personnr)
        for t in tlf:
            f.write("  "+xml.xmlify_dbrow(
                t, xml.conv_colnames(tlfcols), 'arbtlf') + "\n")

        kcols, komm = LT.GetPersKomm(fodtdag, fodtmnd, fodtar, personnr)
        for k in komm:
            f.write("  "+xml.xmlify_dbrow(
                k,  xml.conv_colnames(kcols), 'komm') + "\n")

        rcols, roller = LT.GetPersonRoller(fodtdag, fodtmnd, fodtar, personnr)
        for r in roller:
            f.write("  "+xml.xmlify_dbrow(
                r, xml.conv_colnames(rcols), 'rolle') +"\n")

        for t in persondta[p].get('tils', ()):
            # Unfortunately the oracle driver returns
            # to_char(dato_fra,'yyyymmdd') as key for rows, so we use
            # indexes here :-(
            attr = " ".join(["%s=%s" % (tilscols[i], xml.escape_xml_attr(t[i]))
                             for i in (4,5,6,7,8,9,10, )])
            if t['stillingkodenr_beregnet_sist'] is not None:
                sk = skode2tittel[t['stillingkodenr_beregnet_sist']]
                attr += ' hovedkat=%s' % xml.escape_xml_attr(
                    kate2hovedkat[sk[1]])
                attr += ' tittel=%s' % xml.escape_xml_attr(sk[0])
                f.write("  <tils "+attr+"/>\n")

        if reservasjoner.has_key(p): 
            for r in reservasjoner[p].get('res', ()):
                attr = " ".join(["%s=%s" % (rescols[i], xml.escape_xml_attr(r[i]))
                                 for i in (4,5,6, )])
                f.write("  <res "+attr+"/>\n")
            
        prev = ''
        persondta[p].get('bil', []).sort()
        for t in persondta[p].get('bil', []):
            if t == prev:
                continue
            f.write('  <bilag stedkode="%s"' % t + "/>\n")
            prev = t
        for g in persondta[p].get('gjest', ()):
            attr = string.join(["%s=%s" % (gcols[i], xml.escape_xml_attr(g[i]))
                                for i in range(len(gcols))],
                               " ")
            f.write("  <gjest "+attr+"/>\n")
        # od
 
        f.write("</person>\n")

    f.write("</data>\n")

def usage(exitcode=0):
    print """Usage: -s sid -u uname [options]
    -v | --verbose : turn up verbosity
    -s | --sid sid: sid to connect with
    -u uname: username to connect with
    --sted-file file: filename to write sted info to
    --person-file file: filename to write person info to"""
    sys.exit(exitcode)

def main():
    global LT, xml, verbose

    personfile = None
    stedfile = None
    sid = None
    user = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'vs:u:',
                                   ['verbose', 'sid=', 'sted-file=', 'person-file='])
    except getopt.GetoptError:
        usage(1)
    for opt, val in opts:
        if opt in ('-v', '--verbose'):
            pass  # not currently used
        elif opt in ('-s', '--sid'):
            sid = val
        elif opt in ('-u',):
            user = val
        elif opt in ('--sted-file',):
            stedfile = val
        elif opt in ('--person-file',):
            personfile = val
    if user is None or sid is None:
        usage(1)
    db = Database.connect(user=user, service=sid, DB_driver='Oracle')
    LT = LT(db)
    xml = XMLHelper()

    if stedfile is not None:
        get_sted_info(stedfile)
    if personfile is not None:
        get_person_info(personfile)

if __name__ == '__main__':
    main()

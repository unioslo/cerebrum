#!/usr/bin/env python
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
from Cerebrum.Utils import AtomicFileWriter
from Cerebrum.extlib import xmlprinter
from Cerebrum.Utils import Factory


def get_sted_info(outfile):
    f = AtomicFileWriter(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")

    steder = LT.GetSteder()
    for s in steder:
        column_names = LT.get_column_names(s)
        f.write(xml.xmlify_dbrow(s, xml.conv_colnames(column_names), 'sted', 0) + "\n")
        komm = LT.GetStedKomm(s['fakultetnr'], s['instituttnr'], s['gruppenr'])
        for k in komm:
            column_names2 = LT.get_column_names(k)
            f.write(xml.xmlify_dbrow(k, xml.conv_colnames(column_names2), 'komm') + "\n")
        # od
        f.write("</sted>\n")
    # od 
    f.write("</data>\n")
    f.close()
# end get_sted_info



def get_person_info(outfile):
    """
    Henter info om alle personer i LT som er av interesse.  Ettersom
    opplysningene samles fra flere datakilder, lagres de først i en dict
    persondta
    """

    # Lag mapping fra stillingskodenr til titel (ala overing)
    skode2tittel = {}
    for t in LT.GetTitler():
        skode2tittel[t['stillingkodenr']] = (t['tittel'], t['univstkatkode'])
    # od

    # Lag mapping fra univstkatkode til hovedkatkode (VIT etc.)
    kate2hovedkat = {}
    for t in LT.GetHovedkategorier():
        kate2hovedkat[t['univstkatkode']] = t['hovedkatkode']
    # od

    # Hent alle aktive tilsetninger
    tils = LT.GetTilsettinger()
    persondta = {}
    for t in tils:
        key = '-'.join(["%i" % x for x in [t['fodtdag'], t['fodtmnd'],
                                           t['fodtar'], t['personnr']]])
        if not persondta.has_key(key):
            persondta[key] = {}
        # fi

        persondta[key]['tils'] = persondta[key].get('tils', []) + [t]
    # od

    # Hent alle reservasjoner
    res = LT.GetReservasjoner()
    reservasjoner = {}
    for r in res:
        key = '-'.join(["%i" % x for x in [r['fodtdag'], r['fodtmnd'],
                                           r['fodtar'], r['personnr']]])
        if not reservasjoner.has_key(key):
            reservasjoner[key] = {}
        # fi

        reservasjoner[key]['res'] = reservasjoner[key].get('res', []) + [r]
    # od

    # Hent alle lønnsposteringer siste 30 dager.
    #
    # Tidligere cachet vi disse dataene slik at vi kunne søke over
    # færre dager, men det ser ikke ut til å være nødvendig da søket
    # ikke tar mer enn ca et minutt
    tid = time.strftime("%Y%m%d", time.gmtime(time.time() - (3600*24*30)))
    lonnspost = LT.GetLonnsPosteringer(tid)
    for lp in lonnspost:
        key = '-'.join(["%i" % x for x in [lp['fodtdag'], lp['fodtmnd'],
                                           lp['fodtar'], lp['personnr']]])
        if not persondta.has_key(key):
            persondta[key] = {}
        # fi

        persondta[key]['bil'] = persondta[key].get('bil', []) + [lp]
    # od

    gjester = LT.GetGjester()
    for g in gjester:
        key = '-'.join(["%i" % x for x in [g['fodtdag'], g['fodtmnd'],
                                           g['fodtar'], g['personnr']]])
        if not persondta.has_key(key):
            persondta[key] = {}
        # fi

        persondta[key]['gjest'] = persondta[key].get('gjest', []) + [g]
    # od

    permisjoner = LT.GetPermisjoner()
    for p in permisjoner:
        key = string.join([ str(x)
                            for x in 
                              [p["fodtdag"], p["fodtmnd"],
                               p["fodtar"], p["personnr"]]
                            ], "-")
        if not persondta.has_key(key):
            persondta[key] = {}
        # fi

        if not persondta[key].has_key("permisjon"):
            persondta[key]["permisjon"] = {}
        # fi

        # Since LT.Permisjon(key, tilsnr) is the PK, this assignment will
        # never overwrite any information
        pkey = str(p.tilsnr)
        if not persondta[key]["permisjon"].has_key(pkey):
            persondta[key]["permisjon"][pkey] = []
        # fi
        
        persondta[key]["permisjon"][pkey].append(p)
    # od


    # Skriv ut informasjon om de personer vi allerede har hentet, og
    # hent noe tilleggsinformasjon om dem
    f = AtomicFileWriter(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")
    for p in persondta.keys():
        fodtdag, fodtmnd, fodtar, personnr = p.split('-')
        pi = LT.GetPersonInfo(fodtdag, fodtmnd, fodtar, personnr)
        picols = LT.get_column_names(pi)
        f.write(
            xml.xmlify_dbrow(pi[0],  xml.conv_colnames(picols), 'person', 0,
                             extra_attr={'fodtdag': fodtdag, 'fodtmnd':fodtmnd,
                                         'fodtar':fodtar, 'personnr': personnr}
                             ) + "\n")
        tlf = LT.GetArbTelefon(fodtdag, fodtmnd, fodtar, personnr)
        tlfcols = LT.get_column_names(tlf)
        for t in tlf:
            f.write("  "+xml.xmlify_dbrow(
                t, xml.conv_colnames(tlfcols), 'arbtlf') + "\n")
        # od

        komm = LT.GetPersKomm(fodtdag, fodtmnd, fodtar, personnr)
        kcols = LT.get_column_names(komm)
        for k in komm:
            f.write("  "+xml.xmlify_dbrow(
                k,  xml.conv_colnames(kcols), 'komm') + "\n")
        # od

        roller = LT.GetPersonRoller(fodtdag, fodtmnd, fodtar, personnr)
        rcols = LT.get_column_names(roller)
        for r in roller:
            f.write("  "+xml.xmlify_dbrow(
                r, xml.conv_colnames(rcols), 'rolle') +"\n")
        # od

        permisjoner = persondta[p].get("permisjon", {})
        for t in persondta[p].get('tils', ()):
            attr = string.join(["%s=%s" % (name,
                                           xml.escape_xml_attr(t[name]))
                                for name in
                                ["fakultetnr_utgift",
                                 "instituttnr_utgift",
                                 "gruppenr_utgift",
                                 "prosent_tilsetting",
                                 "dato_fra", "dato_til",
                                 "tilsnr"]])
            key = "stillingkodenr_beregnet_sist"
            attr = attr + (" %s=%s " % (key,
                                        xml.escape_xml_attr(int(t[key])))) 
            
            sk = skode2tittel[t['stillingkodenr_beregnet_sist']]
            attr += ' hovedkat=%s' % xml.escape_xml_attr(
                                       kate2hovedkat[sk[1]])
            attr += ' tittel=%s' % xml.escape_xml_attr(sk[0])
            f.write("  <tils " + attr + " >\n" )

            formatted_leaves = output_leaves(t, permisjoner)
            for leave in formatted_leaves:
                pattr = string.join( ["%s=%s" %
                                      (x[0], xml.escape_xml_attr(x[1]))
                                      for x in leave] )
                f.write("    <permisjon " + pattr + " />\n")
            # od
                
            f.write( "  </tils>\n" )
        # od

        if reservasjoner.has_key(p): 
            for r in reservasjoner[p].get('res', ()):
                attr = string.join(["%s=%s" % (name,
                                               xml.escape_xml_attr(r[name]))
                                    for name in
                                      ["katalogkode",
                                       "felttypekode",
                                       "resnivakode",]])
                f.write("  <res "+attr+"/>\n")
            # od
        # fi
            
        prev = None
        # Order by 'stedkode', then by reverse date
        persondta[p].get('bil', []).sort(lambda x, y:
                                         cmp(make_key(x), make_key(y))
                                         or cmp(y["dato_oppgjor"],
                                                x["dato_oppgjor"]))
        for t in persondta[p].get('bil', []):
            if make_key(t) == make_key(prev):
                continue
            # fi

            attr = string.join(["%s=%s" % (name,
                                           xml.escape_xml_attr(t[name]))
                                for name in
                                  ["dato_oppgjor",
                                   "fakultetnr_kontering",
                                   "instituttnr_kontering",
                                   "gruppenr_kontering",]])
            f.write("  <bilag " + attr + "/>\n")
            prev = t
        # od

        for g in persondta[p].get('gjest', ()):
            attr = string.join(["%s=%s" % (name,
                                           xml.escape_xml_attr(g[name]))
                                for name in
                                  ["fakultetnr",
                                   "instituttnr",
                                   "gruppenr",
                                   "gjestetypekode",
                                   "dato_fra",
                                   "dato_til",]]) 
            f.write("  <gjest "+attr+"/>\n")
        # od
 
        f.write("</person>\n")

    f.write("</data>\n")
    f.close()
# end get_person_info



def output_leaves( tilsetting, permisjoner ):
    """
    Returns a sequence S of subsequences Q, where each Q contains pairs P of
    the form (<name>, <value>):

    [ [ ('permisjonskode', '13'), ('dato_fra', '20031212'), ... ],
      [ ('permisjonskode', '46'), ('dato_fra', '20040107'), ... ],
    ]
    """

    accumulator = []

    key = str(tilsetting.tilsnr)
    for permisjon in permisjoner.get(key, []):
        result = [ (x, getattr(permisjon, x)) for x in
                   [ "permarsakkode", "dato_fra", "dato_til",
                     "prosent_permisjon", "lonstatuskode" ] ]
        accumulator.append( result )
    # od

    return accumulator
# end 



def make_key(db_row):
    if db_row is None:
        return ''
    # fi
    
    return "%02d%02d%02d" % (db_row['fakultetnr_kontering'],
                             db_row['instituttnr_kontering'],
                             db_row['gruppenr_kontering'])
# end 



def get_fnr_update_info(filename):
    """
    Fetch updates in Norwegian sosial security number (fødselsnummer) from
    LT and generate a suitable xml dump containing the changes.
    """

    output_stream = AtomicFileWriter(filename, "w")
    writer = xmlprinter.xmlprinter(output_stream,
                                   indent_level = 2,
                                   # Output is for humans too
                                   data_mode = True,
                                   input_encoding = 'latin1')
    writer.startDocument(encoding = "iso8859-1")

    db = Factory.get("Database")()
    const = Factory.get("Constants")(db)
    writer.startElement("data", {"source_system" : str(const.system_lt)})
    
    for row in LT.GetFnrEndringer():
        # Make the format resemble the corresponding FS output as close as
        # possible.
        attributes = { "type" : str(const.externalid_fodselsnr), 
                       "new"  : "%02d%02d%02d%05d" % (row["fodtdag_ble_til"],
                                                      row["fodtmnd_ble_til"],
                                                      row["fodtar_ble_til"],
                                                      row["personnr_ble_til"]),
                       "old"  : "%02d%02d%02d%05d" % (row["fodtdag_kom_fra"],
                                                      row["fodtmnd_kom_fra"],
                                                      row["fodtar_kom_fra"],
                                                      row["personnr_kom_fra"]),
                       "date" : str(row["dato_endret"]),
                     }
        
        writer.emptyElement("external_id", attributes)
    # od

    writer.endElement("data")
    writer.endDocument()
    output_stream.close()
# end get_fnr_update_info



def usage(exitcode=0):
    print """Usage: -s sid -u uname [options]
    -v | --verbose : turn up verbosity
    -s | --sid sid: sid to connect with
    -u uname: username to connect with
    --sted-file file: filename to write sted info to
    --person-file file: filename to write person info to
    -f | --fnr-update <filename> : generate fnr updates from LT
    """
    sys.exit(exitcode)

def main():
    global LT, xml, verbose

    personfile = None
    stedfile = None
    sid = None
    user = None
    fnr_update = None
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'vs:u:f:',
                                   ['verbose', 'sid=', 'sted-file=',
                                    'person-file=',
                                    'fnr-update='])
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
        elif opt in ('-f', '--fnr-update'):
            fnr_update = val
        # fi
    # od
            
    if user is None or sid is None:
        usage(1)

    db = Database.connect(user=user, service=sid, DB_driver='Oracle')
    LT = LT(db)
    xml = XMLHelper()

    if stedfile is not None:
        get_sted_info(stedfile)
    # fi
    
    if personfile is not None:
        get_person_info(personfile)
    # fi

    if fnr_update is not None:
        get_fnr_update_info(fnr_update)
    # fi
# end main





if __name__ == '__main__':
    main()
# fi

# arch-tag: 24f6639e-0c42-4fb1-bb4a-a53f3d76d532

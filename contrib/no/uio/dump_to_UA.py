#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Generate dump files for exporting to UA.  The files contains
# information about people known in Cerebrum.  Documentation for the
# dump format apears to be non-existent.

import getopt
import sys
import time
import os

import cereconf
import pprint
from Cerebrum import Person
from Cerebrum.Utils import Factory
from Cerebrum.Constants import _PersonAffiliationCode, _PersonAffStatusCode, \
     _SpreadCode

db = Factory.get('Database')()
const = Factory.get('Constants')(db)
debug = 0
pp = pprint.PrettyPrinter(indent=4)

# TODO: Move this class to Cerebrum.Utils
class ConstantMappings(object):
    def __init__(self, const):
        self.const = const
        
    def get_affiliation_mapping(self):
        ret = {}
        for c in dir(self.const):
            c2 = getattr(self.const, c)
            if isinstance(c2, _PersonAffiliationCode):
                ret[str(c2)] = {'': c2}
        for c in dir(self.const):
            c2 = getattr(self.const, c)
            if isinstance(c2, _PersonAffStatusCode):
                ret[str(c2.affiliation)][str(c2)] = c2
        return ret

    def get_spread_mapping(self):
        ret = {}
        for c in dir(self.const):
            c2 = getattr(self.const, c)
            if isinstance(c2, _SpreadCode):
                ret[str(c2)] = c2
        return ret

def dump_persons(out_dir, spread=None, affiliations=None):
    person = Person.Person(db)
    matches = {}
    if ((spread is not None and affiliations is not None) or
        (spread is None and affiliations is None)):
        print "Cannot set both or none of affiliations and spread"
        sys.exit(1)

    if spread is not None:
        for e in person.list_all_with_spread(int(spread)):
            matches[int(e['entity_id'])] = 1
    else:
        for tmp in affiliations:
            aff, statuses = tmp
            for p in person.list_affiliations(affiliation=aff):
                if isinstance(statuses, str) or int(p['status']) in statuses:
                    matches[int(p['person_id'])] = 1
    lines = []
    for id in matches.keys():
        person.clear()
        person.find(id)
        full_name = person.get_name(const.system_cached, const.name_full)
        first_name, last_name = full_name.split(" ", 1)
        fnr = person.get_external_id(id_type=const.externalid_fodselsnr)
        if len(fnr) > 0:
            fnr = fnr[0]['external_id']
        else:
            fnr = ''
        # TODO: Old script had a file adgkonv.dta to convert sko to adgsko
        lines.append(format_person({'systemnr': systemnr, 'korttype': korttype,
                                    'fnr': fnr, 'lname': last_name,
                                    'fname': first_name,
##                                  'arbsted': $sko,
##                                  'adgsko': $sko2sted{$sko},
##                                  'startdato': $start,
##                                  'sluttdato': $slutt,
##                                  'interntlf': $telefoner[0]
                                    }
                                   ))
    out = file("%s/uadata.new" % out_dir, 'w')
    lines.sort()
    for t in lines:
        out.write(t+"\n")
    out.close()
    
def format_person(dta):

## Format: 
## 0: fødselsnummer, 1: systemnummer, 2: korttype, 3: fornavn, 4: etternavn
## 5..10: adgnivå 1..6,  11: sit-bet-semesteravgift, 12: betalingsdato
## 13: startdato, 14: sluttdato, 15: privattlf, 16: interntlf, 
## 17: avdelingsnr, 18: arbeidssted, 19: studieniva,
## 20..23: tilhørighet hjemmeaddr[1..4], 24..27: semesteraddr[1..4])
## 28..29: Ukjent.

    felter = ['systemnr', 'korttype', 'fname', 'lname', 'adg1',
              'adg2', 'adg3', 'adg4', 'adg5', 'adg6', 'sistbetsem',
              'betdato', 'startdato', 'sluttdato', 'privtlf',
              'interntlf', 'avdnr', 'arbsted', 'tilhorighet',
              'hjemadr1', 'hjemadr2', 'hjemadr3', 'hjemadr4',
              'semadr1', 'semadr2', 'semadr3', 'semadr4']
    ret = ['%s%s' % (dta['fnr'], dta['systemnr'])]
    for f in felter:
        ret.append(dta.get(f, ''))
    ret.append('')
    ret.append('')
    return ";".join(ret)

def do_sillydiff(dirname, oldfile, newfile, outfile):
    old = ''
    try:
        oldin = file("%s/%s" % (dirname, oldfile))
        old = oldin.readline()
    except IOError:
        print "Warning, old file did not exist, assuming first run ever"
        pass
    newin = file("%s/%s" % (dirname, newfile))
    out = file("%s/%s" % (dirname, outfile), 'w')
    new = newin.readline()
    while 1:
        if len(new) == 0 or len(old) == 0:
            break
        if(old == new):
            new = newin.readline()
            old = oldin.readline()
            new.rstrip()
            old.rstrip()
            continue
        if old[0:11] == new[0:11]:
            # Lag endrings-record for denne personen. fnr, systemnr,
            # korttype, fname, lname skal altid med.
            olddta = old.split(";")
            newdta = new.split(";")
            gen = newdta[0:5]
            for i in range(5, len(olddta)):
                if olddta[i] != newdta[i]:
                    gen.append(newdta[i])
                else:
                    gen.append('#')
            out.write(";".join(gen)+"\n")
            new = newin.readline()
            old = oldin.readline()
            new.rstrip()
            old.rstrip()
            continue
        if old < new:
            # Denne ser ut til å oppdatere informasjon for personar som har 
            # slutta.  Viss sluttdato (14) er seinare enn i dag, vil sluttdato bli 
            # sett til i dag.  Andre felt enn 0-4 og 14 vert sett tomme.
            olddta = old.split(";")
            gen = olddta[0:4]
            for foo in range(25):
                gen.append("")
            if olddta[14] > today:
                gen[14] = today
            else:
                gen[14] = olddta[14]
            out.write(";".join(gen)+"\n")
            old = oldin.readline()
            old.rstrip()
        else:
            out.write(new)
            new = newin.readline()
            new.rstrip()
    if len(new):
	# Flere nye.  Oppdater som over.
        while 1:
            out.write(new)
            new = newin.readline()
            new.rstrip()
            if len(new) == 0:
                break
    if len(old):
	# Flere som har slutta.  Oppdater som over.
        while 1:
            olddta = old.split(";")
            gen = olddta[0:4]
            for foo in range(25):
                gen.append("")
            if olddta[14] > today:
                gen[14] = today
            else:
                gen[14] = olddta[14]
            out.write(";".join(gen)+"\n")
            old = oldin.readline()
            old.rstrip()
            if len(old) == 0:
                break
    out.close()

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'o:s:a:k:S:',
                                   ['out-dir=', 'spread=', 'affiliation=',
                                    'kort-type=', 'system-nr='])
    except getopt.GetoptError:
        usage(1)

    global korttype, systemnr
    affiliations = None
    out_dir = None
    spread = None
    korttype = None
    systemnr = None
    cm = ConstantMappings(const)
    aff_mapping = cm.get_affiliation_mapping()
    spread_mapping = cm.get_spread_mapping()
    #pp.pprint( aff_mapping)
    #pp.pprint( spread_mapping)
    for opt, val in opts:
        if opt in ('-o', '--out-dir'):
            out_dir = val
        elif opt in ('-s', '--spread'):
            spread = spread_mapping[val]
        elif opt in ('-k', '--kort-type'):
            korttype = val
        elif opt in ('-S', '--system-nr'):
            systemnr = val
        elif opt in ('-a', '--affiliation'):
            if affiliations is None:
                affiliations = []
            aff, status = val.split(":")
            tmp = []
            if status <> '':
                for s in status.split(","):
                    tmp.append(aff_mapping[aff][s])
                status = tmp
            affiliations.append((aff_mapping[aff][''], status))
    if korttype is None or systemnr is None:
        print "Must set korttype and systemnr"
        sys.exit(1)
    dump_persons(out_dir, spread, affiliations)
    do_sillydiff(out_dir, "uadata.old", "uadata.new",
                 "uadata.%s" % (time.strftime("%Y-%m-%d")))
    os.rename("%s/uadata.new" % out_dir, "%s/uadata.old" % out_dir)
    
def usage(exitcode=0):
    print """Usage: dump_to_UA.py [options]
    -o | --out-dir name: dump to this directory
    -s | --spread code:  dump all persons with this spread
    -S | --system-nr nr: systemnr (UA begrep)
    -k | --kort-type kt: kort type (UA begrep)
    -a | --affiliation aff: dump all persons with this affiliation.
       May be repeated.  Format:
       person_affiliation_code:comma_separated_person_aff_status_code.
       empty string after the colon may be ued to match any status_code.

    Example: dump_to_UA.py -o /tmp  -a MANUELL: -S 2 -k 'Tilsatt UiO'

    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()

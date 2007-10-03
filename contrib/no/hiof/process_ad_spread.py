#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2007 University of Oslo, Norway
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


"""Dette scriptet går gjennom alle personer som har spread til et av
HIOFs tre AD-domener.  Scriptet har noen oppgaver:

* Beregne home/profile-path/OU-plassering dersom slik verdi ikke er
  beregnet tidligere
* Oppdatere eksisterende verdi dersom tilknyttingsforhold e.l. er
  endret (dette er ikke implemetert enda, da en spec må skrives
  først).

Usage: process_AD.py [options]
-p fname : xml-fil med person informasjon
-s fname : xml-fil med studieprogram informasjon
"""

import getopt
import sys
import cPickle
import cerebrum_path
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.hiof import ADMappingRules
from Cerebrum.modules.xmlutils.GeneralXMLParser import GeneralXMLParser

db = Factory.get('Database')()
db.cl_init(change_program="process_ad")
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
ou = Factory.get('OU')(db)
person = Factory.get('Person')(db)

logger = Factory.get_logger("cronjob")

class StudieInfo(object):
    """Parse student-info."""

    def __init__(self, person_fname, stprog_fname):
        self._person_fname = person_fname
        self._stprog_fname = stprog_fname
        # Bruker lazy-initalizing av data-dictene slik at vi slipper å
        # parse XML-filen medmindre vi trenger å slå opp i den
        self.stdnr2stproginfo = None
        self.studieprog2sko = None
        
    def get_persons_studieprogrammer(self, stdnr):
        if self.stdnr2stproginfo is None:
            self.stdnr2stproginfo = self._parse_studinfo()
        return self.stdnr2stproginfo.get(stdnr)

    def get_studprog_sko(self, studieprog):
        if self.studieprog2sko is None:
            self.studieprog2sko = self._parse_studieprog()
        return self.studieprog2sko.get(studieprog)

    def _parse_studinfo(self):
        logger.debug("Parsing %s" % self._person_fname)
        stdnr2stproginfo = {}
        def got_aktiv(dta, elem_stack):
            entry = elem_stack[-1][-1]
            stdnr = entry['studentnr_tildelt']
            stdnr2stproginfo.setdefault(stdnr, []).append(entry)

        cfg = [(['data', 'person', 'aktiv'], got_aktiv)]
        GeneralXMLParser(cfg, self._person_fname)
        return stdnr2stproginfo

    def _parse_studieprog(self):
        logger.debug("Parsing %s" % self._stprog_fname)
        stprog2sko = {}
        def got_aktiv(dta, elem_stack):
            entry = elem_stack[-1][-1]
            sko = "%02i%02i%02i" % (int(entry['faknr_studieansv']),
                                    int(entry['instituttnr_studieansv']),
                                    int(entry['gruppenr_studieansv']))
            stprog2sko[entry['studieprogramkode']] = sko

        cfg = [(['data', 'studprog'], got_aktiv)]
        GeneralXMLParser(cfg, self._stprog_fname)
        return stprog2sko

class Job(object):
    """Oppdater profile_path, ou og homedir-path for kontoen dersom
    verdiene ikke allerede er satt """

    class CalcError(Exception):
        pass

    def __init__(self, student_info):
        self._student_info = student_info
        self.entity_id2profile_path = {}
        for row in ac.list_traits(co.trait_ad_profile_path):
            self.entity_id2profile_path[int(row['entity_id'])] = row['strval']
        logger.debug("Found %i profile-path traits" % len(self.entity_id2profile_path))

        self.entity_id2account_home = {}
        for row in ac.list_traits(co.trait_ad_homedir):
            self.entity_id2account_home[int(row['entity_id'])] = row['strval']
        logger.debug("Found %i home traits" % len(self.entity_id2account_home))

        self.entity_id2account_ou = {}
        for row in ac.list_traits(co.trait_ad_account_ou):
            self.entity_id2account_ou[int(row['entity_id'])] = row['strval']
        logger.debug("Found %i ou traits" % len(self.entity_id2account_ou))

        self._adm_rules = ADMappingRules.Adm()
        self._fag_rules = ADMappingRules.Fag()
        self._stud_rules = ADMappingRules.Student()

        self.process_spreads(co.spread_ad_account_fag,
                             co.spread_ad_account_adm,
                             co.spread_ad_account_stud)
            
    def process_spreads(self, *spreads):
        """Sjekk om ou, profile_path og home er satt for en bruker.
        Hvis ikke, beregn verdiene og populer som traits."""

        # Sjekk først om ou, profile_path og home er satt. Hvis ikke
        # skal de beregnes. Lag datastruktur slik at traits enkelt kan
        # settes.
        user_maps = {}
        for spread in spreads:
            logger.debug("Process accounts with spread=%s" % spread)
            for row in ac.list_account_home(home_spread=spread,
                                            account_spread=spread,
                                            filter_expired=True,
                                            include_nohome=True):
                entity_id = int(row['account_id'])
                # Ikke gjør noe hvis OU og profile_path allerede er satt
                #
                # TBD: Hva skal gjøres her hvis brukere blir flyttet
                # til annet domene? Det var først bestemt at brukere
                # ikke skulle flyttes, men så ble man enige om at det
                # skulle kunne skje likevel. Derfor må noe gjøres her.
                # Antagelig bør gammel verdi bare overskrives.
                if (self.entity_id2profile_path.has_key(entity_id) and
                    self.entity_id2account_ou.has_key(entity_id) and
                    self.entity_id2account_home.has_key(entity_id)):
                    continue
                # Trenger spread<->ou, spread<->profile_path og
                # spread<->home mappinger for hver bruker.
                # (Litt tung datastruktur, men det forenkler koden i neste for-løkke)
                if not entity_id in user_maps:
                    user_maps[entity_id] = {'ou':{}, 'profile_path':{}, 'home':{}}
                ac.clear()
                ac.find(entity_id)
                try:
                    canonical_name, profile_path, home = self.calc_home(entity_id, spread)
                    canonical_name = canonical_name[canonical_name.find(",")+1:]
                    logger.debug("Calculated values for %i: cn=%s,%s pp=%s, home=%s" % (
                        entity_id, ac.account_name, canonical_name, profile_path, home))
                    user_maps[entity_id]['ou'][int(spread)] = canonical_name
                    user_maps[entity_id]['profile_path'][int(spread)] = profile_path
                    user_maps[entity_id]['home'][int(spread)] = home
                except Job.CalcError, v:
                    logger.warn(v)
                except ADMappingRules.MappingError, v:
                    logger.warn(v)

        # Sett ou, home og profile_path traits.
        for e_id, spread_maps in user_maps.items():
            ac.clear()
            ac.find(e_id)
            # store pickled spread<->profile_path mapping 
            ac.populate_trait(co.trait_ad_profile_path,
                              strval=cPickle.dumps(spread_maps['profile_path']))
            # store pickled spread<->ou mapping 
            ac.populate_trait(co.trait_ad_account_ou,
                              strval=cPickle.dumps(spread_maps['ou']))
            # store pickled spread<->home mapping 
            ac.populate_trait(co.trait_ad_homedir,
                              strval=cPickle.dumps(spread_maps['home']))
            logger.debug("OU, profile_path and home trait populated for account %d",
                         entity_id)
            ac.write_db()

        if dryrun:
            logger.info("Rolling back all changes")
            db.rollback()
        else:
            logger.info("Committing all changes")
            db.commit()

    def calc_home(self, entity_id, spread):
        ac.clear()
        ac.find(entity_id)

        if spread == co.spread_ad_account_stud:
            return self.calc_stud_home(ac)

        # Henter sted fra affiliation med høyest prioritet uavhengig
        # av dens type.
        affs = ac.get_account_types()
        if not affs:
            raise Job.CalcError("No affs for entity: %i" % entity_id)
        # TODO, _get_ou_sko is not defined
        sko = self._get_ou_sko(affs[0]['ou_id'])
        logger.debug("sko: %s", sko)
        if spread == co.spread_ad_account_fag:
            rules = self._fag_rules
        if spread == co.spread_ad_account_adm:
            rules = self._adm_rules
        return (rules.getDN(sko, ac.account_name),
                rules.getProfilePath(sko, ac.account_name),
                rules.getHome(sko, ac.account_name))

    def _get_ou_sko(self, ou_id):
        ou.clear()
        ou.find(ou_id)
        return "%d%02d%02d" % (ou.fakultet, ou.institutt, ou.avdeling)

    def _get_stdnr(self, fnr):
        person.clear()
        person.find_by_external_id(co.externalid_fodselsnr, fnr,
                                   source_system=co.system_fs,
                                   entity_type=co.entity_person)
        stdnr = person.get_external_id(source_system=co.system_fs,
                                       id_type=co.externalid_studentnr)
        return stdnr[0]['external_id']
    
    def calc_stud_home(self, ac):
        if int(ac.owner_type) != int(co.entity_person):
            raise Job.CalcError("Cannot update account for non-person owner of entity: %i" % ac.entity_id)
        person.clear()
        person.find(ac.owner_id)
        rows = person.get_external_id(id_type=co.externalid_fodselsnr, source_system=co.system_fs)
        if not rows:
            raise Job.CalcError("No FS-fnr for entity: %i" % ac.entity_id)
        fnr = rows[0]['external_id']
        stdnr = self._get_stdnr(fnr)
        stprogs = self._student_info.get_persons_studieprogrammer(stdnr)
        if not stprogs:
            raise Job.CalcError("Ikke noe studieprogram for %s" % fnr)
        # Velger foreløbig det første studieprogrammet i listen...
        sko = self._student_info.get_studprog_sko(stprogs[0]['studieprogramkode'])
        if not sko:
            raise Job.CalcError("Ukjent sko for %s" % stprogs[0]['studieprogramkode'])
        try:
            kkode = stprogs[0]['klassekode']
        except KeyError:
            kkode = ""
        studinfo = "".join((stprogs[0]['arstall_kull'][-2:],
                            stprogs[0]['terminkode_kull'][0],
                            stprogs[0]['studieprogramkode'],
                            kkode)).lower()
                           
        return (self._stud_rules.getDN(sko, studinfo, ac.account_name),
                self._stud_rules.getProfilePath(sko, ac.account_name),
                self._stud_rules.getHome(sko, ac.account_name))

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'ds:p:', ['help'])
    except getopt.GetoptError:
        usage(1)

    global dryrun

    dryrun = False
    person_file = None
    stprog_file = None
    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('-s',):
            stprog_file = val
        elif opt in ('-p',):
            person_file = val
        elif opt in ('-d',):
            dryrun = True

    si = StudieInfo(person_file, stprog_file)
    Job(si)

def usage(exitcode=0):
    print __doc__
    sys.exit(exitcode)

if __name__ == '__main__':
    main()

#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2007-2008 University of Oslo, Norway
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
Dette scriptet går gjennom alle brukere som har spread til et av
HIOFs tre AD-domener. For hver bruker i hvert domene skal det:

* beregnes homedir/profile-path/OU-plassering iht til reglene som er
  definert i ADMappingRules.

* hvis disse attributtene er lagret for brukeren fra før skal de nye
  og gamle verdiene sammenlignes. Dersom verdiene er forskjellige skal
  det automatisk sendes en e-post til liste(r) definert i cereconf.
  (Dette gjøres av et eget script) Om endringene er fornuftig skal
  IT-personell ved hiof slette gamle verdier, med bofh-kommandoen user
  delete_ad_attr. Ved neste kjøring vil dette skriptet sette de nye
  verdiene.

* Dersom det ikke er lagret verdier for ad-attributtene fra før
  (gjelder for nye brukere og for brukere der gamle verdier er
  slettet) skal de nye beregnede verdiene settes.

Usage: process_AD.py [options]
-p fname : xml-fil med person informasjon
-s fname : xml-fil med studieprogram informasjon
"""

import getopt
import sys
import os.path
import cPickle
import cerebrum_path
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.hiof import ADMappingRules
from Cerebrum.modules.xmlutils.GeneralXMLParser import GeneralXMLParser
from mx import DateTime

db = Factory.get('Database')()
db.cl_init(change_program="process_ad")
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
ou = Factory.get('OU')(db)
person = Factory.get('Person')(db)
logger = Factory.get_logger("cronjob")

spread2domain = {}
entity_id2uname = {}
user_diff_attrs = {} # Users which new and old AD attrs differ


class StudieInfo(object):
    """Parse student-info from FS files."""

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
    """
    Class for processing user's AD attributes
    """

    class CalcError(Exception):
        pass

    def __init__(self, student_info, out_file):
        """
        Init ad_attr info by reading old values from Cerebrum. Start
        processing of ad attrs for each domain in ad, given by spread.
        """
        self._student_info = student_info
        self.out_file = out_file
        self.entity_id2profile_path = {}
        for row in ac.list_traits(co.trait_ad_profile_path):
            unpickle_val = cPickle.loads(str(row['strval']))
            self.entity_id2profile_path[int(row['entity_id'])] = unpickle_val
        logger.info("Found %i profile-path traits" % len(self.entity_id2profile_path))

        self.entity_id2homedir = {}
        for row in ac.list_traits(co.trait_ad_homedir):
            unpickle_val = cPickle.loads(str(row['strval']))
            self.entity_id2homedir[int(row['entity_id'])] = unpickle_val
        logger.info("Found %i homedir traits" % len(self.entity_id2homedir))

        self.entity_id2account_ou = {}
        for row in ac.list_traits(co.trait_ad_account_ou):
            unpickle_val = cPickle.loads(str(row['strval']))
            self.entity_id2account_ou[int(row['entity_id'])] = unpickle_val
        logger.info("Found %i ou traits" % len(self.entity_id2account_ou))

        self._adm_rules = ADMappingRules.Adm()
        self._fag_rules = ADMappingRules.Fag()
        self._stud_rules = ADMappingRules.Student()
        spread2domain[int(co.spread_ad_account_fag)] = self._fag_rules.DOMAIN_NAME
        spread2domain[int(co.spread_ad_account_adm)] = self._adm_rules.DOMAIN_NAME
        spread2domain[int(co.spread_ad_account_stud)] = self._stud_rules.DOMAIN_NAME

        for spread in (co.spread_ad_account_fag,
                       co.spread_ad_account_adm,
                       co.spread_ad_account_stud):
            self.process_ad_attrs(spread)
        # Write to file where ad_attrs differ
        self.write_diff_output()
    
    def write_diff_output(self):
        now = DateTime.now()
        #file_name = '/cerebrum/dumps/AD/ad_attr_diffs-%s' % now.date
        file_name = '%s-%s' % (self.out_file, now.date)
        # To avoid writing this file every time the script runs (every
        # 15 mins) we write it once per day after important FS and SAP
        # jobs have run, that is after 0400.
        if not user_diff_attrs or os.path.exists(file_name) or now.hour < 5:
            return 
        try:
            f = file(file_name, 'w')
            f.write("brukernavn;domene;gammel verdi;ny verdi\n")
            f.write("---------------------------------------\n")
            for e_id, attr_map in user_diff_attrs.items():
                for spread, attrs in attr_map.items():
                    for old_val, new_val in attrs:
                        f.write("%s;%s;%s;%s\n" % (entity_id2uname[e_id],
                                                   spread2domain[int(spread)],
                                                   old_val, new_val))
            logger.info("Wrote user_diff_ad_attrs to file %s" % file_name)
        except IOError:
            logger.warning("Couldn't open file %s" % file_name)
        else:
            f.close()
    
    def process_ad_attrs(self, spread):
        """
        In each AD domain, given by spread, check attributes homedir,
        profile_path og ou for all users. Perform the following tasks

        1. Calculate new attribute values based on rules defined in
           ADMappingRules.
        2. If a user has old values, compare these with the new ones.
           If there are differences send a report email.
        3. If not old values exists, populate the new ones.
        """
        logger.debug("Process accounts with spread=%s" % spread)
        for row in ac.list_account_home(home_spread=spread,
                                        account_spread=spread,
                                        filter_expired=True,
                                        include_nohome=True):
            entity_id = int(row['account_id'])
            # Calculate new ad attr values
            try:
                cn, profile_path, homedir = self.calc_ad_attrs(entity_id, spread)
                ou_val = cn[cn.find(",")+1:]
                entity_id2uname[entity_id] = ac.account_name
                #logger.debug("Calculated values for %i: cn=%s,%s pp=%s, homedir=%s" % (
                #    entity_id, ac.account_name, ou_val, profile_path, homedir))
            except Job.CalcError, v:
                logger.warn(v)
                continue
            except ADMappingRules.MappingError, v:
                logger.warn("Couldn't calculate homedir for user %d. %s" % (
                    entity_id, v))
                continue
            # Check if user already have ad_attrs for this domain in
            # cerebrum and compare
            if not self.check_ad_attrs_and_cmp(spread, entity_id, ou_val,
                                               profile_path, homedir):
                # set new ad attrs
                self.populate_ad_attrs(spread, entity_id, ou_val,
                                       profile_path, homedir)

    def check_ad_attrs_and_cmp(self, spread, entity_id, ou_val, profile_path, homedir):
        """
        Check ad attrs ou, homedir and profile_path in Cerebrum for given
        user and spread. If attrs doesn't exist in Cerebrum, return
        False. If attrs exist, compare with the new values, given as
        parameters. 
        """
        def attr_eq(new, old):
            if new and old:
                if new.strip().lower() == old.strip().lower():
                    return True
            return False

        ret = False         # If no old attrs is found return False
        spread = int(spread)
        for mapping, attr in ((self.entity_id2account_ou, ou_val),
                              (self.entity_id2profile_path, profile_path),
                              (self.entity_id2homedir, homedir)):
            # get old values
            ad_trait = mapping.get(entity_id, None)
            if ad_trait and ad_trait.has_key(spread):
                # ad attrs for this user in the given domain exists. Compare with new values
                if not attr_eq(attr, ad_trait[spread]):
                    # New AD attrs are not equal the old ones
                    # Where attr differs, store as a 2d mapping:
                    # user <-> {spread <-> [(old attr, new attr)]}
                    if not entity_id in user_diff_attrs:
                        user_diff_attrs[entity_id] = {}
                    if not spread in user_diff_attrs[entity_id]:
                        user_diff_attrs[entity_id][spread] = []
                    user_diff_attrs[entity_id][spread].append((attr, ad_trait[spread]))
                ret = True            
        return ret

    def populate_ad_attrs(self, spread, entity_id, ou_val, profile_path, homedir):
        """
        populate spread<->ad_attr mapping as an entity_trait in
        Cerebrum. No
        """
        ac.clear()
        ac.find(entity_id)
        # get and set spread<->profile_path mapping for this user
        pp_mapping = self._get_trait(ac, co.trait_ad_profile_path)
        pp_mapping[int(spread)] = str(profile_path)
        ac.populate_trait(co.trait_ad_profile_path,
                          strval=cPickle.dumps(pp_mapping))
        # get and set spread<->homedir mapping for this user
        homedir_mapping = self._get_trait(ac, co.trait_ad_profile_path)
        homedir_mapping[int(spread)] = str(homedir)
        ac.populate_trait(co.trait_ad_homedir,
                          strval=cPickle.dumps(homedir_mapping))
        # get and set spread<->ou mapping for this user
        ou_mapping = self._get_trait(ac, co.trait_ad_profile_path)
        ou_mapping[int(spread)] = str(ou_val)
        ac.populate_trait(co.trait_ad_account_ou,
                          strval=cPickle.dumps(ou_mapping))
        ac.write_db()
        logger.info("OU, profile_path and homedir trait populated for account %d",
                     entity_id)

    def _get_trait(self, account, trait_const):
        """
        Return trait of given type for this user
        """
        tmp = account.get_trait(co.trait_const)
        if not tmp:
            return {}
        else:
            return cPickle.loads(str(tmp['strval']))

    def calc_ad_attrs(self, entity_id, spread):
        ac.clear()
        ac.find(entity_id)

        if spread == co.spread_ad_account_stud:
            return self.calc_stud_home(ac)

        # Henter sted fra affiliation med høyest prioritet uavhengig
        # av dens type.
        affs = ac.get_account_types()
        if not affs:
            raise Job.CalcError("No affs for entity: %i" % entity_id)
        sko = self._get_ou_sko(affs[0]['ou_id'])
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
        if not stdnr:
            raise Job.CalcError("No FS-stdnr for entity with fnr: %s" % fnr)
        return stdnr[0]['external_id']
    
    def calc_stud_home(self, ac):
        if int(ac.owner_type) != int(co.entity_person):
            raise Job.CalcError("Cannot update non-personal account: %i" %
                                ac.entity_id)
        person.clear()
        person.find(ac.owner_id)
        rows = person.get_external_id(id_type=co.externalid_fodselsnr,
                                      source_system=co.system_fs)
        if not rows:
            raise Job.CalcError("No FS-fnr for entity: %i" % ac.entity_id)
        fnr = rows[0]['external_id']
        stdnr = self._get_stdnr(fnr)
        stprogs = self._student_info.get_persons_studieprogrammer(stdnr)
        if not stprogs:
            raise Job.CalcError("No studieprogram for %s" % fnr)
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
        opts, args = getopt.getopt(sys.argv[1:], 'ds:p:o:', ['help'])
    except getopt.GetoptError:
        usage(1)

    dryrun = False
    sendmail = False
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
        elif opt in ('-o',):
            out_file = val

    si = StudieInfo(person_file, stprog_file)
    Job(si, out_file)
    # Committ changes?
    if dryrun:
        logger.info("Rolling back all changes")
        db.rollback()
    else:
        logger.info("Committing all changes")
        db.commit()

def usage(exitcode=0):
    print __doc__
    sys.exit(exitcode)

if __name__ == '__main__':
    main()

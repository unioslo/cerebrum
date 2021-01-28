#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2007-2018 University of Oslo, Norway
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
Dette scriptet går gjennom alle brukere med gitt spread. For hver
bruker skal det:

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
-a ad_spread : spread_str for spread (domene)
-o fname : utfil
"""

import getopt
import sys
import six

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.modules.no.hiof import ADMappingRules
from Cerebrum.modules.xmlutils.GeneralXMLParser import GeneralXMLParser

db = Factory.get('Database')()
db.cl_init(change_program="process_ad")
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
ou = Factory.get('OU')(db)
person = Factory.get('Person')(db)
logger = None

entity_id2uname = {}
user_diff_attrs = {}  # Users which new and old AD attrs differ


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

    def __init__(self, spread_str, student_info):
        """
        Init ad_attr info by setting mapping rules for a AD domain,
        given by spread.

        @param spread_str: account ad spread
        @type  spread_str: str
        @param student_info: parse student info files
        @type  student_info: StudieInfo
        """
        self.student_info = student_info
        # Verify spread
        self.spread = co.Spread(spread_str)

        # TODO: få vekk denne hardkodingen av spreads
        if self.spread == co.spread_ad_account_fag:
            self.rules = ADMappingRules.Fag()
        elif self.spread == co.spread_ad_account_adm:
            self.rules = ADMappingRules.Adm()
        elif self.spread == co.spread_ad_account_stud:
            self.rules = ADMappingRules.Student()

    def process_ad_attrs(self):
        """
        Check account's AD attributes in AD domain given by spread.
        Perform the following tasks

        1. Calculate new attribute values based on rules defined in
           ADMappingRules.
        2. If a user has old values, compare these with the new ones.
           If there are differences send a report email.
        3. If not old values exists, populate the new ones.
        """
        logger.debug("Process accounts with spread=%s" % self.spread)
        for row in ac.list_account_home(home_spread=self.spread,
                                        account_spread=self.spread,
                                        filter_expired=True,
                                        include_nohome=True):
            entity_id = int(row['account_id'])
            ac.clear()
            ac.find(entity_id)
            # Calculate new ad attr values
            try:
                new_attrs = self.calc_ad_attrs()
                entity_id2uname[entity_id] = ac.account_name
                logger.debug1("Calculated values for %i: %s" % (
                    entity_id, new_attrs))
            except Job.CalcError, v:
                logger.warn(v)
                continue
            except ADMappingRules.MappingError, v:
                logger.warn("Couldn't calculate ad attrs for user %d. %s" % (
                    entity_id, v))
                continue
            # Check if user already have ad_attrs for this domain in
            # cerebrum and compare
            old_attrs = ac.get_ad_attrs_by_spread(self.spread)
            # if no attributes in Cerebrum, populate the new ones
            # else compare old and new
            if old_attrs:
                self.compare_attrs(old_attrs, new_attrs, entity_id)
            else:
                self.populate_ad_attrs(new_attrs)
                ac.write_db()
                logger.info(
                    "AD attributes %s populated for account %s (id:%d)",
                    new_attrs, ac.account_name, entity_id)

    def calc_ad_attrs(self):
        """
        Calculate and return AD attributes for an account.

        @rtype: dict
        @return: {attr_type : attr_value, ...}
        """
        # Non-personal accounts have their own rules
        if int(ac.owner_type) == int(co.entity_group):
            return self.calc_nonpersonal_ad_attrs()
        if self.spread == co.spread_ad_account_stud:
            return self.calc_stud_home()
        ret = {}
        # Henter sted fra affiliation med høyest prioritet uavhengig
        # av dens type.
        affs = ac.get_account_types()
        if not affs:
            raise Job.CalcError("No affs for account: %s (id:%i)" % (
                ac.account_name, ac.entity_id))
        sko = self._get_ou_sko(affs[0]['ou_id'])
        cn = self.rules.getDN(ac.account_name, sko)
        ret['ad_account_ou'] = cn[cn.find(",") + 1:]
        ret['ad_profile_path'] = self.rules.getProfilePath(
            ac.account_name, sko)
        ret['ad_homedir'] = self.rules.getHome(ac.account_name, sko)
        return ret

    def calc_nonpersonal_ad_attrs(self):
        """
        Calculate and return AD attributes for an non personal
        account.

        @rtype: dict
        @return: {attr_type : attr_value, ...}
        """
        ret = {}
        ret['ad_account_ou'] = cereconf.AD_DEFAULT_OU
        ret['ad_profile_path'] = self.rules.getProfilePath(ac.account_name)
        ret['ad_homedir'] = self.rules.getHome(ac.account_name)
        return ret

    def calc_stud_home(self):
        """
        Calculate and return AD attributes for a student account.

        @rtype: dict
        @return: {attr_type : attr_value, ...}
        """
        person.clear()
        person.find(ac.owner_id)
        # Get FS fnr
        rows = person.get_external_id(id_type=co.externalid_fodselsnr,
                                      source_system=co.system_fs)
        if not rows:
            raise Job.CalcError("No FS-fnr for entity: %i" % ac.entity_id)
        fnr = rows[0]['external_id']
        # Get FS studentnr
        rows = person.get_external_id(source_system=co.system_fs,
                                      id_type=co.externalid_studentnr)
        if not rows:
            raise Job.CalcError("No FS-stdnr for entity with fnr: %s" % fnr)
        stdnr = rows[0]['external_id']
        stprogs = self.student_info.get_persons_studieprogrammer(stdnr)
        if not stprogs:
            raise Job.CalcError("No studieprogram for %s" % fnr)
        # Velger foreløbig det første studieprogrammet i listen...
        sko = self.student_info.get_studprog_sko(
            stprogs[0]['studieprogramkode'])
        if not sko:
            raise Job.CalcError(
                "Ukjent sko for %s" % stprogs[0]['studieprogramkode'])
        try:
            kkode = stprogs[0]['klassekode']
        except KeyError:
            kkode = ""
        studinfo = "".join((stprogs[0]['arstall_kull'][-2:],
                            stprogs[0]['terminkode_kull'][0],
                            stprogs[0]['studieprogramkode'],
                            kkode)).lower()
        ret = {}
        cn = self.rules.getDN(ac.account_name, sko, studinfo)
        ret['ad_account_ou'] = cn[cn.find(",") + 1:]
        ret['ad_profile_path'] = self.rules.getProfilePath(
            ac.account_name, sko)
        ret['ad_homedir'] = self.rules.getHome(ac.account_name, sko)
        return ret

    def _get_ou_sko(self, ou_id):
        ou.clear()
        ou.find(ou_id)
        return "%02d%02d%02d" % (ou.fakultet, ou.institutt, ou.avdeling)

    def compare_attrs(self, old_attrs, new_attrs, entity_id):
        """
        Compare old and new AD attributes.

        @param old_attrs: attr type -> attr value mapping
        @type  old_attrs: dict
        @param new_attrs: attr type -> attr value mapping
        @type  new_attrs: dict
        """
        def attr_eq(new, old):
            if new and old:
                if new.strip().lower() == old.strip().lower():
                    return True
            return False

        spread = int(self.spread)
        for k in new_attrs.keys():
            if (not (old_attrs.get(k, None) and
                     attr_eq(new_attrs[k], old_attrs[k]))):
                # New AD attrs are not equal the old ones
                # Where attr differs, store as a 2d mapping:
                # user <-> {spread <-> [(new attr, old attr)]}
                if entity_id not in user_diff_attrs:
                    user_diff_attrs[entity_id] = {}
                if spread not in user_diff_attrs[entity_id]:
                    user_diff_attrs[entity_id][spread] = []
                user_diff_attrs[entity_id][spread].append(
                    (new_attrs[k], old_attrs.get(k, None)))

    def populate_ad_attrs(self, new_attrs):
        """
        populate spread->attr_value mapping as an entity_trait in
        Cerebrum.

        @param new_attrs: attr type -> attr value mapping
        @type  new_attrs: dict
        """
        for attr_type, attr_val in new_attrs.iteritems():
            # Before populating spread we must check if there are old
            # values. Account might have attributes for more than one
            # spread. Those must not be deleted
            existing_attrs = ac.get_ad_attrs_by_type(attr_type)
            # Update spread -> ad val mapping with new value
            existing_attrs[int(self.spread)] = six.text_type(attr_val)
            ac.populate_ad_attrs(attr_type, existing_attrs)


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hda:s:p:o:', [
            'help', 'dryrun', 'ad-spread=', 'studie-prog=',
            'person-file=', 'out-file='])
    except getopt.GetoptError:
        usage(1)

    global logger
    dryrun = False
    person_file = None
    stprog_file = None
    spread_str = None
    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('-d', '--dryrun'):
            dryrun = True
        elif opt in ('-a', '--ad-spread'):
            spread_str = val
        elif opt in ('-s', '--studie-prog'):
            stprog_file = val
        elif opt in ('-p', '--person-file'):
            person_file = val

    if not spread_str:
        usage(1)
    logger_name = "process_ad_" + str(spread_str).split('@ad_')[1]
    logger = Factory.get_logger(logger_name)
    si = StudieInfo(person_file, stprog_file)
    j = Job(spread_str, si)
    # Process ad attributes for accounts with this spread
    j.process_ad_attrs()

    # Commit changes?
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

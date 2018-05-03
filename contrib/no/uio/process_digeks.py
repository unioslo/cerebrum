#!/usr/bin/env python
# coding: latin1
# -*- coding: iso-8859-1 -*-
# vim: set fileencoding=latin1 :
# Copyright 2013-2018 University of Oslo, Norway
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
This script generates an export of exams and exam participants for digital
examinations.

It will also create exam groups, and add candidates to those groups.


Program flow:

  + Fetch exams and candidates from FS, organize into dictionaries with keys
    based on: institition, subject, version number, exam code, semester, year
      Note: We first fetch the exams in one query (get_exam_data), then the
            candidates for each exam in separate queries (get_candidate_data).
      Note: Multiple exams in the same subject, same year,
            same semester must have *different* exam codes (vurdkombkode in
            FS). If these fields aren't unique, then two different exams will
            be treated as one single exam by the script and export files. If
            this occurs, a WARNING will be logged.
  + Look up/cache account_id, owner_id, mobile number (if it exists) for every
    candidate username fetched from FS.
      Note: With many candidates, caching saves a *lot* of time in the
            processing stage. This has only been tested up to ~10.000 users.
            If the number of candidates exceeds this with an order of
            magnitude, we could run into memory issues.
  + Go through every exam, fetch and/or create the neccessary moderator
    group and candidate group (get_exam_group)
    + Go through every candidate username for that exam
      - If not found in the cache (not in cerebrum), the candidate is omitted
        from groups and export files. A WARNING will be logged.
      - Look up mobile number for the username in the cache. If no mobile
        number is found, a DEBUG message is logged.
      - The user is added to the exam group. If already a member, a DEBUG
        message will be logged. If unable to add candidate to group, the
        candidate will be omitted from the candidate report as well, ans a
        WARNING will be logged.
      - Write the candidate data to candidate csv file.
    - Write group changes to DB
    - Write exam data to csv file
      
"""
import getopt
import sys
import re
from os.path import basename, dirname, exists
from os import makedirs

import cereconf

from Cerebrum.Utils import Factory, argument_to_sql
from Cerebrum.Errors import NotFoundError
from Cerebrum.modules.bofhd.auth import BofhdAuthOpSet, BofhdAuthOpTarget, BofhdAuthRole
from Cerebrum.modules.no.access_FS import make_fs

from mx import DateTime

logger = Factory.get_logger('cronjob')

# TODO: Add actual cereconf-vars
# This is the parent group for all candidates. Candidate groups should be added
# to this group.
cereconf.DIGEKS_PARENT_GROUP = 'deksamen-test'

# FIXME: These are the classes that we will be looking up exams for. This list
# should be replaced by an automated selection of subjects, which is probably
# another FS lookup.
cereconf.DIGEKS_EXAMS = ['PPU3310L', 'JUS4111', ]

# When looking up exams, we need to filter out non-digital exams and other
# deliverables (obligatory assignments). This string will be matched with the
# FS field 'vurdkombkode'. FIXME: This needs to be standardized.
cereconf.DIGEKS_TYPECODE = 'SPC%'

# Spreads for new groups created for candidates and admins
cereconf.DIGEKS_GROUP_SPREADS = ['AD_group']

# Required spreads for candidates. A log warning will be thrown if a candidate
# is missing this spread. The candidate will still be processed as normal.
cereconf.DIGEKS_CANDIDATE_SPREADS = ['AD_account']

# Symbol for use as separator in csv export files
# TODO/TBD: Should this be a cereconf variable?
CSV_SEPARATOR = u';'


def usage(exitcode=0):
    """ Print script usage, and exits with C{exitcode}. """
    print """ Usage: %(name)s [options]

    Sets up exam groups, and generates an export of exams and participants as
    CSV-files.

    Options:
      -c, --candidates <file>    Output CSV-file with the candidates
      -e, --exams      <file>    Output CSV-file with the exam data
      -d, --dry-run              Only ouput files, don't commit membership
                                 changes to the db
      -s, --subject    <s1,...>  Subjects to look up exams for
      -y, --year       <year>    Restrict to exams in the given year
      -t, --semester   <term>    Restrict to exams in the given term. Tip -
                                 check encoding, might want to use:
                                    -t `print '<term>' | iconv -f <enc> -t <enc>`
      -h, --help                 Show this help text.
    """ % {'name': basename(sys.argv[0])}

    sys.exit(exitcode)


## These objects were created as a consequence of debugging: They may not be an
## ideal representation. We might as well use simple dicts.
class Exam(object):

    """ An exam object.

    Temporary storage of exam info, sanitizes data. Easily converted to a
    unicode string for writing to CSV file.

    Attributes
        separator: The separator to use in CSV files.

    """

    separator = CSV_SEPARATOR

    class Candidate(object):
        """ A candidate object. Temporary storage of candidate info, sanitizes
        data. Easily converted to a unicode string for writing to CSV file.
        """

        def __init__(self, exam, username, candidate, commision):
            """ Create a new candidate object. Should not be created outside of a Exam object. """

            # Check the argument types, and throw error if not as expected
            for (arg, typ) in (('candidate', int),
                               ('commision', int),
                               ('username', (str, unicode))):
                val = locals().get(arg)
                assert isinstance(val, typ), ("%s must be %s, was %s" %
                                              (arg, repr(typ), type(val)))

            self.exam = exam
            self.username = unicode(username)
            self.candidate = int(candidate)
            self.commision = int(commision)
            self.mobile = None

        def set_mobile(self, mobile):
            """ Sets the candidate mobile phone number """
            self.mobile = unicode(mobile)

        def __hash__(self):
            return hash((self.exam.key(), self.username))

        def __str__(self):
            return self.exam.separator.join([
                escape_chars(self.username, special=self.exam.separator),
                self.exam.key(),
                escape_chars(str(self.candidate), special=self.exam.separator),
                escape_chars(str(self.commision), special=self.exam.separator),
                escape_chars(self.mobile, special=self.exam.separator), ])

    def __init__(self, institution, subject, year, timecode, typecode, version,
                 datetime, place, access):
        """ Create a new exam object. """

        # Check the argument types, and throw error if not as expected
        for (arg, typ) in (('institution', int), 
                           ('year', int),
                           ('version', (str, unicode)),
                           ('subject', (str, unicode)),
                           ('timecode', (str, unicode)),
                           ('typecode', (str, unicode)),
                           ('place', (str, unicode)),
                           ('access', (str, unicode)),
                           ('datetime', (str, unicode, DateTime)),):
            val = locals().get(arg)
            assert isinstance(val, typ), "%s must be %s, was %s" % (arg, repr(typ), type(val))

        self.institution = int(institution)
        self.year = int(year)
        self.version = unicode(version)
        self.subject = unicode(subject)
        self.timecode = unicode(timecode)
        self.typecode = unicode(typecode)
        self.place = unicode(place)
        self.access = unicode(access)  # FIXME if anything changes.
        self.datetime = DateTime.DateTimeFrom(datetime)
        self.candidates = set()

    def key(self):
        """ Return the exam key (unique id) for this exam. """
        return self.separator.join([
            str(self.institution),
            escape_chars(self.subject, special=self.separator),
            escape_chars(self.version,  special=self.separator),
            escape_chars(self.typecode, special=self.separator),
            escape_chars(self.timecode, special=self.separator),
            str(self.year), ])

    def addCandidate(self, username, candidate, commision):
        """ Add a new candidate to this exam.

        Returns True if candidate was added, and False if candidate was already
        a candidate in this exam.

        """
        candidate = self.Candidate(
            self,
            username,
            candidate,
            commision,)
        if candidate in self.candidates:
            return False
        self.candidates.add(candidate)
        return True

    def __hash__(self):
        return hash((self.key(), str(self.datetime)))

    def __str__(self):
        return self.separator.join([
            self.key(),
            unicode(self.datetime),
            self.place,
            self.access, ])


class CandidateCache:

    """ A caching object, for storing candidate account names and data. """

    def __init__(self, db, candidates):
        """ All caching happens on init.

        @type db: Cerebrum.DatabaseAccessor
        @param db: A database connection

        @type candidates: set
        @param candidates: All the candidates that should have their
                           information looked up/cached

        """
        self.accounts = dict()     # mapping account_name -> acc_id + owner_id
        self.mobiles = dict()      # mapping person_id -> mobile
        self.spreads = list()      # tuple (account_id, spread_code)
        self.quarantined = dict()  # mapping account_id -> [ quarantine list ]

        self.db = db  # For any future use
        self.co = Factory.get('Constants')(db)

        self.cacheAccounts(candidates)

    def cacheAccounts(self, account_names):
        """ Cache data for a list of account names, efficiently.

        This function has a bit of an overhead, because it looks up all users
        in the db. It is, however, a lot more efficient than looking up
        individual accounts when there's a lot of L{account_names}.

        @type account_names: set
        @param account_names:
            An iterable (ideally a set) of account names to cache data for.

        """
        ac = Factory.get('Account')(self.db)
        pe = Factory.get('Person')(self.db)

        # Save some time
        if not account_names:
            return

        # Fetch all accounts. ...would be nice to filter by names in the query
        all_accounts = ac.search(owner_type=self.co.entity_person)

        # self.accounts - Account and owner id for all candidates. Dict map:
        #   account_name -> {account_id -> , owner_id -> ,}
        filtered_accounts = filter(lambda a: a['name'] in account_names,
                                   all_accounts)
        self.accounts = dict((a['name'], {
            'account_id': a['account_id'],
            'owner_id': a['owner_id']}) for a in filtered_accounts)

        # self.mobiles - Look up the mobile phone number (from FS) for all
        # candidates. Dict mapping:
        #   person_id -> mobile number
        owners = set([a['owner_id'] for a in self.accounts.values()])
        if owners:
            self.mobiles = dict((mob['entity_id'], mob['contact_value']) for mob in
                    pe.list_contact_info(source_system=self.co.system_fs,
                                         contact_type=self.co.contact_mobile_phone,
                                         entity_type=self.co.entity_person, 
                                         entity_id=owners))

        # self.spreads - The spreads of all candidates. List of tuples: 
        #   (account_id, spread_code)
        account_ids = set([a['account_id'] for a in self.accounts.values()])
        for s in cereconf.DIGEKS_CANDIDATE_SPREADS:
            spread = self.co.Spread(s)
            spreads = filter(lambda s: s['entity_id'] in account_ids, ac.list_all_with_spread(spread))
            self.spreads.extend(spreads)

        # Quarantines
        quarantines = []
        if len(account_ids) > 0:
            quarantines = ac.list_entity_quarantines(
                    entity_types=self.co.entity_account,
                    entity_ids=account_ids, 
                    only_active=False)
        for q in quarantines:
            if q['entity_id'] not in self.quarantined.keys():
                self.quarantined[q['entity_id']] = []
            self.quarantined[q['entity_id']].append(str(self.co.Quarantine(q['quarantine_type'])))


    def cacheAccount(self, account_name):
        """ Cache data for one individual L{account_name}. Can be used to refresh the
        cache, or to fetch additional data

        @type account_name: str
        @param account_name: An account name to cache data for

        @rtype: bool
        @return: True if caching was successful, otherwise False (typically
                 the account_name does not exist as a personal account)
        """
        ac = Factory.get('Account')(self.db)
        pe = Factory.get('Person')(self.db)
        try:
            ac.find_by_name(account_name)
            pe.find(ac.owner_id) # NotFoundError if owner_id != Person
        except NotFoundError:
            return False

        # account_name -> account_id + owner_id
        self.accounts[ac.account_name] = {
                'account_id': ac.entity_id,
                'owner_id': ac.owner_id
                }

        # owner_id -> mobile
        contact = pe.get_contact_info(source=self.co.system_fs,
                type=self.co.contact_mobile_phone)
        if len(contact) == 1:
            self.mobiles[pe.entity_id] = contact[0].get('contact_value')
        
        # account_id + spread table
        spreads = [(ac.entity_id, spread.get('spread')) for spread in ac.get_spread()]
        print account_name, str(spreads)
        self.spreads.extend(spreads)
        print 'all', str(self.spreads)

        # account_id -> quarantine list
        for q in ac.get_entity_quarantine():
            if ac.entity_id not in self.quarantined.keys():
                self.quarantined[ac.entity_id] = []
            self.quarantined[ac.entity_id].append(str(self.co.Quarantine(q['quarantine_type'])))

        return True


    def uname2id(self, account_name):
        """ Cache lookup: account_name -> account_id """
        account = self.accounts.get(account_name, None)
        if not account:
            return None
        return account['account_id']

    def uname2mobile(self, account_name):
        """ Cache lookup: account_name -> cellphone number """
        account = self.accounts.get(account_name, None)
        if not account:
            return ''
        return self.mobiles.get(account['owner_id'], '')

    def uname_has_spread(self, account_name, spread):
        """ Cache lookup: returns true if account_name has the given spread.
        This can be used to warn about accounts with missing spreads. 
        
        NOTE: cacheAccounts will only cache spreads in
              C{cereconf.DIGEKS_CANDIDATE_SPREADS}. We cannot look up other
              spreads
        """
        account_id = self.uname2id(account_name)
        if not account_id:
            return False

        spread = self.co.Spread(spread)
        try:
            return (account_id, spread) in self.spreads
        except NotFoundError:
            return False

    def uname_quarantines(self, account_name):
        """ Return a list of quarantines (may be inactive) for the given user

        @rtype: list
        @return: A list of quarantine strvals applied to the user
        """
        account_id = self.uname2id(account_name)
        if not account_id:
            return []
        return self.quarantined.get(account_id, [])


class Digeks(object):
    """ This is an abstract class, with all the common methods for Digital exams.
        All the non-implemented methods will raise an NotImplementedError.
        To use this class, you will need to overrride the following methods:

        TODO: This is a hack/workaround until the process (and FS data) is standardized.
    """

    def __init__(self, subjects, year, version=None, typecode=None, timecode=None):
        self.db = Factory.get('Database')()
        self.db.cl_init(change_program='proc-digeks')
        self.co = Factory.get('Constants')(self.db)
        self.fs = make_fs()

        # TODO: Describe the structure here
        self.exams = set()
        self.candidates = set()

        # FIXME: We shouldn't need to specify subject/semester/...
        if not isinstance(subjects, (list,set,tuple)):
            raise Exception('Subjects must be a (list,set,tuple)')

        self.subjects = subjects
        self.year = year
        self.typecode = typecode # vurdkombkode
        self.timecode = timecode # vurdtidkode
        self.version  = version  # versjonskode

        # Start processing
        #
        self.process_exams()

        all_candidates = set([c.username for c in self.candidates])
        logger.debug('Caching candidate data for %d unique candidates...' % len(all_candidates))
        self.cache = CandidateCache(self.db, all_candidates)


    # FIXME: This should not be class specific, as we progress with the
    # automation, as the subclassing is actually a workaround for a lack of
    # standatdizing in the FS data, and the exam folder structure
    def gen_group_name(self, identity, is_admin=False):
        raise NotImplementedError("""This needs to be implemented in a
        subclass. This class must be subclassed.""")


    def fetch_candidate_data(self, subject, year, timecode=None, typecode=None, version=None):
        raise NotImplementedError("""This needs to be implemented in a
        subclass. This class must be subclassed.""")

    def fetch_exam_data(self, subjects, year, timecode=None):
        raise NotImplementedError("""This needs to be implemented in a
        subclass. This class must be subclassed.""")


    def find_or_create_group(self, group_name):
        """ This method will find and return the group object corresponding to
        L{group_name}. If no group exists with that name, the group will be
        created and returned.

        @type db: Cerebrum.database.Database
        @param db: A Cerebrum database object.
        
        @type group_name: str
        @param group_name: Name of the group to find or create

        @rtype: Cerebrum.Group.Group
        @return: A Cerebrum group object, with the specified group selected.
        """
        gr = Factory.get('Group')(self.db)
        
        # FIXME: This is ugly, as we bypass the test for NIS-memberships in the UIO
        # mixin. The group *could* get promoted to PosixGroup and get NIS-spreads.
        # However, the test that we bypass causes add_member() to take approx.
        # 100 ms. Adding 100 candidates to an exam group will then take ~10
        # seconds, and *that* doesn't scale very well.
        #from Cerebrum.Group import Group
        #gr = Group(self.db)

        try:
            gr.find_by_name(group_name)
            return gr
        except NotFoundError:
            pass

        logger.info("Group '%s' didn't exist, will be created" % group_name)
        ac = Factory.get('Account')(self.db)
        creator = ac.search(name='bootstrap_account')[0]['account_id']
        gr.populate(creator_id = creator, name = group_name,
                visibility = self.co.group_visibility_all,
                description = "Digital exams group '%s'" % group_name)
        gr.write_db()
        for spread in cereconf.DIGEKS_GROUP_SPREADS:
            gr.add_spread(self.co.Spread(spread))
            gr.write_db()

        return gr

    # As things get standardized, this should be moved into the get_exam_group method
    def add_group_to_parent(self, group):
        """ Adds a group to the parent group cereconf.DIGEKS_PARENT_GROUP """
        assert hasattr(group, 'entity_id')
        assert group.entity_type == self.co.entity_group

        gr = Factory.get('Group')(self.db)
        gr.find_by_name(cereconf.DIGEKS_PARENT_GROUP)

        if not gr.has_member(group.entity_id):
            gr.add_member(group.entity_id)
            gr.write_db()
            return True

        return False


    def set_group_owner(self, owner_id, group_id):
        """ This method will simply set up the Entity L{owner_id} as a
        C{Group-owner} of group L{group_id}.
        
        @type db: Cerebrum.database.Database
        @param db: A Cerebrum database object.
        
        @type owner_id: int
        @param owner_id: The C{entity_id} of the owner object.

        @type group_id: int
        @param group_id: The C{group_id} of a group object.
        """
        ar = BofhdAuthRole(self.db)
        aos = BofhdAuthOpSet(self.db)
        aot = BofhdAuthOpTarget(self.db)

        # Find or create group operation target
        try:
            aot.find(aot.list(entity_id=group_id, 
                              target_type=self.co.auth_target_type_group
                             )[0]['op_target_id'])
        except IndexError:
            aot.populate(group_id, self.co.auth_target_type_group)
            aot.write_db()
        
        # Find the 'Group-owner' OpSet to get its entity_id
        aos.find_by_name('Group-owner')

        if not len(ar.list(owner_id, aos.op_set_id, aot.op_target_id)):
            ar.grant_auth(owner_id, aos.op_set_id, aot.op_target_id)
            return True

        return False


    def get_exam_group(self, identity):
        """ This method will find or create the group for exam candidates. It will
        also find or create an owner group, and set up the group-owner
        relation.

        @type identity: str
        @param identity: The identifying factor. Currently, this is the SKO.

        @rtype:  Group
        @return: The Group object that was found/created.
        """

        owner_name = self.gen_group_name(identity, True)
        owner = self.find_or_create_group(owner_name)

        group_name = self.gen_group_name(identity, False)
        group = self.find_or_create_group(group_name)

        if self.set_group_owner(owner.entity_id, group.entity_id):
            logger.info("Group-owner relation created, %s -> %s" % 
                    (owner.group_name, group.group_name))

        return group


    def process_exams(self):
        # Document, this is a bit messy. Used to gather, sanitize and organize
        # results.
        logger.debug('Fetching FS data...')
        db_exams = self.fetch_exam_data(self.subjects, self.year, timecode=self.timecode)

        for exam_row in db_exams:
            logger.debug('Exam: %s' % repr(exam_row))
            try:
                exam = Exam(
                        exam_row['institusjon'],
                        exam_row['emnekode'].decode(self.fs.db.encoding),
                        exam_row['arstall'],
                        exam_row['vurdtidkode'].decode(self.fs.db.encoding),
                        exam_row['vurdkombkode'].decode(self.fs.db.encoding),
                        exam_row['versjonskode'],
                        '%s %s' % (exam_row['dato'], exam_row['tid']),
                        '%02d0000' % exam_row['fakultet'],
                        '',)

                if exam in self.exams:
                    logger.warn("Unable to process exam, duplicate exam with key '%s'!" % exam.key())
                    continue

                db_candidates = self.fetch_candidate_data(
                        exam.subject.encode(self.fs.db.encoding), 
                        exam.year,
                        timecode=exam.timecode.encode(self.fs.db.encoding),
                        typecode=exam.typecode.encode(self.fs.db.encoding),
                        version=exam.version.encode(self.fs.db.encoding), )
            
            except KeyError, e:
                logger.warn('Unable to process exam, no such column in FS result: %s' % str(e))
                continue
            except AssertionError, e:
                logger.warn('Unable to process exam, invalid value from FS: %s' % str(e))
                continue

            for cand_row in db_candidates:
                try:
                    if not exam.addCandidate(cand_row['brukernavn'],
                                             cand_row['kandidatlopenr'],
                                             cand_row['kommislopenr'],):
                        logger.warn('Duplicate candidate %s (cand: %d) in exam %s' % 
                                (cand_row['brukernavn'], cand_row['kandidatlopenr'], exam.key()))
                        continue
                except KeyError, e:
                    logger.warn('Unable to process candidate, no such column in FS result: %s' % str(e))
                    continue
                except AssertionError, e:
                    logger.warn('Unable to process candidate, invalid value from FS: %s' % str(e))
                    continue
            
            self.exams.add(exam)
            self.candidates.update(exam.candidates)

        logger.debug('Found %d candidates in %d exams' % (len(self.candidates), len(self.exams)))


    def process_candidates(self):
        """ Process candidates. This will fetch missing candidate data from
        cache, and report on conditions that could cause problems later, e.g.
        missing spreads, missing mobile number, ...

        """
        # We don't need to report on the same issue for candidates with the
        # same username. We keep track on which usernames we've seen, to avoid
        # multiple log messages on the same issue.
        seen_accounts = set()

        for candidate in self.candidates:
            account_id = self.cache.uname2id(candidate.username)
            if not account_id:
                if candidate.username not in seen_accounts:
                    logger.error(("No account found for '%s', will be omitted"
                        + " from export") % candidate.username)
                    seen_accounts.add(candidate.username)
                continue

            # Fetch/Update candidate mobile number 
            mobile = self.cache.uname2mobile(candidate.username)
            if mobile:
                candidate.set_mobile(mobile)
            elif candidate.username not in seen_accounts:
                logger.warn("No mobile number for '%s'" % candidate.username)

            # Check quarantines
            quarantines = self.cache.uname_quarantines(candidate.username)
            # Log the first hit for a given user with quarantines
            if quarantines and candidate.username not in seen_accounts:
                logger.warn("User '%s' has potential quarantine(s): %s" % (
                    candidate.username, 
                    ', '.join(quarantines)))

            # Check sperads
            missing_spreads = []
            for spread in cereconf.DIGEKS_CANDIDATE_SPREADS:
                if not self.cache.uname_has_spread(candidate.username, spread):
                    missing_spreads.append(spread)
            # Log the first hit for a given user with missing spreads
            if missing_spreads and candidate.username not in seen_accounts:
                logger.warn("User '%s' is missing required spread(s): %s" % (
                    candidate.username, 
                    ', '.join(missing_spreads)))

            seen_accounts.add(candidate.username)


    def write(self, examfile, candidatefile):
        """ Writes the exams and candidates to their respective files. Also
        adds the candidate to the correct group.
        """
        self.process_candidates()

        for exam in self.exams:
            logger.debug('Exam %s, %d candidates' % 
                    (exam.key(), len(exam.candidates)))

            exam_group = self.get_exam_group(exam.place)

            # Process candidates
            for candidate in exam.candidates:

                account_id = self.cache.uname2id(candidate.username)
                if not account_id:
                    continue
                
                if exam_group.has_member(account_id):
                    logger.debug('User %s already in group %s' %
                            (candidate.username, exam_group.group_name))
                else:
                    try:
                        exam_group.add_member(account_id)
                    except exam_group.db.IntegrityError, e:
                        logger.warn('Unable to add user %s to group %s: %s' % (
                            candidate.username, 
                            exam_group.group_name,
                            str(e)))
                        continue

                line = unicode(candidate) + u'\n'
                candidatefile.write(line.encode('utf8'))
            
            exam_group.write_db()

            line = unicode(exam) + u'\n'
            examfile.write(line.encode('utf8'))


    def rollback(self):
        self.db.rollback()

    def commit(self):
        self.db.commit()



class JUSDigeks(Digeks):

    def gen_group_name(self, identity, is_admin=False):
        return "digital-eksamen-%s%s" % (('', 'adm-')[int(is_admin)], identity)

    def get_exam_group(self, identity):
        #group = self.find_or_create_group(cereconf.DIGEKS_PARENT_GROUP)

        # Fixme: Directory structure
        group = super(JUSDigeks, self).get_exam_group(identity)
        #self.add_group_to_parent(group)
        
        return group


    def fetch_candidate_data(self, subject, year, timecode=None, typecode=None, version=None):
        """ Fetches exam candidates from FS. 

        @type subject: string
        @param subject: The subjects to fetch exam data for

        @type year: int or string
        @param year: Filter results by year

        @type semester: string
        @param semester: Either 'HØST' or 'VÅR'. Filters results by semester

        @rtype: Cerebrum.extlib.db_row.row
        @return: Database rows with the FS results (exams).
                 Fields: 
                   brukernavn (str), emnekode (str), vurdtidkode (str),
                   kandidatlopenr (int), kommislopenr (int), institusjonsnr (int),
                   versjonskode (str), vurdkombkode (str), dato (str), tid (str),
        """

        # Build query
        binds = {'subject': subject, 'year': year, }

        additional_clauses = ""
        if timecode:
            additional_clauses += "AND v2.vurdtidkode=:timecode "
            binds['timecode'] = timecode
        if typecode:
            additional_clauses += "AND v2.vurdkombkode=:typecode "
            binds['typecode'] = typecode
        if version:
            additional_clauses += "AND v2.versjonskode=:version "
            binds['version'] = version

        # TBD: How do we properly do case insensitive searching in FS?
        # nlssort(vm.emnekode, 'NLS_SORT = Latin_CI') = nlssort(:subject, 'NLS_SORT = Latin_CI')?
        # Or should we not do case insensitive searching? Is the LIKE UPPER(:subject) ok? Should we just do LIKE :subject, and require correct casing?
        query = """SELECT DISTINCT p.brukernavn, vm.emnekode, vm.vurdtidkode, 
            vm.kandidatlopenr, vm.kommislopenr, v2.institusjonsnr, v2.versjonskode,
            v2.vurdkombkode, 
            to_char(nvl(ve.dato_eksamen,v2.dato_eksamen),'yyyy-mm-dd') AS dato,
            to_char(nvl(ve.klokkeslett_fremmote_tid,v2.klokkeslett_fremmote_tid),'hh24:mi') AS tid
        FROM fs.vurdkombmelding vm
        JOIN fs.person p 
            ON (p.fodselsdato = vm.fodselsdato
            AND p.personnr = vm.personnr
            AND p.brukernavn IS NOT NULL)
        JOIN fs.vurdkombenhet ve 
            ON (ve.emnekode = vm.emnekode
            AND ve.versjonskode = vm.versjonskode
            AND ve.vurdtidkode = vm.vurdtidkode
            AND ve.arstall = vm.arstall)
        JOIN fs.vurderingskombinasjon v 
            ON (v.emnekode = ve.emnekode
            AND v.versjonskode = ve.versjonskode
            AND v.vurdkombkode = ve.vurdkombkode
            AND v.status_vurdering='J')   
        LEFT OUTER JOIN fs.vurdkombenhet v2 
        CROSS JOIN fs.eksavviklingperson e 
            ON (v2.emnekode = vm.emnekode
            AND v2.versjonskode = vm.versjonskode
            AND v2.vurdtidkode = vm.vurdtidkode
            AND v2.arstall = vm.arstall
            AND e.fodselsdato = vm.fodselsdato
            AND e.personnr = vm.personnr
            AND e.emnekode = v2.emnekode
            AND e.vurdkombkode = v2.vurdkombkode
            AND e.vurdtidkode = v2.vurdtidkode
            AND e.arstall = v2.arstall)
        WHERE NOT nvl(ve.dato_eksamen,v2.dato_eksamen) IS NULL
            AND vm.status_er_kandidat = 'J'
            AND vm.emnekode LIKE UPPER(:subject)
            AND vm.arstall = :year
            %(clauses)s
        ORDER BY 4;""" % {'clauses': additional_clauses}
        return self.fs.db.query(query, binds)


    # TODO: Move to uio/access_FS when we have confirmed that the selections are OK
    def fetch_exam_data(self, subjects, year, timecode=None):
        """ Fetches digital exams from FS. 

        @type db: Cerebrum.database.Database
        @param db: The database connection of an FS-object.

        @type subject: string
        @param subject: The subjects to fetch exam data for

        @rtype: Cerebrum.extlib.db_row.row
        @return: Database rows with the FS results (exams).
                 Fields:
                   emnekode (str), versjonskode (str), vurdkombkode (str), 
                   vurdtidkode (str), arstall (int), institusjon (int),
                   fakultet (int), institutt (int), gruppe (int), dato (str),
                   tid (str),
        """
        binds = {'year': year, 'typecode': cereconf.DIGEKS_TYPECODE}

        subjects_clause = argument_to_sql(subjects, 'v2.emnekode', binds, str)

        time_clause = ""
        if timecode:
            time_clause = "AND v2.vurdtidkode = :timecode "
            binds['timecode'] = timecode

        query = """SELECT DISTINCT v2.emnekode, v2.versjonskode, v2.vurdkombkode,
            v2.vurdtidkode, v2.arstall, v2.institusjonsnr AS institusjon,
            e.faknr_kontroll AS fakultet, e.instituttnr_kontroll AS institutt,
            e.gruppenr_kontroll AS gruppe,
            to_char(nvl(ve.dato_eksamen,v2.dato_eksamen),'yyyy-mm-dd') AS dato,
            to_char(nvl(ve.klokkeslett_fremmote_tid,v2.klokkeslett_fremmote_tid),'hh24:mi') AS tid
        FROM fs.vurdkombenhet ve
        JOIN fs.vurderingskombinasjon v 
            ON (v.emnekode = ve.emnekode
            AND v.versjonskode = ve.versjonskode
            AND v.vurdkombkode = ve.vurdkombkode
            AND v.status_vurdering = 'J')
        JOIN fs.emne e 
            ON (e.emnekode = ve.emnekode 
            AND e.institusjonsnr = ve.institusjonsnr
            AND e.versjonskode = ve.versjonskode)
        LEFT OUTER JOIN fs.vurdkombenhet v2 
            ON (v2.emnekode = ve.emnekode
            AND v2.versjonskode = ve.versjonskode
            AND v2.vurdtidkode = ve.vurdtidkode
            AND v2.arstall = ve.arstall)
        WHERE NOT nvl(ve.dato_eksamen,v2.dato_eksamen) IS NULL
            AND %(subjects)s
            AND v2.vurdkombkode LIKE :typecode
            AND v2.arstall = :year
            %(timecode)s
        ORDER BY 1;""" % {'subjects': subjects_clause,
                          'timecode': time_clause, }
        return self.fs.db.query(query, binds)




class UVDigeks(Digeks):
    """ PPU3310L specific, overrides the exam/candidate queries """

    def gen_group_name(self, identity, is_admin=False):
        if is_admin:
            return "uvdig-it"
        return "uvdig-s"

    # FIXME: PPU3310L specific data, remove
    def fetch_candidate_data(self, subject, year, timecode=None, typecode=None, version=None):
        """ Test for PPU3310L """

        binds = {'subject': subject, 'year': year, }

        additional_clauses = ""
        if timecode:
            additional_clauses += "AND ve.vurdtidkode=:timecode "
            binds['timecode'] = timecode
        if typecode:
            additional_clauses += "AND ve.vurdkombkode=:typecode "
            binds['typecode'] = typecode
        if version:
            additional_clauses += "AND ve.versjonskode=:version "
            binds['version'] = version

        query = """SELECT DISTINCT p.brukernavn, vm.emnekode, vm.vurdtidkode,
            vm.kandidatlopenr, vm.kommislopenr, ve.institusjonsnr, ve.versjonskode,
            ve.vurdkombkode, 
            to_char(ve.dato_uttak,'yyyy-mm-dd') AS dato,
            to_char(ve.klokkeslett_uttak,'hh24:mi') AS tid,
            to_char(ve.dato_innlevering,'yyyy-mm-dd') AS dato_innlevering,
            to_char(ve.klokkeslett_innlevering,'hh24:mi') AS tid_innlevering
        FROM fs.vurdkombmelding vm
        JOIN fs.person p ON (
                p.fodselsdato = vm.fodselsdato 
            AND p.personnr = vm.personnr 
            AND p.brukernavn is not null) 
        JOIN fs.vurdkombenhet ve ON (
                ve.emnekode = vm.emnekode 
            AND ve.versjonskode = vm.versjonskode 
            AND ve.vurdtidkode = vm.vurdtidkode 
            AND ve.arstall = vm.arstall 
            AND ve.vurdkombkode = vm.vurdkombkode) 
        WHERE vm.emnekode LIKE UPPER(:subject)
            AND vm.arstall = :year
            AND vm.status_er_kandidat = 'J' 
            %(clauses)s
        ORDER BY 1;""" % {'clauses': additional_clauses, }

        return self.fs.db.query(query, binds)


    # FIXME: PPU3310L specific data, remove
    def fetch_exam_data(self, subjects, year, timecode=None):
        """ Test for PPU3310L """

        typecode = ('1FAG-HO-H', '2FAG-HO-H', 'H')

        binds = {'year': year, }

        subjects_clause = argument_to_sql(subjects, 've.emnekode', binds, str)

        type_clause = ""
        if typecode:
            type_clause = 'AND ' + argument_to_sql(typecode, 've.vurdkombkode', binds, str)

        time_clause = ""
        if timecode:
            time_clause = "AND ve.vurdtidkode = :timecode "
            binds['timecode'] = timecode

        query = """SELECT ve.emnekode, ve.versjonskode, ve.vurdkombkode,
            ve.vurdtidkode, ve.arstall, ve.institusjonsnr AS institusjon,
            e.faknr_kontroll AS fakultet, e.instituttnr_kontroll AS institutt,
            e.gruppenr_kontroll AS gruppe, 
            to_char(ve.dato_uttak,'yyyy-mm-dd') AS dato, 
            to_char(ve.klokkeslett_uttak,'hh24:mi') AS tid,
            to_char(ve.dato_innlevering,'yyyy-mm-dd') AS dato_innlevering,
            to_char(ve.klokkeslett_innlevering,'hh24:mi') AS tid_innlevering
        FROM fs.vurdkombenhet ve
        JOIN fs.emne e ON (
                e.emnekode = ve.emnekode 
            AND e.institusjonsnr = ve.institusjonsnr 
            AND e.versjonskode = ve.versjonskode)
        WHERE %(subjects)s
            AND ve.arstall = :year
            %(typecode)s
            %(timecode)s
        ORDER BY 1;""" % {'subjects': subjects_clause,
                          'typecode': type_clause,
                          'timecode': time_clause, }

        return self.fs.db.query(query, binds)


class DigeksTest(Digeks):
    """ Let's us create dummy data for testing, by importing exam data from a
    prevously generated exam CSV file, and a set of usernames.

    Useful for testing the Cerebrum-related funcitons of this script
    """

    def __init__(self, exam_file, candidates=set()):
        """ Sets up the exam_file and usernames for later processing.
        Each of the candidates given as arguments, will be added to each of the
        exams from exam_file.

        @type exam_file: str
        @param exam_file: A file containing exam data, as exported by this script

        @type candidates: set
        @param candidates: A set of usernames that should be included in each
                           of the exams given in exam_file
        """

        self.exam_file = exam_file
        self.usernames = candidates

        super(DigeksTest, self).__init__([], 0) # Not neccessary to specify exam data, as that comes from the file


    def gen_group_name(self, identity, is_admin=False):
        """ Group name syntax for test exams
        """
        return "digital-eksamen-%s%s" % (('', 'adm-')[int(is_admin)], identity)


    def process_exams(self):
        """ Overloads the parent process_exams method (the method that reads
        exam/candidate info from FS, and creates the appropriate object
        representation.

        In stead of using an FS-database, we use the dummy data given in init
        to produce Exam and Candidate objects.
        """

        # Read the file
        exam_lines = []
        try:
            file = open(self.exam_file, 'r')
            exam_lines.extend(file.readlines(-1))
            file.close()
        except IOError:
            logger.error('Unable to open exam file (%s)' % self.exam_file)
            return

        def _from_line(line):
            """ Converts a line from an exams file to an Exam object
            """
            raw_fields = line.split(';')
            arg_fields = []
            try:
                # Reorder fields -> arguments
                arg_fields.append(int(raw_fields[0])) # institusjonskode
                arg_fields.append(raw_fields[1]) # emnekode
                arg_fields.append(int(raw_fields[5])) # arstall
                arg_fields.append(raw_fields[4].decode('utf-8')) # vurdtidkode
                arg_fields.append(raw_fields[3]) # vurdkombkode
                arg_fields.append(raw_fields[2]) # versjon
                arg_fields.append(raw_fields[6]) # datetime
                arg_fields.append(raw_fields[7]) # sko
                arg_fields.append(raw_fields[8]) # access/blank
            except IndexError, e:
                logger.error("Invalid data in exam_file: %s" % (str(e), ))
                return None

            try:
                return Exam(*arg_fields)
            except AssertionError, e:
                logger.warn('Unable to process exam, invalid value from exam file: %s' % str(e))
                return None


        for line in exam_lines:
            exam = _from_line(line)
            if not exam:
                continue

            if exam in self.exams:
                logger.warn("Unable to process exam, duplicate exam with key '%s'!" % exam.key())
                continue

            # Generate sequential candidate numbers and modular commission
            # numbers
            cand = 0
            comm = 0

            # Add each username to the exam
            for username in self.usernames:
                exam.addCandidate(username, cand, comm)
                cand += 1
                comm = (comm + 1) % 3
            
            # Update class sets
            self.exams.add(exam)
            self.candidates.update(exam.candidates)




# TBD: Should this be in a util file? Is it needed elsewhere?
def escape_chars(string, special='', escape='\\'):
    """ Adds escape characters to a string, L{string}. Prepends L{escape} to
    any occurance of L{escape} and L{special}.

    @type string: str
    @param string: The string to format (add escape chars to)

    @type special: iterable
    @param string: String or other iterable containing characters that
                   needs to be escaped (prepended with L{escape}).

    @type escape: str
    @param escape: The escape character(s) to use.

    @rtype: str
    @return: A string with special and escape characters escaped.
    """
    # Backslash is our escape character, so it needs to be replaced first.
    assert escape not in special
    if not string:
        return ''
    special = set(special)
    tmp = string.replace(escape, escape+escape)
    for char in special:
        tmp = tmp.replace(char, escape+char)
    return tmp

def main():

    # Setup params
    examfile = sys.stdout
    candidatefile = sys.stdout
    dryrun = False
    year = None
    semester = None
    subjects = list()
    #examcodes = list()

    opts, args = getopt.getopt(sys.argv[1:], 'hdc:e:s:y:t:')
    # TODO: Longopts
    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage(0)
        elif opt in ('-d', '--dryrun'):
            dryrun = True
        elif opt in ('-s', '--subject'):
            subjects.extend(val.split(','))
        elif opt in ('-y', '--year'):
            year = val
        elif opt in ('-t', '--semester'):
            semester = val
        elif opt in ('-c', '--candidate-file'):
            try:
                candidatedirectory = dirname(val)
                if not exists(candidatedirectory):
                    makedirs(candidatedirectory)
                candidatefile = open(val, 'w')
            except IOError:
                logger.error('Unable to open candidate file (%s)' % val)
                sys.exit(1)
        elif opt in ('-e', '--exam-file'):
            try:
                examdirectory = dirname(val)
                if not exists(examdirectory):
                    makedirs(examdirectory)
                examfile = open(val, 'w')
            except IOError:
                logger.error('Unable to open exam file (%s)' % val)
                sys.exit(2)
        else:
            logger.error("Invalid argument: '%s'" % val)
            usage(3)

    if not subjects:
        logger.info('No subjects given, defaulting to %s' % ', '.join(cereconf.DIGEKS_EXAMS))
        subjects = cereconf.DIGEKS_EXAMS

    if not year:
        year = 2013

    if not semester:
        semester = 'HØST'

    if dryrun:
        logger.info('Dryrun is enabled: No changes will be commited to Cerebrum')

    # Candidate processing

    # Handlers for the different subject codes.
    handlers = {'UV': {'class': UVDigeks,
                       'regex': re.compile('^(PPU)[0-9]+[A-Z]?$'),
                       'subjects': [], },
                'JUS': {'class': JUSDigeks,
                        'regex': re.compile('^(JUS|JUR)[0-9]+$'),
                        'subjects': [], }, }

    # TEST
    # Comment out the regular digeks section (if 'PPU', 'JUS', ...), uncomment
    # and fill in the following:
    # digeks = DigeksTest('<filename>', ('user1', 'user2', '...'))
    # where <filename> is a file with the same structure as the exams csv file
    # (e.g. a previously exported file) and <user1>, <user2>, ... is a list of
    # exiting users to use as candidates.
    #
    ## TESTING - UNCOMMENT
    #handlers = None
    #digeks = DigeksTest('exams.csv', ('fhl', ))
    #digeks.write(examfile, candidatefile)
    #digeks.rollback()
    ## TESTING

    # Distribute subjects
    for ident, handler in handlers.items():
        if not handler.get('class'):
            logger.error("No class for handler '%s', unable to process", ident)
            sys.exit(1)
        if not handler.get('regex'):
            logger.error("Invalid regex for handler '%s'" % ident)
            sys.exit(2)
        for s in subjects:
            if handler.get('regex').match(s):
                handler['subjects'].append(s)
                subjects.remove(s)

    # Leftover subjects (no handler)?
    if subjects:
        logger.error("No handler for subject(s): %s" % str(subjects))
        sys.exit(3)

    for ident, handler in handlers.items():
        cls = handler.get('class')
        subs = handler.get('subjects', [])
        if not subs:
            continue

        logger.debug("Using handler %s for subjects: %s",
                     ident, str(handler.get('subjects')))
        digeks = cls(subs, year, timecode=semester)

        logger.debug('Processing candidates...')
        digeks.write(examfile, candidatefile)

        if dryrun:
            logger.debug('Dry-run, no changes commited')
            digeks.rollback()
        else:
            digeks.commit()

    # Close file handlers
    if not examfile is sys.stdout:
        examfile.close()
    if not candidatefile is sys.stdout:
        candidatefile.close()

if __name__ == '__main__':
    main()

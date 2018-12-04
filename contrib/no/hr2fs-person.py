#!/usr/bin/env python
# -*- encoding: utf-8 -*-

# Copyright 2008-2018 University of Oslo, Norway
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

r"""
Backports data to FS from a HR system (SAP, LT or something else).

Specifically, FS.person and FS.fagperson are populated based on the
affiliations that have already been assigned in Cerebrum.

FS.person/FS.fagperson are populated based on the information from
affiliations. The exact affiliation/status set is specified on the command
line.

no/uio/lt2fsPerson.py's equivalent is:

hr2fs-person.py -p affiliation_ansatt \
                 affiliation_tilknyttet/affiliation_tilknyttet_grlaerer \
                -a system_sap \
                -o perspective_sap \
                -f affiliation_ansatt/affiliation_status_ansatt_vit \
                 affiliation_tilknyttet/affiliation_tilknyttet_grlaerer \
                --commit
"""
from __future__ import unicode_literals
from UserDict import IterableUserDict

import argparse
import logging
import sys
import traceback
from phonenumbers import NumberParseException
import six

import Cerebrum.logutils.options

from Cerebrum import Errors
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.access_FS import make_fs
from Cerebrum.utils.argutils import get_constant
from Cerebrum.utils.funcwrap import memoize
from Cerebrum.Utils import Factory

logger = logging.getLogger(__name__)


@six.python_2_unicode_compatible
class SimplePerson(IterableUserDict, object):
    """
    FS-relevant info storage.

    Give access to attributes by 'dotting in' and via a dict interface. Trap
    attempts to stuff unknown keys. This is mainly a convenience class to make
    it easier to represent a 'bag' of information about the same individual in
    a flexible and simple way.
    """

    # Add all possible keys..
    # Config to controll what we export.

    allowed_keys = ("fnr11",       # 11-siffret norsk fnr
                    "fnr6",        # 6-digit birth date part of fnr
                    "pnr",         # personnummer (5-digit part of fnr)
                    "ansattnr",    # ansattnummer
                    "birth_date",  # birth date as YYYY-MM-DD
                    "gender",      # 'M' or 'K'
                    "email",       # primary e-mail address
                    "name_first",
                    "name_last",
                    "work_title",
                    "phone",
                    "fax",
                    "mobile")

    def __keys_are_legal(self, *keys):
        for key in keys:
            if key not in self.allowed_keys:
                return False
        return True

    def __init__(self, **kwargs):
        assert self.__keys_are_legal(*kwargs.iterkeys())
        super(SimplePerson, self).__init__(**kwargs)

    def __setitem__(self, key, item):
        assert self.__keys_are_legal(key)
        super(SimplePerson, self).__setitem__(key, item)

    def __getattr__(self, name):
        if name in self.allowed_keys:
            return self.__getitem__(name)
        super(SimplePerson, self).__getattr__(name)

    def __setattr__(self, name, value):
        if name in self.allowed_keys:
            return self.__setitem__(name, value)
        super(SimplePerson, self).__setattr__(name, value)

    def update(self, dictionary=None, **kwargs):
        assert self.__keys_are_legal(*kwargs.iterkeys())
        super(SimplePerson, self).update(dictionary, **kwargs)

    def setdefault(self, key, failobj=None):
        assert self.__keys_are_legal(key)
        super(SimplePerson, self).setdefault(key, failobj)

    def __str__(self):
        return "Person(fnr={0}, {1}): birth={2}; email={3}; {4}, {5};".format(
            self.fnr11, self.gender, self.birth_date, self.email,
            self.name_last, self.name_first)


class HR2FSSyncer(object):
    """Syncs a selection of HR data to FS."""

    def __init__(self,
                 person_affiliations,
                 fagperson_affiliations,
                 authoritative_system,
                 ou_perspective,
                 db,
                 fs,
                 co,
                 use_cache=True,
                 fagperson_export_fields=None,
                 email_cache=False,
                 commit=False,
                 ansattnr_code_str='NO_SAPNO'):

        self.person_affiliations = person_affiliations
        self.fagperson_affiliations = fagperson_affiliations
        self.authoritative_system = authoritative_system
        self.ou_perspective = ou_perspective

        self.use_cache = use_cache
        self.fs = fs
        self.co = co
        self.db = db

        self.commit = commit

        self.ansattnr_code = co.EntityExternalId(ansattnr_code_str)

        # Check if ansattnr_code is valid
        try:
            int(self.ansattnr_code)
        except Errors.NotFoundError:
            raise ValueError('Invalid "ansattnr" code')

        if not self.commit:
            logger.info('Dryrun, no changes committed')
            self.fs.db.commit = self.fs.db.rollback

        self.fnr_cache = None
        self.email_cache = None
        self.title_cache = None
        self.contact_cache = None
        self.name_cache = None
        self.ansattnr_cache = None

        # We only want to export each person once.
        # Keeping track of who has been exported.
        self.exported_to_fs_person = set()
        self.exported_to_fs_fagperson = set()

        default_fagperson_export_fields = {
            'work_title': True,
            'phone': True,
            'fax': True,
            'mobile': True,
        }

        if fagperson_export_fields is None:
            # Use default (all)
            self.fagperson_fields = default_fagperson_export_fields
        else:
            if set(fagperson_export_fields.keys()) != set(
                    default_fagperson_export_fields.keys()):
                raise ValueError('Field in fagperson_export_fields')

            self.fagperson_fields = fagperson_export_fields

        if use_cache:
            # The fnr cache is used by the other caches.
            # Load it first.
            self._create_fnr_cache()
            self._create_ansattnr_cache()
            self._create_name_cache()

            if email_cache:
                self._create_email_cache()

            if (self.fagperson_fields['mobile'] or
                    self.fagperson_fields['phone'] or
                    self.fagperson_fields['fax']):

                self._create_contact_info_cache(
                    phone=self.fagperson_fields['phone'],
                    fax=self.fagperson_fields['fax'],
                    mobile=self.fagperson_fields['mobile'],
                )

            if self.fagperson_fields['work_title']:
                self._create_title_cache()

    @classmethod
    def exc_to_message(cls, exc_tuple):
        """Return a human-friendly version of exception exc."""
        exc, exc_type, tb = exc_tuple
        # oracle's exception object do some attribute manipulation and don't
        # let us poke in the exception objects easily.
        msg = traceback.format_exception_only(exc, exc_type)[0]
        msg = msg.split("\n", 1)[0]
        return six.text_type(msg)

    @classmethod
    def _selection_to_aff_dict(cls, selection_criteria):
        """Convert affiliations/status to dict for easier use in filtering."""
        aff2status = {}
        for affiliation, status in selection_criteria:
            s = aff2status.setdefault(int(affiliation), set())
            if status is not None:
                s.add(int(status))
            else:
                s.add(None)
        return aff2status

    @classmethod
    def criteria2affiliations(cls, selection_criteria):
        """Extract affiliations from selection_criteria."""
        return tuple(set(int(affiliation)
                         for affiliation, status in selection_criteria))

    def find_fnr(self, person):
        """
        Find a person's fnr.

        We require that *all* fnrs for this particular person match. Otherwise
        we risk stuffing weird fnrs into FS and wrecking havoc there. E.g.
        if SAP and FS have an fnr mismatch, this should be fixed manually
        first before affecting FS automatically from this script.
        """
        if self.fnr_cache:
            if person.entity_id in self.fnr_cache:
                return self.fnr_cache[person.entity_id]
            return None

        permissible_sources = (int(self.co.system_fs),
                               int(self.authoritative_system))
        fnrs = person.get_external_id(id_type=self.co.externalid_fodselsnr)
        # It makes no sense to look at other systems than source
        # (i.e. authoritative_system) and target (i.e. system_fs)
        numbers = set(r["external_id"] for r in fnrs
                      # IVR 2008-05-13 FIXME: API should take care of this
                      if int(r["source_system"]) in permissible_sources)

        if len(numbers) == 0:
            logger.warn("No fnrs for person_id=%s", person.entity_id)
            return None

        if len(numbers) != 1:
            logger.warn("Multiple fnrs for person_id=%s: %s",
                        person.entity_id, numbers)
            return None

        return numbers.pop()

    def find_name(self, person, name_variant):
        """Find a specific name for person."""
        if self.name_cache:
            if person.entity_id in self.name_cache:
                return self.name_cache[person.entity_id].get(int(name_variant))
            return None
        try:
            name = person.get_name(self.authoritative_system, name_variant)
            return name
        except Errors.NotFoundError:
            return None

    def find_title(self, person):
        """Find a person's work title, if any."""
        if self.title_cache:
            if person.entity_id in self.title_cache:
                return self.title_cache[person.entity_id]
            return None
        return person.get_name_with_language(name_variant=self.co.work_title,
                                             name_language=self.co.language_nb,
                                             default=None)

    def find_ansattnr(self, person):
        """Find a person's ansattnr."""
        if self.ansattnr_cache:
            if person.entity_id in self.ansattnr_cache:
                a = self.ansattnr_cache[person.entity_id]
                return a
            return None

        pe = Factory.get('Person')(self.db)
        for row in pe.list_external_ids(
                entity_id=person.entity_id,
                source_system=self.authoritative_system,
                id_type=self.ansattnr_code):
            if 'external_id' in row.keys():
                return row['external_id']
        # No ansattnr found
        return None

    def find_primary_mail_address(self, person):
        """
        Find a person's primary mail address.

        A person's primary e-mail address is defined as the primary e-mail
        address of the person's primary account.
        """
        if self.email_cache:
            if person.entity_id in self.email_cache:
                return self.email_cache[person.entity_id]
            return None

        try:
            account_id = person.get_primary_account()
            account = Factory.get("Account")(self.db)
            account.find(account_id)
            return account.get_primary_mailaddress()
        except Errors.NotFoundError:
            return None

    def find_contact_info(self, person, contact_variant):
        """Find a specific contact info (phone, fax, etc.) for a person."""
        if self.contact_cache:
            if person.entity_id in self.contact_cache:
                return self.contact_cache[person.entity_id].get(
                    int(contact_variant))

        result = person.get_contact_info(source=self.authoritative_system,
                                         type=contact_variant)
        if len(result) == 0:
            return None

        # They arrive already sorted
        value = result[0]["contact_value"]
        return value

    def find_my_affiliations(self, person, selection_criteria):
        """
        Returns the affiliations for a person matching a specified criteria.

        :param person: Cerebrum person instance
        :param selection_criteria: Affiliation selection
        :return: A set containing all affiliations for person matching the
        specified filters. Each element in the set is a tuple (ou_id, aff)
        represented as ints.
        """
        my_affiliations = set()
        for row in self.select_rows(selection_criteria,
                                    person.list_affiliations,
                                    source_system=self.authoritative_system,
                                    person_id=person.entity_id):
            my_affiliations.add((int(row["ou_id"]),
                                 int(row["affiliation"])))

        logger.debug("Person id=%s has affiliations: %s",
                     person.entity_id,
                     [(x, six.text_type(self.co.PersonAffiliation(y)))
                      for x, y in my_affiliations])
        return my_affiliations

    def find_primary_ou(self, person, selection_criteria):
        """
        Find primary OU for person.

        Unfortunately this process involves a bit of a guesswork. Potentially,
        a person may hold several employments, whereas fs.fagperson allows for
        registering one OU association only. This means we have to institute a
        choice process. A primary OU for a person is derived thus:

        - locate ou_id from account_type with the highest priority where
          affiliation matches what has been specified as
          person_affiliations/fagperson_affiliations
        - remap that ou_id to sko
        - if the sko does not exist, use the parent (recursively) until an OU
          known in FS is located.

        :param person: A Cerebrum Person instance.
        :param selection_criteria: Affiliation selection
        :return: ou_id for what we believe to be person's primary ou.
        """
        # Locate all accounts with priorities
        account = Factory.get("Account")(self.db)
        accounts = []
        just_affiliations = self.criteria2affiliations(selection_criteria)
        for row in account.list_accounts_by_type(affiliation=just_affiliations,
                                                 person_id=person.entity_id):
            accounts.append(row)

        # ... arrange them with respect to priority
        accounts.sort(lambda x, y: cmp(x['priority'], y['priority']))

        # ... and whichever matches first is the answer. IOW, whichever account
        # has the highest priority AND matches the specified affiliations for
        # the owner will be the one used to determine the primary OU. This is
        # incredibly convoluted, since we do not have a notion of OU priorities
        # for person affiliations. Perhaps we should?
        # ok?
        my_affiliations = self.find_my_affiliations(person, selection_criteria)
        ou_id = None
        for row in accounts:
            key = int(row["ou_id"]), int(row["affiliation"])
            if key in my_affiliations:
                ou_id = int(row["ou_id"])
                break

        # If that fails, chose the lowest ou_id. This is horrible, but it is in
        # reality the only way to break unknowns (i.e. what happens when no
        # account matches the specified affiliations? We cannot NOT export at
        # least some OU and the process must be deterministic).
        if ou_id is None:
            ou_id = min(x[0] for x in my_affiliations)

        # There will always be one, since we always have
        # len(my_affiliations) >= 1 (otherwise this function would not have
        # been called).
        logger.debug("Person id=%s has primary ou_id=%s", person.entity_id,
                     ou_id)
        return ou_id

    @memoize
    def find_primary_sko(self, primary_ou_id):
        """
        Find the sko corresponding to a primary_ou_id.

        In the simplest case, this is just ou.find(). However, if the sko
        found is NOT known to FS (that happens), then we follow the
        OU-hierarchy until we find a parent that *is* known to FS.
        """
        ou = Factory.get("OU")(self.db)
        try:
            ou.find(primary_ou_id)
            if self.fs.info.get_ou(ou.fakultet, ou.institutt, ou.avdeling,
                                   ou.institusjon):
                return ou.institusjon, ou.fakultet, ou.institutt, ou.avdeling
            # go up 1 level to the parent
            return self.find_primary_sko(ou.get_parent(self.ou_perspective))
        except Errors.NotFoundError:
            return None

    def _create_fnr_cache(self):
        """Create a person_id to fnr cache."""
        logger.info("Creating fnr cache")
        pe = Factory.get("Person")(self.db)

        self.fnr_cache = {
            int(x["entity_id"]): x["external_id"] for x in
            pe.list_external_ids(source_system=self.authoritative_system,
                                 id_type=self.co.externalid_fodselsnr)}

        for row in pe.list_external_ids(source_system=self.co.system_fs,
                                        id_type=self.co.externalid_fodselsnr):
            person_id = int(row["entity_id"])
            fs_fnr = row["external_id"]
            if (person_id in self.fnr_cache
                    and self.fnr_cache[person_id] != fs_fnr):
                # Mismatch between fnr in SAP and FS
                # Skipping
                logger.info("Skipping person. Mismatching fnrs for "
                            "person_id=%s", person_id)
                del self.fnr_cache[person_id]

        logger.info("Done creating fnr cache (%d entries)",
                    len(self.fnr_cache))

    def _create_email_cache(self):
        """Creates a person_id to primary mail address cache."""
        pe = Factory.get('Person')(self.db)
        logger.info("Create primary e-mail addresses cache")

        self.email_cache = {
            person_id: email for person_id, email in
            pe.list_primary_email_address(self.co.entity_person)
            if person_id in self.fnr_cache
        }

        logger.info("Done creating primary e-mail addresses cache (%d "
                    "entries)", len(self.email_cache))

    def _create_contact_info_cache(self, phone=True, fax=True, mobile=True):
        """Creates a person_id to contact info cache."""
        logger.info("Creating contact info cache")
        pe = Factory.get('Person')(self.db)

        contact_types = []

        # Only cache the needed contact types
        if phone:
            contact_types.append(self.co.contact_phone)
        if fax:
            contact_types.append(self.co.contact_fax)
        if mobile:
            contact_types.append(self.co.contact_mobile_phone)

        self.contact_cache = {}
        for contact_type in contact_types:
            for contact_info in pe.list_contact_info(
                    source_system=self.authoritative_system,
                    contact_type=contact_type):

                person_id = int(contact_info['entity_id'])
                value = contact_info['contact_value']
                if person_id in self.fnr_cache:
                    self.contact_cache.setdefault(person_id, {})[int(
                        contact_type)] = value

        logger.info('Done creating contact info cache (%d entries)',
                    len(self.contact_cache))

    def _create_name_cache(self):
        """Create a person_id to name cache."""
        pe = Factory.get('Person')(self.db)
        logger.info('Creating name cache')
        self.name_cache = {}
        for row in pe.search_person_names(
                source_system=self.authoritative_system,
                name_variant=(self.co.name_first, self.co.name_last)):

            person_id = row['person_id']
            if person_id in self.fnr_cache:

                self.name_cache.setdefault(person_id, {})[int(
                    row['name_variant'])] = row['name']

        logger.info('Done creating name cache (%d entries)',
                    len(self.name_cache))

    def _create_title_cache(self):
        """Create a person_id to work title cache."""
        logger.info("Creating work title cache")
        pe = Factory.get('Person')(self.db)
        self.title_cache = {row["entity_id"]: row["name"] for row in
                            pe.search_name_with_language(
                                entity_type=self.co.entity_person,
                                name_variant=self.co.work_title,
                                name_language=self.co.language_nb)}
        logger.info("Done creating work title cache (%d entries)",
                    len(self.title_cache))

    def _create_ansattnr_cache(self, ansattnr_code_str="NO_SAPNO"):
        """Create a personnr to ansattnr cache."""
        logger.info('Creating ansattnr cache')
        pe = Factory.get('Person')(self.db)
        ansattnr_code = self.co.EntityExternalId(ansattnr_code_str)
        # We'll do this try/except/else stuff to insure that we get an existing
        # constant.
        try:
            int(ansattnr_code)
        except Errors.NotFoundError:
            logger.error('Could not load "ansattnr" code. Skipping..')
            return

        self.ansattnr_cache = {}
        for row in pe.list_external_ids(
                source_system=self.authoritative_system,
                id_type=ansattnr_code):
            if 'external_id' in row.keys():
                self.ansattnr_cache[row['entity_id']] = row['external_id']

        logger.info('Done creating ansattnr cache (%d entries)',
                    len(self.ansattnr_cache))

    def person_to_fs_info(self, row, person):
        """Converts a person db-row to a SimplePerson object."""
        person_id = int(row['person_id'])
        person.clear()
        person.find(person_id)

        fnr = self.find_fnr(person)
        if fnr is None:
            return None

        try:
            date6, pnr = fodselsnr.del_fnr(fnr)
        except fodselsnr.InvalidFnrError:
            logger.warn(
                'Invalid fnr (person_id=%s). Person will be ignored',
                person_id)
            return None

        date = person.birth_date
        result = SimplePerson(
            **{'fnr11': fnr,
               'fnr6': date6,
               'pnr': pnr,
               'birth_date': date.strftime('%Y-%m-%d'),
               'gender': person.gender == self.co.gender_male and 'M' or 'K',
               'email': self.find_primary_mail_address(person),
               'phone': self.find_contact_info(person, self.co.contact_phone),
               ''
               'fax': self.find_contact_info(person, self.co.contact_fax),
               'ansattnr': self.find_ansattnr(person),
               'mobile': self.find_contact_info(person,
                                                self.co.contact_mobile_phone)
               })

        for name_type, attr_name in ((self.co.name_first, 'name_first'),
                                     (self.co.name_last, 'name_last'),):
            result[attr_name] = self.find_name(person, name_type)

        if self.fagperson_fields['work_title']:
            # ... and work title
            result['work_title'] = self.find_title(person)
            if None in (result['name_first'], result['name_last']):
                logger.warn('Missing name for fnr=%s', fnr)
                return None

        return result

    def select_rows(self, selection_criteria, row_generator, **kw_args):
        """
        Create a iterator over specific affiliations.

        The affiliations are specified by L{selection_criteria}. Only the rows
        with these affiliations/statuses are returned.

        :param selection_criteria: Affiliation selection
        :param row_generator: Something which generates db_rows we can filter.
        This is typically a method in the Person or Account class.
        :param kw_args: Additional arguments to pass to row_generator. We allow
        'person_id' and 'source_system' only as keys. The meaning of these
        parameters depends on the row_generator.
        :return: Generator yielding db-rows matching the specified filters in
        Cerebrum.
        """
        logger.debug('Selecting rows')
        just_affiliations = self.criteria2affiliations(selection_criteria)
        affiliation2status = self._selection_to_aff_dict(selection_criteria)

        # assert set(kw_args.keys()).issubset({"source_system", "person_id"})

        for row in row_generator(affiliation=just_affiliations, **kw_args):
            # even though a person matches on affiliation, we must make sure
            # (s)he matches on the aff status as well.
            aff_status = int(row["status"])
            aff = int(row["affiliation"])

            if not (None in affiliation2status[aff] or
                    aff_status in affiliation2status[aff]):
                continue

            yield row
        logger.debug('Done selecting rows')

    def select_fs_candidates(self, selection_criteria):
        """
        Find all people to be exported to FS.

        :param selection_criteria: Affiliation selection
        :return: A dict mapping person_ids to information chunks that will be
        pushed to FS. The information chunks support a dict interface to give
        easier access to several attributes
        """
        logger.debug('Selecting persons to export')
        result = {}
        person = Factory.get("Person")(self.db)
        rows = list(self.select_rows(selection_criteria,
                                     person.list_affiliations,
                                     source_system=self.authoritative_system))
        logger.debug("%d db-rows match %s criteria", len(rows),
                     [six.text_type(x) for x in selection_criteria])

        for row in rows:
            person_id = int(row["person_id"])
            if person_id in result:
                continue

            info_object = self.person_to_fs_info(row, person)
            if info_object is not None:
                result[person_id] = info_object

        logger.debug('Found %d persons to export to fs', len(result))
        return result

    def export_person(self, person_id, person_data):
        """
        Push information to FS.person.

        Register information in FS about a person with person_id. The
        necessary entries are created in FS, if they did not exist beforehand.

        :param person_id: Cerebrum person_id
        :param person_data: person data to export
        :return:
        """
        if person_id in self.exported_to_fs_person:
            # Person already exported in this run. Skipping
            logger.debug('Skipping. Person: {0} already exported'.format(
                person_id))
            return

        if 'ansattnr' not in person_data:
            person_data.ansattnr = None
        if not self.fs.person.get_person(person_data.fnr6, person_data.pnr):
            try:
                logger.debug("Adding new entry to fs.person id=%s", person_id)

                self.fs.person.add_person(person_data.fnr6, person_data.pnr,
                                          person_data.name_first,
                                          person_data.name_last,
                                          person_data.email,
                                          person_data.gender,
                                          person_data.birth_date,
                                          person_data.ansattnr)

            except (self.db.IntegrityError, self.db.DatabaseError):
                logger.error("Insertion of id=%s (email=%s) failed: %s",
                             person_id, person_data.email,
                             self.exc_to_message(sys.exc_info()))

        # Here we inject the ansattnummer for people that are already in the
        # DB.
        elif 'ansattnr' in person_data and person_data.ansattnr is not None:
            try:
                self.fs.person.set_ansattnr(person_data.fnr6, person_data.pnr,
                                            person_data.ansattnr)
            except self.db.IntegrityError:
                logger.error("Setting of ansattnr=%s on id=%d failed: %s",
                             person_data.ansattnr, person_id,
                             self.exc_to_message(sys.exc_info()))

        self.exported_to_fs_person.add(person_id)

    def export_fagperson(self, person_id, person_data, selection_criteria):
        """
        Push information to FS.fagperson.

        Register information in FS.fagperson about a person with L{person_id}.
        The necessary entries are created in FS, if they did not exist
        beforehand.

        :param person_id: person_id (in Cerebrum)
        :param person_data: data to be exported
        :param selection_criteria: selection criteria
        :return: None
        """
        if person_id in self.exported_to_fs_fagperson:
            # Person already exported in this run. Skipping
            logger.debug('Skipping. Fagperson: {0} already exported'.format(
                person_id))
            return

        # Basically, all we have to do is to push changes to FS.person,
        # calculate primary OU and push changes to FS.fagperson.
        self.export_person(person_id, person_data)
        person = Factory.get("Person")(self.db)
        person.find(person_id)
        primary_ou_id = self.find_primary_ou(person, selection_criteria)

        primary_sko = self.find_primary_sko(primary_ou_id)
        logger.debug("Person person_id=%d has primary sko=%s",
                     person_id, primary_sko)
        if primary_sko is None:
            logger.warn("Cannot locate primary OU for person (id=%s) "
                        "No changes will be sent to FS", person.entity_id)
            return

        fs_info = self.fs.person.get_fagperson(person_data.fnr6,
                                               person_data.pnr)

        values = {"fodselsdato": person_data.fnr6,
                  "personnr": person_data.pnr,
                  "adrlin1_arbeide": None,
                  "adrlin2_arbeide": None,
                  "postnr_arbeide": None,
                  "adrlin3_arbeide": None,
                  "arbeidssted": None,
                  "institusjonsnr_ansatt": primary_sko[0],
                  "faknr_ansatt": primary_sko[1],
                  "instituttnr_ansatt": primary_sko[2],
                  "gruppenr_ansatt": primary_sko[3],
                  }

        if self.fagperson_fields['work_title']:
            values['stillingstittel_norsk'] = person_data.work_title

        if not fs_info:
            logger.debug("Pushing new entry to FS.fagperson, pid=%s",
                         person_id)
            try:
                # According to mgrude, this field is to be set to 'N' for new
                # entries and left untouched for already existing entries.
                values["status_aktiv"] = 'N'
                self.fs.person.add_fagperson(**values)

            except self.db.IntegrityError:
                logger.info("Failed updating person %s: %s",
                            person_id, self.exc_to_message(sys.exc_info()))
        else:
            logger.debug("Fagperson %s exists in FS", person_id)
            tmp = fs_info[0]
            if any(values[k] != tmp[k] for k in values.keys()):
                logger.debug("Updating data for fagperson %s", person_id)
                self.fs.person.update_fagperson(**values)
            else:
                logger.debug("Fagperson %s does not need updating",
                             person_id)

        instno = primary_sko[0]
        if self.fagperson_fields['phone']:
            self._export_phone(person_data, person_data.phone, 'ARB', instno)

        if self.fagperson_fields['fax']:
            self._export_phone(person_data, person_data.fax, 'FAXS', instno)

        if self.fagperson_fields['mobile']:
            self._export_phone(person_data, person_data.mobile, 'MOBIL',
                               instno)

        self.exported_to_fs_fagperson.add(person_id)

    def _export_phone(self, person_data, nr, phone_type, instno):

        contact = self.fs.person.get_telephone(person_data.fnr6,
                                               person_data.pnr,
                                               instno, phone_type,
                                               fetchall=True)
        if contact:
            if contact[0]['telefonlandnr']:
                contact = '+' + contact[0]['telefonlandnr'] + contact[0][
                    'telefonnr']
            else:
                contact = contact[0]['telefonnr']
        try:
            if nr and not contact:
                logger.debug("Setting phone (%s) to %s", phone_type, nr)
                self.fs.person.add_telephone(person_data.fnr6,
                                             person_data.pnr, phone_type, nr)

            elif nr and contact != nr:
                logger.debug("Updating phone (%s): %s --> %s",
                             phone_type, contact, nr)
                self.fs.person.update_telephone(person_data.fnr6,
                                                person_data.pnr, phone_type,
                                                nr)
        except (ValueError, NumberParseException) as e:
            logger.error("Could not set phone (%s) %s: %s",
                         phone_type, nr, e)

    def sync_to_fs(self):
        """Writes all updates to FS."""
        logger.debug('Start syncing to FS')
        logger.debug('Scanning data from source=%s (perspective=%s)',
                     self.authoritative_system, self.ou_perspective)

        people = self.select_fs_candidates(self.person_affiliations)

        for person_id, person_data in people.iteritems():
            self.export_person(person_id, person_data)

        people = self.select_fs_candidates(self.fagperson_affiliations)
        for person_id, person_data in people.iteritems():
            self.export_fagperson(person_id, person_data,
                                  self.fagperson_affiliations)


def main():
    """Argparser and script run."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '-p', '--person-affiliations',
        dest='person_affs',
        action='append',
        required=True,
        help='List of person affiliations to use. On the form <affiliation> '
             'or <affiliation>/<status>. '
             'affiliation_ansatt/affiliation_status_ansatt_vit'
    )
    parser.add_argument(
        '-f', '--fagperson-affiliation',
        dest='fagperson_affs',
        action='append',
        required=True,
        help='TODO Fagperson aff'
    )
    parser.add_argument(
        '-a', '--authoritative-system',
        dest='authoritative_system',
        required=True,
        help='TODO Authoritative system'
    )
    parser.add_argument(
        '-o', '--ou-perspective',
        dest='ou_perspective',
        required=True,
        help='TODO The OU perspective'
    )
    parser.add_argument(
        '-e', '--fagperson-fields',
        dest='fagperson_fields',
        nargs='+',
        help='Fagperson data fields to be exported. Valid inputs are: '
             'work_title, phone, fax, mobile. Default is all'
    )
    parser.add_argument(
        '-n', '--no-extra-fields',
        action='store_true',
        dest='no_extra_fields',
        help='Do not export any of the "extra" fagperson fields (work_title, '
             'phone, fax, mobile)'
    )
    parser.add_argument(
        '-m', '--with-cache-email',
        action='store_true',
        dest='email_cache',
        help='Cache e-mail addresses'
    )
    parser.add_argument(
        '-c', '--commit',
        action='store_true',
        dest='commit',
        help='Write data to FS'
    )

    db = Factory.get("Database")()
    co = Factory.get("Constants")(db)
    fs = make_fs()

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf('cronjob', args)
    logger.info('START {0}'.format(parser.prog))

    def parse_affiliation_string(affiliation):
        """Splits string into aff and status."""
        if affiliation is None:
            return None

        if len(affiliation.split("/")) == 1:
            aff, status = (
                co.human2constant(affiliation, co.PersonAffiliation),
                None)

        elif len(affiliation.split("/")) == 2:
            aff, status = affiliation.split("/")
            aff, status = (co.human2constant(aff, co.PersonAffiliation),
                           co.human2constant(status, co.PersonAffStatus))

            if aff is None or status is None:
                return None
        else:
            logger.error("Wrong syntax for affiliation %s", affiliation)
            return None

        return aff, status

    person_affs = [parse_affiliation_string(x) for x in args.person_affs]
    fagperson_affs = [parse_affiliation_string(x) for x in
                      args.fagperson_affs]

    ou_perspective = get_constant(db, parser, co.OUPerspective,
                                  args.ou_perspective)
    authoritative_system = get_constant(db, parser, co.AuthoritativeSystem,
                                        args.authoritative_system)

    if ou_perspective is None:
        logger.error('No valid OU perspective given')
        return None

    if authoritative_system is None:
        logger.error('No valid authoritative system given')
        return None

    if args.commit:
        logger.info('Changes will be committed')
    else:
        logger.info('Dryrun mode, no changes will be committed')

    valid_fagperson_fields = ['work_title', 'phone', 'fax', 'mobile']

    if args.no_extra_fields:
        fagperson_fields = {x: False for x in valid_fagperson_fields}
    elif args.fagperson_fields:
        fagperson_fields = {x: False for x in valid_fagperson_fields}
        for field in args.fagperson_fields:
            if field in fagperson_fields:
                fagperson_fields[field] = True
    else:
        fagperson_fields = None

    syncer = HR2FSSyncer(person_affs, fagperson_affs, authoritative_system,
                         ou_perspective, db, fs, co,
                         fagperson_export_fields=fagperson_fields,
                         use_cache=True, email_cache=args.email_cache,
                         commit=args.commit)

    syncer.sync_to_fs()

    if args.commit:
        logger.info('Committing FS db')
        fs.db.commit()
    else:
        logger.info('Rolling back changes in the FS db')
        fs.db.rollback()
    logger.info('Done syncing to FS')


if __name__ == "__main__":
    main()

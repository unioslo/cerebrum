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

"""This scripts backports some of the data to FS from the authoritative human
resources system (SAP, LT or something else).

Specifically, FS.person and FS.fagperson are populated based on the
affiliations that have already been assigned in Cerebrum.

FS.person/FS.fagperson are populated based on the information from
affiliations. The exact affiliation/status set is specified on the command
line.

no/uio/lt2fsPerson.py's equivalent is:

hr2fs-person.py -p affiliation_ansatt \
                -p affiliation_tilknyttet/affiliation_tilknyttet_grlaerer \
                -a system_sap \
                -o perspective_sap \
                -f affiliation_ansatt/affiliation_status_ansatt_vit \
                -f affiliation_tilknyttet/affiliation_tilknyttet_grlaerer \
                --dryrun
"""
from UserDict import IterableUserDict
import getopt
import sys
import traceback
import six

import cerebrum_path

from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.access_FS import make_fs
from Cerebrum import Errors
from Cerebrum.utils.funcwrap import memoize
from Cerebrum import database


logger = Factory.get_logger("cronjob")
constants = Factory.get("Constants")()
database = Factory.get("Database")()


@six.python_2_unicode_compatible
class SimplePerson(IterableUserDict, object):
    """FS-relevant info storage.

    Give access to attributes by 'dotting in' and via a dict interface. Trap
    attempts to stuff unknown keys. This is mainly a convenience class to make
    it easier to represent a 'bag' of information about the same individual in
    a flexible and simple way.
    """

    allowed_keys = ("fnr11",       # 11-siffret norsk fnr
                    "fnr6",        # 6-digit birth date part of fnr
                    "pnr",         # personnummer (5-digit part of fnr)
                    "ansattnr",        # ansattnummer
                    "birth_date",  # birth date as YYYY-MM-DD
                    "gender",      # 'M' or 'K'
                    "email",       # primary e-mail address
                    "name_first",
                    "name_last",
                    "work_title",
                    "phone",
                    "fax")

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
        return "Person(fnr=%s, %s): birth=%s; email=%s; %s, %s;" % (
            self.fnr11, self.gender, self.birth_date, self.email,
            self.name_last, self.name_first)


def exc2message(exc_tuple):
    """Return a human-friendly version of exception exc.

    exc_tuple represents the exception to typeset, as returned by
    sys.exc_info().
    """

    exc, exc_type, tb = exc_tuple
    # oracle's exception object do some attribute manipulation and don't let us
    # poke in the exception objects easily.
    msg = traceback.format_exception_only(exc, exc_type)[0]
    msg = msg.split("\n", 1)[0]
    return six.text_type(msg)


def _selection2aff_dict(selection_criteria):
    """Convert a bunch of affiliations/status to a dict that is easier to use
       to filter people.

    @param selection_criteria: cf L{make_fs_updates}.

    @rtype: dict (from int to sequence of int)
    @return:
      A dictionary mapping affiliations to sequences of affiliation
      statuses. This way we can look up easily whether a given (aff, status)
      pair qualifies a person to be selected. If no status is specified in a
      pair, None will be the status value (effectively meaning that people
      will be filtered based on affiliation only).
    """

    aff2status = dict()
    for affiliation, status in selection_criteria:
        s = aff2status.setdefault(int(affiliation), set())
        if status is not None:
            s.add(int(status))
        else:
            s.add(None)

    return aff2status


def criteria2affiliations(selection_criteria):
    """Extract affiliations from L{selection_criteria}.

    @param selection_criteria: cf L{make_fs_updates}.

    @rtype: tuple (of ints)
    @return:
      A tuple of affiliations extracted from L{selection_criteria}.
    """

    return tuple(set(int(affiliation)
                     for affiliation, status in selection_criteria))


def find_fnr(person, authoritative_system):
    """Locate person's fnr.

    We require that *all* fnrs for this particular person match. Otherwise we
    risk stuffing weird fnrs into FS and wrecking havoc there. E.g. if SAP and
    FS have an fnr mismatch, this should be fixed manually first before
    affecting FS automatically from this script.

    @type person: Factory.get('Person') instance
    @param person:
      A person proxy associated with a specific person in Cerebrum.

    @param authoritative_system: Cf. L{make_fs_updates}.

    @rtype: basestring or None
    @return:
      fnr (11 digits in a string) or None, if nothing suitable is found.
    """

    permissible_sources = (int(constants.system_fs), int(authoritative_system))
    fnrs = person.get_external_id(id_type=constants.externalid_fodselsnr)
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


def find_name(person, name_variant, authoritative_system):
    """Locate a specific name for person

    @type person: Factory.get('Person') instance
    @param person:
      A person proxy associated with a specific person in Cerebrum.

    @type name_variant: PersonName instance
    @param name_variant:
      A specific name type to look for.

    @param authoritative_system: Cf. L{make_fs_updates}.
      Ideally SSLO should take care of this.

    @rtype: basestring or None
    @return:
      Name of the specified type or None, if nothing suitable is found.
    """

    try:
        name = person.get_name(authoritative_system, name_variant)
        return name
    except Errors.NotFoundError:
        return None


def find_title(person):
    """Locate person's work title, if any exists."""

    return person.get_name_with_language(name_variant=constants.work_title,
                                         name_language=constants.language_nb,
                                         default=None)


def find_primary_mail_address(person):
    """Locate person's primary e-mail address.

    A person's primary e-mail address is defined as the primary e-mail address
    of the person's primary account.

    NB! This could be expensive (a whole bunch of 'expensive' objects are
    created).

    @type person: Factory.get('Person') instance
    @param person:
      A person proxy associated with a specific person in Cerebrum.

    @rtype: basestring or None
    @return:
      E-mail address (username@domain) or None if no suitable address is found.
    """

    try:
        account_id = person.get_primary_account()
        account = Factory.get("Account")(database)
        account.find(account_id)
        return account.get_primary_mailaddress()
    except Errors.NotFoundError:
        return None



def find_contact_info(person, contact_variant, authoritative_system):
    """Locate a specific contact info (phone, fax, etc.) entry for person.

    @type person: Factory.get('Person') instance
    @param person:
      A person proxy associated with a specific person in Cerebrum.

    @type contact_variant: ContactInfo instance
    @param name_variant:
      A specific contact type to look for.

    @param authoritative_system: Cf. L{make_fs_updates}.

    @rtype: basestring or None
    @return:
      Contact info of the specified type or None, if nothing suitable is
      found.
    """

    result = person.get_contact_info(source=authoritative_system,
                                     type=contact_variant)
    if len(result) == 0:
        return None

    # They arrive already sorted
    value = result[0]["contact_value"]
    return value


def find_my_affiliations(person, selection_criteria, authoritative_system):
    """Return a list of affiliations for person matching the specified
    criteria.

    @type person: Factory.get('Person') instance
    @param person:
      A person proxy associated with a specific person in Cerebrum.

    @param selection_criteria: Cf. L{make_fs_updates}

    @param authoritative_system: Cf. L{make_fs_updates}.

    @rtype: set of tuples of ints
    @return:
      A set containing all affiliations for person matching the specified
      filters. Each element in the set is a tuple (ou_id, aff) represented as
      ints.
    """

    my_affiliations = set()
    for row in select_rows(selection_criteria,
                           person.list_affiliations,
                           source_system=authoritative_system,
                           person_id=person.entity_id):
        my_affiliations.add((int(row["ou_id"]),
                             int(row["affiliation"])))

    logger.debug("Person id=%s has affiliations: %s",
                 person.entity_id,
                 [(x, six.text_type(constants.PersonAffiliation(y)))
                  for x, y in my_affiliations])
    return my_affiliations


def find_primary_ou(person, selection_criteria, authoritative_system):
    """Find primary OU for person.

    Unfortunately this process involves a bit of a guesswork. Potentially, a
    person may hold several employments, whereas fs.fagperson allows for
    registering one OU association only. This means we have to institute a
    choice process. A primary OU for a person is derived thus:

    - locate ou_id from account_type with the highest priority where
      affiliation matches what has been specified as
      person_affiliations/fagperson_affiliations in L{make_fs_updates}.
    - remap that ou_id to sko
    - if the sko does not exist, use the parent (recursively) until an OU
      known in FS is located.

    @type person: Factory.get('Person') instance
    @param person:
      A person proxy associated with a specific person in Cerebrum.

    @param selection_criteria: Cf. L{make_fs_updates}

    @param authoritative_system: Cf. L{make_fs_updates}.

    @rtype: int
    @return:
      ou_id for what is calculated to be person's primary ou.
    """

    # Locate all accounts with priorities
    account = Factory.get("Account")(database)
    accounts = list()
    just_affiliations = criteria2affiliations(selection_criteria)
    for row in account.list_accounts_by_type(affiliation=just_affiliations,
                                             person_id=person.entity_id):
        accounts.append(row)

    # ... arrange them with respect to priority
    accounts.sort(lambda x, y: cmp(x['priority'], y['priority']))

    # ... and whichever matches first is the answer. IOW, whichever account
    # has the highest priority AND matches the specified affiliations for the
    # owner will be the one used to determine the primary OU. This is
    # incredibly convoluted, since we do not have a notion of OU priorities
    # for person affiliations. Perhaps we should?
    my_affiliations = find_my_affiliations(person, selection_criteria,
                                           authoritative_system)
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

    # There will always be one, since we always have len(my_affiliations) >= 1
    # (otherwise this function would not have been called).
    assert ou_id is not None
    logger.debug("Person id=%s has primary ou_id=%s", person.entity_id, ou_id)
    return ou_id


@memoize
def find_primary_sko(primary_ou_id, fs, ou_perspective):
    """Locate sko corresponding to primary_ou_id.

    In the simplest case, this is just ou.find(). However, if the sko found is
    NOT known to FS (that happens), then we follow the OU-hierarchy until we
    find a parent that *is* known to FS.

    @type primary_ou_id: int
    @param primary_ou_id:
      ou_id that we seek to remap to a sko.

    @param fs: Cf. L{make_fs_updates}.

    @param ou_perspective: Cf. L{make_fs_updates}.
    """

    ou = Factory.get("OU")(database)
    try:
        ou.find(primary_ou_id)
        if fs.info.get_ou(ou.fakultet, ou.institutt, ou.avdeling,
                          ou.institusjon):
            return ou.institusjon, ou.fakultet, ou.institutt, ou.avdeling
        # go up 1 level to the parent
        return find_primary_sko(ou.get_parent(ou_perspective), fs,
                                ou_perspective)
    except Errors.NotFoundError:
        return None


def _populate_caches(selection_criteria, authoritative_system, email_cache,
                     ansattnr_code_str="NO_SAPNO"):
    """This is a performance enhacing hack.

    Looking things up on per-person basis takes too much time (about a
    fivefold increase in the running time). The idea is to create a bunch of
    caches that all of the find_-methods in this module can use. Naturally, we
    do not want to hack find_-methods so this function creates closures that
    consult the caches and re-binds global find_* names to such
    closures. Everyone wins :)

    @param selection_criteria: Cf. L{make_fs_updates}

    @param authoritative_system: Cf. L{make_fs_updates}.

    @param email_cache:
      Controls whether we want to cache e-mail addresses. Caching them relies
      on the Email module, and some installations do not have it/use it.

    @param ansattnr_code:
      The textual code used to fetch the constant representing ansattnummer.
      This should be \"NO_SAPNO\" for all higher education instances, so this
      is set by default.
    """

    # Pre-load fnrs for everyone
    logger.debug("Preloading fnrs...")
    person = Factory.get("Person")(database)
    _person_id2fnr = dict()
    for row in person.list_external_ids(source_system=authoritative_system,
                                        id_type=constants.externalid_fodselsnr):
        _person_id2fnr[int(row["entity_id"])] = row["external_id"]
    for row in person.list_external_ids(source_system=constants.system_fs,
                                        id_type=constants.externalid_fodselsnr):
        p_id = int(row["entity_id"])
        fnr = row["external_id"]
        if p_id in _person_id2fnr and _person_id2fnr[p_id] != fnr:
            #
            # These errors happen to often to be classified as errors(). We
            # cannot influence fnr values in authoritative systems anyway.
            logger.info("Mismatching fnrs for person_id=%s: %s=%s, %s=%s",
                        p_id, authoritative_system, _person_id2fnr[p_id],
                        constants.system_fs, fnr)
            # cannot allow the mapping to be there
            del _person_id2fnr[p_id]
    global find_fnr
    find_fnr = lambda p, auth: _person_id2fnr.get(p.entity_id)
    logger.debug("Done preloading fnrs (%d entries)", len(_person_id2fnr))

    # Preload primary e-mail addresses...
    if email_cache:
        logger.debug("Preloading primary e-mail addresses")
        _person_id2email = dict()

        for entry in person.list_primary_email_address(constants.entity_person):
            p_id, email = entry
            if p_id in _person_id2fnr:
                _person_id2email[p_id] = email

        global find_primary_mail_address
        find_primary_mail_address = lambda p: _person_id2email.get(p.entity_id)
        logger.debug("Done preloading e-mail addresses (%d entries)",
                     len(_person_id2email))

    logger.debug("Preloading contact info")
    _person_id2contact = dict()
    for contact_type in (constants.contact_phone, constants.contact_fax):
        for row in person.list_contact_info(source_system=authoritative_system,
                                            contact_type=contact_type):
            p_id = int(row["entity_id"])
            value = row["contact_value"]
            if p_id not in _person_id2fnr:
                continue

            _person_id2contact.setdefault(p_id, {})[int(contact_type)] = value
    global find_contact_info
    find_contact_info = lambda p, c, a: _person_id2contact.get(p.entity_id,
                                                               {}).get(int(c))
    logger.debug("Done preloading contact info (%d entries)",
                 len(_person_id2contact))

    logger.debug("Preloading name information")
    _person_id2name = dict()
    for row in person.search_person_names(source_system=authoritative_system,
                                          name_variant=(constants.name_first,
                                                        constants.name_last)):
        p_id = row["person_id"]
        if p_id not in _person_id2fnr:
            continue

        _person_id2name.setdefault(p_id, {})[int(row["name_variant"])] = row["name"]

    global find_name
    find_name = lambda p, n, a: _person_id2name.get(p.entity_id,
                                                    {}).get(int(n))

    logger.debug("Preloading title information")
    _person_id2title = dict((row["entity_id"], row["name"])
                            for row in
                            person.search_name_with_language(
                                entity_type=constants.entity_person,
                                name_variant=constants.work_title,
                                name_language=constants.language_nb))
    global find_title
    find_title = lambda p: _person_id2title.get(p.entity_id)
    logger.debug("Done preloading name information (%d entries)",
                 len(_person_id2name))

    logger.debug("Preloading ansattnr information")
    ansattnr_code = constants.EntityExternalId(ansattnr_code_str)
    # We'll do this try/except/else stuff to insure that we get an existing
    # constant.
    try:
        int(ansattnr_code)
    except Errors.NotFoundError:
        _fnr2ansattnr = dict()
    else:
        eid2fnr = person.getdict_fodselsnr()
        _fnr2ansattnr = dict()

        # External employees may be missing external_id 'fnr', and will throw
        # errors. These should not be exported anyway, and will be skipped.
        for row in person.list_external_ids(
                source_system=authoritative_system,
                id_type=ansattnr_code):
            try:
                _fnr2ansattnr[eid2fnr[row['entity_id']]] = row['external_id']
            except:
                pass

    global find_ansattnr
    find_ansattnr = lambda p: _fnr2ansattnr.get(p)
    logger.debug("Done preloading ansattnr information (%d entries)",
                 len(_fnr2ansattnr))


def person2fs_info(row, person, authoritative_system):
    """Convert a db-row with person id to a chunk of data to be exported to FS
    for that particular person.

    @type row: db_row instance.
    @param row:
      A row containing a person_id and affiliation information for a
      candidate to be output.

    @type person: a Factory.get('Person') instance.
    @param person:
      DB person proxy.

    @param authoritative_system: Cf. L{make_fs_updates}.

    @rtype: SimplePerson instance or None.
    @return:
      A SimplePerson object with all the allowed_keys filled in with
      appropriate data. If names or fnr are missing, None is returned (we
      cannot proceed without a certain minimum of information about a person).
    """

    person_id = int(row['person_id'])
    person.clear()
    person.find(person_id)

    fnr = find_fnr(person, authoritative_system)
    if fnr is None:
        return None

    try:
        date6, pnr = fodselsnr.del_fnr(fnr)
    except fodselsnr.InvalidFnrError:
        logger.warn('Invalid fnr: %s (person_id=%s). Person will be ignored', \
                    fnr, person_id)
        return None

    date = person.birth_date
    result = SimplePerson(**{'fnr11': fnr,
                             'fnr6': date6,
                             'pnr': pnr,
                             'birth_date': date.strftime('%Y-%m-%d'),
                             'gender': person.gender == constants.gender_male
                                         and 'M' or 'K',
                             'email': find_primary_mail_address(person),
                             'phone': find_contact_info(person,
                                                        constants.contact_phone,
                                                        authoritative_system),
                             'fax': find_contact_info(person,
                                                      constants.contact_fax,
                                                      authoritative_system),
                             'ansattnr': find_ansattnr(fnr),
                             })
    # Slurp in names...
    for name_type, attr_name in ((constants.name_first, 'name_first'),
                                 (constants.name_last, 'name_last'),):
        result[attr_name] = find_name(person, name_type, authoritative_system)

    # ... and work title
    result['work_title'] = find_title(person)
    if None in (result['name_first'], result['name_last']):
        logger.warn('Missing name for fnr=%s', fnr)
        return None

    return result


def select_rows(selection_criteria, row_generator, **kw_args):
    """Return a iterator over specific affiliations.

    The affiliations are specified by L{selection_criteria}. Only the rows
    with these affiliations/statuses are returned.

    @param selection_criteria: Cf. L{make_fs_updates}

    @type person_id: int or None
    @param person_id:
      Specific person for whom the affiliations are to be collected. If None
      is specified, only selection_criteria will be used for filtering.

    @type row_generator: a generator or a callable.
    @param row_generator:
      Something which generates db_rows we can filter. This is typically a
      method i Person or account class or somesuch.

    @param kw_args:
      Additional arguments to pass to L{row_generator}. We allow 'person_id'
      and 'source_system' only as keys. The meaning of these parameters
      depends on the L{row_generator}.

    @rtype: generator
    @return:
      Generator yielding db-rows matching the specified filters in Cerebrum.
    """

    just_affiliations = criteria2affiliations(selection_criteria)
    affiliation2status = _selection2aff_dict(selection_criteria)
    assert set(kw_args.keys()).issubset(set(("source_system", "person_id")))

    for row in row_generator(affiliation=just_affiliations, **kw_args):
        # even though a person matches on affiliation, we must make sure (s)he
        # matches on the aff status as well.
        aff_status = int(row["status"])
        aff = int(row["affiliation"])

        if not (None in affiliation2status[aff] or
                aff_status in affiliation2status[aff]):
            continue

        yield row


def select_FS_candidates(selection_criteria, authoritative_system):
    """Collect all people to be exported to FS.

    @param selection_criteria: Cf. L{make_fs_updates}

    @param authoritative_system: Cf. L{make_fs_updates}.

    @rtype: dict
    @return:
      A dict mapping person_ids to information chunks that will be pushed to
      FS. The information chunks support a dict interface to give easier
      access to several attributes
    """

    result = dict()
    person = Factory.get("Person")(database)
    rows = list(select_rows(selection_criteria,
                            person.list_affiliations,
                            source_system=authoritative_system))
    logger.debug("%d db-rows match %s criteria",
                 len(rows),
                 list(six.text_type(x) for x in selection_criteria))
    for row in rows:
        person_id = int(row["person_id"])
        if person_id in result:
            continue

        info_object = person2fs_info(row, person, authoritative_system)
        if info_object is not None:
            result[person_id] = info_object

    return result


def export_person(person_id, info_chunk, fs):
    """Push information to FS.person.

    Register information in FS about a person with L{person_id}. The necessary
    entries are created in FS, if they did not exist beforehand.

    @type person_id: int
    @param person_id: person_id (in Cerebrum) whom L{info_chunk} describes.

    @param info_chunk: cf L{select_FS_candidates}

    @param fs: cf L{make_fs_updates}.
    """

    data = info_chunk
    if not data.has_key('ansattnr'):
        data.ansattnr = None
    if not fs.person.get_person(data.fnr6, data.pnr):
        try:
            logger.debug("Adding new entry to fs.person id=%s (fnr=%s)",
                         person_id, data["fnr11"])
            fs.person.add_person(data.fnr6, data.pnr, data.name_first,
                                 data.name_last, data.email, data.gender,
                                 data.birth_date, data.ansattnr)

        except database.IntegrityError:
            logger.info("Insertion of id=%s (fnr=%s, email=%s) failed: %s",
                        person_id, data.fnr11, data.email,
                        exc2message(sys.exc_info()))
    # Here we inject the ansattnummer for people that are already in the DB.
    elif data.has_key('ansattnr') and data.ansattnr is not None:
        try:
            fs.person.set_ansattnr(data.fnr6, data.pnr, data.ansattnr)
        except database.IntegrityError:
            logger.info("Setting of ansattnr=%d on id=%d failed: %s",
                        data.ansattnr, person_id, exc2message(sys.exc_info()))


def export_fagperson(person_id, info_chunk, selection_criteria, fs,
                     authoritative_system, ou_perspective):
    """Push information to FS.fagperson.

    Register information in FS.fagperson about a person with L{person_id}. The
    necessary entries are created in FS, if they did not exist beforehand.

    @type person_id: int
    @param person_id: person_id (in Cerebrum) whom L{info_chunk} describes.

    @param info_chunk: cf L{select_FS_candidates}

    @param selection_criteria: cf L{make_fs_updates}.

    @param fs: cf L{make_fs_updates}.

    @param authoritative_system: cf L{make_fs_updates}.

    @param ou_perspective: cf L{make_fs_updates}.
    """

    # Basically, all we have to do is to push changes to FS.person, calculate
    # primary OU and push changes to FS.fagperson.
    export_person(person_id, info_chunk, fs)

    person = Factory.get("Person")(database)
    person.find(person_id)
    primary_ou_id = find_primary_ou(person, selection_criteria,
                                    authoritative_system)
    primary_sko = find_primary_sko(primary_ou_id, fs, ou_perspective)
    logger.debug("Person fnr=%s has primary sko=%s",
                 info_chunk.fnr11, primary_sko)
    if primary_sko is None:
        logger.warn("Cannot locate primary OU for person (id=%s fnr=%s)"
                    "No changes will be sent to FS",
                    person.entity_id, info_chunk.fnr11)
        return

    fs_info = fs.person.get_fagperson(info_chunk.fnr6, info_chunk.pnr)
    values2push = {"fodselsdato": info_chunk.fnr6,
                   "personnr": info_chunk.pnr,
                   "adrlin1_arbeide": None, "adrlin2_arbeide": None,
                   "postnr_arbeide": None,
                   "adrlin3_arbeide": None,
                   "arbeidssted": None,
                   "institusjonsnr_ansatt": primary_sko[0],
                   "faknr_ansatt": primary_sko[1],
                   "instituttnr_ansatt": primary_sko[2],
                   "gruppenr_ansatt": primary_sko[3],
                   # "telefonnr_arbeide": info_chunk.phone,
                   "stillingstittel_norsk": info_chunk.work_title,
                   # "telefonnr_fax_arb": info_chunk.fax
                   }
    if not fs_info:
        logger.debug("Pushing new entry to FS.fagperson: %s pid=%s",
                     info_chunk, person_id)
        try:
            # According to mgrude, this field is to be set to 'N' for new
            # entries and left untouched for already existing entries.
            values2push["status_aktiv"] = 'N'
            fs.person.add_fagperson(**values2push)
        except:
            logger.info("Failed updating person %s (fnr=%s): %s",
                        person_id, info_chunk.fnr11,
                        exc2message(sys.exc_info()))
    else:
        logger.debug("Fagperson fnr=%s exists in FS", info_chunk.fnr11)
        tmp = fs_info[0]
        for key in values2push:
            val_in_cerebrum = values2push[key]
            val_in_fs = tmp[key]
            if val_in_fs != val_in_cerebrum:
                break
        else:
            logger.debug("Fagperson fnr=%s does not need updating",
                         info_chunk.fnr11)
            return

        logger.debug("Updating data for fagperson fnr=%s", info_chunk.fnr11)
        fs.person.update_fagperson(**values2push)
    instno = primary_sko[0]
    phone = fs.person.get_telephone(info_chunk.fnr6, info_chunk.pnr,
                                    instno, 'ARB', fetchall=True)

    if phone:
        if phone[0]['telefonlandnr']:
            phone = '+' + phone[0]['telefonlandnr'] + phone[0]['telefonnr']
        else:
            phone = phone[0]['telefonnr']
    try:
        if info_chunk.phone and not phone:
            logger.debug("Setting phone to %s", info_chunk.phone)
            fs.person.add_telephone(info_chunk.fnr6, info_chunk.pnr, 'ARB',
                                    info_chunk.phone)
        elif info_chunk.phone and phone != info_chunk.phone:
            logger.debug("Updating phone: %s > %s",
                         phone, info_chunk.phone)
            fs.person.update_telephone(info_chunk.fnr6, info_chunk.pnr, 'ARB',
                                       info_chunk.phone)
    except Exception as e:
        logger.info("Could not set phone %s: %s", info_chunk.phone, e)

    fax = fs.person.get_telephone(info_chunk.fnr6, info_chunk.pnr,
                                  instno, 'FAKS', fetchall=True)
    if fax:
        if fax[0]['telefonlandnr']:
            fax = '+' + fax[0]['telefonlandnr'] + fax[0]['telefonnr']
        else:
            fax = fax[0]['telefonnr']
    try:
        if info_chunk.fax and not fax:
            logger.debug("Setting fax to %s", info_chunk.fax)
            fs.person.add_telephone(info_chunk.fnr6, info_chunk.pnr, 'FAKS',
                                    info_chunk.fax)
        elif info_chunk.fax and fax != info_chunk.fax:
            logger.debug("Updating fax: %s > %s",
                         fax, info_chunk.fax)
            fs.person.update_telephone(info_chunk.fnr6, info_chunk.pnr, 'FAKS',
                                       info_chunk.fax)
    except Exception as e:
        logger.info("Could not set fax %s: %s", info_chunk.fax, e)


def make_fs_updates(person_affiliations, fagperson_affiliations, fs,
                    authoritative_system, ou_perspective):
    """Send all updates to FS.

    For all people with specified affiliations, push the necessary data to
    FS.

    @type person_affiliations: sequence of pairs (of constants)
    @param person_affiliations:
      Sequence of affiliations and statuses that we use in person
      selection. Each element is a pair (affiliation, aff_status). If no
      status has been specified (it is a possibility), aff_status will be
      None. People with these affiliations will be used to populate
      FS.person.

    @type fagperson_affiliations: sequence of pairs (of constants)
    @param fagperson_affiliations:
      Sequence of affiliations, much like L{person_affiliations}. This one is
      used to populate FS.fagperson.

    @type fs: make_fs() instance.
    @param fs:
      An FS db proxy.

    @type authoritative_system: An AuthoritativeSystem instance.
    @param authoritative_system:
      The authoritative system for lookup up names and contact
      information. Ideally this should be handled by scoped system lookup
      order, but we are not quite there.

    @type ou_perspective: An OUPerspective instance.
    @param ou_perspective:
      The perspective for following up our OU hierarchy.
    """

    logger.debug("Scanning data from source=%s (perspective=%s)",
                 authoritative_system, ou_perspective)

    people = select_FS_candidates(person_affiliations, authoritative_system)
    for person_id, info_chunk in people.iteritems():
        export_person(person_id, info_chunk, fs)
    fs.db.commit()

    people = select_FS_candidates(fagperson_affiliations, authoritative_system)
    for person_id, info_chunk in people.iteritems():
        export_fagperson(person_id, info_chunk, fagperson_affiliations, fs,
                         authoritative_system, ou_perspective)
    fs.db.commit()


def main():
    try:
        opts, junk = getopt.getopt(sys.argv[1:], 'p:f:da:o:',
                                   ('person-affiliation=',
                                    'fagperson-affiliation=',
                                    'dryrun',
                                    'authoritative-system=',
                                    'ou-perspective=',
                                    'with-cache-email',))
    except getopt.GetoptError:
        print "Wrong option", sys.exc_info()
        return

    def append_affiliation(value, where):
        if len(value.split("/")) == 1:
            aff, status = (
                constants.human2constant(value, constants.PersonAffiliation),
                None)
        elif len(value.split("/")) == 2:
            aff, status = value.split("/")
            aff, status = (
                constants.human2constant(aff, constants.PersonAffiliation),
                constants.human2constant(status, constants.PersonAffStatus))
            assert not (aff is None or status is None), "Missing aff/status"
        else:
            logger.error("Wrong syntax for affiliation %s", value)
            return

        where.append((aff, status))
    # end append_affiliation

    person_affiliations = list()
    fagperson_affiliations = list()
    dryrun = False
    authoritative_system = ou_perspective = None
    email_cache = False
    for option, value in opts:
        if option in ('-p', '--person-affiliation',):
            append_affiliation(value, person_affiliations)
        elif option in ('-f', '--fagperson-affiliation',):
            append_affiliation(value, fagperson_affiliations)
        elif option in ('-d', '--dryrun',):
            dryrun = True
        elif option in ('-a', '--authoritative-system',):
            authoritative_system = constants.human2constant(
                value, constants.AuthoritativeSystem)
        elif option in ('-o', '--ou-perspective',):
            ou_perspective = constants.human2constant(
                value, constants.OUPerspective)
        elif option in ('--with-cache-email',):
            email_cache = True

    assert authoritative_system is not None
    assert ou_perspective is not None
    if not person_affiliations:
        logger.error("No person affiliations are specified. "
                     "This is most likely not what you want")
        return

    fs = make_fs()
    if dryrun:
        fs.db.commit = fs.db.rollback

    # This is a performance improvement hack. It can be removed, if memory is
    # at a premium. The trade-off is 5x difference in execution speed.
    _populate_caches(person_affiliations + fagperson_affiliations,
                     authoritative_system,
                     email_cache)

    make_fs_updates(person_affiliations, fagperson_affiliations, fs,
                    authoritative_system, ou_perspective)
    logger.debug("Pushed all changes to FS")


if __name__ == "__main__":
    main()

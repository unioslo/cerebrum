#!/usr/bin/env python
# -*- coding: utf-8 -*-

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


"""This file is a HiA-specific extension of Cerebrum. It contains code which
assigns and deletes affiliations/aff. statuses for people based on their
employment records in SAP (feide_persti)

The rules for assigning affiliations are thus:

* Each valid[1] entry in feide_persti results in exactly one
  affiliation_ansatt. The aff. status for this affiliation is calculated based
  on the employment code (lønnstittelkode) from that entry.
* Each affiliation in Cerebrum must have a corresponding entry in the file.

There are roughly two different ways of synchronising all the affiliations:

#. Drop all affiliation_ansatt (this should be the only script assigning them)
   in Cerebrum and re-populate them from data file.
#. Cache the affiliation_ansatt in the db, compare it to file, remove the
   affs in the cache but not in the file, add the affs in the file, but not in
   cache.

The problem with the first approach is that 1) there is no telling what the
various mixin classes would do on delete 2) we'd flood the change_log with
bogus updates (remove A, add A) 3) the db would probably not appreciate such a
usage pattern.
"""

import argparse
from mx.DateTime import today, DateTimeDelta
import os

import cereconf

from Cerebrum import Errors
from Cerebrum.database import Database
from Cerebrum.Utils import Factory
from Cerebrum.Utils import NotSet
from Cerebrum.utils.funcwrap import memoize
from Cerebrum.modules.no.hia.mod_sap_utils import load_expired_employees
from Cerebrum.modules.no.hia.mod_sap_utils import load_invalid_employees
from Cerebrum.modules.no.hia.mod_sap_utils import make_employment_iterator
from Cerebrum.modules.no.Constants import SAPLonnsTittelKode


def sap_employment2affiliation(sap_lonnstittelkode):
    """Decide the affiliation to assign to a particular employment entry.

    The rules are:

    * aff = ANSATT, and VIT/ØVR depending on lonnstittelkode, when:
      sap_lonnstittelkode != 20009999 (const.sap_9999_dummy_stillingskode)
      fo_kode != 9999

    * aff = TILKNYTTET/ekstern, when:
      sap_lonnstittelkode = 20009999 (const.sap_9999_dummy_stillingskode)
      fo_kode != 9999
    """

    try:
        lonnskode = SAPLonnsTittelKode(sap_lonnstittelkode)
        kategori = lonnskode.get_kategori()
        if not isinstance(kategori, unicode):
            kategori = kategori.decode(Database.encoding)
    except Errors.NotFoundError:
        logger.warn(u"No SAP.STELL/lønnstittelkode <%s> found in Cerebrum",
                    sap_lonnstittelkode)
        return None, None

    if lonnskode != constants.sap_9999_dummy_stillingskode:
        affiliation = constants.affiliation_ansatt
        status = {
            u'ØVR': constants.affiliation_status_ansatt_tekadm,
            u'VIT': constants.affiliation_status_ansatt_vitenskapelig}[kategori]
    else:
        affiliation = constants.affiliation_tilknyttet
        status = constants.affiliation_status_tilknyttet_ekstern

    return affiliation, status


@memoize
def get_ou_id(sap_ou_id):
    """
    Map SAP OU id to Cerebrum entity_id.
    """

    ou = Factory.get("OU")(database)
    try:
        ou.find_by_external_id(constants.externalid_sap_ou, sap_ou_id)
        return int(ou.entity_id)
    except Errors.NotFoundError:
        return None


def get_person(sap_person_id):
    """
    Map SAP ansattnr to Cerebrum entity_id.
    """

    person = Factory.get("Person")(database)
    try:
        person.find_by_external_id(constants.externalid_sap_ansattnr,
                                   sap_person_id)
        return person
    except Errors.NotFoundError:
        return None


def cache_db_affiliations():
    """Return a cache with all affilliation_ansatt.

    The cache itself is a mapping person_id -> person-mapping, where
    person-mapping is a mapping ou_id -> status. I.e. with each person_id we
    associate all affiliation_ansatt that the person has indexed by ou_id.
    """

    person = Factory.get("Person")(database)
    # A cache dictionary mapping person -> D, where D is a mapping (ou_id,
    # affiliation) -> status. Why such a weird arrangement? Well, the API
    # makes it easier to delete all affiliations one person at a time
    # (therefore, person_id as the first-level key).
    #
    # Then, if an affiliation status changes, we cannot just yank the
    # affiliation out (because there would be a FK to it) and we need to
    # update, rather than remove-add it. Thus the magic with ou/affiliation as
    # the second key.
    cache = dict()
    for row in person.list_affiliations(
        source_system=constants.system_sap,
        affiliation=(constants.affiliation_ansatt,
                     constants.affiliation_tilknyttet)):
        p_id, ou_id, affiliation, status = [int(row[x]) for x in
                                            ("person_id", "ou_id",
                                             "affiliation", "status",)]
        cache.setdefault(p_id, {})[(ou_id, affiliation)] = status

    return cache


def remove_affiliations(cache):
    "Remove all affiliations in cache from Cerebrum."

    # cache is mapping person-id => mapping (ou-id, aff) => status. All these
    # mappings are all for affiliation_ansatt.
    person = Factory.get("Person")(database)
    logger.debug("Removing affiliations for %d people", len(cache))

    for person_id in cache:
        try:
            person.clear()
            person.find(person_id)
        except Errors.NotFoundError:
            logger.warn("person_id %s is in cache, but not in Cerebrum",
                        person_id)
            continue

        # person is here, now we delete all the affiliation_ansatt
        # affiliations.
        handle = True
        if 'handled' in cache[person_id]:
            handle = not cache[person_id]['handled']
            del cache[person_id]['handled']
        for (ou_id, affiliation) in cache[person_id].iterkeys():
            if handle:
                person.delete_affiliation(ou_id,
                                          affiliation,
                                          constants.system_sap)
            logger.debug("Removed aff=%s/ou_id=%s for %s",
                         constants.PersonAffiliation(affiliation),
                         ou_id, person_id)


def synchronize_affiliations(aff_cache, person, ou_id,
                             affiliation, status):
    """Register/update an affiliation for a specific person.

    aff_cache is updated destructively.

    person must be associated with a person in the db.
    """

    # A log message has already been issued...
    if (affiliation, status) == (None, None):
        return

    logger.debug("Registering affiliation %s/%s for person_id %s",
                 affiliation, status, person.entity_id)

    # For accessing aff_cache
    key_level1 = int(person.entity_id)
    key_level2 = (int(ou_id), int(affiliation))

    # Ok, now we have everything we need to register/adjusted affiliations
    # case 1: the affiliation did not exist => make a new affiliation
    person.populate_affiliation(constants.system_sap,
                                ou_id,
                                affiliation,
                                status)

    if key_level1 not in aff_cache:
        aff_cache[key_level1] = {'handled': True}
    else:
        aff_cache[key_level1]['handled'] = True
    if key_level2 not in aff_cache[key_level1]:
        logger.debug("New affiliation %s (status: %s) for (person_id: %s)",
                     affiliation, status, person.entity_id)

    # case 2: the affiliation did exist => update aff.status and fix the cache
    else:
        cached_status = aff_cache[key_level1][key_level2]
        # Update cache info (we'll need this to delete obsolete
        # affiliations from Cerebrum). Remember that if aff.status is the
        # only thing changing, then we should not delete the "old"
        # aff.status entry. Thus, regardless of the aff.status, we must
        # clear the cache.
        del aff_cache[key_level1][key_level2]
        if not aff_cache[key_level1]:
            del aff_cache[key_level1]

        # The affiliation is there, but the status is different => update
        if cached_status != int(status):
            logger.debug("Updating affiliation status %s => %s for "
                         "(p_id: %s)",
                         str(constants.PersonAffStatus(cached_status)),
                         status, person.entity_id)
        else:
            logger.debug("Refreshing last seen for aff %s for (person id: %s)",
                         status, person.entity_id)


def process_affiliations(employment_file, person_file, use_fok,
                         people_to_ignore=None):
    """Parse employment_file and determine all affiliations.

    There are roughly 3 distinct parts:

    #. Cache all the affiliations in Cerebrum
    #. Scan the file and compare the file data with the cache. When there is a
       match, remove the entry from the cache.
    #. Remove from Cerebrum whatever is left in the cache (once we are done
       with the file, the cache contains those entries that were in Cerebrum
    """

    expired = load_expired_employees(file(person_file), use_fok, logger)

    # First we cache all existing affiliations. It's a mapping person-id =>
    # mapping (ou-id, affiliation) => status.
    affiliation_cache = cache_db_affiliations()
    person_cache = dict()

    def person_cacher(empid):
        ret = person_cache.get(empid, NotSet)
        if ret is NotSet:
            ret = person_cache[empid] = get_person(empid)
        return ret

    for tpl in make_employment_iterator(
            file(employment_file), use_fok, logger):
        if not tpl.valid():
            logger.debug("Ignored invalid entry for person while "
                         "processing affiliation: «%s»",
                         tpl.sap_ansattnr)
            continue

        if people_to_ignore and tpl.sap_ansattnr in people_to_ignore:
            logger.debug("Invalid person with sap_id=%s", tpl.sap_ansattnr)
            continue

        if tpl.sap_ansattnr in expired:
            logger.debug("Person sap_id=%s is no longer an employee; "
                         "all employment info will be ignored",
                         tpl.sap_ansattnr)
            continue

        # is the entry within a valid time frame?
        # The shift by 180 days has been requested by UiA around 2007-03-27
        if not (tpl.start_date - DateTimeDelta(180) <= today() <=
                tpl.end_date):
            logger.debug("Entry %s has wrong timeframe (start: %s, end: %s)",
                         tpl, tpl.start_date, tpl.end_date)
            continue

        ou_id = get_ou_id(tpl.sap_ou_id)
        if ou_id is None:
            logger.warn("Cannot map SAP OU %s to Cerebrum ou_id (employment "
                        "for person sap_id=%s).",
                        tpl.sap_ou_id, tpl.sap_ansattnr)
            continue

        person = person_cacher(tpl.sap_ansattnr)
        if person is None:
            logger.warn("Cannot map SAP ansattnr %s to cerebrum person_id",
                        tpl.sap_ansattnr)
            continue

        (affiliation,
         affiliation_status) = sap_employment2affiliation(tpl.lonnstittel)

        synchronize_affiliations(affiliation_cache,
                                 person,
                                 ou_id, affiliation,
                                 affiliation_status)

    # We are done with fetching updates from file.
    # Need to write persons
    for p in person_cache.values():
        if p is None:
            continue
        logger.info("Writing cached affs for person id:%s", p.entity_id)
        p.write_db()

    # All the affiliations left in the cache exist in Cerebrum, but NOT in the
    # datafile. Thus delete them!
    remove_affiliations(affiliation_cache)


def cache_db_employments():
    """
    Preload all existing employment data.

    Note that we just need the primary keys here.
    """

    logger.debug("Preloading all existing employments")
    result = set()
    person = Factory.get("Person")(database)
    for row in person.search_employment(source_system=constants.system_sap):
        key = (row["person_id"], row["ou_id"], row["description"],
               row["source_system"])
        result.add(key)

    logger.debug("Done preloading all existing employments")
    return result


def remove_db_employments(remaining_employments):
    """
    Nuke whatever remains of employments.

    Whichever keys remain in remaining_employments, they exist in the db, but
    not in the source file.
    """

    logger.debug("Will delete %s remaining employments",
                 len(remaining_employments))
    person = Factory.get("Person")(database)
    for (pid, ou_id, title, source) in remaining_employments:
        person.clear()
        person.find(pid)
        person.delete_employment(ou_id, title, source)
        # If person has a work_title defined and it matches the current
        # employment's title, remove work_title as well.
        try:
            if title == person.get_name_with_language(constants.work_title,
                                                      constants.language_nb):
                person.delete_name_with_language(constants.work_title,
                                                 constants.language_nb)
        except Errors.NotFoundError:
            pass

    logger.debug("Completed deletion")


def synchronise_employment(employment_cache, tpl, person, ou_id):
    """
    Synchronise a specific employment entry with the database.

    Updates employment_cache destructively.
    """

    try:
        employment = SAPLonnsTittelKode(tpl.lonnstittel)
        description = employment.description
    except Errors.NotFoundError, e:
        logger.warn("Unknown lonnstittelkode %s for person with SAP-id: %s",
                    tpl.lonnstittel, tpl.sap_ansattnr)
        logger.warn(e)
        return

    if " " not in description:
        logger.debug("Employment type %s for person %s"
                     " missing code/description",
                     description, person.entity_id)
        return

    code, title = description.split(" ", 1)
    if not code.isdigit():
        logger.debug("Employment for %s is missing code/title: %s",
                     person.entity_id, description)
        return

    key = (person.entity_id, ou_id, title, constants.system_sap)
    if key in employment_cache:
        employment_cache.remove(key)

    try:
        float(tpl.percentage)
    except TypeError:
        logger.debug("Invalid employment fraction specification in %s",
                     str(tpl))
        return

    # This will either insert or update
    person.add_employment(ou_id, title, constants.system_sap,
                          tpl.percentage, tpl.start_date, tpl.end_date,
                          code, tpl.stillingstype == 'H')


def process_employments(employment_file, use_fok, people_to_ignore=None):
    "Synchronise the data in person_employment based on the latest SAP file."

    logger.debug("processing employments")
    employment_cache = cache_db_employments()
    for tpl in make_employment_iterator(
            file(employment_file), use_fok, logger):
        if not tpl.valid():
            logger.debug("Ignored invalid entry for person while "
                         "processing employment: «%s»",
                         tpl.sap_ansattnr)
            continue

        if people_to_ignore and tpl.sap_ansattnr in people_to_ignore:
            # e.g. those with wrong MG/MU
            logger.debug("Invalid person with sap_id=%s", tpl.sap_ansattnr)
            continue

        # just like process_affiliations
        ou_id = get_ou_id(tpl.sap_ou_id)
        if ou_id is None:
            logger.debug("No OU registered for SAP ou_id=%s", tpl.sap_ou_id)
            continue

        person = get_person(tpl.sap_ansattnr)
        if person is None:
            logger.debug("No person is registered for SAP ansatt# %s",
                         tpl.sap_ansattnr)
            continue

        synchronise_employment(employment_cache, tpl, person, ou_id)
        # Add person to employee-set, which is later used by
        # populate_work_titles()
        if person not in employees:
            employees.add(person)

    remove_db_employments(employment_cache)
    logger.debug("done with employments")


def populate_work_titles():
    """
    Calculates the main employment entry for every person listed in the
    source file, and adds the description as the person's work_title.
    We first try to check which employment is defined as the person's main one.
    If no employment entry is defined as the main employment, we look through
    the other employments and use the entry with the highest percentage number.
    If several entries with an equal percentage number exists for a given
    person, the first one encountered is used.
    """
    logger.debug('Populating work_titles...')
    logger.debug('Number of persons to set titles for: %d' % len(employees))
    for person in employees:
        main_employment = None
        employments = person.search_employment(person.entity_id,
                                               main_employment=True)
        for employment in employments:
            if main_employment is None or \
               employment['percentage'] > main_employment['percentage']:
                main_employment = employment
        if main_employment is None:
            employments = person.search_employment(person.entity_id)
            for employment in employments:
                if main_employment is None or \
                   employment['percentage'] > main_employment['percentage']:
                    main_employment = employment
        if main_employment is not None:
            person.add_name_with_language(name_variant=constants.work_title,
                                          name_language=constants.language_nb,
                                          name=main_employment['description'])
            person.write_db()
            logger.debug("Adding %s '%s' to person with entity_id %d" %
                         (str(constants.work_title),
                          main_employment['description'],
                          person.entity_id))


def main():
    global logger
    logger = Factory.get_logger('cronjob')

    parser = argparse.ArgumentParser(description=__doc__)
    required_args = parser.add_argument_group('required arguments')
    required_args.add_argument('-e', '--employment-file',
                               dest='employment_file',
                               required=True,
                               help='File containing employment data-export '
                                    'from SAP.')
    required_args.add_argument('-p', '--person-file', dest='person_file',
                               required=True,
                               help='File containing person data-export '
                                    'from SAP.')
    parser.add_argument('--without-fok', dest='use_fok', action='store_false',
                        help='Do not use forretningsområdekode for checking '
                             'if a person should be imported. (default: use.)')
    parser.set_defaults(use_fok=True)
    parser.add_argument('--with-employment', dest='sync_employment',
                        action='store_true',
                        help='Synchronise person employments based '
                             'on specified employment-file.')
    parser.set_defaults(sync_employment=False)
    parser.add_argument('-c', '--commit', dest='commit', action='store_true',
                        help='Write changes to DB.')
    args = parser.parse_args()

    assert (args.person_file is not None and
            os.access(args.person_file, os.F_OK))
    assert (args.employment_file is not None and
            os.access(args.employment_file, os.F_OK))

    global database
    database = Factory.get("Database")()
    database.cl_init(change_program="import_SAP")

    global constants
    constants = Factory.get("Constants")()

    global employees
    employees = set()

    if getattr(cereconf, 'SAP_MG_MU_CODES', None) and args.use_fok:
        raise Exception("Use of both MG/MU codes and fok isn't implemented")

    ignored_people = load_invalid_employees(file(args.person_file),
                                            args.use_fok)

    if args.sync_employment:
        process_employments(args.employment_file,
                            args.use_fok,
                            ignored_people)
        populate_work_titles()

    process_affiliations(args.employment_file,
                         args.person_file,
                         args.use_fok,
                         ignored_people)

    if args.commit:
        database.commit()
        logger.info("All changes committed")
    else:
        database.rollback()
        logger.info("All changes rolled back")

if __name__ == "__main__":
    main()

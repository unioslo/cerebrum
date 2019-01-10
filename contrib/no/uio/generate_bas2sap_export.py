#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2015-2018 University of Oslo, Norway
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

"""This script generates a data file for SAP-UIO.

SAP-UIO is one of the main sources for authoritative data in
Cerebrum. However, Cerebrum also reports some of the data back to
SAP-UIO. This script generates such a file.

This script fulfills roughly the same purpose as
contrib/no/uio/export_to_SAP.py.

The file is latin-1 encoded csv-variant structured thus:

<ansattnr>;<full name>;<uname>;<e-mail address>;<url>;<tlf>

';' is the separator character. If it happens in the data, it will be quoted
(with a backslash. The quote character ('\') itself is also quoted). Each
lines ends with a Unix-style newline character (\n).

This file is generated for all employees (people with
affiliation=const.affiliation_ansatt). The fields are:

<ansattnr> 	 - 8-digit internal SAP ansattnr (employee number)
<full name>      - const.person_name_full (from any source system?)
<uname>          - primary user name
<e-mail address> - primary user name's e-mail address
<url>            - const.contact_url
<tlf>            - Office telephone number

<ansattnr> is selected from const.system_sap
<full name> is selected from const.system_cached.
"""

import csv
import getopt
import sys

from Cerebrum.Utils import Factory
from Cerebrum.utils.atomicfile import AtomicFileWriter

logger = None


def build_cache(db):
    """Build a few caches to speed up value lookup for certain types."""
    cache = dict()
    account = Factory.get("Account")(db)
    person = Factory.get("Person")(db)
    const = Factory.get("Constants")(db)
    logger.debug("Fetching uname->mail...")
    for key, value in account.getdict_uname2mailaddr().iteritems():
        cache[key] = value
    logger.debug("... done (total: %d entries)", len(cache))
    # There should not be collisions between unames and sap_ansattnr :)
    logger.debug("Fetching sap_ansattnr->uname...")
    for key, value in person.getdict_external_id2primary_account(
            const.externalid_sap_ansattnr).iteritems():
        cache[key] = value
    logger.debug("... done (total: %d entries)", len(cache))
    return cache


def person2e_id(person, eid_type, const):
    """Map the internal person_id (entity_id) to an external id.

    We fetch all external ids from system_sap (the rest is of no interest
    here).

    :type person: a Factory.get('Person') instance.
    :param person:
      Person db proxy associated with a person in Cerebrum.

    :type eid_type: A constant object (or an int)
    :param eid_type:
      External id type we want to locate.

    :type const: A Factory.get('Constants') instance
    :param const:
      Constant db proxy
    """
    eid = person.get_external_id(const.system_sap, eid_type)
    if eid:
        return eid[0]["external_id"]
    return None


def fetch_person_fields(person, const):
    """Return a tuple with all of the values to output to the csv file.

    :type person: Person instance.
    :param:
      Person instance associated with an object in the db.

    :rtype: tuple (of strings)
    :return:
      A tuple (ansattnr, full name, uname, e-mail, url, tlf)
    """
    ansattnr = person2e_id(person, const.externalid_sap_ansattnr, const)
    # we *must* have the ansattnr
    if not ansattnr:
        return None
    cache = fetch_person_fields.cache
    # the rest is optional...
    fullname = person.get_name(const.system_cached, const.name_full)
    uname = cache.get(ansattnr)
    mail = cache.get(uname)
    url = None
    for item in person.get_contact_info(type=const.contact_url):
        url = item["contact_value"]
        break
    # Select telephone number. We constrain on numbers from VoIP, which are
    # VoIP numbers. Then we sort them based on their priority. Lower is
    # preferred. Finally, set the var, if appropriate.
    voip = person.get_contact_info(source=const.system_voip,
                                   type=const.contact_voip_extension)
    voip.sort(key=lambda x: x['contact_pref'])
    voip = voip.pop(0)['contact_value'] if voip else None
    # force latin-1
    values = [ansattnr, fullname, uname, mail, url, voip]
    for idx in range(len(values)):
        if not values[idx]:
            continue
        # The import routine can't cope with quotechars.
        for forbidden_char in ('\r', '\n', ';'):
            if forbidden_char in values[idx]:
                logger.warn("Illegal char %s in data %s. %s is skipped.",
                            forbidden_char, values[idx], values)
                return None
    return values


def generate_people(db):
    """Return a sequence of person_id for everybody eligible for this export.

    We are supposed to list all persons having ansatt# from SAP and having an
    active user.
    """
    person = Factory.get("Person")(db)
    account = Factory.get("Account")(db)
    constants = Factory.get("Constants")(db)
    logger.debug("Fetching account holders")
    # this yields a set of all persons with an active account.
    account_holders = set(
        int(x["owner_id"])
        for x in account.search(expire_start='[:now]',
                                owner_type=constants.entity_person))
    logger.debug("Collecting people set")
    # this yields a set of all persons with a SAP id.
    for row in person.search_external_ids(
            source_system=constants.system_sap,
            id_type=constants.externalid_sap_ansattnr,
            fetchall=False):
        if int(row["entity_id"]) not in account_holders:
            continue
        yield int(row["entity_id"])


def generate_file(filename):
    """Write the data about everyone to L{filename}.

    :type filename: basestring
    :param filename:
      Output filename
    """
    ostream = AtomicFileWriter(filename, mode='wb')
    writer = csv.writer(ostream,
                        delimiter=';',
                        quotechar='',
                        quoting=csv.QUOTE_NONE,
                        # Make sure that lines end with a Unix-style linefeed
                        lineterminator='\n')
    db = Factory.get("Database")()
    person = Factory.get("Person")(db)
    const = Factory.get("Constants")()
    logger.debug("Preloading uname/account data...")
    cache = build_cache(db)
    fetch_person_fields.cache = cache
    logger.debug("...finished")
    processed = set()
    for person_id in generate_people(db):
        if person_id in processed:
            continue
        logger.debug("Processing person id=%d", person_id)
        processed.add(person_id)
        person.clear()
        person.find(person_id)
        fields = fetch_person_fields(person, const)
        if fields is not None:
            # csv module does not support unicode (str is called on all
            # non-string variables), so we encode in UTF-8 before writing CSV
            # rows
            # PYTHON3 remove encoding
            writer.writerow(
                [x.encode('UTF-8') if isinstance(x, unicode) else x for x in fields])
        else:
            logger.info("ansattnr is missing for person id=%d", person_id)
    logger.debug("Output %d people", len(processed))
    ostream.close()


def main():
    global logger
    logger = Factory.get_logger("cronjob")
    options, rest = getopt.getopt(sys.argv[1:],
                                  "f:",
                                  ("file=",))
    filename = None
    for option, value in options:
        if option in ("-f", "--file"):
            filename = value
    assert filename, "Must provide output filename"
    generate_file(filename)


if __name__ == "__main__":
    main()

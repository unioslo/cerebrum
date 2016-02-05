#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2004 University of Oslo, Norway
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
This file is a UiO-specific extensions of Cerebrum.

It provides user/person statistics about various organizational units (OUs)
at the UiO. The script provides statistics at various granularity levels
(--level option).

--level fakultet produces statistics grouped by faculty (fakultet). A
  faculty of a given OU is the first OU in the OU hierarchy that has
  (institutt, avdeling) == (0. 0). For all OUs that do not have such
  parents, the stats are grouped together under the same tag.

--level institutt produces statistics grouped by department (institutt). A
  department of a given OU is the first OU in the OU hierarchy that has
  avdeling = 0. For all OUs that do not have such parents, the stats are
  grouped together under the same tag.

--level gruppe produces statistics with each OU taking as is, without any
  parent lookup.

"""

import argparse
import copy
import types

import cerebrum_path

from Cerebrum.extlib.sets import Set
from Cerebrum.Utils import Factory

del cerebrum_path
logger = None


def make_ou_to_stedkode_map(db):
    """
    Returns a dictionary mapping ou_ids to (fak,inst,avd) triplets
    (stedkoder).
    """

    ou = Factory.get("OU")(db)
    result = dict()

    for row in ou.get_stedkoder():
        result[int(row["ou_id"])] = (int(row["fakultet"]),
                                     int(row["institutt"]),
                                     int(row["avdeling"]))

    logger.debug("%d ou -> stedkode mappings", len(result))
    return result


def make_ou_to_parent_map(perspective, db):
    """
    Returns a dictionary mapping ou_ids to their parent ids (or None, if no
    parent exists) in a given PERSPECTIVE (FS, LT, etc.)
    """

    ou = Factory.get("OU")(db)
    result = dict()

    for item in ou.get_structure_mappings(perspective):
        if item["parent_id"] is not None:
            parent_id = int(item["parent_id"])
        else:
            parent_id = None
        result[int(item["ou_id"])] = parent_id

    logger.debug("%d ou -> parent mappings", len(result))
    return result


#
# sko for all OUs that we cannot classify.
__undef_ou = "andre"


def locate_ou(ou_id, ou2parent, ou2stedkode, level):
    """
    Return a suitable parent of OU_ID.

    LEVEL determines how far up the hierarchy we are walking.
        0 means the entity itself
        1 means the closest parent with avdeling part of the sko == 0
        2 means the closest parent with avdeling and institutt part of
          the sko == 0.

    Should we reach the top of the hierarchy without finding a suitable
    (parent) OU, a special value is returned. The statistics for that group
    will be cumulative for _all_ OU_ID that have no suitable (parent) OU.
    """

    ou_id = int(ou_id)

    # If level == oneself, just return the ou_id
    if level == 0:
        return ou2stedkode[ou_id]

    tmp = ou_id
    while 1:
        if tmp is None:
            # We reached the top of the hierarchy without seeing anything
            # suitable
            logger.debug("ou_id %d has no proper parent", ou_id)
            return __undef_ou

        if tmp not in ou2stedkode:
            logger.warn("Cannot locate sko for ou_id %s. Assuming undef", tmp)
            return __undef_ou

        tmp_sko = ou2stedkode[tmp]
        # extract the right part of the sko
        if tmp_sko[3-level:] == (0,)*level:
            return tmp_sko

        # ... or continue with parent
        tmp = ou2parent.get(tmp)


def display_statistics(statistics):
    """
    STATISTICS is a dictionary indexed by faculty numbers (K) and with
    values (V) being dictionaries with statistics information.

    This function assumes that _all_ Vs have the exactly same set of keys.
    """

    logger.debug("Statistics:")

    # The keys we are interested in
    keys = ('ansatt', 'student', 'a&s', 'tilknyttet', 'manuell', 'upersonlig',)
    # Dictionary for totalling up numbers per affiliation
    total = dict([(key, 0) for key in keys])

    faculty_keys = statistics.keys()
    # Order the faculty output by sko
    faculty_keys.sort()

    # Yes, the code is ugly, but people do not like
    # pprint.print(dictionary)
    fak_width = 11
    field_width = 7
    fak_underline = "-" * fak_width + "+"
    field_underline = "-" * field_width + "+"
    fak_format = "%%%ds" % fak_width
    field_format = "%%%ds" % field_width

    values = ("navn",) + tuple([str(x)[0:field_width] for x in keys])
    print (((fak_format + "|") % "fak") +
           ((field_format + "|") * len(values)) % values)
    print "%s%s" % (fak_underline, field_underline * len(values))

    for faculty in faculty_keys:
        value = statistics[faculty]
        if isinstance(faculty, types.TupleType):
            faculty_text = "%02d%02d%02d" % faculty
        else:
            faculty_text = str(faculty)

        message = ((fak_format % str(faculty_text)) +
                   ("|" + field_format) % str(value["name"])[0:field_width])

        for key in keys:
            message += "|" + field_format % value[key]
            total[key] += value[key]

        print message

    print "%s%s" % (fak_underline, field_underline * len(values))

    message = (fak_format + "|") % "Total" + (field_format + "|") % "--"
    sum = 0
    for key in keys:
        message += (field_format + "|") % total[key]
        sum += total[key]

    print message, field_format % sum


def make_empty_statistics(level, db):
    """
    Return an empty dictionary suitable for statistics collection.

    Depending on the LEVEL, we'll have a different number of keys in
    STATISTICS.
    """

    fakultet, institutt, avdeling = None, None, None
    if level > 0:
        avdeling = 0

    if level > 1:
        institutt = 0

    ou = Factory.get("OU")(db)
    sko = ou.get_stedkoder(fakultet=fakultet, institutt=institutt,
                           avdeling=avdeling)
    const = Factory.get("Constants")()

    statistics = dict()
    # "Unspecified" stats.
    statistics[__undef_ou] = {"name": "undef"}

    for row in sko:
        ou_sko = (int(row["fakultet"]),
                  int(row["institutt"]),
                  int(row["avdeling"]))
        ou.clear()
        ou.find(row["ou_id"])

        acronyms = ou.search_name_with_language(
            entity_id=ou.entity_id, name_variant=const.ou_name_acronym)
        if acronyms:
            ou_name = acronyms[0]["name"]
        else:
            names = ou.search_name_with_language(entity_id=ou.entity_id,
                                                 name_variant=const.ou_name)
            if names:
                ou_name = names[0]["name"]
            else:
                ou_name = "N/A"

        statistics[ou_sko] = {"name": ou_name}

    for key in statistics.keys():
        value = {"ansatt": 0,
                 "a&s": 0,
                 "student": 0,
                 "tilknyttet": 0,
                 "manuell": 0,
                 "upersonlig": 0,
                 None: 0,
                 }
        statistics[key].update(value)

    logger.debug("Generating stats for %d top-level OUs" % len(statistics))
    return statistics


def make_affiliation_priorities(const):
    """
    Prepares and returns a dictionary sorting affiliations/stati according
    to this ruleset:

    When associating an entity with a faculty during statistics collection,
    we have to break ties. The ties are broken in the following fashion:

    1. First we compare affiliation; they are classified in this order
       ansatt, student, tilknyttet, manuell, upersonlig
    2. If an entity has two affiliations of the same type, affiliation
       status is used to break up ties in this order:

       ansatt -> vitenskaplig, tekadm, bilag, permisjon
       student -> aktiv, evu, alumni, perm, opptak, tilbud, soker, privatist
       tilknyttet -> emeritus, ekst_forsker, ekst_stip, fagperson, bilag,
                     gjesteforsker, sivilarbeider, diverse
       manuell -> don't care
       upersonlig -> don't care.

       For the latter two, we just select one entry. Does not matter which
       one (this might mean though that statistics run one after the other
       might fluctuate. Blame baardj for imprecise specification.

    The dictionary uses affiliations as keys. Each value is in turn a
    dictionary D, sorting that affiliation's stati. D has at least two
    (key,value) pairs -- 'name' and 'value', holding that affiliation's name
    and relative sort order.
    """

    return {
        int(const.affiliation_ansatt): {
            "name": "ansatt",
            "value": 0,
            int(const.affiliation_status_ansatt_vit): 0,
            int(const.affiliation_status_ansatt_tekadm): 1,
            int(const.affiliation_status_ansatt_bil): 2,
            int(const.affiliation_status_ansatt_perm): 3
        },
        int(const.affiliation_student): {
            "name": "student",
            "value": 1,
            int(const.affiliation_status_student_aktiv): 0,
            int(const.affiliation_status_student_evu): 1,
            int(const.affiliation_status_student_alumni): 2,
            int(const.affiliation_status_student_perm): 3,
            int(const.affiliation_status_student_opptak): 4,
            int(const.affiliation_status_student_tilbud): 5,
            int(const.affiliation_status_student_soker): 6,
            int(const.affiliation_status_student_privatist): 7,
        },
        int(const.affiliation_tilknyttet): {
            "name": "tilknyttet",
            "value": 2,
            int(const.affiliation_tilknyttet_emeritus): 0,
            int(const.affiliation_tilknyttet_ekst_forsker): 1,
            int(const.affiliation_tilknyttet_ekst_stip): 2,
            int(const.affiliation_tilknyttet_fagperson): 3,
            int(const.affiliation_tilknyttet_bilag): 4,
            int(const.affiliation_tilknyttet_gjesteforsker): 5,
            int(const.affiliation_tilknyttet_sivilarbeider): 6,
            int(const.affiliation_tilknyttet_diverse): 7,
        },
        int(const.affiliation_manuell): {
            "name": "manuell",
            "value": 3,
        },
        int(const.affiliation_upersonlig): {
            "name": "upersonlig",
            "value": 4,
        },
    }


def generate_people_statistics(perspective, empty_statistics, level, db):
    """
    Collect statistics about people.

    PERSPECTIVE determines how we view the OU hierarchy (FS, LT, etc)
    EMPTY_STATISTICS is a dictionary with default stat values.
    LEVEL designates how far up OU hierarchy we walk

    The strategy is pretty straightforward:

    for each person P
       look at P's affiliations A
       sort them according to the rules in make_affiliation_priorities
       select the first affiliation FA
       register P's contribution under the suitable OU derived from FA.ou_id
           and affiliation derived from FA.affiliation
    done

    This will ensure that each person is counted only once, despite having
    multiple affiliations to multiple faculties.

    NB! A silly thing is that the ruleset is incomplete. Harass baardj for a
    more complete specification.
    """

    person = Factory.get("Person")(db)
    const = Factory.get("Constants")(db)

    ou2stedkode = make_ou_to_stedkode_map(db)
    ou2parent = make_ou_to_parent_map(perspective, db)

    statistics = copy.deepcopy(empty_statistics)

    # Cache processed entities
    processed = Set()
    # Sort order for affiliations/stati
    order = make_affiliation_priorities(const)

    for row in person.list_affiliations(fetchall=False):
        id = int(row["person_id"])
        if id in processed:
            continue
        else:
            processed.add(id)

        affiliations = person.list_affiliations(person_id=id)
        # If there are no affiliations, this person contributes nothing to
        # the statistics.
        if not affiliations:
            continue

        affiliations.sort(lambda x, y:
                          cmp(order[x["affiliation"]],
                              order[y["affiliation"]])
                          or cmp(order.get(x["status"], 0),
                                 order.get(y["status"], 0)))
        aff = affiliations[0]
        ou_result = locate_ou(aff["ou_id"], ou2parent, ou2stedkode, level)

        # a&s (ansatt og student) has a special rule
        affs = [x["affiliation"] for x in affiliations]
        if (const.affiliation_student in affs and
                const.affiliation_ansatt in affs):
            affiliation_name = "a&s"
        else:
            affiliation_name = order[aff["affiliation"]]["name"]

        statistics[ou_result][affiliation_name] += 1

    return statistics


def generate_account_statistics(perspective, empty_statistics, level, db):
    """
    Collect statistics about accounts.

    for each account A
        look at A's affiliations F
        sort them according to the rules in make_affiliation_priorities
                                  (and by using priority to break ties)
        select the first affiliation FA
        register A's contribution under a suitable OU derived from FA.ou_id and
        affiliation derived from FA.affiliation
    done
    """

    account = Factory.get("Account")(db)
    const = Factory.get("Constants")(db)

    ou2stedkode = make_ou_to_stedkode_map(db)
    ou2parent = make_ou_to_parent_map(perspective, db)

    statistics = copy.deepcopy(empty_statistics)

    # sort order for affiliations
    order = make_affiliation_priorities(const)

    # Keep track of accounts that had been processed
    processed = Set()

    for row in account.list_accounts_by_type(fetchall=False):

        if int(row["account_id"]) in processed:
            continue
        else:
            processed.add(int(row["account_id"]))
        # fi

        affiliations = account.list_accounts_by_type(
            account_id=row["account_id"],
            filter_expired=True,
            fetchall=True)
        # Affiliations have already been ordered according to priority. Just
        # pick the first one.
        if not affiliations:
            continue
        # fi

        aff = affiliations[0]
        ou_result = locate_ou(aff["ou_id"], ou2parent, ou2stedkode, level)

        affs = [x["affiliation"] for x in affiliations]
        if (const.affiliation_student in affs and
                const.affiliation_ansatt in affs):
            affiliation_name = "a&s"
        else:
            affiliation_name = order[aff["affiliation"]]["name"]

        try:
            statistics[ou_result][affiliation_name] += 1

        except:
            logger.error("ou_result = %s (%s; %s);",
                         ou_result, ou_result in statistics, str(aff.ou_id))
            raise

    return statistics


def main():

    global logger
    logger = Factory.get_logger("cronjob")
    logger.info("Statistics for OUs at UiO")

    ap = argparse.ArgumentParser()
    ap.add_argument('-p', '--people', action='store_true',
                    help='Get people statistics')
    ap.add_argument('-u', '--users', action='store_true',
                    help='Get user statistics')
    ap.add_argument('-l', '--level', action='store',
                    choices=('fakultet', 'institutt', 'gruppe'),
                    required=True,
                    help='The granularity of the report')
    ap.add_argument('-e', '--perspective', action='store',
                    choices=('FS', 'SAP', 'LT'),
                    required=True,
                    help='OU perspective to use')
    args = ap.parse_args()

    db = Factory.get("Database")()
    const = Factory.get("Constants")(db)

    level = {"fakultet": 2, "institutt": 1, "gruppe": 0}[args.level]
    perspective = {
        "FS": const.perspective_fs,
        "SAP": const.perspective_sap,
        "LT": const.perspective_lt
    }[args.perspective]

    if args.people:
        people_result = generate_people_statistics(
            perspective,
            make_empty_statistics(level, db), level, db)
        display_statistics(people_result)

    if args.users:
        users_result = generate_account_statistics(
            perspective,
            make_empty_statistics(level, db), level, db)
        display_statistics(users_result)


if __name__ == '__main__':
    main()

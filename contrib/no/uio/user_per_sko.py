#!/usr/bin/env python
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

from __future__ import unicode_literals

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
import locale
from six import text_type


from Cerebrum.extlib.sets import Set
from Cerebrum.Utils import Factory

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
    keys = ('ansatt', 'student', 'a&s', 'tilknyttet', 'manuell', 'alle manuell')
    nosum = ('alle manuell')
    # Dictionary for totalling up numbers per affiliation
    total = dict([(key, 0) for key in keys])

    faculty_keys = statistics.keys()
    # Order the faculty output by sko
    faculty_keys.sort()

    # Yes, the code is ugly, but people do not like
    # pprint.print(dictionary)
    fak_width = 14
    field_width = 10
    fak_underline = u"-" * fak_width + u"+"
    field_underline = u"-" * field_width + u"+"
    fak_format = u"%%%ds" % fak_width
    field_format = u"%%%ds" % field_width

    values = (u"navn",) + tuple([x[0:field_width] for x in keys])
    enc = locale.getpreferredencoding()
    print (((fak_format + u"|") % u"fak") +
           ((field_format + u"|") * len(values)) % values).encode(enc)
    print (u"%s%s" % (fak_underline, field_underline * len(values))).encode(enc)

    def output_fak(faculty, value):
        if isinstance(faculty, types.TupleType):
            faculty_text = u"%02d%02d%02d" % faculty
        else:
            faculty_text = faculty

        message = ((fak_format % faculty_text) +
                   (u"|" + field_format) % value["name"][0:field_width])

        for key in keys:
            message += "|" + field_format % value[key]

        print message.encode(enc)

    for faculty in faculty_keys:
        value = statistics[faculty]
        if 'cum' in value:
            value['cum']['name'] = u'totalsum'
            if isinstance(faculty, types.TupleType):
                text = u'%02d****' % faculty[0]
            else:
                text = faculty + u' *'
            # print (u"%s%s" % (fak_underline,
            #                  field_underline * len(values))).encode(enc)
            output_fak(text, value['cum'])
        output_fak(faculty, value)
        for key in keys:
            total[key] += value[key]

    print ("%s%s" % (fak_underline, field_underline * len(values))).encode(enc)

    message = (fak_format + u"|") % u"Total" + (field_format + u"|") % u"--"
    summa = 0
    nosumma = 0
    for key in keys:
        message += (field_format + u"|") % total[key]
        if key not in nosum:
            summa += total[key]
        else:
            nosumma += total[key]

    print message.encode(enc), (field_format % '{} (+{})'.format(summa, nosumma)
                                .encode(enc))


def purge_0rows(statistics):
    for key in statistics.keys():
        val = statistics[key]
        cum = val.get('cum')
        empty = not any((val[k] for k in val.keys() if k not in ('cum',
                                                                 'name')))
        if cum and empty and any((cum[k] for k in cum.keys() if k != 'name')):
            cum['name'] = u'totalsum'
            if isinstance(key, types.TupleType):
                name = u'%02d****' % key[0]
            else:
                name = u'%s *' % key
            statistics[name] = cum
        if empty:
            del statistics[key]
    return statistics


def make_empty_statistics(level, db, extra_fak_sum=False):
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
    statistics[__undef_ou] = {"name": u"undef", 'cum': dict()}

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
                ou_name = u"N/A"

        statistics[ou_sko] = {"name": ou_name}
        if extra_fak_sum and ou_sko[1] == ou_sko[2] == 0:
            statistics[ou_sko]['cum'] = dict()

    for key in statistics.keys():
        value = {"ansatt": 0,
                 "a&s": 0,
                 "student": 0,
                 "tilknyttet": 0,
                 "manuell": 0,
                 "kun manuell": 0,
                 "alle manuell": 0,
                 None: 0,
                 }
        statistics[key].update(value)
        if 'cum' in statistics[key]:
            statistics[key]['cum'].update(value)

    logger.debug("Generating stats for %d top-level OUs" % len(statistics))
    return statistics


def make_affiliation_priorities(const):
    """
    Prepares and returns a dictionary sorting affiliations/stati according
    to this ruleset:

    When associating an entity with a faculty during statistics collection,
    we have to break ties. The ties are broken in the following fashion:

    1. First we compare affiliation; they are classified in this order
       ansatt, student, tilknyttet, manuell
    2. If an entity has two affiliations of the same type, affiliation
       status is used to break up ties in this order:

       ansatt -> vitenskaplig, tekadm, bilag, permisjon
       student -> aktiv, evu, alumni, perm, opptak, tilbud, soker, privatist
       tilknyttet -> emeritus, ekst_forsker, ekst_stip, fagperson, bilag,
                     gjesteforsker, sivilarbeider, diverse
       manuell -> don't care

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
    }


def generate_people_statistics(perspective, empty_statistics, level, db,
                               fak_cum=False):
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
        if fak_cum:
            ou_cum = locate_ou(aff["ou_id"], ou2parent, ou2stedkode, 2)

        # a&s (ansatt og student) has a special rule
        affs = [x["affiliation"] for x in affiliations]
        if (const.affiliation_student in affs and
                const.affiliation_ansatt in affs):
            affiliation_name = "a&s"
        else:
            affiliation_name = order[aff["affiliation"]]["name"]

        statistics[ou_result][affiliation_name] += 1
        if fak_cum:
            statistics[ou_cum]['cum'][affiliation_name] += 1

    return statistics


def generate_account_statistics(perspective, empty_statistics, level, db,
                                extra_cum=False):
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

        affiliations = account.list_accounts_by_type(
            account_id=row["account_id"],
            filter_expired=True,
            fetchall=True)
        # Affiliations have already been ordered according to priority. Just
        # pick the first one.
        if not affiliations:
            continue

        manual_only = all((x['affiliation'] == const.affiliation_manuell
                           for x in affiliations))
        manual = [x for x in affiliations
                  if x['affiliation'] == const.affiliation_manuell]

        if manual and not manual_only:
            for a in affiliations:
                if a['affiliation'] != const.affiliation_manuell:
                    aff = a
                    break
        else:
            aff = affiliations[0]
        ou_result = locate_ou(aff["ou_id"], ou2parent, ou2stedkode, level)
        if extra_cum:
            ou_cum = locate_ou(aff["ou_id"], ou2parent, ou2stedkode, 2)

        affs = [x["affiliation"] for x in affiliations]
        if (const.affiliation_student in affs and
                const.affiliation_ansatt in affs):
            affiliation_name = "a&s"
        else:
            affiliation_name = order[aff["affiliation"]]["name"]

        try:
            statistics[ou_result][affiliation_name] += 1
            if extra_cum:
                statistics[ou_cum]['cum'][affiliation_name] += 1
            if manual_only:
                statistics[ou_result]['kun manuell'] += 1
                if extra_cum:
                    statistics[ou_cum]['cum']['kun manuell'] += 1
        except:
            logger.error("ou_result = %s (%s; %s);",
                         ou_result, ou_result in statistics,
                         text_type(aff.ou_id))
            raise

        for aff in manual:
            ou_result = locate_ou(aff['ou_id'], ou2parent, ou2stedkode, level)
            try:
                statistics[ou_result]['alle manuell'] += 1
                if extra_cum:
                    statistics[locate_ou(aff['ou_id'],
                                         ou2parent,
                                         ou2stedkode,
                                         2)]['cum']['alle manuell'] += 1
            except:
                logger.error('ou_result = %s (%s; %s); (for manual)',
                             ou_result, ou_result in statistics,
                             text_type(aff.ou_id))

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
    ap.add_argument('-c', '--cumulate', action='store_true',
                    help='Add cumulated results to faculty')
    ap.add_argument('-e', '--perspective', action='store',
                    choices=('FS', 'SAP', 'LT'),
                    required=True,
                    help='OU perspective to use')
    ap.add_argument('-k', '--keep', action='store_true',
                    help='Keep all zero rows')
    args = ap.parse_args()

    db = Factory.get("Database")()
    const = Factory.get("Constants")(db)

    level = {"fakultet": 2, "institutt": 1, "gruppe": 0}[args.level]
    perspective = {
        "FS": const.perspective_fs,
        "SAP": const.perspective_sap,
        "LT": const.perspective_lt
    }[args.perspective]

    cum = args.cumulate

    if args.people:
        people_result = generate_people_statistics(
            perspective,
            make_empty_statistics(level, db, cum), level, db, cum)
        if not args.keep:
            purge_0rows(people_result)
        display_statistics(people_result)

    if args.users:
        users_result = generate_account_statistics(
            perspective,
            make_empty_statistics(level, db, cum), level, db, cum)
        if not args.keep:
            purge_0rows(users_result)
        display_statistics(users_result)


if __name__ == '__main__':
    main()

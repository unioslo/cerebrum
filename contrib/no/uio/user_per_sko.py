#! /usr/bin/env python2.2
# -*- coding: iso8859-1 -*-
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
This file is part of UiO-specific extensions of Cerebrum.

It provides various statistics about certain faculties at the UiO.

The faculty list is hardwired:

110000  	TF
120000  	JF
130000  	MF
140000  	HF
150000  	MN
160000  	OF
170000  	SV
180000  	UV
340000  	UB
3[123]0000 	SADM
2[78]0000 	Museumene
<others> 	Andre

<others> repsesents all OUs that do not fit into any of the aforementioned
categories. Given an OU, we select its corresponding faculty by walking up
the hierarchy tree until we see a parent from the faculty list. 


"""

import sys
import getopt
import copy

import cerebrum_path
import cereconf

from Cerebrum.extlib.sets import Set
from Cerebrum.Utils import Factory





def make_ou_map(db):
    """
    Return a dictionary mapping ou_ids to (fak,inst,avd) triplets
    (stedkoder).
    """

    ou = Factory.get("OU")(db)
    result = dict()
    
    for row in ou.get_stedkoder():
        result[int(row.ou_id)] = (int(row.fakultet),
                                  int(row.institutt),
                                  int(row.avdeling))
    # od

    logger.debug("%d ou -> stedkode mappings", len(result))
    return result
# end make_ou_map



def cache_affiliations(entity_index, selector, const):
    """
    Returns entity IDs grouped by affiliations.

    ENTITY_INDEX is the name of the id to extract
    SELECTOR is a function that performs the lookup

    The return value is a quintuple:

    (ANSATT, STUDENT, TILKNYTTET, MANUELL, UPERSONLIG)

    ... each element being a Set of IDs (as ints)
    """

    # employees
    logger.debug("Fetching employees")
    ansatt = Set([int(row[entity_index]) for row in
                  selector(affiliation = const.affiliation_ansatt)])

    # The memory footprint is too large to fetch all of them directly
    logger.debug("Fetching students")
    student = Set()
    for row in selector(affiliation = const.affiliation_student,
                        fetchall = False):
        student.add(int(row[entity_index]))
    # od
    
    logger.debug("Fetching tilknyttet")
    tilknyttet = Set([int(row[entity_index]) for row in
                      selector(affiliation = const.affiliation_tilknyttet)])

    logger.debug("Fetching manuell")
    manuell = Set([int(row[entity_index]) for row in
                   selector(affiliation = const.affiliation_manuell)])

    logger.debug("Fetching upersonlig")
    upersonlig = Set([int(row[entity_index]) for row in
                      selector(affiliation = const.affiliation_upersonlig)])
    logger.debug("Done fetching all")

    return (ansatt, student, tilknyttet, manuell, upersonlig)
# end cache_affiliations



def locate_faculty(ou_id, ou_to_stedkode, predefined_faculties):
    """
    Returns a faculty 'root' for a given ou_id

    (All OUs belong to a faculty. We return the faculty number for the root
    of the hierarchy that starts at OU_ID).
    """

    # 
    # This code assumes that OU.fakultet for ou with OU_ID designates the
    # proper faculty.

    ou_id = int(ou_id)
    faculty = "others"
    if ou_id in ou_to_stedkode:
        faculty = ou_to_stedkode[ou_id][0]
    # fi

    if faculty in predefined_faculties:
        return faculty
    else:
        return "others"
    # fi
# end locate_faculty



def people_statistics(ou_to_stedkode, db):
    """
    Collect statistics for _humans_ registered in Cerebrum.
    """

    person = Factory.get("Person")(db)
    const = Factory.get("Constants")(db)

    # First, group all person_ids by affiliations
    cache =  cache_affiliations("person_id",
                                lambda **rest:
                                  person.list_affiliations(**rest),
                                const)

    return make_statistics("person_id",
                           lambda **rest:
                             person.list_affiliations(**rest),
                           cache, 
                           ou_to_stedkode,
                           db)
# end people_statistics
    


def account_statistics(ou_to_stedkode, db):
    """
    Collect statistics for _accounts_ registered in Cerebrum.
    """

    const = Factory.get("Constants")(db)
    account = Factory.get("Account")(db)

    # First, group all account_ids by affiliations
    cache = cache_affiliations("account_id",
                               lambda **rest:
                                 account.list_accounts_by_type(**rest),
                               const)

    return make_statistics("account_id",
                           lambda **rest:
                             account.list_accounts_by_type(**rest),
                           cache,
                           ou_to_stedkode,
                           db)
# end account_statistics



def make_statistics(id, selector, cache, ou_to_stedkode, db):
    """
    Populate STATISTICS.

    STATISTICS is the dictionary with the result
    ID         is the id field we are interested in (person_id or account_id)
    SELECTOR   is the function that scans through all relevant records
    CACHE      is a quintuple with IDs grouped by different affiliations
    OU_TO_STEDKODE is a map of ou_id -> fs.stedkode
    DB         is the database reference.

    This function returns a dictionary with all the stats.
    """

    const = Factory.get("Constants")(db)
    
    (ansatt, student, tilknyttet, manuell, upersonlig) = cache

    # A dictionary with statistics information.
    # Keys are faculty numbers/designators for those faculties we are
    # interested in (this set is hardwired).
    # Values are also dictionaries, containing entity counts for various
    # affiliations.
    statistics = { 11 : {"name" : "TF"},
                   12 : {"name" : "JF"},
                   13 : {"name" : "MF"},
                   14 : {"name" : "HF"},
                   15 : {"name" : "MN"},
                   16 : {"name" : "OF"},
                   17 : {"name" : "SV"},
                   18 : {"name" : "UV"},
                   34 : {"name" : "UB"},
                   31 : {"name" : "SADM"},
                   32 : {"name" : "SADM"},
                   33 : {"name" : "SADM"},
                   27 : {"name" : "Museumene"},
                   28 : {"name" : "Museumene"},
                   "others" : {"name" : "Andre"}, }

    for key in statistics.keys():
        value = { "ansatt"     : 0,
                  "a&s"        : 0,
                  "student"    : 0,
                  "tilknyttet" : 0,
                  "manuell"    : 0,
                  "upersonlig" : 0,
                  None         : 0, }
        statistics[key].update(value)
    # od

    predefined_faculties = statistics.keys()

    # Okey, the rules are a bit annoying -- we want to split people into
    # these five groups:
    #
    # ansatt   - those with affiliation 'ANSATT' but without affiliation
    #            'STUDENT'
    # a&s      - those with affiliation 'ANSATT' and 'STUDENT'.
    # student  - those with affiliation 'STUDENT' but without affiliation
    #            'ANSATT'
    # tilknyttet - those with affiliation 'TILKNYTTET' but without 'ANSATT' or
    #              'STUDENT'.
    # manuell - those with affiliation 'MANUELL' but without
    #           'ANSATT'/'STUDENT'/'TILKNYTTET'
    # upersonlig - those who do not fall into any of the aforementioned 4
    #              categories.
    row_count = 0; limit = 10000
    for row in selector(fetchall = False):
        row_count += 1
        if row_count % limit== 0:
            logger.debug("Next %d rows (%d) have been processed", limit, row_count)
        # fi
        
        entity_id = int(row[id])
        
        faculty = locate_faculty(row.ou_id,
                                 ou_to_stedkode,
                                 predefined_faculties)

        affiliation = int(row.affiliation)

        # 'None' means that the affiliation was discarded, because there
        # existed an affiliation with "higher precedence".
        affiliation_translated = None

        # FIXME: this code is too ugly
        if affiliation == int(const.affiliation_ansatt):
            if entity_id not in student:
                affiliation_translated = "ansatt"
            else:
                affiliation_translated = "a&s"
            # fi
        elif affiliation == int(const.affiliation_student):
            if entity_id not in ansatt:
                affiliation_translated = "student"
            # fi

            # NB! Do *not* count 'a&s' here (or we would have twice as
            # many entries in this category (one from 'affiliation_ansatt'
            # and one from 'affiliation_student')). Pretend this entry
            # did not exist.
        elif affiliation == int(const.affiliation_tilknyttet):
            if (entity_id not in student and
                entity_id not in ansatt):
                affiliation_translated = "tilknyttet"
            # fi
        elif affiliation == int(const.affiliation_manuell):
            if (entity_id not in student and
                entity_id not in ansatt and
                entity_id not in tilknyttet):
                affiliation_translated = "manuell"
            # fi
        elif affiliation == int(const.affiliation_upersonlig):
            if (entity_id not in student and
                entity_id not in ansatt and
                entity_id not in tilknyttet and
                entity_id not in manuell):
                affiliation_translated = "upersonlig"
            # fi
        # fi

        # Both keys *are* necessarily present. KeyError is structurally
        # impossible
        statistics[faculty][affiliation_translated] += 1
    # od

    return statistics
# end make_statistics



def display_statistics(statistics):
    """
    STATISTICS is a dictionary indexed by faculty numbers (K) and with
    values (V) being dictionaries with statistics information.

    This function assumes that _all_ Vs have the exactly same set of keys.
    """

    logger.debug("Statistics:")

    keys = ("student", "ansatt", "a&s", "tilknyttet", "manuell",
            "upersonlig", None)
    total = dict([(key, 0) for key in keys])

    faculty_keys = statistics.keys()
    # Order the faculty output by faculty name
    faculty_keys.sort(lambda x, y: cmp(statistics[x]["name"],
                                       statistics[y]["name"]))
    # Header first
    #             fak  navn stud ans  a&s  tilk man  uper
    print ("%7s|%7s|%7s|%7s|%7s|%7s|%7s|%7s|%7s" %
           (("fak", "navn") + tuple([str(x)[0:7] for x in keys])))
    print "-" * 80

    for faculty in faculty_keys:
        value = statistics[faculty]
        message = "%7s|%7s" % (faculty, value["name"][0:7])

        for key in keys:
            message += "|%7s" % value[key]
            total[key] += value[key]
        # od
        
        print message
    # od
    print "-" * 80

    message = "%7s|%7s" % ("Total", "--")
    for key in keys:
        message += "|%7s" % total[key]
    # od
    print message
# end display_statistics



def main():

    global logger
    logger = Factory.get_logger("console")
    logger.info("Statistics for OUs at UiO")

    options, rest = getopt.getopt(sys.argv[1:],
                                  "pu",
                                  ["people",
                                   "users",])
    process_people = False
    process_users = False
    for option, value in options:
        if option in ("-p", "--people"):
            process_people = True
        elif option in ("-u", "--users"):
            process_users = True
        # fi
    # od

    db = Factory.get("Database")()
    ou_to_stedkode = make_ou_map(db)

    if process_people:
        people_result = people_statistics(ou_to_stedkode, db)
        display_statistics(people_result)
    # fi

    if process_users:
        users_result = account_statistics(ou_to_stedkode, db)
        display_statistics(users_result)
    # fi
# end main





if __name__ == '__main__':
    main()
# fi

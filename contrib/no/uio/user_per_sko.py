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
This file is a UiO-specific extensions of Cerebrum.

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



def locate_faculty(ou_id, ou_to_stedkode, predefined_faculties):
    """
    Returns a faculty 'root' for a given ou_id

    (All OUs belong to a faculty. We return the faculty number for the root
    of the hierarchy that starts at OU_ID).
    """

    # 
    # This code assumes that OU.fakultet for ou with OU_ID designates the
    # proper faculty. I do not know whether it is actually the case
    # 

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
    # Order the faculty output by faculty name
    faculty_keys.sort(lambda x, y: cmp(statistics[x]["name"],
                                       statistics[y]["name"]))

    # Header first, trim names till 7 characters
    values = ("fak", "navn") + tuple([str(x)[0:7] for x in keys]) 
    print ("%7s|" * len(values)) % values
    print "-------+" * len(values)

    for faculty in faculty_keys:
        value = statistics[faculty]
        message = "%7s|%7s" % (faculty, value["name"][0:7])

        for key in keys:
            message += "|%7s" % value[key]
            total[key] += value[key]
        # od
        
        print message
    # od
    print "-------+" * len(values)

    message = "%7s|%7s" % ("Total", "--")
    sum = 0
    for key in keys:
        message += "|%7s" % total[key]
        sum += total[key]
    # od

    print message, "|%7s" % sum
# end display_statistics



def make_empty_statistics():
    """
    Return an empty dictionary suitable for statistics collection
    """

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

    return statistics
# end make_empty_statistics



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

    return { int(const.affiliation_ansatt) :
               { "name"  : "ansatt",
                 "value" : 0,
                 int(const.affiliation_status_ansatt_vit) : 0,
                 int(const.affiliation_status_ansatt_tekadm) : 1,
                 int(const.affiliation_status_ansatt_bil) : 2,
                 int(const.affiliation_status_ansatt_perm) : 3
               },
             int(const.affiliation_student) :
               { "name"  : "student",
                 "value" : 1,
                 int(const.affiliation_status_student_aktiv) : 0,
                 int(const.affiliation_status_student_evu) : 1,
                 int(const.affiliation_status_student_alumni) : 2,
                 int(const.affiliation_status_student_perm) : 3,
                 int(const.affiliation_status_student_opptak) : 4,
                 int(const.affiliation_status_student_tilbud) : 5,
                 int(const.affiliation_status_student_soker) : 6,
                 int(const.affiliation_status_student_privatist) : 7,
               },
             int(const.affiliation_tilknyttet) :
               { "name" : "tilknyttet",
                 "value" : 2,
                 int(const.affiliation_tilknyttet_emeritus) : 0,
                 int(const.affiliation_tilknyttet_ekst_forsker) : 1,
                 int(const.affiliation_tilknyttet_ekst_stip) : 2,
                 int(const.affiliation_tilknyttet_fagperson) : 3,
                 int(const.affiliation_tilknyttet_bilag) : 4,
                 int(const.affiliation_tilknyttet_gjesteforsker) : 5,
                 int(const.affiliation_tilknyttet_sivilarbeider) : 6,
                 int(const.affiliation_tilknyttet_diverse) : 7,
               },
             int(const.affiliation_manuell) :
               { "name" : "manuell",
                 "value" : 3,
               },
             int(const.affiliation_upersonlig) :
               { "name" : "upersonlig",
                 "value" : 4,
               },
             }
    return status_values
# end make_affiliation_priorities



def people_statistics(ou_to_stedkode, db):
    """
    Collect statistics about people.

    The strategy is pretty straightforward:

    for each person P
       look at P's affiliations A
       sort them according to the rules in make_affiliation_priorities
       select the first affiliation FA
       register P's contribution under faculty derived from FA.ou_id and
       affiliation derived from FA.affiliation
    done

    This will ensure that each person is counted only once, despite having
    multiple affiliations to multiple faculties.

    NB! A silly thing is that the ruleset is incomplete. Harass baardj for a
    more complete specification.
    """

    people = Factory.get("Person")(db)
    const = Factory.get("Constants")(db)

    statistics = make_empty_statistics()
    predefined_faculties = statistics.keys()

    # sort order for affiliations/statuses
    order = make_affiliation_priorities(const)
    row_count = 0; limit = 10000

    # Keep track of accounts that had been processed
    processed = Set()

    for row in people.list_affiliations(fetchall = False):
        row_count += 1
        if row_count % limit == 0:
            logger.debug("Next %d (%d) rows", limit, row_count)
        # fi

        if int(row.person_id) in processed:
            continue
        else:
            processed.add(int(row.person_id))
        # fi

        # Fetch all of row's affiliations. 
        affiliations = people.list_affiliations(person_id = row["person_id"])
        if not affiliations:
            continue
        # fi

        affiliations.sort(lambda x, y: cmp(order[x.affiliation],
                                           order[y.affiliation])
                                    or cmp(order.get(x.status, 0),
                                           order.get(y.status, 0)))
        aff = affiliations[0]
        faculty = locate_faculty(aff.ou_id, ou_to_stedkode,
                                 predefined_faculties)

        affs = [ x.affiliation for x in affiliations ]
        if (const.affiliation_student in affs and
            const.affiliation_ansatt in affs):
            affiliation_name = "a&s"
        else:
            affiliation_name = order[aff.affiliation]["name"]
        # fi
        
        statistics[faculty][affiliation_name] += 1
    # od

    return statistics
# end people_statistics



def account_statistics(ou_to_stedkode, db):
    """
    Collect statistics about accounts.

    for each account A
        look at A's affiliations F
        sort them according to the rules in make_affiliation_priorities
                                  (and by using priority to break ties)
        select the first affiliation FA
        register A's contribution under faculty derived from FA.ou_id and
        affiliation derived from FA.affiliation
    done
    """

    account = Factory.get("Account")(db)
    const = Factory.get("Constants")(db)

    statistics = make_empty_statistics()
    predefined_faculties = statistics.keys()

    # sort order for affiliations
    order = make_affiliation_priorities(const)
    row_count = 0; limit = 10000

    # Keep track of accounts that had been processed
    processed = Set()

    for row in account.list_accounts_by_type(filter_expired = True,
                                             fetchall = False):
        row_count += 1
        if row_count % limit == 0:
            logger.debug("Next %d (%d) rows", limit, row_count)
        # fi

        if int(row.account_id) in processed:
            continue
        else:
            processed.add(int(row.account_id))
        # fi

        affiliations = account.list_accounts_by_type(account_id=row.account_id,
                                                     filter_expired = True,
                                                     fetchall = True)

        # Affiliations have already been ordered according to priority. Just
        # pick the first one.
        if not affiliations:
            continue
        # fi

        aff = affiliations[0]
        faculty = locate_faculty(aff.ou_id, ou_to_stedkode,
                                 predefined_faculties)

        affs = [ x.affiliation for x in affiliations ]
        if (const.affiliation_student in affs and
            const.affiliation_ansatt in affs):
            affiliation_name = "a&s"
        else:
            affiliation_name = order[aff.affiliation]["name"]
        # fi
        
        statistics[faculty][affiliation_name] += 1
    # od

    return statistics
# end account_statistics



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
    new_rules = False
    
    for option, value in options:
        if option in ("-p", "--people"):
            process_people = True
        elif option in ("-u", "--users"):
            process_users = True
        elif option in ("-n",):
            new_rules = True
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

# arch-tag: ca691df0-6369-4575-9a1e-1c31eef5749d

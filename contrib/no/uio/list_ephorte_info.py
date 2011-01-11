#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2010 University of Oslo, Norway
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
List statistical information about ephorte persons. 


"""

import sys
import getopt
import cerebrum_path
from Cerebrum.Utils import Factory

logger = Factory.get_logger("console")
db = Factory.get('Database')()
const = Factory.get('Constants')(db)

options = {"detailed_reports": False,
           "output": sys.stdout}


def present_multi_results(output_stream, result, topic, header=(),
                          line_format=None, line_sep=" "*3):
    """Generic method for presenting results about multiple data to
    the user.

    It expects that 'result' is the result of an SQL query, where the
    first (only?) column contains the entity ID of entities that fit
    the criterea of the particular test/search.

    header is expected to be a list/tuple of strings of same length as
    the result tuples.
    """
    output_stream.write("\n%s: %i\n" % (topic, len(result)))
    if options["detailed_reports"]:
        if header:
            tmp = line_sep.join(header)
            output_stream.write(tmp + "\n")
            output_stream.write("-"*70 + "\n")
        for row in result:
            if line_format:
                line = line_format % tuple(map(str, row))
            else:
                line = line_sep.join(map(str, row))
            output_stream.write(line + "\n")


def generate_ephorte_statistics(output_stream):
    # Get number of people with ephorte spread
    result = db.query_1("""SELECT count(distinct entity_id)
    FROM [:table schema=cerebrum name=entity_spread]
    WHERE spread = :ephorte_spread""",
                        {"ephorte_spread": int(const.spread_ephorte_person)
                         })
    output_stream.write("\nNumber of people with ephorte spread: %s\n" %
                        result)

    # Get number of people with ephorte roles
    result = db.query_1("""SELECT count(distinct person_id)
    FROM [:table schema=cerebrum name=ephorte_role]""")
    output_stream.write("\nNumber of people with one or more ephorte roles: %s\n" %
                        result)

    # List number of people with ANSATT AFF from SAP with a non-expired account
    result = db.query_1("""SELECT count(foo.person_id)
    FROM (SELECT person_id FROM [:table schema=cerebrum name=person_affiliation_source]
          WHERE affiliation = :ansatt_aff AND source_system = :sap_source
          INTERSECT
          SELECT owner_id FROM [:table schema=cerebrum name=account_info]
          WHERE owner_type = :person_owner AND (expire_date is null or expire_date > now())) as foo
          """,
                        {"ansatt_aff":int(const.affiliation_ansatt),
                         "sap_source":int(const.system_sap),
                         "person_owner":int(const.entity_person)})
    output_stream.write("\nNumber of people with ANSATT aff from SAP and active acounts : %s\n" %
                        result)

    # List number of people with only TILKNYTTET AFF and ephorte roles
    result = db.query("""SELECT foo.person_id
    FROM (((SELECT person_id FROM [:table schema=cerebrum name=person_affiliation_source]
           WHERE affiliation = :tilknyttet_aff 
           INTERSECT
           SELECT owner_id FROM [:table schema=cerebrum name=account_info]
           WHERE owner_type = :person_owner AND (expire_date is null or expire_date > now()))
          EXCEPT
          (SELECT person_id FROM [:table schema=cerebrum name=person_affiliation_source]
           WHERE affiliation = :ansatt_aff AND source_system = :sap_source
           INTERSECT
           SELECT owner_id FROM [:table schema=cerebrum name=account_info]
           WHERE owner_type = :person_owner AND (expire_date is null or expire_date > now())))
          INTERSECT
          SELECT person_id FROM [:table schema=cerebrum name=ephorte_role])
           as foo
          """, 
                        {"ansatt_aff":int(const.affiliation_ansatt),
                         "tilknyttet_aff":int(const.affiliation_tilknyttet),
                         "sap_source":int(const.system_sap),
                         "person_owner":int(const.entity_person)})
    if result:
        present_multi_results(output_stream, result,
                              "Number of people with only TLKNYTTET aff and ephorte_roles")

    # Get people with ephorte spread, but no roles
    result = db.query("""SELECT entity_id
    FROM [:table schema=cerebrum name=entity_spread]
    WHERE spread = :ephorte_spread
    EXCEPT
    SELECT distinct person_id
    FROM [:table schema=cerebrum name=ephorte_role]""",
                      {"ephorte_spread": int(const.spread_ephorte_person)
                       })
    if result:
        present_multi_results(output_stream, result,
                              "Number of people with ephorte spread, but no roles")

    # Get number of people with only manually given roles
    result = db.query("""SELECT distinct person_id
    FROM [:table schema=cerebrum name=ephorte_role] EXCEPT
    SELECT distinct person_id FROM [:table schema=cerebrum name=ephorte_role]
    WHERE auto_role = 'T'""")
    if result:
        present_multi_results(output_stream, result,
                              "Number of people with only manually given roles")


    # List people with ephorte spread but no ANSATT aff
    result = db.query("""SELECT distinct entity_id
    FROM [:table schema=cerebrum name=entity_spread]
    WHERE spread=:ephorte_spread
    EXCEPT (SELECT person_id
            FROM [:table schema=cerebrum name=person_affiliation_source]
            WHERE affiliation = :ansatt_aff AND source_system = :sap_source
            INTERSECT
            SELECT owner_id FROM [:table schema=cerebrum name=account_info]
            WHERE owner_type = :person_owner AND (expire_date is null or expire_date > now()))
            """,
                        {"ephorte_spread":int(const.spread_ephorte_person),
                         "ansatt_aff":int(const.affiliation_ansatt),
                         "sap_source":int(const.system_sap),
                         "person_owner":int(const.entity_person)})
    if result:
        present_multi_results(output_stream, result,
                              "Number of people with ephorte spread, but no ANSATT aff")

    

def usage(message=None):
    """Gives user info on how to use the program and its options."""
    if message is not None:
        print >>sys.stderr, "\n%s" % message

    print >>sys.stderr, __doc__


def main(argv=None):
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   "hf:d",
                                   ["help", "file", "details"])
    except getopt.GetoptError, error:
        usage(message=error.msg)
        return 1

    output_stream = options["output"]

    for opt, val in opts:
        if opt in ('-h', '--help',):
            usage()
            return 0
        if opt in ('-d', '--details',):
            options["detailed_reports"] = True
        if opt in ('-f', '--file',):
            output_stream = open(val, "w")

    generate_ephorte_statistics(output_stream)

    if output_stream != sys.stdout:
        output_stream.close()


if __name__ == "__main__":
    main()

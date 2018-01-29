#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2006-2011 University of Oslo, Norway
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

# $Id$

import sys
import getopt

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory

progname = __file__.split("/")[-1]

__doc__ = """
Usage: %s [options]

   --help       Prints this message and quits
   --file FILE  Send output to FILE, rather than stdout

   Report options:
   --all        Generate all reports
   --entities   Generate reports on entities that may or may not
                represent things that need to be addressed
   --numbers    Generate generic statistics about database content
   --details    For '--entitities', provide entity IDs for the
                entities 'suffering' the given 'problem'

This program can generate two different sets of statistics; one that
presents various numeric data about the entities in the database
(number of accounts, number of persons by affiliation, etc) and one
that counts number of entities within various areas that may or may
not represent problems that need to be dealt with in some way. The
last variety can also provide the entity IDs that fall within the
given problematic topic (for lack of better term)

""" % progname

__version__ = "$Revision$"
# $Source$


logger = Factory.get_logger("console")

db = Factory.get('Database')()
const = Factory.get('Constants')(db)

options = {"report_all": False,
           "report_entities": False,
           "report_numbers": False,
           "report_names": False,
           "detailed_reports": False,
           "output": sys.stdout}


def present_entity_results(output_stream, result, topic):
    """Generic method for presenting results about entitites to the
    user.

    It expects that 'result' is the result of an SQL query, where the
    first (only?) column contains the entity ID of entities that fit
    the criterea of the particular test/search.

    """
    output_stream.write("\n%s: %i\n" % (topic, len(result)))
    if options["detailed_reports"]:
        IDs = [str(row[0]) for row in result]
        output_stream.write("Entity IDs for these are: ")
        output_stream.write(", ".join(IDs) + "\n");
    

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
    

def present_grouped_results(output_stream, result, topic):
    """Generic method for presenting grouped results to the user.

    It expects that 'result' is the result of an SQL query, where the
    first column contains the 'label' while the second column
    represents the count/result associated with that particular
    label.

    Any sorting should be done before the result is sent to the
    method.

    """
    output_stream.write("%s:\n" % topic)
    for row in result:
        output_stream.write("    %-36s: %6i\n" % (str(row[0]), row[1]))


def present_nested_grouped_results(output_stream, result, topic):
    """Generic method for presenting results with nested groups to the
    user.

    It expects that 'result' is the result of an SQL query, where the
    first column contains the main categories, the second column
    represents the sub-categories and the third column represents the
    count/result associated with that particular
    category/sub-category.

    Any sorting should be done before the result is sent to the
    method.

    """
    output_stream.write("%s:\n" % topic)
    outer_group = ""
    for row in result:
        if row[0] != outer_group:
            outer_group = row[0]
            output_stream.write("    %-15s %-20s: %6i\n" %
                                (str(row[0]), str(row[1]), row[2]))
        else:
            output_stream.write("    %-15s %-20s: %6i\n" %
                                ("", str(row[1]), row[2]))

    

def present_single_result(output_stream, result, topic):
    """Generic method for presenting 'single' results to the user.

    It expects that 'result' is the result of an SQL query, where the
    first (only?) column of the first (only?) row contains the number
    the represents the result for this particular test/search.

    """
    output_stream.write("\n%-40s: %6i\n" % (topic, result[0][0]))
    

def generate_person_statistics(output_stream):
    output_stream.write("\nReports dealing with person entities\n")
    output_stream.write("------------------------------------\n")

    # Report people that lack both a first name and a last name
    result = db.query("""SELECT person_id
                         FROM [:table schema=cerebrum name=person_info]
                         EXCEPT
                         SELECT pn1.person_id 
                         FROM [:table schema=cerebrum name=person_name] pn1,
                              [:table schema=cerebrum name=person_name] pn2
                         WHERE
                              pn1.source_system not in (:system_fs, :system_sap) AND
                              pn1.person_id = pn2.person_id AND
                              pn1.name_variant = :firstname AND
                              pn2.name_variant = :lastname
                         """, {"firstname": int(const.name_first),
                               "lastname": int(const.name_last),
                               "system_fs": int(const.system_fs),
                               "system_sap": int(const.system_sap),
                               })

    present_entity_results(output_stream, result,
                    "Number of people lacking both first and last name")

    # TODO 2007-01-17 amveha: people without f;dselsnummer (11 digits)
    # or with f;dselsnummer not associated with an authoritative
    # source system.

    # People without birthdates or birthdates in the future
    # TBD 2007-01-03 amveha: Are there other criterea that can qualify
    # as invalid wrt birthdates? Such as being born on Jan 1 1901?
    result = db.query("""SELECT person_id
                         FROM [:table schema=cerebrum name=person_info]
                         WHERE
                              -- No birthdate set:
                              birth_date is NULL OR
                              -- Birthdate in future:
                              birth_date > NOW()
                         """)
                      
    present_entity_results(output_stream, result, "Number of people with unsatisfactory birthdates")

    # Report people without any accounts
    result = db.query("""SELECT person_id
                         FROM [:table schema=cerebrum name=person_info]
                         EXCEPT
                         SELECT owner_id
                         FROM [:table schema=cerebrum name=account_info]
                         """)
                      
    present_entity_results(output_stream, result, "Number of people with no accounts")

    # People without any affiliations
    result = db.query("""SELECT person_id
                         FROM [:table schema=cerebrum name=person_info]
                         EXCEPT
                         SELECT person_id
                         FROM [:table schema=cerebrum name=person_affiliation_source]
                         WHERE deleted_date is NULL OR deleted_date > NOW()
                         """)
                      
    present_entity_results(output_stream, result, "Number of people with no affiliations")


def generate_person_name_statistics(output_stream):
    # Report people with to many white space characters in the name
    result = db.query("""SELECT distinct pn.person_id, eei.external_id, pn.name
                         FROM [:table schema=cerebrum name=person_name] pn,
                              [:table schema=cerebrum name=entity_external_id] eei,
                              [:table schema=cerebrum name=authoritative_system_code] ac,
                              [:table schema=cerebrum name=person_affiliation] pa
                         WHERE pn.name similar to '%%  +%%' AND
                               pn.name_variant = :firstname AND
                               eei.entity_id = pn.person_id AND
                               eei.id_type = :sap_ansattnr AND
                               ac.code = :system_sap AND
                               ac.code = pn.source_system AND
                               pa.person_id = pn.person_id AND
                               pa.affiliation = :affiliation_ansatt
                               order by pn.person_id
                         """, {"firstname": int(const.name_first),
                               "sap_ansattnr": int(const.externalid_sap_ansattnr),
                               "system_sap": int(const.system_sap),
                               "affiliation_ansatt": int(const.affiliation_ansatt)
                               })
    topic = "Number of persons from SAP with too many white spaces in first name"
    header=("Person id", "SAP ansattnr", "Name")
    line_format = "%%%ds   %%%ds   %%s" % (len(header[0]), len(header[1]))
    present_multi_results(output_stream, result, topic, header, line_format)


def generate_account_statistics(output_stream):
    output_stream.write("\nReports dealing with account entities\n")
    output_stream.write("-------------------------------------\n")
    # Accounts without password information
    result = db.query("""SELECT account_id
                         FROM [:table schema=cerebrum name=account_info]
                         EXCEPT
                         SELECT account_id
                         FROM [:table schema=cerebrum name=account_authentication]
                         """)
    present_entity_results(output_stream, result, "Number of accounts without password info") 
    
    # Accounts without spread
    result = db.query("""SELECT account_id
                         FROM [:table schema=cerebrum name=account_info]
                         EXCEPT
                         SELECT entity_id
                         FROM [:table schema=cerebrum name=entity_spread]
                         WHERE entity_type = :entity_type_account
                         """, {"entity_type_account": int(const.entity_account)})

    present_entity_results(output_stream, result, "Number of accounts without spread")
    
    # TODO 2007-01-17 amveha: accounts without home area.
    
    # Personal user accounts without account_type
    result = db.query("""SELECT account_id
                         FROM [:table schema=cerebrum name=account_info]
                         EXCEPT
                         SELECT account_id
                         FROM [:table schema=cerebrum name=account_type]
                         """)
    present_entity_results(output_stream, result, "Number of personal accounts without account_type")
    
    # System (non-personal) accounts without np_type set
    # TBD 2007-01-05 amveha: This test is redundant, since there is a
    # check-contraint in the DB that makes the combination
    # invalid. Remove test?
    result = db.query("""SELECT account_id
                         FROM [:table schema=cerebrum name=account_info]
                         WHERE
                              owner_type = :entity_type_group AND
                              np_type IS NULL                         
                         """, {"entity_type_group": int(const.entity_group)})
    present_entity_results(output_stream, result, "Number of system accounts without np_type")
    

def generate_group_statistics(output_stream):
    output_stream.write("\nReports dealing with group entities\n")
    output_stream.write("-----------------------------------\n")
    
    # Groups without any members at all, directly or indirectly
    result = db.query("""SELECT group_id
                         FROM [:table schema=cerebrum name=group_info]
                         EXCEPT
                         SELECT group_id
                         FROM [:table schema=cerebrum name=group_member]
                         """)
    present_entity_results(output_stream, result, "Number of groups without any members at all")
    
    # TODO 2007-01-17 amveha: Groups without any members at all,
    # directly or indirectly.
        
    # Groups without spread
    result = db.query("""SELECT group_id
                         FROM [:table schema=cerebrum name=group_info]
                         EXCEPT
                         SELECT entity_id
                         FROM [:table schema=cerebrum name=entity_spread]
                         WHERE entity_type = :entity_type_group
                         """, {"entity_type_group": int(const.entity_group)})

    present_entity_results(output_stream, result, "Number of groups without spread")

    # Groups without descriptions
    result = db.query("""SELECT group_id
                         FROM [:table schema=cerebrum name=group_info]
                         WHERE 
                              -- No description set...
                              description is NULL OR
                              -- ... or description is empty
                              description LIKE ''
                         """)
    present_entity_results(output_stream, result, "Number of groups without description")


def generate_ou_statistics(output_stream):
    output_stream.write("\nReports dealing with OU entities\n")
    output_stream.write("--------------------------------\n")
    # TODO 2007-01-17: Valid OU-formats (stedkode or OU)
    
    # OUs with name discrepencies
    result = db.query("""SELECT ou_id
                         FROM [:table schema=cerebrum name=ou_info]
                         WHERE name LIKE ''
                         """)
    present_entity_results(output_stream, result, "Number of OUs with no 'name'")

    result = db.query("""SELECT ou_id
                         FROM [:table schema=cerebrum name=ou_info]
                         WHERE acronym LIKE '' OR acronym IS NULL
                         """)
    present_entity_results(output_stream, result, "Number of OUs with no 'acronym'")
    
    result = db.query("""SELECT ou_id
                         FROM [:table schema=cerebrum name=ou_info]
                         WHERE short_name LIKE '' OR short_name IS NULL
                         """)
    present_entity_results(output_stream, result, "Number of OUs with no 'short_name'")
    
    result = db.query("""SELECT ou_id
                         FROM [:table schema=cerebrum name=ou_info]
                         WHERE display_name LIKE '' OR display_name IS NULL
                         """)
    present_entity_results(output_stream, result, "Number of OUs with no 'display_name'")
    
    result = db.query("""SELECT ou_id
                         FROM [:table schema=cerebrum name=ou_info]
                         WHERE sort_name LIKE '' OR sort_name IS NULL
                         """)
    present_entity_results(output_stream, result, "Number of OUs with no 'sort_name'")
    
    # Orphan OUs (no parent)
    result = db.query("""SELECT ou_id
                         FROM [:table schema=cerebrum name=ou_structure]
                         WHERE parent_id IS NULL
                         """)
    present_entity_results(output_stream, result, "Number of OUs with no parent")

    # TBD 2007-01-17 amveha: The spec calls for structure dump, but
    # also that it might not be necessary. Do we want it or not?


def generate_cerebrum_numbers(output_stream):
    # TODO 2007-01-17 amveha: Modules in use
    
    # Person count...
    result = db.query("""SELECT COUNT(*)
                         FROM [:table schema=cerebrum name=person_info]
                         """)
    present_single_result(output_stream, result, "Number of persons")
    # ... per affiliation...
    result = db.query("""SELECT pac.code_str, count(distinct pa.person_id)
                         FROM [:table schema=cerebrum name=person_affiliation] pa,
                              [:table schema=cerebrum name=person_affiliation_code] pac
                         WHERE pa.affiliation = pac.code
                         GROUP BY pac.code_str
                         ORDER BY pac.code_str
                         """)
    present_grouped_results(output_stream, result, "- distributed by affiliation")
    # ... and by affiliation status
    result = db.query("""SELECT pac.code_str, pasc.status_str, count(distinct pas.person_id)
                         FROM [:table schema=cerebrum name=person_affiliation_source] pas,
                              [:table schema=cerebrum name=person_affiliation_code] pac,
                              [:table schema=cerebrum name=person_aff_status_code] pasc
                         WHERE
                              pas.affiliation = pac.code AND
                              pas.status = pasc.status
                         GROUP BY pac.code_str, pasc.status_str
                         ORDER BY pac.code_str, pasc.status_str
                         """)
    present_nested_grouped_results(output_stream, result, "- distributed by affiliation status")
    
    # Account-count...
    result = db.query("""SELECT COUNT(*)
                         FROM [:table schema=cerebrum name=account_info]
                         """)
    present_single_result(output_stream, result, "Number of accounts")

    # ... per account_type ...
    result = db.query("""SELECT pac.code_str, count(*)
                         FROM [:table schema=cerebrum name=account_type] at,
                              [:table schema=cerebrum name=person_affiliation_code] pac
                         WHERE at.affiliation = pac.code
                         GROUP BY pac.code_str
                         ORDER BY pac.code_str
                     """)
    present_grouped_results(output_stream, result, "- distributed by account type")
    
    # ... per spread...
    result = db.query("""SELECT sc.code_str, count(*)
                         FROM [:table schema=cerebrum name=entity_spread] es,
                              [:table schema=cerebrum name=spread_code] sc
                         WHERE
                              es.spread = sc.code AND
                              es.entity_type = :entity_type_account
                         GROUP BY sc.code_str
                         ORDER BY sc.code_str
                         """, {"entity_type_account": int(const.entity_account)})
    present_grouped_results(output_stream, result, "- distributed by spread")
    # TODO 2007-01-17 amveha: - per host/disk
    
    # OU-count
    result = db.query("""SELECT COUNT(*)
                         FROM [:table schema=cerebrum name=ou_info]
                         """)
    present_single_result(output_stream, result, "Number of OUs")

    # Group-count...
    result = db.query("""SELECT COUNT(*)
                         FROM [:table schema=cerebrum name=group_info]
                         """)
    present_single_result(output_stream, result, "Number of groups")
    # ...per spread...
    result = db.query("""SELECT sc.code_str, count(*)
                         FROM [:table schema=cerebrum name=entity_spread] es,
                              [:table schema=cerebrum name=spread_code] sc
                         WHERE
                              es.spread = sc.code AND
                              es.entity_type = :entity_type_group
                         GROUP BY sc.code_str
                         ORDER BY sc.code_str
                         """, {"entity_type_group": int(const.entity_group)})
    present_grouped_results(output_stream, result, "- distributed by spread")
    
    # TODO 2007-01-17 amveha: Migrated persons not affected by
    # authoratative source systems.

    # TODO 2007-01-17 amveha: Registered e-mail-domains.

    # TODO 2007-01-17 amveha: Resgistered hosts/disks (with description).


def usage(message=None):
    """Gives user info on how to use the program and its options."""
    if message is not None:
        print >>sys.stderr, "\n%s" % message

    print >>sys.stderr, __doc__


def main(argv=None):
    """Main processing hub for program."""
    if argv is None:
        argv = sys.argv
        
    try:
        opts, args = getopt.getopt(argv[1:],
                                   "haef:dns",
                                   ["help", "all", "entities", "file=",
                                    "details", "numbers", "sap_names"])
    except getopt.GetoptError, error:
        usage(message=error.msg)
        return 1

    output_stream = options["output"]

    for opt, val in opts:
        if opt in ('-h', '--help',):
            usage()
            return 0
        if opt in ("-a", "--all", "-e", "--entities"):
            options["report_entities"] = True
        if opt in ("-a", "--all", "-n", "--numbers"):
            options["report_numbers"] = True
        if opt in ('-d', '--details',):
            options["detailed_reports"] = True
        if opt in ('-s', '--sap_names',):
            options["report_names"] = True
        if opt in ('-f', '--file',):
            output_stream = open(val, "w")

    if options["report_numbers"]:
        output_stream.write("\nCerebrum in numbers\n")
        output_stream.write("===================\n")
        generate_cerebrum_numbers(output_stream)

    if options["report_entities"]:
        output_stream.write("\nInformation about possibly problematic entities\n")
        output_stream.write("===============================================\n")
        generate_person_statistics(output_stream)
        generate_account_statistics(output_stream)
        generate_group_statistics(output_stream)
        generate_ou_statistics(output_stream)

    if options["report_names"]:
        output_stream.write("\nInformation about problematic person names\n")
        output_stream.write("===============================================\n")
        generate_person_name_statistics(output_stream)

    output_stream.write("\n")
    if output_stream != sys.stdout:
        output_stream.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())

#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-
# vim: encoding=iso-8859-1:fileencoding=iso-8859-1
# vim: ts=4:sw=4:expandtab
# 
# Copyright 2012 University of Oslo, Norway
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

import sys
import getopt

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules.Email import EmailTarget


def usage():
    """Prints a usage string for the script."""

    print """Usage:
    %s [Options]

    Generate a colon-separated file with employee ids and employee names.

    Options:
    -o, --output <file>            The file to print the report to. Defaults to 
                                   stdout.
    """ % sys.argv[0]


def get_employees_with_enr(logger):
    """Fetches a list of employees with employee number.
    
    @type  logger:  CerebrumLogger
    @param logger:  Logger to use.

    @return a list of dictionary objects with the keys
                         'entity_id' -> <int> Entity id of the person
                         'employee_id' -> <string> Employee id
                         'name' -> <string> Full name of the employee
    """

    # Database-setup
    db = Factory.get('Database')()
    pe = Factory.get('Person')(db)
    co = Factory.get('Constants')(db)

    ext_ids = []
    employees = pe.list_external_ids(source_system=co.system_sap, 
                                     id_type=co.externalid_sap_ansattnr, 
                                     entity_type=co.entity_person)

    for employee in employees:
        pe.clear()
        
        try:
            pe.find(employee['entity_id'])
        except Errors.NotFoundError:
            logger.warn("Couldn't find person with entity id %d" % 
                        employee['entity_id'])
            continue

        name = pe.get_name(source_system=co.system_cached, variant=co.name_full)

        # Each entry in the result list is a dictionary:
        tmp = {
                 'entity_id':   employee['entity_id'],
                 'employee_id': employee['external_id'],
                 'name':        name
              }

        ext_ids.append(tmp)

    return ext_ids


def write_dump_file(output, employees):
    """Writes a list of employees to a file object

    
    @type  logger:     CerebrumLogger
    @param logger:     Logger to use.

    @type  output:     file
    @param output:     Output file handle to write to

    @type  employees:  list
    @param employees:  List of dictionaries, each dictionary should contain:
                         employee_id -> <string> Employee id
                         name -> <string> Full name of the employee
    """

    first = employees.pop(0)
    if first:
        output.write("%s:%s" % (first['employee_id'], first['name']))

    for employee in employees:
        output.write(":%s:%s" % (employee['employee_id'], employee['name']))



def main(argv=None):
    """Main runtime as a function, for invoking the script from other scripts /
    interactive python session.
    
    @param argv: Script args, see 'usage' for details. Defaults to 'sys.argv'
    @type  argv: List of string arguments.
    """

    # Get logger
    # FIXME: 
    # logger = Factory.get_logger('cronjob')
    logger = Factory.get_logger('console')

    # Default opts
    output = sys.stdout

    ## Parse args
    if not argv:
        argv = sys.argv

    try:
        opts, args = getopt.getopt(argv[1:], 
                                   "s:o:", 
                                   ["source_system=", "output="])
    except getopt.GetoptError, e:
        logger.error(e)
        usage()
        return 1

    for o, v in opts:
        if o in ('-o', '--output'):
            try:
                output = open(v, 'w')
            except IOError, e:
                logger.error(e)
                sys.exit(1)
        if o in ('-s', '--source_system'):
            pass


    # Generate selected report
    logger.info("Start dumping all employee id's")
    employees = get_employees_with_enr(logger)
    write_dump_file(output, employees)
    logger.info("Done dumping all employee id's")


    # Close output if we explicitly opened a file for writing
    if not output is sys.stdout:
        output.close()


# If started as a program
if __name__ == "__main__":
    sys.exit(main())


#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2006 University of Oslo, Norway
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
This script generates a list of persons with different names in
regards to 2 source systems (f.eks: SAP/FS, ...) given in argument
to the script.
"""


__doc__ = """
Usage:
       generate_different_names_sources.py [-f|--file [PATH/]FILENAME] -s|--sourcesystems ARG1,ARG2

                Where ARG1 and ARG2 each is one of the follwoing:
                system_sap
                system_fs
                system_manual
                system_migrate
                system_sats
                system_virthome
"""

import sys
import getopt

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
logger = Factory.get_logger("cronjob")


db = Factory.get("Database")()
person = Factory.get("Person")(db)
const = Factory.get("Constants")(db)


# Start generate_person_diff_names
def generate_person_diff_names(stream, fnr_src_sys):

    # Get the right id for for every source system ginve in argument.

    source_systems = [int(getattr(const, x))
                          for x in fnr_src_sys.split(",")]
    # Loop through all the person entities
    for p in person.list_persons():
        pid = p["person_id"]
       # Test if initialisation of person succeeds and person in question exists
        try:
            person.clear()
            person.find(pid)
        except Errors.NotFoundError:
               logger.warn("list_persons() reported a person, but person.find() "
                           "did not find it")
               continue
        # Select fnr objects from the list of candidates.
        fnrs = dict([(int(src), eid) for (junk, src, eid) in
               person.get_external_id(id_type=const.externalid_fodselsnr)])
        # TODO: check if fnr objects have identical numbers as well
        fnr = ""
        firstname1 = ""
        firstname2 = ""
        lastname1  = ""
        lastname2  = ""
        # Check if the person object in question has got both source systems
        if source_systems[0] in fnrs:
          if source_systems[1] in fnrs:
            # Check if there is a name entry for the first source system
            try:
                (person.get_name(source_systems[0],const.name_first))
                (person.get_name(source_systems[0],const.name_last))
            except Errors.NotFoundError:
                  continue
            else:
                 firstname1 = (person.get_name(source_systems[0],const.name_first))
                 lastname1 = (person.get_name(source_systems[0],const.name_last))
                 # Check if there is a name entry for the second source system
                 try:
                     (person.get_name(source_systems[1],const.name_first))
                     (person.get_name(source_systems[1],const.name_last))
                 except Errors.NotFoundError:
                       continue
                 else:
                      firstname2 = (person.get_name(source_systems[1],const.name_first))
                      lastname2 = (person.get_name(source_systems[1],const.name_last))
                      # Test if names are not identical and print
                      if (firstname1 != firstname2) or (lastname1 != lastname2):
                        fnr = fnrs[source_systems[0]]
                        stream.write(":".join((fnr,firstname1+" "+lastname1,
                                     firstname2+" "+lastname2)))
                        stream.write("\n")
# End generate_person_diff_names.


# Gives usage info or how to use the program and its options.
def usage(message=None):
   if message is not None:
     print >>sys.stderr, "\n%s" % message
   print >>sys.stderr, __doc__
# End usage


# Main processing hub for program.
def main(argv=None):
    argv = sys.argv
    try:
        opts, args = getopt.getopt(argv[1:],
                                   "f:s:",
                                   ["file=","sourcesystems="])
    except getopt.GetoptError, error:
          usage(message=error.msg)
          return 1
    output_stream = sys.stdout
    fnr_src_sys = None
    for opt, val in opts:
        if opt in ('-f', '--file',):
          output_stream = open(val, "w")
        elif opt in ('-s', '--sourcesystems',):
            try:
                a = val.split(",")
                if (len(a) != 2):
                  error = getopt.GetoptError
                  usage(message=error.msg)
                  return 1
                if ((a[0] and a[1]) not in ("system_sap","system_fs",
                                            "system_manual","system_migrate",
                                            "system_sats","system_virthome",)):
                  error = getopt.GetoptError
                  usage(message=error.msg)
                  return 1
            except getopt.GetoptError, error:
                  usage(message=error.msg)
                  return 1
            else:
                 generate_person_diff_names(output_stream, val)
        else:
              error=getopt.GetoptError
              usage(message=error.msg)
              return 1
    if output_stream not in (sys.stdout, sys.stderr):
      output_stream.close()
    return 0
# End main


if __name__ == "__main__":
    sys.exit(main())

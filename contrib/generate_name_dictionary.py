#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2007 University of Oslo, Norway
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
""" This file is part of the Cerebrum framework.

It generates a list of names used in the password checking algorithm. Roughly,
we want to prevent people from using their own names (or variations thereof)
for passwords. This has been known to happen.

The idea is to sort all names and write them to a file where bofhd would be
able to pick it up (cereconf.PASSWORD_DICTIONARIES).
"""
import getopt
import sys

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.utils.atomicfile import SimilarSizeWriter


logger = Factory.get_logger("cronjob")


def name_is_valid(name):
    """Check name's eligibility for the dictionary.

    We want to avoid names that are:

    * too short (< 3 characters)
    * digits only (people do use digits, and unfortunately some
      'person' names are with digits only)
    """

    return (len(name) >= 3 and
            bool([x for x in name if not x.isdigit()]))
# end name_is_valid



def generate_list():
    """Generate a list of all names for the dictionary."""

    db = Factory.get("Database")()
    c = Factory.get("Constants")(db)
    logger.debug("Generating list of names")
    result = set()
    
    #
    # First the humans
    person = Factory.get("Person")(db)
    for row in person.search_person_names(name_variant=(c.name_last,
                                                        c.name_first,)):
        name = row["name"]
        if name_is_valid(name):
            result.add(name)

    result.update(row["name"]
                  for row in
                  person.search_name_with_language(entity_type=c.entity_person,
                            name_variant=(c.personal_title,
                                          c.work_title))
                  if name_is_valid(row["name"]))
                                          
    logger.debug("Collected %d human names", len(result))

    #
    # Then the accounts
    account = Factory.get("Account")(db)
    for row in account.search(expire_start=None):
        name = row["name"]
        if name_is_valid(name):
            result.add(name)

    logger.debug("%d entries in total", len(result))
    return result
# end generate_list



def sort_list(names):
    """Return a sorted list of names."""
                                                   
    seq = list(names)
    seq.sort()
    return seq
# end sort_list



def output_file(sequence, f):
    
    for name in sequence:
        f.write(name)
        f.write("\n")
# end output_file
    


def main():
    opts, rest = getopt.getopt(sys.argv[1:], "o:", ("output=",))
    filename = None
    for option, value in opts:
        if option in ("-o", "--output"):
            filename = value

    f = SimilarSizeWriter(filename, "w")
    f.max_pct_change = 50
    output_file(sort_list(generate_list()), f)
    f.close()
# end main

    

if __name__ == "__main__":
    main()


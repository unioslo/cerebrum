#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 
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
This script export work phone statistics requested by SINT.

Specifically, for all employees from a suitable source system (LT or SAP),
extract the phone numbers and locations and output the latter two. Each person
creates one record in the output file.

Each records is formatted thus:

<list of phone numbers>@skoseq1;skoseq2;skoseq3

... where <list of phone numbers> is a list of phone numbers assigned to one
person, and skoseq1, skoseq2, skoseq3 are SKO sequences for that person's
workplaces. skoseq1 corresponds to hovedstilling/bistilling, skoseq2 to
gjest and skoseq3 to bilag. E.g.:

22222222,33333333@150000,150010;140000;

... means that the owner of 22222222 and 33333333 has hovedstilling/bistilling
at OUs 150000 and 150010 as well as gjest association with OU 140000 and no
bilag associations. All entries are optional (naturally, records with all
entries missing are not output).
"""

import getopt
import sys

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.modules.xmlutils.system2parser import system2parser
from Cerebrum.modules.xmlutils.xml2object import DataContact, DataOU
from Cerebrum.modules.xmlutils.xml2object import DataEmployment



def split_emps(emp_iter):
    """Partition all employments of a person into regular, gjest, bilag."""
    de = DataEmployment

    type2idx = { de.HOVEDSTILLING : 0, 
                 de.BISTILLING    : 0,
                 de.GJEST         : 1,
                 de.BILAG         : 2, }

    result = list((list(), list(), list()))
    for emp in emp_iter:
        if not emp.is_active():
            continue
        # fi

        # We may have other id kinds in the future. In that case, we skip
        # the record
        if not emp.place or emp.place[0] != DataOU.NO_SKO:
            continue
        # fi

        place = "%02d%02d%02d" % emp.place[1]
        result[type2idx[emp.kind]].append(place)
    # od

    return result
# end split_emps


def output_data(sysname, pfile):
    """Scan through pfile with a parser derived from sysname."""

    parser = system2parser(sysname)(pfile, logger, False)
    for person in parser.iter_person():
        phones = person.get_contact(DataContact.CONTACT_PHONE)
        if not phones:
            continue
        # fi

        vanlig, gjest, bilag = split_emps(person.iteremployment()) 
        if not (vanlig or gjest or bilag):
            continue
        # fi

        vanlig = ",".join(vanlig)
        gjest = ",".join(gjest)
        bilag = ",".join(bilag)

        phones.sort(lambda x, y: cmp(x.priority, y.priority))
        print "%s@%s;%s;%s" % (",".join([x.value for x in phones]),
                               vanlig, gjest, bilag)
    # od
# end output_data


def main():
    global logger

    logger = Factory.get_logger("console")
    try:
        opts, args = getopt.getopt(sys.argv[1:], "s:",
                                   ["source-spec=",])
    except getopt.GetoptError, val:
        print val
        usage(1)
    # yrt


    for option, value in opts:
        if option in ("-s", "--source-spec"):
            sysname, personfile = value.split(":")
            output_data(sysname, personfile)
        # fi
    # od
# end main





if __name__ == "__main__":
    main()
# fi

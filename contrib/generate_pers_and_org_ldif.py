#!/usr/bin/env python2.2

# Copyright 2002, 2003 University of Oslo, Norway
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

import time, re

import cerebrum_path
from Cerebrum import OU
from Cerebrum import Person
from Cerebrum import Errors
from Cerebrum.Utils import Factory

Cerebrum = Factory.get('Database')()
co = Factory.get('Constants')(Cerebrum)
ou_struct = {}

def vailidate_name(str):
    #str = str.encode("ascii")
    str = re.sub(r'[זרו]','0',str)
    str = re.sub(r',',' ', str)
    return str


def read_OU():
    ou = OU.OU(Cerebrum)
    
    def print_OU(id, par_ou):
        ou.clear()
        ou.find(id)
        str_ou = []
        if ou.acronym:
            str_ou = "ou=%s,%s" % (vailidate_name(ou.acronym),par_ou)
        else:
            str_ou = "ou=%s,%s" % (vailidate_name(ou.name),par_ou)
        print str_ou
        return str_ou

    
    def trav_list(par, list, par_ou):
        chi = []
        for c,p in list:
            if p == par:
                chi.append(c)
        for c in chi:
            ou_struct[str(c)] = par_ou
            str_ou = print_OU(c, par_ou)
            trav_list(c, list, str_ou)
    
    list = ou.get_structure_mappings(29)
    trav_list(None, list, "dc=uio,dc=no")


def read_people():
    pers = Person.Person(Cerebrum)

    list = pers.get_all_person_ids()

    for p in list:
        id = Cerebrum.pythonify_data(p['person_id'])
        pers.clear()
        pers.find(int(id))
        try:
            print pers.get_name(28, 11)
        except Errors.NotFoundError:
            print "Jalla"

def main():
    # read_OU()
    read_people()

if __name__ == '__main__':
    main()

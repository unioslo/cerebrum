#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2005 University of Oslo, Norway
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

import Spine

def mult(a, b):
    r=[]
    for i in a:
        for j in b:
            r.append(i+j)
    return r



name_m = ["ole", "jens", "gunnar", "frode", "jørgen", "kristian",
          "knut", "steinar", "stian", "carl", "thomas", "erik",
          "marius", "lars", "martin", "leiv", "arild", "johan",
          "sverre" ]
name_f  = ["lise", "mari", "gro", "anne", "kristin", "jenny", "hanne",
        "ida", "marit", "maria", "siv", "silje", "tine", "tina",
        "idunn", "hege", "marte", "gry", "vigdis" ]
name_g  = ["myr", "teig", "skog", "fjell", "vass"]
name_s  = ["set", "stad", "sæter", "by", "voll", "eng", "sjø",
        "vatn", "å", "skog", "ås", "vik", "nes"]
name_p  = [ "lille", "stor", "lang", "kort", "brå" ]

name_1 = name_m + name_f
name_2 = mult(name_m, ["sen"]) * 4 + mult(name_m, ["son"]) \
         + mult(name_g, name_s) + mult(name_p, name_g) + mult(name_p, name_s)

import random
def get_name_first(g):
    if g:
        if g=="M":
            return name_m[random.randrange(len(name_m))].capitalize()
        else:
            return name_f[random.randrange(len(name_f))].capitalize()
    else:
        return name_1[random.randrange(len(name_1))].capitalize()

def get_name_last():
    return name_2[random.randrange(len(name_2))].capitalize()

t=Spine.connect().login("admin", "password").new_transaction()
comm=t.get_commands()
accountnamevaluedomain=t.get_value_domain("account_names")
sourcesystem=t.get_source_system('Manual') #it's not
lastnametype=t.get_name_type("LAST")
firstnametype=t.get_name_type("FIRST")
fullnametype=t.get_name_type("FULL")
bashshell=t.get_posix_shell("bash")
usersgroup=comm.get_group_by_name("users")
unionoperation=t.get_group_member_operation_type("union")

def create_random():
   gd=random.choice(("M","F"))
   p=comm.create_person(comm.get_date_now(), t.get_gender_type(gd))
   fn=get_name_first(gd)
   ln=get_name_last()
   p.add_name("%s %s" % (fn, ln), fullnametype, sourcesystem)
   p.add_name(fn, firstnametype, sourcesystem)
   p.add_name(ln, lastnametype, sourcesystem)
   names=comm.suggest_usernames(fn, ln)
   a=comm.create_account(names[0], p, comm.get_date(2010, 12, 31))
   a.promote_posix(usersgroup, bashshell)
   #a.promote_ad(loginscript, homedir)
   a.add_spread(t.get_spread("NIS_user@uio"))
   a.add_spread(t.get_spread("AD_account"))
   g=comm.create_group(names[0])
   g.promote_posix()
   #g.promote_ad()
   g.add_member(a, unionoperation)

import time

def create_many(n):
    t=time.time()
    for i in range(n):
        create_random()
    dt=time.time()-t
    print "Created %d persons/users/groups in %f seconds %f/s\n" % (n, dt, n/dt)



if __name__=="__main__":
    create_many(100)
    t.commit()

# arch-tag: c05b814d-9d58-4b63-b467-25f3bb4b4307

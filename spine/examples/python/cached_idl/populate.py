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

import sys
import ConfigParser
try:
    import SpineClient
except ImportError:
    print "Please make sure SpineClient is in your PYTHONPATH."
    sys.exit(1)

conf = ConfigParser.ConfigParser()
conf.read('client.conf')

username = conf.get('login', 'username')
password = conf.get('login', 'password')


def mult(a, b):
    r=[]
    for i in a:
        for j in b:
            r.append(i+j)
    return r



name_m = ["ole", "jens", "gunnar", "frode", "jørgen", "kristian",
          "knut", "steinar", "stian", "carl", "thomas", "erik",
          "marius", "lars", "martin", "leiv", "arild", "johan",
          "sverre", "alf", "børge", "bjørn", "ove" ]
name_f  = ["lise", "mari", "gro", "anne", "kristin", "jenny", "hanne",
        "ida", "marit", "maria", "siv", "silje", "tine", "tina",
        "idunn", "hege", "marte", "gry", "vigdis", "kari", "eli" ]
name_g  = ["myr", "teig", "skog", "fjell", "vass"]
name_s  = ["set", "stad", "sæter", "by", "voll", "eng", "sjø",
        "vatn", "å", "skog", "ås", "vik", "nes"]
name_p  = [ "lille", "stor", "lang", "kort", "brå" ]

#name_1 = name_m + name_f
name_2 = mult(name_m, ["sen"]) * 4 + mult(name_m, ["son"]) \
         + mult(name_g, name_s) + mult(name_p, name_g) + mult(name_p, name_s)

import random
def get_name_first(g=None):
    if g:
        if g=="M":
            name_1=name_m
        else:
            name_1=name_f
    else:
        name_1=random.choice([name_m, name_f])
    if random.random() < 0.1:
        return (random.choice(name_1).capitalize() + "-"
                + random.choice(name_1).capitalize())
    else:
        return random.choice(name_1).capitalize()

def get_name_last():
    return random.choice(name_2).capitalize()

t=SpineClient.SpineClient(config=conf).connect().login(username, password).new_transaction()
comm=t.get_commands()
accountnamevaluedomain=t.get_value_domain("account_names")
accounttarget=t.get_email_target_type("account")
sourcesystem=t.get_source_system('Manual') #it's not
lastnametype=t.get_name_type("LAST")
firstnametype=t.get_name_type("FIRST")
fullnametype=t.get_name_type("FULL")
bashshell=t.get_posix_shell("bash")
#usersgroup=comm.get_group_by_name("bootstrap_group")
unionoperation=t.get_group_member_operation_type("union")
ansattspread=t.get_spread("user@ansatt")
adspread=t.get_spread("user@ntnu_ad")
emaildomain=comm.get_email_domain_by_name("ntnu.no")


def get_host(t, name):
    s=t.get_host_searcher()
    s.set_name(name)
    return s.search()[0]

def get_disk(t, host, path):
    s=t.get_disk_searcher()
    s.set_host(host)
    s.set_path(path)
    return s.search()[0]

import string
def create_disks():
   disks=[]
   for c in string.ascii_lowercase[:6]:
	hostname="host%s" % c
	diskpath="/home/disk%s" % c
        try:
            h=get_host(t, hostname)
        except:
            h=comm.create_host(hostname, "Home server %s" % c.upper())
        try:
            d=get_disk(t, h, diskpath)
        except:
            d=comm.create_disk(h, diskpath, "Home disk %s" % c.upper())
        disks.append(d)
   return disks

disks=[]

def create_random():
   gd=random.choice(("M","F"))
   fn=get_name_first(gd)
   ln=get_name_last()
   name="%s %s" % (fn, ln)
   print 'Creating %s' % name
   p=comm.create_person(comm.get_date_now(), t.get_gender_type(gd), fn, ln, sourcesystem)
   #p.add_name(fn, firstnametype, sourcesystem)
   #p.add_name(ln, lastnametype, sourcesystem)
   names=comm.suggest_usernames(fn, ln)
   a=comm.create_account(names[0], p, comm.get_date(2010, 12, 31))
   #a.promote_ad(loginscript, homedir)
   a.add_spread(ansattspread)
   a.add_spread(adspread)
   # Prefix group names with "g"
   g=comm.create_group("g_" + names[0])
   g.promote_posix()
   #g.promote_ad()
   g.add_member(a, unionoperation)
   a.promote_posix(comm.get_free_uid(), g, bashshell)
   #a.set_homedir(ansattspread, "/home/%s" % names[0], None)
   a.set_homedir(ansattspread, "", random.choice(disks))
   et = comm.create_email_target(accounttarget)
   et.set_entity(a)
   try:
      addr = comm.create_email_address(("%s.%s" % (fn, ln)).lower(), emaildomain, et)
      et.set_primary_address(addr)
   except:
      pass

import time

def create_many(n):
    t=time.time()
    for i in range(n):
        create_random()
    dt=time.time()-t
    print "Created %d persons/users/groups in %f seconds %f/s\n" % (n, dt, n/dt)



if __name__=="__main__":
    disks=create_disks()
    create_many(100)
    t.commit()

# arch-tag: c05b814d-9d58-4b63-b467-25f3bb4b4307

#!/usr/bin/env python2.2
#
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

import sys
import time
import re

# TODO: Should probably avoid "import *" here.
from socket import *

import cereconf
from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import ADObject
from Cerebrum import OU
from Cerebrum import Person
from Cerebrum import Account
from Cerebrum import Group
from Cerebrum import Entity
#from Cerebrum import Entity.EntityName
from Cerebrum.modules import ADAccount


Cerebrum = Factory.get('Database')()
co = Factory.get('Constants')(Cerebrum)
ad_object = ADObject.ADObject(Cerebrum)
ad_account = ADAccount.ADAccount(Cerebrum)
entity = Entity.Entity(Cerebrum)
entityname = Entity.EntityName(Cerebrum)
ou = OU.OU(Cerebrum)
person = Person.Person(Cerebrum)
group = Group.Group(Cerebrum)
account = Account.Account(Cerebrum)

#Legge info inn i adtabellene.
#Først accounts.

user_namespace = int(co.account_namespace)

for row in ad_account.list_all_with_type(co.entity_account):
    ad_account.clear()
    id = row['entity_id']
        
#Stygt hack, men det virker.
    ad_account.entity_id = id
    try:
        name = ad_account.get_name(user_namespace)    
    except Errors.NotFoundError:
        print "object %s don't exists" % (id)
        continue

    try:
        ad_account.clear()
        ad_account.find(id)
    except Errors.NotFoundError:
        print "updating user: ",name
        ad_account.clear()
        #Stygt hack, men det virker.
        ad_account.entity_id = id
        ad_account.populate(co.entity_account,"7043","users\login.bat","\\\\carsten\\%s" % (name))
        ad_account.write_db()
        ad_account.commit()
    else:
        print "Already updated %s" % (id)
        
#Hente alle grupper

grp_namespace = int(co.group_namespace)

for row in ad_account.list_all_with_type(co.entity_group):
    ad_object.clear()
    id = row['entity_id']

#Stygt hack, men det virker.
    ad_object.entity_id = id
    try:
        name = ad_object.get_name(grp_namespace)    
    except Errors.NotFoundError:
        print "object %s don't exists" % (id)
        continue

    try:
        ad_object.clear()
        ad_object.find(id)
    except Errors.NotFoundError:
        print "updating group: ",name
        #Stygt hack, men det virker.
        ad_object.clear()
        ad_object.entity_id = id
        ad_object.populate(co.entity_group,"7043")
        ad_object.write_db()
        ad_object.commit()
    else:
        print "Already updated %s" % (id)



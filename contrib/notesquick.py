#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-
#
# Copyright 2003 University of Oslo, Norway
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
import re
import pickle
import string

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum import Entity
from Cerebrum.modules import CLHandler
import notesutils


db = Factory.get('Database')()
co = Factory.get('Constants')(db)
clco = Factory.get('CLConstants')(db)
person = Factory.get('Person')(db)
entity = Entity.Entity(db)
entityname = Entity.EntityName(db)
ou = Factory.get('OU')(db)
account = Factory.get('Account')(db)
cl = CLHandler.CLHandler(db)
logger = Factory.get_logger("cronjob")


def quick_sync():

#Change_log entries to react on:
#
#OK notes add spread
#OK notes del spread
#OK notes changed passwd
#OK notes add quarantine
#OK notes del quarantine
#
#Secondary:
#Account changed OU 
#Account connected same Person changed spread.

    answer=cl.get_events('notes',(clco.account_password,clco.spread_add,clco.spread_del,clco.quarantine_add,clco.quarantine_del,clco.quarantine_mod))
    for ans in answer:
	cl.confirm_event(ans)	
        chg_type = ans['change_type_id']
	try:
	    entity.clear()
    	    entity.find(ans['subject_entity'])
#            entity.has_spread(int(co.spread_uio_notes_account))
    	
	    if entity.has_spread(int(co.spread_uio_notes_account)):        
	        if chg_type == clco.account_password:
            	    change_params = pickle.loads(ans['change_params'])	
                    change_pw(ans['subject_entity'],change_params)
                elif chg_type == clco.spread_add:
                    change_params = pickle.loads(ans['change_params'])
                    if change_params['spread'] == int(co.spread_uio_notes_account):    
                        add_user(ans['subject_entity'])
                elif chg_type == clco.spread_del:
            	    change_params = pickle.loads(ans['change_params'])
		    if change_params['spread'] == int(co.spread_uio_notes_account):    
              	        delundel_user(ans['subject_entity'],'splatt')
                elif chg_type == clco.quarantine_add or chg_type == clco.quarantine_del or chg_type == clco.quarantine_mod:
		    change_quarantine(ans['subject_entity']) 
	except Errors.NotFoundError:
	    logger.warn("Could not find entity %s", ans['subject_entity'])

    cl.commit_confirmations()    

def change_quarantine(entity_id):
    if notesutils.chk_quarantine(entity_id):
	delundel_user(entity_id,'splatt')
    else:
	delundel_user(entity_id,'unsplat')

    	
def change_pw(account_id,pw_params):
    pw=pw_params['password']
    user = id_to_name(account_id)
    pw=string.replace(pw,'%','%25')
    pw=string.replace(pw,'&','%26')
    sock.send('CHPASS&ShortName&%s&pass&%s\n' % (user,pw))
    sock.read()


def add_user(account_id):		
    account_name =id_to_name(account_id)        
    pri_ou = notesutils.get_primary_ou( account_id, co.account_namespace)
    if not pri_ou:
	oustr="OU1&%s" % (cereconf.NOTES_DEFAULT_OU)
    else:
    	ou = notesutils.get_crbrm_ou(pri_ou)
    	if ou:
    	    oustr = ""
    	    i=0
	    ou.reverse()				
    	    for elem in ou:
	    	i = i+1
	    	oustr="%sOU%s&%s&" % (oustr,i,elem)
    	else:
	    oustr="OU1&%s" % (cereconf.NOTES_DEFAULT_OU)

    name=get_names(account_id)	 
    if name: 	
        sock.send('CREATEUSR&ShortName&%s&FirstName&%s&LastName&%s&%s\n' % (account_name,name[0],name[1],oustr))
        sock.read()        	
    if notesutils.chk_quarantine(account_id):
	delundel_user(account_id,'splatt')	

def delundel_user(account_id,status):
    account_name = id_to_name(account_id)
    name=get_names(account_id)
    if name:		 	
    	sock.send('DELUNDELUSR&ShortName&%s&FirstName&%s&LastName&%s&Status&%s\n' % (account_name,name[0],name[1],status))
    	sock.read()



def get_names(account_id):
    try:
        account.clear()
        account.find(account_id)
        person_id = account.owner_id
        person.clear()
        person.find(person_id)
    except Errors.NotFoundError:
        logger.warn("find on person or account failed: %s", account_id)
        return False

    firstname = lastname = None
    for ss in cereconf.NOTES_SOURCE_SEARCH_ORDER:
        try:
            firstname = person.get_name(int(getattr(co, ss)), int(co.name_first))
            lastname = person.get_name(int(getattr(co, ss)), int(co.name_last))
        except Errors.NotFoundError:
            pass
        if firstname and lastname:
            return (firstname, lastname)

    logger.warn("getting persons name failed, account.owner_id: %s", person_id)
    return False




def id_to_name(id):
    e_type = int(co.entity_account)
    namespace = int(co.account_namespace)
    entityname.clear()
    entityname.find(id)
    name = entityname.get_name(namespace)
    return name


if __name__ == '__main__':
    sock = notesutils.SocketCom()  
    quick_sync()
    sock.close()


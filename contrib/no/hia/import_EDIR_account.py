#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-
 
# Copyright 2004 University of Oslo, Norway
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
 


import re, string, os, getopt, sys
 
import cerebrum_path
import cereconf

from Cerebrum import Account
from Cerebrum import Entity
from Cerebrum import Person
#from Cerebrum import logger
from Cerebrum import Disk

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr

db = Factory.get('Database')()
co = Factory.get('Constants')(db)


def get_user_from_file(file_name):
    try:
	f = file(file_name,'r')
    except:
	print"Failed top open file"
	sys.exit(0)
    blokk = f.read()
    f.close()
    user_tab = {}
    for x in blokk.split('\n'):
	if x:
	    key,user,home = x.split(':')
	    value = "%s:%s" % (user,home)
	    if user_tab.has_key(key):
		user_tab[key].append(value)
	    else:
		user_tab[key] = [value,]
    return(user_tab)

def procces_users(user_tab):
    person = Factory.get('Person')(db)
    account = Factory.get('Account')(db)
    disk = Factory.get('Disk')(db)
    for k,v in user_tab.items():
	fodls_nr = str(k)
	person.clear()
	try:
	    person.find_by_external_id(co.externalid_fodselsnr,k)
	except Errors.NotFoundError:
	    #logger.xx("No person found with fodselnr: %s" % k
	    continue
	#Do check on entry with fodselnr and get person_id
	for n in user_tab[k]:
	    account.clear()
	    disk.clear()
	    name,nw_path =  n.lower().split(':')
	    path_list = [str(x) for x in nw_path.split('#')]
	    user_path =  path_list[(len(path_list) - 1)]
	    server_list = [re.sub('cn=','',y) for y in path_list[0].split(',')]
	    server,disk_name = server_list[0].split('_')
	    disk_path = "%s\%s\%s" % (server,disk_name,'bruker')
	    try:
		account.find_by_name(name)
	    except Errors.NotFoundError:
		account.populate(name,co.entity_person,person.entity_id,None,2,None)
	    	account.write_db()
	    if not account.has_spread(co.spread_hia_novell_user):
	        account.add_spread(co.spread_hia_novell_user)
	    try:
		disk.find_by_path(disk_path)
	    except Errors.NotFoundError:
		disk.entity_id = make_disk(server,disk_name,user_path,disk_path)
	    account.set_home(co.spread_hia_novell_user,disk.entity_id, \
				None,status=co.home_status_on_disk)	
	    	
	    
def make_disk(server,disk_name,user_path,disk_path):
    disk = Factory.get('Disk')(db)
    host = Disk.Host(db)			
    try:
	host.find_by_name(server)
    except Errors.NotFoundError:
	host.entity_id = make_host(server)
    disk.populate(host.entity_id,disk_path,'Novell disk area')
    disk.write_db()
    return(disk.entity_id)

def make_host(server):
    host = Disk.Host(db)
    host.populate(server,'Novell server at HIA') 
    host.write_db()
    return(host.entity_id)


def main():
    #global logger
    db.cl_init(change_program='import_NW_user')
    p = {}
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'n:d',
                                   ['novell-file=','dryrun'])
    except getopt.GetoptError:
        usage(1)
    dry_para = False
    for opt, val in opts:
        m_val = []
        if opt in ('--help',):
            usage()
        elif opt in ('-n', '--novell-file'):
            p['n_file'] = val
        elif opt in ('-d', '--dryrun'):
            dry_para = True
	    print "dryrun"
	else:
	    usage(0)
    if (p.get('n_file') != None):
	users = get_user_from_file(p.get('n_file'))	
	procces_users(users)
	if not dry_para: db.commit()
	else: db.rollback()
    else:
	usage(0)

def usage(exitcode=0):
    print """Usage: [options]
 
   Import from text-based dump from eDirectory.
   Format: "<fodsl.nr>:<account_name>:<account_homep_path>:<enable|disable>
 
    --novell_file=<path/file> | -n <path/file>
        Import file
 
    --dryrun | -d
	Do not import, but will give you error-messages
    """
    sys.exit(exitcode)



if __name__ == '__main__':
        main()


# -*- coding: iso-8859-1 -*-
                                                                                                                    
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

import re, string, os, getopt, sys, time
 
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


# fodel brukernavn context account_loock "forname etternavn" disk <student_nummer>

def get_user_from_file(file_name=None):
    if file_name:
	try:
	    f = file(file_name,'r')
	except:
	    print"Failed top open file"
	    sys.exit(0)
    else:
	f = file('/usit/parese/u1/larn/migrere/edir-alle-tab.txt','r')
    blokk = f.read()
    f.close()
    for x in blokk.split('\n'):
	# read lines 
	if x:
	    entr = x.split('\t')
	    # Tab split lines. Check if lines contains valid amount av fields
	    if entr[0] != '' and len(entr) >= 7:
		key = entr[0]
		value = ';'.join([x for x in entr[1:]])
		if user_tab.has_key(key):
		    user_tab[key].append(value)
		else:
		    user_tab[key] = [value,]
	    else:
		# Add not valid entries (without fdsl.nr.)
		account_tab[entr[1]] = ';'.join([x for x in entr[2:]])

def add_non_fdsnr_to_account(k):
    for n in user_tab[k]:
	entr = n.split(';')
	if not account_tab.has_key(entr[0]):
	    account_tab[entr[0]] = ';'.join([x for x in entr[1:]])
    

def process_users():
    person = Factory.get('Person')(db)
    for k,v in user_tab.items():
	fodls_nr = str(k)
	person.clear()
	try:
	    person.find_by_external_id(co.externalid_fodselsnr,k)
	    for n in user_tab[k]:
		process_account(n,personid=person.entity_id)
	except Errors.NotFoundError:
	    print "No person found with fodselnr: %s" % k
	    add_non_fdsnr_to_account(k)
    process_leftovers()

def process_account(n, personid=None):
    account = Factory.get('Account')(db)
    disk = Factory.get('Disk')(db)
    account.clear()
    disk.clear()
    entr = n.split(';')
    if (len(entr) >= 7):
	try:
	    serv_l = (entr[7].split('.'))[0].split('_')
	    disk_path = "%s/%s/%s" % (serv_l[0],serv_l[1],'bruker')
	    print disk_path
	except: print (entr[0],personid)
	try:
	    account.find_by_name(entr[0])
	    #logger.debug("Prossesing account %s" % entr[0])
	except Errors.NotFoundError:
	    account.populate(entr[0],co.entity_person,personid,None,2,None)
	    account.write_db()
	if not account.has_spread(co.spread_hia_novell_user):
	    account.add_spread(co.spread_hia_novell_user)
	    try:
		disk.find_by_path(disk_path)
	    except Errors.NotFoundError:
		disk.entity_id = make_disk(serv_l[0],disk_path)
	    account.set_home(co.spread_hia_novell_user,disk.entity_id, \
				None,status=co.home_status_on_disk)
	#else:
            #print "Novell spread already exists ! user: %s" % entr[0]
            #logger.info("Novell spread already exists ! user: %s" % entr[0])
	if entr[2] != 'no':
		if not account.get_entity_quarantine(type=co.quarantine_generell):
		    account.add_entity_quarantine(co.quarantine_generell, '2', \
                                description='From initial eDir import.',
				start=time.strftime("%Y-%m-%d", time.localtime()))
	if entr[3] != '':
	    try:
	    	exp_time = time.strptime(entr[3], '%d-%b-%Y %H:%M:%S')
		if time.mktime(exp_time) < time.time():
		    if not account.get_entity_quarantine(type=co.quarantine_generell):
			    account.add_entity_quarantine(co.quarantine_generell, 2,  
					description='From initial eDir import.', 
					start=time.strftime("%Y-%m-%d", time.localtime()))
		else:
		    account.add_entity_quarantine(co.quarantine_generell, 2,
						description='From initial eDir import.',
						start= time.strftime("%d-%m-%Y", exp_time))
	    except: 
		#logger.info("Could not resolve expire-time: %s" % entr[3])
		print "Could not resolve expire-time: %s" % entr[3]
    else:
        print "Record of account %s is not complete" % entr[0]
	#logger.info("Account %s doesent exists" % entr[0])
		
	    
def make_disk(server,disk_path):
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

def process_leftovers():
    account = Account.Account(db)
    for k,v in account_tab.items():
	account.clear()
	try:
	    account.find_by_name(k)
	    acc_info = ';'.join((k,v))
	    process_account(acc_info)	    
	except Errors.NotFoundError:
	    acc_info = ';'.join((k,v))
	    lucky = search_full_name(k,v)
	    if not lucky:
	        no_proc_file.write("%s;%s" % (k,v))


def search_full_name(k,v):
    person = Person.Person(db)
    try:
	pers.clear()
	entr = v.split(':')
	names = [string.capitalize(x) for x in entr[6].split(' ')]
	full_name = []
	for na in names:
	    if '-' in na:
		na = '-'.join([string.capitalize(x) for x in na.split('-')])
	    full_name.append(na)
	name = ' '.join((full_name))
	pers.clear()
	pos_pers = pers.find_persons_by_name(name)
	if pos_pers <> []:
	    for x in pos_pers:
		pers.clear()
		pers.find(int(x['person_id']))
		fdsl = pers.get_external_id(id_type=co.externalid_fodselsnr)
		name_hit_file.write("Account:%s Person: %s fdsl.nr: %s " % (k,name,fdsl[0]['external_id']))
		n = ':'.join((k,v))
		prossess_account(n, personid=fdsl[0]['person_id'])
		return(True)
	else:
	    return(False)
    except: return(False)
   
    

def main():
    global user_tab, account_tab, name_hit_file, no_proc_file
    name_hit_file = file('/tmp/name_hit_file.txt','w')
    no_proc_file = file('/tmp/no_proc_file.txt','w')
    user_tab = {}
    account_tab = {}
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
	get_user_from_file(p.get('n_file'))	
	procces_users()
	if not dry_para: db.commit()
	else: db.rollback()
    else:
	get_user_from_file()
	process_users()
    name_hit_file.close()
    no_proc_file.close()	
	

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


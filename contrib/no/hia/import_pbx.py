#!/usr/bin/env python
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
                                                                                                                                                      
"""
Import from a pbx in ldif-format. Options 'optimize' only updates 
necessary changes and do not create changelog of all entries.

> python import_pbx.py [-r] [-o] -l <file>

'-l' or '--ldif_file=' 	: full path to ldif-file 
'-r' or '--dryrun' 	: do not commit to base
'-o' or '--optimize'	: only updates changes, less entries in changelog

"""

import cerebrum_path
import cereconf
import getopt, locale, sys
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import LDIFutils
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
person = Factory.get('Person')(db)
logger = Factory.get_logger("cronjob")
db.cl_init(change_program='import_pbx')

db_list = {}
optimal = False 

def get_db_entr():
    for row in person.list_contact_info(source_system = \
					co.AuthoritativeSystem('PBX')):
	db_key,cont_type = int(row.entity_id),int(row.contact_type)
	db_value = row['contact_value']
	if not db_list.has_key(db_key):
	    db_list[db_key] = {}
	if not db_list[db_key].has_key(cont_type):
	    db_list[db_key][cont_type] = [db_value,]
	else:
	    db_list[db_key][cont_type].append(db_value)
	    db_list[db_key][cont_type].sort()
 
		
def get_ldif_info(ldif_file):
    fax, fax_num = int(co.contact_fax),'facsimiletelephonenumber'
    phone, ph_num = int(co.contact_phone),'internationalisdnnumber'
    acc = Factory.get('Account')(db)
    con_info = {}
    lt = LDIFutils.ldif_parser(ldif_file)
    for val in lt.parse().values():
	if val.has_key('uid'): 
	    acc.clear()
	    try:
		uname = val['uid'][0].split('@')[0]
		if '/' in uname:
		    uname = uname.split('/')[0]
		acc.find_by_name(uname)
		pers_id = acc.owner_id
	    except Errors.NotFoundError:
		logger.debug("Could not find person: %s" % uname) 
		continue
	    if not con_info.has_key(pers_id):
		con_info[pers_id] = {}
	    if val.has_key(ph_num):
		con_info[pers_id][phone] = val[ph_num]
		con_info[pers_id][phone].sort()
	    if val.has_key(fax_num):
		con_info[pers_id][fax] = val[fax_num]
		con_info[pers_id][fax].sort()
    return(con_info)

def sync_contact_info(cont_info):
    for pers_id,val in cont_info.iteritems():
	person.clear()
	try:
	    person.find(pers_id)
	except Errors.NotFoundError:
	    logger.info("Person not found. owner_id:%d" % pers_id)
	    continue
	if optimal:
	    do_update = False
	    for attr, info_l in val.items():
		try:
		    if info_l != db_list[pers_id][attr]:
			do_update = True
		except KeyError:
		    do_update = True
	if optimal and not do_update:
	    continue
	for attr, info_l in val.items():
	    pref = 1
	    for inf in info_l:
		person.populate_contact_info(co.AuthoritativeSystem('PBX'),
						type = attr,
						value = inf,
						contact_pref=pref)
		logger.debug("Person(%s) contact info updated" % pers_id)
	 	pref += 1
	person.write_db()

def usage(exit_code=0):
    if exit_code:
        print >>sys.stderr, exit_code
    print >>sys.stderr, __doc__
    sys.exit(bool(exit_code))


	

def main():
    global db_list, optimal
    locale.setlocale(locale.LC_CTYPE, ('en_US', 'iso88591'))
    try:
	opts, args = getopt.getopt(sys.argv[1:],
				'l:or', ['ldif-file=','optimize','dryrun'])
    except getopt.GetoptError, e:
	usage(str(e))
    l_file = None
    dryrun = False

    for opt, val in opts:
	if opt in ('-l', '--ldif-file'):
	    l_file = val
	if opt in ('-o', '--optimize'):
	    optimal = True
	elif opt in ('-r', '--dryrun'):
	    dryrun = True	
    try:
	f = open(l_file,'r')
    except IOError, e :
	usage(str(e))
    cont_info = get_ldif_info(f)
    f.close()
    if optimal:
	get_db_entr()
    sync_contact_info(cont_info)
    if dryrun:
	db.rollback()
    else:
	db.commit()



if __name__ == '__main__':
    main()


#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# Copyright 2003-2010 University of Oslo, Norway
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
Import from a pbx in ldif-format. 

> python import_pbx.py [-r] [-o] -l <file>

'-l' or '--ldif_file=' 	: full path to ldif-file 
'-r' or '--dryrun' 	: do not commit to base

"""
import re
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

def get_db_entr():
    for row in person.list_contact_info(source_system = \
					co.AuthoritativeSystem('PBX')):
	db_key,cont_type = int(row['entity_id']),int(row['contact_type'])
	db_value = row['contact_value']
	if not db_list.has_key(db_key):
	    db_list[db_key] = {}
	if not db_list[db_key].has_key(cont_type):
	    db_list[db_key][cont_type] = [db_value,]
	else:
	    db_list[db_key][cont_type].append(db_value)
	    db_list[db_key][cont_type].sort()
 
		
def get_ldif_info(ldif_file):
    fax, fax_num = co.contact_fax,'facsimiletelephonenumber'
    phone, ph_num = co.contact_phone,'internationalisdnnumber'
    mobile, mob_num = int(co.contact_mobile_phone),'mobile'
    acc = Factory.get('Account')(db)
    con_info = {}
    lt = LDIFutils.ldif_parser(ldif_file)
    r = re.compile("^(\w+)@[uh]ia\.no(\/(\w+))?")
    for val in lt.parse().values():
        if not val.has_key('uid'):
            continue
        # check for syntax in 'uid'
        m = r.match(val['uid'][0])
        if not m:
            continue
        # Iff '/x' the 'x' has to be a digit
        if m.group(2) and not m.group(3).isdigit():
            continue
        uname = m.group(1)
        acc.clear()
        try:
            acc.find_by_name(uname)
            if not acc.owner_type == int(co.entity_person):
                logger.debug("Owner (%d) for '%s' is not a person" % 
                             (acc.owner_id,uname))
                continue
            pers_id = acc.owner_id
        except Errors.NotFoundError:
            logger.debug("Could not find account: %s" % uname) 
            continue
        if not con_info.has_key(pers_id):
            con_info[pers_id] = {}
        if val.has_key(ph_num):
            con_info[pers_id].setdefault(phone,[]).append(val[ph_num][0])
        if val.has_key(fax_num):
            con_info[pers_id][fax] = val[fax_num]
            con_info[pers_id][fax].sort()
        if val.has_key(mob_num):
            con_info[pers_id][mobile] = val[mob_num]
            con_info[pers_id][mobile].sort()
    return(con_info)

def sync_contact_info(cont_info):
    for pers_id,val in cont_info.iteritems():
	person.clear()
	try:
	    person.find(pers_id)
	except Errors.NotFoundError:
	    logger.debug("Person not found. owner_id:%d" % pers_id)
	    continue
        do_update = False
        for attr, info_l in val.items():
            try:
                if info_l != db_list[pers_id][attr]:
                    do_update = True
            except KeyError:
                do_update = True
	if not do_update:
	    continue
	for attr, info_l in val.items():
	    pref = 1
	    for inf in info_l:
		person.populate_contact_info(co.AuthoritativeSystem('PBX'),
                                             type = attr,
                                             value = inf,
                                             contact_pref=pref)
		logger.info("Person(%s) contact info updated: %s %s" % \
                             (pers_id, attr, inf))
	 	pref += 1
	person.write_db()
    # Clean up after update of valid data
    for pers_id, types in db_list.iteritems():
        for c_type in types:
            if cont_info.has_key(pers_id) and cont_info[pers_id].has_key(c_type):
                continue
            person.clear()
            person.find(pers_id)
            person.delete_contact_info(co.AuthoritativeSystem('PBX'), c_type)
            logger.info("Person(%s) contact info deleted: %s" % (pers_id, c_type)) 

def usage(exit_code=0):
    if exit_code:
        print >>sys.stderr, exit_code
    print >>sys.stderr, __doc__
    sys.exit(bool(exit_code))


	

def main():
    global db_list
    locale.setlocale(locale.LC_CTYPE, ('en_US', 'iso88591'))
    try:
	opts, args = getopt.getopt(sys.argv[1:],
                                   'l:r', ['ldif-file=','dryrun'])
    except getopt.GetoptError, e:
	usage(str(e))
    l_file = None
    dryrun = False

    for opt, val in opts:
	if opt in ('-l', '--ldif-file'):
	    l_file = val
	elif opt in ('-r', '--dryrun'):
	    dryrun = True	
    try:
	f = open(l_file,'r')
    except IOError, e :
	usage(str(e))
    cont_info = get_ldif_info(f)
    f.close()
    
    get_db_entr()
    sync_contact_info(cont_info)
    if dryrun:
	db.rollback()
    else:
	db.commit()



if __name__ == '__main__':
    main()


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
 


import sys, re, locale, os
import xml.sax

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.hia import access_FS #Not sure yet
from Cerebrum import Database
from Cerebrum import Person
from Cerebrum import Group
from Cerebrum.modules.no.Stedkode import Stedkode 
from Cerebrum.modules.no.hia import fronter_lib

db = const = logger = None
acc2names = {}
ent2uname = {}
global db, const, logger, acc2name, person
db = Factory.get("Database")()
person = Factory.get('Person')(db)
const = Factory.get("Constants")(db)
logger = Factory.get_logger("console")



def load_acc2name():
    logger.debug('Loading person/user-to-names table')
    front = fronter_lib.hiafronter(db)
    """	Followin field in fronter_lib.hiafronter.list_cf_persons         
	person_id, account_id, external_id, name, entity_name,
	fs_l_name, fs_f_name, local_part, domain """
    for pers in front.list_cf_persons():
	#logger.debug("Loading person: %s" % pers['name'])
	if pers['fs_l_name'] == None:
	    l_name,f_name = get_names(pers['person_id'])
	else:
	    l_name,f_name = pers['fs_l_name'],pers['fs_f_name']
	acc2names[pers['account_id']] = {'NAME': pers['entity_name'],
					'FN': pers['name'],
					'GIVEN': l_name, 
					'FAMILY': f_name,
					'EMAIL': '@'.join((pers['local_part'],pers['domain'])),
					'USERACCESS':  2,
					'PASSWORD': 5, 
					'EMAILCLIENT': 1}



def get_names(person_id):
    name_tmp = {}
    person.clear()
    person.entity_id = int(person_id)
    for names in person.get_all_names():
	if (int(names['source_system']) <> int(const.system_cached)):
	    sys_key = int(names['source_system'])
	    name_li = "%s:%s" % (names['name_variant'],names['name'])
	    if name_tmp.has_key(sys_key):
		name_tmp[sys_key].append(name_li)
	    else: 
		 name_tmp[sys_key] = [name_li,]
    last_n = first_n = None
    for a_sys in cereconf.SYSTEM_LOOKUP_ORDER:
	sys_key = int(getattr(const,a_sys))
	if name_tmp.has_key(sys_key):
	    for p_name in name_tmp[sys_key]:
		var_n,nam_n = p_name.split(':')
		if (int(var_n) == int(const.name_last)):
		    last_n = nam_n
		elif (int(var_n) == int(const.name_first)):
		    first_n = nam_n
		else: pass 
	    return(last_n,first_n)
	    break	    


def get_group():
    group = Factory.get('Group')(db)
    global und_grp, stu_grp
    und_grp = {}
    stu_grp = {}
    for x in group.search(filter_spread=const.spread_hia_fronter):
	if 'undenh' in [str(y) for y in  (x['name']).split(':')]:
	    name_l = [str(y) for y in  (x['name']).split(':')]
	    und_key = ':'.join(name_l[5:])
	    grp_name = name_l[7:8][0]
	    mem_l = []
	    group.clear()
	    group.entity_id = int(x['group_id'])
	    for grp in group.list_members(None, int(const.entity_group),
						get_entity_name=True)[0]:
		mem_l.append("%s:%s" % (int(grp[1]),([str(y) for y in \
						grp[2].split(':')][-1:][0])))
	    if len(mem_l) != 0:
		und_grp[und_key] = {'group_id': int(x['group_id']),
					'group_name': x['name'], 
					'title': sh2long[grp_name]['navn'],
					'members': mem_l}
	    else:
		und_grp[und_key] = {'group_id':int(x['group_id']),
					'group_name': grp_name}
	else:
	    stu_key = ':'.join([str(y) for y in  (x['name']).split(':')][5:])
            stu_grp[stu_key] = {int(x['group_id']): True}
            group.clear()
            group.entity_id = int(x['group_id'])
            for grp in group.list_members(None, int(const.entity_group),
                                                get_entity_name=True)[0]:
                stu_key = ':'.join([str(y) for y in  grp[2].split(':')][5:])
                stu_grp[stu_key] = {int(grp[1]): False}



def make_fak_dict(fak_dict):
    res1 = {}
    res2 = {}
    sted = Stedkode.Stedkode(db)
    for k in fak_dict.keys():
	sted.clear()
	try:
	    sted.find_stedkode(k,0,0,201) # Constant, senere
	    if sted.acronym:
		st_name = sted.acronym
	    else: st_name = sted.short_name
	    sted_k = "%02d0000" % k 
	    res2[int(k)] = {'title': st_name, 'group_name':('hia.no:fs:struktur:emner:2004:host:' + (str(sted_k))),
				'parent':'hia.no:fs:struktur:emner:2004:host','level': 1}
	    res1[int(k)] = {'title': st_name, 'group_name':('hia.no:fs:struktur:emner:2004:vaar:' + (str(sted_k))),
                                'parent':'hia.no:fs:struktur:emner:2004:vaar','level': 1}
	except Errors.NotFoundError: 
	    pass
    return(res1,res2)

#def check_adm_access():
#    global 
#    fdsl2prim = person.getdict_external_id2primary_account(const.externalid_fodselsnr,ent_id=True)
#    roles_xml_parser('/cerebrum/dumps/FS/roles.xml',process_role_callback)

#def process_role_callback(r_info):
#    fnr = "%06d%05d" % (int(r_info['fodselsdato']),int(r_info['personnr']))
#    print fnr
#    for k,v in r_info.items():
#	print k,v

def process_undenh(undenh):
    if not sh2long.has_key(str(undenh['emnekode']).lower()):
	sh2long[str(undenh['emnekode']).lower()] =  {'navn':undenh['emnenavn_bokmal'],
							'fak':undenh['faknr_kontroll']}
 
   
def get_faknr():
    fak_dict = {}
    for k,v in sh2long.items():
	if fak_dict.has_key(int(v['fak'])):
	    fak_dict[int(v['fak'])].append(k)
	else:
	    fak_dict[int(v['fak'])] = [k,]
    return(fak_dict)


class CFroleParser(xml.sax.ContentHandler):
   
    def __init__(self, filename, call_back_function):
        self.call_back_function = call_back_function
        xml.sax.parse(filename, self)
                                                                                                                                                    
    def startElement(self, name, attrs):
        if name == 'data':
            pass
        elif name == "role" :
            self.p_data = {}
            for k in attrs.keys():
                self.p_data[k] = attrs[k].encode('iso8859-1')
	    self.call_back_function(self.p_data)
        else:
            print "WARNING: unknown element: %s" % name
                                                                                                                                                    
    def endElement(self, name):
        if name == "data":
            self.call_back_function(self.p_data)
  

class CFundenhParser(xml.sax.ContentHandler):
                                                                                                                                                            
    def __init__(self, filename, call_back_function):
        self.call_back_function = call_back_function
        xml.sax.parse(filename, self)
                                                                                                                                                            
    def startElement(self, name, attrs):
        if name == 'undervenhet':
            pass
        elif name == "undenhet":
            self.p_data = {}
            for k in attrs.keys():
                self.p_data[k] = attrs[k].encode('iso8859-1')
	    self.call_back_function(self.p_data)
        else:
            print "WARNING: unknown element: %s" % name
                                                                                                                                                            
    def endElement(self, name):
        if name == "undervenhet":
            self.call_back_function(self.p_data)
                                                                                                                                                            


def main():
    # H&ndter upper- og lowercasing av strenger som inneholder norske
    # tegn.
    cf_dir = '/cerebrum/dumps/Fronter/'
    locale.setlocale(locale.LC_CTYPE, ('en_US', 'iso88591'))
 
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h:',
                                   ['host=', 'fs-db-user=', 'fs-db-service=',
                                    'debug-file=', 'debug-level='])
    except getopt.GetoptError:
        usage(1)
    debug_file = "%s/x-import.log" % cf_dir
    debug_level = 4
    for opt, val in opts:
        if opt in ('-h', '--host'):
            host = val
        elif opt == '--fs-db-user':
            fs_db_user = val
        elif opt == '--fs-db-service':
            fs_db_service = val
        elif opt == '--debug-file':
            debug_file  = val
        elif opt == '--debug-level':
            debug_level = val
                                                                                                                                                                                               
    if len(args) != 1:
        usage(1)
                                                                                                                                                                                               
    global xml1, fdsl2prim, sh2long
    top_dict = {}
    sh2long = {}
    fdsl2prim = person.getdict_external_id2primary_account(const.externalid_fodselsnr,ent_id=True)
    xml1 = fronter_lib.FronterXML('test.xml',cf_dir = cf_dir,debug_file = debug_file,
				debug_level = debug_level, fronter = None)
    load_acc2name()
    CFundenhParser('/cerebrum/dumps/FS/underv_enhet.xml',process_undenh)
    CFundenhParser('/cerebrum/dumps/FS/under_next_sem.xml',process_undenh)
    get_group()
    top_dict[0] = {'level': 0 , 'group_name':'hia.no:fs:top',
                'title':'HiA-Fronter','parent':'hia.no:fs:top'}
    top_dict[1] = {'level': 0 , 'group_name':'hia.no:fs:struktur:emner',
                'title':'Emner','parent':'hia.no:fs:top'}
    top_dict[2] = {'level': 0 , 'group_name':'hia.no:fs:struktur:emner:2004:vaar',
                'title':'Emner VAAR 2004','parent':'hia.no:fs:struktur:emner'}
    top_dict[3] = {'level': 0 , 'group_name':'hia.no:fs:struktur:emner:2004:host',
                'title':'Emner HOST 2004','parent':'hia.no:fs:struktur:emner'}
    fak_dict = get_faknr()
    fak_d1,fak_d2 = make_fak_dict(fak_dict)
    xml1.start_xml_head()
    #genere topp struktur 
    for k,v in top_dict.items():
	xml1.group_to_XML(v)
    for k,v in 
    for k,v in acc2names.items():
	xml1.user_to_XML(v)
    for k,v in und_grp.items():
	xml1.group_to_XML(v)
    xml1.end()
    


if __name__ == '__main__':
    main()


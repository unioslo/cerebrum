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

import time, re, string, sys, getopt
import cerebrum_path
import cereconf  
from Cerebrum import OU
from Cerebrum import Person
from Cerebrum import Errors
from Cerebrum import Account
from Cerebrum import Group
from Cerebrum import Disk
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import Stedkode
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup
from Cerebrum.Constants import _SpreadCode
#from Cerebrum.modules.no.uio import Constants

Cerebrum = Factory.get('Database')()
co = Factory.get('Constants')(Cerebrum)
ou_struct = {}
entity2uname = {}
affiliation_code = {}
alias_list = {}
org_root = None

def vailidate_name(str):
    #str = str.encode("ascii")
    #str = re.sub(rå]','0',str)
    str = re.sub(r',',' ', str)
    return str

def load_code_tables():
    person = Person.Person(Cerebrum)
    affili_codes = person.list_person_affiliation_codes()
    for aff in affili_codes:
        affiliation_code[int(Cerebrum.pythonify_data(aff['code']))] = Cerebrum.pythonify_data(aff['code_str'])
    

def init_ldap_dump(ou_org,filename=None):
    if filename:
	f = file(filename,'w')
    else:
	f = file(string.join((cereconf.LDAP_DUMP_DIR,cereconf.ORG_FILE),'/'), 'w')
    init_str = "dn: %s\n" % (cereconf.LDAP_BASE)    
    init_str += "objectClass: top\n"
    for oc in cereconf.BASE_OBJECTCLASS:
	init_str += "objectClass: %s\n" % oc
    for bc in cereconf.BASE_BUSINESSCATEGORY:
	init_str += "businessCategory: %s\n" % bc
    for dc in cereconf.BASE_ALTERNATIVE_DN:
	init_str += "dc: %s\n" % dc
    for des in cereconf.BASE_DESCRIPTION:
	init_str += "description: %s\n" % des
    ou = OU.OU(Cerebrum)
    ou.find(ou_org)
    ou_fax = None
    try:
	ou_faxnumber = ou.get_contact_info(None, co.contact_fax)
        if ou_faxnumber:
	    ou_fax = (Cerebrum.pythonify_data(ou_faxnumber[0]['contact_value']))
            init_str += "facsimileTlephoneNumber: %s\n" % ou_fax
    except:
	pass
    try:
	stedkode = Stedkode.Stedkode(Cerebrum)
	stedkode.find(ou_org)
	stedkodestr = string.join((string.zfill(str(stedkode.fakultet),2), string.zfill(str(stedkode.institutt),2), string.zfill(str(stedkode.avdeling),2)),'')
        init_str += "norInstitutionNumber: %s\n" % stedkodestr
    except:
        pass
    init_str += "l: %s\n" % cereconf.BASE_CITY
    for alt in cereconf.BASE_ALTERNATIVE_NAME:
	init_str += "o: %s\n" % alt
    try:
	post_addr = ou.get_entity_address(None, co.address_post)
	post_addr_str = "%s" % string.replace(string.rstrip(post_addr[0]['address_text']),"\n","$")
        post_string = "%s$ %s %s" % (post_addr_str,vailidate_name(post_addr[0]['postal_number']),vailidate_name(post_addr[0]['city']))
        init_str += "postalAddress: %s\n" % post_string
	street_addr = ou.get_entity_address(None,co.address_street)
        street_addr_str = "%s" % string.replace(string.rstrip(street_addr[0]['address_text']),"\n","$")
        street_string = "%s$ %s %s" %(street_addr_str, vailidate_name(street_addr[0]['postal_number']),vailidate_name(street_addr[0]['city']))
        init_str += "streetAddress: %s\n" % street_string
    except:
        pass
    ou_phone = None
    try:
	ou_phonenumber = ou.get_contact_info(None, co.contact_phone)
        if ou_phonenumber:
	    ou_phone = (Cerebrum.pythonify_data(ou_phonenumber[0]['contact_value']))
            init_str += "telephoneNumber: %s\n" % ou_phone
    except:
        pass
    try:
        init_str += "labeledURI: %s\n" % cereconf.BASE_URL
    except:
        pass
    f.write(init_str)
    f.write("\n")
    ou_struct[int(ou.ou_id)]= cereconf.LDAP_BASE,post_string,street_string,ou_phone,ou_fax
    for org in cereconf.ORG_GROUPS:
	org = string.upper(org)
	init_str = "dn: %s=%s,%s\n" % (cereconf.ORG_ATTR,getattr(cereconf,(string.join((org,'DN'),'_'))),cereconf.LDAP_BASE)
	init_str += "objectClass: top\n"
	for obj in cereconf.ORG_OBJECTCLASS:
	    init_str += "objectClass: %s\n" % obj
	for ous in getattr(cereconf,(string.join((org,'ALTERNATIVE_NAME'),'_'))):
	    init_str += "%s: %s\n" % (cereconf.ORG_ATTR,ous)
	init_str += "description: %s\n\n" % getattr(cereconf,(string.join((org,'DESCRIPTION'),'_'))) 
	f.write(init_str)
    f.close()	

def root_OU():
    ou = OU.OU(Cerebrum)
    root_id=ou.root()
    if len(root_id) > 1:
	text1 = "You have %d roots in your organization-tree. Cerebrum only support 1.\n" % (len(root_id))
        sys.stdout.write(text1)
    	for p in root_id:
            root_org = Cerebrum.pythonify_data(p['ou_id'])
	    ou.clear()
	    ou.find(root_org)
	    text2 = "Organization: %s   ou_id= %s \n" % (ou.sort_name, ou.ou_id)
	    sys.stdout.write(text2)
	text3 = "Fill in the right organization-root(ou_id) in cerebrum/design/ldapconf.py!\n"
	sys.stdout.write(text3)
	org_root = None
	return(org_root)
    else:    
	root_org = Cerebrum.pythonify_data(root_id[0]['ou_id'])	
	return(root_org)

def generate_org(ou_id,filename=None):
    ou = OU.OU(Cerebrum)
    ou_list = ou.get_structure_mappings(152)
    ou_string = "%s=%s,%s" % (cereconf.ORG_ATTR,cereconf.ORG_DN, cereconf.LDAP_BASE)
    trav_list(ou_id, ou_list, ou_string, filename)
    stedkode = Stedkode.Stedkode(Cerebrum)
    if (cereconf.PRINT_NONE_ROOT == 'Enable'):
	root_ids = ou.root()
	if len(root_ids) > 1:
	    for org in root_ids:
		non_org = org['ou_id']
		if non_org <> ou_id:
		    stedkode.clear()
		    stedkode.find(non_org)
		    if (stedkode.katalog_merke == 'T'):
			stedkodestr = string.join((string.zfill(str(stedkode.fakultet),2), string.zfill(str(stedkode.institutt),2), string.zfill(str(stedkode.avdeling),2)),'')
			par_ou = "%s=%s,%s" % (cereconf.ORG_ATTR,cereconf.NON_ROOT_ATTR,ou_string)
			str_ou = print_OU(non_org, par_ou, stedkodestr, filename)
    
def print_OU(id, par_ou, stedkodestr, filename=None):
    ou = OU.OU(Cerebrum)
    ou.clear()
    ou.find(id)
    str_ou = []
    ou_fax = None
    street_string = None
    post_string = None
    ou_phone = None
    if filename:
	f = file(filename, 'a')
    else:
	f = file(string.join((cereconf.LDAP_DUMP_DIR,cereconf.ORG_FILE),'/'), 'a')
    f.write("\n")
    if ou.acronym:
        str_ou = "%s=%s,%s" % (cereconf.ORG_ATTR,vailidate_name(ou.acronym),par_ou)
    else:
        str_ou = "%s=%s,%s" % (cereconf.ORG_ATTR,vailidate_name(ou.name),par_ou)
    ou_str = "dn: %s\n" % str_ou
    ou_str += "objectClass: top\n"
    for ss in cereconf.ORG_OBJECTCLASS:
        ou_str += "objectClass: %s\n" % ss
    try:
    	ou_faxnumber = ou.get_contact_info(None, co.contact_fax)
    	if ou_faxnumber:
	    ou_fax = "%s" % (Cerebrum.pythonify_data(ou_faxnumber[0]['contact_value']))
	    for x in ou_faxnumber:
	    	ou_str += "facsimileTelephoneNumber: %s\n" % (Cerebrum.pythonify_data(x['contact_value']))
    except:
	pass
    if stedkodestr:	
	ou_str += "norOrgUnitNumber: %s\n" % stedkodestr
    if ou.acronym:
	ou_str += "ou: %s\n" % ou.acronym
    ou_str += "ou: %s\n" % ou.short_name
    ou_str += "ou: %s\n" % ou.display_name
    ou_str += "cn: %s\n" % ou.sort_name
    try:
	for cc in cereconf.SYSTEM_LOOKUP_ORDER:
	    post_addr = ou.get_entity_address(getattr(co, cc), co.address_post)
    	    if post_addr:
		post_addr_str = "%s" % string.replace(string.rstrip(post_addr[0]['address_text']),"\n","$") 
		post_string = "%s$ %s %s" % (post_addr_str,vailidate_name(post_addr[0]['postal_number']),vailidate_name(post_addr[0]['city']))
		ou_str += "postalAddress: %s\n" % post_string
		break
    	for dd in cereconf.SYSTEM_LOOKUP_ORDER:
            street_addr = ou.get_entity_address(getattr(co, dd), co.address_street)
            if street_addr:
		street_addr_str = "%s" % string.replace(string.rstrip(street_addr[0]['address_text']),"\n","$")
		street_string = "%s$ %s %s" %(street_addr_str, vailidate_name(street_addr[0]['postal_number']),vailidate_name(street_addr[0]['city']))
		ou_str += "streetAddress: %s\n" % street_string
                break
   	ou_phnumber = (ou.get_contact_info(None, co.contact_phone))
    	if ou_phnumber:
	    for x in ou_phnumber:
		ou_phone = "%s" % (Cerebrum.pythonify_data(x['contact_value']))
		ou_str += "telephoneNumber: %s\n" % ou_phone
    except:
	pass
    ou_struct[int(id)]= str_ou,post_string,street_string,ou_phone,ou_fax
    f.write(ou_str)
    f.close()
    return str_ou

    
def trav_list(par, ou_list, par_ou,filename=None):
    stedkode = Stedkode.Stedkode(Cerebrum)
    for c,p in ou_list:
	if (p == par) and (c <> par):
	    stedkode.clear()
	    try:
		stedkode.find(c)
 	   	if stedkode.katalog_merke == 'T':
		    stedkodestr = string.join((string.zfill(str(stedkode.fakultet),2), string.zfill(str(stedkode.institutt),2), string.zfill(str(stedkode.avdeling),2)),'')
            	    str_ou = print_OU(c, par_ou, stedkodestr, filename)
            	    trav_list(c, ou_list, str_ou, filename)
    	    	else:
		    trav_list(c, ou_list, par_ou, filename)
	    except:
		ou_struct[str(c)] = par_ou
		str_ou = print_OU(c, par_ou, None, filename)
		trav_list(c, ou_list, str_ou, filename)

def generate_person(filename=None):
    person = Person.Person(Cerebrum)
    if filename:
	f = file(filename, 'a')
    else:
	f = file(string.join((cereconf.LDAP_DUMP_DIR,cereconf.PERSON_FILE),'/'), 'w')	
    f.write("\n")
    objclass_string = "objectClass: top\n"
    for objclass in cereconf.PERSON_OBJECTCLASS:
	objclass_string += "objectclass: %s\n" % objclass
    dn_attr = cereconf.PERSON_ATTR
    dn_base = "%s" % cereconf.LDAP_BASE
    dn_string = "%s=%s,%s" % (cereconf.ORG_ATTR,cereconf.PERSON_DN,dn_base) 
    for row in person.list_extended_person():
	id, birth_date,external_id,name,entity_name,phone,passwd,ou_id,email,domain,affili = row['person_id'], row['birth_date'],row['external_id'],row['name'],row['entity_name'],row['contact_value'],row['auth_data'],row['ou_id'],row['local_part'],row['domain'],row['affiliation']
	if external_id:
	    person.clear()
	    person.entity_id = id
	    pers_string = "dn: %s=%s,%s\n" % (dn_attr,entity_name,dn_string)
	    pers_string += "%s" % objclass_string
	    pers_string += "cn: %s\n" % name
	    if birth_date:
		pers_string += "birthDate: %s\n" % (time.strftime("%d%m%y",time.strptime(str(birth_date),"%Y-%m-%d %H:%M:%S.00")))
	    pers_string += "norSSN: %s\n" % external_id
	    pers_string += "eduPersonOrgDN: %s\n" % dn_base
	    prim_org = (ou_struct[int(ou_id)][0])
	    pers_string += "eduPersonPrimaryOrgUnitDN: %s\n" % prim_org
            p_affiliations = person.get_affiliations()
	    org_printed = str(' ')
	    for edu_org in p_affiliations:
		org = ou_struct[int(edu_org['ou_id'])][0]
		if (string.find(org_printed,org) == -1):
		    pers_string += "eduPersonOrgUnitDN: %s\n" % org
		    org_printed += org
	    pers_string += "eduPersonPrincipalName: %s@%s\n" % (entity_name, cereconf.BASE_DOMAIN)
	    for sys in cereconf.SYSTEM_LOOKUP_ORDER:
		given_name = None
		lastname = None
		try:
		    pers_string += "givenName: %s\n" % person.get_name(getattr(co,sys),co.name_first)
		    lastname = person.get_name(getattr(co,sys),co.name_last)
		    break
		except:
		    pass
		#if given_name:
		#    print "Givenname::: %s %s" % (person.get_name(getattr(co,sys),co.name_first),sys)
		#    pers_string += "\ngivenName: %s" % given_name
		#    break
	    if email and domain:
		pers_string += "mail: %s@%s\n" % (email,domain)
	    if lastname:
		pers_string += "sn: %s\n" % lastname
	    if (int(affili) == int(co.affiliation_ansatt)): 
		pers_string += "postalAddress: %s\n" % ou_struct[int(ou_id)][1]
		pers_string += "street: %s\n" % ou_struct[int(ou_id)][2]
		#pers_string += "title: "
		if phone:
		    pers_string += "telephoneNumber: %s\n" % phone
		else:
		    pers_string += "telephoneNumber: %s\n" % ou_struct[int(ou_id)][3]
		if ou_struct[int(ou_id)][4]:
		    pers_string += "facsimileTelephoneNumber: %s\n" % ou_struct[int(ou_id)][4]
	    for affi in p_affiliations:
		pers_string += "eduPersonAffiliation: %s\n" % string.lower(affiliation_code[int(affi['affiliation'])])
	    pers_string += "uid: %s\n" % entity_name
	    if passwd:
		pers_string += "userPassword: {crypt}%s\n" % passwd
	    else:
		pers_string += "userPassword: *\n"
	    alias_list[int(id)] = entity_name, prim_org, name, lastname
	    f.write("\n")
	    f.write(pers_string)
	else:
	    pass
    f.close()

def generate_alias(filename=None):
    person = Person.Person(Cerebrum)
    dn_string = "%s=%s,%s" % (cereconf.ORG_ATTR,cereconf.PERSON_DN,cereconf.LDAP_BASE)
    if filename:
	f = file(filename,'a')
    else:
	f = file(string.join((cereconf.LDAP_DUMP_DIR,cereconf.ALIAS_FILE),'/'), 'w')
    f.write("\n")
    obj_string = "\nobjectClass: top"
    for obj in cereconf.ALIAS_OBJECTCLASS:
        obj_string += "\nobjectClass: %s" % obj
    for alias in person.list_persons():
	#print "Person_id: %s" % alias
	person_id = int(alias['person_id'])
	if alias_list.has_key(person_id):
	    #print "has_key treff"
	    entity_name, prim_org, name, lastname = alias_list[person_id]
	    alias_str = "\ndn: uid=%s,%s" % (entity_name, prim_org)
	    alias_str += "%s" % obj_string
	    alias_str += "\nuid: %s" % entity_name
	    if name:
		alias_str += "\ncn: %s" % name
	    if lastname:
		alias_str += "\nsn: %s" % lastname
	    alias_str += "\naliasedObjectName: uid=%s,%s" % (entity_name,dn_string)
	    f.write("\n")
	    f.write(alias_str)
    f.close()

def generate_users(spread=None,filename=None):
    shells = {}	
    disks = {}
    posix_user = PosixUser.PosixUser(Cerebrum)
    posix_group = PosixGroup.PosixGroup(Cerebrum)
    disk = Disk.Disk(Cerebrum)
    for sh in posix_user.list_shells():
	shells[int(sh['code'])] = sh['shell']
    for hd in disk.list():
	disks[int(hd['disk_id'])] = hd['path']  
    posix_dn = ",%s=%s,%s" % (cereconf.ORG_ATTR,cereconf.USER_DN,cereconf.LDAP_BASE)
    posix_dn_string = "%s=" % cereconf.USER_ATTR
    obj_string = "objectClass: top\n"
    for obj in cereconf.USER_OBJECTCLASS:
	obj_string += "objectClass: %s\n" % obj
    if filename:
	f = file(filename, 'w')
    else:
	f = file(string.join((cereconf.LDAP_DUMP_DIR,cereconf.USER_FILE),'/'), 'w')
    if not spread: 
    	pos_user = posix_user.list_extended_posix_users(getattr(co,'auth_type_md5_crypt'))
    else:
	pos_user = posix_user.list_extended_posix_users(getattr(co,'auth_type_md5_crypt'),spread)
    f.write("\n")
    for row in pos_user:
	acc_id,uid,shell,gecos,uname,home,disk_id,passwd,gid, full_name = row['account_id'],row['posix_uid'],row['shell'],row['gecos'],row['entity_name'],row['home'],row['disk_id'],row['auth_data'],row['posix_gid'],row['name']
	entity2uname[int(acc_id)] = uname
	if not passwd:
	    passwd = '*'
	else:
	    passwd = "{crypt}%s" % passwd
	if not gecos:
	    gecos = posix_user._conv_name(full_name)
	if not home:
	    home = "%s/%s" % (disks[int(disk_id)],uname)
        shell = shells[int(shell)]
	posix_text = """
\ndn: %s%s%s
%scn: %s
uid: %s
uidNumber: %s
gidNumber: %s
homeDirectory: %s
userPassword: %s
loginShell: %s
gecos: %s""" % (posix_dn_string, uname, posix_dn, obj_string, gecos, uname,
	str(uid), str(gid),
	home, passwd, shell, gecos)
	f.write(posix_text)
    f.close()

def generate_posixgroup():
   for spread in cereconf.GROUP_SPREAD:
	generate_group(int(getattr(co,spread)))

def generate_group(spread=None, filename=None):
    posix_group = PosixGroup.PosixGroup(Cerebrum)
    if filename:
	f = file(filename, 'w')
    else:
	f = file(string.join((cereconf.LDAP_DUMP_DIR,("%s%s" % (spread,cereconf.GROUP_FILE))),'/'), 'w')
    f.write("\n")
    groups = {}
    dn_str = "%s=%s,%s" % (cereconf.ORG_ATTR,cereconf.GROUP_DN,cereconf.LDAP_BASE)
    obj_str = "objectClass: top\n"
    for obj in cereconf.GROUP_OBJECTCLASS:
	obj_str += "objectClass: %s\n" % obj
    for row in posix_group.list_all(spread):
	posix_group.clear()
	try:
	    posix_group.find(row.group_id)
	    gname = posix_group.group_name
	    pos_grp = "dn: %s=%s,%s\n" % (cereconf.GROUP_ATTR,gname,dn_str)
	    pos_grp += "%s" % obj_str
	    pos_grp += "cn: %s\n" % gname
	    pos_grp += "gidNumber: %s\n" % posix_group.posix_gid
	    if posix_group.description:
		pos_grp += "description: %s\n" % posix_group.description
	    for id in posix_group.get_members():
		uname_id = int(Cerebrum.pythonify_data(id))
		if entity2uname.has_key(uname_id):
		    pos_grp += "memberUid: %s\n" % entity2uname[uname_id]
		else:
 		    posix_group.clear()
		    posix_group.entity_id = uname_id
		    mem_name = posix_group.get_name(co.account_namespace)
		    entity2uname[int(uname_id)] = mem_name
		    pos_grp += "memberUid: %s\n" % mem_name
	    f.write("\n")
            f.write(pos_grp)
	except:
	    pass
    f.close()


def genenerate_netgroup(spread=None, filename=None):
    pos_netgrp = Group.Group(Cerebrum) 
    #posix_user = PosixUser.PosixUser(Cerebrum)
    if filename:
        f = file(filename, 'w')
    else:
        f = file(string.join((cereconf.LDAP_DUMP_DIR,cereconf.NETGROUP_FILE),'/'), 'w')
    if spread:
	spread = "%s" % spread
    else:
	spread = "%s" % cereconf.NETGROUP_SPREAD
    f.write("\n")
    dn_str = "%s=%s,%s" % (cereconf.ORG_ATTR,cereconf.NETGROUP_DN,cereconf.LDAP_BASE)
    obj_str = "objectClass: top\n"
    for obj in cereconf.NETGROUP_OBJECTCLASS:
        obj_str += "objectClass: %s\n" % obj
    for row in pos_netgrp.list_all(int(getattr(co,spread))):
        pos_netgrp.clear()
        try:
            pos_netgrp.find(row.group_id)
            netgrp_name = pos_netgrp.group_name
            netgrp_str = "dn: %s=%s,%s\n" % (cereconf.NETGROUP_ATTR,netgrp_name,dn_str)
            netgrp_str += "%s" % obj_str
            netgrp_str += "cn: %s\n" % netgrp_name
	    if not entity2uname.has_key(int(row.group_id)):
		entity2uname[int(row.group_id)] = netgrp_name
	    if pos_netgrp.description:
                 netgrp_str+= "description: %s\n" % pos_netgrp.description
	    members = []
	    hosts = []
	    groups = []
	    members = pos_netgrp.list_members(None,int(co.entity_account))[0]
#	    hosts = pos_netgrp.list_members(None,int(co.entity_host))[0]
	    groups = pos_netgrp.list_members(None,int(co.entity_group))[0]
	    for id in members:
                uname_id = int(id[1])
                if entity2uname.has_key(uname_id):
                    netgrp_str += "nisNetgroupTriple: (,%s,)\n" % entity2uname[uname_id]
                else:
                    pos_netgrp.clear()
                    pos_netgrp.entity_id = uname_id
                    netgrp_str += "nisNetgroupTriple: (,%s,)\n" % posix_group.get_name(co.account_namespace)
#	    for host in hosts:
#		host_id = int(host[1])
#		if entity2uname.has_key(host_id):
#		    netgrp_str += "nisNetgroupTriple: (%s,-,)\n" % % entity2uname[host_id]
#		else:
#		    pos_netgrp.clear()
#		    pos_netgrp.entity_id = host_id
#		    netgrp_str += "nisNetgroupTriple: (%s,-,)\n" % posix_group.get_name(co.host_namespace)
	    for group in groups:
		group_id = int(group[1])
		if entity2uname.has_key(group_id):
		    netgrp_str += "memberNisNetgroup: %s\n" % entity2uname[group_id]
		else:
		    pos_netgrp.clear()
		    pos_netgrp.find(group_id)
		    netgrp_str += "memberNisNetgroup: %s\n" % pos_netgrp.group_name
            f.write("\n")
            f.write(netgrp_str)
        except:
            pass
    f.close()

    

def main():
    global debug
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'dg:p:n:',
                                   ['debug', 'help', 'group=','org=','person=',
                                    'group_spread=','user_spread=', 'netgroup='])
    except getopt.GetoptError:
        usage(1)

    user_spread = group_spread = None

    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('-d', '--debug'):
            debug += 1
	elif opt in ('-o','--org'):
	    if (cereconf.ORG_ROOT_AUTO == 'Enable'):
		org_root = int(cereconf.ORG_ROOT)
	    else:
		org_root = root_OU()
	    if org_root:
		load_code_tables() #sjekk nærmere
		init_ldap_dump(org_root,val)
		generate_org(org_root,val)
		generate_person(val)
		generate_alias(val)
	elif opt in ('-p', '--person'):
            generate_person(val)
	elif opt in ('-u', '--user'):
            generate_users()
	elif opt in ('-g', '--group'):
	    load_entity2uname()
	    generate_group(group_spread, val)
	elif opt in ('-n', '--netgroup'):
	    load_entity2uname()
	    generate_netgroup(val, group_spread)
	elif opt in ('--user_spread',):
	    user_spread = map_spread(val)
	elif opt in ('--group_spread',):
	    group_spread = map_spread(val)
        else:
            usage()
    if len(opts) == 0:
        config()

def usage(exitcode=0):
    print """Usage: [options]
    --group_spread=value
      Filter by group_spread
    --user_spread=value
      Filter by user_spread
    --org=<outfile> 
      Write organization, person and alias to a LDIF-file
    --user=<outfile>
      Write users to a LDIF-file
    --group=<outfile>
      Write posix groups to a LDIF-file
    --netgroup outfile
      Write netgroup map to a LDIF-file

    Generates a NIS map of the requested type for the requested spreads."""
    sys.exit(exitcode)

def map_spread(id):
    try:
        return int(_SpreadCode(id))
    except Errors.NotFoundError:
        print "Error mapping %s" % id
        raise

def config():
	if (cereconf.ORG_ROOT_AUTO == 'Enable'):
	    org_root = int(cereconf.ORG_ROOT)
	else:
	    org_root = root_OU()
	if org_root: 
	    load_code_tables() #sjekk nærmere
	    init_ldap_dump(org_root)
	    generate_org(org_root)
	    if (cereconf.PERSON == 'Enable'):
    		print "Person generate" 
		generate_person()
	    if (cereconf.ALIAS == 'Enable'):
		print "Alias generate"
		generate_alias()
	    if (cereconf.USER == 'Enable'):
		print "User generate"
		generate_users()
	    if (cereconf.GROUP == 'Enable'):
		print "Group generate"
		generate_posixgroup()
	    if (cereconf.NETGROUP == 'Enable'):
		print "Netgroup generate"
		genenerate_netgroup()
	else:
	    pass
	
if __name__ == '__main__':
    	main()

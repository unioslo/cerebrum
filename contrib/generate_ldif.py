#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

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

import time
import re
import string
import sys
import getopt
import base64
import os

import cerebrum_path
import cereconf  
from Cerebrum import Errors
from Cerebrum import Entity
from Cerebrum.Utils import Factory, latin1_to_iso646_60, SimilarSizeWriter
from Cerebrum.modules.no import Stedkode
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup
from Cerebrum import QuarantineHandler
from Cerebrum.Constants import _SpreadCode

Cerebrum = Factory.get('Database')()
co = Factory.get('Constants')(Cerebrum)
ou_struct = {}
entity2uname = {}
affiliation_code = {}
alias_list = {}
org_root = None
global dn_dict
dn_dict = {}

normalize_trans = string.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ\t\n\r\f\v",
    "abcdefghijklmnopqrstuvwxyz     ")


def load_code_tables():
    global ph_tab, fax_tab
    ph_tab = {}
    fax_tab = {}
    person = Factory.get('Person')(Cerebrum)
    affili_codes = person.list_person_affiliation_codes()
    for aff in affili_codes:
        affiliation_code[int(Cerebrum.pythonify_data(aff['code']))] = \
				Cerebrum.pythonify_data(aff['code_str'])
    ph_tab = get_contacts(source_system=int(co.system_lt),\
                                contact_type=int(co.contact_phone))
    fax_tab = get_contacts(source_system=int(co.system_lt),\
                                contact_type=int(co.contact_fax))
    

def make_address(sep, p_o_box, address_text, postal_number, city, country):
    if (p_o_box and int(postal_number or 0) / 100 == 3):
        address_text = "Pb. %s - Blindern" % p_o_box
    else:
        address_text = some2utf(address_text or "").strip()
    post_nr_city = None
    if city or (postal_number and country):
        post_nr_city = " ".join(filter(None, (postal_number,
                                              some2utf(city or "").strip())))
    if country:
        country = some2utf(country)
    return sep.join(filter(None, (address_text,
                                  post_nr_city,
                                  country))).replace("\n", sep)

def init_ldap_dump(ou_org,filename=None):
    if filename:
	f = file(filename,'w')
    else:
	f = file(string.join((cereconf.LDAP_DUMP_DIR,cereconf.LDAP_ORG_FILE),'/'), 'w')
    print "Generate organization"
    init_str = "dn: %s\n" % (cereconf.LDAP_BASE)    
    init_str += "objectClass: top\n"
    for oc in cereconf.LDAP_BASE_OBJECTCLASS:
	init_str += "objectClass: %s\n" % oc
    for bc in cereconf.LDAP_BASE_BUSINESSCATEGORY:
	init_str += "businessCategory: %s\n" % bc
    for dc in cereconf.LDAP_BASE_ALTERNATIVE_DN:
	init_str += "dc: %s\n" % dc
    for des in cereconf.LDAP_BASE_DESCRIPTION:
	init_str += "description: %s\n" % des
    ou = Factory.get('OU')(Cerebrum)
    ou.find(ou_org)
    if fax_tab.has_key(int(ou_org)):
	for fax in fax_tab[int(ou_org)]:
	    init_str += "facsimileTelephoneNumber: %s\n" % fax
    try:
	stedkode = Stedkode.Stedkode(Cerebrum)
	stedkode.find(ou_org)
    except:
        pass
    else:
	stedkodestr = "%02d%02d%02d" % (stedkode.fakultet,
                                        stedkode.institutt,
                                        stedkode.avdeling)
        init_str += "norInstitutionNumber: %s\n" % stedkodestr
    init_str += "l: %s\n" % cereconf.LDAP_BASE_CITY
    for alt in cereconf.LDAP_BASE_ALTERNATIVE_NAME:
	init_str += "o: %s\n" % alt
    post_string = street_string = None
    try:
	post_addr = ou.get_entity_address(None, co.address_post)[0]
    except:
        pass
    else:
        post_string = make_address("$",
                                   post_addr['p_o_box'],
                                   post_addr['address_text'],
                                   post_addr['postal_number'],
                                   post_addr['city'],
                                   post_addr['country'])
        if post_string:
            init_str += "postalAddress: %s\n" % post_string
    try:
	street_addr = ou.get_entity_address(None,co.address_street)[0]
    except:
        pass
    else:
        street_string = make_address(", ",
                                     None,
                                     street_addr['address_text'],
                                     street_addr['postal_number'],
                                     street_addr['city'],
                                     street_addr['country'])
        if street_string:
            init_str += "street: %s\n" % street_string
    if ph_tab.has_key(int(ou_org)):
        for phone in ph_tab[int(ou_org)]:
            init_str += "telephoneNumber: %s\n" % phone

    try:
        init_str += "labeledURI: %s\n" % cereconf.LDAP_BASE_URL
    except:
        pass
    f.write(init_str)
    f.write("\n")
    try:
    	ou_struct[int(ou.ou_id)] = (cereconf.LDAP_BASE,
                                    post_string, street_string,
                                    ou_phones, ou_faxs)
    except: pass
    for org in cereconf.LDAP_ORG_GROUPS:
	org = string.upper(org)
	org_name = str(getattr(cereconf,(string.join((string.join(('LDAP',org),'_'),'DN'),'_'))))
	init_str = "dn: %s=%s,%s\n" % (cereconf.LDAP_ORG_ATTR,org_name,cereconf.LDAP_BASE)
	init_str += "objectClass: top\n"
	for obj in cereconf.LDAP_ORG_OBJECTCLASS:
	    init_str += "objectClass: %s\n" % obj
	for ous in getattr(cereconf,(string.join((string.join(('LDAP',org),'_'),'ALTERNATIVE_NAME'),'_'))):
	    init_str += "%s: %s\n" % (cereconf.LDAP_ORG_ATTR,ous)
	init_str += "description: %s\n" % some2utf(getattr(cereconf,(string.join((string.join(('LDAP',org),'_'),'DESCRIPTION'),'_')))) 
	try:
	    for attrs in getattr(cereconf,(string.join((string.join(('LDAP',org),'_'),'ADD_ATTR'),'_'))):
		init_str += attrs + '\n'
	except: pass
	init_str += '\n'
	f.write(init_str)
    if cereconf.LDAP_MAN_LDIF_ADD_FILE:
        try:
	    lfile = file((string.join((cereconf.LDAP_DUMP_DIR,cereconf.LDAP_MAN_LDIF_ADD_FILE)),'/'), 'r')
        except:
            pass
        else:
	    f.write(lfile.read().strip()) 
	    f.write('\n')
	    lfile.close()
    f.close()	

def root_OU():
    ou = Factory.get('OU')(Cerebrum)
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
	text3 = """
Fill in the right organization-root in cereconf!
Set LDAP_ORG_ROOT_AUTO='Disable' and LDAP_ORG_ROOT to the correct ou_id number!"""
	sys.stdout.write(text3)
	org_root = None
	return(org_root)
    else:    
	root_org = Cerebrum.pythonify_data(root_id[0]['ou_id'])	
	return(root_org)

def generate_org(ou_id,filename=None):
    ou = Factory.get('OU')(Cerebrum)
    ou_list = ou.get_structure_mappings(co.perspective_lt)
    ou_string = "%s=%s,%s" % (cereconf.LDAP_ORG_ATTR,cereconf.LDAP_ORG_DN, cereconf.LDAP_BASE)
    trav_list(ou_id, ou_list, ou_string, filename)
    stedkode = Stedkode.Stedkode(Cerebrum)
    if (cereconf.LDAP_PRINT_NONE_ROOT == 'Enable'):
	root_ids = ou.root()
	if len(root_ids) > 1:
	    for org in root_ids:
		non_org = org['ou_id']
		if non_org <> ou_id:
		    stedkode.clear()
		    stedkode.find(non_org)
		    if (stedkode.katalog_merke == 'T'):
			stedkodestr = "%02d%02d%02d" % (stedkode.fakultet,
                                                        stedkode.institutt,
                                                        stedkode.avdeling)
			par_ou = "%s=%s,%s" % (cereconf.LDAP_ORG_ATTR,cereconf.LDAP_NON_ROOT_ATTR,ou_string)
			str_ou = print_OU(non_org, par_ou, stedkodestr, filename)
    
def print_OU(id, par_ou, stedkodestr,par, filename=None):
    ou = Factory.get('OU')(Cerebrum)
    ou.clear()
    ou.find(id)
    str_ou = []
    street_string = None
    post_string = None
    ou_phones = ou_faxs = ''
    if filename:
	f = file(filename, 'a')
    else:
	f = file(string.join((cereconf.LDAP_DUMP_DIR,cereconf.LDAP_ORG_FILE),'/'), 'a')
    if ou.acronym:
	ou_dn = make_ou_for_rdn(some2utf(ou.acronym))
    else:
	ou_dn = make_ou_for_rdn(some2utf(ou.short_name))
    str_ou = "%s=%s,%s" % (cereconf.LDAP_ORG_ATTR,ou_dn,par_ou)
    if dn_dict.has_key(str_ou):
        str_ou = "%s=%s+norOrgUnitNumber=%s,%s" % (cereconf.LDAP_ORG_ATTR,ou_dn,stedkodestr,par_ou)
    dn_dict[str_ou] = stedkodestr
    ou_str = "dn: %s\n" % str_ou
    ou_str += "objectClass: top\n"
    for ss in cereconf.LDAP_ORG_OBJECTCLASS:
        ou_str += "objectClass: %s\n" % ss
    if fax_tab.has_key(id):
	for ou_fax in fax_tab[id]:
	    ou_str += "facsimileTelephoneNumber: %s\n" % ou_fax
    try: 
	ou_email = get_contacts(entity_id=id,contact_type=int(co.contact_email),email=1)
    except:
        pass
    else:
	if ou_email:
	    for email in ou_email:
		ou_str += "mail: %s\n" % email
    if stedkodestr:	
	ou_str += "norOrgUnitNumber: %s\n" % stedkodestr
    cmp_ou_str = []
    if ou.acronym:
	acr_name = some2utf(ou.acronym)
	ou_str += "acronym: %s\n" % acr_name
    ou_str += "ou: %s\n" % ou_dn
    cmp_ou_str.append(normalize_string(ou_dn))
    cn_str = ou_dn
    if ou.acronym and normalize_string(acr_name) not in cmp_ou_str:
	cmp_ou_str.append(normalize_string(acr_name)) 
	ou_str += "ou: %s\n" % acr_name.strip()
    if ou.short_name:
	sho_name =  some2utf(ou.short_name).strip() 
	if normalize_string(sho_name) not in cmp_ou_str:
	    cmp_ou_str.append(normalize_string(sho_name))
	    ou_str += "ou: %s\n" % sho_name
            cn_str = sho_name
    if ou.display_name:
	dis_name = some2utf(ou.display_name).strip()
	if normalize_string(dis_name) not in cmp_ou_str:
	    cmp_ou_str.append(normalize_string(dis_name))
            ou_str += "ou: %s\n" % dis_name
            cn_str = dis_name
    if ou.sort_name:
        sor_name = some2utf(ou.sort_name).strip()
        if normalize_string(sor_name) not in cmp_ou_str:
            cmp_ou_str.append(normalize_string(sor_name))
            ou_str += "ou: %s\n" % sor_name
            cn_str = sor_name
    if cn_str:
	ou_str += "cn: %s\n" % cn_str
    for cc in cereconf.SYSTEM_LOOKUP_ORDER:
	try:
	    post_addr = ou.get_entity_address(int(getattr(co, cc)), 
						co.address_post)
	except:
            pass
        else:
    	    if post_addr:
                post_string = make_address("$",
                                           post_addr[0]['p_o_box'],
                                           post_addr[0]['address_text'],
                                           post_addr[0]['postal_number'],
                                           post_addr[0]['city'],
                                           post_addr[0]['country'])
                if post_string:
                    ou_str += "postalAddress: %s\n" % post_string
		break
    for dd in cereconf.SYSTEM_LOOKUP_ORDER:
	try:
            street_addr = ou.get_entity_address(int(getattr(co, dd)), co.address_street)
	except:
            pass
        else:
            if street_addr:
                street_string = make_address(", ",
                                             None,
                                             street_addr[0]['address_text'],
                                             street_addr[0]['postal_number'],
                                             street_addr[0]['city'],
                                             street_addr[0]['country'])
                if street_string:
                    ou_str += "street: %s\n" % street_string
                break
    if ph_tab.has_key(ou.ou_id):
	for phone in ph_tab[ou.ou_id]:
	    ou_str += "telephoneNumber: %s\n" % phone
    if par:
	ou_struct[int(id)] = (str_ou, post_string,
                              ", ".join(filter(None, (ou.short_name,
                                                      street_string))),
                              ou_phones, ou_faxs, int(par))
	f.close()
	return par_ou
    else:
	ou_struct[int(id)] = (str_ou, post_string, street_string,
                              ou_phones, ou_faxs, None)
        f.write("\n")
    	f.write(ou_str)
    	f.close()
    	return str_ou

    
def trav_list(par, ou_list, par_ou,filename=None):
    stedkode = Stedkode.Stedkode(Cerebrum)
    for c,p in ou_list:
	# Check if it is child of parent and not cyclic
	if (p == par) and (c <> par):
	    stedkode.clear()
	    try:
		stedkode.find(c)
	    except:
		ou_struct[str(c)] = par_ou
		str_ou = print_OU(c,par_ou,None,filename)
		trav_list(c,ou_list,str_ou,filename)
            else:
		stedkodestr = "%02d%02d%02d" % (stedkode.fakultet,
                                                stedkode.institutt,
                                                stedkode.avdeling)
 	   	if stedkode.katalog_merke == 'T':
            	    str_ou = print_OU(c,par_ou,stedkodestr,None,filename)
            	    trav_list(c,ou_list,str_ou,filename)
    	    	else:
		    dummy = print_OU(c,par_ou,stedkodestr,p,filename)
		    trav_list(c,ou_list,par_ou,filename)

def generate_person(filename=None):
    person = Factory.get('Person')(Cerebrum)
    group = Factory.get('Group')(Cerebrum)
    if filename:
	f = file(filename, 'a')
    else:
	f = SimilarSizeWriter(string.join((cereconf.LDAP_DUMP_DIR,cereconf.LDAP_PERSON_FILE),'/'), 'w')	
	f.set_size_change_limit(10)
    f.write("\n")
    objclass_string = "objectClass: top\n"
    for objclass in cereconf.LDAP_PERSON_OBJECTCLASS:
	objclass_string += "objectclass: %s\n" % objclass
    dn_attr = cereconf.LDAP_PERSON_ATTR
    dn_base = "%s" % cereconf.LDAP_BASE
    dn_string = "%s=%s,%s" % (cereconf.LDAP_ORG_ATTR,cereconf.LDAP_PERSON_DN,dn_base) 
    person_spread = acl_spread = None
    valid_print_affi = []
    valid_phaddr_affi = []
    valid_aff_aci = []
    aci_student_gr = {}
    aci_empl_gr = {}
    if (cereconf.LDAP_PERSON_FILTER == 'Enable'):
	try: 
	    for status in cereconf.LDAP_PERSON_LIST_AFFI:
		valid_print_affi.append(int(getattr(co,status)))
	except: pass
	try:
	    for status in cereconf.LDAP_PERSON_PH_ADDR_AFFI:
		valid_phaddr_affi.append(int(getattr(co,status)))
	except: pass
	try:
            for status in cereconf.LDAP_PERSON_AFF_ACI:
                valid_aff_aci.append(int(getattr(co,status)))
        except: pass
	try:
	    group.find_by_name(str(cereconf.PERSON_NOT_PUBLIC_GR))
	    for entries in group.list_members(member_type=co.entity_person)[0]:
		aci_empl_gr[int(entries[1])] = True
		#aci_empl_gr.append(entries[1])
	except: pass
	group.clear()
	try: 
	    group.find_by_name(str(cereconf.PERSON_PUBLIC_GR))
	    for entries in group.list_members(member_type=co.entity_person)[0]:
		aci_student_gr[int(entries[1])] = True
	except Errors.NotFoundError: pass
	try:  person_spread = int(getattr(co,cereconf.PERSON_SPREAD))
	except:  pass
	try:  acl_spread = int(cereconf.LDAP_PERSON_ACL_SPREAD) 
	except:  pass
    if (cereconf.LDAP_CEREMAIL == 'Enable'):
	email_enable = True
	email_domains = {}
	try:
	    email_domains = cereconf.LDAP_REWRITE_EMAIL_DOMAIN
	except: pass
    else: email_enable = False
    affili_stu = "student"
    affili_em = "employee"
    for row in person.list_extended_person(person_spread,
				include_quarantines = True, include_mail = email_enable):
	name,entity_name,ou_id,affili,status = row['name'],row['entity_name'],row['ou_id'],row['affiliation'],int(row['status'])
	person.clear()
        person.entity_id = row['person_id']
	p_affiliations = person.get_affiliations()
	aci_person = False 
	print_person = False
	print_phaddr = False
	if (cereconf.LDAP_PERSON_FILTER == 'Enable'):
	    for pr_status in p_affiliations:
		status = int(pr_status['status'])
		if status in valid_print_affi: 
		    print_person = True
		    if status in valid_phaddr_affi: 
			print_phaddr = True
		    if status in valid_aff_aci: 
			aci_person = True 
	else: 
	    print_person = True
	    aci_person = True
	    print_phaddr = True
	if print_person:
	    person.clear()
	    person.entity_id = row['person_id']
	    pers_string = "dn: %s=%s,%s\n" % (dn_attr,entity_name,dn_string)
	    pers_string += "%s" % objclass_string
  	    utf_name = some2utf(name)
	    pers_string += "cn: %s\n" % utf_name
	    if row['birth_date']:
		pers_string += "birthDate: %s\n" % (time.strftime("%d%m%y",time.strptime(str(row['birth_date']),
									"%Y-%m-%d %H:%M:%S.00")))
	    pers_string += "norSSN: %s\n" % re.sub('\D','',row['external_id'])
	    pers_string += "eduPersonOrgDN: %s\n" % dn_base
	    try:
		if (ou_struct[int(ou_id)][5] == None):
	    	    prim_org = (ou_struct[int(ou_id)][0])
		else:
		    par = int(ou_struct[int(ou_id)][5])
		    while ou_struct[par][5] <> None:
			par = int(ou_struct[int(par)][5])
		    prim_org = (ou_struct[par][0])
	    except:
		prim_org = "%s=%s,%s" % (cereconf.LDAP_ORG_ATTR,cereconf.LDAP_DUMMY_DN,cereconf.LDAP_BASE)
	    if (string.find(prim_org,cereconf.LDAP_ORG_DN) == -1):
		prim_org = "%s=%s,%s" % (cereconf.LDAP_ORG_ATTR,cereconf.LDAP_DUMMY_DN,cereconf.LDAP_BASE)
	    pers_string += "eduPersonPrimaryOrgUnitDN: %s\n" % prim_org
	    org_printed = []
	    pers_string += "eduPersonOrgUnitDN: %s\n" % prim_org
	    org_printed.append(prim_org)
	    for edu_org in p_affiliations:
		try:
		    org = ou_struct[int(edu_org['ou_id'])][0]
		    if org not in org_printed and (ou_struct[int(edu_org['ou_id'])][5] == None):
			pers_string += "eduPersonOrgUnitDN: %s\n" % org
			org_printed.append(org)
		except: pass
	    pers_string += "eduPersonPrincipalName: %s@%s\n" % (entity_name, cereconf.LDAP_BASE_DOMAIN)
	    lastname = name
	    for sys in cereconf.SYSTEM_LOOKUP_ORDER:
		try:
		    pers_string += "givenName: %s\n" % some2utf(person.get_name(getattr(co,sys),co.name_first))
		    lastname = person.get_name(getattr(co,sys),co.name_last)
		    break
		except:
		    pass
	    if email_enable:
	    	if row['local_part'] and row['domain']:
		    domain = row['domain']
		    if email_domains and email_domains.has_key(domain):
			pers_string += "mail: %s@%s\n" % (row['local_part'],email_domains[domain])
		    else:
			pers_string += "mail: %s@%s\n" % (row['local_part'],domain)
	    else:
		pers_string += "mail: %s\n" % person.get_contact_info(source=None,type=co.contact_email)
	    if lastname:
		pers_string += "sn: %s\n" % some2utf(lastname)
	    if print_phaddr:
		if ((row['post_text']) or (row['post_postal'])):
		    post_string = make_address("$",
					row['post_box'],
					row['post_text'],
					row['post_postal'],
					row['post_city'],
					row['post_country'])
		if post_string:
		    pers_string += "postalAddress: %s\n" % post_string
		if ((row['address_text']) or (row['postal_number'])):
		    street_string = make_address(", ",
					None,
					row['address_text'],
					row['postal_number'],
					row['city'],
					row['country'])
		if street_string:
		    pers_string += "street: %s\n" % street_string
		if row['personal_title']:
		    pers_string += "title: %s\n" % some2utf(row['personal_title'])
		else:
     		    if row['title']:
			pers_string += "title: %s\n" % some2utf(row['title'])
		if ph_tab.has_key(person.entity_id):
		    for phone in ph_tab[person.entity_id]:
			pers_string += "telephoneNumber: %s\n" % phone
		if fax_tab.has_key(person.entity_id):
                    for fax in fax_tab[person.entity_id]:
                        pers_string += "facsimileTelephoneNumber: %s\n" % fax
	    affili_str = str('')
	    for affi in p_affiliations:
                if (int(affi['affiliation']) == int(co.affiliation_ansatt)):
                    if (string.find(affili_str,affili_em) == -1):
                        pers_string += "eduPersonAffiliation: %s\n" % affili_em
			affili_str += affili_em
		    if (affi['status'] == co.affiliation_status_ansatt_tekadm) and \
					(string.find(affili_str,'staff') == -1):
			pers_string += "eduPersonAffiliation: staff\n"
			affili_str += 'staff' 
		    if (affi['status'] == co.affiliation_status_ansatt_vit) and \
					(string.find(affili_str,'faculty') == -1):
			pers_string += "eduPersonAffiliation: faculty\n"
			affili_str += 'faculty'
                if (int(affi['affiliation']) == int(co.affiliation_student)):
                    if (string.find(affili_str,affili_stu) == -1):
                        pers_string += "eduPersonAffiliation: %s\n" % affili_stu
                        affili_str += affili_stu
	    pers_string += "uid: %s\n" % entity_name
	    passwd = row['auth_data']
	    if passwd:
		if row['quarantine_type'] is not None:
            	    qh = QuarantineHandler.QuarantineHandler(Cerebrum, [row['quarantine_type']])
            	    if qh.should_skip():
			continue
            	    if qh.is_locked():
			passwd = '*Locked'
		pers_string += "userPassword: {crypt}%s\n" % passwd
	    else:
		pers_string += "userPassword: {crypt}*Invalid\n"
	    #if aci_person  and (int(person.entity_id)  not in aci_empl_gr):
	    if aci_person  and not aci_empl_gr.has_key(int(person.entity_id)):
		pers_string += "%s\n" % cereconf.LDAP_PERSON_ACI
	    elif (aci_student_gr.has_key(int(person.entity_id))) and not aci_person:
		pers_string += "%s\n" % cereconf.LDAP_PERSON_ACI
	    alias_list[int(person.entity_id)] = entity_name,prim_org,name,lastname
	    f.write("\n")
	    f.write(pers_string)
	else:
	    pass
    f.close()

def generate_alias(filename=None):
    person = Factory.get('Person')(Cerebrum)
    dn_string = "%s=%s,%s" % (cereconf.LDAP_ORG_ATTR,cereconf.LDAP_PERSON_DN,cereconf.LDAP_BASE)
    if filename:
	f = file(filename,'a')
    else:
	f = SimilarSizeWriter(string.join((cereconf.LDAP_DUMP_DIR,cereconf.LDAP_ALIAS_FILE),'/'), 'w')
	f.set_size_change_limit(10)
    f.write("\n")
    obj_string = "\nobjectClass: top"
    for obj in cereconf.LDAP_ALIAS_OBJECTCLASS:
        obj_string += "\nobjectClass: %s" % obj
    for alias in person.list_persons():
	person_id = int(alias['person_id'])
	if alias_list.has_key(person_id):
	    entity_name, prim_org, name, lastname = alias_list[person_id]
	    alias_str = "\ndn: uid=%s,%s" % (entity_name, prim_org)
	    alias_str += "%s" % obj_string
	    alias_str += "\nuid: %s" % entity_name
	    if name:
		alias_str += "\ncn: %s" % some2utf(name)
	    if lastname:
		alias_str += "\nsn: %s" % some2utf(lastname)
	    alias_str += "\naliasedObjectName: uid=%s,%s" % (entity_name,dn_string)
	    f.write("\n")
	    f.write(alias_str)
    f.close()

def generate_users(spread=None,filename=None):
    posix_user = PosixUser.PosixUser(Cerebrum)
    disk = Factory.get('Disk')(Cerebrum)
    if spread: spreads = eval_spread_codes(spread)
    else: spreads = eval_spread_codes(cereconf.LDAP_USER_SPREAD)
    shells = {}
    for sh in posix_user.list_shells():
	shells[int(sh['code'])] = sh['shell']
    disks = {}
    for hd in disk.list(spread=user_spread):
	disks[int(hd['disk_id'])] = hd['path']  
    posix_dn = ",%s=%s,%s" % (cereconf.LDAP_ORG_ATTR,cereconf.LDAP_USER_DN,cereconf.LDAP_BASE)
    posix_dn_string = "%s=" % cereconf.LDAP_USER_ATTR
    obj_string = "objectClass: top\n"
    for obj in cereconf.LDAP_USER_OBJECTCLASS:
	obj_string += "objectClass: %s\n" % obj
    if filename is None:
        filename = os.path.join(cereconf.LDAP_DUMP_DIR,
                                cereconf.LDAP_USER_FILE)
    f = SimilarSizeWriter(filename)
    f.set_size_change_limit(10)
    done_users = {}
    # When all authentication-needing accounts possess an 'md5_crypt'
    # password hash, the below code can be fixed to call
    # list_extended_posix_users() only once.  Until then, we fall back
    # to using 'crypt3_des' hashes.
    #
    # We already favour the stronger 'md5_crypt' hash over any
    # 'crypt3_des', though.
    for auth_method in (co.auth_type_md5_crypt, co.auth_type_crypt3_des):
        prev_userid = 0
        for row in posix_user.list_extended_posix_users(
            auth_method, spreads, include_quarantines = True):
            (acc_id, shell, gecos, uname) = (
                row['account_id'], row['shell'], row['gecos'],
                row['entity_name'])
            acc_id = int(acc_id)
            if done_users.has_key(acc_id):
                continue
            entity2uname[acc_id] = uname
            if row['auth_data'] is None:
                if auth_method == co.auth_type_crypt3_des:
                    # Neither md5_crypt nor crypt3_des hash found.
                    passwd = '{crypt}*Invalid'
                else:
                    continue
            else:
                passwd = "{crypt}%s" % row['auth_data']
            shell = shells[int(shell)]
            if row['quarantine_type'] is not None:
                qh = QuarantineHandler.QuarantineHandler(
                    Cerebrum, [row['quarantine_type']])
                if qh.should_skip():
                    continue
                if qh.is_locked():
                    passwd = '{crypt}*Locked'
                qshell = qh.get_shell()
                if qshell is not None:
                    shell = qshell
            if row['name']:
                cn = some2utf(row['name'])
            elif gecos:
                cn = some2utf(gecos)
            else:
                cn = uname
            if gecos:
                gecos = latin1_to_iso646_60(some2iso(gecos))
            else:
                gecos = latin1_to_iso646_60(some2iso(cn))
            if not row['home']:
                home = "%s/%s" % (disks[int(row['disk_id'])],uname)
            else:
                home = row['home']
            if acc_id <> prev_userid:
                f.write('dn: %s%s%s\n' % (posix_dn_string, uname, posix_dn))
                f.write('%scn: %s\n' % (obj_string, gecos))
                f.write('uid: %s\n' % uname)
                f.write('uidNumber: %s\n' % str(row['posix_uid']))
                f.write('gidNumber: %s\n' % str(row['posix_gid']))
                f.write('homeDirectory: %s\n' % home)
                f.write('userPassword: %s\n' % passwd)
                f.write('loginShell: %s\n' % shell)
                f.write('gecos: %s\n' % gecos)
                f.write('\n')
                done_users[acc_id] = True
                prev_userid = acc_id
    f.write("\n")
    f.close()


def generate_posixgroup(spread=None, filename=None):
    posix_group = PosixGroup.PosixGroup(Cerebrum)
    group = Factory.get('Group')(Cerebrum)
    if spread: spreads = eval_spread_codes(spread)
    else: spreads = eval_spread_codes(cereconf.LDAP_GROUP_SPREAD)
    user_spread = int(getattr(co,cereconf.LDAP_USER_SPREAD[0]))
    if filename:
	f = file(filename, 'w')
    else:
	f = SimilarSizeWriter(string.join((cereconf.LDAP_DUMP_DIR,cereconf.LDAP_GROUP_FILE),'/'), 'w')
	f.set_size_change_limit(10)
    groups = {}
    dn_str = "%s=%s,%s" % (cereconf.LDAP_ORG_ATTR,cereconf.LDAP_GROUP_DN,cereconf.LDAP_BASE)
    obj_str = "objectClass: top\n"
    for obj in cereconf.LDAP_GROUP_OBJECTCLASS:
	obj_str += "objectClass: %s\n" % obj
    for row in posix_group.list_all_test(spreads):
	distinct_mem = {}
	posix_group.clear()
	try:
	    posix_group.find(row.group_id)
	    gname = posix_group.group_name
	    pos_grp = "dn: %s=%s,%s\n" % (cereconf.LDAP_GROUP_ATTR,gname,dn_str)
	    pos_grp += "%s" % obj_str
	    pos_grp += "cn: %s\n" % gname
	    pos_grp += "gidNumber: %s\n" % posix_group.posix_gid
	    if posix_group.description:
		pos_grp += "description: %s\n" % some2utf(posix_group.description) #latin1_to_iso646_60 later
	    group.clear()
	    group.find(row.group_id)
	    for id in group.get_members(spread=user_spread,get_entity_name=True):
		uname_id = int(id[0])
		if not distinct_mem.has_key(uname_id):
		    distinct_mem[uname_id] = True
		    if entity2uname.has_key(uname_id):
			pos_grp += "memberUid: %s\n" % entity2uname[uname_id]
		    else:
			mem_name = id[1]
			entity2uname[uname_id] = mem_name 
			pos_grp += "memberUid: %s\n" % mem_name
	    f.write("\n")
            f.write(pos_grp)
	except:  pass
    f.write("\n")
    f.close()

def generate_netgroup(spread=None, filename=None):
    global grp_memb
    pos_netgrp = Factory.get('Group')(Cerebrum)
    if filename:
        f = file(filename, 'w')
    else:
        f = SimilarSizeWriter(string.join((cereconf.LDAP_DUMP_DIR,cereconf.LDAP_NETGROUP_FILE),'/'), 'w')
        f.set_size_change_limit(10)
    if spread: spreads = eval_spread_codes(spread)
    else: spreads = eval_spread_codes(cereconf.LDAP_NETGROUP_SPREAD)
    f.write("\n")
    dn_str = "%s=%s,%s" % (cereconf.LDAP_ORG_ATTR,cereconf.LDAP_NETGROUP_DN,cereconf.LDAP_BASE)
    obj_str = "objectClass: top\n"
    for obj in cereconf.LDAP_NETGROUP_OBJECTCLASS:
        obj_str += "objectClass: %s\n" % obj
    for row in pos_netgrp.list_all_test(spreads):
	grp_memb = {}
        pos_netgrp.clear()
        try:
            pos_netgrp.find(row.group_id)
            netgrp_name = pos_netgrp.group_name
            netgrp_str = "dn: %s=%s,%s\n" % (cereconf.LDAP_NETGROUP_ATTR,netgrp_name,dn_str)
            netgrp_str += "%s" % obj_str
            netgrp_str += "cn: %s\n" % netgrp_name
            if not entity2uname.has_key(int(row.group_id)):
                entity2uname[int(row.group_id)] = netgrp_name
            if pos_netgrp.description:
                 netgrp_str+= "description: %s\n" % latin1_to_iso646_60(pos_netgrp.description)
            f.write(netgrp_str)
            get_netgrp(row.group_id,spreads,f)
            f.write("\n")
        except:
            pass
    f.close()

def get_netgrp(netgrp_id,spreads,f):
    pos_netgrp = Factory.get('Group')(Cerebrum)
    pos_user = PosixUser.PosixUser(Cerebrum)
    pos_netgrp.clear()
    pos_netgrp.find(int(netgrp_id))
    try:
        for id in pos_netgrp.list_members(int(getattr(co,(cereconf.LDAP_USER_SPREAD[0]))),\
							int(co.entity_account))[0]:
            uname_id = int(id[1])
	    try:
            	if entity2uname.has_key(uname_id):
                    uname = entity2uname[uname_id]
		else:
		    pos_user.clear()
		    pos_user.find(uname_id)
		    uname = pos_user.account_name
            # The LDAP schema for NIS netgroups doesn't allow
            # usernames with '_' in.
		if ('_' not in uname) and not grp_memb.has_key(uname_id):
		    f.write("nisNetgroupTriple: (,%s,)\n" % uname)
		    grp_memb[uname_id] = True
	    except: print "LDAP:netgroup: User not valid (%d)" % uname_id
        for group in pos_netgrp.list_members(None,int(co.entity_group))[0]:
            valid_spread = False
            pos_netgrp.clear()
            group_id = int(group[1])
            pos_netgrp.find(group_id)
            for spread_search in spreads:
                if pos_netgrp.has_spread(spread_search):
                    valid_spread = True
            if valid_spread:
                f.write("memberNisNetgroup: %s\n" % pos_netgrp.group_name)
            else:
                get_netgrp(group_id,spreads,f)
    except: print "Fault with group: %s" % netgrp_id


def eval_spread_codes(spread):
    spreads = []
    if (type(spread) == type(0) or type(spread) == type('')):
        if (spread_code(spread)):
            spreads.append(spread_code(spread))
    elif (type(spread) == type([]) or type(spread) == type(())):
        for entry in spread:
            if (spread_code(entry)):
                spreads.append(spread_code(entry))
    else:
        spreads = None
    return(spreads)


def spread_code(spr_str):
    spread = None
    if (type(spr_str) == type(0)):
        spread = spr_str
    elif (type(spr_str) == type('')):
        if (len(spr_str) > 1):
            try: spread = int(getattr(co,spr_str))
            except:
                try: spread = int(spr_str)
                except: print "Not valid spread code: '%s'" % spr_str # Change to logger
        else:
            try: spread = int(spr_str)
            except: print "Not valid spread code: '%s'" % spr_str # Change to logger
    return(spread)


def iso2utf(s):
    """Convert iso8859-1 to utf-8"""
    utf_str = unicode(s,'iso-8859-1').encode('utf-8')
    return utf_str

def utf2iso(s):
    """Convert utf-8 to iso8859-1"""
    iso_str = unicode(s,'utf-8').encode('iso-8859-1')
    return iso_str

# match an 8-bit string which is not an utf-8 string
iso_re = re.compile("[\300-\377](?![\200-\277])|(?<![\200-\377])[\200-\277]")

# match an 8-bit string
eightbit_re = re.compile('[\200-\377]')

# match multiple spaces
multi_space_re = re.compile('[%s]{2,}' % string.whitespace)

def some2utf(str):
    """Convert either iso8859-1 or utf-8 to utf-8"""
    if iso_re.search(str):
        str = unicode(str, 'iso8859-1').encode('utf-8')
    return str

def some2iso(str):
    """Convert either iso8859-1 or utf-8 to iso8859-1"""
    if eightbit_re.search(str) and not iso_re.search(str):
        str = unicode(str, 'utf-8').encode('iso8859-1')
    return str

def normalize_phone(phone):
    """Normalize phone/fax numbers for LDAP"""
    return phone.translate(normalize_trans, " -")
 
def normalize_string(str):
    """Normalize strings for LDAP"""
    str = multi_space_re.sub(' ', str.translate(normalize_trans).strip())
    if eightbit_re.search(str):
        str = unicode(str, 'utf-8').lower().encode('utf-8')
    return str

# Match attributes with the printableString LDAP syntax
printablestring_re = re.compile('^[a-zA-Z0-9\'()+,\\-.=/:? ]+$')

ou_rdn_re = re.compile(r'[,+\\ ]+')

def make_ou_for_rdn(ou):
    return ou_rdn_re.sub(' ', ou).strip()


def verify_printableString(str):
    """Return true if STR is valid for the LDAP syntax printableString"""
    return printablestring_re.match(str)

#def get_contacts(id,contact_type,email=0):
#    """ Process infomation in entity_contact_info into a list.
#        Splits string in to entities, nomalize and remove duplicats"""
#    entity = Entity.EntityContactInfo(Cerebrum)
#    entity.clear()
#    entity.entity_id = int(id)
#    list_contact_entry = []
#    contact_entries = entity.get_contact_info(co.system_lt, int(contact_type))
#    if len(contact_entries) == 1:
#    	for contact in string.split((Cerebrum.pythonify_data(contact_entries[0]['contact_value'])),'$'):
#	    if normalize_phone(contact) not in list_contact_entry and email == 0:
#		list_contact_entry.append(normalize_phone(contact))
#	    elif contact not in list_contact_entry and email == 1:
#		list_contact_entry.append(contact)  
#    elif len(contact_entries) >> 1:
#	for contact_entry in contact_entries:
#	    for contact in  string.split((Cerebrum.pythonify_data(contact_entry['contact_value'])),'$'):
#		if normalize_phone(contact) not in list_contact_entry and email == 0:
#                    list_contact_entry.append(normalize_phone(contact))
#		elif contact not in list_contact_entry and email == 1:
#		     list_contact_entry.append(contact)
#    else:
#	list_contact_entry = None
#    return(list_contact_entry)
	
def get_contacts(entity_id=None,source_system=None,contact_type=None,email=0):
    entity = Entity.EntityContactInfo(Cerebrum)
    cont_tab = {}
    for x in entity.list_contact_info(entity_id=entity_id, \
		source_system=source_system,contact_type=contact_type):
	ph_list = []
	if '$' in str(x['contact_value']):
	    ph_list = [str(y) for y in str(x['contact_value']).split('$')]
	elif ('/' in str(x['contact_value']) and not email):
	    ph_list = [str(y) for y in str(x['contact_value']).split('/')]
	else: ph_list.append(str(x['contact_value']))
	key = int(x['entity_id'])
	for ph in ph_list:
	    if (ph <> '0'):
		if not email:
		    ph = re.sub('\s','',normalize_phone(ph))
		if ph:
		    if cont_tab.has_key(key):
			if ph not in cont_tab[key]: cont_tab[key].append(ph)
		    else: cont_tab[key] = [ph,]
    if ((len(cont_tab) == 1) or entity_id):
	for k,v in cont_tab.items():
	    return(v)
    else:
	return(cont_tab)




need_base64_re = re.compile('^\\s|[\0\r\n]|\\s$')

def make_attr(name, strings, normalize = None, verify = None, raw = False):
    ret = []
    done = {}

    # Make each attribute name and value - but only one of
    # each value, compared by attribute syntax ('normalize')
    for str in strings:
        if not raw:
            # Clean up the string: remove surrounding and multiple whitespace
            str = multi_space_re.sub(' ', str.strip())

        # Skip the value if it is not valid according to its LDAP syntax
        if str == '' or (verify and not verify(str)):
            continue

        # Check if value has already been made (or equivalent by normalize)
        if normalize:
            norm = normalize(str)
        else:
            norm = str
        if done.has_key(norm):
            continue
        done[norm] = True

        # Encode as base64 if necessary, otherwise as plain text
        if need_base64_re.search(str):
            ret.append("%s:: %s\n" % (name, (base64.encodestring(str)
                                             .replace("\n", ''))))
        else:
            ret.append("%s: %s\n" % (name, str))

    return ''.join(ret)


def main():
    global debug, user_spread
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'dg:p:n:',
                                   ['debug', 'help', 'group=','org=','person=','user=',
                                    'group_spread=','user_spread=', 'netgroup=','posix'])
    except getopt.GetoptError:
        usage(1)

    user_spread = group_spread = None
    
    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('-d', '--debug'):
            debug += 1
	elif opt in ('-o','--org'):
	    if (cereconf.LDAP_ORG_ROOT_AUTO == 'Enable'):
		org_root = int(cereconf.LDAP_ORG_ROOT)
	    else:
		org_root = root_OU()
	    if org_root:
		load_code_tables() 
		init_ldap_dump(org_root,val)
		generate_org(org_root,val)
		generate_person(val)
		generate_alias(val)
	elif opt in ('-p', '--person'):
            generate_person(val)
	elif opt in ('-u', '--user'):
            #generate_users(user_spread, val)
	    generate_users()
	elif opt in ('-g', '--group'):
	    #load_entity2uname()
	    generate_posixgroup(group_spread, val)
	elif opt in ('-n', '--netgroup'):
	    #load_entity2uname()
	    #generate_netgroup(group_spread, val)
	    generate_netgroup()
	elif opt in ('--user_spread',):
	    user_spread = map_spread(val)
	elif opt in ('--group_spread',):
	    group_spread = map_spread(val)
	elif opt in ('--posix',):
            generate_users()
            generate_posixgroup()
            generate_netgroup()
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
    --netgroup=<outfile>
      Write netgroup map to a LDIF-file
    --posix 
      write all posix-user,-group and -netgroup from default ldapconf parameters

    Generates an LDIF-file of the requested type for the requested spreads."""
    sys.exit(exitcode)

def map_spread(id):
    try:
        return int(_SpreadCode(id))
    except Errors.NotFoundError:
        print "Error mapping %s" % id
        raise

def config():
	if (cereconf.LDAP_ORG_ROOT_AUTO != 'Enable'):
	    try:
	    	org_root = int(cereconf.LDAP_ORG_ROOT)
	    except Errors.NotFoundError:
		print "ORG_ROOT parametre in ldapconf.py not valid"
		raise
	else:
	    org_root = root_OU()
	if org_root: 
	    load_code_tables()
	    init_ldap_dump(org_root)
	    generate_org(org_root)
	    if (cereconf.LDAP_PERSON == 'Enable'):
    		print "Person generate" 
		generate_person()
	    if (cereconf.LDAP_ALIAS == 'Enable'):
		print "Alias generate"
		generate_alias()
	    if (cereconf.LDAP_USER == 'Enable'):
		print "User generate"
		generate_users()
	    if (cereconf.LDAP_GROUP == 'Enable'):
		print "Group generate"
		generate_posixgroup()
	    if (cereconf.LDAP_NETGROUP == 'Enable'):
		print "Netgroup generate"
		generate_netgroup()
	    #files_
	else:
	    pass
	
if __name__ == '__main__':
    	main()

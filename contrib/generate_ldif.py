#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Copyright 2002, 2003, 2004 University of Oslo, Norway
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

import time, re, string, sys, getopt, base64, os

import cerebrum_path
import cereconf  
from Cerebrum import Errors
from Cerebrum import Entity
from Cerebrum.extlib import logging
from Cerebrum.Utils import Factory, latin1_to_iso646_60, SimilarSizeWriter
from Cerebrum.modules.no import Stedkode
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup
from Cerebrum import QuarantineHandler
from Cerebrum.Constants import _SpreadCode
from Cerebrum.modules.LDIFutils import *

Cerebrum = Factory.get('Database')()
co = Factory.get('Constants')(Cerebrum)

logging.fileConfig(cereconf.LOGGING_CONFIGFILE)
logger = logging.getLogger("cronjob")

ou_struct = {}
entity2uname = {}
affiliation_code = {}
alias_list = {}
org_root = None
global dn_dict
dn_dict = {}
disablesync_cn = 'disablesync'


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
	f = file(filename, 'w')
    else:
	f = file(cereconf.LDAP_DUMP_DIR + "/" + cereconf.LDAP_ORG_FILE, 'w')
    init_str = "dn: %s\n" % (cereconf.LDAP_BASE)    
    for oc in ('top', 'organization', 'eduOrg', 'norEduOrg'):
	init_str += "objectClass: %s\n" % oc
    homepage = cereconf.getattr(LDAP_BASE_URL, None)
    if homepage:
        init_str += """objectClass: labeledURIObject
labeledURI: %s
eduOrgHomePageURI: %s
""" % (homepage, homepage)
    init_str += "%s: %s\n" % tuple(cereconf.LDAP_BASE
                                   .split(',')[0].split('=', 2))
    init_str += ("norEduOrgUniqueNumber: %08d\n"
                 % int(cereconf.DEFAULT_INSTITUSJONSNR))
    for bc in cereconf.LDAP_BASE_BUSINESSCATEGORY:
	init_str += "businessCategory: %s\n" % bc
    for des in cereconf.LDAP_BASE_DESCRIPTION:
	init_str += "description: %s\n" % des
    ou = Factory.get('OU')(Cerebrum)
    ou.find(ou_org)
    if fax_tab.has_key(int(ou_org)):
	for fax in fax_tab[int(ou_org)]:
	    init_str += "facsimileTelephoneNumber: %s\n" % fax

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
    f.write(init_str)
    f.write("\n")

    ou_struct[int(ou.ou_id)] = (cereconf.LDAP_BASE, post_string,
                                street_string, None, None, None)
    for org in cereconf.LDAP_ORG_GROUPS:
	if org == 'DUMMY': continue     # backwards compatibility hack
	org = org.upper()
	init_str = "dn: %s\n" % get_tree_dn(org)
	init_str += "objectClass: top\n"
	for obj in cereconf.LDAP_ORG_OBJECTCLASS:
	    init_str += "objectClass: %s\n" % obj
	for ous in getattr(cereconf, 'LDAP_' + org + '_ALTERNATIVE_NAME'):
	    init_str += "%s: %s\n" % (cereconf.LDAP_ORG_ATTR,ous)
	init_str += "description: %s\n" % \
                    some2utf(getattr(cereconf, 'LDAP_' + org + '_DESCRIPTION'))
        try:
            for attrs in getattr(cereconf, 'LDAP_' + org + '_ADD_ATTR'):
                init_str += attrs + '\n'
        except AttributeError:
            pass
	init_str += '\n'
	f.write(init_str)
    if cereconf.LDAP_MAN_LDIF_ADD_FILE:
        try:
	    lfile = file(cereconf.LDAP_DUMP_DIR + '/' +
                         cereconf.LDAP_MAN_LDIF_ADD_FILE, 'r')
        except:
            pass
        else:
	    f.write(lfile.read().strip()) 
	    f.write('\n')
	    lfile.close()

    if True:
        stedkode = Stedkode.Stedkode(Cerebrum)
	stedkode.find(ou_org)
        stedkodestr = "%02d%02d%02d" % (
            stedkode.fakultet, stedkode.institutt, stedkode.avdeling)

	init_str = "dn: ou=%s,%s" % (cereconf.LDAP_NON_ROOT_ATTR,
                                     get_tree_dn('ORG'))
        for ss in ('top', 'organizationalUnit', 'norEduOrgUnit'):
            init_str += "objectClass: %s\n" % ss
        init_str += "ou: %s\n" % cereconf.LDAP_NON_ROOT_ATTR
        init_str += "norEduOrgUnitUniqueNumber: %s\n" % stedkodestr
        init_str += ("norEduOrgUniqueNumber: %08d\n"
                   % int(cereconf.DEFAULT_INSTITUSJONSNR))
	f.write(init_str)
        f.write("\n")

    f.close()

def root_OU():
    ou = Factory.get('OU')(Cerebrum)
    root_id=ou.root()
    if len(root_id) > 1:
	text1 = """
You have %d roots in your organization-tree. Cerebrum only support 1.\n""" % \
								(len(root_id))
        sys.stdout.write(text1)
    	for p in root_id:
            root_org = Cerebrum.pythonify_data(p['ou_id'])
	    ou.clear()
	    ou.find(root_org)
	    text2 = "Organization: %s   ou_id= %s \n" % (ou.sort_name, ou.ou_id)
	    sys.stdout.write(text2)
	text3 = """
Fill in the right organization-root in cereconf!
Set LDAP_ORG_ROOT_AUTO='Disable' and LDAP_ORG_ROOT to the correct ou_id no.!"""
	sys.stdout.write(text3)
	org_root = None
	return(org_root)
    else:    
	root_org = Cerebrum.pythonify_data(root_id[0]['ou_id'])	
	return(root_org)

def generate_org(ou_id,filename=None):
    ou = Factory.get('OU')(Cerebrum)
    ou_list = ou.get_structure_mappings(co.perspective_lt)
    ou_string = get_tree_dn('ORG')
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
			par_ou = "ou=%s,%s" % (cereconf.LDAP_NON_ROOT_ATTR,
						ou_string)
			str_ou = print_OU(non_org, par_ou, stedkodestr, filename)
    
def print_OU(id, par_ou, stedkodestr,par, filename=None):
    ou = Factory.get('OU')(Cerebrum)
    ou.clear()
    ou.find(id)
    street_string = None
    post_string = None
    ou_phones = ou_faxs = ''
    if filename:
	f = file(filename, 'a')
    else:
	f = file(cereconf.LDAP_DUMP_DIR + '/' + cereconf.LDAP_ORG_FILE, 'a')
    if ou.acronym:
	ou_dn = make_ou_for_rdn(some2utf(ou.acronym))
    else:
	ou_dn = make_ou_for_rdn(some2utf(ou.short_name))
    str_ou = "ou=%s,%s" % (ou_dn, par_ou)
    if dn_dict.has_key(str_ou):
        str_ou = "norEduOrgUnitUniqueNumber=%s+%s" % (stedkodestr, str_ou)
    dn_dict[str_ou] = stedkodestr
    ou_str = "dn: %s\n" % str_ou
    for ss in ('top', 'organizationalUnit', 'norEduOrgUnit'):
        ou_str += "objectClass: %s\n" % ss
    if fax_tab.has_key(id):
	for ou_fax in fax_tab[id]:
	    ou_str += "facsimileTelephoneNumber: %s\n" % ou_fax
    try: 
	ou_email = get_contacts(entity_id=id,contact_type=int(co.contact_email),
									email=1)
    except:
        pass
    else:
	if ou_email:
	    for email in ou_email:
		ou_str += "mail: %s\n" % email
    ou_str += "norEduOrgUnitUniqueNumber: %s\n" % stedkodestr
    ou_str += ("norEduOrgUniqueNumber: %08d\n"
               % int(cereconf.DEFAULT_INSTITUSJONSNR))
    cmp_ou_str = []
    if ou.acronym:
	acr_name = some2utf(ou.acronym)
	ou_str += "norEduOrgAcronym: %s\n" % acr_name
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
            street_addr = ou.get_entity_address(int(getattr(co, dd)), 
							co.address_street)
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
                sys.exit("ou_id %s mangler stedkode" % c)
            stedkodestr = "%02d%02d%02d" % (stedkode.fakultet,
                                            stedkode.institutt,
                                            stedkode.avdeling)
            if stedkode.katalog_merke == 'T':
                str_ou = print_OU(c, par_ou, stedkodestr, None, filename)
                trav_list(c, ou_list, str_ou, filename)
            else:
                dummy = print_OU(c, par_ou, stedkodestr, p, filename)
                trav_list(c, ou_list, par_ou, filename)

def generate_person(filename=None):
    person = Factory.get('Person')(Cerebrum)
    group = Factory.get('Group')(Cerebrum)
    if filename:
	f = file(filename, 'a')
    else:
	f = SimilarSizeWriter(cereconf.LDAP_DUMP_DIR + '/' +
                              cereconf.LDAP_PERSON_FILE, 'w')	
	f.set_size_change_limit(10)
    f.write("\n")
    objclass_string = ""
    for objclass in ('top', 'person', 'organizationalPerson',
                     'inetOrgPerson', 'eduPerson', 'norEduPerson'):
	objclass_string += "objectClass: %s\n" % objclass
    dn_base = cereconf.LDAP_BASE
    dn_string = get_tree_dn('PERSON')
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
			include_quarantines=True, include_mail=email_enable):
	name,entity_name,ou_id,affili,status = row['name'],row['entity_name'],\
			row['ou_id'],row['affiliation'],int(row['status'])
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
	    print_phaddr = True
	if print_person:
	    person.clear()
	    person.entity_id = row['person_id']
	    pers_string = "dn: uid=%s,%s\n" % (entity_name,dn_string)
	    pers_string += "%s" % objclass_string
  	    utf_name = some2utf(name)
	    pers_string += "cn: %s\n" % utf_name
	    if row['birth_date']:
		pers_string += "norEduPersonBirthDate: %s\n" % (
                    time.strftime("%Y%m%d",
                                  time.strptime(str(row['birth_date']),
                                                "%Y-%m-%d %H:%M:%S.00")))
	    pers_string += ("norEduPersonNIN: %s\n"
                            % re.sub(r'\D', '', row['external_id']))
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
                prim_org = ""
	    if prim_org.find(cereconf.LDAP_ORG_DN) == -1:
		prim_org = "ou=%s,%s" % (cereconf.LDAP_NON_ROOT_ATTR,
                                         get_tree_dn('ORG'))
	    pers_string += "eduPersonPrimaryOrgUnitDN: %s\n" % prim_org
	    org_printed = []
	    pers_string += "eduPersonOrgUnitDN: %s\n" % prim_org
	    org_printed.append(prim_org)
	    for edu_org in p_affiliations:
		try:
		    org = ou_struct[int(edu_org['ou_id'])][0]
		    if org not in org_printed and \
				(ou_struct[int(edu_org['ou_id'])][5]==None):
			pers_string += "eduPersonOrgUnitDN: %s\n" % org
			org_printed.append(org)
		except: pass
	    pers_string += "eduPersonPrincipalName: %s@%s\n" % (
                entity_name, cereconf.INSTITUTION_DOMAIN_NAME)
	    lastname = name
	    for sys in cereconf.SYSTEM_LOOKUP_ORDER:
		try:
		    pers_string += "givenName: %s\n" % \
			some2utf(person.get_name(getattr(co,sys),co.name_first))
		    lastname = person.get_name(getattr(co,sys),co.name_last)
		    break
		except:
		    pass
	    if email_enable:
	    	if row['local_part'] and row['domain']:
		    domain = row['domain']
		    if email_domains and email_domains.has_key(domain):
			pers_string += "mail: %s@%s\n" % (row['local_part'],
							email_domains[domain])
		    else:
			pers_string += "mail: %s@%s\n" % (row['local_part'],
									domain)
	    else:
		pers_string += "mail: %s\n" % person.get_contact_info(source=None,
							type=co.contact_email)
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
		    pers_string += "postalAddress: %s\n" % post_string
		if ((row['address_text']) or (row['postal_number'])):
		    street_string = make_address(", ",
					None,
					row['address_text'],
					row['postal_number'],
					row['city'],
					row['country'])
		    pers_string += "street: %s\n" % street_string
		if row['personal_title']:
		    pers_string += "title: %s\n" % \
				some2utf(row['personal_title'])
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
                    if (affili_str.find(affili_em) == -1):
                        pers_string += "eduPersonAffiliation: %s\n" % affili_em
			affili_str += affili_em
		    if (affi['status'] == co.affiliation_status_ansatt_tekadm
                        and affili_str.find('staff') == -1):
			pers_string += "eduPersonAffiliation: staff\n"
			affili_str += 'staff' 
		    if (affi['status'] == co.affiliation_status_ansatt_vit
                        and affili_str.find('faculty') == -1):
			pers_string += "eduPersonAffiliation: faculty\n"
			affili_str += 'faculty'
                if (int(affi['affiliation']) == int(co.affiliation_student)):
                    if (affili_str.find(affili_stu) == -1):
                        pers_string +="eduPersonAffiliation: %s\n" % affili_stu
                        affili_str += affili_stu
	    pers_string += "uid: %s\n" % entity_name
	    passwd = (row['auth_data'] or row['auth_crypt'])
	    if row['quarantine_type'] is not None:
                qh = QuarantineHandler.QuarantineHandler(Cerebrum, 
                                                    [row['quarantine_type']])
                if qh.should_skip():
                    continue
                if qh.is_locked():
                    passwd = '*Locked'
            pers_string += "userPassword: {crypt}%s\n" % (passwd or '*Invalid')

	    #if aci_person  and (int(person.entity_id)  not in aci_empl_gr):
	    if aci_person  and not aci_empl_gr.has_key(int(person.entity_id)):
		pers_string += "%s\n" % cereconf.LDAP_PERSON_ACI
	    elif (aci_student_gr.has_key(int(person.entity_id))) and \
							not aci_person:
		pers_string += "%s\n" % cereconf.LDAP_PERSON_ACI
	    alias_list[int(person.entity_id)] = entity_name, prim_org,\
							name, lastname
	    f.write("\n")
	    f.write(pers_string)
	else:
	    pass
    f.close()

def generate_alias(filename=None):
    person = Factory.get('Person')(Cerebrum)
    dn_string = get_tree_dn('PERSON')
    if filename:
	f = file(filename,'a')
    else:
	f = SimilarSizeWriter(cereconf.LDAP_DUMP_DIR + '/' +
                              cereconf.LDAP_ALIAS_FILE, 'w')
	f.set_size_change_limit(10)
    f.write("\n")
    obj_string = "".join(["\nobjectClass: %s" % oc for oc in
                          ('top', 'alias', 'extensibleObject')])
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
	    alias_str += "\naliasedObjectName: uid=%s,%s" % (entity_name,
								dn_string)
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
    for hd in disk.list(spread=spreads[0]):
	disks[int(hd['disk_id'])] = hd['path']  
    posix_dn = "," + get_tree_dn('USER')
    obj_string = "".join(["objectClass: %s\n" % oc for oc in
                          ('top', 'account', 'posixAccount')])
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
            if row['disk_id']:
                home = "%s/%s" % (disks[int(row['disk_id'])],uname)
            elif row['home']:
                home = row['home']
	    else:
                continue
            if acc_id <> prev_userid:
                f.write('dn: uid=%s%s\n' % (uname, posix_dn))
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


def generate_posixgroup(spread=None,u_spread=None,filename=None):
    posix_group = PosixGroup.PosixGroup(Cerebrum)
    group = Factory.get('Group')(Cerebrum)
    if spread: spreads = eval_spread_codes(spread)
    else: spreads = eval_spread_codes(cereconf.LDAP_GROUP_SPREAD)
    if u_spread: u_spreads = eval_spread_codes(u_spread)
    else: u_spreads = eval_spread_codes(cereconf.LDAP_USER_SPREAD)
    if filename:
	f = file(filename, 'w')
    else:
	f = SimilarSizeWriter(cereconf.LDAP_DUMP_DIR + '/' +
                              cereconf.LDAP_GROUP_FILE, 'w')
	f.set_size_change_limit(10)
    groups = {}
    dn_str = get_tree_dn('GROUP')
    obj_str = "".join(["objectClass: %s\n" % oc for oc in
                       ('top', 'posixGroup')])
    for row in posix_group.list_all_grp(spreads):
	posix_group.clear()
        posix_group.find(row.group_id)
        gname = posix_group.group_name
        pos_grp = "dn: cn=%s,%s\n" % (gname, dn_str)
        pos_grp += "%s" % obj_str
        pos_grp += "cn: %s\n" % gname
        pos_grp += "gidNumber: %s\n" % posix_group.posix_gid
        if posix_group.description:
            # latin1_to_iso646_60 later
            pos_grp += "description: %s\n" % some2utf(posix_group.description)
	group.clear()
        group.find(row.group_id)
        # Since get_members only support single user spread, spread is
        # set to [0]
        for id in group.get_members(spread=u_spreads[0], get_entity_name=True):
            uname_id = int(id[0])
            if not entity2uname.has_key(uname_id):
                entity2uname[uname_id] = id[1]
            pos_grp += "memberUid: %s\n" % entity2uname[uname_id]
	f.write("\n")
        f.write(pos_grp)
    f.write("\n")
    f.close()

def generate_netgroup(spread=None,u_spread=None,filename=None):
    global grp_memb
    pos_netgrp = Factory.get('Group')(Cerebrum)
    if filename:
        f = file(filename, 'w')
    else:
        f = SimilarSizeWriter(cereconf.LDAP_DUMP_DIR + '/' +
                              cereconf.LDAP_NETGROUP_FILE, 'w')
        f.set_size_change_limit(10)
    if spread: spreads = eval_spread_codes(spread)
    else: spreads = eval_spread_codes(cereconf.LDAP_NETGROUP_SPREAD)
    if u_spread: u_spreads = eval_spread_codes(u_spread)
    else: u_spreads = eval_spread_codes(cereconf.LDAP_USER_SPREAD)
    f.write("\n")
    dn_str = get_tree_dn('NETGROUP')
    obj_str = "".join(["objectClass: %s\n" % oc for oc in
                       ('top', 'nisNetGroup')])
    for row in pos_netgrp.list_all_grp(spreads):
	grp_memb = {}
        pos_netgrp.clear()
        pos_netgrp.find(row.group_id)
        netgrp_name = pos_netgrp.group_name
        netgrp_str = "dn: cn=%s,%s\n" % (netgrp_name, dn_str)
        netgrp_str += "%s" % obj_str
        netgrp_str += "cn: %s\n" % netgrp_name
        if not entity2uname.has_key(int(row.group_id)):
            entity2uname[int(row.group_id)] = netgrp_name
        if pos_netgrp.description:
            netgrp_str += "description: %s\n" % \
                          latin1_to_iso646_60(pos_netgrp.description)
        f.write(netgrp_str)
        get_netgrp(int(row.group_id), spreads, u_spreads, f)
        f.write("\n")
    f.close()

def get_netgrp(netgrp_id, spreads, u_spreads, f):
    pos_netgrp = Factory.get('Group')(Cerebrum)
    pos_netgrp.clear()
    pos_netgrp.entity_id = int(netgrp_id)
    for id in pos_netgrp.list_members(u_spreads[0], int(co.entity_account),\
						get_entity_name= True)[0]:
        uname_id,uname = int(id[1]),id[2]
        if ('_' not in uname) and not grp_memb.has_key(uname_id):
            f.write("nisNetgroupTriple: (,%s,)\n" % uname)
            grp_memb[uname_id] = True
    for group in pos_netgrp.list_members(None, int(co.entity_group),
						get_entity_name=True)[0]:
        pos_netgrp.clear()
        pos_netgrp.entity_id = int(group[1])
	if True in ([pos_netgrp.has_spread(x) for x in spreads]):
            f.write("memberNisNetgroup: %s\n" % group[2])
        else:
            get_netgrp(int(group[1]), spreads, u_spreads, f)


def eval_spread_codes(spread):
    spreads = []
    if isinstance(spread,(str,int)):
        if (spread_code(spread)):
            spreads.append(spread_code(spread))
    elif isinstance(spread,(list,tuple)):
        for entry in spread:
            if (spread_code(entry)):
                spreads.append(spread_code(entry))
    else:
        spreads = None
    return(spreads)


def spread_code(spr_str):
    spread=""
    #if isinstance(spr_str, _SpreadCode):
    #    return int(_SpreadCode(spr_str))
    try: spread = int(spr_str)
    except:
	try: spread = int(getattr(co, spr_str))
        except: 
	    try: spread = int(_SpreadCode(spr_str)) 
	    except:
		print "Not valid Spread-Code"
		spread = None
    return(spread)


ou_rdn_re = re.compile(r'[,+\\ ]+')

def make_ou_for_rdn(ou):
    return ou_rdn_re.sub(' ', ou).strip()


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
		    ph = re.sub(r'\s','',normalize_phone(ph))
		if ph:
		    if cont_tab.has_key(key):
			if ph not in cont_tab[key]: cont_tab[key].append(ph)
		    else: cont_tab[key] = [ph,]
    if ((len(cont_tab) == 1) or entity_id):
	for k,v in cont_tab.items():
	    return(v)
    else:
	return(cont_tab)


def disable_ldapsync_mode():
    try:
	ldap_servers = cereconf.LDAP_SERVER
	from Cerebrum.modules import LdapCall
    except AttributeError:
	logger.info('No active LDAP-sync severs configured')
    except ImportError: 
	logger.info('LDAP modules missing. Probably python-LDAP')
    else:
	s_list = LdapCall.ldap_connect()
	LdapCall.add_disable_sync(s_list,disablesync_cn)
	LdapCall.end_session(s_list)
	logg_dir = cereconf.LDAP_DUMP_DIR + '/log'
	if os.path.isdir(logg_dir):  
	    rotate_file = '/'.join((logg_dir,'rotate_ldif.tmp'))
	    if not os.path.isfile(rotate_file):
		f = file(rotate_file,'w')
		f.write(time.strftime("%d %b %Y %H:%M:%S", time.localtime())) 
		f.close()

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'u:g:n:U:G:N:po',
					['help', 'group=','org=','user=',
					'netgroup_spread=', 'group_spread=',
					'user_spread=', 'netgroup=','posix'])
    except getopt.GetoptError:
        usage(1)

    user_spread = group_spread = None
    p = {}
    for opt, val in opts:
	m_val = []
        if opt in ('--help',):
            usage()
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
	elif opt in ('-u', '--user'):
            p['u_file'] = val
	elif opt in ('-g', '--group'):
            p['g_file'] = val
	elif opt in ('-n', '--netgroup'):
            p['n_file'] = val
	elif opt in ('-U','--user_spread'):
	    [m_val.append(str(x)) for x in val.split(',')]
	    p['u_spr'] = eval_spread_codes(m_val)
	elif opt in ('-G','--group_spread',):
	    [m_val.append(str(x)) for x in val.split(',')]
	    p['g_spr'] = eval_spread_codes(m_val)
        elif opt in ('-N','--netgroup_spread',):
	    [m_val.append(str(x)) for x in val.split(',')]
            p['n_spr'] = eval_spread_codes(m_val)
	elif opt in ('--posix',):
	    disable_ldapsync_mode()
            generate_users()
            generate_posixgroup()
            generate_netgroup()
        else:
            usage()
    if len(opts) == 0:
        config()
    if p.has_key('n_file'):
        generate_netgroup(p.get('n_spr'), p.get('u_spr'), p.get('n_file'))
    if p.has_key('g_file'):
        generate_posixgroup(p.get('g_spr'), p.get('u_spr'), p.get('g_file'))
    if p.has_key('u_file'):
        generate_users(p.get('u_spr'), p.get('u_file'))

def usage(exitcode=0):
    print """Usage: [options]

 No option will generate a full dump with default values from cereconf.

  --org=<outfile>
      Write organization, person and alias to a LDIF-file

  --user=<outfile>| -u <outfile> --user_spread=<value>|-U <value>
      Write users to a LDIF-file

  --group=<outfile>| -g <outfile>  --group_spread=<value>|-G <value> -U <value>
      Write posix groups to a LDIF-file

  --netgroup=<outfile>| -n <outfile> --netgroup_spread=<value>|-N <val> -U <val>
      Write netgroup map to a LDIF-file

  --posix
      write all posix-user,-group and -netgroup
      from default cereconf parameters

  Both --user_spread, --netgroup_spread  and --group_spread can handle
  multiple spread-values (<value> | <value1>,<value2>,,,)"""
    sys.exit(exitcode)

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
		generate_person()
	    if (cereconf.LDAP_ALIAS == 'Enable'):
		generate_alias()
	    if (cereconf.LDAP_USER == 'Enable'):
		disable_ldapsync_mode()
		generate_users()
	    if (cereconf.LDAP_GROUP == 'Enable'):
		generate_posixgroup()
	    if (cereconf.LDAP_NETGROUP == 'Enable'):
		generate_netgroup()
	else:
	    pass
	
if __name__ == '__main__':
    	main()

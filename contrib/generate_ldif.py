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
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

import time, re, string, sys, getopt, base64
import cerebrum_path
import cereconf  
from Cerebrum import OU
from Cerebrum import Person
from Cerebrum import Errors
from Cerebrum import Account
from Cerebrum import Group
from Cerebrum import Disk
from Cerebrum import Entity
from string import maketrans
from Cerebrum.Utils import Factory, latin1_to_iso646_60,SimilarSizeWriter
from Cerebrum.modules.no import Stedkode
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup
from Cerebrum import QuarantineHandler
from Cerebrum.Constants import _SpreadCode
#from Cerebrum.modules.no.uio import Constants

Cerebrum = Factory.get('Database')()
co = Factory.get('Constants')(Cerebrum)
ou_struct = {}
entity2uname = {}
affiliation_code = {}
alias_list = {}
org_root = None

normalize_trans = maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ\t\n\r\f\v",
    "abcdefghijklmnopqrstuvwxyz     ")


def load_code_tables():
    person = Person.Person(Cerebrum)
    affili_codes = person.list_person_affiliation_codes()
    for aff in affili_codes:
        affiliation_code[int(Cerebrum.pythonify_data(aff['code']))] = Cerebrum.pythonify_data(aff['code_str'])
    

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
    ou = OU.OU(Cerebrum)
    ou.find(ou_org)
    ou_fax = None
    ou_faxs = ''
    try:
	ou_faxnumber = get_contacts(int(ou_org),int(co.contact_fax))
	for fax in ou_fax_number:
            if verify_printableString(fax):
		init_str += "facsimileTelephoneNumber: %s\n" % fax
		ou_faxs += fax + '$'
    except: pass
    try:
	stedkode = Stedkode.Stedkode(Cerebrum)
	stedkode.find(ou_org)
	stedkodestr = string.join((string.zfill(str(stedkode.fakultet),2), 
			string.zfill(str(stedkode.institutt),2), 
			string.zfill(str(stedkode.avdeling),2)),'')
        init_str += "norInstitutionNumber: %s\n" % stedkodestr
    except:
        pass
    init_str += "l: %s\n" % cereconf.LDAP_BASE_CITY
    for alt in cereconf.LDAP_BASE_ALTERNATIVE_NAME:
	init_str += "o: %s\n" % alt
    post_string = street_string = None
    try:
	post_addr = ou.get_entity_address(None, co.address_post)
	post_addr_str = "%s" % string.replace(string.rstrip(post_addr[0]['address_text']),"\n","$")
        post_string = "%s$%s %s" % (post_addr_str,post_addr[0]['postal_number'],
					post_addr[0]['city'])
        init_str += "postalAddress: %s\n" % post_string
    except: pass
    try:
	street_addr = ou.get_entity_address(None,co.address_street)
        street_addr_str = "%s" % string.replace(string.rstrip(street_addr[0]['address_text']),"\n",", ")
        street_string = "%s, %s %s" %(street_addr_str, street_addr[0]['postal_number'],
							street_addr[0]['city'])
        init_str += "street: %s\n" % street_string
    except:
        pass
    ou_phone = None
    ou_phones = ''
    try:
	phones = get_contacts(int(ou_org),co.contact_phone)
	if phones is not None:
	    for phone in phones:
                if verify_printableString(phone):
		    init_str += "telephoneNumber: %s\n" % phone
		    ou_phones += phone + '$'
    except:
        pass
    try:
        init_str += "labeledURI: %s\n" % cereconf.LDAP_BASE_URL
    except:
        pass
    f.write(init_str)
    f.write("\n")
    try:
    	ou_struct[int(ou.ou_id)]= cereconf.LDAP_BASE,post_string,street_string,ou_phones,ou_faxs
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
    try:
	if cereconf.LDAP_MAN_LDIF_ADD_FILE:
	    lfile = file((string.join(('/usit/cerebellum/u1/areen/cerebrum',cereconf.LDAP_MAN_LDIF_ADD_FILE),'/')),'r')
	    f.write(lfile.read().strip()) 
	    f.write('\n')
	    lfile.close()
    except: pass
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
    ou = OU.OU(Cerebrum)
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
			stedkodestr = string.join((string.zfill(str(stedkode.fakultet),2), 
						string.zfill(str(stedkode.institutt),2), 
						string.zfill(str(stedkode.avdeling),2)),'')
			par_ou = "%s=%s,%s" % (cereconf.LDAP_ORG_ATTR,cereconf.LDAP_NON_ROOT_ATTR,ou_string)
			str_ou = print_OU(non_org, par_ou, stedkodestr, filename)
    
def print_OU(id, par_ou, stedkodestr,par, filename=None):
    ou = OU.OU(Cerebrum)
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
    f.write("\n")
    if ou.acronym:
	ou_dn = make_ou_for_rdn(some2utf(ou.acronym))
    else:
	ou_dn = make_ou_for_rdn(some2utf(ou.short_name))
    str_ou = "%s=%s,%s" % (cereconf.LDAP_ORG_ATTR,ou_dn,par_ou)
    ou_str = "dn: %s\n" % str_ou
    ou_str += "objectClass: top\n"
    for ss in cereconf.LDAP_ORG_OBJECTCLASS:
        ou_str += "objectClass: %s\n" % ss
    try:
	ou_fax_numbers = get_contacts(id, co.contact_fax)
	if ou_fax_numbers is not None:
	    ou_faxs = ''
	    for ou_fax in ou_fax_numbers:
		ou_str += "facsimileTelephoneNumber: %s\n" % ou_fax
		ou_faxs += ou_fax + '$'
    except:  pass
    try: 
	ou_email = get_contacts(id,co.contact_email,email=1)
	if ou_email:
	    for email in ou_email:
		ou_str += "mail: %s\n" % email
    except:  pass
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
    	    if post_addr:
		post_addr_str = "%s" % string.replace(string.rstrip(post_addr[0]['address_text']),"\n","$") 
		if (post_addr[0]['postal_number']) is not None and (post_addr[0]['city']) is not None:
		    if int(post_addr[0]['postal_number']) >> 0:
			post_string = "%s$%s %s" % (post_addr_str,
						string.zfill((post_addr[0]['postal_number']),4),
						post_addr[0]['city'])
		    else:
			post_string = "%s$%s" % (post_addr_str,post_addr[0]['city'])
		if (post_addr[0]['country']):
		    post_string += '$' + (post_addr[0]['country'])
		ou_str += "postalAddress: %s\n" % some2utf(post_string)
		break
	except: pass
    for dd in cereconf.SYSTEM_LOOKUP_ORDER:
	try:
            street_addr = ou.get_entity_address(int(getattr(co, dd)), co.address_street)
            if street_addr:
		street_addr_str = "%s" % string.replace(string.rstrip(street_addr[0]['address_text']),"\n",", ")
		if (street_addr[0]['postal_number']) and (street_addr[0]['city']):
		    if int(street_addr[0]['postal_number']) > 0:
		    	street_string = "%s, %s %s" %(street_addr_str, 
							string.zfill((street_addr[0]['postal_number']),4),
							street_addr[0]['city'])
		    else:
			street_string = "%s, %s" %(street_addr_str,street_addr[0]['city'])
		if street_addr[0]['country']:
		    street_string += ', ' + street_addr[0]['country']
		ou_str += "street: %s\n" % some2utf(street_string)
                break
	except: pass
    try:
	ou_phnumber = get_contacts(ou.ou_id, co.contact_phone)
	ou_phones = ''
	for phone in ou_phnumber:
            if verify_printableString(phone):
	        ou_str += "telephoneNumber: %s\n" % phone
	        ou_phones += phone + '$'
    except: pass
    if par:
	ou_struct[int(id)]= str_ou,post_string,street_string,ou_phones,ou_faxs,int(par)
	f.close()
	return par_ou
    else:
	ou_struct[int(id)]= str_ou,post_string,street_string,ou_phones,ou_faxs,None
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
		stedkodestr = string.join((string.zfill(str(stedkode.fakultet),2),
                                                string.zfill(str(stedkode.institutt),2),
                                                string.zfill(str(stedkode.avdeling),2)),'')
 	   	if stedkode.katalog_merke == 'T':
            	    str_ou = print_OU(c,par_ou,stedkodestr,None,filename)
            	    trav_list(c,ou_list,str_ou,filename)
    	    	else:
		    dummy = print_OU(c,par_ou,stedkodestr,p,filename)
		    trav_list(c,ou_list,par_ou,filename)
	    except:
		ou_struct[str(c)] = par_ou
		str_ou = print_OU(c,par_ou,None,filename)
		trav_list(c,ou_list,str_ou,filename)

def generate_person(filename=None):
    person = Person.Person(Cerebrum)
    group = Group.Group(Cerebrum)
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
    aci_empl_gr = valid_print_affi = []
    aci_student_gr = {}
    try: 
	for status in cereconf.LDAP_PERSON_LIST_AFFI:
	    valid_print_affi.append(int(getattr(co,status)))
    except: pass
    try:
	group.find_by_name(str(cereconf.PERSON_NOT_PUBLIC_GR))
	for entries in group.list_members(member_type=co.entity_person)[0]:
	    aci_empl_gr.append(entries[1])
    except: pass
    group.clear()
    try: 
	group.find_by_name(str(cereconf.PERSON_PUBLIC_GR))
	for entries in group.list_members(member_type=co.entity_person)[0]:
	    aci_student_gr[int(entries[1])] = '1'
    except Errors.NotFoundError: pass
    try:  person_spread = int(getattr(co,cereconf.PERSON_SPREAD))
    except:  pass
    try:  acl_spread = int(cereconf.LDAP_PERSON_ACL_SPREAD) 
    except:  pass
    try:
	email_domains = {}  
	email_domains = cereconf.LDAP_REWRITE_EMAIL_DOMAIN
    except: pass
    affili_stu = "student"
    affili_em = "employee"
    for row in person.list_extended_person(person_spread, include_quarantines=1):
	name,entity_name,ou_id,affili,status = row['name'],row['entity_name'],row['ou_id'],row['affiliation'],int(row['status'])
	person.clear()
        person.entity_id = row['person_id']
	p_affiliations = person.get_affiliations()
	aci_person = print_person = 'F'
	for pr_status in p_affiliations:
	    if (int(pr_status['status'])) in valid_print_affi:
		print_person = 'T'
		if (int(pr_status['affiliation']) == int(co.affiliation_ansatt)):
		    aci_person = 'T' 
		    break
	if print_person == 'T':
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
	    if row['local_part'] and row['domain']:
		domain = row['domain']
		if email_domains and email_domains.has_key(domain):
		    pers_string += "mail: %s@%s\n" % (row['local_part'],email_domains[domain])
		else:
		    pers_string += "mail: %s@%s\n" % (row['local_part'],domain)
	    if lastname:
		pers_string += "sn: %s\n" % some2utf(lastname)
	    if (int(affili) == int(co.affiliation_ansatt)): 
		try:
		    if ou_struct[int(ou_id)][1]:
			pers_string += "postalAddress: %s\n" % some2utf(ou_struct[int(ou_id)][1])
		    if ou_struct[int(ou_id)][2]:
			pers_string += "street: %s\n" % some2utf(ou_struct[int(ou_id)][2])
		except: pass
		#pers_string += "title: "
		if row['contact_value']:
		    phone_str = []
		    for phones in string.split(row['contact_value'],'$'):
 	               if verify_printableString(phones):
			    phone_nr = normalize_phone(phones)
			    if phone_nr not in phone_str: 
		    	        pers_string += "telephoneNumber: %s\n" % phones
			        phone_str.append(phone_nr)
		faxes = []
		if row['fax']:
		    for fax in string.split(row['fax'],'$'):
 	               if verify_printableString(fax):
			    fax_n = normalize_phone(fax)
			    if fax_n not in faxes:
			    	pers_string += "facsimileTelephoneNumber: %s\n" % fax
				faxes.append(fax_n)
		else:
		    try:
			for fax in string.split(ou_struct[int(ou_id)][4],'$'):
			    if fax is not '':
			    	pers_string += "facsimileTelephoneNumber: %s\n" % fax
		    except: pass
	    affili_str = str('')
	    for affi in p_affiliations:
                if (int(affi['affiliation']) == int(co.affiliation_ansatt)):
                    if (string.find(affili_str,affili_em) == -1):
                        pers_string += "eduPersonAffiliation: %s\n" % affili_em
			if row['status'] == co.affiliation_status_ansatt_tekadm:
			    pers_string += "eduPersonAffiliation: staff\n" 
			elif row['status'] == co.affiliation_status_ansatt_vit:
			    pers_string += "eduPersonAffiliation: faculty\n"
                        affili_str += affili_em
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
	    if (aci_person == 'T') and (int(person.entity_id)  not in aci_empl_gr):
		pers_string += "%s\n" % cereconf.LDAP_PERSON_ACL
	    elif  aci_student_gr.has_key(int(person.entity_id)): # (aci_student_gr[int(person.entity_id)]):
		pers_string += "%s\n" % cereconf.LDAP_PERSON_ACL
	    alias_list[int(person.entity_id)] = entity_name,prim_org,name,lastname
	    f.write("\n")
	    f.write(pers_string)
	else:
	    pass
    f.close()

def generate_alias(filename=None):
    person = Person.Person(Cerebrum)
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
    shells = disks = {}
    prev_userid = 0
    posix_user = PosixUser.PosixUser(Cerebrum)
    posix_group = PosixGroup.PosixGroup(Cerebrum)
    disk = Disk.Disk(Cerebrum)
    spreads = []
    if spread:
	#for entry in spread:
 	    spreads.append(int(spread))
    else:
	for entry in cereconf.LDAP_USER_SPREAD:
	    spreads.append(int(getattr(co,entry)))
    for sh in posix_user.list_shells():
	shells[int(sh['code'])] = sh['shell']
    for hd in disk.list():
	disks[int(hd['disk_id'])] = hd['path']  
    posix_dn = ",%s=%s,%s" % (cereconf.LDAP_ORG_ATTR,cereconf.LDAP_USER_DN,cereconf.LDAP_BASE)
    posix_dn_string = "%s=" % cereconf.LDAP_USER_ATTR
    obj_string = "objectClass: top\n"
    for obj in cereconf.LDAP_USER_OBJECTCLASS:
	obj_string += "objectClass: %s\n" % obj
    if filename: 
	f = file(filename, 'w')
    else: 
	f = SimilarSizeWriter(string.join((cereconf.LDAP_DUMP_DIR,cereconf.LDAP_USER_FILE),'/'), 'w')
	f.set_size_change_limit(10)
    pos_user = posix_user.list_extended_posix_users_test(getattr(co,'auth_type_md5_crypt'),
								spreads,include_quarantines=1)
    f.write("\n")
    for row in pos_user:
	acc_id,shell,gecos,uname = row['account_id'],row['shell'],row['gecos'],row['entity_name']
	entity2uname[int(acc_id)] = uname
	if not row['auth_data']:
	    passwd = '{crypt}*Invalid'
	else:
	    passwd = "{crypt}%s" % row['auth_data']
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
        shell = shells[int(shell)]
	if row['quarantine_type'] is not None:
	    qh = QuarantineHandler.QuarantineHandler(Cerebrum, [row['quarantine_type']])
            if qh.should_skip():
                continue
            if qh.is_locked():
                passwd = '{crypt}*Locked'
            qshell = qh.get_shell()
            if qshell is not None:
                shell = qshell
	posix_text = """
dn: %s%s%s
%scn: %s
uid: %s
uidNumber: %s
gidNumber: %s
homeDirectory: %s
userPassword: %s
loginShell: %s
gecos: %s\n""" % (posix_dn_string, uname, posix_dn, obj_string, gecos, 
		uname,str(row['posix_uid']), str(row['posix_gid']),
		home, passwd,shell, gecos)
	if int(acc_id) <> prev_userid:
	    f.write(posix_text)
	prev_userid = int(acc_id)
    f.close()

def generate_posixgroup():
    spreads = []
    for spread in cereconf.LDAP_GROUP_SPREAD:
	spreads.append(int(getattr(co,spread)))
    generate_group(spreads)

def generate_group(spread=None, filename=None):
    posix_group = PosixGroup.PosixGroup(Cerebrum)
    group = Group.Group(Cerebrum)
    pos_usr = PosixUser.PosixUser(Cerebrum)
    user_spread = int(getattr(co,cereconf.LDAP_USER_SPREAD[0]))
    if filename:
	f = file(filename, 'w')
    else:
	f = SimilarSizeWriter(string.join((cereconf.LDAP_DUMP_DIR,cereconf.LDAP_GROUP_FILE),'/'), 'w')
	f.set_size_change_limit(10)
    f.write("\n")
    groups = {}
    dn_str = "%s=%s,%s" % (cereconf.LDAP_ORG_ATTR,cereconf.LDAP_GROUP_DN,cereconf.LDAP_BASE)
    obj_str = "objectClass: top\n"
    for obj in cereconf.LDAP_GROUP_OBJECTCLASS:
	obj_str += "objectClass: %s\n" % obj
    for row in posix_group.list_all_test(spread):
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
	    for id in group.get_members(spread=int(user_spread)):
		uname_id = int(Cerebrum.pythonify_data(id))
		if entity2uname.has_key(uname_id):
		    pos_grp += "memberUid: %s\n" % entity2uname[uname_id]
		else:
		    print "ID ikke funnet i tab: %s" % uname_id
 		    posix_group.clear()
		    posix_group.entity_id = uname_id
		    mem_name = posix_group.get_name(co.account_namespace)
		    entity2uname[int(uname_id)] = mem_name
		    pos_grp += "memberUid: %s\n" % mem_name
	    f.write("\n")
            f.write(pos_grp)
	except:  pass
    f.close()


def generate_netgroup(spread=None, filename=None):
    pos_netgrp = Group.Group(Cerebrum) 
    posix_user = PosixUser.PosixUser(Cerebrum)
    if filename:
        f = file(filename, 'w')
    else:
        f = SimilarSizeWriter(string.join((cereconf.LDAP_DUMP_DIR,cereconf.LDAP_NETGROUP_FILE),'/'), 'w')
	f.set_size_change_limit(10)
    spreads = []
    if spread:
	spreads.append(int(getattr(co,spread)))
    else:
	for spread in cereconf.LDAP_NETGROUP_SPREAD:
	    spreads.append(int(getattr(co,spread)))
    f.write("\n")
    dn_str = "%s=%s,%s" % (cereconf.LDAP_ORG_ATTR,cereconf.LDAP_NETGROUP_DN,cereconf.LDAP_BASE)
    obj_str = "objectClass: top\n"
    for obj in cereconf.LDAP_NETGROUP_OBJECTCLASS:
        obj_str += "objectClass: %s\n" % obj
    for row in pos_netgrp.list_all_test(spreads):
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
	    members = []
	    hosts = []
	    groups = []
	    members = pos_netgrp.list_members(None,int(co.entity_account))[0]
#	    hosts = pos_netgrp.list_members(None,int(co.entity_host))[0]
	    groups = pos_netgrp.list_members(None,int(co.entity_group))[0]
	    for id in members:
                uname_id = int(id[1])
                if entity2uname.has_key(uname_id):
		    netgrp_str += "nisNetgroupTriple: (,%s,)\n" % entity2uname[uname_id].replace('_','')
                else:
                    pos_netgrp.clear()
                    pos_netgrp.entity_id = uname_id
		    netgrp_str += "nisNetgroupTriple: (,%s,)\n" % entity2uname[uname_id].replace('_','')
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

def iso2utf(s):
     utf_str = unicode(s,'iso-8859-1').encode('utf-8')
     return utf_str

def utf2iso(s):
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

def get_contacts(id,contact_type,email=0):
    """ Process infomation in entity_contact_info into a list.
        Splits string in to entities, nomalize and remove duplicats"""
    entity = Entity.EntityContactInfo(Cerebrum)
    entity.clear()
    entity.entity_id = int(id)
    list_contact_entry = []
    contact_entries = entity.get_contact_info(None, int(contact_type))
    if len(contact_entries) == 1:
    	for contact in string.split((Cerebrum.pythonify_data(contact_entries[0]['contact_value'])),'$'):
	    if normalize_phone(contact) not in list_contact_entry and email == 0:
		list_contact_entry.append(normalize_phone(contact))
	    elif contact not in list_contact_entry and email == 1:
		list_contact_entry.append(contact)  
    elif len(contact_entries) >> 1:
	for contact_entry in contact_entries:
	    for contact in  string.split((Cerebrum.pythonify_data(contact_entry['contact_value'])),'$'):
		if normalize_phone(contact) not in list_contact_entry and email == 0:
                    list_contact_entry.append(normalize_phone(contact))
		elif contact not in list_contact_entry and email == 1:
		     list_contact_entry.append(contact)
    else:
	list_contact_entry = None
    return(list_contact_entry)
	

def unique(values, normalize):
    """Return the unique values in VALUES, compared after doing NORMALIZE"""
    done = {}
    ret = []
    for val in values:
        norm = normalize(val)
        if not done.has_key(norm):
            done[norm] = 1
            ret.append(val)
    return ret

need_b64_re = re.compile('^\\s|[\0\r\n]|\\s$')

def print_string_attr(name, strings, normalize):
    strings = unique(strings, normalize)
    for str in strings:
        str = str.strip()
        while str.find('  ') >= 0:
            str = str.replace('  ', ' ')
        if str == '':
            str = ' '
        str = unicode(str, 'iso-8859-1').encode('utf-8')
        if re.match(need_b64_re, str):
            print "%s:: %s" % (name, (base64.encodestring(str).replace("\n", '')))
        else:
            print "%s: %s" % (name, str)

def main():
    global debug
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
	    #generate_posixgroup()
	    generate_group(group_spread, val)
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
    --netgroup outfile
      Write netgroup map to a LDIF-file
    --posix 
      write all posix-user,-group and -netgroup from default ldapconf parameters

    Generates a ldif-file of the requested type for the requested spreads."""
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

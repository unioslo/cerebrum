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
from Cerebrum import QuarantineHandler
from Cerebrum.Constants import _SpreadCode
from Cerebrum.modules.LDIFutils import *
from time import time as now

db = Factory.get('Database')()
co = Factory.get('Constants')(db)

logging.fileConfig(cereconf.LOGGING_CONFIGFILE)
logger = logging.getLogger("cronjob")

ou_struct = {}
affiliation_code = {}
alias_list = {}
org_root = None
global dn_dict
dn_dict = {}


def load_code_tables():
    global ph_tab, fax_tab
    ph_tab = {}
    fax_tab = {}
    person = Factory.get('Person')(db)
    affili_codes = person.list_person_affiliation_codes()
    for aff in affili_codes:
        affiliation_code[int(db.pythonify_data(aff['code']))] = \
				db.pythonify_data(aff['code_str'])
    ph_tab = get_contacts(source_system=int(
        getattr(co,cereconf.LDAP_SOURCE_SYSTEM)),\
                          contact_type=int(co.contact_phone))
    fax_tab = get_contacts(source_system=int(
        getattr(co,cereconf.LDAP_SOURCE_SYSTEM)),\
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


def init_ldap_dump(ou_org):
    attrs = {
        'norEduOrgUniqueNumber': ("%08d" % cereconf.DEFAULT_INSTITUSJONSNR,) }
    ou = Factory.get('OU')(db)
    ou.find(ou_org)
    if fax_tab.has_key(int(ou_org)):
        attrs['facsimileTelephoneNumber'] = fax_tab[int(ou_org)]
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
            attrs['postalAddress'] = (post_string,)
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
            attrs['street'] = (street_string,)
    if ph_tab.has_key(int(ou_org)):
        attrs['telephoneNumber'] = ph_tab[int(ou_org)]
    attrs.update(cereconf2utf('LDAP_BASE_ATTRS', {}))
    ocs  = ['top', 'organization', 'eduOrg', 'norEduOrg']
    ocs += [oc for oc in attrs.get('objectClass', ()) if oc not in ocs]
    attrs['objectClass'] = ocs
    if attrs.get('labeledURI'):
        attrs.setdefault('eduOrgHomePageURI', attrs['labeledURI'])

    glob_fd.write("\n")
    glob_fd.write(entry_string(cereconf.LDAP_BASE, attrs))

    ou_struct[int(ou.ou_id)] = (cereconf.LDAP_BASE, post_string,
                                street_string, None, None, None)

    add_ldif_file(glob_fd, getattr(cereconf, 'LDAP_ORG_ADD_LDIF_FILE', None))


def root_OU():
    ou = Factory.get('OU')(db)
    root_id=ou.root()
    if len(root_id) > 1:
	text1 = """
You have %d roots in your organization-tree. Cerebrum only support 1.\n""" % \
								(len(root_id))
        sys.stdout.write(text1)
    	for p in root_id:
            root_org = db.pythonify_data(p['ou_id'])
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
	root_org = db.pythonify_data(root_id[0]['ou_id'])	
	return(root_org)


def generate_org(ou_id):
    glob_fd.write(container_entry_string('ORG'))

    stedkode = Stedkode.Stedkode(db)
    if True:
	stedkode.find(ou_id)
	stedkodestr = "%02d%02d%02d" % (stedkode.fakultet,
                                        stedkode.institutt,
                                        stedkode.avdeling)
        attrs = {
            'objectClass': ('top', 'organizationalUnit', 'norEduOrgUnit'),
            'norEduOrgUnitUniqueNumber': (stedkodestr,),
            'norEduOrgUniqueNumber':("%08d" % cereconf.DEFAULT_INSTITUSJONSNR,)
            }
        attrs.update(cereconf2utf('LDAP_NON_ROOT_ATTRS', {}))
        non_root_dn = "ou=%s,%s" % (cereconf.LDAP_NON_ROOT_ATTR,
                                    get_tree_dn('ORG'))
	glob_fd.write(entry_string(non_root_dn, attrs))

    ou = Factory.get('OU')(db)
    ou_list = ou.get_structure_mappings(getattr(co,cereconf.LDAP_PERSPECTIVE))
    logger.debug("OU-list length: %d", len(ou_list))
    trav_list(ou_id, ou_list, get_tree_dn('ORG'))
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
			dummy = print_OU(non_org, non_root_dn, stedkodestr)

def print_OU(id, par_ou, stedkodestr, par):
    ou = Factory.get('OU')(db)
    ou.clear()
    ou.find(id)
    street_string = None
    post_string = None
    ou_phones = ou_faxs = ''
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
               % cereconf.DEFAULT_INSTITUSJONSNR)
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
	return par_ou
    else:
	ou_struct[int(id)] = (str_ou, post_string, street_string,
                              ou_phones, ou_faxs, None)
    	glob_fd.write(ou_str)
        glob_fd.write("\n")
    	return str_ou

def trav_list(par, ou_list, par_ou):
    stedkode = Stedkode.Stedkode(db)
    for c,p in ou_list:
	# Check if it is child of parent and not cyclic
	if (p == par) and (c <> par):
	    stedkode.clear()
	    try:
		stedkode.find(c)
	    except:
		ou_struct[str(c)] = par_ou
		str_ou = print_OU(c, par_ou, None)
		trav_list(c, ou_list, str_ou)
            else:
		stedkodestr = "%02d%02d%02d" % (stedkode.fakultet,
                                                stedkode.institutt,
                                                stedkode.avdeling)
 	   	if stedkode.katalog_merke == 'T':
            	    str_ou = print_OU(c, par_ou, stedkodestr, None)
            	    trav_list(c, ou_list, str_ou)
    	    	else:
		    dummy = print_OU(c, par_ou, stedkodestr, p)
		    trav_list(c, ou_list, par_ou)


def generate_person():
    glob_fd.write(container_entry_string('PERSON'))

    person = Factory.get('Person')(db)
    group = Factory.get('Group')(db)
    account = Factory.get('Account')(db)
    objclass_string = ""
    for objclass in ('top', 'person', 'organizationalPerson',
                     'inetOrgPerson', 'eduPerson', 'norEduPerson'):
	objclass_string += "objectClass: %s\n" % objclass

    if mail_module:
        # We don't want to import this if mod_email isn't present.
        from Cerebrum.modules import Email

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

    # Make dict with all affiliations.
    logger.debug("Starting person.list_affiliations().")
    start = now()
    affiliations = {}
    for row in person.list_affiliations():
        # 'affiliation', 'source_system', 'status', 'ou_id'
        dict = {}
        for x in ('affiliation', 'source_system', 'status', 'ou_id'):
            dict[x] = row[x]
        affiliations.setdefault(int(row['person_id']),
                                []).append(dict)
    logger.debug("person.list_affiliations() done in '%d' secs.", now()-start)

    # Make dict with all contacts.
    logger.debug("Starting person.list_contact_info().")
    start = now()
    contact_info = {}
    for row in person.list_contact_info(entity_type=co.entity_person):
        if not contact_info.has_key(int(row['entity_id'])):
            contact_info[int(row['entity_id'])] = {}
        contact_info[int(row['entity_id'])][row['contact_type']] = row['contact_value']
    logger.debug("person.list_contact_info() done in '%d' secs.", now()-start)

    # Make dict with all person_names.
    logger.debug("Starting person.list_names_info().")
    start = now()
    person_names = {}
    for row in person.list_persons_name(source_system=co.system_cached,
                                        name_type=[co.name_full,
                                                   co.name_first,
                                                   co.name_last]):
        if not person_names.has_key(int(row['person_id'])):
            person_names[int(row['person_id'])] = {}
        person_names[int(row['person_id'])][int(row['name_variant'])] = row['name']
    logger.debug("person.list_names() done in '%d' secs.", now()-start)

    # Make dict with all person_names2.
    logger.debug("Starting person.list_names_info2().")
    start = now()
    person_title = {}
    for row in person.list_persons_name(name_type=[co.name_personal_title,
						   co.name_work_title]):
        if not person_title.has_key(int(row['person_id'])):
            person_title[int(row['person_id'])] = {}
        person_title[int(row['person_id'])][int(row['name_variant'])] = row['name']
    logger.debug("person.list_names2() done in '%d' secs.", now()-start)

    # Iff Make dict with all email-addresses.
    if mail_module:
        et = Email.EmailTarget(db)
        logger.debug("Starting et.list_email_target_primary_addresses().")
        start = now()
        mail_addresses = {}
        for row in et.list_email_target_primary_addresses(target_type=\
                                                          co.email_target_account):
            if row['entity_id']:
                # TBD: Should we check for multiple values for primary
                #      addresses?
                mail_addresses[int(row['entity_id'])] = [row['local_part'],
                                                         row['domain']]
            else:
                logger.warn("email_target: '%d' got no user.", int(row['target_id']))
        logger.debug("et.list_email_target_primary_addresses() done in '%d' secs.",
                     now()-start)
    else:
        logger.debug("Mail-module skipped.")

    # Make dict with all auth-data.
    logger.debug("Starting account.list_account_authentication().")
    start = now()
    acc_info = {}
    auth_info = {}
    for row in account.list_account_authentication(auth_type=[co.auth_type_md5_crypt,
                                                              co.auth_type_crypt3_des]):
        acc_info[int(row['account_id'])] = row['entity_name']            
        if not auth_info.has_key(int(row['account_id'])):
            auth_info[int(row['account_id'])] = {}
        if row['method']:
            auth_info[int(row['account_id'])][int(row['method'])] = row['auth_data']
    logger.debug("account.list_account_authentication() done in '%d' secs.",
                 now()-start)

    # Make dict with all entity_address.
    logger.debug("Starting person.list_entity_addresses().")
    start = now()
    addr_info = {}
    for row in person.list_entity_addresses(\
        entity_type=co.entity_person,
        source_system=getattr(co,cereconf.LDAP_SOURCE_SYSTEM),
        address_type=[co.address_street, co.address_post]):
        if not addr_info.has_key(int(row['entity_id'])):
            addr_info[int(row['entity_id'])] = {}
        addr_info[int(row['entity_id'])][int(row['address_type'])] = (
            row['address_text'], row['p_o_box'], row['postal_number'],
            row['city'], row['country'])
    logger.debug("person.list_entity_addresses() done in '%d' secs.",
                 now()-start)
    


    # Start iterating over people:    
    logger.debug("Starting person.list_extended_person().")
    round = 0
    start = now()
    cur = now()
    for row in person.list_persons_atype_extid(person_spread,
                                               include_quarantines=True):
        if round % 10000 == 0:
            logger.debug("Rounded '%d' rows in '%d' secs.", round, now()-cur)
            cur = now()

        round += 1
        person_id, account_id, ou_id = row['person_id'], row['account_id'],\
                                       row['ou_id']
                                                       
        if affiliations.has_key(person_id):
            p_affiliations = affiliations[person_id]
        else:
            logger.warn("Person %s got no affiliations. Skipping.", person_id)
            continue
        if acc_info.has_key(account_id):
            uname = acc_info[account_id]
        else:
            logger.warn("Person %s got no account. Skipping.", person_id)
            continue
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
	if not print_person: continue
        
        pers_string = "dn: uid=%s,%s\n" % (uname, dn_string)
        pers_string += "%s" % objclass_string
        if person_names.has_key(person_id):
            if person_names[person_id].has_key(int(co.name_full)):
                utf_name = some2utf(person_names[person_id][int(co.name_full)])
            elif person_names[person_id].has_key(int(co.name_first)) and \
                     person_names[person_id].has_key(int(co.name_last)):
                utf_name = some2utf("%s %s" % (
                    person_names[person_id][int(co.name_first)],
                    person_names[person_id][int(co.name_last)]))
            else:
                logger.warn("Person got no name: %s", person_id)
                continue
        pers_string += "cn: %s\n" % utf_name
        if row['birth_date']:
            pers_string += "norEduPersonBirthDate: %s\n" % (
                time.strftime("%Y%m%d",
                              time.strptime(str(row['birth_date']),
                                            "%Y-%m-%d %H:%M:%S.00")))
        pers_string += ("norEduPersonNIN: %s\n"
                        % re.sub(r'\D','',row['external_id']))
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
        if not prim_org.endswith(get_tree_dn('ORG')):
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
            uname, cereconf.INSTITUTION_DOMAIN_NAME)
        lastname = utf_name
        if person_names.has_key(person_id):
            if person_names[person_id].has_key(int(co.name_first)):
                pers_string += "givenName: %s\n" % \
                               some2utf(person_names[person_id][int(co.name_first)])
            else:
                logger.warn("Person got no firstname: %s", person_id)
                continue
            if person_names[person_id].has_key(int(co.name_last)):
                lastname = person_names[person_id][int(co.name_last)]
            else:
                logger.warn("Person got no lastname: %s", person_id)
                continue
        else:
            logger.warn("Person got no names: %s", person_id)
            continue
                
        if mail_module:
            if mail_addresses.has_key(int(row['account_id'])):
                lp, dom = mail_addresses[int(row['account_id'])]
                if email_domains and email_domains.has_key(dom):
                    pers_string += "mail: %s@%s\n" % (lp,
                                                      email_domains[dom])
                else:
                    pers_string += "mail: %s@%s\n" % (lp,
                                                      dom)
        else:
            pers_string += "mail: %s\n" % person.get_contact_info(source=None,
                                                                  type=co.contact_email)
        if lastname:
            pers_string += "sn: %s\n" % some2utf(lastname)
        if print_phaddr:
            # address_post:
            if addr_info.has_key(person_id) and \
                   addr_info[person_id].has_key(int(co.address_post)):
                a_txt, p_o_box, p_num, city, country = \
                       addr_info[person_id][int(co.address_post)]
                post_string = make_address("$", p_o_box, a_txt, p_num,
                                           city, country)
                pers_string += "postalAddress: %s\n" % post_string
            # address_street:
            if addr_info.has_key(person_id) and \
                   addr_info[person_id].has_key(int(co.address_street)):
                a_txt, p_o_box, p_num, city, country = \
                       addr_info[person_id][int(co.address_street)]
                street_string = make_address(", ", None, a_txt, p_num,
                                           city, country)
                pers_string += "street: %s\n" % street_string
            # titles:
	    if person_title.has_key(person_id) and \
		   person_title[person_id].has_key(int(co.name_personal_title)):
	        pers_string += "title: %s\n" % \
                               some2utf(person_title[person_id][int( \
                    co.name_personal_title)])
	    else:
		if person_title.has_key(person_id) and \
		       person_title[person_id].has_key(int(co.name_work_title)):
		    pers_string += "title: %s\n" % \
				some2utf(person_title[person_id][int( \
                        co.name_work_title)])
            # phone & fax:
            if ph_tab.has_key(person_id):
                for phone in ph_tab[person_id]:
                    pers_string += "telephoneNumber: %s\n" % phone
            if fax_tab.has_key(person_id):
                for fax in fax_tab[person_id]:
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
        pers_string += "uid: %s\n" % uname
        passwd = ""
        if auth_info.has_key(account_id):
            passwd = auth_info[account_id].get(int(co.auth_type_md5_crypt))
            if not passwd:
                passwd = auth_info[account_id].get(int(co.auth_type_crypt3_des))
        else:
            logger.warn("User %s got no password-hash.", uname)
    
        if row['quarantine_type'] is not None:
            qh = QuarantineHandler.QuarantineHandler(db, 
                                                     [row['quarantine_type']])
            if qh.should_skip():
                continue
            if qh.is_locked():
                passwd = '*Locked'
        pers_string += "userPassword: {crypt}%s\n" % (passwd or '*Invalid')

        #if aci_person  and (int(person.entity_id)  not in aci_empl_gr):
        if aci_person  and not aci_empl_gr.has_key(int(person_id)):
            pers_string += "%s\n" % cereconf.LDAP_PERSON_ACI
        elif (aci_student_gr.has_key(int(person_id))) and \
                 not aci_person:
            pers_string += "%s\n" % cereconf.LDAP_PERSON_ACI
        alias_list[int(person_id)] = uname, prim_org,\
                                     utf_name, lastname
        glob_fd.write(pers_string)
        glob_fd.write("\n")
	
    logger.debug("person.list_extended_person done in '%d' sec.", now()-start)
    

def generate_alias():
    person = Factory.get('Person')(db)
    dn_string  = get_tree_dn('PERSON')
    obj_string = "".join(["objectClass: %s\n" % oc for oc in
                          ('top', 'alias', 'extensibleObject')])
    for alias in person.list_persons():
	person_id = int(alias['person_id'])
	if alias_list.has_key(person_id):
	    entity_name, prim_org, name, lastname = alias_list[person_id]
	    alias_str = "dn: uid=%s,%s\n" % (entity_name, prim_org)
	    alias_str += obj_string
	    alias_str += "uid: %s\n" % entity_name
	    if name:
		alias_str += "cn: %s\n" % some2utf(name)
	    if lastname:
		alias_str += "sn: %s\n" % some2utf(lastname)
	    alias_str += "aliasedObjectName: uid=%s,%s\n" % (entity_name,
                                                             dn_string)
	    glob_fd.write(alias_str)
	    glob_fd.write("\n")


ou_rdn_re = re.compile(r'[,+\\ ]+')


def make_ou_for_rdn(ou):
    return ou_rdn_re.sub(' ', ou).strip()


def get_contacts(entity_id=None,source_system=None,contact_type=None,email=0):
    entity = Entity.EntityContactInfo(db)
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


def main():
    global logger, mail_module

    logger = Factory.get_logger("console")
    # The script is designed to use the mail-module.
    mail_module = True
    ofile = None

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'o:m', ['help',
                                                         'org=',
                                                         'omit-mail-module'])
    except getopt.GetoptError:
        usage(1)
    for opt, val in opts:
        if opt in ('-o', '--org'):
            ofile = val
        elif opt in ('-m', '--omit-mail-module'):
            mail_module = False
        elif opt in ('-h', '--help'):
            usage(0)

    if (cereconf.LDAP_ORG_ROOT_AUTO != 'Enable'):
        try:
            org_root = int(cereconf.LDAP_ORG_ROOT)
        except Errors.NotFoundError:
            logger.error("ORG_ROOT parameter in ldapconf.py not valid")
            raise
    else:
        org_root = root_OU()

    if not org_root:
        logger.error("Noe root-OU found. Exiting.")
        sys.exit(1)
        
    global glob_fd
    start = now()
    logger.debug("Opening file and starting dump.")
    glob_fd = SimilarSizeWriter(ofile or
                                cereconf.LDAP_DUMP_DIR + '/'
                                + cereconf.LDAP_ORG_FILE)
    glob_fd.set_size_change_limit(10)
    config(org_root)
    glob_fd.close()
    logger.debug("Closing file, dump done in %d sec.", now()-start)

def usage(exitcode=0):
    print """Usage: [-h|--help] [-o <outfile>|--org=<outfile>] [-m|--omit-mail-module]
      -o <outfile> | --org=<outfile> : Set ouput-file. 
      -m | --omit-mail-module        : Omit the mail-module in Cerebrum.
      -h | --help                    : This help-text.
 Write organization, person (if enabled) and alias (if enabled) to LDIF-file.
 If --omit-mail-module; mail-addresses are read from contact_info. Usefull
 for instalations without the mod_email-module."""
    sys.exit(exitcode)

def config(org_root):
            load_code_tables()
            init_ldap_dump(org_root)
            generate_org(org_root)
	    if (cereconf.LDAP_PERSON == 'Enable'):
		generate_person()
	    if (cereconf.LDAP_ALIAS == 'Enable'):
		generate_alias()

if __name__ == '__main__':
    	main()

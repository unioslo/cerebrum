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
    ph_tab = get_contacts(
        source_system = int(getattr(co, cereconf.LDAP_EMPLOYEE_SOURCE_SYSTEM)),
        contact_type  = int(co.contact_phone))
    fax_tab = get_contacts(
        source_system = int(getattr(co, cereconf.LDAP_EMPLOYEE_SOURCE_SYSTEM)),
        contact_type  = int(co.contact_fax))


def make_address(sep, p_o_box, address_text, postal_number, city, country):
    # UiO-specific p_o_box hack - should be moved
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
You have %d roots in your organization-tree. Cerebrum only supports 1.
""" % len(root_id)
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
    ou_list = ou.get_structure_mappings(
        co.OUPerspective(cereconf.LDAP_OU_PERSPECTIVE))
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
                        #### ???? Missing 'parent_id' argument
			print_OU(non_org, non_root_dn, stedkodestr)


def print_OU(id, parent_dn, stedkodestr, parent_id):
    # If parent_id is set, print this ou, otherwise do not show it.
    # Return the DN of this OU if printed, or parent_dn otherwise.
    # Update ou_struct[int(id)] with info about this ou.

    ou = Factory.get('OU')(db)
    ou.clear()
    ou.find(id)

    ou_attr = []
    cn_str = rdn_ou = None
    for val in (ou.acronym, ou.short_name, ou.display_name, ou.sort_name):
        val = some2utf((val or '').strip())
        ou_attr.append(val)
        if val:
            cn_str = val
            if not rdn_ou:
                rdn_ou = make_ou_for_rdn(val)
    dn = "ou=%s,%s" % (rdn_ou, parent_dn)
    if dn_dict.has_key(dn):
        dn = "norEduOrgUnitUniqueNumber=%s+%s" % (stedkodestr, dn)
    dn_dict[dn] = True
    entry = ["dn: %s\n" % dn]
    for ss in ('top', 'organizationalUnit', 'norEduOrgUnit'):
        entry.append("objectClass: %s\n" % ss)
    entry.extend(["ou: %s\n" % val
                  for val in attr_unique([rdn_ou] + ou_attr, normalize_string)
                  if val])
    entry.append("cn: %s\n" % cn_str)
    if ou_attr[0]:
        entry.append("norEduOrgAcronym: %s\n" % ou_attr[0])

    ou_phones = ou_faxs = ''
    if ph_tab.has_key(ou.ou_id):
        for phone in ph_tab[ou.ou_id]:
            entry.append("telephoneNumber: %s\n" % phone)
    if fax_tab.has_key(id):
        for fax in fax_tab[id]:
            entry.append("facsimileTelephoneNumber: %s\n" % fax)

    try:
	ou_email = get_contacts(
            entity_id = id, contact_type = int(co.contact_email), email = True)
    except:
        pass
    else:
        entry.extend(["mail: %s\n" % mail for mail in ou_email])

    entry.append("norEduOrgUnitUniqueNumber: %s\n" % stedkodestr)
    entry.append(("norEduOrgUniqueNumber: %08d\n"
                  % cereconf.DEFAULT_INSTITUSJONSNR))

    post_string = street_string = None
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
                    entry.append("postalAddress: %s\n" % post_string)
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
                    entry.append("street: %s\n" % street_string)
                    break

    if parent_id:
	ou_struct[int(id)] = (dn, post_string,
                              ", ".join(filter(None, (ou.short_name,
                                                      street_string))),
                              ou_phones, ou_faxs, int(parent_id))
	return parent_dn
    else:
	ou_struct[int(id)] = (dn, post_string, street_string,
                              ou_phones, ou_faxs, None)
        entry.append("\n")
    	glob_fd.write("".join(entry))
    	return dn


def trav_list(parent_id, ou_list, parent_dn):
    stedkode = Stedkode.Stedkode(db)
    for ou_id, ou_parent in ou_list:
	# Check if it is child of parent and not cyclic
	if ou_parent == parent_id and ou_id <> parent_id:
	    stedkode.clear()
	    try:
		stedkode.find(ou_id)
	    except:
		ou_struct[str(ou_id)] = parent_dn
                #### ???? Missing 'parent_id' argument
		dn = print_OU(ou_id, parent_dn, None)
		trav_list(ou_id, ou_list, dn)
            else:
		stedkodestr = "%02d%02d%02d" % (stedkode.fakultet,
                                                stedkode.institutt,
                                                stedkode.avdeling)
 	   	if stedkode.katalog_merke == 'T':
            	    dn = print_OU(ou_id, parent_dn, stedkodestr, None)
            	    trav_list(ou_id, ou_list, dn)
    	    	else:
		    print_OU(ou_id, parent_dn, stedkodestr, ou_parent)
		    trav_list(ou_id, ou_list, parent_dn)


_init_person_visibility_done = False

def init_person_visibility():
    global valid_print_affi, valid_phaddr_affi, valid_aff_aci
    global aci_student_gr, aci_empl_gr
    valid_print_affi = []
    valid_phaddr_affi = []
    valid_aff_aci = []
    aci_student_gr = {}
    aci_empl_gr = {}

    global _init_person_visibility_done
    _init_person_visibility_done = True

    if (cereconf.LDAP_PERSON_FILTER == 'Enable'):
        group = Factory.get('Group')(db)
	try:
	    for status in cereconf.LDAP_PERSON_LIST_AFFI:
		valid_print_affi.append(int(getattr(co, status)))
	except:
            pass
	try:
	    for status in cereconf.LDAP_PERSON_PH_ADDR_AFFI:
		valid_phaddr_affi.append(int(getattr(co, status)))
	except:
            pass
	try:
            for status in cereconf.LDAP_PERSON_AFF_ACI:
                valid_aff_aci.append(int(getattr(co, status)))
        except:
            pass
	try:
	    group.find_by_name(str(cereconf.PERSON_NOT_PUBLIC_GR))
	    for entries in group.list_members(member_type=co.entity_person)[0]:
		aci_empl_gr[int(entries[1])] = True
		#aci_empl_gr.append(entries[1])
	except:
            pass
	group.clear()
	try:
	    group.find_by_name(str(cereconf.PERSON_PUBLIC_GR))
	    for entries in group.list_members(member_type=co.entity_person)[0]:
		aci_student_gr[int(entries[1])] = True
	except Errors.NotFoundError:
            pass

def person_visibility(person_id, p_affiliations):
    if not _init_person_visibility_done:
        init_person_visibility()

    print_person = aci_person = print_phaddr = False
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
        print_person = print_phaddr = True

    #if aci_person  and (int(person.entity_id)  not in aci_empl_gr):
    if ((    aci_person and not aci_empl_gr.has_key(int(person_id))   ) or
        (not aci_person and     aci_student_gr.has_key(int(person_id)))  ):
        aci = "%s\n" % cereconf.LDAP_PERSON_ACI
    else:
        aci = None

    return print_person, aci, print_phaddr

_affili_em  = { 'employee': True }
_affili_stu = { 'student':  True }

def eduPersonAffiliation(person_id, p_affiliations):
    affi_names = {}
    for affi in p_affiliations:
        if int(affi['affiliation']) == int(co.affiliation_ansatt):
            affi_names.update(_affili_em)
            if affi['status'] == co.affiliation_status_ansatt_tekadm:
                affi_names['staff'] = True
            if affi['status'] == co.affiliation_status_ansatt_vit:
                affi_names['faculty'] = True
        if int(affi['affiliation']) == int(co.affiliation_student):
            affi_names.update(_affili_stu)
    affi_names = affi_names.keys()
    affi_names.sort()
    return affi_names


def generate_person():
    glob_fd.write(container_entry_string('PERSON'))

    person = Factory.get('Person')(db)
    account = Factory.get('Account')(db)

    objclass_string = "".join(
        ["objectClass: %s\n" % oc
         for oc in ('top', 'person', 'organizationalPerson',
                    'inetOrgPerson', 'eduPerson', 'norEduPerson')])

    if mail_module:
        # We don't want to import this if mod_email isn't present.
        from Cerebrum.modules import Email

    dn_base = cereconf.LDAP_BASE
    dn_string = get_tree_dn('PERSON')

    person_spread = None
    if (cereconf.LDAP_PERSON_FILTER == 'Enable'):
	try:
            person_spread = int(getattr(co, cereconf.PERSON_SPREAD))
	except:
            pass

    email_enable  = cereconf.LDAP_CEREMAIL == 'Enable'
    email_domains = getattr(cereconf, 'LDAP_REWRITE_EMAIL_DOMAIN', None) or {}

    # Make dict with all affiliations.
    logger.debug("Fetching personal affiliations...")
    start = now()
    affiliations = {}
    for row in person.list_affiliations():
        # 'affiliation', 'source_system', 'status', 'ou_id'
        dict = {}
        for x in ('affiliation', 'source_system', 'status', 'ou_id'):
            dict[x] = row[x]
        affiliations.setdefault(int(row['person_id']), []).append(dict)
    logger.debug("...affiliations done in '%d' secs.", now()-start)

    # Make dict with all contacts.
    logger.debug("Fetching personal contact info...")
    start = now()
    contact_info = {}
    for row in person.list_contact_info(entity_type=co.entity_person):
        row_id = int(row['entity_id'])
        if not contact_info.has_key(row_id):
            contact_info[row_id] = {}
        contact_info[row_id][row['contact_type']] = row['contact_value']
    logger.debug("...contact info done in '%d' secs.", now()-start)

    # Make dict with all names.
    logger.debug("Fetching personal names...")
    start = now()
    person_names = {}
    for row in person.list_persons_name(source_system=co.system_cached,
                                        name_type=[co.name_full,
                                                   co.name_first,
                                                   co.name_last]):
        if not person_names.has_key(int(row['person_id'])):
            person_names[int(row['person_id'])] = {}
        person_names[int(row['person_id'])][int(row['name_variant'])] = \
            row['name']
    logger.debug("...personal names done in '%d' secs.", now()-start)

    # Make dict with all titles.
    logger.debug("Fetching personal titles...")
    start = now()
    person_title = {}
    for row in person.list_persons_name(name_type=[co.name_personal_title,
						   co.name_work_title]):
        if not person_title.has_key(int(row['person_id'])):
            person_title[int(row['person_id'])] = {}
        person_title[int(row['person_id'])][int(row['name_variant'])] = \
            row['name']
    logger.debug("...personal titles done in '%d' secs.", now()-start)

    # Iff Make dict with all email-addresses.
    if mail_module:
        et = Email.EmailTarget(db)
        logger.debug("Fetching e-mail addresses...")
        start = now()
        mail_addresses = {}
        for row in et.list_email_target_primary_addresses(
                target_type = co.email_target_account):
            if row['entity_id']:
                # TBD: Should we check for multiple values for primary
                #      addresses?
                mail_addresses[int(row['entity_id'])] = [row['local_part'],
                                                         row['domain']]
            else:
                logger.warn("email_target: '%d' got no user.",
                            int(row['target_id']))
        logger.debug("...e-mail addresses done in '%d' secs.", now()-start)
    else:
        logger.debug("Mail-module skipped.")

    # Make dict with all auth-data.
    logger.debug("Fetching password hashes...")
    start = now()
    acc_info = {}
    auth_info = {}
    for row in account.list_account_authentication(
            auth_type = [co.auth_type_md5_crypt, co.auth_type_crypt3_des]):
        acc_info[int(row['account_id'])] = row['entity_name']
        if not auth_info.has_key(int(row['account_id'])):
            auth_info[int(row['account_id'])] = {}
        if row['method']:
            auth_info[int(row['account_id'])][int(row['method'])] = \
                row['auth_data']
    logger.debug("...password hashes done in '%d' secs.", now()-start)

    # Make dict with all entity_address.
    logger.debug("Fetching personal addresses...")
    start = now()
    addr_info = {}
    for row in person.list_entity_addresses(
            entity_type = co.entity_person,
            source_system = getattr(co, cereconf.LDAP_EMPLOYEE_SOURCE_SYSTEM),
            address_type = [co.address_street, co.address_post]):
        row_id = int(row['entity_id'])
        if not addr_info.has_key(row_id):
            addr_info[row_id] = {}
        addr_info[row_id][int(row['address_type'])] = (
            row['address_text'], row['p_o_box'], row['postal_number'],
            row['city'], row['country'])
    logger.debug("...personal addresses done in '%d' secs.", now()-start)

    # Start iterating over people:
    logger.debug("Processing persons...")
    round = 0
    start = now()
    cur = now()
    for row in person.list_persons_atype_extid(person_spread,
                                               include_quarantines=True):
        if round % 10000 == 0:
            logger.debug("Rounded '%d' rows in '%d' secs.", round, now()-cur)
            cur = now()
        round += 1

        person_id, account_id, ou_id = (row['person_id'], row['account_id'],
                                        row['ou_id'])

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

	print_person, aci, print_phaddr = person_visibility(
            person_id, p_affiliations)
	if not print_person: continue

        entry = ["dn: uid=%s,%s\n" % (uname, dn_string),
                 objclass_string,
                 "uid: %s\n" % uname]

        names = person_names.get(person_id)
        if not names:
            logger.warn("Person %s got no names. Skipping.", person_id)
            continue
        name      = some2utf(names.get(int(co.name_full),  '').strip())
        givenname = some2utf(names.get(int(co.name_first), '').strip())
        lastname  = some2utf(names.get(int(co.name_last),  '').strip())
        if not (lastname and givenname):
            givenname, lastname = split_name(name, givenname, lastname)
            if not lastname:
                logger.warn("Person %s got no lastname. Skipping.", person_id)
                continue
        if not name:
            name = " ".join(filter(None, (givenname, lastname)))
        entry.append("cn: %s\n" % name)
        entry.append("sn: %s\n" % lastname)
        if givenname:
            entry.append("givenName: %s\n" % givenname)

        if row['birth_date']:
            entry.append("norEduPersonBirthDate: %s\n" % (
                time.strftime("%Y%m%d",
                              time.strptime(str(row['birth_date']),
                                            "%Y-%m-%d %H:%M:%S.00"))))
        entry.append(("norEduPersonNIN: %s\n"
                      % re.sub(r'\D+', '', row['external_id'])))
        entry.append("eduPersonOrgDN: %s\n" % dn_base)

        try:
            ou_info = ou_struct[int(ou_id)]
            if ou_info[5] == None:
                prim_org = ou_info[0]
            else:
                parent_id = int(ou_info[5])
                while ou_struct[parent_id][5] <> None:
                    parent_id = int(ou_struct[int(parent_id)][5])
                prim_org = (ou_struct[parent_id][0])
        except:
            prim_org = ""
        if not prim_org.endswith(get_tree_dn('ORG')):
            prim_org = "ou=%s,%s" % (cereconf.LDAP_NON_ROOT_ATTR,
                                     get_tree_dn('ORG'))
        entry.append("eduPersonPrimaryOrgUnitDN: %s\n" % prim_org)
        edu_orgs = [prim_org]
        for edu_org in p_affiliations:
            try:
                edu_org = ou_struct[int(edu_org['ou_id'])]
                if edu_org[5] is None:
                    edu_orgs.append(edu_org[0])
            except:
                pass
        for edu_org in attr_unique(edu_orgs):
            entry.append("eduPersonOrgUnitDN: %s\n" % edu_org)

        entry.append("eduPersonPrincipalName: %s@%s\n" % (
            uname, cereconf.INSTITUTION_DOMAIN_NAME))

        if mail_module:
            mail = mail_addresses.get(int(row['account_id']))
            if mail:
                lp, dom = mail
                entry.append("mail: %s@%s\n" % (lp,email_domains.get(dom,dom)))
        else:
            mail = get_contacts(entity_id = person_id,
                                contact_type = co.contact_email, email = True)
            if mail:
                entry.extend(["mail: %s\n" % m for m in mail])

        if print_phaddr:
            # addresses:
            addrs = addr_info.get(person_id)
            post  = (addrs and addrs.get(int(co.address_post)))
            if post:
                a_txt, p_o_box, p_num, city, country = post
                post = make_address("$", p_o_box, a_txt, p_num, city, country)
                if post:
                    entry.append("postalAddress: %s\n" % post)
            street = (addrs and addrs.get(int(co.address_street)))
            if street:
                a_txt, p_o_box, p_num, city, country = street
                street = make_address(", ", None, a_txt, p_num, city, country)
                if street:
                    entry.append("street: %s\n" % street)
            # title:
            title = person_title.get(person_id)
            if title:
                title = (title.get(int(co.name_personal_title)) or
                         title.get(int(co.name_work_title    ))   )
                if title:
                    entry.append("title: %s\n" % some2utf(title))
            # phone & fax:
            if ph_tab.has_key(person_id):
                for phone in ph_tab[person_id]:
                    entry.append("telephoneNumber: %s\n" % phone)
            if fax_tab.has_key(person_id):
                for fax in fax_tab[person_id]:
                    entry.append("facsimileTelephoneNumber: %s\n" % fax)

        for affi in eduPersonAffiliation(person_id, p_affiliations):
            entry.append("eduPersonAffiliation: %s\n" % affi)

        passwd = auth_info.get(account_id)
        if passwd:
            passwd = (passwd.get(int(co.auth_type_md5_crypt )) or
                      passwd.get(int(co.auth_type_crypt3_des))   )
        if row['quarantine_type'] is not None:
            qh = QuarantineHandler.QuarantineHandler(db,
                                                     [row['quarantine_type']])
            if qh.should_skip():
                continue
            if qh.is_locked():
                passwd = '*Locked'
        if not passwd:
            logger.debug("User %s got no password-hash.", uname)
        # Store a useless password rather than no password so that
        # the password attribute easily can be replaced with a more recent
        # password if that is generated more frequently than this file.
        entry.append("userPassword: {crypt}%s\n" % (passwd or '*Invalid'))

        if aci:
            entry.append(aci)

        alias_list[int(person_id)] = uname, prim_org, name, lastname
        entry.append("\n")
        glob_fd.write("".join(entry))

    logger.debug("...persons done in '%d' secs.", now()-start)


def generate_alias():
    person = Factory.get('Person')(db)
    person_dn = get_tree_dn('PERSON')
    obj_string = "".join(["objectClass: %s\n" % oc for oc in
                          ('top', 'alias', 'extensibleObject')])
    for alias in person.list_persons():
	alias = alias_list.get(int(alias['person_id']))
	if alias:
	    uname, prim_org, name, lastname = alias
            glob_fd.write("""\
dn: uid=%s,%s
%s\
aliasedObjectName: uid=%s,%s
uid: %s
cn: %s
sn: %s
\n""" % (uname, prim_org, obj_string, uname, person_dn, uname, name, lastname))


ou_rdn_re = re.compile(r'[,+\\ ]+')

def make_ou_for_rdn(ou):
    return ou_rdn_re.sub(' ', ou).strip()


whitespace_re = re.compile(r'\s+')

def get_contacts(entity_id = None, source_system = None,
                 contact_type = None, email = False):
    entity = Entity.EntityContactInfo(db)
    cont_tab = {}
    for x in entity.list_contact_info(entity_id = entity_id,
                                      source_system = source_system,
                                      contact_type = contact_type):
        ph_list = [whitespace_re.sub('', str(x['contact_value']))]
	if '$' in ph_list[0]:
	    ph_list = ph_list[0].split('$')
	elif not email and '/' in ph_list[0]:
	    ph_list = ph_list[0].split('/')
        ph_list = [ph for ph in ph_list if ph not in ('', '0')]
	key = int(x['entity_id'])
        if cont_tab.has_key(key):
            cont_tab[key].extend(ph_list)
        else:
            cont_tab[key] = ph_list
    normalize = not email and normalize_phone
    for k, v in cont_tab.items():
        cont_tab[k] = attr_unique(v, normalize = normalize)
    if entity_id is None:
	return cont_tab
    else:
        return (cont_tab.values() or ((),))[0]


def attr_unique(values, normalize = None):
    if len(values) < 2:
        return values
    result = []
    done = {}
    for val in values:
        if normalize:
            norm = normalize(val)
        else:
            norm = val
        if not done.has_key(norm):
            done[norm] = True
            result.append(val)
    return result


nonspace_re_u = re.compile(ur'\S+')

def split_name(fullname = None, givenname = None, lastname = None):
    """Return UTF-8 (given name, last name)."""
    full, given, last = [nonspace_re_u.findall(unicode(n or '', 'utf-8'))
                       for n in (fullname, givenname, lastname)]
    if full and not (given and last):
        if last:
            rest_l = last
            while full and rest_l and rest_l[-1].lower() == full[-1].lower():
                rest_l.pop()
                full.pop()
            if full and rest_l:
                given = [full.pop(0)]
                if not [True for n in rest_l if not n.islower()]:
                    while full and not full[0].islower():
                        given.append(full.pop(0))
            else:
                given = full
        else:
            last = [full.pop()]
            got_given = rest_g = given
            if got_given:
                while full and rest_g:
                    if rest_g[0].lower() != full[0].lower():
                        try:
                            rest_g = rest_g[rest_g.index(full[0]):]
                        except ValueError:
                            try:
                                full = full[full.index(rest_g[0]):]
                            except ValueError:
                                pass
                    rest_g.pop(0)
                    full.pop(0)
            elif full:
                given = [full.pop(0)]
            if full and not (given[0].islower() or last[0].islower()):
                while full and full[-1].islower():
                    last.insert(0, full.pop())
            if not got_given:
                given.extend(full)
    return [u' '.join(n).encode('utf-8') for n in given, last]


def main():
    global logger, mail_module, glob_fd

    logger = Factory.get_logger("console")

    # The script is designed to use the mail-module.
    mail_module = True
    ofile = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'o:m', ['help',
                                                         'org=',
                                                         'omit-mail-module'])
        if args:
            raise getopt.GetoptError
    except getopt.GetoptError:
        usage(1)
    for opt, val in opts:
        if opt in ('-o', '--org'):
            ofile = val
        elif opt in ('-m', '--omit-mail-module'):
            mail_module = False
            sys.stderr.write(
                "Warning: Option --omit-mail-module (-m) is untested.\n")
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
    print """\
Usage: [-h|--help] [-o <outfile>|--org=<outfile>] [-m|--omit-mail-module]
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

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

import time, re, string, sys

import cereconf  
from Cerebrum import OU
from Cerebrum import Person
from Cerebrum import Errors
from Cerebrum import Account
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import Stedkode
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup

Cerebrum = Factory.get('Database')()
co = Factory.get('Constants')(Cerebrum)
ou_struct = {}
entity2uname = {}

def vailidate_name(str):
    #str = str.encode("ascii")
    #str = re.sub(rå]','0',str)
    str = re.sub(r',',' ', str)
    return str


#def get_nor_org
#    stedkode = Stedkode.Stedkode(Cerebrum)
#    root_ou = '900000'
    
def root_OU():
    ou = OU.OU(Cerebrum)
    root_id=ou.root()
    if len(root_id) > 1:
	text1 = "You have %d roots in your organization-tree. Cerebrum only support 1.\n" % (len(root_id))
        sys.stdout.write(text1)
    	for p in root_id:
            k = Cerebrum.pythonify_data(p['ou_id'])
	    ou.clear()
	    ou.find(k)
	    text2 = "Organization: %s   'ou_id': %s \n" % (ou.sort_name, ou.ou_id)
	    sys.stdout.write(text2)
#	""Fetch baseDN and/or nor-org-unit-number from config""
#	try:
#	    for line in open('/etc/cerebrum.conf','r').readlines():
#		baseDN = re.split((re.match('BaseDN', line, flags=0)), ':')
#	
    else:    
	pre_k = Cerebrum.pythonify_data(root_id[0]['ou_id'])	
	#k = Cerebrum.pythonify_data((list_parent
	print " ROOT: %s" % k
	return(k)

def generate_org(ou_id):
    ou = OU.OU(Cerebrum)
    list = ou.get_structure_mappings(36)
    ou_string = "%s,%s" % (cereconf.ORGANIZATION_DN, cereconf.LDAP_BASE)
    trav_list(ou_id, list, ou_string)

    
def print_OU(id, par_ou, stedkodestr):
    ou = OU.OU(Cerebrum)
    ou.clear()
    ou.find(id)
    str_ou = []
    ou_fax = None
    street_string = None
    post_string = None
    ou_phone = None
    if ou.acronym:
        str_ou = "%s=%s,%s" % (cereconf.ORG_ATTR,vailidate_name(ou.acronym),par_ou)
    else:
        str_ou = "%s=%s,%s" % (cereconf.ORG_ATTR,vailidate_name(ou.name),par_ou)
    print "dn: %s" % str_ou
    for ss in cereconf.ORG_OBJECTCLASS:
        print "objectClass: %s" % ss
    try:
    	ou_faxnumber = ou.get_contact_info(None, co.contact_fax)
    	if ou_faxnumber:
	    ou_fax = "%s" % (Cerebrum.pythonify_data(ou_faxnumber[0]['contact_value']))
	    for x in ou_faxnumber:
	    	print "facsimileTelephoneNumber: %s" % (Cerebrum.pythonify_data(x['contact_value']))
    except:
	pass
    if stedkodestr:	
	print "norOrgUnitNumber: %s" % stedkodestr
    if ou.acronym:
	print "ou: %s" % ou.acronym
    print "ou: %s" % ou.short_name
    print "ou: %s" % ou.display_name
    print "cn: %s" % ou.sort_name
    try:
	for cc in cereconf.SYSTEM_LOOKUP_ORDER:
	    post_addr = ou.get_entity_address(getattr(co, cc), co.address_post)
    	    if post_addr:
		post_addr_str = "%s" % string.replace(string.rstrip(post_addr[0]['address_text']),"\n","$") 
		post_string = "%s$ %s %s" % (post_addr_str,vailidate_name(post_addr[0]['postal_number']),vailidate_name(post_addr[0]['city']))
		print "postalAddress: %s" % post_string
		break
    	for dd in cereconf.SYSTEM_LOOKUP_ORDER:
            street_addr = ou.get_entity_address(getattr(co, dd), co.address_street)
            if street_addr:
		street_addr_str = "%s" % string.replace(string.rstrip(street_addr[0]['address_text']),"\n","$")
		street_string = "%s$ %s %s" %(street_addr_str, vailidate_name(street_addr[0]['postal_number']),vailidate_name(street_addr[0]['city']))
		print "streetAddress: %s" % street_string
                break
   	ou_phnumber = (ou.get_contact_info(None, co.contact_phone))
    	if ou_phnumber:
	    for x in ou_phnumber:
		ou_phone = "%s" % (Cerebrum.pythonify_data(x['contact_value']))
		print "telephoneNumber: %s" % ou_phone
    except:
	pass
    print ""
    #Setter str_ou istedenfor par_ou under
    ou_struct[str(id)]= str_ou,post_string,street_string,ou_phone,ou_fax
    return str_ou

    
def trav_list(par, list, par_ou):
    stedkode = Stedkode.Stedkode(Cerebrum)
    for c,p in list:
        if p == par:
	    stedkode.clear()
	    try:
		stedkode.find(c)
 	    	if stedkode.katalog_merke == 'T':
		        stedkodestr = string.join((string.zfill(str(stedkode.fakultet),2), string.zfill(str(stedkode.institutt),2), string.zfill(str(stedkode.avdeling),2)),'')
              		#ou_struct[str(c)] = par_ou
            		str_ou = print_OU(c, par_ou, stedkodestr)
            		trav_list(c, list, str_ou)
    	    	else:
			trav_list(c, list, par_ou)
	    except:
		ou_struct[str(c)] = par_ou
                str_ou = print_OU(c, par_ou, None)
                trav_list(c, list, str_ou)

def read_people():
    person = Person.Person(Cerebrum)
    ou = OU.OU(Cerebrum)
    account = Account.Account(Cerebrum)
    affili_codes = person.list_person_affiliation_codes()
    pers_affili_codes = {}
    for aff in affili_codes:
	pers_affili_codes[int(Cerebrum.pythonify_data(aff['code']))] = Cerebrum.pythonify_data(aff['code_str'])
    list = person.list_persons()
    for p in list:
        id = int(Cerebrum.pythonify_data(p['person_id'])) 
        person.clear()
    	person.find(id)
	try:
	    p_norssn = person.get_external_id()
	    account.clear()
	    u_id = account.list_accounts_by_owner_id(id)
	    if p_norssn and u_id:
    		try:
		    # TODO: Change to Cache-value
	    	    p_gname = person.get_name(getattr(co,'system_ureg'), co.name_first)
	    	    p_lname = person.get_name(getattr(co,'system_ureg'), co.name_last)
	    	    if (len(u_id)) >> 1:
	        	# TODO: Make a priority of the accounts
	    		account.entity_id = int(Cerebrum.pythonify_data(u_id[0]['account_id']))
	    	    else:
			account.entity_id = int(Cerebrum.pythonify_data(u_id[0]['account_id']))
	    	    p_uname = account.get_name(co.account_namespace)
	    	    print "\n"
	    	    print "dn: %s=%s,%s,%s" % (cereconf.PERSON_ATTR,p_uname,cereconf.PERSON_DN,cereconf.LDAP_BASE)
		    for ee in cereconf.PERSON_OBJECTCLASS:
			print "objectClass: %s" % ee
	    	    print "cn: %s" % (person.get_name(getattr(co,'system_cached'),co.name_full))
	    	    print "birthDate: %s" % (time.strftime("%d%m%y",time.strptime(str(person.birth_date),"%Y-%m-%d %H:%M:%S.00"))) 
		    print "norSSN: %s" % (Cerebrum.pythonify_data(p_norssn[0]['external_id']))
	    	    print "eduPersonOrgDN: %s" % cereconf.LDAP_BASE
		    try:
	    		p_affili = person.get_affiliations()
			if p_affili:
	    	    	    for x in p_affili:
            	        	p_ouid = int(Cerebrum.pythonify_data(x['ou_id']))
		        	ou.clear()
		        	ou.find(p_ouid)
   		        	if ou.acronym:
        	            	    print "eduPersonPrimaryOrgUnitDN: ou=%s,%s" % (vailidate_name(ou.acronym),ou_struct[str(p_ouid)][0])
    		        	else:
        	    	    	    print "eduPersonPrimaryOrgUnitDN: ou=%s,%s" % (vailidate_name(ou.name),ou_struct[str(p_ouid)][0])
		        print "eduPersonOrgUnitDN: %s" % ou_struct[str(p_ouid)][0]
	    	    except:
			pass
	    	    print "eduPersonPrincipalName: %s@uio.no" % p_uname
	    	    print "givenName: %s" % p_gname
		    cont_email = None
		    cont_phone = None
		    cont_fax = None
		    for inf_ord in cereconf.SYSTEM_LOOKUP_ORDER:
		    	cont_info = person.get_contact_info(getattr(co, inf_ord), None)
		    	for info in cont_info:
			    if (Cerebrum.pythonify_data(info['contact_type']) == co.contact_email) and not cont_email: 
			    	cont_email = (Cerebrum.pythonify_data(info['contact_value']))
			    if (Cerebrum.pythonify_data(info['contact_type']) == co.contact_phone) and (Cerebrum.pythonify_data(info['contact_pref']) == 1) and not cont_phone:
                            	cont_phone = (Cerebrum.pythonify_data(info['contact_value']))
			    if (Cerebrum.pythonify_data(info['contact_type']) == co.contact_fax) and not cont_fax:
                            	cont_fax = (Cerebrum.pythonify_data(info['contact_value']))
	    	    try:
			print "mail: %s" % cont_email
	    	    except:
			pass
	    	    print "sn: %s" % p_lname 
	    	    try:
			p_uids = account.list_accounts_by_type(p_ouid, co.affiliation_employee, None)
			if p_uids:
			    acc_ouid = int(Cerebrum.pythonify_data(p_uids[0]['ou_id']))
		    	    if ou_struct[str(acc_ouid)][1]:
				print "postAddress: %s" % ou_struct[str(acc_ouid)][1]
			    if ou_struct[str(acc_ouid)][2]:
				print "streetAddress: %s" % ou_struct[str(acc_ouid)][2]
		    	#print "title: "
	    	    except:
			pass
	    	    try:
			if p_uids:
			    if cont_phone:
				print "telephoneNumber: %s" % cont_phone
			    else:
				if ou_struct[str(acc_ouid)][3]:
				    print "telephoneNumber: %s" % ou_struct[str(acc_ouid)][3]
				else:
				    pass
			    if cont_fax:
				print "facsimileTelephoneNumber: %s" % cont_fax 
			    else:
				if ou_struct[str(acc_ouid)][4]:
                                    print "facsimileTelephoneNumber: %s" % ou_struct[str(acc_ouid)][4]
                                else:
                                    pass
		    except:
			pass
		
		    try:
			for y in p_affili:
			    p_affi = int(Cerebrum.pythonify_data(y['affiliation']))
			    print "eduPersonAffiliation: %s" % (string.lower(pers_affili_codes[p_affi]))
		    except:
			pass
		    print "uid: %s" % p_uname
		    p_passwd = account.get_account_authentication(co.auth_type_md5_crypt)
		    if p_passwd:
		    	if (string.find(p_passwd, '*invalid')) <> -1:
		    	    print "userPassword: %s" % p_passwd
		    	else:
		    	    print "userPassword: {crypt}%s" % p_passwd
		    else:
		    	print "userPassword: *invalid"
		except Errors.NotFoundError:
			pass 
            else:
                pass
        except:
            pass

def generate_users():
    posix_user = PosixUser.PosixUser(Cerebrum)
    posix_group = PosixGroup.PosixGroup(Cerebrum)
    for row in posix_user.list_posix_users():

        id = Cerebrum.pythonify_data(row['account_id'])
        posix_user.clear()
        posix_user.find(id)
        # TODO: The value_domain should be fetched from somewhere
        # The array indexes should be replaced with hash-keys
        uname = posix_user.get_name(co.account_namespace)
        if entity2uname.has_key(id):
            raise ValueError, "Entity %d has multiple unames: (%s, %s)" % (
                entity2uname[id], uname)
        else:
            entity2uname[id] = uname
        # TODO: Something should set which auth_type to use for this map
        # TODO: Change 23 to a constant entry
        try:
            passwd = posix_user.get_account_authentication(co.auth_type_md5_crypt)
        except Errors.NotFoundError:
            passwd = '*'
        try:
            posix_group.clear()
            posix_group.find(posix_user.gid_id)
        except Errors.NotFoundError:
            continue

        # TODO: PosixUser.get_gecos() should default to .gecos.
        gecos = posix_user.get_gecos()

        # TODO: Using .description to get the shell's path is ugly.
        shell = PosixUser._PosixShellCode(int(posix_user.shell))
        shell = shell.description

        print "dn: %s=%s,%s,%s" % (cereconf.USER_ATTR,uname,cereconf.USER_DN,cereconf.LDAP_BASE)
        for ss in cereconf.USER_OBJECTCLASS:
           print "objectClass: %s" % ss
        print "cn: %s" % gecos
        print "uid: %s" % uname
        print "uidNumber: %s" % str(posix_user.posix_uid)
        print "gidNumber: %s" % str(posix_group.posix_gid)
        print "homeDirectory: %s" % str(posix_user.get_home())
        print "userPassword: {crypt}%s" % passwd
        print "loginShell: %s" % shell
        print "gecos: %s" % gecos
        print "\n"

def generate_group():
    posix_group = PosixGroup.PosixGroup(Cerebrum)
    groups = {}
    for row in posix_group.list_all('88'):
        posix_group.clear()
	print "%s" % (row.group_id)
        posix_group.find(row.group_id)
        # Group.get_members will flatten the member set, but returns
        # only a list of entity ids; we remove all ids with no
        # corresponding PosixUser, and resolve the remaining ones to
        # their PosixUser usernames.
        gname = posix_group.group_name
        gid = str(posix_group.posix_gid)

        members = []
        for id in posix_group.get_members():
            id = Cerebrum.pythonify_data(id)
            if entity2uname.has_key(id):
                members.append(entity2uname[id])
            else:
                raise ValueError, "Found no id: %s for group: %s" % (
                    id, gname)

        print "dn: %s=%s,%s,%s" % (cereconf.GROUP_ATTR,gname,cereconf.GROUP_DN,cereconf.LDAP_BASE)
        for ss in cereconf.GROUP_OBJECTCLASS:
            print "objectClass: %s" % ss
        print "cn: %s" % gname
        print "gidNumber: %s" % gid
        if posix_group.description:
            print "description: %s" % posix_group.description
        for m in members:
            print "memberUid: %s" % m
        print "\n"


def main():
	#init_ldap_dump()
	if cereconf.ORG_ROOT:
	    k = int(cereconf.ORG_ROOT)
	else:
	    root_OU(k)
	print "Org generate %d" % k
	generate_org(k)
	if (cereconf.PERSON == 'Enable'):
    	    print "Person generate" 
	    #read_people()
	if (cereconf.ALIAS == 'Enable'):
	    print "Alias generate"
	    #generate_alias()
	if (cereconf.USER == 'Enable'):
	    print "User generate"
	    generate_users()
	if (cereconf.GROUP == 'Enable'):
	    print "Group generate"
	    generate_group()
	
if __name__ == '__main__':
    	main()

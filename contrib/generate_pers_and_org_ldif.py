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

import cerebrum_path
from Cerebrum import OU
from Cerebrum import Person
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import Stedkode

Cerebrum = Factory.get('Database')()
co = Factory.get('Constants')(Cerebrum)
ou_struct = {}

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
	k = Cerebrum.pythonify_data(root_id[0]['ou_id'])	
	read_OU(k)

def read_OU(ou_id):
    ou = OU.OU(Cerebrum)
    list = ou.get_structure_mappings(29)
    trav_list(ou_id, list, "ou=organization,dc=uio,dc=no")

    
def print_OU(id, par_ou, stedkodestr):
    ou = OU.OU(Cerebrum)
    #info = Entity.Entity()
    ou.clear()
    ou.find(id)
    str_ou = []
    if ou.acronym:
        str_ou = "ou=%s,%s" % (vailidate_name(ou.acronym),par_ou)
    else:
        str_ou = "ou=%s,%s" % (vailidate_name(ou.name),par_ou)
    print "dn: %s" % str_ou
    print "objectClass: top"
    print "objectClass: organizationalUnit"
    print "objectClass: norOrganizationalUnit"
    try:
    	ou_faxnumber = ou.get_contact_info(id,'2')
    	if ou_faxnumber:
	    print "facsimileTelephoneNumber: %s" % ou_faxnumber
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
    	ou_pbox, ou_addrtxt, ou_postnr, ou_city = (ou.get_saddr(id,'4'))
    	ou_postadr = string.join((ou_pbox,ou_addrtxt,string.join((ou_postnr,ou_city),' ')),',')
    	if ou_postadr:
	    print "postalAddress: Pb.%s" % ou_postadr
    	ou_spbox, ou_saddrtxt, ou_spostnr, ou_scity = (ou.get_saddr(id,'5'))
    	ou_streetadr = string.join((ou_saddrtxt,string.join((ou_spostnr,ou_scity),' ')),',')
    	if ou_streetadr:
	    print "street: %s" % ou_streetadr
    	ou_phnumber = (ou.get_contact_info(id,'1'))
    	if ou_phnumber:
	    print "telephoneNumber: %s" % ou_phnumber
    except:
	pass
    print ""
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
              		ou_struct[str(c)] = par_ou
            		str_ou = print_OU(c, par_ou, stedkodestr)
            		trav_list(c, list, str_ou)
    	    	else:
			trav_list(c, list, par_ou)
	    except:
		ou_struct[str(c)] = par_ou
                str_ou = print_OU(c, par_ou, None)
                trav_list(c, list, str_ou)

def read_people():
    pers = Person.Person(Cerebrum)
    ou = OU.OU(Cerebrum)
    list = pers.get_all_person_ids()
    for p in list:
        id = int(Cerebrum.pythonify_data(p['person_id'])) 
        pers.clear()
    	pers.find(id)
	try:
	    p_norssn = (pers.get_norssn(id))
	    u_id = pers.get_uid_ids(id)
	    if p_norssn and u_id:
    		try:
	    	    p_gname = pers.get_name(28, 10)
	    	    p_lname = pers.get_name(28, 11)
	    	    #u_id = pers.get_uid_ids(id)
	    	    if (len(u_id)) >> 1:
	    		p_uid = int(Cerebrum.pythonify_data(u_id[0]['account_id']))
	    	    else:
	    		p_uid = int(pers.get_uid_id(id))
	    	    p_uname = (pers.get_uid(p_uid))
	    	    print "\n"
	    	    print "dn: uid=%s,ou=people,dc=uio,dc=no" %  p_uname
	    	    print "objectClass: top"
	    	    print "objectClass: person"
	    	    print "objectClass: organizationalPerson"
	    	    print "objectClass: inetOrgPerson"
	    	    print "objectClass: eduPerson"
            	    print "objectClass: norPerson"
	    	    print "cn: %s %s" % (p_gname,p_lname) 
	    	    print "birthDate: %s" % (time.strftime("%d%m%y", time.gmtime(pers.get_birth(id)))) 
	     	    #print "norSSN: %s" % (pers.get_norssn(id))
		    print "norSSN: %s" % p_norssn
	    	    print "eduPersonOrgDN: dc=uio,dc=no"
		    try:
	    		p_affili = pers.get_uids_affili(id)
			if p_affili:
	    	    	    for x in p_affili: 
            	        	p_ouid = int(Cerebrum.pythonify_data(x['ou_id']))
		        	ou.clear()
		        	ou.find(p_ouid)
   		        	if ou.acronym:
        	            	    print "eduPersonPrimaryOrgUnitDN: ou=%s,%s" % (vailidate_name(ou.acronym),ou_struct[str(p_ouid)])
    		        	else:
        	    	    	    print "eduPersonPrimaryOrgUnitDN: ou=%s,%s" % (vailidate_name(ou.name),ou_struct[str(p_ouid)])
		        print "eduPersonOrgUnitDN: %s" % ou_struct[str(p_ouid)]
	    	    except:
			pass
	    	    print "eduPersonPrincipalName: %s@uio.no" % p_uname
	    	    print "givenName: %s" % p_gname
	    	    try:
	    		print "mail: %s" % (pers.get_mail(id,'3'))
	    	    except:
			pass
	    	    print "sn: %s" % p_lname 
	    	    try:
			p_uids = pers.get_uid_info(id,'13') 
			if p_uids:
		    	    p_pbox, p_addrtxt, p_postnr, p_city = (pers.get_saddr(p_ouid,'4'))
		    	    p_postadr = string.join((p_pbox,p_addrtxt,string.join((p_postnr,p_city),' ')),',')
		    	    if p_postadr:
				print "postalAddress: Pb.%s" % p_postadr
		    	    p_spbox, p_saddrtxt, p_spostnr, p_scity = (pers.get_saddr(p_ouid,'5'))
			    p_streetadr = string.join((p_saddrtxt,string.join((p_spostnr,p_scity),' ')),',')
			    if p_streetadr:
				print "street: %s" % p_streetadr
		    	#print "title: "
	    	    except:
			pass
	    	    try:
			if p_uids:
			    phnumber = (pers.get_mail(id,'1'))
			    if phnumber:
				print "telephoneNumber: %s" % phnumber
			    else:
		 		print "telephoneNumber: %s" % (pers.get_mail(p_ouid,'1'))
			    faxnumber = (pers.get_mail(id,'2'))
			    if faxnumber:
				print "facsimileTelephoneNumber: %s" % faxnumber 
			    else:
				print "facsimileTelephoneNumber: %s" % (pers.get_mail(p_ouid,'2'))
		    except:
			pass
		    try:
			for y in p_affili:
			    p_affi = int(Cerebrum.pythonify_data(y['affiliation']))
			    print "eduPersonAffiliation: %s" % (string.lower(pers.get_affi(p_affi)))
		    except:
			pass
		    print "uid: %s" % p_uname
		    p_passwd = pers.get_passwd(p_uid)
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

def main():
	root_OU()
    	read_people()

if __name__ == '__main__':
    	main()

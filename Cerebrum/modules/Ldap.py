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

import os
import re
import ldif
import ldap
from ldap import modlist

import cereconf
 
from Cerebrum.extlib import logging
from Cerebrum import Database
from Cerebrum.Database import Errors
from Cerebrum.Utils import Factory
 
db = Factory.get('Database')()
 
logger = Factory.get_logger("console")

ldap_update_str = ','.join(('ou=services', cereconf.LDAP_BASE_DN))


class LdapCall:

    def __init__(self,s_dict):
	self.s_list = {}
	
    def __call__(self, s_dict):
	return s_dict

    def get_update_tag(self,cn_tag):
	ldap_update_dn = ','.join(('cn=' + cn_tag, ldap_update_str))
	ldap_update_tag =  [ (ldap_update_dn),
                        {'cn':[cn_tag],
                        'objectclass':['top','applicationProcess'],
                        'description':['Disable dynamic LDAP sync.']}]
	return(ldap_update_tag)



    def ldap_connect(self,serv_l=None):
        if not serv_l:
            serv_l = cereconf.LDAP_SERVER
        for server in serv_l:
            try:
                serv,user = [str(y) for y in server.split(':')]
                f_name = cereconf.LDAP_DUMP_DIR + '/log/' + serv + '.sync.log'
                try:
                    passwd = db._read_password(serv,user)
                except:
                    logger.warn('No valid password-file for %s!' % serv)
                    break
                if os.path.isfile(f_name): self.s_list[serv] = [file(f_name,'a'),]
                else: self.s_list[serv] = [file(f_name,'w'),]
                user = ','.join((user, cereconf.LDAP_BASE_DN))
                con = ldap.open(serv)
                con.protocol_version = ldap.VERSION3
                try:
                    if cereconf.TLS_CACERT_FILE is not None:
                        con.OPT_X_TLS_CACERTFILE = cereconf.TLS_CACERT_FILE
                except:  pass
                try:
                    if cereconf.TLS_CACERT_DIR is not None:
                        con.OPT_X_TLS_CACERTDIR = cereconf.TLS_CACERT_DIR
                except:  pass
                l_bind = None
                try:
                    con.start_tls_s()
                    l_bind = con.simple_bind(user,passwd)
                    self.s_list[serv].append(con)
                except:
                    logger.warn("Could not open TLS-connection to %s" % serv)
                    self.s_list[serv][0].close()
                    del self.s_list[serv]
                if l_bind and con:
                    logger.info("TLS-connection open to %s" % serv)
            except ldap.LDAPError, e:
                logger.warn(e)


    def end_session(self):
        for serv,value in self.s_list.items():
            try: value[1].unbind()
            except: logger.warn("Could not close LDAP/SSL to server: %s" % serv)
            value[0].write("\n# Closed TLS-connection and log_file.")
            logger.info('Closed TLS-chanel and log to server %s' % serv)
            try:
                value[0].close()
                logger.info('File closed')
            except:
                logger.warn("Could not close log-file to server: %s" % serv)
        self.s_list = {}


    def get_ldap_value(self,search_id,dn,retrieveAttributes=None):
	searchScope = ldap.SCOPE_SUBTREE
	result_set = []
	for serv,l in self.s_list.items():
	    try:
		ldap_result_id = l[1].search(search_id,searchScope,dn,retrieveAttributes)
		while 1:
		    result_type, result_data = l[1].result(ldap_result_id, 0)
		    if (result_data == []):
			break
		    else:
			if result_type == ldap.RES_SEARCH_ENTRY:
			    result_data.append(serv)
			    result_set.append(result_data)
			else:
			    pass
	    except ldap.LDAPError, e:
		logger.info(e) # Do some spec logging of server-messages
	    	return(None)
	return(result_set)

 
    def mod_ldap(self,ldap_mod,attr,attr_value,dn_value,list=None):
	if list:
	    ldif_list = [(ldap_mod,attr,attr_value)]
	else:
	    ldif_list = [(ldap_mod,attr,(attr_value,))]
	for serv,l in self.s_list.items():
	    result_ldap_mod = l[1].modify(dn_value,ldif_list)
	    log_str = '\n' + ldif.CreateLDIF(dn_value,ldif_list)
	    if result_ldap_mod:
		l[0].write(log_str)
	    else:
		log_str = '\n# ' + serv + ': ' + log_str
		logger.info(log_str)
                                                                                                                                                                                                                                        
    def mod_ldap_serv(self,ldap_mod,attr,attr_value,dn_value,k,list=None):
	if list:
	    ldif_list = [(ldap_mod,attr,attr_value)]
	else:
	    ldif_list = [(ldap_mod,attr,(attr_value,))]
	result_ldap_mod = self.s_list[k][1].modify(dn_value,ldif_list)
	log_str = '\n' + ldif.CreateLDIF(dn_value,ldif_list)
	if result_ldap_mod :
	    self.s_list[k][0].write(log_str)
	else:
	    log_str = '\n# ' + serv + ': ' + log_str
	    logger.info(log_str)


    def add_ldap(self,dn_value,ldif_list):
	for serv,l in self.s_list.items():
	    result_add_ldap = l[1].add(dn_value,ldif_list)
	    log_str = '\n' + ldif.CreateLDIF(dn_value,ldif_list)
	    if result_add_ldap:
		l[0].write(log_str)
	    else:
		log_str = '\n# ' + serv + ': ' + log_str
		logger.info(log_str)


    def add_ldap_serv(self,dn_value,ldif_list,k):
	result_add_ldap = self.s_list[k][1].add(dn_value,ldif_list)
	log_str = '\n' + ldif.CreateLDIF(dn_value,ldif_list)
	if result_add_ldap:
	    self.s_list[k][0].write(log_str)
	else:
	    log_str = '\n# ' + serv + ': ' + log_str
	    logger.info(log_str)


    def delete_ldap(self,dn_value):
	for serv,l in self.s_list.items():
	    result_del_ldap = l[1].delete(dn_value)
	    log_str = '\n' + ldif.CreateLDIF(dn_value,{'changetype': \
							('delete',)})
	    if result_del_ldap:
		l[0].write(log_str)
	    else:
		log_str = '\n# ' + serv + ': ' + log_str
		logger.info(log_str)
                                                                                                                                  
    def delete_ldap_serv(self,dn_value,k):
	result_del_ldap = self.s_list[k][1].delete(dn_value)
	log_str = '\n' + ldif.CreateLDIF(dn_value,{'changetype': ('delete',)})
	if result_del_ldap:
	    s_list[k][0].write(log_str)
	else:
	    log_str = '\n# ' + k + ': ' + log_str
	    logger.info(log_str)
                                                                                                                                  
          
    def modrdn_ldap(self,dn_value,new_value,delete_old=True):
	for serv,l in self.s_list.items():
	    result_del_ldap = l[1].modrdn(dn_value,new_value,delete_old)
	    log_str = '\n' + ldif.CreateLDIF(dn_value,\
					{'changetype': ('modrdn',),\
                        		'newrdn':(new_value,),\
					'deleteoldrdn':(str(delete_old),)})
	    if result_del_ldap:
		l[0].write(log_str)
	    else:
		log_str = '# ' + serv + ': ' + log_str
		logger.info(log_str)

 
    def add_disable_sync(self,cn_tag):
	ldap_update_tag = self.get_update_tag(cn_tag)
	ldif_list = modlist.addModlist(ldap_update_tag[1])
	self.add_ldap(ldap_update_tag[0],ldif_list)

 
    def check_sync_mode(self,cn_tag):
	cn_str = str('cn=' + cn_tag)
	value = self.get_ldap_value(ldap_update_str,cn_str)
	if (value == []):
	    return(True)
	else:
 	    return(False)

    def delete_disable_sync(self,cn_tag):
	cn_str = ','.join(('cn=' + cn_tag, ldap_update_str))
	self.delete_ldap(cn_str)



# arch-tag: 623f4d9e-e3cf-4bfa-8538-7b86a5ab1927

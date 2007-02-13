#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2006 University of Oslo, Norway
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

# account_add
# name_set, name_mod (not finished)
import sys, os, getopt, time, string, pickle, re, ldap, ldif

import cerebrum_path
import cereconf
from Cerebrum import Constants
from Cerebrum.modules.no.hia import EdirUtils
from Cerebrum.modules.no.hia import EdirLDAP
from Cerebrum import Errors
from Cerebrum import Group
from Cerebrum import Entity
from Cerebrum.Constants import _SpreadCode
from Cerebrum.extlib import logging
from Cerebrum.Utils import Factory
from Cerebrum.modules import CLHandler


def account_make_attrs(account_id):
    attr = {}
    gen_qual_str = ""
    account.clear()
    account.find(account_id)
    attr['ObjectClass'] = ['user'] 
    attr['cn'] = [account.account_name]
    attr['uid'] = [account.account_name]
    attr['userPassword'] = ['xxxxxx']
    attr['passwordAllowChange'] = ['FALSE']
    attr['loginDisabled'] = ['FALSE']
    attr['passwordRequired'] = ['TRUE']
    names = _person_find_names(account.owner_id)
    attr['fullName'] = [names['name_full']]
    attr['sn'] = [names['name_last']]
    attr['givenName'] = [names['name_first']]
    email = account.get_primary_mailaddress()
    attr['mail'] = [email]
    gen_qual_str = _person_find_gen_qualifier(account.owner_id)
    attr['generationQualifier'] = [gen_qual_str]
    desc = "Cerebrum: created %s" % edir_util.date
    attr['description'] = [desc]
    
    return attr


def _person_account_make_dn(account_id):
    dn = ""
    edir_ou = ""
    account.clear()
    account.find(account_id)
    if account.has_spread(constants.Spread(cereconf.NW_LAB_SPREAD)):
        tmp = "cn=%s,%s,%s" % (account.account_name,
                               cereconf.NW_LDAP_STUDOU,
                               cereconf.NW_LDAP_ROOT)
        dn = unicode(tmp, 'iso-8859-1').encode('utf-8')
        return dn
    if _is_employee(account.owner_id):
        tmp = "cn=%s,%s,%s" % (account.account_name,
                               cereconf.NW_LDAP_ANSOU,
                               cereconf.NW_LDAP_ROOT)
        dn = unicode(tmp, 'iso-8859-1').encode('utf-8')
        return dn
    tmp = "cn=%s,%s,%s" % (account.account_name,
                           cereconf.NW_LDAP_STUDOU,
                           cereconf.NW_LDAP_ROOT)
    dn = unicode(tmp, 'iso-8859-1').encode('utf-8')
    return dn


def _is_employee(owner_id):
    person.clear()
    try:
        person.find(owner_id)
    except Errors.NotFoundError:
        logger.debug("No such person, entity_id: %s", owner_id)
        return False
    person_affs = person.get_affiliations()
    for r in person_affs:
        if r['affiliation'] == constants.affiliation_ansatt:
            return True
        elif r['affiliation'] == constants.affiliation_manuell:
            if r['status'] in [constants.affiliation_status_manuell_filonova,
                               constants.affiliation_status_manuell_agderforskning,
                               constants.affiliation_status_manuell_statsbygg,
                               constants.affiliation_status_manuell_ans_uten_sap,
                               constants.affiliation_status_manuell_gjest]:
                return True
        elif r['affiliation'] == constants.affiliation_tilknyttet:
            return True
        else:
            logger.debug("Not an employee, entity_id %s", owner_id)
    return False
        
    
def _person_find_gen_qualifier(owner_id):
    ext_id = []
    ret = "empty"
    person.clear()
    try:
        person.find(owner_id)
    except Errors.NotFoundError:
        logger.debug("Account %s not owned by a person in Cerebrum", uname)
        return ret
    ext_id = person.get_external_id(source_system=constants.system_sap,
                                    id_type=constants.externalid_sap_ansattnr)
    if ext_id == []:
        ext_id = person.get_external_id(source_system=constants.system_fs,
                                        id_type=constants.externalid_studentnr)
    if ext_id <> []:
        ret = ext_id[0]['external_id']
    return ret

    
def _person_find_names(owner_id):
    ret = {}
    fname = lname = ""
    person.clear()
    try:
        person.find(owner_id)
    except Errors.NotFoundError:
        logger.debug("Account % not owned by a person in Cerebrum", uname)
        return ret
    name_full = person.get_name(constants.system_cached, constants.name_full)
    names = name_full.split(' ')
    lname = names[len(names)-1]

    fname = names[0]
    i = 1
    while i < len(names) - 1:
        fname = fname + ' ' + names[i]
        i = i + 1
    fname = fname.strip()

    ret = {'name_full': unicode(name_full, 'iso-8859-1').encode('utf-8'),
           'name_first': unicode(fname, 'iso-8859-1').encode('utf-8'),
           'name_last': unicode(lname, 'iso-8859-1').encode('utf-8')}
    return ret


def person_mod_names(person_id):
    person.clear()
    person.find(person_id)
    accs = person.get_accounts()
    for a in accs:
        account.clear()
        account.find(a['account_id'])
        # Only try to update names for accounts registered in eDir
        if (account.has_spread(constants.spread_hia_novell_user) or
            account.has_spread(constants.Spread(cereconf.NW_LAB_SPREAD))):
            names = _person_find_names(person_id)
            if names:
                logger.debug("Modified name for %s", account.account_name)
                edir_util.person_set_name(account.account_name,
                                          names['name_first'],
                                          names['name_last'],
                                          names['name_full'])
            else:
                logger.error("No name for %s, skipping", account.account_name)
                return
                                          
        
def main():
    global db, constants, account, person
    global edir_util, logger
    
    db = Factory.get('Database')()
    constants = Factory.get('Constants')(db)
    account = Factory.get('Account')(db)
    person = Factory.get('Person')(db)
    cl_handler = CLHandler.CLHandler(db)
    logger = Factory.get_logger('cronjob')

    cl_events = []

    passwd = db._read_password(cereconf.NW_LDAPHOST,
                               cereconf.NW_ADMINUSER.split(',')[:1][0])
    ldap_handle = EdirLDAP.LDAPConnection(db, cereconf.NW_LDAPHOST,
                                          cereconf.NW_LDAPPORT,
                                          binddn=cereconf.NW_ADMINUSER,
                                          password=passwd, scope='sub')
    edir_util = EdirUtils.EdirUtils(db, ldap_handle)

    try:
        cl_events = cl_handler.get_events('edirusync', (constants.spread_add,
                                                       constants.person_name_add,
                                                       constants.person_name_mod))
        if cl_events == []:
            logger.info("Nothing to do.")
            ldap_handle.close_connection()
            sys.exit(0)
            
        for event in cl_events:
            if event['change_type_id'] == constants.spread_add:
                s = pickle.loads(event['change_params'])['spread']
                if s == int(constants.spread_hia_novell_user):
                    dn =  _person_account_make_dn(event['subject_entity'])
                    edir_util.object_edir_create(dn, account_make_attrs(event['subject_entity']))
                    cl_handler.confirm_event(event)
            elif event['change_type_id'] in [constants.person_name_add, constants.person_name_mod]:
                person_mod_names(event['subject_entity'])
                cl_handler.confirm_event(event)
    except TypeError, e:
        logger.warn("No such event, %s" % e)
        return None
    cl_handler.commit_confirmations()

    ldap_handle.close_connection()

    
if __name__ == '__main__':
    main()

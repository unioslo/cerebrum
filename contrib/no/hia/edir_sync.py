#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2006-2010 University of Oslo, Norway
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

# sync account info and group memberships
# probably a temporary solution
import sys, time, pickle

import cerebrum_path
import cereconf
from Cerebrum.modules.no.hia import EdirUtils
from Cerebrum.modules.no.hia import EdirLDAP
from Cerebrum import Errors
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
    if len(names.keys()) < 3:
        names = {'name_full': unicode('no_name', 'iso-8859-1').encode('utf-8'),
                 'name_first': unicode('no_name', 'iso-8859-1').encode('utf-8'),
                 'name_last': unicode('no_name', 'iso-8859-1').encode('utf-8')}
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
    return account.account_name, dn


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
        logger.debug("Not a person, entity_id %s", owner_id)
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
        logger.debug("Not a person, entity_id %s", owner_id)
        return ret
    name_full = person.get_name(constants.system_cached, constants.name_full)
    names = name_full.split(' ')
    lname = names[len(names)-1]
    names.pop(len(names)-1)
    if len(names) >= 1:
        i = 0
        while i < len(names):
            fname = fname + ' ' + names[i]
            if len(fname) > 32:
                if len(names) > 1:
                    logger.info("Given name too long for %s, partially removing", owner_id)
                    fname = names[i]
                else:
                    fname = 'no_name'
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
                                          

def group_make_attrs(group_id):
    attr = {}
    group = Factory.get("Group")(db)
    group.clear()
    group.find(group_id)
    if not group.group_name:
        return {}
    
    group_name = cereconf.NW_GROUP_PREFIX + '-' + group.group_name
    desc = unicode(group.description).encode('utf-8')
    attr = {'objectClass': ['group'],
            'cn': [group_name],
            'member': [],
            'description': [desc]}
    return attr

def _group_make_dn(group_id, org):
    group = Factory.get("Group")(db)
    group.clear()
    group.find(group_id)
    if not group.group_name:
        return ''
    
    group_name = cereconf.NW_GROUP_PREFIX + '-' + group.group_name
    utf8_dn = unicode('cn=%s' % group_name, 'iso-8859-1').encode('utf-8')
    ldap_dn = utf8_dn + ',ou=grp,' + org + ',' + cereconf.NW_LDAP_ROOT    
    return ldap_dn

def group_mod(mod_type, group_id, member_id):
    group = Factory.get("Group")(db)
    grp = Factory.get("Group")(db)
    acc = Factory.get("Account")(db)
    member_name = ""
    member_type = "account"
    edir_group = False
    known_group = False
    group.clear()
    try:
        group.find(group_id)
    except Errors.NotFoundError:
        logger.info("Could not find group id:%s, group may be deleted", group_id)
        return
    if not group.group_name:
        logger.warn("Ignoring cl event on group_id=%s, since group has no name",
                    group_id)
        return

    for row in group.get_spread():
        if row['spread'] in [int(constants.spread_hia_novell_group),
                             int(constants.spread_hia_edir_grpemp),
                             int(constants.spread_hia_edir_grpstud)]:
            edir_group = True
    if not edir_group:
        logger.debug("Skipping, group %s not in eDir", group.group_name)
        return

    group_name = cereconf.NW_GROUP_PREFIX + '-' + group.group_name
    subj_ent = Factory.get('Entity')(db)
    subj_ent.clear()
    try:
        subj_ent.find(member_id)
    except Errors.NotFoundError:
        logger.warn('No such entity %s.', member_id)
        return
    if subj_ent.entity_type == constants.entity_group:
        grp.find(member_id)
        for row in group.get_spread():
            if row['spread'] in [int(constants.spread_hia_novell_group),
                                 int(constants.spread_hia_edir_grpemp),
                                 int(constants.spread_hia_edir_grpstud)]:
                known_group = True
        if known_group:        
            member_type = "group"
            member_name = cereconf.NW_GROUP_PREFIX + '-' + grp.group_name
    elif subj_ent.entity_type == constants.entity_account:
        acc.clear()
        try:
            acc.find(member_id)
        except Errors.NotFoundError:
            logger.error("No such account, %s", member_id)
            return
        member_name = acc.account_name
    else:
        logger.warn("Only groups or accounts may be members!")
        return 
    if mod_type == constants.group_add:
        ret = edir_util.group_modify('add', group_name, member_name, member_type)
        if ret:
            logger.info('New member %s added to %s' % (member_name, group_name))
    elif mod_type == constants.group_rem:
        logger.info('Removing from group')
        ret = edir_util.group_modify('delete', group_name, member_name, member_type)
        if ret:
            logger.info('Member %s removed from %s' % (member_name, group_name))

        
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
            logger.info("Nothing to do (account creation).")

        for event in cl_events:
            if event['change_type_id'] == constants.spread_add:
                s = pickle.loads(event['change_params'])['spread']
                if s == int(constants.spread_hia_novell_user):
                    uname, dn = _person_account_make_dn(event['subject_entity'])
                    tmp_attrs = account_make_attrs(event['subject_entity'])
                    if tmp_attrs:
                        # Check if user exists first
                        if edir_util._find_object(uname, edir_util.c_person):
                            logger.debug("Account %s already extist in Edir." %
                                         uname)
                        else:
                            edir_util.object_edir_create(dn, tmp_attrs)
                            time.sleep(1)
                        
            elif event['change_type_id'] in [constants.person_name_add,
                                             constants.person_name_mod]:
                person_mod_names(event['subject_entity'])
            cl_handler.confirm_event(event)
    except TypeError, e:
        logger.warn("No such event, %s" % e)
    cl_handler.commit_confirmations()

    time.sleep(2)
    
    try:
        cl_events = cl_handler.get_events('edirgroups', (constants.group_add,
                                                         constants.group_rem,
                                                         constants.spread_add))
        if cl_events == []:
            logger.info("Nothing to do (group memberships).")
            ldap_handle.close_connection()
            sys.exit(0)
        for event in cl_events:
            if event['change_type_id'] in [constants.group_add, constants.group_rem,]:
                group_mod(event['change_type_id'],
                          event['dest_entity'],
                          event['subject_entity'])
            elif event['change_type_id'] == constants.spread_add:
                s = pickle.loads(event['change_params'])['spread']
                if s == int(constants.spread_hia_edir_grpemp):
                    dn =  _group_make_dn(event['subject_entity'], 'ou=Ans')
                elif s == int(constants.spread_hia_edir_grpstud):
                    dn =  _group_make_dn(event['subject_entity'], 'ou=Stud')
                else:
                    cl_handler.confirm_event(event)             
                    continue
                attrs = group_make_attrs(event['subject_entity'])
                if not attrs or not dn:
                    logger.warn("Ignoring event, since group_id=%s has no name",
                                event['subject_entity'])
                else:
                    edir_util.object_edir_create(dn,
                                                 group_make_attrs(event['subject_entity']))
                    time.sleep(1)
            cl_handler.confirm_event(event)             
    except TypeError, e:
        logger.warn("No such event, %s" % e)
    cl_handler.commit_confirmations()

    ldap_handle.close_connection()

    
if __name__ == '__main__':
    main()

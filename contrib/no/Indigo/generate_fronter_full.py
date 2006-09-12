#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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


import sys
import locale
import os
import getopt
import time
import re

import cerebrum_path
getattr(cerebrum_path, 'This will shut the linters up', None)

import cereconf
from Cerebrum import Errors
from Cerebrum import Database
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uio.fronter_lib import XMLWriter
from Cerebrum.modules.abcenterprise.ABCUtils import ABCFactory

cf_dir = '/cerebrum/dumps/Fronter'
infile = '/cerebrum/dumps/ofk-data/abc_enterprise-ofk.xml'

db = const = logger = None 
fronter = fxml = None
new_users = None


def get_members(group_name):
    db = Factory.get("Database")()
    group = Factory.get("Group")(db)
    usernames = ()
    try:
        group.find_by_name(group_name)
    except Errors.NotFoundError:
        pass
    else:
        members = group.get_members(get_entity_name=True)
        usernames = tuple([x[1] for x in members])
    return usernames

host_config = {
    'ovgs.no': {'DBinst': 'ofkfronter',
                'admins': 'test', #get_members('classfronter-tavle-drift'),
                'export': ['All_users'],
                'spread': 'spread_lms_acc',
                },
    }


class Fronter(object):
    STATUS_ADD = 1
    STATUS_UPDATE = 2
    STATUS_DELETE = 3

    ROLE_READ = '01'
    ROLE_WRITE = '02'
    ROLE_DELETE = '03'
    ROLE_CHANGE = '07'

    def __init__(self, db, const, logger=None):
        self.db = db
        self.const = const
        self.logger = logger
        _config = host_config['ovgs.no']
        self.export = _config.get('export')
        self.spread = _config.get('spread', None)
        self.groups = self.get_groups_from_xml(infile)
        self.s_nodes = self.std_school_nodes()
        self.std_grp_nodes = self.std_grp_nodes()
        self.std_f_e_nodes = self.std_nodes()
        self.uname2extid = self.uname2ext_id_fnr()

    def uname2ext_id_fnr(self):
        person = Factory.get("Person")(self.db)
        const = Factory.get("Constants")(self.db)
        uname2ext_id = {}
        ext_id2uname = person.getdict_external_id2primary_account(const.externalid_fodselsnr)
        for k, v in ext_id2uname.iteritems():
            uname2ext_id[v] = k
        return uname2ext_id

    def std_nodes(self):
        ret = []
        title = group_id = parent_id = ""
        schools = ('ASKI', 'BORG', 'FRED', 'GLEM', 'GREA',
                   'HALD', 'KALN', 'KIRK', 'MALA', 'MYSE',
                   'STOL', 'BORGTF', 'BORGRESS')

        for s in schools:
            tmp = {'title': s + ' vgs - klasser samlet',
                   'group_id': s + 'Students',
                   'parent_id': s + 'Groups'}
            ret.append(tmp)
        for s in schools:
            tmp = {'title': s + ' Faggrupper',
                   'group_id': s + 'faggrupper',
                   'parent_id': s + 'Groups'}
            ret.append(tmp)
        for s in schools:
            tmp = {'title': 'Alle elever' + ' ' + s,
                   'group_id': s + 'all_students',
                   'parent_id': s + 'Groups'}
            ret.append(tmp)
        for s in schools:
            tmp = {'title': 'Ansatte' + ' ' + s,
                   'group_id': s + 'Employees',
                   'parent_id': s + 'Groups'}
            ret.append(tmp)            
        return ret

    def std_grp_nodes(self):
        ret = []
        title = group_id = parent_id = ""
        schools = ('ASKI', 'BORG', 'FRED', 'GLEM', 'GREA',
                   'HALD', 'KALN', 'KIRK', 'MALA', 'MYSE',
                   'STOL', 'BORGTF', 'BORGRESS')
        for s in schools:
            tmp = {'title': s + ' vgs - standargrupper',
                   'group_id': s + 'Groups', 
                   'parent_id': s}
            ret.append(tmp)
        return ret
    
    def std_school_nodes(self):
        ret = []
        title = group_id = parent_id = ""
        schools = ('ASKI', 'BORG', 'FRED', 'GLEM', 'GREA',
                   'HALD', 'KALN', 'KIRK', 'MALA', 'MYSE',
                   'STOL', 'BORGTF', 'BORGRESS')

        for s in schools:
            tmp = {'title': s + ' vgs',
                   'group_id': s,
                   'parent_id': 'root'}
            ret.append(tmp)
        return ret    
    
    def get_frontergroups_names(self):
        group = Factory.get("Group")(self.db)
        ret = []
        for e in group.list_all_with_spread(self.const.spread_oid_grp):
            group.clear()
            group.find(e['entity_id'])
            tmp = {'title': group.group_name,
                   'group_id': group.group_name,
                   'parent_id': None}
            ret.append(tmp)
        return ret

    def get_groups_from_xml(self, infile):
        xmliter = ABCFactory.get('EntityIterator')(infile, 'group')
        g_parser = ABCFactory.get('GroupParser')(xmliter)
        ret = []
        tmp_name = school = year = fk = nk = ""
        for group in g_parser:
            nk = group._ids.values()[0]
            fk = group._ids.keys()[0]
            school, year, tmp_name = nk.split(':')
            if tmp_name == "":
                logger.warn("Invalid name for group (%s):%s" % (fk, school))
                continue
            write_name = school + ':' + tmp_name
            tmp = {'g_type': fk,
                   'g_name': write_name}
            ret.append(tmp)
        return ret

    def pwd(self, p):
        pwtype, password = p.split(":")
        type_map = {'md5': 1,
                    'unix': 2,
                    'nt': 3,
                    'plain': 4,
                    'ldap': 5}
        ret = {'pwencryptiontype': 'ldap1:'} #type_map['ldap1]}
        return ret
    
    def useraccess(self, access):
        # TODO: move to config section
        mapping = {
            # Not allowed to log in
            0: 'None',
            # Normal user
            'viewmygroups': 'User',
            'allowlogin': 'User',
            # Admin
            'administrator': 'SysAdmin',
            }
        return mapping[access]

class FronterXML(object):
    def __init__(self, fname, cf_dir=None, debug_file=None, debug_level=None,
                 fronter=None, include_password=True):
        self.xml = XMLWriter(fname)
        self.xml.startDocument(encoding='ISO-8859-1')
        self.rootEl = 'enterprise'
        self.DataSource = 'OVGS-Cerebrum'
        self.cf_dir = cf_dir
        self.debug_file = debug_file
        self.debug_level = debug_level
        self.fronter = fronter
        self.include_password = include_password

    def start_xml_file(self):
        self.xml.comment("Eksporterer data...")
        self.xml.startTag(self.rootEl)
        self.xml.startTag('properties')
        self.xml.dataElement('datasource', self.DataSource)
        self.xml.dataElement('target', "ClassFronter/Østfold")
        self.xml.dataElement('datetime', time.strftime("%F %T %z"))
        self.xml.endTag('properties')

    def user_to_XML(self, id, userid, recstatus, data):
        """Lager XML for en person"""
        self.xml.startTag('person', {'recstatus': recstatus})
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', id)
        self.xml.endTag('sourcedid')
        if self.include_password:
            self.xml.dataElement('userid', userid,
                                 self.fronter.pwd(data['PASSWORD']))
        self.xml.startTag('name')
        self.xml.dataElement('fn',
                             " ".join([x for x in (data['GIVEN'],
                                                   data['FAMILY'])
                                       if x]))
        self.xml.startTag('n')
        self.xml.dataElement('family', data['FAMILY'])
        self.xml.dataElement('given', data['GIVEN'])
        self.xml.endTag('n')
        self.xml.endTag('name')
        self.xml.dataElement('email', data['EMAIL'])
        self.xml.emptyTag('systemrole',
                          {'systemroletype':
                           fronter.useraccess(data['USERACCESS'])})
        self.xml.endTag('person')

    def group_to_XML(self, id, recstatus, data, type):
        # Lager XML for en gruppe
        self.xml.startTag('group', {'recstatus': recstatus})
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', id)
        self.xml.endTag('sourcedid')
        self.xml.startTag('grouptype')
        self.xml.dataElement('scheme', 'FronterStructure1.0')
        self.xml.emptyTag('typevalue', {'level': type})
        self.xml.endTag('grouptype')
        self.xml.startTag('description')
        if (len(data['title']) > 60):
            self.xml.emptyTag('short')
            self.xml.dataElement('long', data['title'])
        else:
            self.xml.dataElement('short', data['title'])
        self.xml.endTag('description')
        self.xml.startTag('relationship', {'relation': 1})
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', data['parent'])
        self.xml.endTag('sourcedid')
        self.xml.endTag('relationship')
        self.xml.endTag('group')


    def personmembers_to_XML(self, gid, recstatus, members):
        # lager XML av medlemer
        self.xml.startTag('membership')
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', gid)
        self.xml.endTag('sourcedid')
        for fnr in members:
            self.xml.startTag('member')
            self.xml.startTag('sourcedid')
            self.xml.dataElement('source', self.DataSource)
            self.xml.dataElement('id', str(fnr))
            self.xml.endTag('sourcedid')
            # This is a person member (as opposed to a group).
            self.xml.dataElement('idtype', '1')
            self.xml.startTag('role', {'recstatus': recstatus,
                                       'roletype': Fronter.ROLE_READ})
            self.xml.dataElement('status', '1')
            self.xml.startTag('extension')
            # Member of group, not room.
            self.xml.emptyTag('memberof', {'type': 1})
            self.xml.endTag('extension')
            self.xml.endTag('role')
            self.xml.endTag('member')
        self.xml.endTag('membership')

    def end(self):
        self.xml.endTag(self.rootEl)
        self.xml.endDocument()


class IMS_object(object):
    def __init__(self, objtype, **data):
        self.objtype = objtype
        self.data = data.copy()

    def dump(self, xml, recstatus):
        dumper = getattr(self, 'dump_%s' % self.objtype, None)
        if dumper is None:
            raise NotImplementedError, \
                  "Can't dump IMS object of type %s" % (self.objtype,)
        dumper(xml, recstatus)

    def attr_dict(self, required=(), optional=()):
        data = self.data.copy()
        res = {}
        for a in required:
            try:
                res[a] = data.pop(a)
            except KeyError:
                raise ValueError, \
                      "Required <%s> attribute %r not present: %r" % (
                    self.objtype, a, self.data)
        for a in optional:
            if a in data:
                res[a] = data.pop(a)
        # Remaining values in ``data`` should be either sub-objects or
        # DATA.
        return res


class IMSv1_0_object(IMS_object):
    def dump_comments(self, xml, recstatus):
        lang = getattr(self, 'lang', None)
        xml.dataElement('COMMENTS', self.DATA, self.attr_dict())

    def dump_properties(self, xml, recstatus):
        xml.startTag('PROPERTIES', self.attr_dict(optional=('lang',)))
        # TODO: Hva med subelementer som kan forekomme mer enn en gang?
        for subel in ('DATASOURCE', 'TARGET', 'TYPE', 'DATETIME', 'EXTENSION'):
            if subel in self.data:
                self.data[subel].dump(xml, recstatus)
        xml.endTag('PROPERTIES')


def init_globals():
    global db, const, logger, group, users_only
    db = Factory.get("Database")()
    const = Factory.get("Constants")(db)
    group = Factory.get("Group")(db)
    logger = Factory.get_logger("cronjob")

    cf_dir = '/cerebrum/dumps/Fronter'
    try:
        opts, args = getopt.getopt(sys.argv[1:], '',
                                   ['debug-file=', 'debug-level=',
                                    'cf-dir=',
                                     ])
    except getopt.GetoptError:
        usage(1)
    debug_file = os.path.join(cf_dir, "x-import.log")
    debug_level = 4
    set_pwd = True
    users_only = False 

    for opt, val in opts:
        if opt == '--debug-file':
            debug_file = val
        elif opt == '--debug-level':
            debug_level = val
        elif opt == '--uten-passord':
            set_pwd = False
        elif opt == '--cf-dir':
            cf_dir = val
        else:
            raise ValueError, "Invalid argument: %r", (opt,)

    global fronter

    fronter = Fronter(db, const, logger=logger)

    filename = os.path.join(cf_dir, 'test.xml')
    if len(args) == 1:
        filename = args[0]
    elif len(args) <> 0:
        usage(2)

    global fxml
    fxml = FronterXML(filename,
                      cf_dir = cf_dir,
                      debug_file = debug_file,
                      debug_level = debug_level,
                      fronter = fronter,
                      include_password = set_pwd)

    # Finn `uname` -> account-data for alle brukere.
    global new_users
    new_users = get_new_users()


def list_users_for_fronter_export():  
    ret = []
    email_addr = ""
    account = Factory.get("Account")(db)
    person = Factory.get("Person")(db)
    constants = Factory.get("Constants")(db)
    for row in account.list_all_with_spread(const.spread_lms_acc):
        account.clear()
        account.find(row['entity_id'])
        try:
            email_addr = account.get_primary_mailaddress()
        except Errors.NotFoundError:
            logger.error("No primary address for %s", account.account_name)
            email_addr = "N/A"
        person.clear()
        person.find(account.owner_id)
        pwd = account.get_account_authentication(constants.auth_type_md5_unsalt)
        tmp = {'email': email_addr,
               'uname': account.account_name,
               'fullname': person.get_name(const.system_cached, const.name_full),
               'pwd': pwd}
        ret.append(tmp)
    return ret

def get_new_users():
    # Hent info om brukere i cerebrum
    users = {}
    for user in list_users_for_fronter_export():
        # lagt inn denne testen fordi scriptet feilet uten, har en liten
        # følelse av det burde løses på en annen måte
        if user['fullname'] is None:
            continue
        names = re.split('\s+', user['fullname'].strip())
        user_params = {'FAMILY': names.pop(),
                       'GIVEN': " ".join(names),
                       'EMAIL': user['email'],
                       'USERACCESS': 0,
                       'PASSWORD': 'ldap:dummy' #% user['pwd'],
                       }

        if 'All_users' in fronter.export:
            if fronter.uname2extid.has_key(user['uname']):
                fnr = fronter.uname2extid[user['uname']]
                new_groupmembers.setdefault('All_users',
                                            {}) [fnr] = 1
            else:
                logger.info("Could not find id for %s", user['uname'])
                continue
            user_params['USERACCESS'] = 'allowlogin'
        users[user['uname']] = user_params

    logger.debug("get_new_users returns %i users", len(users))
    return users

new_groupmembers = {}
def update_elev_ans_groups():
    db = Factory.get("Database")()
    ou = Factory.get("OU")(db)
    person = Factory.get("Person")(db)
    const =  Factory.get("Constants")(db)
    sted = {}
    elever = {}
    ansatte = {}
    ret = []
    
    schools = ('ASKI', 'BORG', 'FRED', 'GLEM', 'GREA',
               'HALD', 'KALN', 'KIRK', 'MALA', 'MYSE',
               'STOL', 'BORGTF', 'BORGRESS')
    for s in schools:
        ou.clear()
        sted = ou.search(acronym=s)
        elever = person.list_affiliations(affiliation=const.affiliation_elev,
                                          ou_id=sted[0]['ou_id'])
        ansatte = person.list_affiliations(affiliation=const.affiliation_ansatt,
                                           ou_id=sted[0]['ou_id'])
        elev_group_id = s + 'all_students'
        ans_group_id = s + 'Employees'
        for e in elever:
            person.clear()
            person.find(e['person_id'])
            fnr = person.get_external_id(source_system=const.system_ekstens,
                                         id_type=const.externalid_fodselsnr)
            ret.append({'group_id': elev_group_id,
                        'member_id': fnr[0][2]})
        for a in ansatte:
            person.clear()
            person.find(a['person_id'])
            fnr = person.get_external_id(source_system=const.system_ekstens,
                                         id_type=const.externalid_fodselsnr)
            ret.append({'group_id': ans_group_id,
                        'member_id': fnr[0][2]})
        
    return ret
            
new_group = {}
def register_group(type, title):
    """Adds info in new_group about group."""
    parent_id = group_id = ""
    pid, rest = title.split(':')
    if type == 'GRP_ID_KLID':
        parent_id = pid + 'Students'
    elif type == 'GRP_ID_FGID':
        parent_id = pid + 'faggrupper'            
    group_id = pid + rest
    new_group[group_id] = {'title': rest,
                           'parent': parent_id,
                           }

new_school_nodes = {}
def register_school_nodes(title, group_id, parent_id):
    new_school_nodes[group_id] = {'title': title,
                                  'parent': parent_id}
def usage(exitcode):
    print "Usage: generate_fronter_full.py OUTPUT_FILENAME"
    sys.exit(exitcode)


def main():
    # Håndter upper- og lowercasing av strenger som inneholder norske
    # tegn.
    locale.setlocale(locale.LC_CTYPE, ('en_US', 'iso88591'))
    
    elev_ans_grupper = {}
    elev_ans_grupper = update_elev_ans_groups()


    init_globals()

    fxml.start_xml_file()

    # Spytt ut <person>-elementene.
    for uname, data in new_users.iteritems():
        if fronter.uname2extid.has_key(uname):
            fnr = fronter.uname2extid[uname]
            fxml.user_to_XML(fnr, uname, fronter.STATUS_ADD, data)
        else:
            logger.warn("Could not find extid for %s", uname)

    for n in fronter.s_nodes:
        register_school_nodes(n['title'], n['group_id'], n['parent_id'])
    for s in fronter.std_grp_nodes:
        register_school_nodes(s['title'], s['group_id'], s['parent_id'])
    for k in fronter.std_f_e_nodes:
        register_school_nodes(k['title'], k['group_id'], k['parent_id'])

    for g in fronter.groups:
        fnr = None
        register_group(g['g_type'], g['g_name'])
        group.clear()
        try:
            group.find_by_name(g['g_name'])
        except Errors.NotFoundError:
            logger.warn("Could not find group %s in Cerebrum", g['g_name'])
            continue
        for row in \
                group.list_members(member_type = const.entity_account,
                                   get_entity_name = True)[0]:
            if fronter.uname2extid.has_key(row[2]):
                fnr = fronter.uname2extid[row[2]]
                tmp1, tmp2 = group.group_name.split(':')
                grp_name = tmp1 + tmp2
                new_groupmembers.setdefault(grp_name,
                                            {})[fnr] = 1
            else:
                logger.warn("Could not find fnr for %s", row[2])

    all_users_dat = {'title': 'All_users',
                     'parent': 'root'}
    fxml.group_to_XML('All_users', fronter.STATUS_ADD, all_users_dat, 2)

    for gname, data in new_school_nodes.iteritems():
        if re.search('all_students', gname) or re.search('Employees', gname):
            fxml.group_to_XML(gname, fronter.STATUS_ADD, data, 2)
        else:
            fxml.group_to_XML(gname, fronter.STATUS_ADD, data, 0)
        
    for gname, data in new_group.iteritems():
        fxml.group_to_XML(gname, fronter.STATUS_ADD, data, 2)

    for e in elev_ans_grupper:
        new_groupmembers.setdefault(e['group_id'],
                                    {})[e['member_id']] = 1
        
    for gname, members_as_dict in new_groupmembers.iteritems():
        fxml.personmembers_to_XML(gname, fronter.STATUS_UPDATE,
                                  members_as_dict.keys())
    fxml.end()


if __name__ == '__main__':
    main()

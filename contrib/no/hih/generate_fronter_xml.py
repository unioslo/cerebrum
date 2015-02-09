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
from Cerebrum.Utils import AtomicFileWriter, SimilarSizeWriter
from Cerebrum.modules.no.uio.fronter_lib import XMLWriter

from Cerebrum.modules.no.hih.access_FS import FS

cf_dir = '/cerebrum/hih/dumps/Fronter'

db = const = logger = None 
fronter = fxml = None
new_users = None


host_config = {
    'hih.no': {'DBinst': 'hihfronter',
               'admins': 'fronter-admins',
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
        _config = host_config['hih.no']
        self.export = _config.get('export')
        self.spread = _config.get('spread', None)
        self.groups = self.get_frontergroups_names()
        self.s_nodes = self.std_inst_nodes()
        self.uname2extid = self.uname2ext_id_fnr()

    def uname2ext_id_fnr(self):
        """Return a dict with mappings of fnr to primary accounts. This
        includes all persons in the database, not only students.
        """
        person = Factory.get("Person")(self.db)
        const = Factory.get("Constants")(self.db)
        uname2ext_id = {}
        ext_id2uname = person.getdict_external_id2primary_account(const.externalid_fodselsnr)
        for k, v in ext_id2uname.iteritems():
            uname2ext_id[v] = k
        return uname2ext_id

    def std_inst_nodes(self):
        ret = []
        title = group_id = parent_id = ""
        institutter = ('220000', '230000')

        for i in institutter:
            tmp = {'title': 'Alle studenter på ' + ' ' + i,
                   'group_id': 'stud-' + i,
                   'parent_id': '99 NO-FS Studenter importert fra FS', #'root', #'Groups' + ' ' + i,
                   'typeval': ''}
            ret.append(tmp)

        for i in institutter:
            tmp = {'title': 'Alle ansatte på' + ' ' + i,
                   'group_id': 'ans-' + i,
                   'parent_id': '98 NO-FS Ansatte importert fra FS', #'root', #'Groups' + ' ' + i,
                   'typeval': ''}
            ret.append(tmp)
        return ret

    #def std_studieprog_nodes(self):
    #    ret = []
    #    title = group_id = parent_id = ""

    #    for x in fs.info.list_studieprogrammer():
    #        inst =  "%02d" % int(x['faknr_studieansv'])
    #        if inst == '22':
    #            parent_id = '220000'
    #        elif inst = '23':
    #            parent_id = '230000'
    #        else:
    #            parent_id = 'root'
    #        tmp = {'title': 'Studieprogram ' + ' ' + x['studieprogramkode'],
    #               'group_id': 'studieprog-' + , x['studieprogramkode']
    #               'parent_id': parent_id,
    #               'typeval': 'STUDIEPROGRAM'}
    #        ret.append(tmp)
    
    def get_frontergroups_names(self):
        """Get a list of all LMS groups' names and descriptions."""
        group = Factory.get("Group")(self.db)
        ret = []
        for e in group.list_all_with_spread(self.const.spread_lms_group):
            group.clear()
            group.find(e['entity_id'])
            if not group.group_name:
                continue
            tmp = {'title': group.description,
                   'group_id': group.group_name,
                   'parent_id': None}
            ret.append(tmp)
        return ret

    def pwd(self, p):
        pwtype, password = p.split(":")
        type_map = {'md5': 1,
                    'unix': 2,
                    'nt': 3,
                    'plain': 4,
                    'ldap': 5}
        ret = {'pwencryptiontype': 'ldap1:'} 
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
        self.DataSource = 'HiH-Cerebrum'
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
        self.xml.dataElement('target', "Fronter/HiH")
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
        self.xml.emptyTag('institutionrole',
                          {'institutionroletype': data['INSTROLETYPE']})
        self.xml.startTag('adr')
        self.xml.dataElement('street', data['STREET'])
        self.xml.dataElement('pcode', data['ZIP'])
        self.xml.dataElement('locality', data['LOCALITY'])
        self.xml.dataElement('country', data['COUNTRY'])                
        self.xml.endTag('adr')
        self.xml.dataElement('tel', data['MOBILE'], {'teltype': 3})
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
        self.xml.dataElement('typevalue', data['typeval'], {'level': type})
        self.xml.endTag('grouptype')
        self.xml.startTag('description')
        description = data.get("description", data["title"])
        if (len(description) > 60):
            self.xml.emptyTag('short')
            self.xml.dataElement('long', description)
        else:
            self.xml.dataElement('short', description)
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
        for fnr in members.keys():
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
            self.xml.dataElement('subrole', members[fnr])
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
    global db, const, logger, group, users_only, ou, person
    db = Factory.get("Database")()
    const = Factory.get("Constants")(db)
    group = Factory.get("Group")(db)
    person = Factory.get("Person")(db)
    ou = Factory.get("OU")(db)
    logger = Factory.get_logger("cronjob")

    fsdb = Database.connect(user='I0208_cerebrum',
                            service=cereconf.FS_DATABASE_NAME,
                            DB_driver='cx_Oracle') 
    fs = FS(fsdb)

    cf_dir = '/cerebrum/hih/dumps/Fronter'
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
    elif len(args) != 0:
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
    """Gather information about all users with the LMS spread.

    The information is gathered to be exported to the LMS system.

    """
    ret = []
    account = Factory.get("Account")(db)
    person = Factory.get("Person")(db)
    for row in account.list_all_with_spread(const.spread_lms_account):
        account.clear()
        account.find(row['entity_id'])
        try:
            email_addr = account.get_primary_mailaddress()
        except Errors.NotFoundError:
            logger.error("No primary address for %s", account.account_name)
            email_addr = "N/A"
        person.clear()
        try:
            person.find(account.owner_id)
        except Errors.NotFoundError:
            logger.error("Account %s is impersonal, but has lms spread.",
                         account.account_name)
            continue
        mobile = street = zip = city = locality = ''
        country = 'Norge'
        for a in person.get_affiliations():
            if a['affiliation'] == int(const.affiliation_student):
                tmp = [x["contact_value"] for x in
                       person.get_contact_info(source=const.system_fs,
                                               type=const.contact_mobile_phone)]
                if tmp:
                    mobile = tmp[0]
                else:
                    logger.debug("No mobile for user '%s'" % account.account_name)

                addr = person.get_entity_address(source=const.system_fs, type=const.address_post)
                if addr:
                    address = addr[0]
                    alines = address['address_text'].split("\n")+[""]
                    street = alines[0] + '\n' + alines[1]
                    if str(address['city']):
                        #city = str(address['city'])
                        locality = str(address['city'])
                    if str(address['postal_number']):
                        zip = str(address['postal_number'])
                    if address['country']:
                        country = str(address['country'])
                else:
                    logger.debug("No addr for user '%s'" % account.account_name)
        roletype = 'Student'

        # Employees and affiliated gets overridden:
        for a in person.get_affiliations():
            if (a['affiliation'] == int(const.affiliation_ansatt) or
                    a['affiliation'] == int(const.affiliation_tilknyttet)):
                roletype = 'Staff'
                mobile = ''

        tmp = {'email': email_addr,
               'uname': account.account_name,
               'fullname': person.get_name(const.system_cached, 
                                           const.name_full),
               'mobile': mobile,
               'roletype': roletype,
               'street': street,
               'zip': zip,
               'city': city,
               'locality': locality,
               'country': country}
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
                       #'USERACCESS': 'User',
                       'PASSWORD': 'ldap1:', 
                       'INSTROLETYPE': user['roletype'],
                       'MOBILE': user['mobile'],
                       'STREET': user['street'],
                       'ZIP': user['zip'],
                       #'CITY': user['city'],
                       'LOCALITY': user['locality'],
                       'COUNTRY': user['country']
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

new_group = {}
def register_group(title, desc):
     """Adds info in new_group about group."""
     pid, rest = title.split('-', 1)
     parent_id = '99 NO-FS Studenter importert fra FS'
     new_group[title] = {'title': desc,
                         'parent': parent_id,
                         'description': title,
                         'typeval': ''
                         }

new_inst_nodes = {}
def register_inst_nodes(title, group_id, parent_id, typeval):
    new_inst_nodes[group_id] = {'title': title,
                                'parent': parent_id,
                                'typeval': typeval}

def usage(exitcode):
    print "Usage: generate_fronter_full.py OUTPUT_FILENAME"
    sys.exit(exitcode)

def main():
    # Håndter upper- og lowercasing av strenger som inneholder norske
    # tegn.
    locale.setlocale(locale.LC_CTYPE, ('en_US', 'iso88591'))
    
    init_globals()

    fxml.start_xml_file()

    # Spytt ut <person>-elementene.
    for uname, data in new_users.iteritems():
        if fronter.uname2extid.has_key(uname):
            fnr = fronter.uname2extid[uname]
            fxml.user_to_XML(fnr, uname, fronter.STATUS_ADD, data)
        else:
            logger.warn("Could not find extid for %s", uname)

    #for n in fronter.s_nodes:
    #    register_inst_nodes(n['title'], n['group_id'], n['parent_id'], n['typeval'])
    #for s in fronter.studieprog_nodes:
    #    register_inst_nodes(s['title'], s['group_id'], s['parent_id'], s['typeval'])
    # for k in fronter.std_f_e_nodes:
    #     register_school_nodes(k['title'], k['group_id'], k['parent_id'], k['typeval'])

    logger.debug("preloading entity names...")
    entity2name = dict((x["entity_id"], x["entity_name"]) for x in 
                       group.list_names(const.account_namespace))
    entity2name.update((x["entity_id"], x["entity_name"]) for x in
                       group.list_names(const.group_namespace))
    logger.debug("done")
    for g in fronter.groups:
        fnr = None
        register_group(g['group_id'], g['title'])
        group.clear()
        try:
            group.find_by_name(g['group_id'])
        except Errors.NotFoundError:
            logger.warn("Could not find group %s in Cerebrum", g['group_id'])
            continue
        logger.debug("Gathering group: %s", group.group_name)
        for row in group.search_members(group_id=group.entity_id,
                                        member_type=const.entity_account):
            member_id = int(row["member_id"])
            if member_id not in entity2name:
                logger.warn("No name for member id=%s of group %s %s",
                            member_id, group.group_name, group.entity_id)
                continue
            member_name = entity2name[member_id]
            if fronter.uname2extid.has_key(member_name):
                fnr = fronter.uname2extid[member_name]
                #tmp1, tmp2 = group.group_name.split('-', 1)
                #grp_name = tmp1 + tmp2
                new_groupmembers.setdefault(group.group_name,
                                            {})[fnr] = 1
            else:
                logger.warn("Could not find fnr for %s", member_name)

    # trying to sort the xml-file as the fronters import machinery requires sorted XML
    for gname, data in new_inst_nodes.iteritems():
        fxml.group_to_XML(gname, fronter.STATUS_ADD, data, 0)
    
    all_users_dat = {'title': 'All_users',
                     'parent': 'root',
                     'typeval': 'ALLE'}
    fxml.group_to_XML('All_users', fronter.STATUS_ADD, all_users_dat, 2)

    for gname, data in new_group.iteritems():
        fxml.group_to_XML(gname, fronter.STATUS_ADD, data, 2)

    for gname, members_as_dict in new_groupmembers.iteritems():
        members = {}
        for m in members_as_dict:
            members[m] = 'user'
        fxml.personmembers_to_XML(gname, fronter.STATUS_UPDATE,
                                  members)

    fxml.end()


if __name__ == '__main__':
    main()

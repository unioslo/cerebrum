#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

__copyright__ = """Copyright 2008 University of Oslo, Norway

This file is part of Cerebrum.

Cerebrum is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

Cerebrum is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License
along with Cerebrum; if not, write to the Free Software Foundation,
Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""

# $Id$

import sys
import time

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.access_FS import make_fs
from Cerebrum.modules.xmlutils.GeneralXMLWriter import XMLWriter
from Cerebrum.Errors import NotFoundError

__doc__ = """
This is a nice module that you should use correctly.

"""

__version__ = "$Revision$"


db = Factory.get('Database')()
constants = Factory.get("Constants")(db)
logger = Factory.get_logger("cronjob")


def get_members(group_name):
    db = Factory.get("Database")()
    group = Factory.get("Group")(db)
    usernames = ()
    try:
        group.find_by_name(group_name)
    except NotFoundError:
        pass
    else:
        members = group.get_members(get_entity_name=True)
        usernames = tuple([x[1] for x in members])
    return usernames



class LMSExport(object):
    """Generic superclass for handling export of information for LMS
    purposes.

    Not meant for instantiation directly; clients should instead
    retrieve the proper importer by way of the Cerebrum Factory
    
    """

    def __init__(self):
        self.students = {}
        self.faculty = {}
        self.user_entity_id2fnr = {}
        self.user_entity_id2account = {}
        

    def gather_person_information(self, entity_id=None, fnr=None):
        person = Factory.get("Person")(db)
        account = Factory.get("Account")(db)
        data = {}

        person.clear()
        
        if entity_id is not None:
            person.find(entity_id)
        elif fnr is not None:
            try:
                person.find_by_external_id(constants.externalid_fodselsnr, fnr)
            except Errors.NotFoundError:
                logger.warning("Unable to find person with FNR '%s'" % fnr)
                return None
        else:
            raise ValueError("No valid identifier to identify person by")
        
        data["full_name"] = person.get_name(constants.system_cached, constants.name_full)
        data["family_name"] = person.get_name(constants.system_cached, constants.name_last)
        data["given_name"] = person.get_name(constants.system_cached, constants.name_first)
        data["birth_date"] = str(person.birth_date)[:10]
        fnr_data = person.get_external_id(id_type=constants.externalid_fodselsnr)
        data["fnr"] = fnr_data[0]["external_id"]
        data["gender"] = str(constants.Gender(person.gender))
        
        primary_account_id = person.get_primary_account()
        if primary_account_id is None:
            # Only identify people by FNR if no entity_id available
            if entity_id is None:
                identifier = "fnr:'%s'" % fnr
            else:
                identifier = "ent_id:'%s'" % entity_id
            logger.info("Primary account is None for person: %s. Ignoring person" % identifier)
            return None

        account.find(primary_account_id)
        data["username"] = account.get_account_name()

        try:
            data["email"] = account.get_contact_info(type=constants.contact_email)[0]["contact_value"]
        except IndexError:
            if entity_id is None:
                identifier = "fnr:'%s'" % fnr
            else:
                identifier = "ent_id:'%s'" % entity_id
            logger.warning("Email not found for person:%s account:%s. Exporting without email" % (
                identifier, primary_account_id))
            data["email"] = None

        self.user_entity_id2fnr[primary_account_id] = data["fnr"]
        self.user_entity_id2account[primary_account_id] = data["username"]

        return data
        

    def gather_student_information(self):
        logger.debug("gather_student_information start")
        fs = make_fs()
        students = fs.student.list_aktiv()
        person = Factory.get('Person')(db)

        for student in students:
            #person.clear()
            fnr = "%06d%05d" % (int(student['fodselsdato']), int(student['personnr']))
            student_data = self.gather_person_information(fnr=fnr)
            if student_data is not None:
                self.students[fnr] = student_data
        logger.debug("gather_student_information done")
            

    def gather_faculty_information(self):
        logger.debug("gather_faculty_information start")
        person = Factory.get('Person')(db)
        employees = person.list_affiliations(affiliation=constants.affiliation_ansatt)
        for employee in employees:
            try:
                employee_data =  self.gather_person_information(entity_id=employee["person_id"])
                if employee_data is None:
                    continue
            except Errors.NotFoundError:
                #Unable to find because of missing fnr in database?
                logger.warning("Unable to find person info for id '%s'" % employee["person_id"])
                continue
            fnr = employee_data["fnr"]
            self.faculty[fnr] = employee_data
        logger.debug("gather_faculty_information done")
        
    

    def gather_people_information(self):
        logger.debug("gather_people_information start")
        self.gather_student_information()
        self.gather_faculty_information()
        # People who are faculty, should not be students
        for student_fnr in self.students.keys():
            if student_fnr in self.faculty:
                logger.debug("Student '%s' also designated as faculty. Deleting from students" % student_fnr)
                del self.students[student_fnr]
        logger.debug("gather_people_information done")


class ILExport(LMSExport):
    """Class for handling export to It's Learning."""

    gender_values = {"F": "1",
                     "M": "2",
                     "X": None}
    "This contains the mapping from Cerebrum's gender-codes to It's Learning's."

    def __init__(self, output=None):
        LMSExport.__init__(self)
        self.xml = XMLWriter(output)
        self.xml.startDocument(encoding="ISO-8859-1")
        self.xml.notationDecl("enterprise",
                              public_id="IMS Enterprise/LMS Interoperability DTD",
                              system_id="http://www.fs.usit.uio.no/DTD/ims_epv1p1.dtd")
        self.rootEl = 'enterprise'
        self.DataSource = 'Cerebrum'
        logger.debug("ItsLearningexport initialized")


    def begin(self):
        self.xml.startTag(self.rootEl)
        self.xml.startTag('properties', {'lang': 'NO'})
        self.xml.dataElement('datasource', self.DataSource)
        self.xml.dataElement('datetime', time.strftime("%F"))
        self.xml.endTag('properties')

        # Need to have root-group defined
        self.xml.startTag('group', {'recstatus': 1})
        
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', self.IDstcode)
        self.xml.endTag('sourcedid')

        self.xml.startTag('grouptype')
        self.xml.dataElement('scheme', 'NO-FS', {'level': 0})
        self.xml.dataElement('typevalue', 'Sted')
        self.xml.endTag('grouptype')

        self.xml.startTag('description')
        self.xml.dataElement('short', self.IDshort)
        self.xml.dataElement('long', self.ID)
        self.xml.dataElement('full', self.ID)
        self.xml.endTag('description')

        self.xml.startTag('org')
        self.xml.dataElement('orgname', self.ID)
        self.xml.dataElement('orgunit', self.ID)
        self.xml.dataElement('type', self.org_type)
        self.xml.dataElement('id', self.IDcode)
        self.xml.endTag('org')

        self.xml.dataElement('email', "")
        self.xml.dataElement('url', "")

        self.xml.startTag('relationship', {'relation': 1})
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', self.IDstcode)
        self.xml.endTag('sourcedid')
        self.xml.dataElement('label', 'Sted')
        self.xml.endTag('relationship')
        
        self.xml.endTag('group')
        
        
    def end(self):
        self.xml.endTag(self.rootEl)
        self.xml.endDocument()


    def group_to_xml(self, id, grouptype, parentcode,
                     grouptype_level=None, nameshort="", namelong="", namefull=""):
        self.xml.startTag('group', {'recstatus': 1})
        
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', id)
        self.xml.endTag('sourcedid')

        self.xml.startTag('grouptype')
        self.xml.dataElement('scheme', "NO-FS")
        level = {}
        if grouptype_level is not None:
            level["level"] = grouptype_level
        self.xml.dataElement('typevalue', grouptype, level)
        self.xml.endTag('grouptype')

        self.xml.startTag('description')
        self.xml.dataElement('short', nameshort)
        self.xml.dataElement('long', namelong)
        self.xml.dataElement('full', namefull)
        self.xml.endTag('description')

        self.xml.startTag('org')
        self.xml.dataElement('orgname', self.ID)
        self.xml.dataElement('orgunit', self.ID)
        self.xml.dataElement('type', self.org_type)
        self.xml.dataElement('id', self.IDcode)
        self.xml.endTag('org')

        self.xml.dataElement('email', "")
        self.xml.dataElement('url', "")

        self.xml.startTag('relationship', {'relation': 1})
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', parentcode)
        self.xml.endTag('sourcedid')
        self.xml.dataElement('label', grouptype)
        self.xml.endTag('relationship')

        self.xml.endTag('group')


    def export_people(self):
        self.export_students()
        self.export_faculty()


    def export_faculty(self):
        for fnr in self.faculty.keys():
            faculty = self.faculty[fnr]
            sort_name = "%s %s" % (faculty["family_name"], faculty["given_name"])
            logger.debug("Exporting data for person with username '%s'" % faculty["username"])
            self.person_to_xml(faculty["username"], account_name=faculty["username"],
                               institution_roletype="Faculty",
                               full_name=faculty["full_name"], sort_name=sort_name,
                               family_name=faculty["family_name"], given_name=faculty["given_name"],
                               gender=faculty["gender"], email=faculty["email"],
                               birth_date=faculty["birth_date"])
    


    def export_students(self):
        for fnr in self.students.keys():
            student = self.students[fnr]
            sort_name = "%s %s" % (student["family_name"], student["given_name"])
            logger.debug("Exporting data for person with username '%s'" % student["username"])
            self.person_to_xml(student["username"], account_name=student["username"],
                               institution_roletype="Student",
                               full_name=student["full_name"], sort_name=sort_name,
                               family_name=student["family_name"], given_name=student["given_name"],
                               gender=student["gender"], email=student["email"],
                               birth_date=student["birth_date"])
    


    def person_to_xml(self, id, account_name="", institution_roletype="Student",
                      full_name="", sort_name="", family_name="", given_name="",
                      gender=None, email=None, birth_date=""):
        self.xml.startTag('person', {'recstatus': 2})
        
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', str(id))
        self.xml.endTag('sourcedid')

        self.xml.dataElement('userid', account_name)

        self.xml.startTag('name')
        self.xml.dataElement('fn', full_name)
        self.xml.dataElement('sort', sort_name)
        self.xml.startTag('n')
        self.xml.dataElement('family', family_name)
        self.xml.dataElement('given', given_name)
        self.xml.endTag('n')
        self.xml.endTag('name')
        
        self.xml.startTag('demographics') # Is this necessary
        if ILExport.gender_values[gender] is not None:
            self.xml.dataElement('gender', ILExport.gender_values[gender])
        self.xml.dataElement('bday', birth_date)
        self.xml.endTag('demographics')

        if email is not None:
            self.xml.dataElement('email', email)
            
##         self.xml.startTag('adr') # May be added when SAP-data is available
##         self.xml.startTag('tel') # May be added when SAP-data is available

        self.xml.emptyTag('institutionrole',
                          {'primaryrole': 'yes',
                           'institutionroletype': institution_roletype})

        self.xml.endTag('person')


    def membership_to_xml(self, id, responsibles, students):

        self.xml.startTag('membership')

        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', str(id))
        self.xml.endTag('sourcedid')

        for member in responsibles:
            self.member_to_xml(member, "02")
        for member in students:
            self.member_to_xml(member, "01")

        self.xml.endTag('membership')



    def member_to_xml(self, id, roletype):
        
        self.xml.startTag('member')
        
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', str(id))
        self.xml.endTag('sourcedid')

        self.xml.dataElement('idtype', "1")

        self.xml.startTag('role', {'roletype': roletype, 'recstatus': "1"})
        self.xml.dataElement('subrole', "")
        self.xml.dataElement('status', "1")
        self.xml.startTag('timeframe')
        self.xml.dataElement('begin', "", {'restrict': '0'})
        self.xml.dataElement('end', "", {'restrict': '0'})
        self.xml.endTag('timeframe')
        self.xml.endTag('role')

        self.xml.endTag('member')


class FronterExport(LMSExport):
    """Class for handling export to Fronter."""

    STATUS_ADD = 1
    STATUS_UPDATE = 2
    STATUS_DELETE = 3

    ROLE_READ = '01'
    ROLE_WRITE = '02'
    ROLE_DELETE = '03'
    ROLE_CHANGE = '07'

    def __init__(self, output=None, include_password=True):
        LMSExport.__init__(self)
        self.output = output
        self.xml = XMLWriter(output)
        self.xml.startDocument(encoding='UTF-8')
        self.rootEl = 'enterprise'
        self.DataSource = 'Cerebrum'
        self.include_password = include_password
        #self.cf_id = self.fronter.fronter_host # TODO: Get this somewhere else
        logger.debug("Fronterexport initialized")


    def pwd(self, p):
        pwtype, password = p.split(":")
        type_map = {'md5': 1,
                    'unix': 2,
                    'nt': 3,
                    'plain': 4,
                    'ldap': 5}
        ret = {'pwencryptiontype': type_map['ldap']}
        if password:
            ret['password'] = password
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


    def start_xml_file(self, kurs):
        self.xml.comment("Eksporterer data om følgende emner:\n  " + 
                         "\n  ".join(kurs))
        self.xml.startTag(self.rootEl)
        self.xml.startTag('properties')
        self.xml.dataElement('datasource', self.DataSource)
        self.xml.dataElement('target', "ClassFronter/")#%s" % self.cf_id)
        # :TODO: Tell Fronter (again) that they need to define the set of
        # codes for the TYPE element.
        # self.xml.dataElement('TYPE', "REFRESH")
        self.xml.dataElement('datetime', time.strftime("%F %T %z"))
        self.xml.endTag('properties')

    begin = start_xml_file

    def user_to_XML(self, id, recstatus, data):
        """Lager XML for en person"""
        self.xml.startTag('person', {'recstatus': recstatus})
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', id)
        self.xml.endTag('sourcedid')
        if self.include_password:
            self.xml.dataElement('userid', id,
                                 self.pwd(data['PASSWORD']))
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
                           self.useraccess(data['USERACCESS'])})
        self.xml.startTag('extension')
        self.xml.emptyTag('emailsettings',
                          {'mail_username': id,
                           'mail_password': 'FRONTERLOGIN',
                           'description': 'UiO-email',
                           'mailserver': 'imap.uio.no',
                           'mailtype': 'imap',
                           'imap_serverdirectory': 'INBOX.',
                           'imap_sentfolder': 'Sent',
                           'imap_draftfolder': 'Drafts',
                           'imap_trashfolder': 'Trash',
                           'use_ssl': 1,
                           'defaultmailbox': 'INBOX',
                           'on_delete_action': 'trash',
                           'is_primary': 1,
                           })
        self.xml.endTag('extension')
        self.xml.endTag('person')


    def group_to_XML(self, id, recstatus, data):
        # Lager XML for en gruppe
        self.xml.startTag('group', {'recstatus': recstatus})
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', id)
        self.xml.endTag('sourcedid')
        self.xml.startTag('grouptype')
        self.xml.dataElement('scheme', 'FronterStructure1.0')
        allow_room = data.get('allow_room', 0)
        allow_contact = data.get('allow_contact', 0)
        # Convert booleans allow_room and allow_contact to bits
        allow_room = allow_room and 1 or 0
        allow_contact = allow_contact and 2 or 0
        self.xml.emptyTag('typevalue',
                          {'level': allow_room | allow_contact})
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
        self.xml.emptyTag('label')
        self.xml.endTag('relationship')
        self.xml.endTag('group')


    def room_to_XML(self, id, recstatus, data):
        # Lager XML for et rom
        #
        # Gamle rom skal aldri slettes automatisk.
        if recstatus == FronterExport.STATUS_DELETE:
            return 
        self.xml.startTag('group', {'recstatus': recstatus})
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', id)
        self.xml.endTag('sourcedid')
        self.xml.startTag('grouptype')
        self.xml.dataElement('scheme', 'FronterStructure1.0')
        self.xml.emptyTag('typevalue', {'level': 4})
        self.xml.endTag('grouptype')
        self.xml.startTag('grouptype')
        self.xml.dataElement('scheme', 'Roomprofile1.0')
        self.xml.emptyTag('typevalue', {'level': data['profile']})
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
        self.xml.emptyTag('label')
        self.xml.endTag('relationship')
        self.xml.endTag('group')

    def personmembers_to_XML(self, gid, recstatus, members):
        # lager XML av medlemer
        self.xml.startTag('membership')
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', gid)
        self.xml.endTag('sourcedid')
        for uname in members:
            self.xml.startTag('member')
            self.xml.startTag('sourcedid')
            self.xml.dataElement('source', self.DataSource)
            self.xml.dataElement('id', uname)
            self.xml.endTag('sourcedid')
            # This is a person member (as opposed to a group).
            self.xml.dataElement('idtype', '1')
            self.xml.startTag('role', {'recstatus': recstatus,
                                       'roletype': FronterExport.ROLE_READ})
            self.xml.dataElement('status', '1')
            self.xml.startTag('extension')
            # Member of group, not room.
            self.xml.emptyTag('memberof', {'type': 1})
            self.xml.endTag('extension')
            self.xml.endTag('role')
            self.xml.endTag('member')
        self.xml.endTag('membership')

    def acl_to_XML(self, node, recstatus, groups):
        self.xml.startTag('membership')
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', node)
        self.xml.endTag('sourcedid')
        for gname in groups.keys():
            self.xml.startTag('member')
            self.xml.startTag('sourcedid')
            self.xml.dataElement('source', self.DataSource)
            self.xml.dataElement('id', gname)
            self.xml.endTag('sourcedid')
            # The following member ids are groups.
            self.xml.dataElement('idtype', '2')
            acl = groups[gname]
            if acl.has_key('role'):
                self.xml.startTag('role', {'recstatus': recstatus,
                                           'roletype': acl['role']})
                self.xml.dataElement('status', '1')
                self.xml.startTag('extension')
                self.xml.emptyTag('memberof', {'type': 2}) # Member of room.
            else:
                self.xml.startTag('role', {'recstatus': recstatus})
                self.xml.dataElement('status', '1')
                self.xml.startTag('extension')
                self.xml.emptyTag('memberof', {'type': 1}) # Member of group.
                self.xml.emptyTag('groupaccess',
                                  {'contactAccess': acl['gacc'],
                                   'roomAccess': acl['racc']})
            self.xml.endTag('extension')
            self.xml.endTag('role')
            self.xml.endTag('member')
        self.xml.endTag('membership')

    def end(self):
        self.xml.endTag(self.rootEl)
        self.xml.endDocument()





class UiOFronterExport(FronterExport):
    """Class for handling export to Fronter."""

    hosts = {
        'internkurs.uio.no': { 'admins': get_members('classfronter-internkurs-drift'),
                               'export': ['All_users'],
                               'plain_users': [],
                               'spread': None,
                               },
        'tavle.uio.no': {'admins': get_members('classfronter-tavle-drift'),
                         'export': ['All_users'],
                         'plain_users': [],
                         'spread': None,
                         },
        'kladdebok.uio.no': { 'admins': get_members('classfronter-kladdebok-drift'),
                              'export': ['FS'],
                              'plain_users': ['mgrude', 'gunnarfk'],
                              'spread': 'spread_fronter_kladdebok',
                              },
        'petra.uio.no': { 'admins': get_members('classfronter-petra-drift'),
                          'export': ['FS', 'All_users'],
                          'plain_users': [],
                          'spread': 'spread_fronter_petra',
                          },
        'blyant.uio.no': { 'admins': get_members('classfronter-blyant-drift'),
                           'export': ['FS', 'All_users'],
                           'plain_users': [],
                           'spread': 'spread_fronter_blyant',
                           }}


    def __init__(self, output=None, host=None):
        FronterExport.__init__(self, output)
        self.DataSource = 'UREG2000@uio.no'
        try:
            hostinfo = UiOFronterExport.hosts[host]
        except KeyError:
            raise KeyError("Unknown host: '%s'" % host)
        self.admins = hostinfo["admins"]
        self.spread = hostinfo["spread"]
        self.export = hostinfo["export"]
        self.plain_users = hostinfo["plain_users"]
        logger.debug("UiOFronterexport initialized")


    
class NMHILExport(ILExport):
    """Class for handling export to Fronter."""

    hosts = {
        'prod.nmh.no': { 'admins': [],
                         'export': ['All_users'],
                         'plain_users': ['All_users'],
                         'spread': 'spread_lms',
        },
        'test.nmh.no': { 'admins': [],
                         'export': ['All_users'],
                         'plain_users': ['All_users'],
                         'spread': 'spread_lms',
        }}


    def __init__(self, output=None, host=None):
        ILExport.__init__(self, output)
        self.DataSource = 'cerebrum@nmh.no'
        try:
            hostinfo = NMHILExport.hosts[host]
        except KeyError:
            raise KeyError("Unknown host: '%s'" % host)
        self.ID = "Norges Musikkhøgskole"
        self.org_type = "Vitenskapelig høgskole"
        self.IDshort = "NMH"
        self.IDcode = "0178000000"
        self.IDstcode = "ST_%s" % self.IDcode
        self.admins = hostinfo["admins"]
        self.spread = hostinfo["spread"]
        self.export = hostinfo["export"]
        self.plain_users = hostinfo["plain_users"]
        logger.debug("NMHILexport initialized")


#!/usr/bin/env python
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

# kbj005 2016.06.07: copied from Leetah

import sys
import locale
import os
import getopt
import time
import string

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uit import access_FS as access_FSUiT
from Cerebrum.modules.no import access_FS
from Cerebrum import Database
from Cerebrum import Entity
from Cerebrum import Person
from Cerebrum import Group
from Cerebrum.modules.no.uit import fronter_lib
from Cerebrum.modules import Email
from Cerebrum.modules.no.uit.Email import email_address
from Cerebrum.modules.no.uit.access_FS import undakt_xml_parser


# Define default file locations
dumpdir = os.path.join(cereconf.DUMPDIR,"Fronter")
default_log_dir = os.path.join(cereconf.CB_PREFIX,'var','log')
default_debug_file = "x-import.log"
default_export_file = 'test.xml'
default_studieprog_file = os.path.join(cereconf.DUMPDIR, 'FS', 'studieprogrammer.xml')
default_underv_enhet_file = os.path.join(cereconf.DUMPDIR, 'FS', 'undervisningenheter.xml')
default_undakt_file = os.path.join(cereconf.DUMPDIR, 'FS', 'undervisningsaktiviteter.xml')

db = const = logger = None
fxml = None
romprofil_id = {}
accid2accname = {}
groupid2groupname = {}

# kbj005, 14.06.2016: Copied from class Fronter in Leetah's uit_fronter_lib.py
STATUS_ADD = 1
STATUS_UPDATE = 2
STATUS_DELETE = 3
ROLE_READ = '01'
ROLE_WRITE = '02'
ROLE_DELETE = '03'
ROLE_CHANGE = '07'

# kbj005, 14.06.2016: Class FronterXML copied from Leetah's uit_fronter_lib.py
class FronterXML(object):
    def __init__(self, fname, cf_dir=None, debug_file=None, debug_level=None,
                 fronter=None, include_password=True):
        self.xml = fronter_lib.XMLWriter(fname)
        self.xml.startDocument(encoding='utf-8')
        self.rootEl = 'enterprise'
        self.DataSource = 'NO-FS'
        self.cf_dir = cf_dir
        self.debug_file = debug_file
        self.debug_level = debug_level
        self.fronter = fronter
        self.include_password = include_password
        self.cf_id = 'uitfronter'

    def start_xml_head(self):
        self.xml.comment("Eksporterer data for UiT")
        self.xml.startTag(self.rootEl)
        self.xml.startTag('properties')
        self.xml.dataElement('datasource', self.DataSource)
        self.xml.dataElement('datetime', time.strftime("%Y-%m-%d"))
        self.xml.endTag('properties')

    def start_xml_file(self, kurs2enhet):
        self.xml.comment("Eksporterer data om følgende emner:\n  " + 
                    "\n  ".join(kurs2enhet.keys()))
        self.xml.startTag(self.rootEl)
        self.xml.startTag('properties')
        self.xml.dataElement('datasource', self.DataSource)
        self.xml.dataElement('target', "ClassFronter/%s@uit.no" % self.cf_id)
        # :TODO: Tell Fronter (again) that they need to define the set of
        # codes for the TYPE element.
        # self.xml.dataElement('TYPE', "REFRESH")
        self.xml.dataElement('datetime', time.strftime("%Y-%m-%d"))
        self.xml.startTag('extension')
        self.xml.emptyTag('debug', {
            'debugdest': 0, # File
            'logpath': self.debug_file,
            'debuglevel': self.debug_level})
        self.xml.emptyTag('databasesettings', {
            'database': 0,  # Oracle
            'jdbcfilename': "%s/%s.dat" % (self.cf_dir, self.cf_id)
            })
        self.xml.endTag('extension')
        self.xml.endTag('properties')

    def user_to_XML(self, id, recstatus, data):
        #Uit: temporary setting recstatus=1 for all users
        recstatus = 1
        """Lager XML for en person"""
        self.xml.startTag('person', {'recstatus': recstatus})
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', id)
        self.xml.endTag('sourcedid')
        #self.xml.emptyTag('userid',{'pwencryptiontype':'5'})  # 5 = ldap

        self.xml.startTag('userid',{'pwencryptiontype':'5'})
        self.xml.data(id)
        self.xml.endTag('userid')
        
        if (recstatus == STATUS_ADD
            or recstatus == STATUS_UPDATE):
            self.xml.startTag('name')
            self.xml.dataElement('fn', data['FN'])
            self.xml.startTag('n')
            self.xml.dataElement('family', data['FAMILY'])
            self.xml.dataElement('given', data['GIVEN'])
            self.xml.endTag('n')
            self.xml.endTag('name')
            self.xml.dataElement('email', data['EMAIL'])
            self.xml.startTag('extension')
            #if self.include_password:
            #    #self.xml.emptyTag('PASSWORD',
            #    #                  {'password': data['PASSWORD_CRYPT'],'passwordtype': data['PASSWORD_TYPE']})
            #    self.xml.emptyTag('password',
            #                      {'passwordtype': 'ldap1'})
            self.xml.emptyTag('useraccess', {'accesstype': data['USERACCESS']})

            self.xml.emptyTag('emailclient',
                              {'clienttype': data['EMAILCLIENT']})
            if data['USE_EMAILCLIENT'] == 1:
                self.xml.emptyTag('emailsettings', 
                                  {'mail_username': id,
                                   'mail_password': data['IMAPPASSWD'],
                                   'description': 'UiT IMAP Server',
                                   'mailserver': data['IMAPSERVER'],
                                   'mailtype': '1', #RMI000 20070919: DTD says IMAP, Fronter Support says 1
                                   'use_ssl': '1',
                                   'is_primary':'1'})
            self.xml.endTag('extension')
        self.xml.endTag('person')

    def group_to_XML(self, id, recstatus, data):
        # Lager XML for en gruppe
        if recstatus == STATUS_DELETE:
            return
        #Uit: temporary setting recstatus=1 for all groups
        recstatus = 1
        self.xml.startTag('group', {'recstatus': recstatus})
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', id)
        self.xml.endTag('sourcedid')
        if (recstatus == STATUS_ADD or
            recstatus == STATUS_UPDATE):
            self.xml.startTag('grouptype')
            self.xml.dataElement('scheme', 'FronterStructure1.0')
            allow_room = data.get('allow_room', 0)
            allow_room = allow_room and 1 or 0
            if allow_room:
                allow_room = 1
            allow_contact = data.get('allow_contact', 0)
            allow_contact = allow_contact and 2 or 0
            if allow_contact:
                allow_contact = 2
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
        if recstatus == STATUS_DELETE:
            return 
        self.xml.startTag('group', {'recstatus': recstatus})
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', id)
        self.xml.endTag('sourcedid')
        if (recstatus == STATUS_ADD or
            recstatus == STATUS_UPDATE):
            self.xml.startTag('grouptype')
            self.xml.dataElement('scheme', 'FronterStructure1.0')
            self.xml.emptyTag('typevalue', {'level': 4})
            self.xml.endTag('grouptype')
            if (recstatus == STATUS_ADD):
                # Romprofil settes kun ved opprettelse av rommet, og vil
                # aldri senere tvinges tilbake til noen bestemt profil.
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
            self.xml.dataElement('idtype', '1') # The following member ids are persons.
            self.xml.startTag('role', {'recstatus': recstatus,
                                       'roletype': ROLE_READ})
            self.xml.dataElement('status', '1')
            self.xml.startTag('extension')
            self.xml.emptyTag('memberof', {'type': 1}) # Member of group, not room.
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
            self.xml.dataElement('idtype', '2') # The following member ids are groups.
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

def init_globals():
    global db, const, logger, use_emailclient
    db = Factory.get("Database")()
    const = Factory.get("Constants")(db)
    logger = Factory.get_logger(cereconf.DEFAULT_LOGGER_TARGET)
    cf_dir = dumpdir
    log_dir = default_log_dir
    use_emailclient = 1

    ent_name = Entity.EntityName(db)
    for name in ent_name.list_names(const.account_namespace):
        accid2accname[name['entity_id']] = name['entity_name']

    for name in ent_name.list_names(const.group_namespace):
        groupid2groupname[name['entity_id']] = name['entity_name']

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h:',
                                   ['host=', 'rom-profil=',
                                    'debug-file=', 'debug-level=', 'activate-emailclient'])
    except getopt.GetoptError:
        usage(1)
    debug_file = os.path.join(log_dir, default_debug_file)
    debug_level = 4
    host = 'uit'
    for opt, val in opts:
        if opt in ('-h', '--host'):
            host = val
        elif opt == '--debug-file':
            debug_file = val
        elif opt == '--debug-level':
            debug_level = val
        elif opt == 'rom-profil':
            profil_navn, profil_id = val.split(':')
            romprofil_id[profil_navn] = profil_id
        elif opt == '--activate-emailclient':
            use_emailclient = 1
        else:
            raise ValueError, "Invalid argument: %r", (opt,)

    host_profiles = {'uit': {'emnerom': 1924, # old value 128
                             'studieprogram': 1924},# old value 128
                     'uit2': {'emnerom': 42,
                              'studieprogram': 42},
                     'uit3': {'emnerom': 128, # old value 1520
                              'studieprogram': 128} # old value 1521
                     }
    if host_profiles.has_key(host):
        romprofil_id.update(host_profiles[host])

    filename = os.path.join(cf_dir, default_export_file)
    if len(args) == 1:
        filename = args[0]
    elif len(args) != 0:
        usage(2)

    global fxml
    fxml = FronterXML(filename,
                      cf_dir = cf_dir,
                      debug_file = debug_file,
                      debug_level = debug_level,
                      fronter = None)

def load_acc2name():
    person = Person.Person(db)
    account = Factory.get('Account')(db)
    logger.debug('Loading person/user-to-names table')
    ret = {}

    logger.info("Cache person names")
    cached_names=person.getdict_persons_names(source_system=const.system_cached,
                                              name_types=(const.name_first,const.name_last))
    has_aff=list()
    logger.debug("Loading account affiliations")
    for acc_aff in account.list_accounts_by_type(primary_only=True):
       has_aff.append(acc_aff['account_id'])

    uname2owner=dict()
    uname2accid=dict()
    logger.info("Retreiving accounts with fronter spread")
    for acc in account.search(spread=const.spread_uit_fronter_account):
        if acc['account_id'] not in has_aff:
            logger.debug("Skipping account %s, no active affiliations" % (acc['name'],))
            continue
        uname2owner[acc['name']]=acc['owner_id']
        uname2accid[acc['name']]=acc['account_id']
    logger.debug("loaded %d accounts from cerebrum" % len(uname2owner))
    
    logger.info("Cache email addresses")
    acc2email = account.getdict_uname2mailaddr()
    logger.info("Building users dict")
    for uname,owner_id in uname2owner.iteritems():

        namelist = cached_names.get(owner_id, None)
        if not namelist:
            logger.error("No namelist found for %s, skipping" % uname)
            continue
        try:
            first_name = namelist.get(int(const.name_first), "")
            last_name = namelist.get(int(const.name_last),"")
        except AttributeError:
            logger.error("Could not get name for %s from %s" % (uname,namelist))
            continue
        
        if first_name=="" and last_name=="":
           logger.error("No names for %s, skipping" % uname)

        email=acc2email.get(uname,None)
        if not email:
           logger.warn("Skipping account %s, no mailaddress found" % (uname,))
           continue

        # Define which IMAP server should be used for different people
        imap = ""
        if not email.endswith("@"+cereconf.NO_MAILBOX_DOMAIN_EMPLOYEES):
            #imap = cereconf.IMAPMAILBOX
            imap = cereconf.EMAIL_DEFAULT_COMMON_DOMAIN
            passw = 'FRONTERLOGIN'
        else:
            #imap = cereconf.IMAPEXCHANGE
            imap = cereconf.EMAIL_DEFAULT_COMMON_DOMAIN
            passw = 'askuser:'
        
        
        ret[uname2accid[uname]] = {
            'NAME': uname,
            'FN': " ".join((first_name,last_name)),
            'GIVEN': first_name,
            'FAMILY': last_name,
            'EMAIL': email,
            'USERACCESS': 2,
            'PASSWORD_TYPE':1,
            'USE_EMAILCLIENT': use_emailclient,
            'EMAILCLIENT': 1,
            'IMAPSERVER': imap,
            'IMAPPASSWD': passw}
       
    logger.debug("Returning %s users" % len(ret))
    return ret


def get_ans_fak(fak_list, ent2uname):
    fak_res = {}
    person = Factory.get('Person')(db)
    ou = Factory.get('OU')(db)
    for fak in fak_list:
        ans_list = []
        # Get all stedkoder in one faculty
        for ou in ou.get_stedkoder(fakultet=int(fak)):
            # get persons in the stedkode
            for pers in person.list_affiliations(source_system=const.system_paga,
                                        affiliation=const.affiliation_ansatt,
                                        ou_id=int(ou['ou_id'])):
                person.clear()
                try:
                    person.find(int(pers['person_id']))
                    acc_id = person.get_primary_account()
                except Errors.NotFoundError:
                    logger.error("Person pers_id: %d , no valid account!" % \
                                 person.entity_id)
                    break
                if acc_id and ent2uname.has_key(acc_id):
                    uname = ent2uname[acc_id]['NAME']
                    if uname not in ans_list:
                        ans_list.append(uname)
                else:
                    logger.error("Person pers_id: %d have no account!" % \
                                                   person.entity_id)
        fak_res[int(fak)] = ans_list
    return fak_res


def register_spread_groups(emne_info, stprog_info, undakt_info):
    group = Factory.get('Group')(db)
    for r in group.search(spread=const.spread_uit_fronter):
        gname = r['name']
        gname_el = gname.split(':')

        logger.warn("###---### : %s" % gname_el)
        # gname_el == ['internal', 'uit.no', 'fs', '186', 'undenh', '2016', 'h\xf8st', 'vpdmil', '1', '1', 'undakt', '1-2mo']

        if len(gname_el) > 10 and gname_el[10] == 'undakt':
        # undakt branch added by rmi000 2009-05-25

            #print '####'
            #print gname_el


            #
            # Creating UNDAKT ROOM
            #
            instnr = gname_el[3]
            ar, term, emnekode, versjon, terminnr, undakt, undaktkode = gname_el[5:12] # emnekode = vpdmil
            if int(ar) < 2006:
                continue
            fak_sko = "%02d0000" % emne_info[emnekode]['fak']

            logger.warn("emnekode:%s"  % (emnekode))
            logger.warn("emneforknavn:%s" % emne_info[emnekode]['emnenavnfork'])
            logger.warn("Undaktkode:%s" % undaktkode)
            logger.warn("aktivitetsnavn:%s" % undakt_info[emnekode][undaktkode]['aktivitetsnavn']) # undakt_info[vpdmil][1-2mo]['aktivitetsnavn']
            undakt_room_title = '%s - %s (%s. Sem) - %s (%s%s)' %(emnekode.upper(), emne_info[emnekode]['emnenavnfork'], terminnr, undakt_info[emnekode][undaktkode]['aktivitetsnavn'], term[0].upper(), ar)
            undakt_room_id = 'ROOM:%s:fs:emner:%s:%s:%s:%s:undenh:%s:%s:%s:undakt:%s' % (cereconf.INSTITUTION_DOMAIN_NAME, ar, term, instnr, fak_sko, emnekode, versjon, terminnr, undaktkode)
            #print "UNDAKT ROOM", undakt_room_id
            undakt_room_parent_id = 'STRUCTURE:%s:fs:emner:%s:%s:emnerom:%s:%s' % (cereconf.INSTITUTION_DOMAIN_NAME, ar, term, instnr, fak_sko)
            #print "UNDAKT ROOM PARENT", undakt_room_parent_id
            undakt_room_profile = romprofil_id['emnerom']

            register_room(undakt_room_title, undakt_room_id, undakt_room_parent_id, undakt_room_profile)


            #
            # Adding Members to UNDAKT ROOM
            #
            group.clear()
            group.find(r['group_id'])
            user_members = [
                    accid2accname[row['member_id']]  # username
                    for row in group.search_members(group_id=group.entity_id,
                                                    member_type=const.entity_account)]

            if user_members:

                if gname_el[0] == 'internal':
                    gname_el.pop(0)
                undakt_group_id = ':'.join(gname_el)

                undakt_group_title = 'Studenter på %s - %s (%s. Sem) - %s (%s%s)' % (emnekode.upper(), emne_info[emnekode]['emnenavnfork'], terminnr, undakt_info[emnekode][undaktkode]['aktivitetsnavn'], term[0].upper(), ar)
                #print "UNDAKT GROUP", undakt_group_title
                undakt_group_parent_id = 'STRUCTURE:%s:fs:emner:%s:%s:%s' % (cereconf.INSTITUTION_DOMAIN_NAME, ar, term, 'undakt')
                rettighet = ROLE_WRITE

                register_group(undakt_group_title, undakt_group_id, undakt_group_parent_id, allow_contact=True)
                register_members(undakt_group_id, user_members)
                register_room_acl(undakt_room_id, undakt_group_id, rettighet)

        elif len(gname_el) > 10 and gname_el[10] == 'gruppelære':
        # gruppelære branch added by rmi000 2009-06-17

            #print '##-##'
            #print gname_el


            #
            # Creating UNDAKT ROOM
            #
            instnr = gname_el[3]
            ar, term, emnekode, versjon, terminnr, undakt, undaktkode = gname_el[5:12]
            if int(ar) < 2006:
                continue
            fak_sko = "%02d0000" % emne_info[emnekode]['fak']


            #undakt_room_title = '%s - %s (%s. Sem) - %s' %(emnekode.upper(), emne_info[emnekode]['emnenavnfork'], terminnr, undakt_info[emnekode][undaktkode]['aktivitetsnavn'])
            undakt_room_id = 'ROOM:%s:fs:emner:%s:%s:%s:%s:undenh:%s:%s:%s:undakt:%s' % (cereconf.INSTITUTION_DOMAIN_NAME, ar, term, instnr, fak_sko, emnekode, versjon, terminnr, undaktkode)
            #print "UNDAKT ROOM", undakt_room_id
            #undakt_room_parent_id = 'STRUCTURE:%s:fs:emner:%s:%s:emnerom:%s:%s' % (cereconf.INSTITUTION_DOMAIN_NAME, ar, term, instnr, fak_sko)
            #print "UNDAKT ROOM PARENT", undakt_room_parent_id
            #undakt_room_profile = romprofil_id['emnerom']

            # Dont register room here, the room will be registered in the previous confitional statement branch
            # register_room(undakt_room_title, undakt_room_id, undakt_room_parent_id, undakt_room_profile)


            #
            # Adding Members to UNDAKT ROOM
            #
            group.clear()
            group.find(r['group_id'])
            user_members = [
                    accid2accname[row['member_id']]  # username
                    for row in group.search_members(group_id=group.entity_id,
                                                    member_type=const.entity_account)]

            if user_members:
                #print "###-###"

                if gname_el[0] == 'internal':
                    gname_el.pop(0)
                undakt_group_id = ':'.join(gname_el)

                undakt_group_title = 'Gruppelærere på %s - %s (%s. Sem) - %s (%s%s)' % (emnekode.upper(), emne_info[emnekode]['emnenavnfork'], terminnr, undakt_info[emnekode][undaktkode]['aktivitetsnavn'], term[0].upper(), ar)
 
                #print "GRUPPELÆRE GROUP", undakt_group_title
                undakt_group_parent_id = 'STRUCTURE:%s:fs:emner:%s:%s:%s' % (cereconf.INSTITUTION_DOMAIN_NAME, ar, term, 'gruppelære')
                rettighet = ROLE_DELETE

                register_group(undakt_group_title, undakt_group_id, undakt_group_parent_id, allow_contact=True)
                register_members(undakt_group_id, user_members)
                register_room_acl(undakt_room_id, undakt_group_id, rettighet)

        elif gname_el[4] == 'undenh':
            #print "##UNDENH##", gname_el
            # Nivå 3: internal:DOMAIN:fs:INSTITUSJONSNR:undenh:ARSTALL:
            #           TERMINKODE:EMNEKODE:VERSJONSKODE:TERMINNR
            #
            # De interessante gruppene (som har brukermedlemmer) er på
            # nivå 4.
            instnr = gname_el[3]
            ar, term, emnekode, versjon, terminnr = gname_el[5:10]
            if int(ar) < 2006:
                continue

            try: #KB
                fak_sko = "%02d0000" % emne_info[emnekode]['fak']
            except KeyError as e: #KB
                logger.warn("Couldn't register spread group for %s because of KeyError. %s not in %s", gname_el, e, default_underv_enhet_file)
                continue

            # Rom for undervisningsenheten.
            emne_id_prefix = '%s:fs:emner:%s:%s:%s:%s' % (
                cereconf.INSTITUTION_DOMAIN_NAME,
                ar, term, instnr, fak_sko)
            my_emne_id_prefix = '%s:fs:emner:%s:%s:emnerom:%s:%s' % (
                cereconf.INSTITUTION_DOMAIN_NAME,
                ar, term, instnr, fak_sko)

            
            emne_sted_id = 'STRUCTURE:%s' % my_emne_id_prefix

            # UIT: we need to represent emenrom with an indication of which termin this
            # emenroom is for. f.eks a room with terminkode 1,2 and 3 would need something like
            # (course_name - semester 1)
            # (course_name - semester 2)
            # (course_name - semester 3)
            # This to diffenrentiate between the different semesters a course can be in.
            #if terminnr != "1":
            #    termin_representation = "%s. semester" % terminnr
            #    emne_rom_id = 'ROOM:%s:undenh:%s (%s):%s:%s' % (emne_id_prefix,emnekode,termin_representation,versjon,terminnr)
            #else:
            emne_rom_id = 'ROOM:%s:undenh:%s:%s:%s' % (
                emne_id_prefix, emnekode, versjon, terminnr)

            #print "--> emnerom = %s" % emne_rom_id
            ##print "emnenavnfork == '%s'" % emne_info[emnekode]['emnenavnfork'] # UIT

            #UIT register_room with versjon and int(terminnr) substituted with emne_info[emnekode]['emnenavnfork']
            termin_representation = "%s. Sem" % terminnr
            register_room('%s - %s - %s (%s%s)' %
                          (emnekode.upper(), emne_info[emnekode]['emnenavnfork'],termin_representation, term[0].upper(), ar),
                          emne_rom_id, emne_sted_id,
                          profile=romprofil_id['emnerom'])

            # Grupper for studenter, forelesere og studieveileder på
            # undervisningsenheten.
            group.clear()
            group.find(r['group_id'])

            for mrow in group.search_members(group_id=group.entity_id, member_type=int(const.entity_group)):
                subg_name = groupid2groupname[mrow['member_id']]
                subg_id = mrow['member_id']
                # Nivå 4: internal:DOMAIN:fs:INSTITUSJONSNR:undenh:ARSTALL:
                #           TERMINKODE:EMNEKODE:VERSJONSKODE:TERMINNR:KATEGORI
                subg_name_el = subg_name.split(':')
                # Fjern "internal:"-prefiks.
                if subg_name_el[0] == 'internal':
                    subg_name_el.pop(0)
                kategori = subg_name_el[9]
                parent_id = 'STRUCTURE:%s:fs:emner:%s:%s:%s' % (
                    subg_name_el[0],    # DOMAIN
                    subg_name_el[4],    # ARSTALL
                    subg_name_el[5],    # TERMINKODE
                    kategori
                    )
                
                if kategori == 'student':
                    title = 'Studenter på '
                    rettighet = ROLE_WRITE
                elif kategori == 'foreleser':
                    title = 'Forelesere på '
                    rettighet = ROLE_DELETE
                elif kategori == 'fagansvarlig':
                    title = 'Fagansvarlige på '
                    rettighet = ROLE_CHANGE
                    #rettighet = ROLE_DELETE
                elif kategori == 'gruppelære':
                    continue
                    #title = 'Gruppelærere på '
                    #rettighet = ROLE_DELETE
                elif kategori == 'undakt':
                    title = ''
                    rettighet = ROLE_WRITE
                else:
                    raise RuntimeError, "Ukjent kategori: %s" % (kategori,)
                #title += '%s (ver %s, %d. termin)' % (
                #    subg_name_el[6].upper(), # EMNEKODE
                #    subg_name_el[7],    # VERSJONSKODE
                #    int(subg_name_el[8])) # TERMINNR
                # UIT TITLE:
                if kategori in ['undakt', ]:
                    title += '%s, %s' % (subg_name_el[6].upper(), subg_name_el[10].upper()) # EMNEKODE, UNDAKT
                else:
                    title += '%s' % (subg_name_el[6].upper()) # EMNEKODE

                title += ' (%s%s)' % (term[0].upper(), ar)

                fronter_gname = ':'.join(subg_name_el)
                register_group(title, fronter_gname, parent_id,
                               allow_contact=True)
                group.clear()
                group.find(subg_id)
                user_members = [
                    accid2accname[row['member_id']]  # username
                    for row in group.search_members(group_id=group.entity_id,
                                                    member_type=const.entity_account)]

                if user_members:
                    register_members(fronter_gname, user_members)
                register_room_acl(emne_rom_id, fronter_gname, rettighet)

	elif gname_el[4] == 'studieprogram':
            ##print "gname data = %s" % (gname_el)
            # En av studieprogram-grenene på nivå 3.  Vil eksportere
            # gruppene på nivå 4.
            group.clear()
            group.find(r['group_id'])
	    # Legges inn new group hvis den ikke er opprettet            
            for mrow in group.search_members(group_id=group.entity_id, member_type=int(const.entity_group)):
                subg_name = groupid2groupname[mrow['member_id']]
                subg_id = mrow['member_id']

                #print "####----####", gname, subg_name, subg_id

                subg_name_el = subg_name.split(':')
                # Fjern "internal:"-prefiks.
                if subg_name_el[0] == 'internal':
                    subg_name_el.pop(0)
                fronter_gname = ':'.join(subg_name_el)
                institusjonsnr = subg_name_el[2]
                stprog = subg_name_el[4]
                fak_sko = '%02d0000' % stprog_info[stprog]['fak']

                # Opprett fellesrom for dette studieprogrammet.
                fellesrom_sted_id = ':'.join((
                    'STRUCTURE', cereconf.INSTITUTION_DOMAIN_NAME,
                    'fs', 'fellesrom', institusjonsnr, fak_sko))
                fellesrom_stprog_rom_id = ':'.join((
                    'ROOM', cereconf.INSTITUTION_DOMAIN_NAME, 'fs',
                    'fellesrom', '186',fak_sko, 'studieprogram', stprog))
                register_room(stprog.upper(), fellesrom_stprog_rom_id,
                              fellesrom_sted_id,
                              profile=romprofil_id['studieprogram'])

                #print subg_name_el

                if subg_name_el[-1] == 'student':
                    #brukere_studenter_id = ':'.join((
                    #    'STRUCTURE', cereconf.INSTITUTION_DOMAIN_NAME,
                    #    'fs', 'brukere', subg_name_el[2], # institusjonsnr
                    #    fak_sko, 'student'))
                    #brukere_stprog_id = brukere_studenter_id + \
                    #                    ':%s' % stprog
                    #register_group(stprog.upper(), brukere_stprog_id,
                    #               brukere_studenter_id)
                    #register_group(
                    #    'Studenter på %s' % subg_name_el[6], # kullkode
                    #    fronter_gname, brukere_stprog_id,
                    #    allow_contact=True)
                    fellesrom_studenter_id = fellesrom_sted_id + \
                                                ':studenter'
                    register_group("Studenter", fellesrom_studenter_id,
                                   fellesrom_sted_id)
                    kull =  subg_name_el[-3]
                    sem =  subg_name_el[-2]   

                    title = "Studenter på %s (Kull %s %s)" % (stprog.upper(), kull,sem)
                    register_group(
                        title,
                        fronter_gname, fellesrom_studenter_id,
                        allow_contact=True)

                    
                    # Gi denne studiekullgruppen 'skrive'-rettighet i
                    # studieprogrammets fellesrom.
                    register_room_acl(fellesrom_stprog_rom_id, fronter_gname,
                                      ROLE_WRITE)



                    # Registrere rom for kullet
                    kullrom_title = "%s (Kull %s %s)" % (stprog.upper(), kull, sem)
                    kullrom_id = fellesrom_stprog_rom_id + ":%s:%s" % (kull, sem)
                    register_room(kullrom_title, kullrom_id,
                              fellesrom_sted_id,
                              profile=romprofil_id['studieprogram'])

                    # Gi studiekullgruppen rettigheter i kullrommet
                    register_room_acl(kullrom_id, fronter_gname,
                                      ROLE_WRITE)

                elif subg_name_el[-1] == 'studieleder-program':
                    fellesrom_rolle_id = fellesrom_sted_id + ':studieleder-program'
                    register_group("Studieledere for program", fellesrom_rolle_id, fellesrom_sted_id)
                    register_group(
                        "Studieledere for program %s" % stprog.upper(),
                        fronter_gname, fellesrom_rolle_id,
                        allow_contact=True)
                    # Gi studieleder-gruppen 'slette'-rettighet i studieprogrammets fellesrom.
                    register_room_acl(fellesrom_stprog_rom_id, fronter_gname,
                                       ROLE_CHANGE)

                elif subg_name_el[-1] == 'lærer-kull':
                    fellesrom_rolle_id = fellesrom_sted_id + ':lærer-kull'
                    register_group("Lærere for kullprogram", fellesrom_rolle_id, fellesrom_sted_id)

                    kull =  subg_name_el[-3]
                    sem =  subg_name_el[-2]
                    title = "Lærere på %s (Kull %s %s)" % (stprog.upper(), kull,sem)
                    register_group(
                        title,
                        fronter_gname, fellesrom_rolle_id,
                        allow_contact=True)

                    # Registrere rom for kullet
                    kullrom_title = "%s (Kull %s %s)" % (stprog.upper(), kull, sem)
                    kullrom_id = fellesrom_stprog_rom_id + ":%s:%s" % (kull, sem)
                    register_room(kullrom_title, kullrom_id,
                              fellesrom_sted_id,
                              profile=romprofil_id['studieprogram'])

                    # Gi lærere rettigheter i kullrommet
                    register_room_acl(kullrom_id, fronter_gname,
                                      ROLE_DELETE)

                elif subg_name_el[-1] == 'studieleder-kull':
                    fellesrom_rolle_id = fellesrom_sted_id + \
                                                ':studieleder-kull'
                    register_group("Studieledere for kullprogram", fellesrom_rolle_id,
                                   fellesrom_sted_id)

                    kull =  subg_name_el[-3]
                    sem =  subg_name_el[-2]
                    title = "Studieledere på %s (Kull %s %s)" % (stprog.upper(), kull,sem)
                    register_group(
                        title,
                        fronter_gname, fellesrom_rolle_id,
                        allow_contact=True)

                    # Registrere rom for kullet
                    kullrom_title = "%s (Kull %s %s)" % (stprog.upper(), kull, sem)
                    kullrom_id = fellesrom_stprog_rom_id + ":%s:%s" % (kull, sem)
                    register_room(kullrom_title, kullrom_id,
                              fellesrom_sted_id,
                              profile=romprofil_id['studieprogram'])

                    # Gi studieledere rettigheter i kullrommet
                    register_room_acl(kullrom_id, fronter_gname,
                                      ROLE_CHANGE)


                else:
                    raise RuntimeError, \
                          "Ukjent studieprogram-gruppe: %r" % (gname,)

                # Synkroniser medlemmer i Cerebrum-gruppa til CF.
                group.clear()
                group.find(subg_id)
                user_members = [
                    accid2accname[row['member_id']]  # username
                    for row in group.search_members(group_id=group.entity_id,
                                                    member_type=const.entity_account)]

                if user_members:
                    register_members(fronter_gname, user_members)
        else:
            raise RuntimeError, \
                  "Ukjent type gruppe eksportert: %r" % (gname,)

new_acl = {}
def register_room_acl(room_id, group_id, role):
    new_acl.setdefault(room_id, {})[group_id] = {'role': role}

def register_structure_acl(node_id, group_id, contactAccess, roomAccess):
    new_acl.setdefault(node_id, {})[group_id] = {'gacc': contactAccess,
                                                 'racc': roomAccess}

new_groupmembers = {}
def register_members(gname, members):
    new_groupmembers[gname] = members

new_rooms = {}
def register_room(title, id, parentid, profile):
    new_rooms[id] = {
        'title': title,
        'parent': parentid,
        'CFid': id,
        'profile': profile}

new_group = {}
def register_group(title, id, parentid,
                   allow_room=False, allow_contact=False):
    """Adds info in new_group about group."""
    
    found = -1
    found2 = -1
    found = id.find(":195:")
    found2 = id.find(":4902:")
    if ((found == -1) and (found2 == -1)):
        logger.info("appending: title:%s, parent:%s, allow_room:%s, allow_contact:%s, CFID:%s" % (title,parentid,allow_room,allow_contact,id))
        new_group[id] = { 'title': title,
                          'parent': parentid,
                          'allow_room': allow_room,
                          'allow_contact': allow_contact,
                          'CFid': id,
                          }
    else:
        logger.warn("not inserting: '%s'" % id)

def output_group_xml():
    """Generer GROUP-elementer uten forover-referanser."""
    done = {}
    def output(id):
        if id in done:
            return

        data = new_group[id]
        parent = data['parent']
        if parent != id:
            output(parent)
        fxml.group_to_XML(data['CFid'], STATUS_ADD, data)
        done[id] = True
    for group in new_group.iterkeys():
        output(group)

def usage(exitcode):
    print "Usage: export_xml_fronter.py OUTPUT_FILENAME"
    sys.exit(exitcode)



def main():
    # Handter upper- og lowercasing av strenger som inneholder norske
    # tegn.
    locale.setlocale(locale.LC_CTYPE, ('en_US', 'iso88591'))

    init_globals()

    # start generating xml file
    fxml.start_xml_head()

    # Finn `account_id` -> account-data for alle brukere.
    acc2names = load_acc2name()
    # Spytt ut PERSON-elementene.
    for user in acc2names.itervalues():
       # 2 = recstatus modify fix denne senere # uit
       fxml.user_to_XML(user['NAME'],2,user)

    # Registrer en del semi-statiske strukturnoder.
    root_node_id = "STRUCTURE:ClassFronter structure root node"

    register_group('Universitetet i Tromsø', root_node_id, root_node_id)

    manuell_node_id = 'STRUCTURE:%s:manuell' % \
                      cereconf.INSTITUTION_DOMAIN_NAME
    register_group('Manuell', manuell_node_id, root_node_id,
                   allow_room=True)

    emner_id = 'STRUCTURE:%s:fs:emner' % cereconf.INSTITUTION_DOMAIN_NAME
    register_group('Emner', emner_id, root_node_id)

    this_sem, next_sem = access_FSUiT.get_semester()
    emner_this_sem_id = emner_id + ':%s:%s' % tuple(this_sem)
    emner_next_sem_id = emner_id + ':%s:%s' % tuple(next_sem)

    register_group('Emner %s %s' % (this_sem[1].upper(), this_sem[0]),
                   emner_this_sem_id, emner_id)
    register_group('Emner %s %s' % (next_sem[1].upper(), next_sem[0]),
                   emner_next_sem_id, emner_id)

    emnerom_this_sem_id = emner_this_sem_id + ':emnerom'
    emnerom_next_sem_id = emner_next_sem_id + ':emnerom'
    register_group('Emnerom %s %s' % (this_sem[1].upper(), this_sem[0]),
                   emnerom_this_sem_id, emner_this_sem_id)
    register_group('Emnerom %s %s' % (next_sem[1].upper(), next_sem[0]),
                   emnerom_next_sem_id, emner_next_sem_id)

    for sem, sem_node_id in ((this_sem, emner_this_sem_id),
                             (next_sem, emner_next_sem_id)):
        for suffix, title in (
            ('undakt', 'Undervisningsaktiviteter %s %s' % (sem[1].upper(),
                                             sem[0])),
            ('student', 'Studenter %s %s' % (sem[1].upper(),
                                             sem[0])),
            ('foreleser', 'Forelesere %s %s' % (sem[1].upper(),
                                                sem[0])),
            ('fagansvarlig', 'Fagansvarlige %s %s' % (sem[1].upper(),
                                                sem[0])),
            ('gruppelære', 'Gruppelærere %s %s' % (sem[1].upper(),
                                                sem[0])),
            #('studieleder', 'Studieledere %s %s' % (sem[1].upper(),
            #                                        sem[0]))
            ):
            node_id = sem_node_id + ':' + suffix
            register_group(title, node_id, sem_node_id)
            #print "GROUP_REG", node_id

    brukere_id= 'STRUCTURE:%s:fs:brukere' % cereconf.INSTITUTION_DOMAIN_NAME
    register_group('Brukere', brukere_id, root_node_id)

    fellesrom_id = 'STRUCTURE:%s:fs:fellesrom' % \
                   cereconf.INSTITUTION_DOMAIN_NAME
    register_group('Studieprogram', fellesrom_id, root_node_id)

    # Populer dicter for "emnekode -> emnenavn" og "fakultet ->
    # [emnekode ...]".
    emne_info = {}
    fak_emner = {}
    def finn_emne_info(element, attrs):
        
        if element != 'enhet':
            return
        emnenavnfork = attrs['emnenavnfork']
        emnekode = attrs['emnekode'].lower()
        faknr = int(attrs['faknr_kontroll'])
        emne_info[emnekode] = {'navn': attrs['emnenavn_bokmal'],
                               'fak': faknr, 'emnenavnfork' : emnenavnfork} # UIT: added emnenavnfork
        fak_emner.setdefault(faknr, []).append(emnekode)
    
    
    access_FS.underv_enhet_xml_parser(default_underv_enhet_file,
                                      finn_emne_info)
    

    stprog_info = {}
    def finn_stprog_info(element, attrs):
        if element == 'studprog':
            stprog = attrs['studieprogramkode'].lower()
            faknr = int(attrs['faknr_studieansv'])
            stprog_info[stprog] = {'fak': faknr}
    access_FS.studieprog_xml_parser(default_studieprog_file,
                                    finn_stprog_info)


    undakt_info = {}
    # cache undervisningsaktiviteter
    # <undakt institusjonsnr="186" emnekode="BIO-2300" versjonskode="1" terminkode="HØST" arstall="2009" terminnr="1" aktivitetkode="2-2" undpartilopenr="2" disiplinkode="TEORI" undformkode="KOL" aktivitetsnavn="Kollokvier gr. 2 (Farmasi)"/>

    def cache_UA_helper(el_name, attrs):
        if el_name == 'aktivitet':

            emnekode = attrs['emnekode'].lower()
            aktivitetkode = attrs['aktivitetkode']
            aktivitetsnavn = attrs['aktivitetsnavn']

            emne_undakt = undakt_info.get(emnekode, None)
            if emne_undakt is None:
                emne_undakt = {}

            emne_undakt[aktivitetkode] = {'aktivitetsnavn': aktivitetsnavn}

            undakt_info[emnekode] = emne_undakt
            if(emnekode == 'vpdmil'):
                logger.warn("adding %s for emnekode vpdmil" % (emne_undakt))
    logger.info("Leser XML-fil: %s",  default_undakt_file)
    undakt_xml_parser(
        default_undakt_file,
        cache_UA_helper)

    # Henter ut ansatte per fakultet
    fak_temp = fak_emner.keys() # UIT
    fak_temp.append(44) # UIT. We add 44 - used to be 74 - which is UVETT)
    fak_temp.append(99) # UIT. we add 99 (which is external units)
    #logger.warn("### fak_temp:%s" % (fak_temp))
    ans_dict = get_ans_fak(fak_temp,acc2names)  # UIT

    # Opprett de forskjellige stedkode-korridorene.
    ou = Factory.get('OU')(db)

    for faknr in fak_temp: # UIT
        fak_sko = "%02d0000" % faknr
        #logger.warn("fak_sko:%s" % (fak_sko))
        ou.clear()
        try:
            ou.find_stedkode(faknr, 0, 0,
                             institusjon = cereconf.DEFAULT_INSTITUSJONSNR)
        except Errors.NotFoundError:
            logger.error("Finner ikke stedkode for fakultet %d", faknr)
            faknavn = '*Ikke registrert som fakultet i FS*'
        else:
            if ou.acronym:
                faknavn = ou.get_name_with_language(const.ou_name_acronym,
                                                    const.language_nb)
            else:
                faknavn = ou.get_name_with_language(const.ou_name_short,
                                                    const.language_nb)
        fak_ans_id = "%s:sap:gruppe:%s:%s:ansatte" % \
                     (cereconf.INSTITUTION_DOMAIN_NAME,
                      cereconf.DEFAULT_INSTITUSJONSNR,
                      fak_sko)
        ans_title = "Ansatte ved %s" % faknavn
        register_group(ans_title, fak_ans_id, brukere_id,
                       allow_contact=True)
        ans_memb = ans_dict[int(faknr)]

        register_members(fak_ans_id, ans_memb)
        for sem_node_id in (emnerom_this_sem_id,
                            emnerom_next_sem_id):
            fak_node_id = sem_node_id + \
                          ":%s:%s" % (cereconf.DEFAULT_INSTITUSJONSNR,
                                      fak_sko)
            register_group(faknavn, fak_node_id, sem_node_id,
                           allow_room=True)
        brukere_sted_id = brukere_id + \
                          ":%s:%s" % (cereconf.DEFAULT_INSTITUSJONSNR,
                                      fak_sko)
        register_group(faknavn, brukere_sted_id, brukere_id)
        brukere_studenter_id = brukere_sted_id + ':student'
        register_group('Studenter ved %s' % faknavn,
                       brukere_studenter_id, brukere_sted_id)
        fellesrom_sted_id = ("STRUCTURE:uit.no:fs:fellesrom") # UIT
        
        #fellesrom_sted_id = fellesrom_id + ":%s:%s" % (
        fellesrom_sted_id = fellesrom_sted_id + ":%s:%s" % (
            cereconf.DEFAULT_INSTITUSJONSNR, fak_sko)
        logger.warn("### fellesrom_sted_id:%s ###" % (fellesrom_sted_id))
        logger.warn("*** %s, %s, %s ***" %(faknavn,fellesrom_sted_id,fellesrom_id))
        register_group(faknavn, fellesrom_sted_id, fellesrom_id,
                       allow_room=True)
    #print "##BEFORE##"

    register_spread_groups(emne_info, stprog_info, undakt_info)

    output_group_xml()
    #print "##ROOMS##"
    for room, data in new_rooms.iteritems():
        #print room
        fxml.room_to_XML(data['CFid'], STATUS_ADD, data)

    for node, data in new_acl.iteritems():
        fxml.acl_to_XML(node, STATUS_ADD, data)
        

    ### lets print out all members in a group
    ##for gname,member in new_groupmembers.iteritems():
    ##    print "gname = %s,member = %s" %(gname,member)

    #print "##GNAMES##"
    for gname, members in new_groupmembers.iteritems():
        #print gname
        fxml.personmembers_to_XML(gname, STATUS_ADD,
                                  members)
    fxml.end()


if __name__ == '__main__':
    main()

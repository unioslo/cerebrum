#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Copyright 2003 University of Oslo, Norway
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

import getopt
import sys
import os

import xml.sax

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum import Person
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.modules import PosixUser
from Cerebrum.modules.no import fodselsnr

fnr2person_id = {}
teacher2school = {}
student2classcourse = {}
student2class = {}
program = {}
person = {}
pupil = {}
institution = {}
ou_local2ou_id = {}
pers_local2ou_local = {}
ou_local2dns = {}


class SASDataParser(xml.sax.ContentHandler):
    """This class is used to iterate over information from SAS-XML-file. """

    def __init__(self, filename):
        xml.sax.parse(filename, self)
        self.var = None

    def characters(self, ch):
        self.var = ch.encode('iso8859-1')

    def startElement(self, name, attrs):
        if name in ("sastransfer","teacheratschool","classcoursestudents",
                    "studentsinclass","programs","students","administration",
                    "teachers","intstitutions"):
            pass
        elif name in ("teacherschool","classcoursestudents","studentinclass",
                      "program","student","person","institution"):
            self.data = {}
            for k in attrs.keys():
                self.data[k] = attrs[k].encode('iso8859-1')
        elif name in ("adressinfo",):
            for k in attrs.keys():
                self.data[k] = attrs[k].encode('iso8859-1')

    def endElement(self, name):
        if name == "teacherschool":
            teacher2school[self.data['personid']] = {}
            pers_local2ou_local[self.data['personid']] = self.data['schoolid']
            for i in self.data.keys():
                teacher2school[self.data['personid']][i] = self.data[i]
                                                            
        elif name == "classcoursestudents":
            id = "%s:%s:%s" % (self.data['countyid'],
                               self.data['schoolid'],
                               self.data['studentid'])
            student2classcourse[id] = {}
            pers_local2ou_local[self.data['studentid']] = self.data['schoolid']
            for i in self.data.keys():
                student2classcourse[id][i] = self.data[i]
                
        elif name == "studentinclass":
            id = "%s:%s:%s" % (self.data['countyid'],
                               self.data['schoolid'],
                               self.data['studentid'])
            student2class[id] = {}
            pers_local2ou_local[self.data['studentid']] = self.data['schoolid']
            for i in self.data.keys():
                student2class[id][i] = self.data[i]
                
        elif name == "program":
            id = "%s:%s:%s:%s" % (self.data['countyid'],
                                  self.data['schoolid'],
                                  self.data['classcode'],
                                  self.data['course'])
            program[id] = {}
            for i in self.data.keys():
                program[id][i] = self.data[i]
                
        elif name == "student":
            student[self.data['localid']] = {}
            for i in self.data.keys():
                if self.data.has_key(i):
                    student[self.data['localid']][i] = self.data[i]
            student[self.data['localid']]['type'] = 'pupil'

        elif name == "person":
            person[self.data['localid']] = {}
            for i in self.data.keys():
                person[self.data['localid']][i] = self.data[i]
            person[self.data['localid']]['type'] = 'teacher'

        elif name == "institution":
            institution[self.data['name']] = {}
            for i in self.data.keys():
                institution[self.data['name']][i] = self.data[i]
        else:
            self.data[name] = self.var

def prosess_data():
    prosess_OUs()
    init_mail()
    prosess_persons(pupil)
    prosess_persons(person)

def prosess_OUs():
    for o in institution.keys():
        op = None
        if not institution[o].has_key('name'):
            print "No name for OU."
            break

        ou_id = None
        ou.clear()
        ou.populate(institution[o]['name'])
        found = False
        tmp_ou = Factory.get('OU')(db)
        for row in ou.list_all():
            id = int(row['ou_id'])
            tmp_ou.clear()
            tmp_ou.find(id)
            if ou.__eq__(tmp_ou):
                found = True
                ou.clear()
                ou_id = tmp_ou.ou_id
                break
        if not found:
            print ": %s" % ou.name
            op = ou.write_db()
            ou.set_parent(co.perspective_sas, None)
            ou_id = ou.entity_id
        if op is None:
            print "**** EQUAL ****"
        elif op == True:
            print "**** NEW ****"
        elif op == False:
            print "**** UPDATE ****"
        db.commit()
        ou_local2ou_id[institution[o]['schoolid']] = ou_id
        ou_local2dns[institution[o]['schoolid']] = institution[o]['dns']

def prosess_persons(dict=None):
    person = dict
    if person == None:
        print "No parameter given! Exiting."
        sys.exit(1)
    for p in person.keys():
        fnr = 0
        if person[p].has_key('borndate') and person[p].has_key('socialsecno'):
            try:
                tmp = person[p]['borndate']
                (year, mon, day) = int(tmp[0:4]), int(tmp[4:6]), int(tmp[6:8])
                fnr = "%02d%02d%02d%05d" % (
                    int(tmp[6:8]), int(tmp[4:6]), int(tmp[2:4]),\
                    int(person[p]['socialsecno']))
            except ValueError:
                print "Ugyldig fødselsnr: %s" % fnr
                continue
            if (year < 1970
                and getattr(cereconf, "ENABLE_MKTIME_WORKAROUND", 0) == 1):
                # Seems to be a bug in time.mktime on some machines
                year = 1970
        else:
            print "No fnr. Skipping."
            continue
        
        gender = co.gender_male
        if(int(fnr[8]) % 2):
            gender = co.gender_female

        if person[p].has_key('givenname'):
            firstname =  person[p]['givenname']
            print "%s" % firstname
        else:
            print "No firstname: %s" % fnr
        if person[p].has_key('familynname'):
            lastname = person[p]['familynname']
            print "%s" % lastname
        else:
            print "No lastname: %s" % fnr
            
        new_person = Person.Person(db)
        new_person.clear()
        if fnr2person_id.has_key(fnr):
            new_person.find(fnr2person_id[fnr])
        
        print fnr, year, mon, day
        new_person.populate(db.Date(year, mon, day), gender)
        new_person.affect_names(co.system_sas, co.name_first, co.name_last)
        new_person.populate_name(co.name_first, firstname)
        new_person.populate_name(co.name_last, lastname)
        
        if person[p].has_key('localid'):
            new_person.affect_external_id(co.system_sas,
                                          co.externalid_sas_id,
                                          co.externalid_fodselsnr)
            new_person.populate_external_id(co.system_sas,
                                            co.externalid_sas_id,
                                            person[p]['localid'])
        else:
            new_person.affect_external_id(co.system_sas,
                                          co.externalid_fodselsnr)
        new_person.populate_external_id(co.system_sas,
                                        co.externalid_fodselsnr,
                                        fnr)
        aff = None
        ou_id = None
        if person[p]['type'] == 'pupil' and person[p].has_key('localid'):
            ou_id = ou_local2ou_id[pers_local2ou_local[person[p]['localtid']]]
            aff = co.affiliation_pupil
            new_person.populate_affiliation(co.system_sas,
                                            int(ou_id),
                                            aff,
                                            co.affiliation_status_pupil_active)
        elif person[p]['type'] == 'teacher' and person[p].has_key('localid'):
            ou_id = ou_local2ou_id[pers_local2ou_local[person[p]['localid']]]
            aff = co.affiliation_teacher
            new_person.populate_affiliation(co.system_sas,
                                            int(ou_id),
                                            aff,
                                            co.affiliation_status_teacher_active)
        
        if person[p].has_key('type'):
            if person[p]['type'] == 'pupil':
                pass
            elif person[p]['type'] == 'teacher':
                pass
            elif person[p]['type'] == 'administration':
                pass
        else:
            print "Warning: %s has no 'type'" % fnr
            
#        new_person.populate_affiliation(co.system_sas,
#                                        ou,
#                                        aff,
#                                        aff_status)

        op = new_person.write_db()
        if not fnr2person_id.has_key(fnr):
            fnr2person_id[fnr] = new_person.entity_id
        db.commit()
        prosess_user(new_person.entity_id,
                     person[p]['localid'],
                     int(aff),
                     firstname,
                     lastname)
        db.commit()
        
        if op is None:
            print "**** EQUAL ****"
        elif op == True:
            print "**** NEW ****"
        elif op == False:
            print "**** UPDATE ****"

def prosess_user(owner_id, local_id, aff, fname, lname):
    ac.clear()

    ou_id = pers_local2ou_local[local_id]

    rows = ac.list_accounts_by_owner_id(owner_id)
    if len(rows) > 0:
        lst = []
        for row in rows:
            lst.append((row['account_id'],ou_id))
        prosess_mail_address(lst)
        return lst
    
    posix_user = PosixUser.PosixUser(db)
    unames = posix_user.suggest_unames(co.account_namespace,
                                      fname, lname)
    # Dirty hack for getting free unames.
    uname = None
    for u in unames:
        try:
            ac.find_by_name(u)
        except Errors.NotFoundError:
            uname = u
    ac.populate(uname,
                co.entity_person,
                owner_id,
                None,
                default_creator_id,
                None)
    password = ac.make_passwd(uname)
    ac.set_password(password)

    tmp = ac.write_db()
    ac.add_spread(co.spread_cerebrum_user)
    
    print owner_id, ou_local2ou_id[pers_local2ou_local[local_id]], aff
    ac.set_account_type(ou_local2ou_id[ou_id], aff)
    
    tmp = ac.write_db()
    lst = ((ac.entity_id,ou_id),)
    prosess_mail_address(lst)
    print "new Account; %s, pw: %s, write_db=%s" % (uname,password,tmp)
    #db.commit()
    #all_passwords[int(account.entity_id)] = [password, profile.get_brev()]
    #update_account(profile, [account.entity_id])
    

def prosess_mail_address(ac_list):
    est = Email.EmailServerTarget(db)
    epat = Email.EmailPrimaryAddressTarget(db)
    for a,o in ac_list:
        ac.clear()
        ac.find(a)
        est.clear()
        try:
            est.find_by_entity(a)
            return
        except Errors.NotFoundError:
            et = Email.EmailTarget(db)
            ea = Email.EmailAddress(db)
            et.clear()
            et.find_by_entity(a)
            est.clear()
            est.populate(mser.entity_id, parent=et)
            est.write_db()
            ea.clear()
            mdom.clear()
            mdom.find_by_domain(ou_local2dns[o])

            prim = None
            # Does the foo.bar-address exist:
            try:
                ea.find_by_local_part_and_domain(ac.get_email_cn_local_part(),
                                                 mdom.email_domain_id)
                # If it did, we want to make uname an address:
                try:
                    ea.clear()
                    ea.find_by_local_part_and_domain(ac.account_name,
                                                 mdom.email_domain_id)
                    print "Warning! Could not make mail-address. Exists."
                    return
                # uname wasn't taken:
                except Errors.NotFoundError:
                    ea.clear()
                    ea.populate(ac.account_name,
                                mdom.email_domain_id,
                                et.email_target_id)
                    ea.write_db()
                    prim = ea.email_addr_id
            # foo.bar didn't exist:
            except Errors.NotFoundError:
                ea.clear()
                ea.populate(ac.get_email_cn_local_part(),
                            mdom.email_domain_id,
                            et.email_target_id)
                ea.write_db()
                prim = ea.email_addr_id
                # Make uname here as well:
                try:
                    ea.clear()
                    ea.find_by_local_part_and_domain(ac.account_name,
                                                     mdom.email_domain_id)
                except Errors.NotFoundError:
                    ea.clear()
                    ea.populate(ac.account_name,
                                mdom.email_domain_id,
                                et.email_target_id)
                    ea.write_db()
                
            epat.clear()
            try:
                epat.find(et.email_target_id)
            except Errors.NotFoundError:
                epat.clear()
                epat.populate(prim, et)
                epat.write_db()
        


def prosess_teachers_schools(data):
    pass


def prosess_guardians(data):
    pass


def init_mail():
    global mdom, mser
    mdom = Email.EmailDomain(db)

    #    try:
    #        mdom.find_by_domain(cereconf.EMAIL_DEFAULT_DOMAIN)
    #    except Errors.NotFoundError:
    #        mdom.clear()
    #        mdom.populate(cereconf.EMAIL_DEFAULT_DOMAIN,
    #                      'Default Email-domain')
    #        mdom.write_db()
    #        db.commit()

    for d in ou_local2dns.keys():
        mdom.clear()
        try:
            mdom.find_by_domain(ou_local2dns[d])
        except Errors.NotFoundError:
            mdom.populate(ou_local2dns[d],
                      'Schools primary domain.')
        mdom.write_db()
        db.commit()

    mser = Email.EmailServer(db)

    try:
        mser.find_by_server_name(cereconf.EMAIL_DEFAULT_SERVER)
    except Errors.NotFoundError:
        mser.clear()
        mser.populate(co.email_server_type_cyrus,
                      cereconf.EMAIL_DEFAULT_SERVER,
                      'Default Email-server')
        mser.write_db()
        db.commit()


def usage():
    print """Usage: import_SAS_XML.py
    -v, --verbose : Show extra information.
    -f, --file    : File to parse.
    """


def main():
    global db, ou, co, ac, default_creator_id

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'vf:', ['verbose','file'])
    except getopt.GetoptError:
        usage()
        
    verbose = 0
    xmlfile = None

    for opt, val in opts:
        if opt in ('-v', '--verbose'):
            verbose += 1
        elif opt in ('-f', '--file'):
            xmlfile = val

    if xmlfile is None:
        usage()

    db = Factory.get('Database')()
    db.cl_init(change_program='import_SAS-XML')
    ou = Factory.get('OU')(db)
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    person = Person.Person(db)

    for p in person.list_external_ids(id_type=co.externalid_fodselsnr):
        if co.system_sas == p['source_system']:
            fnr2person_id[p['external_id']] = p['person_id']
        elif not fnr2person_id.has_key(p['external_id']):
            fnr2person_id[p['external_id']] = p['person_id']

    ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    default_creator_id = ac.entity_id
    SASDataParser(xmlfile)
    prosess_data()
    db.commit()

if __name__ == '__main__':
    main()

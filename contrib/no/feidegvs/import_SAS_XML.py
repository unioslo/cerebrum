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
import re

import xml.sax

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum import Person
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.modules import PosixUser
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.feidegvs import FeideGvs

fnr2person_id = {}
teacher2school = {}
student2classcourse = {}
student2class = {}
program = {}
person = {}
parent = {}
institution = {}
ou_local2ou_id = {}
per_l2ou_l = {}
ou_id2dns = {}
fnr2local_id = {}
par_l2ch_l = {}
per_l2per_id = {}

class SASDataParser(xml.sax.ContentHandler):
    """This class is used to iterate over information from SAS-XML-file. """

    def __init__(self, filename):
        xml.sax.parse(filename, self)
        self.var = None

    def characters(self, ch):
        self.var = ch.encode('iso8859-1')

    def startElement(self, name, attrs):
        if name in ("sastransfer","teacheratschool","classcoursestudents",
                    "studentsinclass","programs","intstitutions"):
            pass
        elif name in ("students",):
            self.ad = 's'
        elif name in ("teachers",):
            self.ad = 't'
        elif name in ("administration",):
            self.ad = 'a'
        elif name in ("parents",):
            self.ad = 'p'
        elif name in ("employees",):
            self.ad = 'e'
        elif name in ("teacherschool","classcoursestudents","studentinclass",
                      "program","student","person","institution",
                      "employee-school","parent"):
            self.data = {}
            for k in attrs.keys():
                self.data[k] = attrs[k].encode('iso8859-1')
        elif name in ("adressinfo",):
            for k in attrs.keys():
                self.data[k] = attrs[k].encode('iso8859-1')

    def endElement(self, name):
        if name in ("sastransfer","teacheratschool","classcoursestudents",
                    "studentsinclass","programs","intstitutions",
                    "students","administration", "teacher",
                    "employeesatschool"):
            pass

        elif name == "teacherschool":
            #teacher2school[self.data['personid']] = {}
            p_id = self.data['personid']
            s_id = self.data['schoolid']
            per_l2ou_l.setdefault(p_id, []).append(s_id)
            #for i in self.data.keys():
            #    teacher2school[self.data['personid']][i] = self.data[i]
        elif name == "employee-school":
            d = self.data['socialsecno']
            m = re.search(r'(\d{2})(\d{2})(\d{2})(\d{5})', d)
            if m:
                d = "19%02d%02d%02d:%05d" % (int(m.group(3)), int(m.group(2)),
                                            int(m.group(1)), int(m.group(4)))
            else:
                print "ERROR: Didn't work: %s" % d
                sys.exit(0)
            if fnr2local_id.has_key(d):
                s_id = self.data['schoolid']
                per_l2ou_l.setdefault(fnr2local_id[d], []).append(s_id)
            else:
                print "WARNING: Didn't find %s in per_l2ou_l" % d
                    
            
        elif name == "classcoursestudents":
            #id = "%s:%s:%s" % (self.data['countyid'],
            #                   self.data['schoolid'],
            #                   self.data['studentid'])
            #student2classcourse[id] = {}
            st_id = self.data['studentid']
            sc_id = self.data['schoolid']
            per_l2ou_l.setdefault(st_id, []).append(sc_id)
            #for i in self.data.keys():
            #    student2classcourse[id][i] = self.data[i]
                
        elif name == "studentinclass":
            #id = "%s:%s:%s" % (self.data['countyid'],
            #                   self.data['schoolid'],
            #                   self.data['studentid'])
            #student2class[id] = {}
            st_id = self.data['studentid']
            sc_id = self.data['schoolid']
            per_l2ou_l.setdefault(st_id, []).append(sc_id)
            #for i in self.data.keys():
            #    student2class[id][i] = self.data[i]
                
        elif name == "program":
            #id = "%s:%s:%s:%s" % (self.data['countyid'],
            #                      self.data['schoolid'],
            #                      self.data['classcode'],
            #                      self.data['course'])
            #program[id] = {}
            #for i in self.data.keys():
            #    program[id][i] = self.data[i]
            pass
 
        elif name == "person":
            person[self.data['localid']] = {}
            for i in self.data.keys():
                person[self.data['localid']][i] = self.data[i]
            if self.data.has_key('borndate') and \
                   self.data.has_key('socialsecno'):
                fnr2local_id["%s:%s" % (self.data['borndate'],
                                        self.data['socialsecno'])] = \
                                        self.data['localid']
            else:
                print "WARNING: no birthdate %s" % self.data['localid']
            if self.ad == 'a':
                person[self.data['localid']]['type'] = 'admin'
            elif self.ad == 't':
                person[self.data['localid']]['type'] = 'teacher'
            elif self.ad == 'p':
                person[self.data['localid']]['type'] = 'parent'
            elif self.ad == 'e':
                person[self.data['localid']]['type'] = 'employee'
            else:
                person[self.data['localid']]['type'] = 'pupil'

        elif name == "institution":
            institution[self.data['name']] = {}
            for i in self.data.keys():
                institution[self.data['name']][i] = self.data[i]

        elif name == "parent":
            p_id = self.data['personid']
            c_id = self.data['childid']
            par_l2ch_l.setdefault(p_id, []).append(c_id)
            
        else:
            self.data[name] = self.var


def process_data():
    process_OUs()
    init_mail()
    process_persons(person)
    process_guardians()

def process_OUs():
    for o in institution.keys():
        op = None
        if not institution[o].has_key('name'):
            print "WARNING: No name for OU."
            continue

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
            op = ou.write_db()
            ou.set_parent(co.perspective_sas, None)
            ou_id = ou.entity_id
        if op is None:
            print "**** EQUAL ****"
        elif op == True:
            print "**** NEW ****"
        elif op == False:
            print "**** UPDATE ****"
        print "   ", institution[o]['name'], ou_id
        db.commit()
        ou_local2ou_id[institution[o]['schoolid']] = ou_id
        ou_id2dns[ou_id] = institution[o]['dns']

def process_persons(pers):
    # Iterate over all persons:
    for p in pers.keys():
        fnr = 0
        if not person[p].has_key('localid'):
            print "WARNING: No localid for person. Skipping."
            continue
        # Get the persons norSSN:
        if person[p].has_key('borndate') and person[p].has_key('socialsecno'):
            try:
                tmp = person[p]['borndate']
                (year, mon, day) = int(tmp[0:4]), int(tmp[4:6]), int(tmp[6:8])
                fnr = "%02d%02d%02d%05d" % (
                    int(tmp[6:8]), int(tmp[4:6]), int(tmp[2:4]),\
                    int(person[p]['socialsecno']))
            except ValueError:
                print "WARNING: Ugyldig fødselsnr: %s" % fnr
                continue
            if (year < 1970
                and getattr(cereconf, "ENABLE_MKTIME_WORKAROUND", 0) == 1):
                # Seems to be a bug in time.mktime on some machines
                year = 1970
        else:
            print "WARNING: No fnr for '%s'. Skipping." % p
            continue
        # Decide gender:
        gender = co.gender_male
        if(int(fnr[8]) % 2):
            gender = co.gender_female
        # Process and register names:
        if person[p].has_key('givenname'):
            firstname =  person[p]['givenname']
        else:
            print "WARNING: No firstname: %s. Skipping." % fnr
            continue
        if person[p].has_key('familynname'):
            lastname = person[p]['familynname']
        else:
            print "WARNING: No lastname: %s. Skipping" % fnr
            continue

        # Make the person.
        new_person = Person.Person(db)
        new_person.clear()
        if fnr2person_id.has_key(fnr):
            new_person.find(fnr2person_id[fnr])
        
        new_person.populate(db.Date(year, mon, day), gender)
        new_person.affect_names(co.system_sas, co.name_first, co.name_last)
        new_person.populate_name(co.name_first, firstname)
        new_person.populate_name(co.name_last, lastname)

        new_person.affect_external_id(co.system_sas,
                                      co.externalid_sas_id,
                                      co.externalid_fodselsnr)
        new_person.populate_external_id(co.system_sas,
                                        co.externalid_sas_id,
                                        person[p]['localid'])
        new_person.populate_external_id(co.system_sas,
                                        co.externalid_fodselsnr,
                                        fnr)
        # Start mapping person <-> OUs iff parent;
        # look at that parents children for OUs:
        if pers[p]['type'] == 'parent':
            p_id = person[p]['localid']
            if par_l2ch_l.has_key(p_id):
                for c in par_l2ch_l[p_id]:
                    if person.has_key(c):
                        c_id = person[c]['localid']
                        if per_l2ou_l.has_key(c_id):
                            for ou_l in  per_l2ou_l[c_id]:
                                per_l2ou_l.setdefault(p_id, []).append(ou_l)
                        else:
                            print "WARNING: No child ",c_id,\
                                  "' in per_l2ou_l. Error."
                    else:
                        print "WARNING: Parent: %s; No child: %s." % (
                            p_id,c) 
                                
        # Process person <-> OU:
        ou_ids = {}
        if per_l2ou_l.has_key(person[p]['localid']):
            p_id = person[p]['localid']
            try:
                for ou_l in per_l2ou_l[p_id]:
                    ou_ids[ou_local2ou_id[ou_l]] = ou_local2ou_id[ou_l]
            except KeyError:
                print "WARNING: Person '%s' belongs to OU not defined: %s" % (
                    p_id, ou_l)
            if ou_ids.keys() == []:
                print "WARNING: Found no OU for person: %s. Skipping." % p_id
                continue
        else:
            print "WARNING: Found no OU for person: %s. Skipping." % \
                  person[p]['localid']
            continue

        # Process affiliations:
        aff = None
        aff_status = None
        if person[p]['type'] == 'pupil' and person[p].has_key('localid'):
            aff = co.affiliation_pupil
            aff_status = co.affiliation_status_pupil_active
        elif person[p]['type'] == 'teacher' and person[p].has_key('localid'):
            aff = co.affiliation_teacher
            aff_status = co.affiliation_status_teacher_active
        elif person[p]['type'] == 'admin' and person[p].has_key('localid'):
            aff = co.affiliation_admin
            aff_status = co.affiliation_status_admin_active
        elif person[p]['type'] == 'parent' and person[p].has_key('localid'):
            aff = co.affiliation_guardian
            aff_status = co.affiliation_status_guardian_active
        elif person[p]['type'] == 'employee' and person[p].has_key('localid'):
            aff = co.affiliation_employee
            aff_status = co.affiliation_status_employee_active
        for ou in ou_ids.keys():
            new_person.populate_affiliation(co.system_sas,
                                            int(ou),
                                            aff,
                                            aff_status)
        
        # Write to db:
        op = new_person.write_db()
        # Register fnr<->e_id and local_id<->e_id:
        if not fnr2person_id.has_key(fnr):
            fnr2person_id[fnr] = new_person.entity_id
        db.commit()
        per_l2per_id[person[p]['localid']] = new_person.entity_id
        
        #Make user and e-mail addresses:
        lst = []
        for ou in ou_ids.keys():
            lst.append(process_user(new_person.entity_id,
                                    ou,
                                    int(aff),
                                    firstname,
                                    lastname))
        if lst != []:
            process_mail_address(lst)

        # Commit it.
        db.commit()
        
        if op is None:
            print "**** EQUAL ****"
        elif op == True:
            print "**** NEW ****"
        elif op == False:
            print "**** UPDATE ****"
        print "   ", firstname, lastname, fnr

def process_user(owner_id, ou_id, aff, fname, lname):
    ac.clear()
    rows = ac.list_accounts_by_owner_id(owner_id)
    if len(rows) > 0:
        for row in rows:
            a_id = row['account_id']
            ac.clear()
            ac.find(a_id)
            found = False
            for row2 in ac.get_account_types():
                if row2['ou_id'] == ou_id and \
                   row2['person_id'] == owner_id:
                    found = True
            if not found:
                ac.set_account_type(ou_id, aff)
        return (row['account_id'],ou_id)
            
    unames = ac.suggest_unames(co.account_namespace, fname, lname)
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
    ac.set_account_type(ou_id, aff)
    
    tmp = ac.write_db()
    lst = (ac.entity_id,ou_id)
    return lst
        

def process_mail_address(ac_list):
    et = Email.EmailTarget(db)
    ea = Email.EmailAddress(db)
    est = Email.EmailServerTarget(db)
    epat = Email.EmailPrimaryAddressTarget(db)
    for a,o in ac_list:
        ac.clear()
        ac.find(a)
        est.clear()
        try:
            est.find_by_entity(a)
            #continue
        except Errors.NotFoundError:
            et.clear()
            et.find_by_entity(a)
            est.clear()
            est.populate(mser.entity_id, parent=et)
            est.write_db()
            ea.clear()
        mdom.clear()
        mdom.find_by_domain(ou_id2dns[o])

        try:
            # Does the foo.bar-address exist:
            ea.clear()
            ea.find_by_local_part_and_domain(ac.get_email_cn_local_part(),
                                             mdom.email_domain_id)
            try:
                # If it did, we want to make uname an address:
                ea.clear()
                ea.find_by_local_part_and_domain(ac.account_name,
                                                 mdom.email_domain_id)
                # Iff found:
                found = False
                for row in ea.list_target_addresses(est.email_target_id):
                    ea.clear()
                    ea.find(row['address_id'])
                    if (ea.email_addr_local_part == ac.get_email_cn_local_part() \
                        or ea.email_addr_local_part == ac.account_name) \
                       and ea.email_addr_domain_id == mdom.email_domain_id:
                        # It is the targets own. No update needed.
                        found = True
                if not found:
                    print "WARNING: Could not make mail-address. Exists.",\
                          "  %s and %s @ %s" % (ac.account_name,
                                                ac.get_email_cn_local_part(),
                                                mdom.email_domain_name)
                    continue
            except Errors.NotFoundError:
                # uname wasn't taken:
                ea.clear()
                ea.populate(ac.account_name,
                            mdom.email_domain_id,
                            est.email_target_id)
                ea.write_db()
                prim = ea.email_addr_id
                
        except Errors.NotFoundError:
            # foo.bar didn't exist:
            ea.clear()
            ea.populate(ac.get_email_cn_local_part(),
                        mdom.email_domain_id,
                        est.email_target_id)
            ea.write_db()
            prim = ea.email_addr_id
                
            try:
                # Make uname here as well:
                ea.clear()
                ea.find_by_local_part_and_domain(ac.account_name,
                                                 mdom.email_domain_id)
                # Iff found:
                found = False
                for row in ea.list_target_addresses(est.email_target_id):
                    ea.clear()
                    ea.find(row['address_id'])
                    if ea.email_addr_local_part == ac.get_email_cn_local_part() \
                       and ea.email_addr_domain_id == mdom.email_domain_id:
                        # It is the targets own. No update needed.
                        found = True
                if not found:
                    print "WARNING: Could not make mail-address. Exists.",\
                          "  %s @ %s" % (ac.account_name, mdom.email_domain_name)
                    continue
            except Errors.NotFoundError:
                ea.clear()
                ea.populate(ac.account_name,
                            mdom.email_domain_id,
                            est.email_target_id)
                ea.write_db()
                
        epat.clear()
        try:
            epat.find(est.email_target_id)
        except Errors.NotFoundError:
            epat.clear()
            epat.populate(prim, est)
            epat.write_db()
        


def process_teachers_schools(data):
    pass


def process_guardians():
    fgg = FeideGvs.FeideGvsGuardian(db)
    for p in par_l2ch_l.keys():
        fgg.clear()
        for ch_l in par_l2ch_l[p]:
            p_id = None
            c_id = None
            if per_l2per_id.has_key(p):
                p_id = per_l2per_id[p]
            else:
                print "WARNING: (proc_guard) Parent not found: %s" % p
                continue
            if per_l2per_id.has_key(ch_l):
                c_id = per_l2per_id[ch_l]
            else:
                print "WARNING: (proc_guard) Child not found: %s" % ch_l
                continue
            try:
                fgg.find(p_id, c_id)
            except Errors.NotFoundError:
                fgg.clear()
                fgg.populate(p_id, c_id, co.feide_gvs_guardian_parent)
                fgg.write_db()
    db.commit()


def init_mail():
    global mdom, mser
    mdom = Email.EmailDomain(db)

    try:
        mdom.find_by_domain(cereconf.EMAIL_DEFAULT_DOMAIN)
    except Errors.NotFoundError:
        mdom.clear()
        mdom.populate(cereconf.EMAIL_DEFAULT_DOMAIN,
                      'Default Email-domain')
        mdom.write_db()
        db.commit()

    for d in ou_id2dns.keys():
        mdom.clear()
        try:
            mdom.find_by_domain(ou_id2dns[d])
        except Errors.NotFoundError:
            mdom.populate(ou_id2dns[d],
                      'Schools primary domain.')
        mdom.write_db()
        db.commit()

    mser = Email.EmailServer(db)

    try:
        mser.find_by_name(cereconf.EMAIL_DEFAULT_SERVER)
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
    process_data()
    db.commit()

if __name__ == '__main__':
    main()

# arch-tag: 0fa609c8-d427-4da4-b8b6-6e58f7709b63

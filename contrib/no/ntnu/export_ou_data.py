#! /usr/bin/env python
# -*- encoding: iso-8859-1 -*-

#
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
#
# $Id$
#

"""
This is an example client that uses python interactive mode to work against
spine.  It adds some shortcuts to often used functionality, but is basically
just a convenient way to connect to Spine and test out things from the 
command line.

For command line completion and such, add the following three lines to your
~/.pythonrc.py:
import rlcompleter
import readline
import sys

readline.parse_and_bind("tab: complete")

Make sure PYTHONPATH contains the path to SpineClient.py and that SpineCore.idl
is in the same directory as SpineClient.py.
"""

import user
import sys, os
import SpineIDL.Errors
import ConfigParser
conf = ConfigParser.ConfigParser()
conf.read(('client.conf.template', 'client.conf'))

try:
    import SpineClient
except:
    print >> sys.stderr, """Importing SpineClient failed.
Please make sure cerebrum/spine/client is in your PYTHONPATH
environment variable.  Example:
export PYTHONPATH=$PYTHONPATH:~/cerebrum/spine/client/"""
    sys.exit(1)

def _login(username=None, password=None):
    global wrapper, __s, tr, c
    wrapper = Session(username=username, password=password)
    __s = wrapper.session
    tr = wrapper.tr
    c = wrapper.c

def _new_transaction():
    global wrapper, tr, c
    wrapper.new_transaction()
    tr = wrapper.tr
    c = wrapper.c
        
class Session(object):
    def __init__(self, ior_file=None, username=None, password=None):
        print "Loggin in..."
        self.username = username or conf.get('login', 'username')
        self.password = password or conf.get('login', 'password')
        ior_file = ior_file or conf.get('SpineClient', 'url')
        cache_dir = conf.get('SpineClient', 'idl_path')
        self.spine = SpineClient.SpineClient(ior_file, idl_path=cache_dir).connect()
        self.session = self.spine.login(self.username, self.password)
        self.new_transaction()

    def new_transaction(self):
        self.tr = self.session.new_transaction()
        self.c = self.tr.get_commands()

    def __del__(self):
        print "Logging out..."
        for i in self.session.get_transactions():
            i.rollback()
        self.session.logout()

_login()

buffersize = 16384
external_id_type = tr.get_entity_external_id_type("NO_BIRTHNO")
source_system = tr.get_source_system('Cached')
first_name_type = tr.get_name_type('FIRST')
last_name_type = tr.get_name_type('LAST')
search_ou = 'ORG/IT'

#
# todo:
# outfile should be placed in a conig-file...
#
f = open("/tmp/export_ou_data.sdv", "w", buffersize)

#
# export file format:
# entity_id;birthdate;nin;birthday;givenname;surname;mail;affiliation;ou-code;username;
#

print 'Getting persons...'
i = 0
persons = tr.get_person_searcher().search()
for person in persons:
    entity_id = str(person.get_id())
    affs = person.get_affiliations()
    for aff in affs:
        ou = aff.get_ou()
        if ou.get_acronym() == search_ou:
            i += 1
            day = ''
            month = ''
            year = ''
            birthdate_iso = ''
            bdate = person.get_birth_date()
            if bdate:
                day = str(bdate.get_day())
            if bdate.get_day() < 10:
                day = '0' + day
            month = str(bdate.get_month())
            if bdate.get_month() < 10:
                month = '0' + month
            year = str(bdate.get_year())
            birthdate_iso = bdate.strftime("%Y-%m-%d")
            birthdate=day+month+year
    
            #
            # had to use try, except because of unlegal data in db
            # maybe it is time to remove this?
            #
            try:
                nin = str(person.get_external_id(external_id_type, source_system))
            except SpineIDL.Errors.NotFoundError, e:
                nin=''

            try:
                givenname = person.get_name(first_name_type, source_system)
            except SpineIDL.Errors.NotFoundError, e:
                givenname = ''

            try:
                surname = person.get_name(last_name_type, source_system)
            except SpineIDL.Errors.NotFoundError, e:
                givenname = ''
    
            email = ''
            emailtarget_searcher = tr.get_email_target_searcher()
            emailtarget_searcher.set_entity(person)
            targets = emailtarget_searcher.search()
            if targets:
                for target in targets:
                    email = target.get_primary_address().get_name()
    
            affiliation = ''
            ou_code = ''
            username = ''
            primary_account = person.get_primary_account()

            #
            # todo:
            # which affiliation and which ou are the right ones?
            #
            if primary_account:
                affiliations = primary_account.get_affiliations()
                if affiliations:
                    for aff in affiliations:
                        affiliation = aff.get_affiliation().get_name()
                        ou_code = str(aff.get_ou().get_stedkode())
    
                username = primary_account.get_name()
            line = entity_id+";"+birthdate+";"+nin+";"+birthdate_iso+";"+givenname+";"+surname+";"+email+";"+affiliation+";"+ou_code+";"+username+';\n'
            f.write(line)
            if (i % 10) == 0:
                print str(i) + ' lines written...'

print 'Total: ' + str(i) + ' persons processed.'
f.flush()
f.close()
sys.exit(0)

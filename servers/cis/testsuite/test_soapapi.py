#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014 University of Oslo, Norway
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

"""Tests for the generic SOAP API."""

import sys
import getopt
import suds
import logging
import string
import random


class TestSoapAPI:
    def __init__(self, wsdl, username, password, debug):
        self.wsdl = wsdl

        if debug:
            logging.basicConfig(level=logging.INFO)
            logging.getLogger('suds.client').setLevel(logging.INFO)
            logging.getLogger('suds.transport').setLevel(logging.INFO)
            logging.getLogger('suds.xsd.schema').setLevel(logging.INFO)
            logging.getLogger('suds.wsdl').setLevel(logging.INFO)
        else:
            logging.basicConfig(filename='/dev/null')

        self.client = suds.client.Client(self.wsdl, cache=None)

        if username and password:
            self.authenticate(username, password)

        if debug:
            print self.client
            print "\n"

        self.test_all_methods()

    def test_all_methods(self):
        to_test = []

        for service in self.client.wsdl.services:
            for port in service.ports:
                for method in port.methods:
                    if service.name == 'PasswordAuthenticationService':
                        continue
                    test_method = "_".join(('test', service.name, method))
                    if hasattr(self, test_method) and callable(
                            getattr(self, test_method)):
                        print "Testable",
                        to_test.append((service.name, method,
                                        getattr(self, test_method)))
                    else:
                        print "Not testable",
                    print "\tMethod: %s.%s" % (service.name, method)

        for test in to_test:
            print "\nCalling test method for %s.%s:" % (test[0], test[1])
            test[2]()

    def test_method(self, method_name, **kwargs):
        try:
            method = getattr(self.client.service, method_name)
            result = method(**kwargs)
        except suds.WebFault, e:
            print "\t\t" + str(e)
            return
        print "\t\tGot result:", result

    def authenticate(self, username, password):
        print "Authenticating as", username
        try:
            result = self.client.service.authenticate(
                username='bootstrap_account', password='test')
        except suds.WebFault, e:
            print 'Caught fault:', e
            return
        print "Got session ID: %s\n" % result
        self.session = self.client.factory.create('{tns}SessionHeader')
        self.session.session_id = result
        self.client.set_options(soapheaders=self.session)

    def test_GroupAPIService_group_create(self):
        from datetime import datetime

        random_group_name = 'test_group_' + ''.join(
            random.sample(string.lowercase, 10))
        print "\tCreating a group that does not exist:", random_group_name
        self.test_method(
            method_name='group_create',
            group_name=random_group_name,
            description='Dette er en flott gruppe til bruk under testing',
            expire_date=datetime.now().replace(datetime.now().year + 1),
            visibility='A',
        )

        print "\tCreating a group that exists:"
        self.test_method(
            method_name='group_create',
            group_name='bootstrap_group',
            description='Description goes here',
            expire_date=None,
            visibility='A',
        )

        print "\tCreating a group with invalid group visibility:"
        random_group_name = 'test_group_' + ''.join(
            random.sample(string.lowercase, 10))
        self.test_method(
            method_name='group_create',
            group_name=random_group_name,
            description='Description goes here',
            expire_date=None,
            visibility='ShouldNotWork',
        )

    def test_GroupAPIService_group_info(self):
        print "\tGetting group information about group_name:bootstrap_group:"
        self.test_method(
            method_name='group_info',
            group_id_type='group_name',
            group_id='bootstrap_group',
        )

        random_group_name = 'test_group_' + ''.join(
            random.sample(string.lowercase, 10))
        print("\tGetting group information about a non-existing group:",
              random_group_name)
        self.test_method(
            method_name='group_info',
            group_id_type='group_name',
            group_id=random_group_name,
        )

    def test_GroupAPIService_group_add_member(self):
        print("\tAdding member account_name:bootstrap_account to group_name:"
              "testgruppe")
        self.test_method(
            method_name='group_add_member',
            group_id_type='group_name',
            group_id='testgruppe',
            member_id_type='account_name',
            member_id='bootstrap_account',
        )

    def test_GroupAPIService_group_remove_member(self):
        print("\tRemoving member account_name:bootstrap_account from "
              "group_name:testgruppe")
        self.test_method(
            method_name='group_remove_member',
            group_id_type='group_name',
            group_id='testgruppe',
            member_id_type='account_name',
            member_id='bootstrap_account',
        )


def usage(exitcode=0):
    print "USAGE:"
    print "\tNo auth:   python test_soapapi.py -w <your WSDL>"
    print("\tWith auth: python test_soapapi.py -w <your WSDL> -u <username> "
          "-p <password>")
    print "OPTIONS:"
    print "\t-w / --wsdl:     Sets the WSDL URI"
    print "\t-d / --debug:    Gives more logging!"
    print "\t-u / --user:     Username used for authentication"
    print "\t-p / --password: Password used for authentication"
    sys.exit(exitcode)


if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(
            sys.argv[1:], 'wdup', ['wsdl=', 'debug=', 'username=', 'password='])
    except getopt.GetoptError, e:
        print e
        sys.exit(1)

    wsdl = None
    debug = False
    username = None
    password = None

    for opt, val in opts:
        if opt in ('-w', '--wsdl'):
            wsdl = val
        elif opt in ('-d', '--debug'):
            debug = True
        elif opt in ('-u', '--username'):
            username = val
        elif opt in ('-p', '--password'):
            password = val
        else:
            print "Unknown argument: %s" % opt
            usage(1)

    if not wsdl:
        print 'Missing WSDL'
        usage(1)

    test = TestSoapAPI(wsdl=wsdl, username=username, password=password,
                       debug=debug)

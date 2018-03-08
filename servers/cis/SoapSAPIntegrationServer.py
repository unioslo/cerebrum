#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2010 University of Oslo, Norway
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
import getopt
import SoapListener
from lxml import etree

import cerebrum_path
import cereconf
from Cerebrum.modules.cis import Utils as CISutils

from soaplib.service import rpc
from soaplib.serializers.primitive import String, Boolean
from soaplib.serializers.clazz import ClassSerializer, Array
from soaplib.wsgi import Application

from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.web.wsgi import WSGIResource
from twisted.internet import reactor
from twisted.python.log import startLogging

del cerebrum_path

try:
    from twisted.internet import ssl
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

"""
This file provides a SOAP server for the Cerebrum - SAP Integration
Service.

TODO: Describe ...
"""
# FIXME: define namespace properly
ns_test = 'tns'


class PersonInfo(ClassSerializer):
    __namespace__ = ns_test
    Ansattnr = String
    Fornavn = String
    Mellomnavn = String
    Etternavn = String
    Title = String
    Fodselsnummer = String
    Fodselsdato = String
    Kjonn = String
    Nasjonalitet = String
    Kommspraak = String


class PersonAddress(ClassSerializer):
    __namespace__ = ns_test
    Ansattnr = String
    AdressType = String
    CO = String
    Gateadress = String
    Adressetillegg = String
    Postnummer = String
    Poststed = String
    Landkode = String
    Reservert = String


class PersonCom(ClassSerializer):
    __namespace__ = ns_test
    Ansattnr = String
    KommType = String
    KommValue = String


class PersonStilling(ClassSerializer):
    __namespace__ = ns_test
    Ansattnr = String
    Stilling_Id = String
    Stillingsgruppe_Id = String
    Start_Date = String
    End_Date = String
    Orgenhet = String


class PersonHovedstilling(PersonStilling):
    pass


class PersonBistilling(PersonStilling):
    pass


class Person(ClassSerializer):
    __namespace__ = ns_test
    PersonInfo = PersonInfo.customize(max_occurs='unbounded')
    PersonAddress = PersonAddress.customize(max_occurs='unbounded')
    PersonComm = PersonCom.customize(max_occurs='unbounded')
    PersonHovedstilling = PersonHovedstilling.customize(max_occurs='unbounded')
    PersonBistilling = PersonBistilling.customize(max_occurs='unbounded')


class SAPIntegrationServer(SoapListener.BasicSoapServer):
    """
    This class defines the SOAP actions that should be available to
    clients. All those actions are decorated as a rpc, defining what
    parameters the methods accept, types and what is returned.
    """

    @rpc(String, String, _returns=Array(String))
    def get_person_data(self, id_type, ext_id):
        """
        Based on id-type and the id, identify a person in Cerebrum and
        return name of primary account and primary email address.

        If person exist but doesn't have any accounts return an empty
        list. If no person match id_type, my_id, throw a ...Exception.
        """
        # Allow any type of exception? Does SOAP handle that?
        return CISutils.get_person_data(id_type, ext_id)

    @rpc(Person, _returns=Boolean)
    def update_person(self, Ansatt):
        """
        get sap_person object from client. Convert sap_person from xml
        to object and update Cerebrum.
        """
        xml_person = etree.Element('test')
        Person.to_xml(Ansatt, ns_test, xml_person)
        xml_person = xml_person[0]
        print "xml_person:", etree.tostring(xml_person, pretty_print=True)

        # p = SAPXMLPerson2Cerebrum(xml_person)
        return True

    def on_method_exception_object(self, environ, exc):
        '''
        Called BEFORE the exception is serialized, when an error occurs durring
        execution
        @param the wsgi environment
        @param the exception object
        '''
        print "on_method_exception_object", environ, exc

    def on_method_exception_xml(self, environ, fault_xml):
        '''
        Called AFTER the exception is serialized, when an error occurs durring
        execution
        @param the wsgi environment
        @param the xml element containing the exception object serialized to a
        soap fault
        '''
        print "on_method_exception_xml", environ, fault_xml


def usage(exitcode=0):
    print """Usage: %s [-p <port number] [-l logfile] [--unencrypted]
  -p | --port num: run on alternative port (default: ?)
  -l | --logfile: where to log
  --unencrypted: don't use https
  """
    sys.exit(exitcode)

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'p:l:',
                                   ['port=', 'unencrypted', 'logfile='])
    except getopt.GetoptError:
        usage(1)

    use_encryption = CRYPTO_AVAILABLE
    port = cereconf.SAPINTEGRATION_SERVICE_PORT
    logfile = cereconf.SAPINTEGRATION_SERVICE_LOGFILE

    for opt, val in opts:
        if opt in ('-l', '--logfile'):
            logfile = val
        elif opt in ('-p', '--port'):
            port = int(val)
        elif opt in ('--unencrypted',):
            use_encryption = False

    # TBD: Use Cerebrum logger instead?
    # Init twisted logger
    log_observer = startLogging(file(logfile, 'w'))
    # Run service
    service = Application([SAPIntegrationServer], 'tns')
    resource = WSGIResource(reactor, reactor.getThreadPool(), service)
    root = Resource()
    root.putChild('SOAP', resource)
    if use_encryption:
        # TODO: we need to set up SSL properly
        sslcontext = ssl.DefaultOpenSSLContextFactory(
            cereconf.SSL_PRIVATE_KEY_FILE,
            cereconf.SSL_CERTIFICATE_FILE)
        reactor.listenSSL(int(port), Site(root), contextFactory=sslcontext)
    else:
        reactor.listenTCP(int(port), Site(root))
    reactor.run()

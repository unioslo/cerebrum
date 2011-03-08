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

import cerebrum_path
import cereconf
from Cerebrum.modules.cis import Individuation

from soaplib.core import Application
from soaplib.core.server import wsgi
from soaplib.core.service import rpc
from soaplib.core.model.primitive import String, Integer, Boolean
from soaplib.core.model.clazz import ClassModel, Array

from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.web.wsgi import WSGIResource
from twisted.internet import reactor
from twisted.python import log

try:
    from twisted.internet import ssl
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

"""
This file provides a SOAP server for the Individuation service at UiO.

TODO: Describe ...

TODO: validate_password and set_password methods still missing

"""

# TODO: authenticate


class Account(ClassModel):
    # FIXME: define namespace properly 
    __namespace__ = 'account'
    uname = String
    priority = Integer
    status = String


class IndividuationServer(SoapListener.BasicSoapServer):
    """
    This class defines the SOAP actions that should be available to
    clients. All those actions are decorated as a rpc, defining
    what parameters the methods accept, types and what is returned.
    """


    @rpc(String, String, _returns=Array(Account))
    def get_usernames(self, id_type, ext_id):
        """
        Based on id-type and the id, identify a person in Cerebrum and
        return a list of the persons account and their status.

        If person exist but doesn't have any accounts return an empty
        list. I no person match id_type, my_id, throw a ...Exception.
        """
        ret = []
        # get_person_accounts returns a list of dicts on the form:
        # [{'uname': '...', 'priority': '...', 'status': '...'}, ...]
        for acc in Individuation.get_person_accounts(id_type, ext_id):
            a = Account()
            for k, v in acc.items():
                setattr(a, k, v)
            ret.append(a)
            
        return ret


    @rpc(String, String, String, String, String, _returns=Boolean)
    def generate_token(self, id_type, ext_id, username, phone_no, browser_token):
        """
        Send a token by SMS to the persons phone and store the token
        in Cerebrum.

        Return True if the person can be identified and phone_no is
        correct according to Cerebrum. Else return False
        """
        return Individuation.generate_token(id_type, ext_id, username,
                                            phone_no, browser_token)


    @rpc(String, String, String, _returns=Boolean)
    def check_token(self, username, token, browser_token):
        """
        Check the validity of a given token.
        """
        return Individuation.check_token(username, token, browser_token)


    @rpc(String, _returns=Boolean)
    def abort_token(self, username):
        """
        Remove token in from Cerebrum
        """
        return Individuation.delete_token(username)


    @rpc(String, String, String, String, _returns=Boolean)
    def set_password(self, username, new_password, token, browser_token):
        """
        Set new password for a user if all information is verified and
        the token is still valid.
        """
        return Individuation.set_password(username, new_password, token, browser_token)


    @rpc(String, _returns=Boolean)
    def validate_password(self, password):
        """
        Check if a given password is good enough.
        """
        return Individuation.validate_password(password)



def usage(exitcode=0):
    print """Usage: %s [-p <port number] [-l logfile] [--unencrypted]
  -p | --port num: run on alternative port (default: ?)
  -l | --logfile: where to log
  --unencrypted: don't use https
  """
    sys.exit(exitcode)

if __name__=='__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'p:l:',
                                   ['port=', 'unencrypted', 'logfile='])
    except getopt.GetoptError:
        usage(1)

    use_encryption = CRYPTO_AVAILABLE
    port = cereconf.INDIVIDUATION_SERVICE_PORT
    logfile = cereconf.INDIVIDUATION_SERVICE_LOGFILE

    for opt, val in opts:
        if opt in ('-l', '--logfile'):
            logfile = val
        elif opt in ('-p', '--port'):
            port = int(val)
        elif opt in ('--unencrypted',):
            use_encryption = False

    # Init twisted logger
    log.startLogging(file(logfile, 'w'))
    # soaplib init
    service = Application([IndividuationServer], 'tns')
    wsgi_application = wsgi.Application(service)
    # Run twisted service
    resource = WSGIResource(reactor, reactor.getThreadPool(), wsgi_application)
    root = Resource()
    root.putChild('SOAP', resource)
    # TODO: Print url of service
    if use_encryption:
        # TODO: we need to set up SSL properly
        sslcontext = ssl.DefaultOpenSSLContextFactory(
            cereconf.SSL_PRIVATE_KEY_FILE,
            cereconf.SSL_CERTIFICATE_FILE)
        reactor.listenSSL(int(port), Site(root), contextFactory=sslcontext)
    else:
        reactor.listenTCP(int(port), Site(root))
    reactor.run()

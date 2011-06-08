#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2010, 2011 University of Oslo, Norway
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

import socket

import soaplib.core
from soaplib.core.server import wsgi
from soaplib.core.service import DefinitionBase

from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.internet import reactor
from twisted.python import log

try:
    from twisted.internet import ssl
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

# TODO: how to import this correctly?
from OpenSSL import SSL

import traceback

"""
The core functionality for SOAP services running in the CIS framework. CIS is
based on the twisted framework and soaplib.

...
"""

class BasicSoapServer(DefinitionBase):
    """
    Base class for SOAP services.

    This class defines general setup useful for SOAP services.
    No SOAP actions are defined here. Define the actions in subclasses.
    """

    # Hooks, nice for logging etc.

    def on_method_call(self, method_name, py_params, soap_params):
        '''Called BEFORE the service implementing the functionality is called

        @param the method name
        @param the tuple of python params being passed to the method
        @param the soap elements for each argument
        '''
        log.msg("Calling method %s(%s)" % (method_name, 
                                         ', '.join(repr(p) for p in py_params)))

    def on_method_return_object(self, py_results):
        '''Called AFTER the service implementing the functionality is called,
        with native return object as argument
        
        @param the python results from the method
        '''
        pass

    def on_method_return_xml(self, soap_results):
        '''Called AFTER the service implementing the functionality is called,
        with native return object serialized to Element objects as argument.
        
        @param the xml element containing the return value(s) from the method
        '''
        pass

    def on_method_exception_object(self, exc):
        '''Called BEFORE the exception is serialized, when an error occurs
        during execution.
    
        @param the exception object
        '''
        log.msg("Exception occured: '%s'" % exc.faultstring)
        if not exc.faultstring.startswith('CerebrumRPCException: '):
            traceback.print_exc()
            # TBD: exchange error messages with default message, to avoid
            # letting people read data they shouldn't read?

    def on_method_exception_xml(self, fault_xml):
        '''Called AFTER the exception is serialized, when an error occurs
        during execution.
        
        @param the xml element containing the exception object serialized to a
        soap fault
        '''
        pass

    def call_wrapper(self, call, params):
        '''Called in place of the original method call.

        @param the original method call
        @param the arguments to the call
        '''
        return call(*params)

def clientVerificationCallback(connection, x509, errnum, errdepth, ok=None, test=None):
    """Callback for verifying a client's certificate."""
    if not ok:
        log.err('Invalid cert from subject: %s, errnum=%s, errdepth=%s' % (
                                    x509.get_subject(), errnum, errdepth))
        return False
    return True


class BasicSoapStarter:
    """
    Basic utility class for starting a soap server with the preferred
    settings.
    """
    def __init__(self):
        pass

    def run(self):
        """Starts the soap server"""
        pass

class TwistedSoapStarter(BasicSoapStarter):
    """
    Basic utility class for starting a soap server through Twisted. Could be
    subclassed or manipulated directly to change standard behaviour. Normally,
    you would only run::

      server = BasicTwistedSoapStarter(applications, port, ...)
      server.run()

    which would start Twisted's reactor for the given port.
    """

    # The namespace for soap's xml data
    namespace = 'tns'

    # The subdirectory in the server where soap is located, e.g.
    # https://example.com/SOAP
    soapchildpath = 'SOAP'

    # The interface the server should be connected to
    interface = ''

    # Callback for verifying client's certificates
    clientverifycallback = clientVerificationCallback

    def __init__(self, applications, port, private_key_file=None,
                 certificate_file=None, client_cert_files=None, encrypt=True):
        """Setting up a standard soap server. If either a key or certificate
        file is given, it will use encryption."""
        #super(TwistedSoapStarter, self).__init__()
        self.setup_soaplib(applications)
        self.setup_twisted()

        if encrypt and not (private_key_file and certificate_file):
            log.err("Encryption without certificate is not good")

        if encrypt:
            self.setup_encrypted_reactor(port, private_key_file,
                                         certificate_file, client_cert_files)
            url = "https://%s:%d/SOAP/" % (socket.gethostname(), port)
        else: # unencrypted
            self.setup_reactor(port=port)
            url = "http://%s:%d/SOAP/" % (socket.gethostname(),
                                          self.port.getHost().port)
        log.msg("Server set up at %s" % url)
        log.msg("WSDL definition at %s?wsdl" % url)

    def setup_soaplib(self, applications):
        """Setting up the soaplib framework."""
        if type(applications) not in (list, tuple, dict):
            applications = [applications]
        self.service = soaplib.core.Application(applications, self.namespace)
        self.wsgi_application = wsgi.Application(self.service)

    def setup_twisted(self):
        """Setting up the twisted service. Soaplib has to be setup first."""
        self.resource = WSGIResourceSession(reactor, reactor.getThreadPool(),
                                            self.wsgi_application)
        self.root = Resource()
        self.root.putChild(self.soapchildpath, self.resource)
        self.site = Site(self.root)

    def setup_encrypted_reactor(self, port, private_key_file,
                                certificate_file, client_cert_files=None):
        """Setting up the reactor with encryption."""
        sslcontext = ssl.DefaultOpenSSLContextFactory(private_key_file,
                                                      certificate_file)
        if client_cert_files:
            ctx = sslcontext.getContext()
            ctx.set_verify(SSL.VERIFY_PEER | SSL.VERIFY_FAIL_IF_NO_PEER_CERT,
                           self.clientverifycallback)
            # Tell the server what certificates it should trust:
            # TODO: check how more than one certificate could be added
            ctx.load_verify_locations(client_cert_files)
        self.port = reactor.listenSSL(int(port), self.site,
                                      contextFactory=sslcontext,
                                      interface=self.interface)

    def setup_reactor(self, port):
        """Setting up the reactor, without encryption."""
        self.port = reactor.listenTCP(int(port), self.site,
                                      interface=self.interface)

    def run(self):
        """Starts the soap server"""
        reactor.run()


### Hacks at Soaplib/Twisted
### Below is collections of different hacks of the soaplib and twisted to fix
### certain behaviour as we want. It should be put here to be able to locate any
### changes when upgrading to newer versions of the packages.

#
# Hack of WSGI/soaplib to support sessions.
#
# Since the WSGI doesn't define any specific support for sessions and cookies we
# need to hack it into soaplib's wsgi support. It is a bad hack, as it might
# crash the server by later soaplib upgrades. This is why it is all put last in
# this file, so it can be easier to locate and change it when problems occur.
#
# To use the hack, you would need to use these subclasses in the server setup.
# Example code:
#
#    import SoapListener
#
#    service = Application([IndividuationServer], 'tns')
#    # instead of wsgi.Application(service):
#    wsgi_app = SoapListener.WSGIApplication(service) 
#
#    # instead of WSGIResource(reactor, ..., wsgi_app):
#    resource = SoapListener.WSGIResourceSession(reactor,
#                               reactor.getThreadPool(), wsgi_application)
#
# If you do not put in these lines in your server setup, the soap server will be
# unaffected by this hack, but you wouldn't have session-support.
#
from twisted.web.server import NOT_DONE_YET
from twisted.web.wsgi import WSGIResource, _WSGIResponse

class WSGIResourceSession(WSGIResource):
    def render(self, request):
        """Creates the session, leaving the rest up to WSGIResource."""
        if request.method == 'POST':
            # Creates the session if it doesn't exist. When created, twisted
            # automatically creates a cookie for it.
            ISessionCache(request.getSession())
            log.msg("DEBUG: session id = %s" % request.getSession().uid)
        return super(WSGIResourceSession, self).render(request)

# To make use of the session, we need to give it functionality, either by
# adaption or subclassing, depending on what we need.

# To use the session as a simple (cached) dict, you could do:
# 
#   cache = ISessionCache(request.getSession())
#   
from zope.interface import Interface, implements, Attribute
from twisted.python import components
from twisted.web.server import Session

class ISessionCache(Interface):
    """Simple class for storing data onto a session object."""
    data = Attribute("For testing")

class SessionCache(dict):
    """A simple class for using the session as a normal dict."""
    implements(ISessionCache)
    def __init__(self, instance=None):
        dict.__init__(self)
components.registerAdapter(SessionCache, Session, ISessionCache)

# Session could also be subclassed, e.g. for setting the timeout, like:
#
#   class BasicSession(Session):
#       sessionTimeout = 60 # in seconds
#   site = Site(rootResource)
#   site.sessionFactory = BasicSession


#
# Unicode/exception problem fix in twisted. We need to change safe_str's default
# behaviour to also be able to encode unicode objects to strings, since we could
# raise unicode exceptions.
#
from twisted.python import reflect
def safer_str(o):
    """Safer than safe_str, as it doesn't seem to handle unicode objects."""
    if isinstance(o, unicode):
        try:
            return o.encode('utf-8')
        except Exception, e:
            log.err("Unicode: %s" % e)
    return reflect._safeFormat(str, o)
reflect.safe_str = safer_str

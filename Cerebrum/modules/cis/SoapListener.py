#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2010, 2011, 2012 University of Oslo, Norway
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
"""The core functionality for SOAP services running in the CIS framework. CIS
is based on the twisted framework and rpclib (now called spyne).

This file contains the main parts that are needed for a basic setup of a new
CIS service. The new service itself has to be created in its own file, and be
given to a TwistedSoapStarter class. Other settings are available, e.g. to
apply SSL encryption, authentication and authorization.

The structure is:

- The L{Server} is run, and sets up the webservice. It is normally located in
  servers/cis/.

- The L{Server} imports the proper L{Service} class and instantiates it. This
  contains the main functionality for the service, and could be defined in
  Cerebrum/modules/cis/ or be in a local instance' code directory.

- The L{Server} defines (or imports) a L{Service Framework} for what commands
  that are available, and how to communicate with the L{Service}. The L{Service
  Framework} is normally a subclass of L{BasicSoapStarter} from this file.

"""

from __future__ import unicode_literals

import socket
import traceback
import time
import re

from os import path
from lxml import etree

import rpclib
import rpclib.application
import rpclib.service
# TODO: should probably import most of these by its parent module:
from rpclib.server.wsgi import WsgiApplication
from rpclib.protocol.soap import Soap11
from rpclib.interface.wsdl import Wsdl11
from rpclib.model.complex import ComplexModel
from rpclib.model.primitive import Unicode

from twisted.web.server import Site, Session
from twisted.web.resource import Resource
from twisted.internet import reactor
from twisted.python import log, logfile, util
from twisted.web.wsgi import WSGIResource
from OpenSSL import SSL

from Cerebrum import Errors
from Cerebrum.modules.bofhd.errors import PermissionDenied
from Cerebrum.modules.cis.faults import (EndUserFault, NotAuthorizedError,
                                         CerebrumFault, UnknownFault)

CRYPTO_AVAILABLE = True
try:
    from twisted.internet import ssl
except ImportError:
    CRYPTO_AVAILABLE = False


class BasicSoapServer(rpclib.service.ServiceBase):
    """
    Base class for our SOAP services, with general setup useful for us.
    Public methods should be defined in subclasses.

    """
    @classmethod
    def call_wrapper(cls, ctx):
        """
        The wrapper for calling a public service method.

        Service classes can raise CerebrumRPCException, which should be
        returned to the client and considered to be shown to the end users.
        Any other exceptions should not be returned to the client, but gets
        logged and a generic 'unknown error' Fault is returned.

        TBD: We still haven't solved how subclasses could make use of their
        own exceptions. It might be necessary, it is probably not need for
        that many different exception types.

        """
        try:
            return super(BasicSoapServer, cls).call_wrapper(ctx)
        except Errors.CerebrumRPCException, e:
            raise EndUserFault(e)
        except PermissionDenied, e:
            raise NotAuthorizedError(e)
        # TODO: also except generic Faults?
        except CerebrumFault:
            raise
        except Exception, e:
            # TODO: How to make unknown exceptions available for subclasses?
            log.msg('ERROR: Unhandled exception: %s' % type(e))
            log.err(e)
            log.msg(traceback.format_exc())
            raise UnknownFault()


def _event_setup_basic(ctx):
    """Event that is executed at every call, which logs the transaction and
    initiates the User Defined Context.

    """
    log.msg("DEBUG: BasicSoapServer - Calling method %s" % ctx.in_object)

    # The UserDefinedContext is The Place to put stuff. Setting it to a dict
    # here, to be able to add different stuff in different Service classes:
    if ctx.udc is None:
        # TBD: Should we have this as an object instead?
        ctx.udc = dict()


BasicSoapServer.event_manager.add_listener('method_call', _event_setup_basic)


def _event_unknown_exceptions(ctx):
    """Event called at the end of a transaction, checking for any unknown
    exception that should not be returned to the client. This should not
    happen, but any bug e.g. inside an event could trigger an exception.

    Note that any event added after this one will not have this protection. If
    rpclib had some support for setting the priorities for events, this could
    be set to the last one, and we could use method_exception_object instead,
    which is a bit more effective as we don't have to parse and generate XML.

    """
    if not isinstance(ctx.out_error, CerebrumFault):
        log.msg('WARNING: Unknown error returned: %s' % ctx.out_error)
        if hasattr(ctx.out_error, 'traceback'):
            log.msg(ctx.out_error.traceback)
        else:
            log.err(ctx.out_error)
            log.msg(traceback.format_exc())

        # Return a generic 'unknown error' to the client. This requires us to
        # both parse the output string to XML, modify the faultstring and
        # regenerate the XML string again. Not quite effective, but it will
        # hopefully not happen that often.
        root = etree.XML(ctx.out_string[0])
        for faultstring in root.iter('faultstring'):
            faultstring.text = 'Unknown Error'
        ctx.out_string[0] = etree.tostring(root)


BasicSoapServer.event_manager.add_listener('method_exception_string',
                                           _event_unknown_exceptions)


#
# Events that could be used by CIS servers
#
# See rpclib.service.ServiceBase.__doc__ for the event handlers
#

def on_method_call_session(ctx):
    """Event for session handling. Add this to services to use sessions. Note
    that they also have to add SessionHeader in their __in_header__, to let
    clients give them the session id.

    """
    site = ctx.service_class.site
    # TODO: what if in_header is empty/None?
    # if ctx.in_header is None or not ctx.in_header.session_id:
    #    raise Exception("No session ID given in header")
    sid = getattr(ctx.in_header, 'session_id', None)

    if not sid:
        session = site.makeSession()
    else:
        try:
            session = site.getSession(sid)
        except KeyError:
            # Either wrong given ID, or the old session has expired
            session = site.makeSession()
    session.touch()
    log.msg("DEBUG: session ID: %s (given: %s)" % (session.uid, sid))
    ctx.udc['session'] = session


def on_method_exit_session(ctx):
    """Event for session handling at exit. By calling this event, the current
    session ID is returned to the client through the reponse SOAP header."""
    sid = ctx.udc['session'].uid
    if not sid:
        return
    sh = SessionHeader()
    sh.session_id = sid

    if ctx.out_header is None:
        ctx.out_header = sh
    elif isinstance(ctx.out_header, list):
        ctx.out_header.append(sh)
    elif isinstance(ctx.out_header, tuple):
        ctx.out_header += (sh,)
    else:
        ctx.out_header = [ctx.out_header, sh]

#
# Session support
#


class SessionHeader(ComplexModel):
    """A header for support of sessions. Can be used both by clients and
    servers. One could subclass this if more data is needed in client's
    header."""
    __namespace__ = 'tns'  # TODO: what is correct tns?
    # __namespace__ = 'SoapListener.session' # TODO: what is correct tns?
    session_id = Unicode


class SessionCacher(Session, dict):
    """The session class does nothing by itself, except for timing out. This is
    a simple class for using the session as a dict. It could be subclassed for
    more functionality.

    To make use of this as your session, you have to set site.sessionFactory to
    this class."""
    # Not sure if zope.interface.components should be used instead, but this
    # was easier.
    sessionTimeout = 60  # in seconds

    # TODO: create a __copy__ method to be able to copy data from an old
    # session to a new one. This is needed for switching session ID when
    # authenticating.


class BasicSoapStarter(object):
    """Basic utility class for starting a soap server with the preferred
    settings.
    """
    def __init__(self):
        pass

    def run(self):
        """Starts the soap server"""
        pass


class TwistedSoapStarter(BasicSoapStarter):
    """Basic utility class for starting a soap server through Twisted. Could be
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
    interface = '0.0.0.0'

    def __init__(self, applications, port, logfile=None, log_prefix=None,
                 log_formatters=None):
        """Setting up a standard SOAP server.
        """
        if logfile:
            self.setup_logging(logfile, log_prefix=log_prefix,
                               log_formatters=log_formatters)
        super(TwistedSoapStarter, self).__init__()
        self.setup_services(applications)
        self.setup_twisted()

        self.setup_reactor(port=port)

    def setup_services(self, applications):
        """Setting up the service that should be run by twisted. This is here
        an rpclib service in the standard WSGI format."""
        if type(applications) not in (list, tuple, dict):
            applications = [applications]

        self.service = rpclib.application.Application(
            applications,
            tns=self.namespace,
            interface=Wsdl11(),
            in_protocol=Soap11(validator='lxml'),
            out_protocol=Soap11())
        self.wsgi_application = WsgiApplication(self.service)

    def setup_twisted(self):
        """Setting up the twisted service. Soaplib has to be setup first."""
        self.resource = WSGIResource(reactor, reactor.getThreadPool(),
                                     self.wsgi_application)
        self.root = Resource()
        self.root.putChild(self.soapchildpath, self.resource)
        self.site = Site(self.root)

    @staticmethod
    def setup_logging(logfilename, rotatelength=50 * 1024 * 1024,
                      maxrotatedfiles=10, log_prefix=None,
                      log_formatters=None):
        """Setting up twisted's log to be used by Cerebrum. This could either
        be run manually before (or after) initiating the
        TwistedSoapStarter."""
        if log_prefix:
            TwistedCerebrumLogger.log_prefix = log_prefix
        if log_formatters:
            TwistedCerebrumLogger.log_formatters = log_formatters
        logger = TwistedCerebrumLogger(logfile.LogFile.fromFullPath(
            logfilename,
            rotateLength=rotatelength,
            maxRotatedFiles=maxrotatedfiles,
            # defaultMode=None # the file mode at creation
        ))
        log.startLoggingWithObserver(logger.emit)

        # Make python's standard logging to also use twisted's logger:
        # TODO: this should be tested for deadlocks before being put in
        # production:
        # logging.basicConfig(level=logging.ERROR, stream=sys.stdout)

    def setup_reactor(self, port):
        """Setting up the reactor, without encryption."""
        self.port = reactor.listenTCP(int(port), self.site,
                                      interface=self.interface)
        url = "http://%s:%d/%s/" % (socket.gethostname(),
                                    self.port.getHost().port,
                                    self.soapchildpath)
        log.msg("DEBUG: Server set up at %s" % url)
        log.msg("DEBUG: WSDL definition at %s?wsdl" % url)

    def run(self):
        """Starts the soap server"""
        reactor.run()


class TLSTwistedSoapStarter(TwistedSoapStarter):
    """Utility class for starting a SOAP server with TLS encryption. To fire it
    up, you could run::

      server = TLSTwistedSoapStarter(applications, port, ...)
      server.run()

    """

    # The certificate whitelist - only the certificates that matches these
    # fingerprints are accepted in a TLS connection.
    client_fingerprints = None

    def __init__(self, private_key_file=None, certificate_file=None,
                 client_ca=None, client_fingerprints=None, **kwargs):
        """Constructor. Takes the arguments necessary to setup the encrypted
        server, the rest of the arguments are sent up to
        L{TwistedSoapStarter}'s __init__ method.

        """
        # The log will be set up by the super class, but we need it already
        # now, so we set it up twice, now just to get any warnings.
        # TODO: it would probably be better to be able to run setup_sslcontext
        # after super.__init__().
        if 'logfile' in kwargs:
            self.setup_logging(kwargs['logfile'],
                               log_prefix=kwargs.get('log_prefix', None),
                               log_formatters=kwargs.get('log_formatters',
                                                         None))

        if not CRYPTO_AVAILABLE:
            raise Exception('Could not import cryptostuff')
        if not (private_key_file and certificate_file):
            # TODO: raise exception instead?
            log.msg("ERROR: Encryption without certificate is not good")
        self.setup_sslcontext(client_ca=client_ca,
                              client_fingerprints=client_fingerprints,
                              private_key_file=private_key_file,
                              certificate_file=certificate_file)
        super(TLSTwistedSoapStarter, self).__init__(**kwargs)

    def setup_sslcontext(self, client_ca, client_fingerprints,
                         private_key_file, certificate_file):
        """Setup the ssl context and its settings."""
        self.sslcontext = ssl.DefaultOpenSSLContextFactory(private_key_file,
                                                           certificate_file)
        if client_fingerprints:
            self.client_fingerprints = client_fingerprints
        if client_ca:
            if not client_fingerprints:
                log.msg('WARNING: No whitelist, accepting signed by CA')
            self.add_certificates(client_ca)
            self.sslcontext.getContext().set_verify(
                SSL.VERIFY_PEER | SSL.VERIFY_FAIL_IF_NO_PEER_CERT,
                self.clientTLSVerify)
        else:
            log.msg('INFO: No CA given, accepting all clients')
        # TODO: could self.sslcontext.getContext().set_verify_depth(<int>) be
        # used to avoid having to validate the whole chain?

    def add_certificates(self, locations):
        """Tell the server what certificates it should trust as signers of the
        clients' certificates."""
        if isinstance(locations, (list, tuple)):
            for location in locations:
                self.add_certificates(location)
            return
        if path.isdir(locations):
            log.msg('WARNING: Adding CA directories might be buggy...')
            self.sslcontext.getContext().load_verify_locations(None, locations)
        else:
            self.sslcontext.getContext().load_verify_locations(locations)

    def setup_reactor(self, port):
        """Setting up the reactor with encryption."""
        self.port = reactor.listenSSL(int(port), self.site,
                                      contextFactory=self.sslcontext,
                                      interface=self.interface)
        url = "https://%s:%d/SOAP/" % (socket.gethostname(),
                                       self.port.getHost().port)
        log.msg("DEBUG: Server set up at %s" % url)
        log.msg("DEBUG: WSDL definition at %s?wsdl" % url)

    @classmethod
    def clientTLSVerify(cls, connection, x509, errnum, errdepth, ok=None):
        """Callback for verifying a client's certificate. This is called every
        time listenSSL gets an incoming connection, and is used for more
        validations, logging and debug.

        Note that load_verify_locations is called at startup, which tells the
        server what specific certificates we trust blindly. Connection by these
        certificates will therefore set ok to True.

        @param connection
        @type  OpenSSL.SSL.Connection

               The TLS connection. Note that the connection gets automatically
               dropped if this function return False.

        @param x509
        @type  X509.X509

               Contains the current X.509 certificate to be verified.

        @param errnum
        @type  int

               The TLS error number if the certificate was not okay. See `man
               verify` for a list of error codes.

        @param errdepth
        @type  int

               TODO: Where we are in the X.509 certificate chain.

        @param ok
        @type  int or None

               If X.509 verified the certificate to be okay or not.

        @return bool
        True if the client should be allowed a connection, False closes the
        connection.

        """
        if not ok:
            log.msg('WARNING: Invalid cert: errnum=%s, errdepth=%s '
                    '(see `man verify` for info)' % (errnum, errdepth))
            try:
                log.msg('  subject: %s' % x509.get_subject())
                log.msg('  issuer:  %s' % x509.get_issuer())
                log.msg('  serial:  %x' % x509.get_serial_number())
                log.msg('  start:   %s' % x509.get_notBefore())
                log.msg('  expires: %s' % x509.get_notAfter())
                log.msg('  version: %s' % x509.get_version())
                log.msg('  digest: %s (sha256)' % x509.digest('sha256'))
                log.msg('  digest: %s (sha1)' % x509.digest('sha1'))
                log.msg('  digest: %s (md5)' % x509.digest('md5'))
            except Exception, e:
                log.msg('  exception: %s' % e)
                log.err(e)
            return False
        # check the whitelist
        if cls.client_fingerprints:
            if x509.digest('sha1') not in cls.client_fingerprints:
                log.msg('WARNING: Valid cert, but not in whitelist')
                log.msg('  subject: %s' % x509.get_subject())
                log.msg('  issuer:  %s' % x509.get_issuer())
                log.msg('  serial:  %x' % x509.get_serial_number())
                log.msg('  version: %s' % x509.get_version())
                log.msg('  digest: %s (sha256)' % x509.digest('sha256'))
                log.msg('  digest: %s (sha1)' % x509.digest('sha1'))
                log.msg('  digest: %s (md5)' % x509.digest('md5'))
                return False
        # TODO: validate the hostname as well?

        # Log if a certificate is close to expiration. A weeks delay.
        expire = x509.get_notAfter()  # format: 'YYYYMMDDhhmmssZ'
        if expire and int(expire[:8]) < int(time.strftime('%Y%m%d')) - 30:
            log.msg('WARNING: Cert close to expire')
            log.msg('  subject: %s' % x509.get_subject())
            log.msg('  issuer:  %s' % x509.get_issuer())
            log.msg('  start:   %s' % x509.get_notBefore())
            log.msg('  expires: %s' % x509.get_notAfter())
        return True


# Hacks at Soaplib/Twisted
# Below is collections of different hacks of the soaplib and twisted to fix
# certain behaviour as we want. It should be put here to be able to locate any
# changes when upgrading to newer versions of the packages.

# Modifying the logger to work with Cerebrum
# Note that Twisted Core 11.1.0 and later supports log prefixes:
#   - Protocols may now implement ILoggingContext to customize their
#     logging prefix.  twisted.protocols.policies.ProtocolWrapper and the
#     endpoints wrapper now take advantage of this feature to ensure the
#     application protocol is still reflected in logs. (#5062)
# which means that this can be removed when upgrading to later twisted
# versions.
class TwistedCerebrumLogger(log.FileLogObserver):
    """Modifying twisted's logger to a more Cerebrum-like format. Used by
    default in TwistedSoapStarter.setup_logging."""

    # Cerebrum's logs make use of a prefix to separate the running scripts.
    # Set this to the current script's name.
    log_prefix = 'cis:'

    # tuple of (pattern, replacement) pairs when defined.
    log_formatters = None

    # The time format known by Cerebrum
    timeFormat = '%Y-%m-%d %H:%M:%S'

    def emit(self, eventDict):
        """Changing the default log format.

        Base method that writes cis log. Here we can access the log
        message and manipulate it as we need. For example, define
        the log format and filter out password from the message.
        This can be configured per service in cisconf with LOG_FORMATTERS
        tuple of pairs (pattern, replacement).

        TODO: This is a hack, twisted should have a better way of modifying
        its log format"""
        text = log.textFromEventDict(eventDict)
        if text is None:
            return

        if isinstance(self.log_formatters, (list, tuple)):
            for pattern, replacement in self.log_formatters:
                text = re.sub(pattern, replacement, text)

        timeStr = self.formatTime(eventDict['time'])
        fmtDict = {'system': eventDict['system'],
                   'text': text.replace("\n", "\n\t")}
        msgStr = log._safeFormat("[%(system)s] %(text)s\n", fmtDict)

        util.untilConcludes(self.write, ('%s %s %s' %
                                         (timeStr, self.log_prefix, msgStr)))
        util.untilConcludes(self.flush)  # Hoorj!

#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011, 2012 University of Oslo, Norway
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

"""A SOAP server for giving Postmaster's what they want of information from
Cerebrum.

Note that the logger is twisted's own logger and not Cerebrum's. Since twisted
works in parallell the logger should not be blocked. Due to this, the format of
the logs is not equal to the rest of Cerebrum. This might be something to work
on later.

"""

import sys
import getopt

from twisted.python import log

from rpclib.model.primitive import Unicode
from rpclib.model.complex import Array
# Note the difference between rpc and the static srpc - the former sets the
# first parameter as the current MethodContext. Very nice if you want
# environment details.
from rpclib.decorator import rpc

import cerebrum_path
from cisconf import postmaster as cisconf
from Cerebrum.Utils import dyn_import
from Cerebrum import Errors
from Cerebrum.modules.cis import SoapListener


del cerebrum_path


class PostmasterServer(SoapListener.BasicSoapServer):
    """The SOAP commands available for the clients.

    TODO: is the following correct anymore? Note that an instance of this class
    is created for each incoming call.

    """
    # Headers: no need for headers for e.g. session IDs in this web service.

    # The class where the Cerebrum-specific functionality is done. This is
    # instantiated per call, to avoid thread conflicts.
    cere_class = None

    # The hock for the site object
    site = None

    @rpc(Array(Unicode), Array(Unicode), Array(Unicode),
         _returns=Array(Unicode))
    def get_addresses_by_affiliation(ctx, status=None, skos=None, source=None):
        """Get primary e-mail addresses for persons that match given
        criteria."""
        if not source and not status:
            raise Errors.CerebrumRPCException('Input needed')
        return ctx.udc['postmaster'].get_addresses_by_affiliation(status=status,
                                                                  skos=skos,
                                                                  source=source)

# Events for the project:


def event_method_call(ctx):
    """Event for incoming calls."""
    ctx.udc['postmaster'] = ctx.service_class.cere_class()
PostmasterServer.event_manager.add_listener('method_call', event_method_call)


def event_exit(ctx):
    """Event for cleaning after a call, i.e. close up db connections. Since
    twisted runs all calls in a pool of threads, we can not trust __del__.

    """
    # TODO: is this necessary any more, as we now are storing it in the method
    # context? Are these deleted after each call? Check it out!
    if 'postmaster' in ctx.udc:
        ctx.udc['postmaster'].close()
PostmasterServer.event_manager.add_listener('method_return_object', event_exit)
PostmasterServer.event_manager.add_listener('method_exception_object',
                                            event_exit)


def usage(exitcode=0):
    print """Usage: %s --port PORT --instance INSTANCE --logfile FILE

Fire up the Postmaster's webservice.

  --port        What port to run the server. Default: cisconf.PORT.

  --interface   What interface the server should listen to (default: 0.0.0.0)
                Default: cisconf.INTERFACE.

  --logfile     Where to log. Default: cisconf.LOG_FILE.

  --fingerprints A comma separated list of certificate fingerprints. If this
                is set, client certificates that doesn't generate fingerprints
                which are in this list gets blocked from the service.
                Default: cisconf.FINGERPRINTS.

  --instance    The Cerebrum instance which should be used. E.g:
                    Cerebrum.modules.no.uio.PostmasterCommands/Commands
                Default: cisconf.CEREBRUM_CLASS.

  --unencrypted Don't use https

  --help        Show this and quit
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h',
                                   ['port=', 'unencrypted', 'logfile=',
                                    'help', 'fingerprints=', 'instance=',
                                    'interface='])
    except getopt.GetoptError, e:
        print e
        usage(1)

    use_encryption = True
    port = getattr(cisconf, 'PORT', 0)
    logfilename = getattr(cisconf, 'LOG_FILE', None)
    instance = getattr(cisconf, 'CEREBRUM_CLASS', None)
    interface = getattr(cisconf, 'INTERFACE', None)
    log_prefix = getattr(cisconf, 'LOG_PREFIX', None)
    log_formatters = getattr(cisconf, 'LOG_FORMATTERS', None)

    for opt, val in opts:
        if opt in ('--logfile',):
            logfilename = val
        elif opt in ('--port',):
            port = int(val)
        elif opt in ('--unencrypted',):
            use_encryption = False
        elif opt in ('--instance',):
            instance = val
        elif opt in ('--interface',):
            interface = val
        elif opt in ('-h', '--help'):
            usage()
        else:
            print "Unknown argument: %s" % opt
            usage(1)

    if not port or not logfilename or not instance:
        print "Missing arguments or cisconf variables"
        usage(1)

    # Get the cerebrum class and give it to the server
    module, classname = instance.split('/', 1)
    mod = dyn_import(module)
    cls = getattr(mod, classname)
    PostmasterServer.cere_class = cls
    log.msg("DEBUG: Cerebrum class used: %s" % instance)

    private_key_file = None
    certificate_file = None
    client_ca = None
    fingerprints = None

    if interface:
        SoapListener.TwistedSoapStarter.interface = interface

    if use_encryption:
        private_key_file = cisconf.SERVER_PRIVATE_KEY_FILE
        certificate_file = cisconf.SERVER_CERTIFICATE_FILE
        client_ca = cisconf.CERTIFICATE_AUTHORITIES
        fingerprints = getattr(cisconf, 'FINGERPRINTS', None)

        server = SoapListener.TLSTwistedSoapStarter(
            port=int(port),
            applications=PostmasterServer,
            private_key_file=private_key_file,
            certificate_file=certificate_file,
            client_ca=client_ca,
            client_fingerprints=fingerprints,
            logfile=logfilename,
            log_prefix=log_prefix,
            log_formatters=log_formatters)
    else:
        server = SoapListener.TwistedSoapStarter(
            port=int(port),
            applications=PostmasterServer,
            logfile=logfilename,
            log_prefix=log_prefix,
            log_formatters=log_formatters)
    PostmasterServer.site = server.site  # to make it global and reachable

    # If sessions' behaviour should be changed (e.g. timeout):
    # server.site.sessionFactory = BasicSession

    # Fire up the server:
    server.run()

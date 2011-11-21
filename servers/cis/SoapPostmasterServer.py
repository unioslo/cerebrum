#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 
# Copyright 2011 University of Oslo, Norway
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

The code is not separated from the server, which is not the recommended way of
creating servers.

Note that the logger is twisted's own logger and not Cerebrum's. Since twisted
works in parallell the logger should not be blocked. Due to this, the format
of the logs is not equal to the rest of Cerebrum. This might be something to
work on later.
"""

import sys, traceback
import getopt

import cerebrum_path, cereconf
from Cerebrum.modules.cis import SoapListener
from Cerebrum.Utils import Messages, dyn_import
from Cerebrum import Errors

from soaplib.core.service import rpc
from soaplib.core.model.primitive import String, Integer, Boolean
from soaplib.core.model.clazz import ClassModel, Array
from soaplib.core.model.exception import Fault

from twisted.python import log

class PostmasterServer(SoapListener.BasicSoapServer):
    """The SOAP commands available for the clients.

    Note that an instance of this class is created for each incoming call."""

    # The class where the Cerebrum-specific functionality is done. This is
    # instantiated per call, to avoid thread conflicts.
    cere_class = None

    # The hock for the site object
    site = None

    def call_wrapper(self, call, params):
        """Subclassing the call wrapper to instantiate the cerebrum instance
        and to handle exceptions in a soap-wise manner."""
        try:
            self.cere_obj = self.cere_class()
            return super(PostmasterServer, self).call_wrapper(call, params)
        except KeyboardInterrupt: # don't catch signals like ctrl+c
            raise
        except Errors.CerebrumRPCException, e:
            msg = self.cache['msgs'][e.args[0]] % e.args[1:]
            raise Fault(faultstring=e.__doc__ + ': ' + msg)
        except Fault, e:
            raise e
        except Exception, e:
            # If anything breaks in here, it will not get logged. Beware!
            log.msg('ERROR: Unhandled exception: %s' % type(e))
            log.err(e)
            log.msg(traceback.format_exc())

            # Don't want the client to know too much about unhandled errors, so
            # return a generic error.
            raise Fault(faultstring='Unknown error')
        finally:
            if hasattr(self, 'cere_obj'):
                del self.cere_obj

    @rpc(Array(String), Array(String), _returns=Array(String))
    def get_addresses_by_affiliation(self, status=None, source=None):
        """Get primary e-mail addresses for persons that match given
        criterias."""
        if not source and not status:
            raise Fault(faultstring='CerebrumRPCException: Input needed')
        return self.cere_obj.get_addresses_by_affiliation(status=status,
                                                          source=source)

def usage(exitcode=0):
    print """Usage: %s --port PORT --instance INSTANCE --logfile FILE

Fire up the Postmaster's webservice.

  --port        What port to run the server.

  --interface   What interface the server should listen to (default: 0.0.0.0)

  --logfile     Where to log

  --instance    The Cerebrum instance which should be used. E.g:
                    Cerebrum.modules.no.uio.PostmasterCommands/Commands

  --unencrypted Don't use https

  --help        Show this and quit
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h',
                                   ['port=', 'unencrypted', 'logfile=',
                                    'help', 'instance=', 'interface='])
    except getopt.GetoptError, e:
        print e
        usage(1)

    use_encryption = True
    port = logfilename = interface = instance = None

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

    if not port or not logfilename or not instance:
        print "Missing arguments"
        usage(1)

    # Get the cerebrum class and give it to the server
    module, classname = instance.split('/', 1)
    mod = dyn_import(module)
    cls = getattr(mod, classname)
    PostmasterServer.cere_class = cls
    log.msg("Cerebrum class used: %s" % instance)

    private_key_file  = None
    certificate_file  = None
    client_ca         = None
    fingerprints      = None

    if use_encryption:
        private_key_file  = cereconf.SSL_PRIVATE_KEY_FILE
        certificate_file  = cereconf.SSL_CERTIFICATE_FILE
        client_ca         = cereconf.INDIVIDUATION_CLIENT_CA
        fingerprints      = getattr(cereconf, 'INDIVIDUATION_CLIENT_FINGERPRINTS', None)
    if interface:
        SoapListener.TwistedSoapStarter.interface = interface

    server = SoapListener.TwistedSoapStarter(port = int(port),
                applications = PostmasterServer,
                private_key_file = private_key_file,
                certificate_file = certificate_file,
                client_ca = client_ca,
                encrypt = use_encryption,
                client_fingerprints = fingerprints,
                logfile = logfilename)
    PostmasterServer.site = server.site # to make it global and reachable (wrong, I know)

    # If sessions' behaviour should be changed (e.g. timeout):
    # server.site.sessionFactory = BasicSession
    server.run()

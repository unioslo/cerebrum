#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013 University of Oslo, Norway
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
"""The server for Resource management for TSD.

Data about resources are registered in Cerebrum, but the resources itself are
managed by a resource system (auto-VM) that is not a part of Cerebrum. This is
the commands that the resource system should be calling to update Cerebrum with
what is happening.

"""

import sys, socket, traceback
import getopt

from twisted.python import log

from rpclib.model.complex import ComplexModel, Iterable
from rpclib.model.primitive import String, Integer, Boolean
# Note the difference between rpc and the static srpc - the former sets the
# first parameter as the current MethodContext. Very nice if you want
# environment details.
from rpclib.decorator import rpc, srpc

import cerebrum_path
from cisconf import resourceservice as cisconf
from Cerebrum.Utils import Messages, dyn_import
from Cerebrum import Errors
from Cerebrum.modules.cis import SoapListener, auth, faults

class ResourceService(SoapListener.BasicSoapServer):
    """Resource Server for managing resources in Cerebrum.

    This server gives a resource managing system commands for getting
    information about resource registered in Cerebrum, and some commands for
    updating the information about the resources in Cerebrum.

    """

    # Require the session ID in the client's header
    __in_header__ = SoapListener.SessionHeader

    # Respond with a header with the current session ID
    __out_header__ = SoapListener.SessionHeader

    # The class where the Cerebrum-specific functionality is done. This is
    # instantiated per call, to avoid thread conflicts.
    cere_class = None

    # The hock for the site object
    site = None

    @rpc(String, String, _returns = Iterable(Iterable(String)),
         _throws=faults.EndUserFault)
    def search_mac_addresses(ctx, hostname=None, mac_address=None):
        """Get a list of hostnames and their MAC addresses.

        If neither the hostname nor the mac_address is given, a complete list of
        all hostnames and their MAC-adresses is returned.

        @type hostname: String
        @param hostname: The name of the host that you would like to get the MAC
            address for.

        @type mac_address: String
        @param mac_address: The MAC address you would like to get the hostname
            for.

        @rtype: Iterable/List/Array
        @return: A list of hostname-to-mac-address connections, formed as
            two-element lists/arrays:

                ((host1, mac1), (host2, mac2), ...)

        """
        return ctx.udc['resources'].search_mac_addresses(hostname, mac_address)

    @rpc(String, String, _returns = Boolean, _throws=faults.EndUserFault)
    def register_mac_address(ctx, hostname, mac_address):
        """Register the MAC address for a given host in Cerebrum.

        This command should be called after the machine has been created and
        gotten a MAC address.

        @type hostname: String
        @param hostname: The name of the host that should be updated.

        @type mac_address: String
        @param mac_address: The MAC address to set for the given hosst. Could be
            set to None or an empty string to remove the MAC address from the
            host.

        @rtype: Boolean
        @return: True if the MAC address could be stored for the given account.

        """
        return ctx.udc['resources'].register_mac_address(hostname, mac_address)

    @rpc(String, _returns = Iterable(String), _throws=faults.EndUserFault)
    def get_vlan_info(ctx, hostname):
        """Get the VLAN information about a given host.

        @type hostname: String
        @param hostname: The name of the host to get the vlan info about.

        @rtype: Iterable/Array/List
        @return: A list with the elements:
            - VLAN number
            - net category

        """
        return ctx.udc['resources'].get_vlan_info(hostname)

# Events for the Service
def _event_setup_resources(ctx):
    """Event method for setting up the ResourceService.
    
    It is called at every client call. It makes use of the session, so it has to
    be run after the session setup.

    """
    operator_id = ctx.udc['session'].get('authenticated', None)
    if operator_id:
        operator_id = operator_id.id
    ctx.udc['resources'] = ctx.service_class.cere_class(operator_id)

def _event_cleanup(ctx):
    """Event for cleaning up the instances, i.e. close the database connections.
    Since twisted runs all calls in a pool of threads, we can not trust
    __del__.

    """
    if ctx.udc.has_key('resources'):
        ctx.udc['resources'].close()

# Add session support to the group service:
ResourceService.event_manager.add_listener('method_call',
                                           SoapListener.on_method_call_session)
ResourceService.event_manager.add_listener('method_return_object',
                                           SoapListener.on_method_exit_session)

# Add the group specific events:
ResourceService.event_manager.add_listener('method_call',
                                           _event_setup_resources)
ResourceService.event_manager.add_listener('method_return_object',
                                           _event_cleanup)
ResourceService.event_manager.add_listener('method_exception_object',
                                           _event_cleanup)

# Add authentication support to the group service:
ResourceService.event_manager.add_listener('method_call',
                                           auth.on_method_authentication)

def usage(exitcode=0):
    print """Usage: %s [-p <port number] [-l logfile] [--unencrypted]

Starts up the ResourceService webservice on a given port. Please note that config
(cisconf) contains more settings for the service.

  -p
  --port num        Run on alternative port than defined in cisconf.PORT.

  --interface ADDR  What interface the server should listen to. Overrides
                    cisconf.INTERFACE. Default: 0.0.0.0

  -l
  --logfile:        Where to log. Overrides cisconf.LOG_FILE.

  --instance        The individuation instance which should be used. Defaults
                    to what is defined in cisconf.CEREBRUM_CLASS, e.g:
                        Cerebrum.modules.cis.GroupInfo/GroupInfo

  --unencrypted     Don't use HTTPS. All communications goes unencrypted, and
                    should only be used for testing.

  -h
  --help            Show this and quit.
    """
    sys.exit(exitcode)

if __name__=='__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'p:l:h',
                                   ['port=', 'unencrypted', 'logfile=',
                                    'help', 'instance=', 'interface='])
    except getopt.GetoptError, e:
        print e
        usage(1)

    use_encryption = True
    port        = getattr(cisconf, 'PORT', 0)
    logfilename = getattr(cisconf, 'LOG_FILE', None)
    instance    = getattr(cisconf, 'CEREBRUM_CLASS', None)
    interface   = getattr(cisconf, 'INTERFACE', None)
    log_prefix  = getattr(cisconf, 'LOG_PREFIX', None)
    log_formatters = getattr(cisconf, 'LOG_FORMATTERS', None)

    for opt, val in opts:
        if opt in ('-l', '--logfile'):
            logfilename = val
        elif opt in ('-p', '--port'):
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

    # Get the service tier class and give it to the server
    module, classname = instance.split('/', 1)
    mod = dyn_import(module)
    cls = getattr(mod, classname)
    ResourceService.cere_class = cls
    # TBD: Should Cerebrum tier be started once per session instead? Takes
    # more memory, but are there benefits we need, e.g. language control?

    private_key_file  = None
    certificate_file  = None
    client_ca         = None
    fingerprints      = None

    services = [auth.PasswordAuthenticationService, ResourceService]
    if interface:
        SoapListener.TwistedSoapStarter.interface = interface

    if use_encryption:
        private_key_file  = cisconf.SERVER_PRIVATE_KEY_FILE
        certificate_file  = cisconf.SERVER_CERTIFICATE_FILE
        client_ca         = cisconf.CERTIFICATE_AUTHORITIES
        fingerprints      = getattr(cisconf, 'FINGERPRINTS', None)

        server = SoapListener.TLSTwistedSoapStarter(port = int(port),
                        applications = services,
                        private_key_file = private_key_file,
                        certificate_file = certificate_file,
                        client_ca = client_ca,
                        client_fingerprints = fingerprints,
                        logfile = logfilename,
                        log_prefix = log_prefix,
                        log_formatters=log_formatters)
    else:
        server = SoapListener.TwistedSoapStarter(port = int(port),
                                    applications = services,
                                    logfile = logfilename,
                                    log_prefix = log_prefix,
                                    log_formatters=log_formatters)
    ResourceService.site = server.site # to make it global and reachable by tier (wrong, I know)
    auth.PasswordAuthenticationService.site = server.site # to make it global and reachable (wrong, I know)

    # We want the sessions to be simple dicts, for now:
    server.site.sessionFactory = SoapListener.SessionCacher
    # Set the timeout to something appropriate:
    SoapListener.SessionCacher.sessionTimeout = 600 # = 10 minutes
    log.msg("DEBUG: Using server class: %s" % instance)
    server.run()

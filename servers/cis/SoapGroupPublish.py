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
""" This file provides a SOAP service for publishing group memberships.
"""
import sys
import getopt
from rpclib.model.complex import Iterable
from rpclib.model.primitive import String
from rpclib.decorator import rpc
from Cerebrum.Utils import dyn_import
from Cerebrum.modules.cis import SoapListener, faults

from cisconf import grouppub as cisconf

class GroupPublishService(SoapListener.BasicSoapServer):

    __namespace__ = 'gp'
    __tns__ = 'gp'

    # Require the session ID in the client's header
    __in_header__ = SoapListener.SessionHeader
    # Respond with a header with the current session ID
    __out_header__ = SoapListener.SessionHeader

    # The class where the Cerebrum-specific functionality is done. This is
    # instantiated per call, to avoid thread conflicts.
    cere_class = None

    # The hock for the site object
    site = None

    @rpc(String, _returns=Iterable(String), _throws=faults.EndUserFault)
    def list_group_members(ctx, group):
        """ This rpc lists names of members of a given group.
        """
        members = ctx.udc['gp'].list_group_members(group)
        return set([m['member_name'] for m in members if m['member_name']]) 
        
    @rpc(String, _returns=Iterable(String), _throws=faults.EndUserFault)
    def list_group_memberships(ctx, user):
        """ This rpc lists names of groups where a given user is member.
        """
        groups = ctx.udc['gp'].list_group_memberships(user)
        return set([g['name'] for g in groups if g['name']])


# The group service events:
def _event_setup_gp(ctx):
    """ Event method for setting up/instantiating the context. """
    ctx.udc['gp'] = ctx.service_class.cere_class()

def _event_cleanup(ctx):
    """ Event for cleaning up the groupinfo instances, i.e. close the database
    connections. """
    if ctx.udc.has_key('gp'):
        ctx.udc['gp'].close()

# Add session support to the service:
add_listener = GroupPublishService.event_manager.add_listener
add_listener('method_call', SoapListener.on_method_call_session)
add_listener('method_return_object', SoapListener.on_method_exit_session)

# Add instance specific events:
add_listener('method_call', _event_setup_gp)
add_listener('method_return_object', _event_cleanup)
add_listener('method_exception_object', _event_cleanup)


def usage(exitcode=0):
    print """Usage: %s [-p <port number] [-l logfile] [--unencrypted]

Starts up the WebIDService webservice on a given port. Please note that config
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
    GroupPublishService.cere_class = cls

    private_key_file  = None
    certificate_file  = None
    client_ca         = None
    fingerprints      = None

    if interface:
        SoapListener.TwistedSoapStarter.interface = interface

    if use_encryption:
        private_key_file  = cisconf.SERVER_PRIVATE_KEY_FILE
        certificate_file  = cisconf.SERVER_CERTIFICATE_FILE
        client_ca         = cisconf.CERTIFICATE_AUTHORITIES
        fingerprints      = getattr(cisconf, 'FINGERPRINTS', None)

        server = SoapListener.TLSTwistedSoapStarter(port = int(port),
                        applications = GroupPublishService,
                        private_key_file = private_key_file,
                        certificate_file = certificate_file,
                        client_ca = client_ca,
                        client_fingerprints = fingerprints,
                        logfile = logfilename,
                        log_prefix = log_prefix,
                        log_formatters=log_formatters)
    else:
        server = SoapListener.TwistedSoapStarter(port = int(port),
                                    applications = GroupPublishService,
                                    logfile = logfilename,
                                    log_prefix = log_prefix,
                                    log_formatters=log_formatters)

    GroupPublishService.site = server.site # to make it global and reachable by tier

    # We want the sessions to be simple dicts, for now:
    server.site.sessionFactory = SoapListener.SessionCacher
    # Set the timeout to something appropriate:
    SoapListener.SessionCacher.sessionTimeout = 600 # = 10 minutes
    server.run()

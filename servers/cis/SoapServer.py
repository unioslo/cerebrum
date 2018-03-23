#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2010-2014 University of Oslo, Norway
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
""" This file provides a SOAP service that provides an API for Digeksd."""
import sys
import getopt
from Cerebrum.Utils import dyn_import
from Cerebrum.modules.cis import SoapListener, auth


def import_class(cls):
    """This function dynamically loads a class.

    :type cls: str
    :param cls: The class path, i.e. 'Cerebrum.modules.cheese/Stilton'
    """
    module, classname = cls.split('/', 1)
    mod = dyn_import(module)
    return getattr(mod, classname)


# The service events:
def _event_setup(ctx):
    """Event method for setting up/instantiating the context."""
    # TODO: the language functionality may be moved into SoapListener? It is
    # probably usable by other services too.
    operator_id = ctx.udc['session'].get('authenticated', None)
    if operator_id:
        operator_id = operator_id.id
    ctx.udc[ctx.service_class.__namespace__] = ctx.service_class.cere_class(
        operator_id, cisconf.SERVICE_NAME, cisconf)


def _event_cleanup(ctx):
    """Event for cleaning up the instances.

    I.e. close the database connections."""
    ctx.udc[ctx.service_class.__namespace__].close()


class Service(object):
    """Utility class to allow run-time configuration."""

    def __init__(self, ServiceCls):
        """Adds listeners to the service-class loaded at run-time."""

        # Add session support to the service:
        ServiceCls.event_manager.add_listener(
            'method_call', SoapListener.on_method_call_session)
        ServiceCls.event_manager.add_listener(
            'method_return_object', SoapListener.on_method_exit_session)

        # Add instance specific events:
        ServiceCls.event_manager.add_listener(
            'method_call', _event_setup)
        ServiceCls.event_manager.add_listener(
            'method_return_object', _event_cleanup)
        ServiceCls.event_manager.add_listener(
            'method_exception_object', _event_cleanup)

        if cisconf.AUTH:
            # Add authentication support:
            ServiceCls.event_manager.add_listener(
                'method_call', auth.on_method_authentication)


def usage(exitcode=0):
    print """Usage: %s [-p <port number] [-l logfile] [--unencrypted]

Starts up the webservice on a given port. Please note that config
(cisconf) contains more settings for the service.

  -p
  --port num        Run on alternative port than defined in cisconf.PORT.

  --interface ADDR  What interface the server should listen to. Overrides
                    cisconf.INTERFACE. Default: 0.0.0.0

  -l
  --logfile:        Where to log. Overrides cisconf.LOG_FILE.

  --service-name    The service configuration to load, e.g. 'digeks'

  --unencrypted     Don't use HTTPS. All communications goes unencrypted, and
                    should only be used for testing.

  -h
  --help            Show this and quit.
    """
    sys.exit(exitcode)


if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'p:l:hd',
                                   ['port=', 'unencrypted', 'logfile=',
                                    'help', 'interface=',
                                    'service-name=', 'dry-run'])
    except getopt.GetoptError, e:
        print e
        usage(1)

    # Scan for the service name before parsing args.
    # TODO: Make this pretty
    service = None
    for opt, val in opts:
        if opt in ('--service-name',):
            service = val

    # Load configuration before parsing args, since we want to preserve
    # overrides.
    try:
        cisconf = dyn_import('cisconf.%s' % service)
    except ImportError, e:
        if e == 'No module named None':
            print('Error: must specify service-name')
            usage(2)
        else:
            print('Error: service-name configuration \'cisconf.%s\' not found'
                  % service)
            usage(3)

    use_encryption = True
    port = getattr(cisconf, 'PORT', 0)
    logfilename = getattr(cisconf, 'LOG_FILE', None)
    instance = getattr(cisconf, 'CEREBRUM_CLASS', None)
    interface = getattr(cisconf, 'INTERFACE', None)
    log_prefix = getattr(cisconf, 'LOG_PREFIX', None)
    log_formatters = getattr(cisconf, 'LOG_FORMATTERS', None)
    dryrun = getattr(cisconf, 'DRYRUN', False)

    for opt, val in opts:
        if opt in ('-l', '--logfile'):
            logfilename = val
        elif opt in ('-p', '--port'):
            port = int(val)
        elif opt in ('--unencrypted',):
            use_encryption = False
        elif opt in ('--interface',):
            interface = val
        elif opt in ('-h', '--help'):
            usage()
        elif opt in ('--service-name',):
            pass
        elif opt in ('--dry-run',):
            dryrun = True
        else:
            print "Unknown argument: %s" % opt
            usage(1)

    private_key_file = None
    certificate_file = None
    client_ca = None
    fingerprints = None

    services = []
    # Get the service tier classes and give it to the server
    for key in getattr(cisconf, 'CLASS_CONFIG'):
        srv_cls = import_class(key)
        srv_cls.cere_class = import_class(
            getattr(cisconf, 'CLASS_CONFIG').get(key))
        srv_cls.dryrun = dryrun
        Service(srv_cls)
        services.append(srv_cls)

    # Add password authentication, if specified in config.
    if cisconf.AUTH:
        services.append(auth.PasswordAuthenticationService)

    if interface:
        SoapListener.TwistedSoapStarter.interface = interface

    if use_encryption:
        private_key_file = cisconf.SERVER_PRIVATE_KEY_FILE
        certificate_file = cisconf.SERVER_CERTIFICATE_FILE
        client_ca = cisconf.CERTIFICATE_AUTHORITIES
        fingerprints = getattr(cisconf, 'FINGERPRINTS', None)

        server = SoapListener.TLSTwistedSoapStarter(
            port=int(port),
            applications=services,
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
            applications=services,
            logfile=logfilename,
            log_prefix=log_prefix,
            log_formatters=log_formatters)

    # Making stuff reachable
    for srv in services:
        srv.site = server.site

    # We want the sessions to be simple dicts, for now:
    server.site.sessionFactory = SoapListener.SessionCacher
    # Set the timeout to something appropriate:
    SoapListener.SessionCacher.sessionTimeout = 10 * 60  # = 10 minutes
    server.run()

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

import sys
import getopt

from twisted.python import log

from rpclib.decorator import rpc
from rpclib.model.complex import ComplexModel, Iterable
from rpclib.model.primitive import String, Boolean, Integer
from Cerebrum.modules.cis.Utils import Unicode, DateTime

import cerebrum_path
#from cisconf import alumniservice as cisconf
from Cerebrum.modules.cis import default_config as cisconf
from Cerebrum.Utils import dyn_import
#from Cerebrum import Errors
from Cerebrum.modules.cis import SoapListener, auth, faults


# FIXME
cisconf.PORT = 8958
cisconf.INTERFACE = '0.0.0.0'
cisconf.CERTIFICATE_AUTHORITIES = []
cisconf.FINGERPRINTS = ()
cisconf.SERVER_CERTIFICATE_FILE = '/usit/platon/gt-u1/fhl/src/cert/cere-utv01.pem'
cisconf.SERVER_PRIVATE_KEY_FILE = '/usit/platon/gt-u1/fhl/src/cert/cere-utv01.key'

cisconf.CEREBRUM_CLASS = 'Cerebrum.modules.cis.Alumni/AlumniControl'
cisconf.LOG_PREFIX = 'cis_alumni:'
cisconf.LOG_FILE = 'alumni.log'


class Alumni(ComplexModel):
    """ An object that represents the alumni-data connected to a personal
    account. This object will be used to transport information to and from the
    client. """
    __namespace__ = 'alumni'
    __tns__ = 'alumni'

    uname = Unicode
    bdate = DateTime
    gender = Unicode

    fname = Unicode
    lname = Unicode
    email = Unicode
    addr_number = Integer
    addr_country = Unicode
    mobile = Unicode
    degree = Unicode


class AlumniSearchParams(ComplexModel):
    # TODO
    __namespace__ = 'alumni'
    __tns__ = 'alumni'

    uname = String
    fname = String
    lname = String
    bdate = DateTime
    gender = String
    degree = String
    addr_number = String


class AlumniService(SoapListener.BasicSoapServer):
    """ The Alumni service. Methods in this class will NOT require
    authentication!
    """

    __namespace__ = 'alumni'
    __tns__ = 'alumni'

    # Require the session ID in the client's header
    __in_header__ = SoapListener.SessionHeader

    # Respond with a header with the current session ID
    __out_header__ = SoapListener.SessionHeader

    # The class where the Cerebrum-specific functionality is done. This is
    # instantiated per call, to avoid thread conflicts.
    cere_class = None

    # The hock for the site object
    site = None

    @rpc(_returns=String)
    def status(ctx):
        if ctx.udc['alumni'].is_admin():
            return 'admin'
        elif ctx.udc['alumni'].is_alumni():
            return 'alumni'

        return 'none'

    @rpc(_returns=Boolean, _throws=faults.EndUserFault)
    def abort(ctx):
        return ctx.udc['alumni'].abort()

    @rpc(Alumni, _returns=Boolean, _throws=faults.EndUserFault)
    def register_alum(ctx, alum):
        #TODO: Document
        alum_dict = getattr(alum, '__dict__', {})
        return ctx.udc['alumni'].register_alum(alum_dict)

    @rpc(Unicode, _returns=Alumni, _throws=faults.EndUserFault)
    def lookup_person_info(ctx, username):
        ##TODO: Document
        return ctx.udc['alumni'].lookup_person_info(username)

    # Debug stuff
    @rpc(String, _returns=Boolean, _throws=faults.EndUserFault)
    def clear_alum_info(ctx, username):
        #TODO: Document
        return ctx.udc['alumni'].clear(username)

    @rpc(String, _returns=Alumni, _throws=faults.EndUserFault)
    def get_alum_info(ctx, username):
        #TODO: Document
        #auth.on_method_authentication(ctx)
        return ctx.udc['alumni'].get_alum_info(username)

    @rpc(Iterable(String), _returns=Iterable(Alumni), _throws=faults.EndUserFault)
    def get_alum_info_multi(ctx, usernames):
        #TODO: Document
        #usernames = [u1, u2]
        ##auth.on_method_authentication(ctx)
        return [ctx.udc['alumni'].get_alum_info(u) for u in usernames]

    @rpc(Alumni, _returns=Alumni, _throws=faults.EndUserFault)
    def set_alum_info(ctx, alum):
        #TODO: Document
        # Ugly
        alum_dict = getattr(alum, '__dict__', {})
        return ctx.udc['alumni'].set_alum_info(alum_dict)

    @rpc(AlumniSearchParams, _returns=Iterable(Alumni), _throws=faults.EndUserFault)
    def search(ctx, params):
        # TODO: Document
        raise NotImplementedError, 'TODO'

    @rpc(String, _returns=String, _throws=faults.EndUserFault)
    def phptest(ctx, string):
        log.msg('DEBUG: Got string (%s)' % string)
        return string

    @rpc(_returns=String, _throws=faults.EndUserFault)
    def cache_test(ctx):
        return ctx.udc['alumni'].set_alum_info()


# TEST: Every method here will require authentication
class AlumniAuthService(AlumniService):

    @rpc(_returns=Unicode)
    def auth_test(ctx):
        return 'Hello, World!'


# The alumni service events:
def _event_setup_service(ctx):
    """ Event method for setting up the controller object """
    operator = ctx.udc['session'].get('authenticated', None)
    if operator:
        ctx.udc['alumni'] = ctx.service_class.cere_class(operator.id)
    else:
        ctx.udc['alumni'] = ctx.service_class.cere_class()


def _event_cleanup(ctx):
    """ Cleanup """
    if ctx.udc.has_key('alumni'):
        ctx.udc['alumni'].close()


# Non-authenticated service class events
AlumniService.event_manager.add_listener('method_call', _event_setup_service)
AlumniService.event_manager.add_listener('method_return_object',
                                         _event_cleanup)
AlumniService.event_manager.add_listener('method_exception_object',
                                         _event_cleanup)

## Add session support:
AlumniService.event_manager.add_listener('method_call',
                                         SoapListener.on_method_call_session)
AlumniService.event_manager.add_listener('method_return_object',
                                         SoapListener.on_method_exit_session)


# Authenticated service class events
AlumniAuthService.event_manager.add_listener('method_call',
                                             _event_setup_service)
AlumniAuthService.event_manager.add_listener('method_return_object',
                                             _event_cleanup)
AlumniAuthService.event_manager.add_listener('method_exception_object',
                                             _event_cleanup)

## Add session support
AlumniAuthService.event_manager.add_listener('method_call',
                                             SoapListener.on_method_call_session)
AlumniAuthService.event_manager.add_listener('method_return_object',
                                             SoapListener.on_method_exit_session)

## Require auth
AlumniAuthService.event_manager.add_listener('method_call',
                                             auth.on_method_authentication)


def usage(exitcode=0):
    print """Usage: %s [-p <port number] [-l logfile] [--unencrypted]

Starts up the AlumniService webservice on a given port. Please note that config
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
    AlumniService.cere_class = cls

    AlumniAuthService.cere_class = cls

    private_key_file  = None
    certificate_file  = None
    client_ca         = None
    fingerprints      = None

    services = [auth.PasswordAuthenticationService, AlumniService, AlumniAuthService]
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
    AlumniService.site = server.site # to make it global and reachable by tier (wrong, I know)
    AlumniAuthService.site = server.site # to make it global and reachable by tier (wrong, I know)
    auth.PasswordAuthenticationService.site = server.site # to make it global and reachable (wrong, I know)

    # We want the sessions to be simple dicts, for now:
    server.site.sessionFactory = SoapListener.SessionCacher
    # Set the timeout to something appropriate:
    SoapListener.SessionCacher.sessionTimeout = 600 # = 10 minutes
    log.msg("DEBUG: AlumniService is using: %s" % instance)
    server.run()

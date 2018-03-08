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

from rpclib.model.complex import ComplexModel, Iterable
from rpclib.model.primitive import String
# Note the difference between rpc and the static srpc - the former sets the
# first parameter as the current MethodContext. Very nice if you want
# environment details.
from rpclib.decorator import rpc

import cerebrum_path
from cisconf import groupservice as cisconf
from Cerebrum.Utils import dyn_import
from Cerebrum.modules.cis import SoapListener, auth, faults

del cerebrum_path


class GroupMember(ComplexModel):
    """Information about a group member."""
    __namespace__ = 'tns'
    __tns__ = 'tns'

    # The username
    uname = String

    # The entity_type of the member
    member_type = String

    # The entity_id of the member
    member_id = String

    # TODO more info about a member?


class GroupService(SoapListener.BasicSoapServer):
    """The Group service, for returning information about groups.

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

    @rpc(String, _returns=Iterable(GroupMember),
         _throws=faults.EndUserFault)
    def get_members(ctx, groupname):
        """Get a list of all the members of a given group.

        @type groupname: String
        @param groupname: The name of the group that should be listed.

        @rtype: List/array of GroupMember objects
        @return: Returns a list or array where the elements are objects of the
                 type GroupMember, which contains the member's username,
                 entity_type and entity_id, i.e. the member's internal ID in
                 Cerebrum.

        """
        return ctx.udc['groupinfo'].search_members_flat(groupname)


# The group service events:
def _event_setup_groupservice(ctx):
    """Event method for fixing the individuation functionality, like language.
    Makes use of the session, so it has to be run after the session setup.

    """
    # TODO: the language functionality may be moved into SoapListener? It is
    # probably usable by other services too.
    operator_id = ctx.udc['session'].get('authenticated', None)
    if operator_id:
        operator_id = operator_id.id
    ctx.udc['groupinfo'] = ctx.service_class.cere_class(operator_id)


def _event_cleanup(ctx):
    """Event for cleaning up the groupinfo instances, i.e. close the
    database connections. Since twisted runs all calls in a pool of threads, we
    can not trust __del__."""
    # TODO: is this necessary any more, as we now are storing it in the method
    # context? Are these deleted after each call?
    if 'groupinfo' in ctx.udc:
        ctx.udc['groupinfo'].close()

# Add session support to the group service:
GroupService.event_manager.add_listener('method_call',
                                        SoapListener.on_method_call_session)
GroupService.event_manager.add_listener('method_return_object',
                                        SoapListener.on_method_exit_session)

# Add the group specific events:
GroupService.event_manager.add_listener('method_call',
                                        _event_setup_groupservice)
GroupService.event_manager.add_listener('method_return_object',
                                        _event_cleanup)
GroupService.event_manager.add_listener('method_exception_object',
                                        _event_cleanup)

# Add authentication support to the group service:
GroupService.event_manager.add_listener('method_call',
                                        auth.on_method_authentication)


def usage(exitcode=0):
    print """Usage: %s [-p <port number] [-l logfile] [--unencrypted]

Starts up the GroupService webservice on a given port. Please note that config
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

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'p:l:h',
                                   ['port=', 'unencrypted', 'logfile=',
                                    'help', 'instance=', 'interface='])
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
    GroupService.cere_class = cls
    # TBD: Should Cerebrum tier be started once per session instead? Takes
    # more memory, but are there benefits we need, e.g. language control?

    private_key_file = None
    certificate_file = None
    client_ca = None
    fingerprints = None

    services = [auth.PasswordAuthenticationService, GroupService]
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
        server = SoapListener.TwistedSoapStarter(port=int(port),
                                                 applications=services,
                                                 logfile=logfilename,
                                                 log_prefix=log_prefix,
                                                 log_formatters=log_formatters)
    GroupService.site = server.site
    auth.PasswordAuthenticationService.site = server.site

    # We want the sessions to be simple dicts, for now:
    server.site.sessionFactory = SoapListener.SessionCacher
    # Set the timeout to something appropriate:
    SoapListener.SessionCacher.sessionTimeout = 600  # 10 minutes
    log.msg("DEBUG: GroupServer is using: %s" % instance)
    server.run()

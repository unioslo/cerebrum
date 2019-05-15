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
"""Doing WinRM protocol stuff.

The WinRM is the protocol that we are using to send CMD and Powershell commands
to Windows machines.

"""

import getopt
import sys
from lxml import etree

import adconf
from Cerebrum.Utils import Factory, read_password
from Cerebrum import Errors
from Cerebrum.modules.ad2.winrm import WinRMClient, WinRMException

logger = Factory.get_logger('console')
db = Factory.get('Database')()
co = Factory.get('Constants')(db)

def usage(exitcode=0):
    print """Usage: winrm.py [OPTIONS]...

    %(doc)s

    Actions:

    --delete-shell SHELLID
                    Send a signal to delete the shell by the given ShellId and
                    quit.

    Options:

    --type TYPE     If given, the server name, credentials and other settings
                    are fetched from the given sync type. Otherwise you have to
                    specify server name and authentication details.

                    Note that the type must exist in adconf.SYNCS.

    Options for when --type is not specified:

    --host HOSTNAME The hostname of the Windows server that should execute the
                    code. Needed if --type is not specified.

    --port PORT     The port number on the Windows server. Default: 5986 for
                    encrypted communication, otherwise 5985.

    Other options:

    --unencrypted   If the communication should go unencrypted. This should only
                    be used for testing!

    -h, --help      Show this and quit.

    """ % {'doc': __doc__}
    sys.exit(exitcode)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   "h",
                                   ["help",
                                    "unencrypted",
                                    "type=",
                                    "host=",
                                    "delete-shell=",
                                    "port="])
    except getopt.GetoptError, e:
        print e
        usage(1)

    encrypted = True
    sync = None
    host = port = None

    for opt, val in opts:
        # General options
        if opt in ('-h', '--help'):
            usage()
        elif opt == '--unencrypted':
            encrypted = False
        elif opt == '--type':
            if val not in adconf.SYNCS:
                print "Sync type '%s' not found in config" % val
                print "Defined sync types:"
                for typ in adconf.SYNCS:
                    print '  %s' % typ
                sys.exit(2)
            sync = adconf.SYNCS[val]
        elif opt == '--host':
            host = val
        elif opt == '--port':
            port = int(val)

    if not host and not sync:
        print "Need either --type or --host to connect to"
        usage(1)

    if not host:
        host = sync['server']
    if not port:
        port = sync.get('port', None)
    user = sync['auth_user']

    logger.info("Start")
    client = WinRMClient(host=host, port=port, encrypted=encrypted,
                         logger=logger)
    # TODO: add ca, client_key and client_cert
    client._winrs_skip_cmd_shell = False
    #client._winrs_consolemode_stdin = False
    client.add_credentials(username=user,
                           password=read_password(user, host))


    for opt, val in opts:
        if opt == '--delete-shell':
            logger.info("Deleting shell with ShellId: %s", val)
            client.wsman_delete(val)
            logger.info("Finished")
            sys.exit()


    # Get server identification:
    logger.info("Identifying server")
    ident = client.wsman_identify()
    # TODO: doesn't work now
    for key in ('ProtocolVersion', 'ProductVendor', 'ProductVersion'):
        for event, elem in ident.iterfind('{http://schemas.dmtf.org/wbem/wsman/identity/1/wsmanidentity.xsd}%s' % key):
            logger.info("  %s: %s", key, elem.text)

    # List active shells and connections:
    logger.info("Listing shells...")
    resource = 'windows/shell'
    req = client.wsman_enumerate(resource)
    logger.debug("Got request Id: %s", req)
    print etree.tostring(client.wsman_pull(resource, req), pretty_print=True)

    logger.info("Listing listeners...")
    resource = 'winrm/config/listener'
    req = client.wsman_enumerate(resource)
    logger.debug("Got request Id: %s", req)
    print etree.tostring(client.wsman_pull(resource, req), pretty_print=True)

    resource = 'http://schemas.microsoft.com/wbem/wsman/1/windows/shell/cmd'
    req = client.wsman_get(resource)
    logger.debug("Got request Id: %s", req)
    print etree.tostring(client.wsman_pull(resource, req), pretty_print=True)

    # Try to create a WinRM shell:
    logger.info("Creating Shell...")
    shellid = client.wsman_create()
    logger.info("Success, got ShellId: %s", shellid)



    logger.info("Finished")

if __name__ == '__main__':
    main()


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
"""Running cmd commands against a Windows machine.

This script is for running generic cmd commands against Windows and AD, e.g.
commands against winrm.

If you want to run powershell commands, you could either run::

    cmd.py powershell.exe ...

or you could just use L{powershell.py}, which sets up a bit more for you, e.g.
credentials for the AD environment.

Examples::

    # Get the WinRM configuration:
    winrm get winrm/config

    # TODO

Note that, due to limitations in the communication with WinRM, the code have to
finish execution before you could see the result. You will therefore not be able
to run a cmd shell, or any other shell, interactively. This might change if we
get more time working with the WinRM protocol.

Don't forget to escape the dollar and other Windows related characters in your
shell!

"""

import getopt
import sys

import adconf
from Cerebrum.Utils import Factory, read_password
from Cerebrum import Errors
from Cerebrum.modules.ad2.winrm import WinRMClient

logger = Factory.get_logger('console')
db = Factory.get('Database')()
co = Factory.get('Constants')(db)

def usage(exitcode=0):
    print """Usage: cmd.py [OPTIONS] CODE...

    %(doc)s

    Parameters:

    CODE            The cmd code that should be executed. The output from the
                    code is returned back to stdout.

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
        else:
            print "Unknown option: %s" % opt
            usage(1)

    if not host and not sync:
        print "Need either --type or --host to connect to"
        usage(1)

    if not args:
        print "Command to run is required"
        usage(1)

    if not host:
        host = sync['server']
    if not port:
        port = sync.get('port', None)
    user = sync['auth_user']

    client = WinRMClient(host=host, port=port, encrypted=encrypted,
                         logger=logger)
    # TODO: add ca, client_key and client_cert
    client._winrs_skip_cmd_shell = False
    #client._winrs_consolemode_stdin = False
    client.add_credentials(username=user,
                           password=unicode(read_password(user, host), 'utf-8'))
    client.connect()

    code = ' '.join(args)
    logger.debug("Running code: %s" % code)

    try:
        out = client.run(code)
    finally:
        client.close()
    for outtype in ('stderr', 'stdout'):
        data = out.get(outtype)
        if data:
            print '%s:' % outtype.upper()
            print data
            print
    logger.debug("Done")

if __name__ == '__main__':
    main()


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
"""Running powershell commands against a Windows machine.

This script is for running generic powershell commands against Windows and AD.
As the usage for this script is to debug our AD sync, some code is sent before
the given code::

    $cred = New-Object System.Management.Automation.PSCredential(DOMAIN_USER, PASSWORD)
    Import-Module ActiveDirectory

Which means, that to be able to run any cmdlet related to ActiveDirectory, you
need to add the parameter::

    -Credential $cred

Which is then making use of the domain account and not the local auth_user. 

Examples::

    # See all attributes for an account as registered in AD:
    Get-ADuser -Credential '$cred' -Properties '*' USERNAME

    # Get information about the AD forest we're in:
    Get-ADForest -Credential '$cred' -Current LocalComputer

    # Get information about the AD domain we're in:
    Get-ADDomain -Credential '$cred' -Current LocalComputer

    # Get information about the Directory Server:
    Get-ADRootDSE -Credential '$cred' 

    # Get the password policy of the domain:
    Get-ADDefaultDomainPasswordPolicy -Credential '$cred' -Current LocalComputer

    # To unlock an account that has tried to authenticate too many times:
    Unlock-ADAccount -Credential '$cred' USERNAME

    # Not sure about the format and parameters of a command?
    Get-Help COMMAND

Note that, due to limitations in the communication with WinRM, the code have to
finish execution before you could see the result. You will therefore not be able
to e.g. start a new session through Enter-PSSession and add more commands to
that session, you must execute everything in one go.

Don't forget to escape the dollar and other Windows related characters in your
shell!

"""

import getopt
import sys

import adconf
from Cerebrum.Utils import Factory
from Cerebrum.modules.ad2.ADUtils import ADclient

logger = Factory.get_logger('console')
db = Factory.get('Database')()
co = Factory.get('Constants')(db)


def usage(exitcode=0):
    print """Usage: powershell.py [OPTIONS] CODE...

    %(doc)s

    Parameters:

    CODE            The powershell code that should be executed. The output from
                    the code is returned back to stdout.

    Options:

    --type TYPE     If given, the server name, credentials and other settings
                    are fetched from the given sync type. Otherwise you have to
                    specify server name and authentication details.

                    Note that the type must exist in adconf.SYNCS.

    --clean         If set, no powershell commands would be executed before the
                    given code. The code sets for instance the variable $cred,
                    which contains the credentials for our domain user.

    Options for when --type is not specified:

    --host HOSTNAME The hostname of the Windows server that should execute the
                    code. Needed if --type is not specified.

    --port PORT     The port number on the Windows server. Default: 5986 for
                    encrypted communication, otherwise 5985.

    --auth_user USERNAME The username of the account that should connect to the
                    Windows machine. Password must be stored in the standard
                    password location.

    --domain_user USERNAME The username of the account that should be able to
                    administrate the AD domain. Password must be stored in the
                    standard password location.

    Other options:

    --unencrypted   If the communication should go unencrypted. This should only
                    be used for testing!

    --ca_cert FILE  Use a given CA certificate chain for testing. If --type is
                    given, the default value will fall back to the setting from
                    adconf.

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
                                    "clean",
                                    "port=",
                                    "auth_user=",
                                    "ca_cert=",
                                    "domain_user="])
    except getopt.GetoptError, e:
        print e
        usage(1)

    encrypted = True
    sync = None
    host = port = None
    auth_user = domain_user = domain = None
    ca = None

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
        elif opt == '--auth_user':
            auth_user = val
        elif opt == '--domain_user':
            domain_user = val
        elif opt == '--ca_cert':
            ca = val
        elif opt == '--clean':
            # Drain the client for pre-code:
            ADclient._pre_execution_code = u''
        else:
            print "Unknown option: %s" % opt
            usage(1)

    if not host and not sync:
        print "Need either --type or --host to connect to"
        usage(1)

    if not args:
        print "Powershell code required"
        usage(1)

    if not host:
        host = sync['server']
    if not port and sync:
        port = sync.get('port')
    if sync:
        if not auth_user:
            auth_user = sync['auth_user']
        if not domain_user:
            domain_user = sync['domain_admin']
        if not domain:
            domain = sync['domain']
        if encrypted and not ca:
            ca = sync.get('ca')
    else:
        if not auth_user:
            print "If no specific sync, --auth_user is required"
            usage(1)

    client = ADclient(logger=logger,
                      host=host,
                      port=port,
                      auth_user=auth_user,
                      domain_admin=domain_user,
                      domain=domain,
                      encrypted=encrypted,
                      ca=ca,
                      dryrun=False)

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

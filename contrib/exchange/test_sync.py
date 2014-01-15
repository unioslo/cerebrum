
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
"""Proof of concept sync"""

import getopt
import sys

import cerebrum_path
import adconf
from Cerebrum.Utils import Factory
from Cerebrum.modules.exchange.ExchangeClient import ExchangeClient
import time

logger = Factory.get_logger('console')
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
gr = Factory.get('Group')(db)

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

    -h, --help      Show this and quit.

    """ % {'doc': __doc__}
    sys.exit(exitcode)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   "h:",
                                   ["help",
                                    "unencrypted",
                                    "type="])
    except getopt.GetoptError, e:
        print e
        usage(1)

    encrypted = True
    sync = None
    host = port = None
    auth_user = ex_domain_user = domain_user = None
    management_server = None

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
        else:
            print "Unknown option: %s" % opt
            usage(1)

    if not host and not sync:
        print "Need either --type or --host to connect to"
        usage(1)

    if not host:
        host = sync['server']
    if not port:
        port = sync.get('port', None)
    if not auth_user:
        auth_user = sync['auth_user']
    if not domain_user:
        domain_user = sync['domain_admin']
    if not ex_domain_user:
        ex_domain_user = sync['ex_domain_admin']
    if not management_server:
        management_server = sync['management_server']


    client = ExchangeClient(logger=logger,
                      host=host,
                      port=port,
                      auth_user=auth_user,
                      domain_admin=domain_user,
                      ex_domain_admin=ex_domain_user,
                      management_server=management_server,
                      encrypted=encrypted)

    #def new_mailbox(self, uname, db, quota, emails):
    #    """Create a new mailbox in Exchange.

    #    @type username: string
    #    @param username: The users username

    #    @type db: string
    #    @param db: The DB the user should reside on

    #    @type quota: string
    #    @param quota: The size of the mailbox

    #    @type emails: string
    #    @param emails: A list of email-addresses the user should
    #        have.

    #    @rtype: bool
    #    @return: Return True if success, False if failure

    # We stuff evereything here
    db = "db01_mail-mbox02"


    # Pull some testusers for export
    gr.find_by_name('mntv')
    for x in gr.search_members(group_id=gr.entity_id, member_type=co.entity_account):
        ac.clear()
        ac.find(x['member_id'])
        try:
            ts = time.time()
            out = client.new_mailbox(ac.account_name, db, '1G', ac.get_primary_mailaddress())
            tf = time.time() - ts
#            out = client.new_local_mailbox(ac.account_name, db)
#            out = client.dbug()
#            out = client.in_ad(ac.account_name)
            if out and out.has_key('stderr') and out['stderr']:
                print "STDERR:"
                print out['stderr']
            else:
                print 'Created %s in %s' % (ac.account_name, str(tf))
        except Exception, e:
            print e
    if client.kill_session():
        print "Session killed"
    else:
        print "Could not kill session!"

if __name__ == '__main__':
    main()


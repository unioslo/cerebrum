
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
                                   "hn:",
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
    number = 1

    for opt, val in opts:
        # General options
        if opt in ('-h', '--help'):
            usage()
        if opt in ('-n',):
            number = int(val)
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

    # We stuff evereything here
    db = "db01_mail-mbox01"

    to_create = []
    gr.find_by_name('hf')
    for x in [e for e in gr.search_members(group_id=gr.entity_id,
                                        member_type=co.entity_account,
                                        member_spread=co.spread_uio_ad_account,
                                        member_filter_expired=True)][:3000]:
        ac.clear()
        ac.find(x['member_id'])
        to_create.append({'uname': ac.account_name, 
                          'db': db,
                          'quota': '1G',
                          'email': ac.get_primary_mailaddress()})

    FAILED = 1
    SUCCESS = 2

    print "Creating %d accounts" % len(to_create)
    def create_mbox(toc, key, r_status):
        client = ExchangeClient(logger=logger,
                          host=host,
                          port=port,
                          auth_user=auth_user,
                          domain_admin=domain_user,
                          ex_domain_admin=ex_domain_user,
                          management_server=management_server,
                          encrypted=encrypted,
                          session_key=key)

        for x in toc:
            ts = time.time()
            out = client.new_mailbox(x['uname'], x['quota'], x['email'])#, x['db'])
            tf = time.time() - ts
            if out and out.has_key('stderr') and out['stderr']:
                print 'Failed creating %s' % x['uname']
                print 'STDERR:'
                print out['stderr']
                r_status.put((FAILED, x['uname']))
            else:
                print 'Created %s in %s' % (x['uname'], str(tf))
                r_status.put((SUCCESS, x['uname']))

        if client.kill_session():
            print "Session killed"
        else:
            print "Could not kill session!"
        client.close()


    # Import stuff for multiprocessing
    import random
    import processing
    from Queue import Empty
    # Define a function for creating random PSSession names
    gen_key = lambda: 'CB%s' % hex(random.randint(0xF00000,0xFFFFFF))[2:].upper()

    # We need to store the procecess, and define the number of threads
    threads = []
    no_threads = 15

    # We want to get return messages from the processes
    r_status = processing.Queue()

    # Create all the processes, and partition up the changelist between them
    for i in range(0, no_threads-1):
        part_start = (len(to_create)/no_threads)*i
        part_stop = ((len(to_create)/no_threads)*i)+ (len(to_create)/no_threads)
        print "part: %d:%d" % (part_start, part_stop)
        threads.append(processing.Process(target=create_mbox,
            args=(to_create[part_start:part_stop], gen_key(), r_status,)))
    part_start = (len(to_create)/no_threads)*(i+1)
    part_stop = ((len(to_create)/no_threads)*(i+1)) + \
                    (len(to_create)/no_threads) + len(to_create) % no_threads
    threads.append(processing.Process(target=create_mbox,
                   args=(to_create[part_start:part_stop],
                   gen_key(),
                   r_status,)))
    print "part: %d:%d" % (part_start, part_stop)

    # Start all processes
    st = time.time()
    for x in threads:
        x.daemon = True
        x.start()
        # Try to eaven out the load a little.
        # TODO: Devise a more effective way of doing this
        time.sleep(0.2)
    
    # TODO: Implement trap of SIGINT or SIGTERM, with termination of the
    # processes or something

    # Fetch all status data returned from the processes
    print "Collecting childrens return status @ %d" % time.time()
    sys.stdout.flush()
    i = 0
    returned = []
    data_left = True
    while data_left:
        try:
            returned.append(r_status.get(block=False))
            if i % 100 == 0:
                print "Collected %d items @ %d" % (i, time.time())
                sys.stdout.flush()
            i = i + 1
        except Empty:
            data_left = False if not processing.activeChildren() else True
            time.sleep(1)

    x.join(0.1)

    # Print some stats
    print '%d accounts failed' % len(filter(lambda x: x[0] is FAILED,
                                        returned))
    print '%d accounts succeded' % len(filter(lambda x: x[0] is SUCCESS,
                                        returned))

    print "joined after %.2f" % (time.time() - st)
   
    f = open('r%d' % time.time(), 'w')
    f.write(str(returned))
    f.close()
    
if __name__ == '__main__':
    main()


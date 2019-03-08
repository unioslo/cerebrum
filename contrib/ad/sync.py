#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2012-2015 University of Oslo, Norway
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
"""Running a generic sync with Active Directory.

This is the default script for running syncs against AD for all instances. The
purpose of the script is to be able to update every instance' Active Directory.
The hope is that we don't need instance specific scripts.

A full sync is gathering all relevant data from both Cerebrum and AD and
comparing it. If there are mismatches between Cerebrum and AD, AD gets updated.
The quick sync does instead just check Cerebrum's change log and blindly sends
the changes to AD. If AD complains, the changes will be processed later on.

"""

import getopt
import sys

import adconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules.ad2.ADSync import BaseSync

logger = Factory.get_logger('ad_sync')
db = Factory.get('Database')(client_encoding='UTF-8')
db.cl_init(change_program="ad_sync")
co = Factory.get('Constants')(db)

def usage(exitcode=0):
    print """Usage: sync.py [OPTIONS] --type TYPE

    %(doc)s

    Sync options:

    --type TYPE     What type of AD-sync to perform. The sync type must be
                    defined in the config file. Normally, the sync type is the
                    name of a spread, which makes the entities with the given
                    spread the targets.

                    TODO: support a comma separated list of types to sync
                    several types in sequence?

    --quick CL_NAME If the sync should do a quicksync, i.e. only sending the
                    latest Cerebrum changes to AD. If not set, a fullsync is
                    processed by default. The CL_NAME is the change-log-key to
                    be used for figuring out what changes has already been sent
                    or not. It could be set to any string, but it MUST be
                    different for each sync!

    --change-ids ID Run the quicksync only for a certain change-log event. The
                    ID(s) must refer to change-log-IDs, which are then processed
                    as in the quicksync. This is typically for password changes.
                    The ID could be a comma separated list of IDs.

    -d, --dryrun    Do not write changes back to AD, but log them. Usable for
                    testing. Note that the sync is still reading data from AD.

    -m, --mock      Do not connect to AD, run with mock of AD.

    -n, --store-mock-state <FILE>
                    Store the mock state in a JSON file.

    -l, --load-mock-state <FILE>
                    Load the mocks state from a JSON file.

    --sync_class CLS If some specific class should be used as the sync class.
                    Defaults to using what is defined in the config file for the
                    sync type. Could be specified several times, and be comma
                    separated; would then create a new class out of all such.
                    Usable for adding mixins.

    --subset        A comma separated list of names to process. If given, only
                    the entities and objects with a name in the list will be
                    processed. This is for debugging and testing purposes only.

    TODO: Include this?
    --attributes    Control what attributes that should be synced.

    --set VALUE=... Set a configuration variable for the sync. This is used to
                    be able to set any configuration variable, e.g. 'store_sid'
                    or 'move_objects'. The name and the value of a configuration
                    variable must be separated with '='. This is for now only
                    supported for config that requires strings (or integers).

                    Note that setting config values like this does not have any
                    input control. Use with care.

    AD related options:

    --host HOSTNAME The hostname of the Windows server we communicate with. We
                    normally don't communicate with a domain controller
                    directly, but rather through a Windows server which again
                    communicates with AD.

    --port PORT     The port number on the Windows server. Default: 5986 for
                    encrypted communication, otherwise 5985.

    --unencrypted   If the communication should go unencrypted. This should only
                    be used for testing! We should e.g. not send passwords in
                    plaintext unencrypted.

    Debug options:

    --debug         Print debug information, mostly for developers.

    --dump-cerebrum-data Instead of syncing, just dump out how Cerebrum wants
                    the AD side to look like, to be able to debug the Cerebrum
                    functionality. The output is independent of how AD looks
                    like. The output is meant to be easy to search and compare,
                    so the format is:

                        ad-id;attribute-name;value

                    For example:

                        emplyoees;GidNumber;1002
                        bob;GivenName;Bob
                        bob;EmployeeNumber;0123456

                    The output is sorted by entity name and the attribute names.

    --dump-diff     Instead of syncing, the Cerebrum data is compared with AD
                    and all the changes that is supposed to happen is dumped
                    out. AD will not be updated.

                    TODO: This is not implemented.

    Other options:

    --logger-level LEVEL What log level should it start logging. This is handled
                         by Cerebrum's logger. Default: DEBUG.

    --logger-name NAME   The name of the log. Default: ad_sync. Could be
                         specified to separate different syncs, e.g. one for
                         users and one for groups. The behaviour is handled by
                         Cerebrum's logger.

                         Note that the logname must be defined in logging.ini.

    -h, --help      Show this and quit.

    TODO: Old options, check if we should use any of these later:

          --forward-sync: sync forward addresses to AD and Exchange
          --sec-group-sync: sync security groups to AD
          --dist-group-sync: sync distribution groups to AD and Exchange
          --exchange-sync: Only sync to exhange if exchange-sync is set
          --sec-group-spread SPREAD: overrides spread from cereconf
          --dist-group-spread SPREAD: overrides spread from cereconf
          --exchange-spread SPREAD: overrides spread from cereconf
          --first-run: Signals that no data from AD is ok

    """ % {'doc': __doc__}

    sys.exit(exitcode)


def make_sync(classes, sync_type, mock=False):
    """Make an instantiated sync."""
    sync_class = BaseSync.get_class(classes=classes, sync_type=sync_type)
    sync = sync_class(db=db, logger=logger)
    adconf.SYNCS[sync_type]['mock'] = mock
    adconf.SYNCS[sync_type]['sync_type'] = sync_type
    sync.configure(adconf.SYNCS[sync_type])
    return sync


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   "hdmn:l:",
                                   ["help",
                                    "dryrun",
                                    "mock",
                                    "store-mock-state=",
                                    "load-mock-state=",
                                    "debug",
                                    "quick=",
                                    "change-ids=",
                                    "set=",
                                    "unencrypted",
                                    "dump-cerebrum-data",
                                    "dump-diff",
                                    "subset=",
                                    "type=",
                                    "sync_class=",
                                    "host=",
                                    "port="])
            # TODO: Check what of the old settings to use
            # "forward-sync", "sec-group-sync", "dist-group-sync",
            # "exchange-sync", "user-spread=", "sec-group-spread=",
            # "dist-group-spread=", "exchange-spread=", "first-run"
    except getopt.GetoptError, e:
        print e
        usage(1)

    # TODO: Should we be able to specify some more settings? How about being
    # able to specify all keys from config? Would be the easiest way to support
    # changing every setting.

    encrypted = True
    sync_type = None
    sync_classes = []
    # If we should do the quicksync instead of fullsync:
    quicksync = False
    change_ids = []
    debug = dump_cerebrum_data = dump_diff = False
    store_mock_state = load_mock_state = None

    # The configuration for the sync
    configuration = dict()

    for opt, val in opts:
        # General options
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('-d', '--dryrun'):
            configuration["dryrun"] = True
        elif opt in ('-m', '--mock'):
            configuration["mock"] = True
        elif opt in ('-n', '--store-mock-state'):
            store_mock_state = val
        elif opt in ('-l', '--load-mock-state'):
            load_mock_state = val
        elif opt == '--unencrypted':
            configuration['encrypted'] = False
        elif opt == '--sync_class':
            sync_classes.extend(val.split(','))
        elif opt == '--type':
            if val not in adconf.SYNCS:
                print "Sync type '%s' not found in config" % val
                print "Defined sync types:"
                for typ in adconf.SYNCS:
                    print '  %s' % typ
                sys.exit(2)
            sync_type = configuration['sync_type'] = val
        elif opt == '--host':
            configuration['server'] = val
        elif opt == '--port':
            configuration['port'] = int(val)
        elif opt == '--subset':
            configuration.setdefault('subset', []).extend(val.split(','))
        elif opt == '--set':
            key, value = val.split('=', 1)
            configuration[key] = value
        elif opt == '--change-ids':
            change_ids.extend(int(v) for v in val.split(','))
        elif opt == '--quick':
            quicksync = val
        elif opt == '--debug':
            debug = True
        elif opt == '--dump-diff':
            raise Exception('Dumping diff is not implemented yet')
        elif opt == '--dump-cerebrum-data':
            dump_cerebrum_data = True
        else:
            print "Unknown option: %s" % opt
            usage(1)

    if not sync_type:
        print "Need to specify what sync type to perform"
        usage(1)

    # Make use of config file settings, if not set otherwise by arguments
    for key, value in adconf.SYNCS[sync_type].iteritems():
        if key not in configuration:
            configuration[key] = value

    sync_class = BaseSync.get_class(classes=sync_classes, sync_type=sync_type)
    logger.debug2("Using sync classes: %s" % ', '.join(repr(c) for c in
                                                      type.mro(sync_class)))
    sync = sync_class(db=db, logger=logger)
    sync.configure(configuration)

    # If debugging instead of syncing:
    if dump_cerebrum_data:
        # TODO: How to avoid fetching the get-dc call at init? Maybe it
        # shouldn't be started somewhere else?
        sync.fetch_cerebrum_data()
        sync.calculate_ad_values()
        sync.server.close()
        atrnames = sorted(sync.config['attributes'])
        for entname in sorted(sync.entities):
            ent = sync.entities[entname]
            print ';'.join((ent.ad_id, u'OU', ent.ou)).encode('utf-8')
            for atrname in atrnames:
                print ';'.join((ent.ad_id, atrname,
                    unicode(ent.attributes.get(atrname,
                                '<Not Set>')))).encode('utf-8')
        return

    try:
        if load_mock_state:
            sync.server._load_state(load_mock_state)

        if change_ids:
            sync.quicksync(change_ids=change_ids)
        elif quicksync:
            sync.quicksync(quicksync)
        else:
            sync.fullsync()
        if store_mock_state:
            sync.server._store_state(store_mock_state)
    finally:
        try:
            sync.server.close()
        except Exception:
            # It's probably already closed
            pass

    # TODO: Print out memory usage. Remove when done debugging:
    if debug:
        for line in open('/proc/self/status', 'r'):
            if 'VmPeak' in line:
                _, size, unit = line.split()
                size = int(size)
                if size > 1024:
                    if unit == 'kB':
                        size = size / 1024
                        unit = 'MB'
                print "Memory peak: %s %s" % (size, unit)

if __name__ == '__main__':
    main()

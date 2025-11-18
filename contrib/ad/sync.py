#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2012-2025 University of Oslo, Norway
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
"""Run a generic sync with Active Directory.

This is the default script for running syncs against AD for all instances. The
purpose of the script is to be able to update every instance' Active Directory.
The hope is that we don't need instance specific scripts.

A full sync is gathering all relevant data from both Cerebrum and AD and
comparing it. If there are mismatches between Cerebrum and AD, AD gets updated.
The quick sync does instead just check Cerebrum's change log and blindly sends
the changes to AD. If AD complains, the changes will be processed later on.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import io
import logging
import textwrap

import adconf
import Cerebrum.logutils
from Cerebrum.Utils import Factory
from Cerebrum.modules.ad2.ADSync import BaseSync
from Cerebrum.modules.ad2 import cli
from Cerebrum.utils import date as date_utils
from Cerebrum.utils import text_compat

logger = logging.getLogger(__name__)


def print_cerebrum_data(sync):
    """ Format and print data collected from Cerebrum. """
    attrs = sorted(sync.config['attributes'])
    for obj_name in sorted(sync.entities):
        obj = sync.entities[obj_name]
        logger.debug("obj: %s - %s", repr(obj), repr(obj.attributes))
        print(";".join((obj.ad_id, "OU", obj.ou)))
        for attr in attrs:
            value = obj.attributes.get(attr, "<Not Set>")
            fields = (obj.ad_id, attr, value)
            print(";".join(text_compat.to_text(f) for f in fields))


def _get_proc_status():
    """ Get process status from /proc/. """
    # TODO: Should probably use /proc/self/stat for this?
    with io.open("/proc/self/status", mode="r",
                 encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                field, value = line.split(":", 1)
            except Exception:
                continue
            yield (field.strip(), value.strip())


def dump_mem_usage():
    """ Print memory usage. """
    proc_status = dict(_get_proc_status())
    vm_peak = proc_status.get("VmPeak")
    if vm_peak:
        size, unit = vm_peak.split()
        size = int(size)
        if size > 1024:
            if unit == 'kB':
                size = size // 1024
                unit = 'MB'
        print("Memory peak:", str(size), str(unit))


def get_sync_class(preset, bases):
    """
    Get sync class from 'sync_class' setting or argument.

    :param str preset: Name of a sync preset in adconf.SYNCS
    :param list bases: A list of mixins to use (from --sync-class)
    :returns type: sync class to use
    """
    sync_class = BaseSync.get_class(classes=bases or [], sync_type=preset)
    pretty_mro = ", ".join(repr(c) for c in type.mro(sync_class))
    logger.debug("Using sync classes: %s", pretty_mro)
    return sync_class


def kv_pair(value):
    """
    Split a key-value argument.

    :param str value: a pair value ("key=value")
    :returns tuple: ("key", "value")
    """
    return value.split('=', 1)


def main(argv=None):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            """
            Run a sync with Active Directory.
            """
        ).lstrip(),
    )

    # Add basic winrm/powershell options
    get_preset = cli.add_sync_subparser(parser)

    #
    # Sync options
    #
    sync_group = parser.add_argument_group(
        "Sync configuration",
        textwrap.dedent(
            """
            AD sync specific options.  Sync settings are mainly fetched from
            the preset selected by the --type option.  Other options can be
            used to override settings from the selected preset.

            Available presets are defined in `adconf.SYNCS`.
            """
        ).lstrip(),
    )
    sync_group.add_argument(
        "--add-subset",
        action="append",
        dest="subset",
        help=textwrap.dedent(
            """
            Limit sync to ad objects with ad-id %(metavar)s.

            The 'subset' setting limits the sync to a list of ad objects.  This
            option *adds* objects to the subset list.
            """
        ).lstrip(),
        metavar="ID",
    )
    quick_mutex = sync_group.add_mutually_exclusive_group()
    quick_mutex.add_argument(
        "--quick",
        dest="quicksync_key",
        help=textwrap.dedent(
            """
            Run a quicksync (for a sync-preset with quicksync settings).

            This will process all previously unprocessed changes using the
            change-handler key %(metavar)s.  Note that each sync must have its
            own change-handler key.
            """
        ),
        metavar="KEY",
    )
    quick_mutex.add_argument(
        "--change-id",
        action="append",
        type=int,
        dest="quicksync_ids",
        help=textwrap.dedent(
            """
            Run a quicksync for the given change record.  %(metavar)s must be a
            valid changelog id.  This option can be repeated to process
            multiple change records.
            """
        ).lstrip(),
        metavar="ID",
    )
    sync_group.add_argument(
        "--sync-class",
        action="append",
        dest="sync_classes",
        help=textwrap.dedent(
            """
            Override 'sync_class' setting.

            This option can be repeated to create a sync class with mixins.
            """
        ).lstrip(),
        metavar="CLS",
    )
    sync_group.add_argument(
        "--set",
        action="append",
        type=kv_pair,
        dest="overrides",
        help=textwrap.dedent(
            """
            Override any setting.

            Generally only works for string settings.  Note that values aren't
            validated, so invalid values may break the sync.
            """
        ).lstrip(),
        metavar="KEY=VALUE",
    )

    #
    # Debug options
    #
    debug_group = parser.add_argument_group(
        "Debug and development",
        textwrap.dedent(
            """
            Various options for debugging in a dev environment.

            Run a dry-run sync (prevent changes) and store current ad
            state for the mock client:

                sync --type <preset> --dryrun --store-debug-state state.json

            Run a mock sync (compare cerebrum with mock-state and print
            changes):

                sync --type <preset> --mock --load-debug-state state.json

            Dump the current cerebrum state as `ad-id;ad-attr;ad-value` lines:

                sync --type <preset> --dump-cerebrum-data
            """
        ).lstrip(),
    )
    debug_group.add_argument(
        "-d", "--dryrun",
        action="store_true",
        help="Do not write any changes to AD",
    )
    debug_group.add_argument(
        "--debug",
        action="store_true",
        help="Print memory debug information after sync",
    )
    debug_group.add_argument(
        "--dump-cerebrum-data",
        action="store_true",
        help=textwrap.dedent(
            """
            Fetch and print the cerebrum-data that should be in AD.
            """
        ).lstrip(),
    )
    debug_group.add_argument(
        "-m", "--mock",
        action="store_true",
        help=textwrap.dedent(
            """
            Use a mock client rather than connect to AD.  The sync assumes AD
            is empty unless you load a state file with --load-mock-state.
            """
        ).lstrip(),
    )
    debug_group.add_argument(
        "-n", "--store-mock-state",
        help=textwrap.dedent(
            """
            Store active directory state as JSON in %(metavar)s.  This is
            usually done in a regular (or dryrun) sync, without --mock.
            """
        ).lstrip(),
        metavar="FILE",
    )
    debug_group.add_argument(
        "-l", "--load-mock-state",
        help="""
          Load a mock state state from JSON file %(metavar)s.  This is used
          with --mock to test the sync without an AD connection.  Generate a
          %(metavar)s with --store-mock-state.
        """,
        metavar="FILE",
    )

    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(argv)
    Cerebrum.logutils.autoconf("ad_sync", args)

    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    #
    # Validate arguments and build configuration
    #
    configuration = get_preset(adconf.SYNCS, args, dryrun=args.dryrun)
    preset_name = configuration['sync_type']

    # Apply override options
    overrides = dict(args.overrides or {})
    if overrides:
        configuration.update(overrides)
        logger.info("Preset overrides: %s",
                    ", ".join("%s=%s" % (k, overrides[k])
                              for k in sorted(overrides)))

    # Apply --add-subset options
    if args.subset:
        subset = list(configuration.get('subset', []))
        subset.extend(args.subset)
        configuration['subset'] = subset
    if configuration.get("subset"):
        logger.info("Limit sync to subset: %s", repr(configuration['subset']))

    # Apply --mock option
    configuration['mock'] = args.mock
    logger.info("Sync dryrun: %s", repr(configuration.get("dryrun", False)))
    logger.info("Sync mock: %s", repr(configuration.get("mock", False)))

    sync_class = get_sync_class(preset_name, args.sync_classes)

    #
    # Start sync
    #

    db = Factory.get('Database')(client_encoding='UTF-8')
    db.cl_init(change_program="ad_sync")
    sync = sync_class(db=db, logger=logger.getChild('sync'))
    sync.configure(configuration)

    logger.info("Running sync with preset: %s", preset_name)
    start = date_utils.now()

    if args.dump_cerebrum_data:
        logger.info("Only dumping Cerebrum data")
        sync.fetch_cerebrum_data()
        sync.calculate_ad_values()
        sync.server.close()
        print_cerebrum_data(sync)
        raise SystemExit()

    try:
        if args.load_mock_state:
            logger.info("Loading server state from %s", args.store_mock_state)
            sync.server._load_state(args.load_mock_state)

        if args.quicksync_ids:
            logger.info("Running quicksync for selected changes")
            sync.quicksync(change_ids=args.quicksync_ids)
        elif args.quicksync_key:
            logger.info("Running quicksync using key: %s", args.quicksync_key)
            sync.quicksync(changekey=args.quicksync_key)
        else:
            logger.info("Running fullsync")
            sync.fullsync()

        if args.store_mock_state:
            logger.info("Storing server state as %s", args.store_mock_state)
            sync.server._store_state(args.store_mock_state)
    finally:
        try:
            sync.server.close()
        except Exception:
            # It's probably already closed
            pass

    runtime = date_utils.now() - start
    logger.info("Sync %s done in %s", preset_name, runtime)

    if args.debug:
        dump_mem_usage()

    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()

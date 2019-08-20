#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2019 University of Oslo, Norway
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
""" Fix missing or incorrect sqlmodule versions in the Cerebrum database. """
import argparse
import logging

import Cerebrum.Errors
import Cerebrum.Metainfo
import Cerebrum.database
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils import argutils

logger = logging.getLogger(__name__)


def get_meta_version(db, crb_module):
    sqlname = 'sqlmodule_' + crb_module
    meta = Cerebrum.Metainfo.Metainfo(db)
    try:
        version = meta.get_metainfo(sqlname)
        logger.debug('database module=%r version=%r', sqlname, version)
    except Cerebrum.Errors.NotFoundError:
        version = None
        logger.debug('database module=%r no version', sqlname)
    return version


def set_meta_version(db, crb_module, version):
    sqlname = 'sqlmodule_' + crb_module
    meta = Cerebrum.Metainfo.Metainfo(db)
    meta.set_metainfo(sqlname, version)
    logger.info('database module=%r set to version=%r', sqlname, version)


def has_table(db, table):
    """
    Check if table exists.

    Note: This function causes a db.rollback()!
    """
    try:
        db.query(
            """
            select null as foo from [:table schema=cerebrum name=%s]
            """ % (table, ))
        present = True
    except Cerebrum.database.ProgrammingError as e:
        msg = str(e).split('\n')[0]
        logger.debug('Unable to select from %r (%s)', table, msg)
        present = False
    logger.info('Table %r present=%r', table, present)
    db.rollback()
    return present


def fix_version(db, name, version, table, force=False):
    """
    Note: This method will cause a db.rollback()
    """
    meta_version = get_meta_version(db, name)
    should_abort = False

    if not has_table(db, table):
        logger.warn('module=%r, table=%r missing', name, table)
        should_abort = True

    if meta_version is not None:
        logger.warn('module %r, meta version=%r is set', name, meta_version)
        should_abort = True

    if should_abort:
        if force:
            logger.warn('Forcing module=%r to version=%r', name, version)
        else:
            logger.error('Checks failed, aborting')
            return

    set_meta_version(db, name, version)


parser = argparse.ArgumentParser(
    description=__doc__,
)
modargs = parser.add_argument_group('module to fix')
modargs.add_argument(
    'module_name',
    help='sqlmodule to fix (e.g. disk_quota)',
    metavar='NAME',
)
modargs.add_argument(
    'version',
    help='Set sqlmodule version to %(metavar)s',
    metavar='VER',
)
modargs.add_argument(
    'table',
    help="A table that the sqlmodule inserts",
    metavar="TABLE",
)
modargs.add_argument(
    '-f', '--force',
    action='store_true',
    default=False,
    help='Set version even if table exists or version already present',
)
argutils.add_commit_args(parser, default=False)
Cerebrum.logutils.options.install_subparser(parser)


def main(inargs=None):
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('tee', args)
    db = Factory.get('Database')()
    db.cl_init(change_program=parser.prog)
    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)

    fix_version(db, args.module_name, args.version, args.table,
                force=args.force)

    if args.commit:
        logger.info('Commiting changes')
        db.commit()
    else:
        logger.info('Rolling back changes')
        db.rollback()

    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()

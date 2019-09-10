#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2012-2017 University of Oslo, Norway
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
"""
Script for updating the Operation Sets (OpSet) with its correct operations,
which are defined in opset_config (usually located in the same place as
cereconf). Please run in dryrun first, just to check that the changes are
okay.

The script goes through all OpSets in the database and compares them with the
config settings. New OpSets are created, and operations are added/removed from
the OpSets, according to the settings.

Please note that the operations itself have to be defined as Cerebrum
Constants (Cerebrum.modules.bofhd.utils).

TBD: What should be done with OpSets that exists in cerebrum, but not in this
script? Should they be removed?

TODO: add option for listing out all defined OpSets and their settings from
the database.

All changes are logged as INFO, while the rest is only DEBUG. This is to make
changes easier to spot.
"""
import argparse
import os
import sys
import six

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.auth import BofhdAuthOpSet, BofhdAuthRole


logger = Factory.get_logger("tee")


class OpsetConfigError(ValueError):
    pass


def convert_opsets(db, opsets):
    """ Changes all granted opsets from `opsets.convert_mapping`.

    For each mapped opset (old_opset -> new_opset) in `convert_mapping`, any
    granted access to the old_opset is changed to the new_opset.

    This is needed when existing opsets are refactored (e.g. split, combined
    or just renamed).

    """
    logger.debug('Convert existing opsets to new ones')

    convert_mapping = getattr(opsets, 'convert_mapping', dict())
    if not convert_mapping:
        raise OpsetConfigError("No opset mappings defined in convert_mapping!")

    baos = BofhdAuthOpSet(db)
    name2id = {}
    for name in convert_mapping.keys():
        baos.clear()
        baos.find_by_name(name)
        name2id[name] = int(baos.op_set_id)
        if not convert_mapping[name]:
            continue
        baos.clear()
        baos.find_by_name(convert_mapping[name])
        name2id[convert_mapping[name]] = int(baos.op_set_id)

    for src, target in convert_mapping.items():
        if not target:
            continue
        logger.info('Converting opset: %s -> %s', src, target)
        db.execute(
            """ UPDATE [:table schema=cerebrum name=auth_role]
            SET op_set_id=:new_id
            WHERE op_set_id=:old_id""",
            {'old_id': name2id[src],
             'new_id': name2id[target]})


def fix_opset(db, name, contents):
    """ Update a single opset.

    Creates the opset name if it doesn't exist, and then syncs the
    operations/permissions in `contents` to the Cerebrum database.

    """
    logger.debug('Checking opset %s' % name)
    co = Factory.get('Constants')(db)
    baos = BofhdAuthOpSet(db)
    baos.clear()
    try:
        baos.find_by_name(name)
    except Errors.NotFoundError:
        baos.populate(name)
        baos.write_db()
        logger.info('OpSet %s unknown, created it', name)
    current_operations = dict([(int(row['op_code']), int(row['op_id']))
                               for row in baos.list_operations()])
    for k in contents.keys():
        op_code = co.AuthRoleOp(k)
        try:
            int(op_code)
        except Errors.NotFoundError:
            logger.error("Operation %s not defined" % k)
            continue
        current_op_id = current_operations.get(int(op_code), None)
        if current_op_id is None:
            current_op_id = baos.add_operation(op_code)
            logger.info('OpSet %s got new operation %s', name, k)
        else:
            # already there
            del current_operations[int(op_code)]
        current_attrs = [row['attr'] for row in
                         baos.list_operation_attrs(current_op_id)]
        for a in contents[k].get('attrs', []):
            if a not in current_attrs:
                baos.add_op_attrs(current_op_id, a)
                logger.info("Add attr for %s:%s: %s", name, k, a)
            else:
                current_attrs.remove(a)
        for a in current_attrs:
            baos.del_op_attrs(current_op_id, a)
            logger.info("Remove attr for %s:%s: %s", name, k, a)

    for op in current_operations:
        # TBD: In theory this should be op_id, should
        # the DB have a unique constraint?
        baos.del_operation(op, current_operations[op])
        logger.info('OpSet %s had unwanted operation %s, removed it',
                    name, co.AuthRoleOp(op))
    baos.write_db()


def import_opsets(db, opsets):
    """ Import or update opsets from ``opsets.operation_sets`.

    Iterates through the opset items definded in the `operation_sets` dict.
    Each opset is updated using `fix_opset`.
    """

    operation_sets = getattr(opsets, 'operation_sets', dict())
    if not operation_sets:
        raise OpsetConfigError("No opsets defined in operation_sets!")

    for k, v in operation_sets.items():
        fix_opset(db, k, v)


def clean_opsets(db, opsets):
    """ Remove opsets not defined in `opsets.operation_sets`. """
    operation_sets = getattr(opsets, 'operation_sets', dict())
    if not operation_sets:
        raise OpsetConfigError("No opsets defined in operation_sets!")

    co = Factory.get('Constants')(db)
    baos = BofhdAuthOpSet(db)
    bar = BofhdAuthRole(db)
    for op_set_id, name in baos.list():
        if name not in operation_sets.keys():
            logger.info('Opset %s is no longer defined', name)
            baos.clear()
            baos.find(op_set_id)
            for op_code, op_id, _ in baos.list_operations():
                logger.info(
                    'Deleting operation for opset %s: op_code=%s op_id=%s',
                    baos.name, six.text_type(co.AuthRoleOp(op_code)), op_id)
                baos.del_operation(op_code, op_id)

            for role in bar.list(op_set_id=op_set_id):
                logger.info('Revoking %s for %s on %s',
                            baos.name, role['entity_id'], role['op_target_id'])
                bar.revoke_auth(**role)
            logger.info('Deleting opset %s', name)
            baos.delete()


def get_opset_config(filename=None):
    """ Load an `opset_config` module.

    :param str filename:
        A python file to load as the opset_config module.
        If `None`, we just `import opset_config`. This is the default.

    :return Module:
        Returns the imported opset_config module.
    """
    if filename is None:
        import opset_config
    else:
        import imp
        opset_config = imp.load_source('opset_config', filename)

    if opset_config and 'opset_config' not in sys.modules:
        sys.modules['opset_config'] = opset_config
    return opset_config


def make_parser():
    parser = argparse.ArgumentParser(
        description="Update opsets in Cerebrum database")

    parser.add_argument(
        '--commit',
        dest='commit',
        action='store_true',
        default=False,
        help="Commit changes to the database (default: %(default)s)")
    parser.add_argument(
        '--config',
        metavar="FILE",
        help=("Path to the opset_config config module. Imports 'opset_config'"
              " from PYTHONPATH by default."))

    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        '--convert',
        dest='action',
        action='store_const',
        const=convert_opsets,
        help="Convert old opset role entries to new op_set_id")
    action.add_argument(
        '--import',
        dest='action',
        action='store_const',
        const=import_opsets,
        help="Import/update opset-definitions in database")
    action.add_argument(
        '--clean',
        dest='action',
        action='store_const',
        const=clean_opsets,
        help=("Remove opsets (and associated operations/roles) "
              "not defined in config"))

    return parser


def main(args=None):
    parser = make_parser()
    args = parser.parse_args(args)

    logger.info("Starting permission_updates.py, {!r}".format(args))

    opset_config = get_opset_config(args.config)
    logger.info("Using opset_config '{!s}'".format(
        os.path.abspath(opset_config.__file__)))

    db = Factory.get('Database')()
    db.cl_init(change_program="permission_updates.py")

    try:
        args.action(db, opset_config)
    except OpsetConfigError as e:
        logger.error("Aborting, invalid config: {}".format(e))
        raise SystemExit(1)

    if args.commit:
        db.commit()
        logger.info('Changes committed')
    else:
        db.rollback()
        logger.info('Rolled back changes')

    logger.info("Done")


if __name__ == '__main__':
    main()

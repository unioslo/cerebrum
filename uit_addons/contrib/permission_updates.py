#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2012, 2014 University of Oslo, Norway
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
import getopt, sys

import cerebrum_path, cereconf
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.auth import BofhdAuthOpSet
from Cerebrum import Errors

db = Factory.get('Database')()
db.cl_init(change_program="permission_updates.py")
co = Factory.get('Constants')(db)
logger = Factory.get_logger("tee")

def usage(exitcode=0):
    print """Usage: %(filename)s [options]

    %(doc)s
    Updates the content of OpSets in the db by the new definitions in this
    script. The script is running in dryrun as default, to see through changes
    before committing.

    --import    Import/update opset-definitions in database
    --convert   Convert old opset role entries to new op_set_id

    --config    Specify what config file to use. Defaults to opset_config
                which should be in python's path.

    --commit    Commit changes

    --help      Show this message
    """ % {'filename': sys.argv[0],
           'doc': __doc__}
    sys.exit(exitcode)

def convert_existing_opsets(dryrun):
    """Convert the opsets in db with those defined in convert_mapping, by
    changing their names."""
    logger.debug('Convert existing opsets to new ones')
    baos = BofhdAuthOpSet(db)
    name2id = {}
    for name in opset_config.convert_mapping.keys():
        baos.clear()
        baos.find_by_name(name)
        name2id[name] = int(baos.op_set_id)
        if not opset_config.convert_mapping[name]:
            continue
        baos.clear()
        baos.find_by_name(opset_config.convert_mapping[name])
        name2id[opset_config.convert_mapping[name]] = int(baos.op_set_id)

    for src, target in opset_config.convert_mapping.items():
        if not target:
            continue
        logger.info('Converting opset: %s -> %s', src, target)
        db.execute("""
            UPDATE [:table schema=cerebrum name=auth_role]
            SET op_set_id=:new_id
            WHERE op_set_id=:old_id""", {
                'old_id': name2id[src], 'new_id': name2id[target]})
    if dryrun:
        db.rollback()
        logger.info('Rolled back changes')
    else:
        db.commit()
        logger.info('Changes committed')


def fix_opset(name, contents):
    """Fix an operation set by giving it the operations defined in operation_sets,
    and removing other operations that shouldn't be there. If the opset doesn't
    exist, it is first created."""
    logger.debug('Checking opset %s' % name)
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
        current_attrs = [row['attr']
                         for row in baos.list_operation_attrs(current_op_id)]
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
        #TBD: In theory this should be op_id, should
        # the DB have a unique constraint?
        baos.del_operation(op, current_operations[op])
        logger.info('OpSet %s had unwanted operation %s, removed it',
                    name, co.AuthRoleOp(op))
    baos.write_db()

def fix_opsets(dryrun, opsets):
    """Go fix all opsets defined in operation_sets, by sending them to
    fix_opset."""
    for k, v in opsets.operation_sets.items():
        fix_opset(k, v)
    if dryrun:
        db.rollback()
        logger.info('Rolled back changes')
    else:
        db.commit()
        logger.info('Changes committed')

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                'h',
               ['help',
                'commit',
                'import',
                'config=',
                'convert'])
    except getopt.GetoptError:
        usage(1)
    if not opts:
        print "No action given"
        usage(1)

    dryrun = True

    # First pick out the auxiliary options...
    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('--commit',):
            # ...most significantly with regards to --commit
            dryrun = False
        elif opt in ('--config',):
            raise Exception('Not implemented yet, can only use default for now')
    try:
        import opset_config
    except ImportError:
        print "No default opset_config found."
        sys.exit(2)
    if not opset_config.operation_sets:
        print "No operation sets defined. Abort"
        sys.exit(1)

    # Then do whatever it is we're supposed to actually be doing
    for opt, val in opts:
        if opt in ('--import',):
            fix_opsets(dryrun=dryrun, opsets=opset_config)
        elif opt in ('--convert',):
            convert_existing_opsets(dryrun=dryrun)

if __name__ == '__main__':
    main()

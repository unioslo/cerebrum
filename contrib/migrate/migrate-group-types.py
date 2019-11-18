#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
This script sets group_type for certain internal cerebrum groups.

The change is needed after upgrade to 0.9.21. The groups altered by this script
would have a group_type set by default in Cerebrum.
"""
from __future__ import print_function

import argparse
import logging

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Metainfo import Metainfo
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import add_commit_args

try:
    import guestconfig
except ImportError:
    guestconfig = object()


logger = logging.getLogger(__name__)


def has_module(db, module):
    meta = Metainfo(db)
    try:
        meta.get_metainfo(module)
    except Errors.NotFoundError:
        return False
    else:
        return True


def update_virtualgroups(db):
    co = Factory.get("Constants")(db)
    binds = {
        'group_type_virtual': int(co.group_type_virtual),
        'vg_normal_group': int(co.vg_normal_group),
    }
    stmt = """
      UPDATE
        [:table schema=cerebrum name=group_info]
      SET
        group_type = :group_type_virtual
      WHERE
        group_id IN (
          SELECT
            group_id
          FROM
            [:table schema=cerebrum name=virtual_group_info]
          WHERE
            virtual_group_type != :vg_normal_group
        )
    """
    db.execute(stmt, binds)
    return db.rowcount


def _get_internal_groups(db):
    gr = Factory.get("Group")(db)
    names = set(
        getattr(cereconf, attr) for attr in
        ('INITIAL_GROUPNAME',
         'BOFHD_SUPERUSER_GROUP',
         # WebID only:
         'BOFHD_SUDOERS_GROUP',)
        if hasattr(cereconf, attr))

    # uio and uia has a guestconfig.GUEST_OWNER_GROUP:
    names.update(
        getattr(guestconfig, attr)
        for attr in ('GUEST_OWNER_GROUP',)
        if hasattr(guestconfig, attr))

    # Get group_ids
    for name in names:
        gr.clear()
        try:
            gr.find_by_name(name)
        except Errors.NotFoundError:
            logger.debug("skipping group_name=%r", name)
            continue
        else:
            logger.debug("including group_name=%r (%d)", name, gr.entity_id)
            yield gr.entity_id


def set_group_type(db, group_type, group_id):
    binds = {
        'group_type': int(group_type),
        'group_id': int(group_id),
    }
    stmt = """
      UPDATE
        group_info
      SET
        group_type = :group_type
      WHERE
        group_id = :group_id
    """
    db.execute(stmt, binds)
    return db.rowcount


def update_internal_groups(db):
    """ Get mappings for the thing. """
    co = Factory.get("Constants")(db)
    count = 0
    for count, group_id in enumerate(_get_internal_groups(db), 1):
        set_group_type(db, co.group_type_internal, group_id)
    return count


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Set initial group_type values for known groups",
    )
    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('tee', args)

    logger.info('Start %s', parser.prog)
    logger.debug('args: %r', args)

    db = Factory.get('Database')()

    logger.info("Setting group type for internal groups")
    count = update_internal_groups(db)
    logger.info("Set group type for %d groups", count)

    if has_module(db, 'sqlmodule_virtual_group'):
        logger.info("Setting group type for 'sqlmodule_virtual_group'")
        count = update_virtualgroups(db)
        logger.info("Set group type for %d groups", count)

    if args.commit:
        logger.info('Commiting changes')
        db.commit()
    else:
        logger.info('Rolling back changes')
        db.rollback()
    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()

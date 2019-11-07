#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2009 University of Oslo, Norway
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

"""Record initial permission sets for VirtHome.

This script loads an initial set of permissions for VirtHome. We need to
establish opsets for bofhd commands. uiocerebrum/hacks/perm_oppdatering.py
does something similar for UiO.

This script is meant to run ONLY ONCE (during the setup stage, say, about
right after makedb.py completes)

This script assumes that the database has already been created and populated
with constants and INITIAL_ACCOUNTNAME/INITIAL_GROUPNAME. Here we just
insert the VirtHome-specific tidbits.

Stuff that needs to be done:

* create a superuser group (cereconf.BOFHD_SUPERUSER_GROUP)
* stuff cereconf.INITIAL_ACCOUNTNAME into superuser group (this way we are
  guaranteed 1 superuser, which may come in handy when operating via bofhd)
* create a 'webapp' user
* create 'group-owner' opset (with group_delete, group_modify)
* create 'group-moderator' opset (with group_modify)
* create 'sudoers' opset
* stuff 'webapp'-user into <sudoers>
"""

import getopt
import sys

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules.bofhd.auth import BofhdAuthOpSet
from Cerebrum.Account import Account
from Cerebrum.Group import Group





def get_entity(ident, entity_type, db):
    """Find a group, given its identity.

    This is much like what _get_group()/_get_account() in bofhd does... except simpler
    """

    const = Factory.get("Constants")()
    if entity_type in ('group', const.entity_group):
        obj = Factory.get("Group")(db)
    elif entity_type in ('account', const.entity_account):
        obj = Account(db)

    finder = None
    if isinstance(ident, str):
        if ident.isdigit():
            finder = obj.find
        else:
            finder = obj.find_by_name
    elif isinstance(ident, int):
        finder = obj.find
    else:
        assert False

    finder(ident)
    return obj
# end group
    


def get_system_account(db):
    return get_entity(cereconf.INITIAL_ACCOUNTNAME, 'account', db)
# end get_system_account



def get_system_group(db):
    return get_entity(cereconf.INITIAL_GROUPNAME, 'group', db)
# end get_system_group



def create_group(gname, db):
    """Helper function to create some system critical groups in VH.

    gname will be owned by the system account (cereconf.INITIAL_ACCOUNTNAME)
    """

    group = Group(db)
    constants = Factory.get("Constants")()
    try:
        group.find_by_name(gname)
        logger.debug("Found group with name=%s, id=%s",
                     group.group_name, group.entity_id)
        return
    except Errors.NotFoundError:
        # They are all owned by system account...
        account = get_system_account(db)
        group.populate(account.entity_id,
                       constants.group_visibility_all,
                       gname)
        group.write_db()
        logger.debug("Created group name=%s, id=%s",
                     group.group_name, group.entity_id)
# end create_group    



def create_user(uname, db):
    """Helper function to create some system users we need in VH.

    uname will be owned by the system group andit will have been created by
    the system account.
    """

    account = Account(db)
    constants = Factory.get("Constants")()
    try:
        account.find_by_name(uname)
        logger.debug("Found account with name=%s, id=%s",
                     account.account_name, account.entity_id)
        return
    except Errors.NotFoundError:
        sys_group = get_system_group(db)
        sys_account = get_system_account(db)
        account.populate(uname,
                         constants.entity_group,       # owned by 
                         sys_group.entity_id,          # ... system group
                         constants.account_program, 
                         sys_account.entity_id, # created by system account
                         None)                  # no expire (duh!)
        account.write_db()
        logger.debug("Created account uname=%s, id=%s",
                     account.account_name, account.entity_id)
        logger.debug("Don't forget to set a password on uname=%s",
                     account.account_name)
# end create_user


def assert_required_permissions_exist(auth_ops):
    """Make sure the necessary auth ops are in the db.

    """
    const = Factory.get("Constants")()
    for auth_op in auth_ops:
        assert const.human2constant(auth_op, const.AuthRoleOp) is not None, \
               "auth_op=%s does not map to anything" % (auth_op,)
# end assert_required_permissions_exist 



def create_required_opsets(operation_sets, db):
    """Make sure the necessary auth op sets are in the db.

    If such an opset already exists, force the specified set of auth_operation. 
    """

    const = Factory.get("Constants")()
    baos = BofhdAuthOpSet(db)
    for auth_opset in operation_sets:
        baos.clear()
        try:
            baos.find_by_name(auth_opset)
        except Errors.NotFoundError:
            baos.populate(auth_opset)
            baos.write_db()

        requested_opcodes = set(int(const.human2constant(x, const.AuthRoleOp))
                                for x in operation_sets[auth_opset])
        existing_opcodes = set(int(row["op_code"])
                               for row in baos.list_operations())
        for op_code in requested_opcodes.difference(existing_opcodes):
            logger.debug("Adding operation opcode=%s (code_str=%s) to opset %s "
                         "(opset_id=%s)",
                         op_code, str(const.AuthRoleOp(op_code)),
                         baos.name, baos.op_set_id)
            baos.add_operation(op_code)
        for op_code in existing_opcodes.difference(requested_opcodes):
            logger.debug("Deleting operation opcode=%s (code_str=%s) from opset %s "
                         "(opset_id=%s)",
                         op_code, str(const.AuthRoleOp(op_code)),
                         baos.name, baos.op_set_id)
            baos.del_operation(op_code)
        baos.write_db()
# end create_required_opsets



def create_permissions(superuser_group, sudoers_group, webapp_user, db):
    """Create basic VH opsets, auth_roles, assign a few basic permissions.

    This is the bare minimum we need to do. The constants (for auth_ops and
    the like) must have been inserted into the db before this function is
    called.

    @param superuser_group:
      Group name for group the members of which are considered
      superusers. (is_superuser() tests for membership in this group).

    @param sudoers_group:
      Group name for group the members of which are allowed to change identity
      to another user. (this group is granted sudoers-opset).

    @param webapp_user:
      Username for php-application 'user'. This user needs special permissions
      in VirtHome and it must exist in the database before the web interface
      can be used for anything.

    @db: DB proxy.
    """

    #
    # We need to assert all these exist
    elementary_auth_ops = ('auth_alter_group_membership', # add/remove members
                           'auth_create_group',           # create/delete groups
                           )
    #
    # 'group-owner'     owners of a VH group.
    # 'group-moderator' moderators of a VH group.
    operation_sets = {
        'group-owner':     ('alter_group_memb',
                            'create_group',),
        'group-moderator': ('alter_group_memb',),
    }

    assert_required_permissions_exist(elementary_auth_ops)

    create_required_opsets(operation_sets, db)

    # 3) grant a few opsets to system groups.
    # bootstrap_account should automatically be superuser (then we'll have at
    # least one, making bofhd usable)
    account = get_system_account(db)
    group = get_entity(superuser_group, 'group', db)
    if not group.has_member(account.entity_id):
        group.add_member(account.entity_id)
        logger.debug("Added account %s (id=%s) to superuser group %s (id=%s)",
                     account.account_name, account.entity_id,
                     group.group_name, group.entity_id)
    else:
        logger.debug("Account %s (id=%s) is already a member of "
                     "superuser group %s (id=%s)",
                     account.account_name, account.entity_id,
                     group.group_name, group.entity_id)

    group = get_entity(sudoers_group, 'group', db)
    account = get_entity(webapp_user, 'account', db)
    if not group.has_member(account.entity_id):
        group.add_member(account.entity_id)
# end create_permissions


def normalize_name(name):
    return name.lower().strip()
# end normalize_name
    

def main(argv):
    global logger

    logger = Factory.get_logger("console")
    opts, junk = getopt.getopt(argv[1:],
                               "w:cps:",
                               ("webapp-user=",
                                "with-commit",
                                "permissions-only",
                                "sudoers-group=",))
    webapp_user = "webapp"
    sudoers_group = cereconf.BOFHD_SUDOERS_GROUP
    superuser_group = cereconf.BOFHD_SUPERUSER_GROUP
    with_commit = False
    permissions_only = False

    for option, value in opts:
        #
        # account name for the php front-end
        if option in ("-w", "--webapp-user",):
            webapp_user = normalize_name(value)
        #
        # do not create any entities -- just opsets and auth_roles.
        elif option in ("-p", "--permissions-only",):
            permissions_only = True
        #
        # whether we should commit the changes
        elif option in ("-c", "--with-commit",):
            with_commit = True
        #
        # group name for group of accounts capable of su-ing to different
        # users
        elif option in ("-s", "--sudoers-group",):
            sudoers_group = normalize_name(value)

    db = Factory.get("Database")()
    db.cl_init(change_program="assign_permissions")
    logger.debug("webapp-user='%s'; sudoers-group='%s'",
                 webapp_user, sudoers_group)
    
    if not permissions_only:
        #
        # Create system groups
        for group_name in (superuser_group, sudoers_group,):
            create_group(group_name, db)
        #
        # Create system users
        for username in (webapp_user,):
            create_user(username, db)

    create_permissions(superuser_group, sudoers_group, webapp_user, db)

    if with_commit:
        db.commit()
        logger.debug("Committed all changes")
    else:
        db.rollback()
        logger.debug("Rolled back all changes")
# end main
    


if __name__ == "__main__":
    main(sys.argv)

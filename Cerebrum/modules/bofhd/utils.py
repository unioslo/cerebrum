# -*- coding: iso-8859-1 -*-

# Copyright 2002, 2003 University of Oslo, Norway
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

import time
from Cerebrum import Constants
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum import Errors
import xmlrpclib

class _BofhdRequestOpCode(Constants._CerebrumCode):
    "Mappings stored in the auth_role_op_code table"
    _lookup_table = '[:table schema=cerebrum name=bofhd_request_code]'

class _AuthRoleOpCode(Constants._CerebrumCode):
    "Mappings stored in the auth_role_op_code table"
    _lookup_table = '[:table schema=cerebrum name=auth_op_code]'

class Constants(Constants.Constants):

    BofhdRequestOp = _BofhdRequestOpCode
    AuthRoleOp = _AuthRoleOpCode

    auth_add_disk = _AuthRoleOpCode('add_disks', 'add userdisks to hosts')
    auth_create_host = _AuthRoleOpCode('create_host',
                                       'Can add hosts for userdisks')
    auth_create_group = _AuthRoleOpCode('create_group',
                                        'Can create groups')
    auth_disk_quota_set = _AuthRoleOpCode('disk_quota_set', 'Can set disk qupta')
    auth_disk_quota_forver = _AuthRoleOpCode('disk_quota_forev',
                                             'Can set unlimited quota duration')
    auth_disk_quota_unlimited = _AuthRoleOpCode('disk_quota_unlim',
                                                'Can set unlimited quota')
    auth_disk_quota_show = _AuthRoleOpCode('disk_quota_show',
                                           'Can see disk quota')
    auth_view_studentinfo = _AuthRoleOpCode('view_studinfo',
                                            'Can view student info')
    auth_alter_printerquota = _AuthRoleOpCode('alter_printerquo', 'desc')
    auth_modify_spread = _AuthRoleOpCode('modify_spread', 'modify spread')
    auth_create_user = _AuthRoleOpCode('create_user', 'create user')
    auth_remove_user = _AuthRoleOpCode('remove_user', 'remove user')
    auth_view_history = _AuthRoleOpCode('view_history', 'view history')
    auth_set_password = _AuthRoleOpCode('set_password', 'desc')
    auth_set_gecos = _AuthRoleOpCode('set_gecos', 'Set persons gecos field')
    auth_move_from_disk = _AuthRoleOpCode('move_from_disk',
                                         'can move from disk')
    auth_move_to_disk = _AuthRoleOpCode('move_to_disk',
                                         'can move to disk')
    auth_alter_group_membership = _AuthRoleOpCode('alter_group_memb', 'desc')
    auth_email_forward_off = _AuthRoleOpCode('email_forw_off',
                                             "Disable user's forwards")
    auth_email_vacation_off = _AuthRoleOpCode('email_vac_off',
                                              "Disable user's vacation message")
    auth_email_migrate = _AuthRoleOpCode('email_migrate',
                                         "Move user's mailbox")
    auth_email_quota_set = _AuthRoleOpCode('email_quota_set',
                                           "Set quota on user's mailbox")
    auth_email_create = _AuthRoleOpCode('email_create',
                                        "Create e-mail addresses")
    auth_email_delete = _AuthRoleOpCode('email_delete',
                                        "Delete e-mail addresses")
    # These are values used as auth_op_target.target_type.  This table
    # doesn't use a code table to map into integers, so we can't use
    # the CerebrumCode framework.  TODO: redefine the database table
    # In the meantime, we define the valid code values as constant
    # strings here.
    auth_target_type_disk = "disk"
    auth_target_type_group = "group"
    auth_target_type_host = "host"
    auth_target_type_maildomain = "maildom"
    auth_target_type_ou = "ou"
    # These are wildcards, allowing access to _all_ objects of that type
    auth_target_type_global_group = "global_group"
    auth_target_type_global_host = "global_host" # also "disk"
    auth_target_type_global_maildomain = "global_maildom"
    auth_target_type_global_ou = "global_ou"

    bofh_move_user = _BofhdRequestOpCode('br_move_user', 'Move user (batch)')
    bofh_move_user_now = _BofhdRequestOpCode('br_move_user_now', 'Move user')
    bofh_move_student = _BofhdRequestOpCode('br_move_student', 'Move student')
    bofh_move_request = _BofhdRequestOpCode('br_move_request', 'Move request')
    bofh_move_give = _BofhdRequestOpCode('br_move_give', 'Give away user')
    bofh_delete_user = _BofhdRequestOpCode('br_delete_user', 'Delete user')
    bofh_quarantine_refresh = _BofhdRequestOpCode('br_quara_refresh',
                                                  'Refresh quarantine')
    
    # br_email_move stays in queue until delivery has stopped.
    # generate_mail_ldif.py will set the mailPause attribute based on
    # entries in the request queue

    # destination server is value in database, source server is passed
    # in destination_id (!) -- this way the fresh data is in the
    # database, and hence LDAP.  state_data is optionally a
    # request_id: wait if that request is in queue (typically a create
    # request).  a bofh_email_convert is inserted when done.
    bofh_email_move = _BofhdRequestOpCode('br_email_move',
                                          'Move user among e-mail servers')
    bofh_email_create = _BofhdRequestOpCode('br_email_create',
                                            'Create user mailboxes')
    # state_data is emailserver (entity_id):
    bofh_email_delete = _BofhdRequestOpCode('br_email_delete',
                                            'Delete all user mailboxes')
    bofh_email_hquota = _BofhdRequestOpCode('br_email_hquota',
                                            'Set e-mail hard quota')
    bofh_email_convert = _BofhdRequestOpCode('br_email_convert',
                                             'Convert user mail config')
    # entity_id is address_id of the official name of the mailing list
    # destination_id is address_id of the admin address
    bofh_mailman_create = _BofhdRequestOpCode('br_mm_create',
                                              'Create mailman list')
    # entity_id and destination_id as above
    # state_data is optional request_id for dependency
    bofh_mailman_add_admin = _BofhdRequestOpCode('br_mm_add_admin',
                                                 'Add admin to mailman list')
    # entity_id as above
    # since this has been deleted by the time process_bofhd_requests runs,
    # the name of the list is passed as a string in state_data as well.
    bofh_mailman_remove = _BofhdRequestOpCode('br_mm_remove',
                                              'Remove mailman list')

class BofhdRequests(object):
    def __init__(self, db, const, id=None):
        self._db = db
        self.co = const
        now = time.time()
        tmp = list(time.localtime(now))
        for i in range(-6,-1):
            tmp[i] = 0
        midnight = time.mktime(tmp)
        if now - midnight > 3600 * 22:
            self.batch_time = self._db.TimestampFromTicks(midnight + 3600 * (24+22))
        else:
            self.batch_time = self._db.TimestampFromTicks(midnight + 3600 * 22)
        self.now = self._db.TimestampFromTicks(time.time())

    def get_conflicts(self, op):
        """Returns a list of conflicting operation types.  op can be
        an integer or a constant."""

        # "None" means _no_ conflicts, there can even be several of
        # that op pending.  All other ops implicitly conflict with
        # themselves, so there can only be one of each op.
        c = self.co
        conflicts = {
            int(c.bofh_move_user):       [ c.bofh_move_student,
                                           c.bofh_move_user_now,
                                           c.bofh_move_request,
                                           c.bofh_delete_user ],
            int(c.bofh_move_student):    [ c.bofh_move_user,
                                           c.bofh_move_user_now,
                                           c.bofh_move_request,
                                           c.bofh_delete_user ],
            int(c.bofh_move_user_now):   [ c.bofh_move_student,
                                           c.bofh_move_user,
                                           c.bofh_move_request,
                                           c.bofh_delete_user ],
            int(c.bofh_move_request):    [ c.bofh_move_user,
                                           c.bofh_move_user_now,
                                           c.bofh_move_student,
                                           c.bofh_delete_user ],
            int(c.bofh_move_give):       None,
            int(c.bofh_delete_user):     [ c.bofh_move_user,
                                           c.bofh_move_user_now,
                                           c.bofh_move_student,
                                           c.bofh_email_create ],
            int(c.bofh_email_move):      [ c.bofh_delete_user ],
            int(c.bofh_email_create):    [ c.bofh_email_delete,
                                           c.bofh_delete_user ],
            int(c.bofh_email_delete):    [ c.bofh_email_create,
                                           c.bofh_email_move ],
            int(c.bofh_email_hquota):    [ c.bofh_email_delete ],
            int(c.bofh_email_convert):   [ c.bofh_email_delete ],
            int(c.bofh_mailman_create):  [ c.bofh_mailman_remove ],
            int(c.bofh_mailman_add_admin):  None,
            int(c.bofh_mailman_remove):  [ c.bofh_mailman_create,
                                           c.bofh_mailman_add_admin ],
            int(c.bofh_quarantine_refresh): None,
            }[int(op)]

        if conflicts is None:
            conflicts = []
        else:
            conflicts.append(op)
        # Make sure all elements in the returned list are integers
        return [int(c) for c in conflicts]

    def add_request(self, operator, when, op_code, entity_id,
                    destination_id, state_data=None):

        conflicts = self.get_conflicts(op_code)

        for r in self.get_requests(entity_id=entity_id):
            if int(r['operation']) in conflicts:
                raise CerebrumError, ("Conflicting request exists (%s)" %
                                      self.co.BofhdRequestOp(r['operation']).
                                      description)
        reqid = int(self._db.nextval('request_id_seq'))
        cols = {
            'requestee_id': operator,
            'run_at': when,
            'operation': int(op_code),
            'entity_id': entity_id,
            'destination_id': destination_id,
            'state_data': state_data,
            'request_id': reqid
            }
        
        self._db.execute("""
        INSERT INTO [:table schema=cerebrum name=bofhd_request] (%(tcols)s)
        VALUES (%(binds)s)""" % {
            'tcols': ", ".join(cols.keys()),
            'binds': ", ".join([":%s" % t for t in cols.keys()])},
                         cols)
        return reqid

    def delay_request(self, request_id, minutes=10):
        for r in self.get_requests(request_id):
            # Note: the semantics of time objects is DB driver
            # dependent, and not standardised in PEP 249.
            # PgSQL will convert to ticks when forced into int().
            t = int(r['run_at'])
            # don't use self.now, it's a DateTime object.
            now = time.time()
            if t < now:
                t = now
            when = self._db.TimestampFromTicks(t + minutes*60)
            self._db.execute("""
                UPDATE [:table schema=cerebrum name=bofhd_request]
                SET run_at=:when WHERE request_id=:id""",
                             {'when': when, 'id': request_id})
            return
        raise Errors.NotFoundError, "No such request %d" % request_id

    def delete_request(self, entity_id=None, request_id=None,
                       operator_id=None, operation=None):
        cols = {}
        if entity_id is not None:
            cols['entity_id'] = entity_id
        if request_id is not None:
            cols['request_id'] = request_id
        if operator_id is not None:
            cols['requestee_id'] = operator_id
        if operation is not None:
            cols['operation'] = int(operation)
        self._db.execute("""DELETE FROM [:table schema=cerebrum name=bofhd_request]
        WHERE %s""" % " AND ".join(["%s=:%s" % (x, x) for x in cols.keys()]), cols)

    def get_requests(self, request_id=None, operator_id=None, entity_id=None,
                     operation=None, destination_id=None, given=False):
        cols = {}
        if request_id is not None:
            cols['request_id'] = request_id
        if entity_id is not None:
            cols['entity_id'] = entity_id
        if operator_id is not None:
            cols['requestee_id'] = operator_id
        if operation is not None:
            cols['operation'] = int(operation)
        if destination_id is not None:
            cols['destination_id'] = int(destination_id)
        qry = """
        SELECT request_id, requestee_id, run_at, operation, entity_id,
               destination_id, state_data
        FROM [:table schema=cerebrum name=bofhd_request]
        WHERE """
        ret = self._db.query(qry + " AND ".join(
            ["%s=:%s" % (x, x) for x in cols.keys()]),
                             cols)
        if given:
            group = Factory.get('Group')(self._db)
            tmp = []
            # TODO: include_indirect_members=1 when Group supports it
            for r in group.list_groups_with_entity(operator_id):
                tmp.append(str(r['group_id']))
            extra_where = ""
            if len(tmp) > 0:
                extra_where = "AND destination_id IN (%s)" % ", ".join(tmp)
            ret.extend(self._db.query(qry + "operation=:op %s" % extra_where,
                                      {'op': int(self.co.bofh_move_give)}))
        return ret

# arch-tag: d6650fa6-6a9b-459f-be7e-80c9e6cbba52

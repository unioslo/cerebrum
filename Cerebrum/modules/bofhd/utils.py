# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway

import time
from Cerebrum import Constants
from Cerebrum import Group

class _BofhdRequestOpCode(Constants._CerebrumCode):
    "Mappings stored in the auth_role_op_code table"
    _lookup_table = '[:table schema=cerebrum name=bofhd_request_code]'

class _AuthRoleOpCode(Constants._CerebrumCode):
    "Mappings stored in the auth_role_op_code table"
    _lookup_table = '[:table schema=cerebrum name=auth_op_code]'

class Constants(Constants.Constants):
    auth_alter_printerquota = _AuthRoleOpCode('alter_printerquo', 'desc')
    auth_modify_spread = _AuthRoleOpCode('modify_spread', 'modify spread')
    auth_create_user = _AuthRoleOpCode('create_user', 'create user')
    auth_remove_user = _AuthRoleOpCode('remove_user', 'remove user')
    auth_set_password = _AuthRoleOpCode('set_password', 'desc')
    auth_move_from_disk = _AuthRoleOpCode('move_from_disk',
                                         'can move from disk')
    auth_move_to_disk = _AuthRoleOpCode('move_to_disk',
                                         'can move to disk')
    auth_alter_group_membership = _AuthRoleOpCode('alter_group_memb', 'desc')

    bofh_move_user = _BofhdRequestOpCode('br_move_user', 'Move user')
    bofh_move_student = _BofhdRequestOpCode('br_move_student', 'Move student')
    bofh_move_request = _BofhdRequestOpCode('br_move_request', 'Move request')
    bofh_move_give = _BofhdRequestOpCode('br_move_give', 'Give away user')
    bofh_delete_user = _BofhdRequestOpCode('br_delete_user', 'Delete user')
    
    # br_email_will_move is left in queue until delivery has stopped.
    # then a new request, br_email_move is inserted, and left in queue
    # until the operation has completed.
    # if either type of request is in the queue, generate_mail_ldif.py
    # will set the mailPause attribute for that user.

    # state_data:
    #    source_server
    #    dest_server
    #    depend_req (request_id: wait while it's in queue)
    bofh_email_will_move = _BofhdRequestOpCode('br_email_will_move',
                                               'Will move user e-mail')
    # same as bofh_email_will_move
    # will insert a bofh_email_convert when done
    bofh_email_move = _BofhdRequestOpCode('br_email_move',
                                          'Move user among e-mail servers')
    # state_data:
    #    hquota (int: quota in mebibytes)
    bofh_email_create = _BofhdRequestOpCode('br_email_create',
                                            'Create user mailboxes')
    # state_data:
    #    imaphost (string: hostname)
    bofh_email_delete = _BofhdRequestOpCode('br_email_delete',
                                            'Delete all user mailboxes')
    # state_data:
    #    hquota (int: quota in mebibytes)
    bofh_email_hquota = _BofhdRequestOpCode('br_email_hquota',
                                            'Set e-mail hard quota')
    # state_data:
    #    (nothing)
    bofh_email_convert = _BofhdRequestOpCode('br_email_convert',
                                             'Convert user mail config')

class BofhdRequests(object):
    def __init__(self, db, const, id=None):
        self._db = db
        self.const = const
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

    def add_request(self, operator, when, op_code, entity_id,
                    destination_id, state_data=None):
        # bofh_move_give is the only place where multiple entries are legal
        if op_code != self.const.bofh_move_give:
            rows = self.get_requests(entity_id=entity_id)
            for r in rows:
                if r['operation'] != self.const.bofh_move_give:
                    raise CerebrumError, "Conflicting request exists"

        cols = {
            'requestee_id': operator,
            'run_at': when,
            'operation': int(op_code),
            'entity_id': entity_id,
            'destination_id': destination_id,
            'state_data': state_data,
            'request_id': int(self._db.nextval('request_id_seq'))
            }
        
        self._db.execute("""
        INSERT INTO [:table schema=cerebrum name=bofhd_request] (%(tcols)s)
        VALUES (%(binds)s)""" % {
            'tcols': ", ".join(cols.keys()),
            'binds': ", ".join([":%s" % t for t in cols.keys()])},
                         cols)

    def delay_request(self, request_id, seconds=600):
	cols = self.get_requests(request_id)
	when = cols['run_at'] + seconds;
	self._db.execute("""
		UPDATE [:table schema=cerebrum name=bofhd_request]
		SET run_at = %d
		WHERE request_id = %d
		""" % (when, request_id))

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

    def get_requests(self, request_id=None, operator_id=None, entity_id=None, operation=None,
                     given=False):
        cols = {}
        if request_id is not None:
            cols['request_id'] = request_id
        if entity_id is not None:
            cols['entity_id'] = entity_id
        if operator_id is not None:
            cols['requestee_id'] = operator_id
        if operation is not None:
            cols['operation'] = int(operation)
        qry = """SELECT request_id, requestee_id, run_at, operation, entity_id, destination_id, state_data
        FROM [:table schema=cerebrum name=bofhd_request]"""
        ret = self._db.query("%s WHERE %s" % (qry, " AND ".join(["%s=:%s" % (x, x) for x in cols.keys()])), cols)
        if given:
            group = Group.Group(self._db)
            tmp = []
            # TODO: include_indirect_members=1 when Group supports it
            for r in group.list_groups_with_entity(operator_id):
                tmp.append(str(r['group_id']))
            extra_where = ""
            if len(tmp) > 0:
                extra_where = "AND destination_id IN (%s)" % ", ".join(tmp)
            ret.extend(self._db.query("%s WHERE operation=:op %s" % (
                qry, extra_where), {'op': int(self.const.bofh_move_give)}))
        return ret
    

# -*- coding: utf-8 -*-
#
# Copyright 2004-2020 University of Oslo, Norway
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
TODO: This code seems obsolete.

Old documentation hints that this code was obsolete back in 2007.  See
<cerebrum-config>/doc/intern/felles/prod-branch-filstruktur.rst
"""
import cereconf

from Cerebrum.Utils import argument_to_sql
from Cerebrum.modules.bofhd import auth


class OperationSet(auth.BofhdAuthOpSet):
    """A set of auth operations.

    Methods for updating auth_operation_set, auth_operation, auth_op_attrs and
    auth_op_code wich specifies what operations may be performed.
    """

    def del_operation(self, op_code):
        """Remove a operation from the operation set.  """
        # TODO: This method differs from BofhdAuthOpSet for some reason
        self.execute(
            """
              DELETE FROM [:table schema=cerebrum name=auth_operation]
              WHERE
                op_code=:op_code AND
                op_set_id=:op_set_id
            """,
            {
                'op_code': int(op_code),
                'op_set_id': self.op_set_id,
            })

    def add_op_code(self, code_str, description=""):
        """Add an operation code.

        Adds an operation code_str and its description into the database.
        """
        op_code = int(self.nextval('code_seq'))
        self.execute(
            """
              INSERT INTO [:table schema=cerebrum name=auth_op_code]
                (code, code_str, description)
              VALUES
                (:code, :code_str, :description)
            """,
            {
                'code': op_code,
                'code_str': code_str,
                'description': description,
            })
        return op_code

    def del_op_code(self, op_code):
        """Delete an operation code.

        Removes an operation code from the database.
        """
        self.execute(
            """
              DELETE FROM [:table schema=cerebrum name=auth_op_code]
              WHERE code=:code
            """,
            {'code': op_code})

    def list_operations(self):
        """Retrieves a list with operations for this operationset.

        Returns a list of tuples with op_id, op_code, op_set_id and code_str.
        """
        # TODO: This method differs from BofhdAuthOpSet for some reason
        return self.query(
            """
              SELECT ao.op_id, ao.op_code, ao.op_set_id, aoc.code_str
              FROM [:table schema=cerebrum name=auth_operation] ao,
                   [:table schema=cerebrum name=auth_op_code] aoc
              WHERE ao.op_set_id=:op_set_id AND
                    ao.op_code=aoc.code
            """,
            {'op_set_id': self.op_set_id})

    def list_operation_codes(self, op_id=None):
        """Retrieves a list with code, code_str and description.

        Filtered by op_id if included, else all operation codes are returned.
        """
        conds = []
        binds = {}
        tables = [
            '[:table schema=cerebrum name=auth_op_code] aoc',
        ]

        if op_id is not None:
            tables.append('[:table schema=cerebrum name=auth_operation] ao')
            conds.extend(('aoc.code=ao.op_code', 'ao.op_id=:op_id'))
            binds['op_id'] = op_id

        sql = """
          SELECT aoc.code, aoc.code_str, aoc.description
          FROM {tables}
          {where}
        """.format(
            tables=', '.join(tables),
            where=('WHERE ' + ' AND '.join(conds)) if conds else '',
        )

        return self.query(sql, binds)


class Target(auth.BofhdAuthOpTarget):

    def search(self, *args, **kwargs):
        return self.list(*args, **kwargs)


class Role(auth.BofhdAuthRole):

    def search(self, *args, **kwargs):
        return self.list(*args, **kwargs)


class Auth(object):
    """Authentication for the gro module.

    Used to authenticate if a operator is allowed to perform commands.
    """

    def __init__(self):
        pass

    def is_superuser(self, operator):
        """Check if the operator is a superuser.

        Operator is the operators entity_id.
        GRO_SUPER_USER_GROUP must be set in the cereconf.
        """
        if operator in self._get_group_members(cereconf.BOFHD_SUPERUSER_GROUP):
            return True
        return False

    def auth(self, operator):
        """Operator is the entity_id for the operator.
        """
        return self.is_superuser(operator)

    def check_permission(self, operator, operation, target_id):
        """Check if operator has permission to do operation.

        ``operator`` is the entity_id of the operator. ``operation`` is either
        a string matching "auth_op_code.code_str" or a int matching
        "auth_operation.op_id". ``target_id`` is the entity_id of the target.
        If one of the following returns true, he has permission to perform
        the given operation:
            1: Is he a superuser?
            2: He got access to perform the operation on the target?
            3: He is member of a group wich got access to the target?
        """
        # 1
        if self.is_superuser(operator):
            return True

        # 2 & 3
        query = self._query_permissions(operator, operation, target_id)
        if len(query):
            return True

        return False

    def _query_permissions(self, operator, operation, target_id):
        auth_entities = self._get_users_auth_entities(operator)
        if not auth_entities:
            return []

        try:
            operation = int(operation)
        except (TypeError, ValueError):
            where = """
              LOWER(aoc.code_str) LIKE LOWER(:operation) AND
              aoc.code=ao.op_code
            """
        else:
            where = 'ao.op_id=:operation'

        binds = {
            'operation': operation,
            'target_id': target_id,
        }
        ent = argument_to_sql(auth_entities, 'ar.entity_id', binds, int)

        sql = """
          SELECT
            aot.attr,
            ao.op_id,
            aot.op_target_id
          FROM
            [:table schema=cerebrum name=auth_op_code] aoc,
            [:table schema=cerebrum name=auth_operation] ao,
            [:table schema=cerebrum name=auth_operation_set] aos,
            [:table schema=cerebrum name=auth_role] ar,
            [:table schema=cerebrum name=auth_op_target] aot
          WHERE
            {where} AND
            ao.op_set_id=aos.op_set_id AND
            aos.op_set_id=ar.op_set_id AND
            {auth_entities} AND
            ar.op_target_id=aot.op_target_id AND
            aot.entity_id=:target_id
        """.format(where=where, auth_entities=ent)
        return self.query(
            sql,
            {
                'operation': operation,
                'target_id': target_id,
            })

    def list_operations(self, operator, target_id):
        """Retrieves a list with operations the operator can perform.

        Returns a list with tuples with the info (op_code, code_str).
        """
        auth_entities = self._get_users_auth_entities(operator)
        if not auth_entities:
            return []

        binds = {'target_id': target_id}
        ent = argument_to_sql(auth_entities, 'ar.entity_id', binds, int)

        sql = """
          SELECT ao.op_code, aoc.code_str
          FROM
            [:table schema=cerebrum name=auth_op_code] aoc,
            [:table schema=cerebrum name=auth_operation] ao,
            [:table schema=cerebrum name=auth_operation_set] aos,
            [:table schema=cerebrum name=auth_role] ar,
            [:table schema=cerebrum name=auth_op_target] aot
          WHERE
            aoc.code=ao.op_code AND
            ao.op_set_id=aos.op_set_id AND
            aos.op_set_id=ar.op_set_id AND
            {auth_entities} AND
            ar.op_target_id=aot.op_target_id AND
            aot.entity_id=:target_id
        """.format(auth_entities=ent)

        return self.query(sql, binds)

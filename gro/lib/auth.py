
import cereconf
from Cerebrum.modules.bofhd.auth import AuthConstants, BofhdAuthOpSet, \
            BofhdAuthOpTarget, BofhdAuthRole, BofhdAuth

class AuthOpSet( BofhdAuthOpSet ):
    """Wrapper for BofhdAuthOpSet
    
    More to come when i know what im gonna use this class for.
    """

    def __init__(self, db):
        BofhdAuthOpSet.__init__(self, db)
        self._db = db


class AuthOpTarget( BofhdAuthOpTarget ):
    """Wrapper for BofhdAuthOpTarget

    More to come when i know what im gonna use this class for.
    """

    def __init__(self, db):
        BofhdAuthOpTarget.__init__(self, db)
        self._db = db


class AuthRole( BofhdAuthRole ):
    """Wrapper for BofhdAuthRole

    More to come when i know what im gonna use this class for.
    """

    def __inti__(self, db):
        BofhdAuthRole.__init__(self, db)
        self._db = db


class Auth( BofhdAuth ):
    """Authentication for the gro module.

    Used to authenticate if a operator is allowed to perform commands wich
    makes changes to the database.
    """

    def __init__(self, db):
        BofhdAuth.__init__(self, db)
        self._db = db
    
    def is_superuser(self, operator):
        """Check if the operator is a superuser.
        
        Operator is the operators entity_id.
        GRO_SUPER_USER_GROUP must be set in the cereconf.
        """
        if operator in self._get_group_members(cereconf.BOFHD_SUPERUSER_GROUP):
            return True
        return False

    def auth(self, operator):
        """Operator is the entity_id for the operator."""
        return self.is_superuser(operator)

    def check_permission(self, operator, operation, target_id, attr):
        """Check if operator has permission to do operation.
        
        ``operator`` is the entity_id of the operator. ``operation`` is either
        "add attr", "remove attr", "change attr" or "read attr". ``target_id``
        is the entity_id of the target. ``attr`` is a attribute in the target_id.
        If one of the following returns true, he has permission to perform
        the given operation:
            1: Is he a superuser?
            2: He got access to the target, regardless of the attr?
            3: He got access to the target and its attribute?
            4: He is member of a group wich got acces to the target?
        """
        # 1
        if self.is_superuser(operator):
            return True
        
        # 2, 4
        if self._gro_query_target_permissions(operator, operation, target_id):
            return True

        # 3
        if self._gro_query_target_permissions(operator, operation, target_id, attr):
            return True
        return False

    def _gro_query_target_permissions(self, operator, operation, target_id, attr=None):
        where = ""
        try:
            operation = int(operation)
        except (TypeError, ValueError):
            where = """LOWER(aoc.code_str) LIKE LOWER(:operation) AND
                       aoc.op_code=ao.op_code"""
        else:
            where = "ao.op_id=:operation"
        sql = """
        SELECT aot.attr, ao.op_id, aot.op_target_id
        FROM [:table schema=cerebrum name=auth_op_code] aoc,
             [:table schema=cerebrum name=auth_operaton] ao,
             [:table schema=cerebrum name=auth_operation_set] aos,
             [:table schema=cerebrum name=auth_role] ar,
             [:table schema=cerebrum name=auth_op_target] aot
        WHERE
            %s AND
            ao.op_set_id=aos.op_set_id AND
            aos.op_set_id=ar.op_set_id AND
            ar.entity_id IN (%s) AND
            ar.op_target_id=aot.op_target_id AND
            aot.entity_id=:target_id
            """ % (where, ", ".join(
            ["%i" % x for x in self._get_users_auth_entities(operator)]))
        return self.query(sql, {'operation': operation, 'target_id': target_id})


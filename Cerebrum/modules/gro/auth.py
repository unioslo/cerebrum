
import cereconf
from Cerebrum.modules.bofhd.auth import AuthConstants, BofhdAuthOpSet, \
            BofhdAuthOpTarget, BofhdAuthRole, BofhdAuth

class OperationSet( BofhdAuthOpSet ):
    """Wrapper for BofhdAuthOpSet
    
    Methods for updating auth_operation_set, auth_operation, auth_op_attrs and
    auth_op_code wich specifies what operations may be performed.
    BofhdAuthOpSet does not have support for updating auth_op_code, therefor we
    have to extend this class with support for it.
    """

    def __init__(self, db):
        BofhdAuthOpSet.__init__(self, db)
        self._db = db

    def add_op_code(self, code_str, description=""):
        """Add an operation code.
        
        Adds an operation code_str and its description into the database.
        """
        op_code = int(self.nextval('code_seq'))
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=auth_op_code]
            (code, code_str, description)
        VALUES (:code, :code_str, :description)""",
            { 'code': op_code, 'code_str': code_str, 'description': description})
        return op_code

    def del_op_code(self, op_code):
        """Delete an operation code.

        Removes an operation code from the database.
        """
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=auth_op_code]
        WHERE code=:code""", {'code': op_code})

    def list_op_codes(self, op_id=None):
        """Retrieves a list with code, code_str and description.
        
        Filtered by op_id if included, else all operation codes are returned.
        """
        sql = 'SELECT aoc.code, aoc.code_str, aoc.description FROM'
        tables = '[:table schema=cerebrum name=auth_op_code] aoc'
        where = ''

        if op_id is not None:
            tables += ', [:table schema=cerebrum name=auth_operation] ao'
            where += 'WHERE aoc.code=ao.op_code AND ao.op_id=:op_id'

        return self.query("""%s %s %s""" %
                            (sql, tables, where), {'op_id': op_id})

    def list_operations(self):
        """Retrieves a list with operations for this operationset.

        BofhdAuthOperationSet does not return the code_str wich can be very
        usefull, so we overloads the method and includes it in the query.
        """
        return self.query("""
        SELECT ao.op_code, ao.op_id, ao.op_set_id, aoc.code_str
        FROM [:table schema=cerebrum name=auth_operation] ao,
             [:table schema=cerebrum name=auth_op_code] aoc
        WHERE ao.op_set_id=:op_set_id AND
              ao.op_code=aoc.code""", {'op_set_id': self.op_set_id})

class Target( BofhdAuthOpTarget ):
    """Wrapper for BofhdAuthOpTarget

    Methods for updating auth_op_target with information identifying targets
    wich operations may be performed on.
    """

    def __init__(self, db):
        BofhdAuthOpTarget.__init__(self, db)
        self._db = db


class Role( BofhdAuthRole ):
    """Wrapper for BofhdAuthRole

    Methods for updating the auth_role table with information about who has
    certain permissions to certain targets.
    """

    def __inti__(self, db):
        BofhdAuthRole.__init__(self, db)
        self._db = db


class Auth( BofhdAuth ):
    """Authentication for the gro module.

    Used to authenticate if a operator is allowed to perform commands.
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
        where = ""
        try:
            operation = int(operation)
        except (TypeError, ValueError):
            where = '''LOWER(aoc.code_str) LIKE LOWER(:operation) AND
                       aoc.code=ao.op_code'''
        else:
            where = 'ao.op_id=:operation'
        sql = """
        SELECT aot.attr, ao.op_id, aot.op_target_id
        FROM [:table schema=cerebrum name=auth_op_code] aoc,
             [:table schema=cerebrum name=auth_operation] ao,
             [:table schema=cerebrum name=auth_operation_set] aos,
             [:table schema=cerebrum name=auth_role] ar,
             [:table schema=cerebrum name=auth_op_target] aot
        WHERE
            %s AND
            ao.op_set_id=aos.op_set_id AND
            aos.op_set_id=ar.op_set_id AND
            ar.entity_id IN (%s) AND
            ar.op_target_id=aot.op_target_id AND
            aot.entity_id=:target_id""" % (where, ", ".join(
                ["%i" % x for x in self._get_users_auth_entities(operator)]))
        return self.query(sql, {'operation': operation,'target_id': target_id})

    def list_operations(self, operator, target_id):
        """Retrieves a list with operations the operator can perform.
        
        Returns a list with tuples with the info (op_code, code_str).
        """
        return self.query("""
        SELECT ao.op_code, aoc.code_str
        FROM [:table schema=cerebrum name=auth_op_code] aoc,
             [:table schema=cerebrum name=auth_operation] ao,
             [:table schema=cerebrum name=auth_operation_set] aos,
             [:table schema=cerebrum name=auth_role] ar,
             [:table schema=cerebrum name=auth_op_target] aot
        WHERE
            aoc.code=ao.op_code AND
            ao.op_set_id=aos.op_set_id AND
            aos.op_set_id=ar.op_set_id AND
            ar.entity_id IN (%s) AND
            ar.op_target_id=aot.op_target_id AND
            aot.entity_id=:target_id""" % (",".join(
                ["%i" % x for x in self._get_users_auth_entities(operator)])),
                {'target_id': target_id})


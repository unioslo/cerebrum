
import cereconf
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Utils import Factory, mark_update


class OperationSet( DatabaseAccessor ):
    """A set of auth operations.
    
    Methods for updating auth_operation_set, auth_operation, auth_op_attrs and
    auth_op_code wich specifies what operations may be performed.
    """
    
    __metaclass__ = mark_update
    __read_attr__ = ('__in_db', 'const')
    __write_attr__ = ('op_set_id', 'name')
    dontclear = ('const',)

    def __init__(self, database):
        super(OperationSet, self).__init__(database)

    def clear_class(self, cls):
        for attr in cls.__read_attr__:
            if hasattr(self, attr):
                if attr not in getattr(cls, 'dontclear', ()):
                    delattr(self, attr)
        for attr in cls.__write_attr__:
            if attr not in getattr(cls, 'dontclear', ()):
                setattr(self, attr, None)

    def clear(self):
        self.clear_class(OperationSet)
        self.__updated = []

    def find(self, id):
        self.name, self.op_set_id = self.query_1("""
        SELECT name, op_set_id
        FROM [:table schema=cerebrum name=auth_operation_set]
        WHERE op_set_id=:id""", {'id': id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def find_by_name(self, name):
        id = self.query_1("""
        SELECT op_set_id
        FROM [:table schema=cerebrum name=auth_operation_set]
        WHERE name=:name""", {'name': name})
        self.find(id)

    def populate(self, name):
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        self.name = name

    def write_db(self):
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.op_set_id = int(self.nextval('entity_id_seq'))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=auth_operation_set]
            (op_set_id, name) VALUES (:os_id, :name)""", {
                'os_id': self.op_set_id, 'name': self.name})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=auth_operation_set]
            SET name=:name
            WHERE op_set_id=:os_id""", {
                'os_id': self.op_set_id, 'name': self.name})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def delete(self):
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=auth_operation_set]
        WHERE op_set_id=:os_id""", {'os_id': self.op_set_id})
        self.clear()

    def add_operation(self, op_code):
        """Add an auth operation.
        
        Add an auth operation to this operation_set with the op_code.
        """
        op_id = int(self.nextval('entity_id_seq'))
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=auth_operation]
        (op_code, op_id, op_set_id)
        VALUES (:code, :op_id, :op_set_id)""", {
            'code': int(op_code), 'op_id': op_id, 'op_set_id': self.op_set_id})
        return op_id

    def del_operation(self, op_code):
        """Remove a operation from the operation set.
        """
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=auth_operation]
        WHERE op_code=:op_code AND op_set_id=:op_set_id""", {
            'op_code': int(op_code), 'op_set_id': self.op_set_id})

    def add_op_attrs(self, op_id, attr):
        """Add operation attrs to the operation op_id.
        """
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=auth_op_attrs] (op_id, attr)
        VALUES (:op_id, :attr)""", {
            'op_id': op_id, 'attr': attr})

    def del_op_attrs(self, op_id, attr):
        """Remove the attr from the operation op_id.
        """
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=auth_op_attrs]
        WHERE op_id=:op_id AND attr=:attr""", {
            'op_id': int(op_id), 'attr': attr})
    
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

    def list(self):
        """Retrives a list with all operation_sets.
        
        Returns a list of tuple with op_set_id and name.
        """
        return self.query("""
        SELECT op_set_id, name
        FROM [:table schema=cerebrum name=auth_operation_set]""")

    def list_operations(self):
        """Retrieves a list with operations for this operationset.

        Returns a list of tuples with op_id, op_code, op_set_id and code_str.
        """
        return self.query("""
        SELECT ao.op_id, ao.op_code, ao.op_set_id, aoc.code_str
        FROM [:table schema=cerebrum name=auth_operation] ao,
             [:table schema=cerebrum name=auth_op_code] aoc
        WHERE ao.op_set_id=:op_set_id AND
              ao.op_code=aoc.code""", {'op_set_id': self.op_set_id})

    def list_operation_attrs(self, op_id):
        """Retrieves a list with attrs for the op_id.
        """
        return self.query("""
        SELECT attr
        FROM [:table schema=cerebrum name=auth_op_attrs]
        WHERE op_id=:op_id""", {'op_id': op_id})

    def list_operation_codes(self, op_id=None):
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


class Target( DatabaseAccessor ):
    """Target for the auth operation.
    
    Methods for updating auth_op_target with information
    identifying targets which operations may be performed on.
    """

    __metaclass__ = mark_update
    __read_attr__ = ('__in_db', 'const')
    __write_attr__ = ('entity_id', 'target_type', 'attr', 'op_target_id')
    dontclear = ('const',)

    def __init__(self, database):
        super(Target, self).__init__(database)

    def clear_class(self, cls):
        for attr in cls.__read_attr__:
            if hasattr(self, attr):
                if attr not in getattr(cls, 'dontclear', ()):
                    delattr(self, attr)
        for attr in cls.__write_attr__:
            if attr not in getattr(cls, 'dontclear', ()):
                setattr(self, attr, None)

    def clear(self):
        self.clear_class(Target)
        self.__updated = []

    def delete(self):
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=auth_op_target]
        WHERE op_target_id=:id""", {'id': self.op_target_id})
        self.clear()

    def find(self, id):
        self.op_target_id, self.entity_id, self.target_type, self.attr = \
        self.query_1("""
        SELECT op_target_id, entity_id, target_type, attr
        FROM [:table schema=cerebrum name=auth_op_target]
        WHERE op_target_id=:id""", {'id': id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def populate(self, entity_id, target_type, attr=None):
        self.__in_db = False
        self.entity_id = entity_id
        self.target_type = target_type
        self.attr = attr

    def write_db(self):
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.op_target_id = int(self.nextval('entity_id_seq'))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=auth_op_target]
            (op_target_id, entity_id, target_type, attr) VALUES
            (:t_id, :e_id, :t_type, :attr)""", {
                't_id': self.op_target_id, 'e_id': self.entity_id,
                't_type': self.target_type, 'attr': self.attr})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=auth_op_target]
            SET target_type=:t_type, attr=:attr, entity_id=:e_id
            WHERE op_target_id=:t_id""", {
                't_id': self.op_target_id, 'e_id': self.entity_id,
                't_type': self.target_type, 'attr': self.attr})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def list(self, *args, **vargs):
        """Search fits the API better, List is DEPRECATED!
        """
        return self.search(*args, **vargs)

    def search(self, target_id=None, target_type=None, entity_id=None, attr=None):
        """Retrives a list of auth targets.

        The list can be filtered if any attributes are given.
        """
        ewhere = []
        if entity_id is not None:
            ewhere.append("entity_id=:entity_id")
        if target_id is not None:
            ewhere.append("op_target_id=:target_id")
        if target_type is not None:
            ewhere.append("target_type=:target_type")
        if attr is not None:
            ewhere.append("attr=:attr")
        if ewhere:
            ewhere = "WHERE %s" % " AND ".join(ewhere)
        else:
            ewhere = ""
        return self.query("""
        SELECT op_target_id, entity_id, target_type, attr
        FROM [:table schema=cerebrum name=auth_op_target]
        %s
        ORDER BY entity_id""" % ewhere, {'entity_id': entity_id, 
            'target_id': target_id, 'target_type': target_type, 'attr': attr})


class Role( DatabaseAccessor ):
    """Linking OperationSet and Target with an entity_id.
    
    Methods for updating the auth_role table with information
    about who has certain permissions to certain targets.
    """

    def __init__(self, database):
        super(Role, self).__init__(database)

    def grant_auth(self, entity_id, op_set_id, op_target_id):
        """Give access to perfom operation on target.

        ''entity_id'' is the entity wich is given access.
        ''op_set_id'' is a set of operations.
        ''op_target_id'' is the target to give access on.
        """
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=auth_role]
        (entity_id, op_set_id, op_target_id)
        VALUES (:e_id, :os_id, :t_id)""", {
            'e_id': entity_id, 'os_id': op_set_id, 't_id': op_target_id})

    def revoke_auth(self, entity_id, op_set_id, op_target_id):
        """Remove access to perform operation on target.
        """
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=auth_role]
        WHERE entity_id=:e_id AND op_set_id=:os_id AND op_target_id=:t_id""", {
            'e_id': entity_id, 'os_id': op_set_id, 't_id': op_target_id})

    def list(self, *args, **vargs):
        """Search fits the API better, List is DEPRECATED!
        """
        return self.search(*args, **vargs)

    def search(self, entity_ids=None, op_set_id=None, op_target_id=None):
        """Return info about where entity_id has permissions.
        
        ''entity_id'' may be a list of entities.
        """
        ewhere = []
        where = ""
        if entity_ids is not None:
            if not isinstance(entity_ids, (list, tuple)):
                entity_ids = [entity_ids]
            ewhere.append("entity_id IN (%s)" % 
                          ", ".join(["%i" % i for i in entity_ids]))
        if op_set_id is not None:
            ewhere.append("op_set_id=:op_set_id")
        if op_target_id is not None:
            ewhere.append("op_target_id=:op_target_id")
        if ewhere:
            where = "WHERE " + " AND ".join(ewhere)
        return self.query("""
        SELECT DISTINCT entity_id, op_set_id, op_target_id
        FROM [:table schema=cerebrum name=auth_role] %s""" % where,
            {'op_set_id': op_set_id, 'op_target_id': op_target_id})

    def list_owners(self, target_ids):
        """Return info about who owns the given target_ids.
        """
        if not isinstance(target_ids, (list, tuple)):
            target_ids = [target_ids]
        if not target_ids:
            return ()
        return self.query("""
        SELECT DISTINCT entity_id, op_set_id, op_target_id
        FROM [:table schema=cerebrum name=auth_role]
        WHERE op_target_id IN (%s)""" % ", ".join(["%i" % i for i in target_ids]))


class Auth( object ):
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

# arch-tag: f65b2899-a8d9-4007-a490-91e7c3816dba

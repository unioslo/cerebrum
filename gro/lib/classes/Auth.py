import Registry
registry = Registry.get_registry()

Builder = registry.Builder
Attribute = registry.Attribute
Searchable = registry.Searchable

AuthOperationType = registry.AuthOperationType

__all__ = ['AuthOperationSet', 'AuthOperation', 'AuthOperationAttr', 'AuthRole', 'EntityAuth']

# samling med operasjoner
class AuthOperationSet(Builder):
    primary = [Attribute('id', 'long')]
    slots = primary + [Attribute('name', 'string')]

    def load_name(self):
        db = self.get_database()
        self._name = db.query_1('''SELECT name
                                   FROM [:table schema=cerebrum name=auth_operation_set]
                                   WHERE op_set_id=:id''', {'id': self._id})

# AuthOperationSet innholder disse
class AuthOperation(Builder, Searchable):
    primary = [Attribute('id', 'long')]
    slots = primary + [Attribute('operation_type', 'AuthOperationType'),
                       Attribute('operation_set', 'AuthOperationSet')]
    def _load_operation(self):
        db = self.get_database()
        row = db.query_1('''SELECT op_code, op_set_id
                            FROM [:table schema=cerebrum name=auth_operation]
                            WHERE op_id=:id''', {'id': self._id})
        self._operation_type = AuthOperationType(id=int(row['op_code']))
        self._operation_set = AuthOperationSet(int(row['op_set_id']))

    load_operation_type = load_operation_set = _load_operation
    
    def create_search_method(cls):
        def search(self, operation_type=None, operation_set=None):
            where = []
            if operation_type is not None:
                where.append('op_code = %i' % operation_type.get_id())
            if operation_set is not None:
                where.append('op_set_id = %i' % operation_set.get_id())

            if where:
                where = 'where %s' % ' and '.join(where)
            else:
                where = ''
                
            objects = []
            db = self.get_database()
            for row in db.query("""SELECT op_id, op_code, op_set_id
                                   FROM [:table schema=cerebrum name=auth_operation]
                                   %s""" % where):
                op_id = int(row['op_id'])
                op_code = int(row['op_code'])
                op_set_id = int(row['op_set_id'])
                obj = AuthOperation(op_id, AuthOperationType(op_code), AuthOperationSet(op_set_id))
                objects.append(obj)
            return objects
        return search
    create_search_method = classmethod(create_search_method)


# hva skal denne brukes til? validation? jaha? kanskje vi kan løse spread-tullet
# i AuthOperationTarget med denne da...
class AuthOperationAttr(Builder):
    primary = [Attribute('id', 'long')]
    slots = primary + [Attribute('attr', 'string')]

# uh. i følge desgin/gro_auth.sql skal entity kunne være en spread? huh?
# men denne er altså en target
# kun entity skal være nødvendig her...
# 1:1 mapping er jo fint
# jeg driter i denne
#class AuthOperationTarget(Builder):
#    primary = [Attribute('id', 'long')]
#    slots = primary + [Attribute('entity', 'Entity')]

class AuthRole(Builder, Searchable):
    primary = [Attribute('entity', 'Entity'), Attribute('operation_set', 'AuthOperationSet'),
               Attribute('target', 'Entity')]
    slots = primary + []

    def create_search_method(cls):
        def search(self, entity=None, operation_set=None, target=None):
            where = []
            if entity is not None:
                where.append('entity_id = %i' % entity.get_entity_id())
            if operation_set is not None:
                where.append('op_set_id = %i' % operation_set.get_id())
            if target is not None:
                where.append('op_target_id = %i' % target.get_entity_id())

            if where:
                where = 'where %s' % ' and '.join(where)
            else:
                where = ''
                
            objects = []
            db = self.get_database()
            for row in db.query("""SELECT entity_id, op_set_id, op_target_id
                                   FROM [:table schema=cerebrum name=auth_role]
                                   %s""" % where):
                entity_id = int(row['entity_id'])
                op_set_id = int(row['op_set_id'])
                op_target_id = int(row['op_target_id'])
                obj = AuthRole(registry.Entity(entity_id), AuthOperationSet(op_set_id),
                               registry.Entity(op_target_id))
                objects.append(obj)
            return objects
        return search
    create_search_method = classmethod(create_search_method)

class EntityAuth(object): # Mixin for Entity
    def is_superuser(self):
        """ Check if this object is a superuser """
        return False

    def check_permission(self, operator, operation_type, check_groups=True):
        """Check if operator has permission to do the operation on this object.
        
        ``operator`` is the entity doing the ``operation``

        operator  - Entity
        operation_type - AuthOperation

        If one of the following returns true, he has permission to perform
        the given operation:
            1: Is he a superuser?
            2: He got access to perform the operation on this target?
            3: He is member of a group wich got access to this target?
        """
        AuthRoleSearch = AuthRole.create_search_class() # FIXME. bruk gro_registry
        AuthOperationSearch = AuthOperation.create_search_class() # FIXME. bruk gro_registry

        # 1 Is he a superuser?
        # -
        if operator.is_superuser():
            return True

        # 2 He got access to perform the operation on this target?
        # -
        # denne kan vi implementere i ren sql...
        # men denne burde være rask nok, siden det ikke blir alt for mange
        # operation_set pr entitet/target

        # finner først alle operation_set's som entiten har lov til å utføre på target
        searcher = AuthRoleSearch()
        searcher.set_entity(operator)
        searcher.set_target(self)

        # sjekker så om operation_type tilhører en av operation_set'ene vi finner
        for auth_role in searcher.search():
            print auth_role, operation_type, auth_role.get_operation_set()
            searcher = AuthOperationSearch()
            searcher.set_operation_type(operation_type)
            searcher.set_operation_set(auth_role.get_operation_set())
            if searcher.search():
                return True
        
        if not check_groups:
            return False
            
        # 3 He is member of a group wich got access to this target?
        # -
        # get_groups er ikke implementert. Den skal hente ut alle grupper denne entiteten
        # er direkte eller indirekte medlem av
        # jeg er litt forvirret av intersection/difference.. kanskje vi skal bestemme at
        # grupper entitenen er union-medlem i skal få lov til å brukes til auth?
        for entity in self.get_groups():
            if self.check_permission(entity, operation, check_groups=False):
                return True

        return False

# arch-tag: 962639fc-ff64-4015-9502-df9542cd25ef

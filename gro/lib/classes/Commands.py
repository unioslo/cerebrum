import Registry
registry = Registry.get_registry()

Builder = registry.Builder
Method = registry.Method

Group = registry.Group
GroupVisibilityType = registry.GroupVisibilityType

__all__ = ['Commands']

class Commands(Builder):
    primary_key = []
    slots = []
    method_slots = [
        Method('create_group', 'Group', [('name', 'string'), ('visibility', 'GroupVisibilityType')],
               write=True)]

    def __init__(self):
        Builder.__init__(self, nocache=True)

    def create_group(self, name, visibility):
        db = self.get_database()
        group = Group.cerebrum_class(db)
        print 'change_by', [db.change_by]
        group.populate(db.change_by, visibility.get_id(), name)
        group.write_db()

        id = group.entity_id
        return Group(id, write_lock=self.get_writelock_holder())

# arch-tag: d756f6b2-7b09-4bf5-a65e-81cacfea017a

from Cerebrum.Utils import Factory

def create_save(attr, cls, cerebrum_attr):
    def save_cerebrum(self):
        db = self.get_database()

        obj = cls(db)
        obj.find(self.get_id())

        value = getattr(self, attr.get_name_private())
        setattr(obj, cerebrum_attr, value)
        obj.write_db()

    return save_cerebrum

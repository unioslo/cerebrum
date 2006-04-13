from SpineLib.Builder import Builder
from SpineLib.DatabaseClass import DatabaseClass, DatabaseTransactionClass, DatabaseAttr

table = 'dummy_building'
class DummyBuilding(DatabaseClass):
    primary = (
        DatabaseAttr('id', table, int),
    )
    slots = (
        DatabaseAttr('name', table, str),
        DatabaseAttr('description', table, str),
    )

    def hello(self):
        return "hello world!"

    hello.signature = str

table = 'dummy_room'
class DummyRoom(DatabaseClass):
    primary = (
        DatabaseAttr('id', table, int),
    )
    slots = (
        DatabaseAttr('name', table, str),
        DatabaseAttr('building', table, DummyBuilding),
        DatabaseAttr('description', table, str),
    )

class DummyCommands(DatabaseTransactionClass):
    def create_building(self, name, description):
        db = self.get_database()
        id = db.nextval('dummy_seq')
        DummyBuilding._create(self.get_database(), id, name, description)
        return DummyBuilding(db, id)

    create_building.signature = DummyBuilding
    create_building.signature_args = [str, str]

    def create_room(self, name, building, description):
        db = self.get_database()
        id = db.nextval('dummy_seq')
        DummyRoom._create(self.get_database(), id, name, building, description)
        return DummyRoom(db, id)

    create_room.signature = DummyRoom
    create_room.signature_args = [str, DummyBuilding, str]

from Cerebrum.gro.Cerebrum_core import KeyValue

import mx.DateTime
import types

class DatabaseOverrides:
    def __init__( self, db ):
        self._db = db
    def get_spread_map( self ):
        spread_map = {}
        for row in self._db.query( 'SELECT code_str, code FROM spread_code' ):
            spread_map[row['code_str']] = int( row['code'] )
        return spread_map

    def get_entity_type_map( self ):
        """
        returns a dict with type:code mappings
        """
        entity_type_map = {}
        for row in self._db.query( 'SELECT code_str, code FROM entity_type_code' ):
            entity_type_map[row['code_str']] = int( row['code'] )
        return entity_type_map

    def get_all_entity_spreads( self ):
        """
        returns a list with (entity_id, spread)'s
        """
        spreads = []

        for row in self._db.query( 'SELECT entity_id, spread FROM entity_spread' ):
            spreads.append( ( int( row['entity_id'] ), int( row['spread'] ) ) )
        return spreads

    def get_object_items( self, entity_type_class, id ):
        object = entity_type_class(self._db)
        object.find( id )

        items = []
        for key, value in object.__dict__.items():
            if key[0] == '_': # private member
                continue
            elif type(value) == mx.DateTime.DateTimeType:
                value = int(value.ticks())
            elif type(value) == types.NoneType:
                value = ''

            items.append( KeyValue( key, str(value) ) )

        return items

    def get_change_type_map( self ):
        change_type_map = {}
        for i in self._db.get_changetypes():
            change_type_map[int( i.change_type_id )] = i.type
        return change_type_map

#!/usr/bin/env  python

import time

from Cerebrum.gro import Cerebrum_core, Cerebrum_core__POA
from Cerebrum.gro.Cerebrum_core import KeyValue

import Iterator

from Cerebrum.Utils import Factory
import Cerebrum.Errors

import DatabaseOverrides

import threading

lock = threading.Lock()

class LOHandler( Cerebrum_core__POA.LOHandler ):
    def __init__( self, gro, db ):
        self._gro = gro
        self._db = db

        dbo = DatabaseOverrides.DatabaseOverrides( db )

        self.spread_map = dbo.get_spread_map()
        self._entity_type_map = dbo.get_entity_type_map()
        self._change_type_map = dbo.get_change_type_map()
        self._get_all_entity_spreads = dbo.get_all_entity_spreads
        self._get_object_items = dbo.get_object_items

        self._latest_change_id = self._get_latest_change()

        self._classes = {}
        for i in self._entity_type_map:
            try:
                self._classes[i] = Factory.get( i.capitalize() ) # so ugly
            except ValueError:
                pass # we dont care

    def _get_type( self, cl ):
        """
        Returns the name of the class, as seen from the database
        """
        for key, value in self._classes.items():
            if issubclass(cl, value):
                return key
        return 'øh'
    
    def _factory_get( self, entity_type_class ):
        """
        Wrapper for Factory.get found in Cerebrum.
        If Factory.get returns nothing it will try to import
        Cerebrum.modules.`entity_type_class` instead.
        """
        try:
            exec 'import Cerebrum.modules.%s as module' % entity_type_class
            exec 'cl = module.%s' % entity_type_class
            return cl
        except:
            try:
                return Factory.get( entity_type_class )
            except ValueError:
                raise Cerebrum_core.Errors.NoSuchTypeError( 'Unknown type \'%s\'' % type )

    def _get_latest_change( self ):
        """
        Return the last change id
        """
        # TODO: Lag database-override
        changes = self._db.get_log_events( start_id = 0 )
        change_ids = [int( i.change_id ) for i in changes]
        change_ids.sort()
        return change_ids.pop()

    def _get_update( self, entity_type_class, spreads, start_id ):
        """
        Returns a list of all entities that has been removed since start_id.
        start_id is an integer indentifying the first changelog id to search
        from"""

        cl = self._factory_get( entity_type_class )
        entity_type = self._get_type( cl )
        if spreads:
            spreads_list = self._get_all_entity_spreads()

        entities = {}
        deleted = {}

        for i in self._db.get_log_events( start_id ):
            id = i.dest_entity or i.subject_entity # ingen anelse om dette er riktig...
            change_type_id = int( i.change_type_id )
            change_id = i.change_id

            if self._change_type_map[change_type_id] in ('del', 'delete', 'rem', 'destroy'): # kanskje flere..
                deleted[id] = [KeyValue( "id", str(id) )]
            else:
                entities[id] = None

        if change_id != self._latest_change_id:
            self._latest_change_id = change_id

        return self._make_objects( cl, entities.keys(), spreads), deleted.values()

    def _get_all( self, entity_type_class, spreads ):
        from Cerebrum import Entity
        entity = Entity.Entity(self._db)

        entities = []
        cl = self._factory_get( entity_type_class )
        entity_type = self._get_type( cl )

        for row in entity.list_all_with_type( self._entity_type_map[entity_type] ):
            entities.append( int( row['entity_id'] ) )

        return self._make_objects( cl, entities, spreads )

    def _make_objects( self, cl, ids, spreads ):
        """
        Makes cl-objects based on the list of ids and spreads
        """
        if spreads:
            spreads_list = self._get_all_entity_spreads()

        entities = []
        def add( id ): # cerebrum er teit! databasen er ikke i sync med seg selv
            try:
                entities.append( self._get_object_items( cl, id ) )
            except Cerebrum.Errors.NotFoundError: # args, denne tar alt
                pass
#                print 'not found (database inconsistent): %s' % ( id )

        for id in ids:
            if spreads: # legger kun til medlemmer, hvis spreads er spesifisert
                for i in spreads:
                    if (id, self.spread_map[i]) in spreads_list:
                        add( id )
                        break
            else:
                add( id )

        return entities

    def get_all( self, entity_type_class, spreads ):
        entities = Iterator.BulkIteratorImpl( self._get_all( entity_type_class, spreads ) )
        latest = self._get_latest_change()

        return latest, self._gro.com.get_corba_representation( entities )

    def get_update( self, entity_type_class, spreads, from_change_id = 0 ):
        if not spreads:
            spreads = None

        entities, deleted = self._get_update( entity_type_class, spreads, from_change_id )

        entities = Iterator.BulkIteratorImpl( entities )
        deleted = Iterator.BulkIteratorImpl( deleted )

        latest = self._get_latest_change()

        return (latest, ) + self._gro.com.get_corba_representation( entities, deleted )


    def benchmark(self, n, m):
        print 'start'
        a = time.time()
        items = []
        for i in xrange(n):
            items.append([KeyValue('0'*m, '1'*m)])
        items = self._gro.com.get_corba_representation(Iterator.BulkIteratorImpl(items))
        print 'slutt', time.time() - a
        return items

    def synchronized_benchmark(self, n, m):
        lock.acquire()
        items = self.benchmark(n, m)
        lock.release()
        return items


if __name__ == '__main__':
    import cerebrum_path
    from Cerebrum.Utils import Factory
    db = Factory.get( 'Database' )()

    lo = LOHandler(None, db)
#    print lo._get_deleted_entities( 0, None )
    for jee in 'PosixUser', 'PosixGroup':
        for i in lo._get_all(jee, ''):
            for i in i:
                print i.key, i.value
#    print lo._get_all('group', '')

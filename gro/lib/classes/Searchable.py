from Builder import Builder
from Cerebrum.gro.classes.db import db

def build_set_method( var ):
    """
    This function creates a simple set method set(self, value), which
    uses setattr().
    Methods created with this function are used in search objects.
    """
    assert type( var ) == str

    def set( self, value ):
        # set the variable
        setattr( self, '_' + var, value )
    return set

def build_search_method( searchclass ):
    """
    This function creates a search method for a search class, using
    the slots convention of the AP API. The generated method calls search()
    on the Cerebrum API class which the search class represents, and returns
    populated AP objects from the results.
    """
    def search( searchclass ):
        searchdict = {}
        for attr in searchclass.slots:
            val = getattr( searchclass, '_' + attr.name )
            if val != None:
                searchdict[attr.name] = val

        obj = searchclass._cerebrum_class( db ) # FIXME: Db-objekter skal deles på annen måte
        rows = obj.search( **searchdict )
        objects = []

        for row in rows:
            try:
                entity_id = int( row[0] )
            except TypeError:
                raise Errors.SearchError( 
                    'Could not fetch the ID of one of the found objects.' )
            objects.append( searchclass._cls( entity_id ) )
            
        return objects
        
    return search


class Searchable:
    def build_search_class( cls ):
        search_class_name = '%sSearch' % cls.__name__
        
        exec 'class %s(Builder):\n\tpass\nsearchclass = %s\n' % ( 
            search_class_name, search_class_name )
            
        searchclass._cls = cls
        
        searchclass.slots = [i for i in cls.slots if i.writable]
        
        for attr in searchclass.slots:
            if not hasattr( searchclass, attr.name ):
                setattr( searchclass, '_' + attr.name, None )
            set = build_set_method( attr.name )
            setattr( searchclass, 'set_' + attr.name, set )
            
        if not hasattr( cls, 'cerebrum_class' ):
            raise Errors.UnsearchableClassError( 
                'Class %s has no cerebrum_class reference' % cls.__name__ )

        searchclass._cerebrum_class = cls.cerebrum_class
        searchclass.search = build_search_method( searchclass )
        return searchclass

    build_search_class = classmethod(build_search_class)

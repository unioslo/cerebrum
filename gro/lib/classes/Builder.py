import time

from Cerebrum.extlib import sets
from Cerebrum.gro.Cerebrum_core import Errors
from Cerebrum.gro.classes.db import db

from Caching import Caching
from Locking import Locking


class Attribute:
    def __init__(self, name, data_type, writable=False):
        self.type = 'Attribute'
        self.name = name
        self.data_type = data_type
        self.writable = writable

class Method:
    def __init__(self, name, data_type, args=[], apHandler=False):
        self.type = 'Method'
        self.name = name
        self.data_type = data_type
        self.args = args
        self.apHandler = apHandler

class Lazy(object):
    pass

# å bruke en klasse med __call__ vil ikke funke, da den ikke vil bli bundet til objektet.
# mulig det kan jukses til med noen stygge metaklassetriks, men dette blir penere.

def LazyMethod(var, load):
    assert type(var) == str
    assert type(load) == str

    def lazy(self):
        value = getattr(self, var)
        if value is Lazy:
            loadmethod = getattr(self, load)
            if loadmethod is None:
                raise NotImplementedError('load for this attribute is not implemented')
            loadmethod()
            value = getattr(self, var)
            if value is Lazy:
                raise Exception('%s was not initialized during load' % var)
        return value
    return lazy

def SetWrapper(var):
    assert type(var) == str

    def set(self, value):
        # make sure the variable has been loaded
        orig = getattr(self, 'get_' + var) # farlig...... kan alle variabler hentes ut?
                                           # men skal jo brukes til rollback....

        if orig != value: # we only set a new value if it is different
            # set the variable
            setattr(self, '_' + var, value)
            self.updated.add(var)
    return set

def SimpleSetWrapper(var):
    """
    SimpleSetWrapper creates a simple set method, using only setattr().
    Methods created with this wrapper are used in search objects.
    """
    assert type(var) == str

    def set(self, value):
        # set the variable
        setattr(self, '_' + var, value)
    return set

def ReadOnly(var):
    def readOnly(self, *args, **vargs):
        raise Errors.ReadOnlyAttributeError('attribute %s is read only' % var)
    return readOnly

# FIXME: slots blir ikke oppdatert hvis register_atttribute blir kjørt og den ikke finnes fra før

class Builder(Caching, Locking):
    primary = []
    slots = []
    methodSlots = []

    def __init__(self, *args, **vargs):
        cls = self.__class__
        mark = '_%s%s' % (cls.__name__, id(self))
        # check if the object is old
        if hasattr(self, mark):
            return getattr(self, mark)
        
        Locking.__init__(self)
        Caching.__init__(self)

        self.prepare()

        slotNames = [i.name for i in cls.slots]
        # set all variables give in args and vargs
        for var, value in zip(slotNames, args) + vargs.items():
            setattr(self, '_' + var, value)

        # make sure all variables are set
        for var in slotNames:
            var = '_' + var
            hasattr(self, var) or setattr(self, var, Lazy)

        # used to track changes
        if not hasattr(self, 'updated'):
            self.updated = sets.Set()

        # mark the object as old
        setattr(self, mark, time.time())

    def load(self):
        # vil vi ha dette?
        # load kan laste _alle_ attributter vel å iterere gjennom slots...
        raise NotImplementedError('this should not happen')

    def save(self):
        """ Save all changed attributes """

        for var in self.updated:
            getattr(self, 'save_' + var)()
        self.updated.clear()

    def reload(self):
        """ Reload all changed attributes """

        for var in self.updated:
            getattr(self, 'load_' + var)()
        self.updated.clear()

    # class methods
    
    def getKey(cls, *args, **vargs):
        """ Get primary key from args and vargs

        Used by the caching facility to identify a unique object
        """
        
        names = [i.name for i in cls.primary]
        for var, value in zip(names, args):
            vargs[var] = value

        key = []
        for i in names:
            key.append(vargs[i])
        return tuple(key)


 
    def register_attribute(cls, attribute, load=None, save=None, get=None, set=None, overwrite=False, override=False):
        """ Registers an attribute

        attribute contains the name and data_type as it will be in the API
        load - loads the value for this attribute
        save - saves a new attribute
        get  - returns the value
        set  - sets the value. Validation can be done here.

        load/save/get/set must take self as first argument.

        overwrite - decides whether to overwrite existing definitions
        override  - decides whether to raise an exception when a definition of this
                    attribute allready exists

        If the attribute does not exist, it will be added to the class
        If overwrite=True load/save/get/set will be overwritten if they allready exists.
        If override=False and load/save/get/set exists, an exception will be raised.

        If get and set is None, the default behavior is for set and get to use
        self._`attribute.name`. load will then be run automatically by get if the
        attribute has not yet been loaded.

        If attribute is not writable, save will not be used.
        """

        var_private = '_' + attribute.name
        var_get = 'get_' + attribute.name
        var_set = 'set_' + attribute.name
        var_load = 'load_' + attribute.name
        var_save = 'save_' + attribute.name

        if get is None:
            get = LazyMethod(var_private, var_load)

        if set is None:
            if attribute.writable:
                set = SetWrapper(attribute.name)
            else:
                set = ReadOnly(attribute.name)

        def register(var, method):
            if hasattr(cls, var) and not overwrite:
                if not override:
                    raise AttributeError('%s already exists in %s' % (attribute.name, cls.__name__))
            else:
                setattr(cls, var, method)

        register(var_load, load)
        register(var_save, save)
        register(var_get, get)
        register(var_set, set)

    def register_method(cls, method, method_func, overwrite=False):
        """ Registers a method
        """
        if hasattr(cls, method.name) and not overwrite:
            raise AttributeError('%s already exists in %s' % ( method.name, cls.__name__))
        setattr(cls, method.name, meth_func)
        # TODO: This needs work

    def prepare(cls):
        for attribute in cls.slots:
            cls.register_attribute(attribute, override=True)

    def build_idl_header( cls ):
        txt = 'interface %s;\n' % cls.__name__
        txt += 'typedef sequence<%s> %sSeq;' % (cls.__name__, cls.__name__)
        return txt

    def build_idl_interface( cls ):
        txt = 'interface %s {\n' % cls.__name__

        txt += '\t//constructors\n'
        txt += '\t%s(%s)\n' % (cls.__name__, ', '.join(['in %s %s' % (attr.data_type, attr.name) for attr in cls.primary]))

        txt += '\n\t//get and set methods for attributes\n'
        for attr in cls.slots:
            txt += '\t%s get_%s();\n' % (attr.data_type, attr.name)
            if attr.writable:
                txt += '\tvoid set_%s(in %s %s);\n' % (attr.name, attr.data_type, attr.name)
            txt += '\n'

        txt += '\n\t//other methods\n'
        for method in cls.methodSlots: # args blir ignorert for øyeblikket...
            txt += '\t%s %s();\n' % (method.data_type, method.name)

        txt += '};'

        return txt

    def build_search_class( cls ):
        class SearchClass:
            pass
        searchcls = SearchClass
        searchcls._cls = cls
        searchcls.__name__ = '%sSearch' % cls.__name__
        searchcls.slots = [i for i in cls.slots if i.writable]
        for attr in searchcls.slots:
            if not hasattr(searchcls, attr.name):
                setattr(searchcls, '_' + attr.name, None)
            set = SimpleSetWrapper(attr.name)
            setattr(searchcls, 'set_' + attr.name, set)
        if not hasattr(cls, 'cerebrum_class'):
            raise UnsearchableClassError('Class %s has no cerebrum_class reference' % cls.__name__)
        searchcls._cerebrum_class = cls.cerebrum_class
        def search(searchcls):
            searchdict = {}
            for attr in searchcls.slots:
                val = getattr(searchcls, '_' + attr.name)
                if val != None:
                    searchdict[attr.name] = val
            o = searchcls._cerebrum_class(db) # FIXME: Db-objekter skal deles på annen måte
            rows = o.search(**searchdict)
            objects = []
            for row in rows:
                try:
                    entity_id = int(row[0])
                except TypeError:
                    raise UnsearchableClassError('Could not find the ID of the found %s object' %
                                                    cls.__name__)
                objects.append(searchcls._cls(entity_id))
            return objects
        searchcls.search = search
        return searchcls
            
    getKey = classmethod(getKey)
    register_attribute = classmethod(register_attribute)
    prepare = classmethod(prepare)
    build_idl_header = classmethod(build_idl_header)
    build_idl_interface = classmethod(build_idl_interface)
    build_search_class = classmethod(build_search_class)

    def __repr__(self):
        key = [repr(i) for i in self._key[1]]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(key))

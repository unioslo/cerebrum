import time

from Cerebrum.extlib import sets
from Cerebrum.gro.Cerebrum_core import Errors

from Caching import Caching
from Locking import Locking


class Attribute:
    def __init__(self, name, data_type, writable=False):
        self.type = 'Attribute'
        self.name = name
        self.data_type = data_type
        self.writable = writable

class Method:
    def __init__(self, name, data_type, args=(), apHandler=False):
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

        # set the variable
        setattr(self, '_' + var, value)
        self.updated.add(var)
#        if var not in self.updated:
#            self.updated[var] = orig
    return set

def ReadOnly(var):
    def readOnly(self, *args, **vargs):
        raise Errors.ReadOnlyAttributeError('attribute %s is read only' % var)
    return readOnly

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

    def getKey(cls, *args, **vargs):
        names = [i.name for i in cls.primary]
        for var, value in zip(names, args):
            vargs[var] = value

        key = []
        for i in names:
            key.append(vargs[i])
        return tuple(key)
    getKey = classmethod(getKey)

    def load(self):
        raise NotImplementedError('this should be implemented in subclass')

    def save(self):
        for var in self.updated:
            getattr(self, 'save_' + var)()
        self.updated.clear()

    def reload(self):
        for var in self.updated:
            getattr(self, 'load_' + var)()
        self.updated.clear()

    # class methods
    
    def register_attribute(cls, name, data_type, load, save, set=None, get=None, overwrite=False):
        var_private = '_' + name
        var_get = 'get_' + name
        var_set = 'set_' + name
        var_load = 'load_' + name
        var_save = 'save_' + name

        if get is None:
            get = LazyMethod(var_private, var_load)

        if overwrite or not hasattr(cls, var_get):
            setattr(cls, var_get, get)

        if overwrite or not hasattr(cls, var_set):
            setattr(cls, var_set, set)

        if overwrite or not hasattr(cls, var_load):
            setattr(cls, var_load, load)

        if overwrite or not hasattr(cls, var_save):
            setattr(cls, var_save, save)

    def prepare(cls):
        for attr in cls.slots:
            if attr.writable:
                set = SetWrapper(attr.name)
            else:
                set = ReadOnly(attr.name)
            load = getattr(cls, 'load_' + attr.name, None)
            save = getattr(cls, 'save_' + attr.name, None)

            cls.register_attribute(attr.name, attr.data_type, load, save, set)

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
            
    register_attribute = classmethod(register_attribute)
    prepare = classmethod(prepare)
    build_idl_header = classmethod(build_idl_header)
    build_idl_interface = classmethod(build_idl_interface)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, getattr(self, 'id', ''))


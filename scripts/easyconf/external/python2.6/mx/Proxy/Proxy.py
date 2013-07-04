""" Python part of the Proxy type implementation.

    Copyright (c) 2000, Marc-Andre Lemburg; mailto:mal@lemburg.com
    Copyright (c) 2000-2008, eGenix.com Software GmbH; mailto:info@egenix.com
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

"""
import types

# Import C extension module & register finalizer
from mxProxy import *
from mxProxy import __version__
try:
    finalizeweakrefs
except NameError:
    pass
else:
    class _ModuleFinalization:
        def __init__(self,function):
            self.fini = function
        def __del__(self):
            self.fini()
    _fini = _ModuleFinalization(finalizeweakrefs)

# Note: The type Proxy is defined in the C extension

try:
    from mx.Tools import freeze
except:
    freeze = lambda x: x

class ProxyFactory:

    """ Factory for producing Proxy-wrapped objects
        of a class.
    """
    def __init__(self,Class,interface=None):

        self.Class = Class
        self.interface = interface

    def __call__(self,*args,**kw):

        """ Return a new (wrapped) object. Pass-objects are not supported.
        """
        return Proxy(apply(self.Class,args,kw),self.interface)

    def __repr__(self):

        return '<ProxyFactory for %s>' % repr(self.Class)

class InstanceProxy:

    """ Proxy that wraps Python instances transparently.
    """
    def __init__(self,object,interface=None,passobj=None,

                 Proxy=Proxy):

        """ The interface is the same as that of the underlying C
            Proxy type.
        """
        dict = self.__dict__
        p = Proxy(object,interface,passobj)
        dict['proxy_getattr'] = p.proxy_getattr
        dict['proxy_setattr'] = p.proxy_setattr
        dict['proxy_object_repr'] = (object.__class__.__module__ + '.' +
                                     object.__class__.__name__)

    def __repr__(self):

        return '<%s.%s for %s at 0x%x>' % ( 
            self.__class__.__module__,
            self.__class__.__name__, 
            self.proxy_object_repr, 
            id(self))

    #
    # XXX Use specialized unbound C methods for these... trading a Python call
    #     against a dict lookup.
    #

    def __getattr__(self,what):
        return self.proxy_getattr(what)

    def __setattr__(self,what,to):
        self.proxy_setattr(what,to)

freeze(InstanceProxy)

class CachingInstanceProxy(InstanceProxy):

    """ Proxy that wraps Python instances transparently and caches
        accessed attributes and methods.

        Note that cached attributes are not looked up in the wrapped
        instance after the first lookup -- if their value changes,
        this won't be noticed by objects that access the object
        through this wrapper.

    """
    def __getattr__(self,what):

        self.__dict__[what] = o = self.proxy_getattr(what)
        return o

    def __setattr__(self,what,to):
        
        self.proxy_setattr(what,to)
        # Delete the cached entry...
        if self.__dict__.has_key(what):
            del self.__dict__[what]

freeze(CachingInstanceProxy)

class SelectiveCachingInstanceProxy(InstanceProxy):

    """ Proxy that wraps Python instances transparently and caches
        accessed attributes and methods depending on their type.

        Cached types are set via the attribute proxy_cacheable_types.
        It defaults to caching only methods (which likely don't change).

    """
    proxy_cacheable_types = (types.MethodType,)

    def __getattr__(self,what):

        o = self.proxy_getattr(what)
        if type(o) in self.proxy_cacheable_types:
            self.__dict__[what] = o
        return o

freeze(SelectiveCachingInstanceProxy)

# Alias
MethodCachingProxy = SelectiveCachingInstanceProxy

class InstanceProxyFactory:

    """ Factory for producing InstanceProxy-wrapped objects
        of a class.
    """
    def __init__(self,Class,interface=None):

        self.Class = Class
        self.interface = interface

    def __call__(self,*args,**kw):

        """ Return a new (wrapped) object. Pass-objects are not supported.
        """
        return InstanceProxy(apply(self.Class,args,kw),self.interface)

    def __repr__(self):

        return '<InstanceProxyFactory for %s>' % repr(self.Class)

class ReadonlyInstanceProxy(InstanceProxy):

    """ Proxy that wraps Python instances transparently in a read-only
        way.

    """
    def __init__(self,object,interface=None,passobj=None,

                 Proxy=Proxy):

        """ The interface is the same as that of the underlying C
            Proxy type.
        """
        dict = self.__dict__
        p = Proxy(object,interface,passobj)
        dict['proxy_getattr'] = p.proxy_getattr
        dict['proxy_object_repr'] = (object.__class__.__module__ + '.' +
                                     object.__class__.__name__)

    def __setattr__(self,what,to):
        raise AccessError,'write access denied'

freeze(ReadonlyInstanceProxy)

### Experimental:

class _Link:

    """ Proxy that links to an instance attribute in another object.

        XXX Should convert special lookups like __len__ to
            PyObject_* calls (for non-instance attributes).

    """
    def __init__(self,object,attrname):

        """ The interface is the same as that of the underlying C
            Proxy type.
        """
        dict = self.__dict__
        dict['proxy_object'] = object
        dict['proxy_attrname'] = attrname

    def __getattr__(self,what):
        return getattr(getattr(self.proxy_object,self.proxy_attrname),what)

    def __setattr__(self,what,to):
        setattr(getattr(self.proxy_object,self.proxy_attrname),what,to)


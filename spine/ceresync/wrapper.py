#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2005 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""Generic wrapper"""

import types

def wrap(obj, name=None, meta=type):
    if hasattr(obj, "__wrapped__"):
        return obj     

    if isinstance(obj, (types.StringType, types.NoneType,
                   types.UnicodeType, types.FileType,
                   types.IntType, types.FloatType,
                   types.LongType)):
        return obj 
    
    if name is None:
        try:
            name = obj.__name__
        except AttributeError:
            name = "%s_%x" % (obj.__class__.__name__, id(obj))
   
    def wrap_method(method_name, method):
        """Closure to keep the method name and function object"""
        def wrapped_method(self, *args ,**kwargs):   
            res = method(obj, *args, **kwargs) 
            # append methodname()
            if method_name == "__call__":
                res_name = "%s()" % name
            else:    
                res_name = "%s.%s()" % (name, method_name)
            # method result is wrapped 
            return wrap(res, res_name, meta)
        return wrapped_method

    def wrap_all_methods(obj, namespace):
        if not hasattr(obj, "__class__"):
            return
        for method_name in dir(obj.__class__):
            method = getattr(obj.__class__, method_name)        
            if (not callable(method) or method_name in("__new__",
                "__init__", "__getattribute__")):
                # Avoid re-calling __new__ and __init__
                continue
            # Register the wrapped method in OUR class
            namespace[method_name] = wrap_method(method_name, method)

    class Wrapper(object):
        __metaclass__ = meta

        def __call__(self, *args, **kwargs):
            # Self-calling
            return wrap(obj(*args, **kwargs), name+"()", meta)

        def __getattribute__(self, key):
            if key == "__wrapped__":
                return obj
            elif key == "__wrap_name__":
                return name
            if key == "__call__":
                myname = name
                print "Called __call__", myname
            else:    
                myname = name+"."+key
            # Getting attribute named key, wrap it
            return wrap(getattr(obj, key), myname, meta)
        
        # Register the wrapped method in OUR class
        wrap_all_methods(obj, locals())       

    return Wrapper()            

if __name__ == "__main__":
    class WrapMeta(type):
        def __new__(cls, name, bases, dict):
            print name
            for name,method in dict.items():
                if not callable(method):
                    continue
                dict[name] = cls.metawrap(name, method)
                print "Wrapping", name
            return type.__new__(cls, name, bases, dict)
        
        def metawrap(name, fun):
            def metawrapper(self, *args, **kwargs):
                print "Before calling", name, args
                res = fun(self, *args, **kwargs)
                print "After", name
                return res
            return metawrapper       
        metawrap = staticmethod(metawrap)          

    c = ["Nei"]
    d = wrap(c, "c", WrapMeta)
    print "d", d
    d[0]
    d[0] = "Hei"
    print d.__wrapped__
    print d.__wrap_name__
    del d[0]
    len(d)
    str(d)


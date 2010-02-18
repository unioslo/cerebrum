#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

"""Generic object wrapper.
"""

# Copyright (c) 2005 Stian Soiland <stian@soiland.no>
# 
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
# 
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 
# Author: Stian Soiland <stian@soiland.no>
# URL: http://soiland.no/software
# License: MIT

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

        def __getattribute__(self, key):
            if key == "__wrapped__":
                return obj
            elif key == "__wrap_name__":
                return name
            elif key == "__call__":
                myname = name
            else:    
                myname = name+"."+key
            # Getting attribute named key, wrap it
            return wrap(getattr(obj, key), myname, meta)
        
        # Register the wrapped method in OUR class
        wrap_all_methods(obj, locals())       

    return Wrapper()            

class WrapMeta(type):
    """Metaclass for the Wrapper classes made by wrap().
    The methods of a wrapped object will be wrapped by the classmethod
    wrapmeta. 

    When a method is called on a wrapped object, say
    obj.method("Hello", fish="Something"), this will happen:
    
    Before the real object method (obj.__wrapped__.method) is called,
    the before() classmethod is called:

        WrapMeta.before(obj ,"method", args=("hello",), 
                        kwargs={"fisWh:"Something"})
    
    The before() method can be overloaded to implement security checks,
    argument validity, add or remove parameters, etc. The before() method
    must return (args, kwargs) to be used by the real method call.
    If a security check in before() finds out this method call should
    not proceed, any exception may be thrown.


    Then, the real method call is performed on the real object, using
    the possibly modified args, kwargs returned form before(). If any
    exceptions occurs in this call, the catch() classmethod is called:
        
        WrapMeta.catch(obj ,"method", args=("hello",), 
                       kwargs={"fisWh:"Something"}, exception)
    
    The default catch() method will reraise all exceptions. An overloaded
    version could choose to instead raise an transformed exception, for
    instance translating a win32 error codes to more specific exception
    classes. The catch() method can also be overloaded to pass through
    exceptions raised, but log this to a file or display it on screen.

    If the catch() method decides to really "catch" the exception by not
    raising a new exception, it must return the result as if returned by
    the original method, for instance by calling another method in obj. 
    The outside caller will then never notice that an exception occured.
    
    
    Finally, if an exception wasn't raised in catch() - the result is
    passed on to after() before returning it to the original caller:
        
        WrapMeta.after(obj ,"method", args=("hello",), 
                       kwargs={"fisWh:"Something"}, result=res)
  
    The after() method can be overloaded to implement checks and
    transformations on the returned value. 

    """ 
    def __new__(cls, name, bases, dict):
        for name,method in dict.items():
            if not callable(method):
                continue
            dict[name] = cls.metawrap(name, method)
        return type.__new__(cls, name, bases, dict)       
    
    def before(cls, obj, name, args, kwargs):
        """Called before obj.name(*args, **kwargs) is called.
        Must return (args, kwargs) in unmodified or modified form.
        """
        return args, kwargs
    before = classmethod(before)      
    
    def catch(cls, obj, name, args, kwargs, exception):
        """Called if obj.name(*args, **kwargs) raised an exception.
        Must either re-raise exception or a derivate of the exception,
        or return an alternative result.
        """
        raise exception
    catch = classmethod(catch)        

    def after(cls, obj, name, args, kwargs, result):
        """Called after result = obj.name(*args, **kwargs) is called.
        Must return result in unmodified or unmodified form.
        """
        return result
    after = classmethod(after)       
     
    def metawrap(cls, name, fun):
        def metawrapper(obj, *args, **kwargs):
            (args, kwargs) = cls.before(obj, name, args, kwargs)
            try:
                res = fun(obj, *args, **kwargs)
            except Exception, e:
                 res = cls.catch(obj, name, args, kwargs, e)
            return cls.after(obj, name, args, kwargs, res)
        return metawrapper       
    metawrap = classmethod(metawrap)      

if __name__ == "__main__":
    class MyWrapper(WrapMeta):
        def before(cls, obj, name, args, kwargs):
            print "Before", name
            return args, kwargs
        before = classmethod(before)    
        
        def catch(cls, obj, name, args, kwargs, exception):
            print "Got exception", exception
            raise exception
        catch = classmethod(catch)    

        def after(cls, obj, name, args, kwargs, result):
            print "After", name, "got", repr(result)
            return result
        after = classmethod(after)    

    c = ["Nei"]
    d = wrap(c, "c", MyWrapper)
    print "d", d
    d[0]
    d[0] = "Hei"
    print d.__wrapped__
    print d.__wrap_name__
    del d[0]
    len(d)
    str(d)
    e = []
    print "Appending"
    d.append(e)
    print "\n\n\nWoo  f = d[0]"
    f = d[0]
    print "\n\n print f"
    print f

# arch-tag: c42934e4-d8e0-11d9-8cef-c60cb2cc6f9d

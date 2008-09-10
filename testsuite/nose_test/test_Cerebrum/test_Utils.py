#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""Testing of Utils.py's functionality."""

import re
import sys
import nose.tools
import Cerebrum.Utils as Utils


def starter(func):
    "useful for checking if the function is run by the test framework."
    def wrapper_test(*rest, **kw):
        print "\n\tstarting", func.func_name
        func(*rest, **kw)
        print "\n\tending", func.func_name

    return wrapper_test


##### Utils.format_exception_context

def test_format_exception_context_wrong_args():
    for count in range(3):
        nose.tools.assert_raises(TypeError,
           Utils.format_exception_context, *(None,)*count)

def test_format_exception_context_no_exc():
    retval = Utils.format_exception_context(None, None, None)
    assert retval == ''

def test_format_exception_context1():
    try:
        raise ValueError("aiee!")
    except ValueError:
        message = Utils.format_exception_context(*sys.exc_info())
        assert re.search("Exception <type 'exceptions.ValueError'> occured \(in context.*: aiee!",
                         message)


##### Utils.exception_wrapper

def noop(): pass
def raise1(): raise ValueError("raise1")

def test_exception_wrapper_returns_callable():
    assert hasattr(Utils.exception_wrapper(noop), '__call__')
    Utils.exception_wrapper(noop)()

def test_exception_wrapper_arg_count():
    for count in 0, 5:
        nose.tools.assert_raises(TypeError,
            Utils.exception_wrapper, *(None,)*count)
    
def test_exception_wrapper_behaviour():        
    # Ignoring all exceptions with defaults always yields None
    assert Utils.exception_wrapper(noop, None)() == None
    # Ignoring the exception raised with defaults always yields None
    assert Utils.exception_wrapper(raise1, ValueError)() == None
    # Exceptions can be given as tuples ... 
    assert Utils.exception_wrapper(raise1, (ValueError,))() == None
    # ... lists
    assert Utils.exception_wrapper(raise1, [ValueError,])() == None
    # ... or sets without affecting the result
    assert Utils.exception_wrapper(raise1, set((ValueError,)))() == None

    # Exception not matching the spec are not caught
    nose.tools.assert_raises(ValueError, 
                             Utils.exception_wrapper(raise1, AttributeError))

    # Return value with no exceptions is not altered
    assert Utils.exception_wrapper(noop, None, '')() == None
    # Return value with exceptions matches the arg
    assert Utils.exception_wrapper(raise1, ValueError, '')() == ''
# end test_exception_wrapper_behaviour


##### Utils.NotSet tests

def test_notset_single():
    """There can be only one"""
    ns1 = Utils.NotSet
    ns2 = Utils.NotSet

    assert ns1 is ns2

    ns3 = Utils._NotSet()
    assert ns1 is ns3
    assert ns1 == ns2 == ns3
# ned test_notset_single


##### Utils.dyn_import

def dyn_import_test():
    """dyn_import must make sense"""

    for name in ("Cerebrum.Utils", "Cerebrum.modules", "Cerebrum.modules.no"):
        Utils.dyn_import(name)
        assert name in sys.modules

    x = "Cerebrum.modules.no"
    assert Utils.dyn_import(x) is sys.modules[x]
# end dyn_import_tests


##### Utils.this_module

def this_module_test():
    me = sys.modules[this_module_test.__module__]

    assert Utils.this_module() is me
    assert Utils.this_module() == me
# end this_module_test
    


##### Utils.separate_entries

#!/usr/bin/env python

"""This module can be used to extract doc from python source."""

import sys
import re
import traceback
import getopt
import os
import inspect
import pprint
from pydoc import importfile, resolve, describe, isdata

pp = pprint.PrettyPrinter(indent=4)
func_template = ("def <func_name>(<args>)\n"
                 "\n<doc>")

def find_func_in_class(name, tmp_obj, as_regexp=False):
    """Find a function in a class"""
    attrs = inspect.classify_class_attrs(tmp_obj)
    ret = []
    for a in attrs:
        if a[2] is tmp_obj:
            if not a[1] in ('method', 'static method'):
                continue
            func_ref = a[-1]
            if a[1] == 'static method':
                func_ref = getattr(tmp_obj, a[0])
            if as_regexp:
                if not re.match(name, a[0]):
                    continue
            elif name == a[0]:
                return [ (a[0], func_ref) ]
            # print a
            ret.append( (a[0], func_ref) )
    return ret

def find_func(name, tmp_obj, as_regexp=False):
    ret = []
    if name.find(":") != -1:
        class_name, name = name.split(":", 1)
        tmp_obj = find_class(class_name, tmp_obj)
        return find_func_in_class(name, tmp_obj, as_regexp)

    for key, value in inspect.getmembers(tmp_obj, inspect.isroutine):
        if as_regexp:
            if re.match(name, key):
                if inspect.ismethod(value) or inspect.isfunction(value):
                    ret.append((key, value))
        elif key == name:
            return [(key, value)]
    return ret

def find_class(name, tmp_obj):
    for key, value in inspect.getmembers(tmp_obj, inspect.isclass):
        if key == name:
            return value

def dump_func_doc(name, func_obj):
    argspec = inspect.getargspec(func_obj)
    args = argspec[0]
    for i in range(len(argspec[-1] or '')):
        tmp = argspec[-1][-(i+1)]
        if isinstance(tmp, (int, float)):
            tmp = str(tmp)
        else:
            tmp = '"%s"' % tmp
        args[-(i+1)] += "="+tmp
    if argspec[1]:
        args.append('*'+argspec[1])
    if argspec[2]:
        args.append('**'+argspec[2])
    doc = inspect.getdoc(func_obj) or inspect.getcomments(func_obj)
    ret = func_template
    ret = ret.replace("<func_name>", name)
    ret = ret.replace("<args>", ", ".join(args))
    ret = ret.replace("<doc>", doc)
    print ret
            
def usage(exitcode=0):
    print """ext_doc.py [options]
    --module  <path-to_py_file>
    --func  [class]:func
    --class_doc class
    --module_doc
    --func_template template_file
    TBD: det er sikkert fint om noen argumenter kan repeteres...

    Eksempler:
      ./ext_doc.py  --module ./ext_doc.py --module_doc
      ./ext_doc.py  --module ./ext_doc.py --class_doc foo
      ./ext_doc.py  --module ./ext_doc.py --func foo:bar
      ./ext_doc.py  --module ./ext_doc.py --func find_func_in_class
"""
    sys.exit(exitcode)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '',
                                   ['test', 'module=', 'func=',
                                    'class_doc=', 'module_doc',
                                    'as_regexp=', 'func_template='])
    except getopt.GetoptError:
        usage(1)

    as_regexp = True
    for opt, val in opts:
        if opt == '--help':
            usage()
        elif opt == '--test':
            test()
        elif opt == '--module':
            module = importfile(val)
            module_ref, module_name = resolve(module)
        elif opt == '--as_regexp':
            as_regexp = int(val)
        elif opt == '--func':
            funcs = find_func(val, module_ref, as_regexp=as_regexp)
            for f_name, f_ref in funcs:
                dump_func_doc(f_name, f_ref)
        elif opt == '--class_doc':
            class_ref = find_class(val, module_ref)
            if not class_ref:
                print "Unknown class: ", val
            else:
                doc = inspect.getdoc(class_ref) or inspect.getcomments(class_ref)
                print doc
        elif opt == '--module_doc':
            print inspect.getdoc(module_ref)
        elif opt == '--func_template':
            global func_template
            file = open(val, "r")
            func_template = "".join(file.readlines())

######### Misc. junk that will be removed once the code is #########
########################### goodenough #############################
        
class supfoo(object):
    """Superclass to check that we can hide its doc"""
    def suptest(self, test):
        pass

class foo(supfoo):
    """Test-class for doc extraction"""

    def __init__(self, test, mest, foo="bar", *mer, **endamer):
        """dette er
        constructoren til denne <>greia.
          litt indent
        normal"""
        pass

    ## Litt foobar
    # test hei
    def bar(self, test, foo="bar", hei="mei"):
        pass

    def gazonk(test):
        "burgle urge"
        pass
    gazonk = staticmethod(gazonk)

def dump_object(name, tmp_obj):
    print ">>>>>>>>>>>>>>>>>>>>>>>>>>", name, tmp_obj
    print describe(tmp_obj)

    # From line 921, method docmodule:
    classes = []
    for key, value in inspect.getmembers(tmp_obj, inspect.isclass):
        if (inspect.getmodule(value) or tmp_obj) is tmp_obj:
            classes.append((key, value))
            dump_object(key, value)
    funcs = []
    for key, value in inspect.getmembers(tmp_obj, inspect.isroutine):
        if inspect.isbuiltin(value) or inspect.getmodule(value) is tmp_obj:
            funcs.append((key, value))
    data = []
    for key, value in inspect.getmembers(tmp_obj, isdata):
        if key not in ['__builtins__', '__doc__']:
            data.append((key, value))
    methods = []
    for key, value in inspect.getmembers(tmp_obj, inspect.ismethod):
        if key not in ['__builtins__', '__doc__']:
            methods.append((key, value))

    print "C:", classes
    print "\nF:", funcs
    print "\nD:", data
    print "\nM:", methods
    for m in methods:
        print inspect.getargspec(m[1]), inspect.getdoc(m[1]), inspect.getcomments(m[1])
    print "<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"

def test():
    module = importfile("ext_doc.py")
    tmp_obj, name = resolve(module)
    print "GOT_C: ", find_class("foo", tmp_obj)
    print "GOT_F: ", find_func("find_func", tmp_obj)
    print "GOT_CF: ", find_func("foo:bar", tmp_obj)
    print "GOT_RF: ", find_func("find_.*", tmp_obj, as_regexp=True)
    print "GOT_CRF: \n", find_func("foo:.*", tmp_obj, as_regexp=True)
    funcs = find_func("foo:.*", tmp_obj, as_regexp=True)
    for f_name, f_ref in funcs:
        dump_func_doc(f_name, f_ref)
    dump_object(name, tmp_obj)

if __name__ == '__main__':
    main()

# arch-tag: ae5bc75a-a31c-4ece-a6ff-000342a8bea9

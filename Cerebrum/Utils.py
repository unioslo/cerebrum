# Copyright 2002 University of Oslo, Norway
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

"""

"""

import sys
import re

def dyn_import(name):
    """Dynamically import python module ``name``."""
    try:
        mod = __import__(name)
        components = name.split(".")
        for comp in components[1:]:
            mod = getattr(mod, comp)
        return mod
    except AttributeError, mesg:
        raise ImportError, mesg

def this_module():
    """Return module object of the caller."""
    caller_frame = sys._getframe(1)
    globals = caller_frame.f_globals
    #
    # If anyone knows a better way (e.g. one that isn't based on
    # iteration over sys.modules) to get at the module object
    # corresponding to a frame/code object, please do tell!
    correct_mod = None
    for mod in filter(None, sys.modules.values()):
        if globals is mod.__dict__:
            assert correct_mod is None
            correct_mod = mod
    assert correct_mod is not None
    return correct_mod

def separate_entries(rows, *predicates):
    """Separate ``rows`` into (keep, reject) tuple based on ``predicates``.

    The ``rows`` argument should be a sequence of db_row.py-generated
    objects.  Each predicate in ``predicate`` should be a (key, value)
    tuple.  The key must be a valid attribute name of each row object.

    The rows are separated according to these rules:
    1. By default rows go to the keep list.
    2. If a predicate's value is None, that predicate is ignored.
    3. Compare each predicate's value with the attribute named key in
       each row.  Rows matching all predicates go to the keep list,
       while the rest end up in the reject list.

    """
    keep = []
    reject = []
    for row in rows:
        ok = 1
        for key, value in predicates:
            if value is None:
                continue
            ok = (row[key] == value)
            if not ok:
                break
        if ok:
            keep.append(row)
        else:
            reject.append(row)
    return (keep, reject)

def keep_entries(rows, *predicates):
    """Return the 'keep' part of separate_entries() return value."""
    return separate_entries(rows, *predicates)[0]

def reject_entries(rows, *predicates):
    """Return the 'reject' part of separate_entries() return value."""
    return separate_entries(rows, *predicates)[1]

def mangle_name(classname, attr):
    """Do 'name mangling' for attribute ``attr`` in class ``classname``."""
    if not classname or not isinstance(classname, str):
        raise ValueError, "Not a valid class name: '%s'" % classname
    if attr.startswith("__") and not attr.endswith("__"):
        # Attribute name starts with at least two underscores, and
        # ends with at most one underscore.
        #
        # Strip leading underscores from classname.
        for i in range(len(classname)):
            if classname[i] <> "_":
                classname = classname[i:]
                break
        if classname and classname[0] == "_":
            # classname is all underscores.  No mangling.
            return attr
        return '_' + classname + attr
    return attr


class auto_super(type):
    """Metaclass adding a private class variable __super, set to super(cls).

    Any class C of this metaclass can use the shortcut
      self.__super.method(args)
    instead of
      super(C, self).method(args)

    Besides being slightly shorter to type, this should also be less
    error prone -- there's no longer a need to remember that the first
    argument to super() must be changed whenever one copies its
    invocation into a new class.

    NOTE: As the __super trick relies on Pythons name-mangling
          mechanism for class private identifiers, it won't work if a
          subclass has the same name as one of its base classes.  This
          is a situation that hopefully won't be very common; however,
          if such a situation does arise, the subclass's definition
          will fail, raising a ValueError.

    """
    def __init__(cls, name, bases, dict):
        super(auto_super, cls).__init__(name, bases, dict)
        attr = mangle_name(name, '__super')
        if hasattr(cls, attr):
            # The class-private attribute slot is already taken; the
            # most likely cause for this is a base class with the same
            # name as the subclass we're trying to create.
            raise ValueError, \
                  "Found '%s' in class '%s'; name clash with base class?" % \
                  (attr, name)
        setattr(cls, attr, super(cls))


class mark_update(auto_super):
    """Metaclass marking objects as 'updated' per superclass.

    This metaclass looks in the class attributes ``__read_attr__`` and
    ``__write_attr__`` (which should be tuples of strings) to
    determine valid attributes for that particular class.  The
    attributes stay valid in subclasses, but assignment to them are
    handled by code objects that live in the class where they were
    defined.

    The following class members are automatically defined for classes
    with this metaclass:

    ``__updated`` (class private variable):
      Set to ``False`` initially; see description of ``__setattr__``.

    ``__setattr__`` (Python magic for customizing attribute assignment):
      * When a 'write' attribute gets assigned to, the appropriate
        class's ``__updated`` attribute gets set.

      * 'Read' attributes can only be assigned to if there hasn't
        already been defined any attribute by that name on the
        instance.
        This means that initial assignment will work, but plain
        reassignment will fail.  To perform a reassignment one must
        delete the attribute from the instance (e.g. by using ``del``
        or ``delattr``).
      NOTE: If a class has an explicit definition of ``__setattr__``,
            that class will retain that definition.

    ``__new__``:
      Make sure that instances get ``__updated`` attributes for the
      instance's class and for all of its base classes.
      NOTE: If a class has an explicit definition of ``__new__``,
            that class will retain that definition.

    ``__slots__``:
      Set automatically from ``__write_attr__`` and ``__read_attr__``.
      NOTE: If a class has an explicit definition of ``__slots__``,
            this metaclass will only add to the slots already defined.

    ``__read_attr__`` and ``__write_attr__``:
      Gets overwritten with tuples holding the name-mangled versions
      of the names they initially held.  If there was no initial
      definition, the attribute is set to the empty tuple.

    Additionally, mark_update is a subclass of the auto_super
    metaclass; hence, all classes with metaclass mark_update will also
    be subject to the functionality provided by the auto_super
    metaclass.

    A quick (and rather nonsensical) example of usage:

    >>> class A(object):
    ...     __metaclass__ = mark_update
    ...     __write_attr__ = ('breakfast',)
    ...     def print_updated(self):
    ...         if self.__updated:
    ...             print  'A'
    ... 
    >>> class B(A):
    ...     __write_attr__ = ('egg', 'sausage', 'bacon')
    ...     __read_attr__ = ('spam',)
    ...     def print_updated(self):
    ...         if self.__updated:
    ...             print  'B'
    ...         self.__super.print_updated()
    ... 
    >>> b = B()
    >>> b.breakfast = 'vroom'
    >>> b.spam = False
    >>> b.print_updated()
    A
    >>> b.egg = 7
    >>> b.print_updated()
    B
    A
    >>> b.spam = True
    Traceback (most recent call last):
      File "<stdin>", line 1, in ?
      File "Cerebrum/Utils.py", line 237, in __setattr__
        raise AttributeError, \
    AttributeError: Attribute 'spam' is read-only.
    >>> del b.spam 
    >>> b.spam = True
    >>> b.spam
    1
    >>> b.egg
    7
    >>> b.sausage
    Traceback (most recent call last):
      File "<stdin>", line 1, in ?
    AttributeError: sausage
    >>> 

    """
    def __new__(cls, name, bases, dict):
        read = [mangle_name(name, x) for x in
                dict.get('__read_attr__', ())]
        dict['__read_attr__'] = read
        write = [mangle_name(name, x) for x in
                 dict.get('__write_attr__', ())]
        dict['__write_attr__'] = write
        mupdated = mangle_name(name, '__updated')
        msuper = mangle_name(name, '__super')

        # Define the __setattr__ method that should be used in the
        # class we're creating.
        def __setattr__(self, attr, val):
##            print "%s.__setattr__:" % name, self, attr, val
            if attr in read:
                # Only allow setting if attr has no previous
                # value.
                if hasattr(self, attr):
                    raise AttributeError, \
                          "Attribute '%s' is read-only." % attr
            elif attr in write:
                if hasattr(self, attr) and val == getattr(self, attr):
                    # No change, don't set __updated.
                    return
            elif attr <> mupdated:
                # This attribute doesn't belong in this class; try the
                # base classes.
                return getattr(self, msuper).__setattr__(attr, val)
            # We're in the correct class, and we've established that
            # it's OK to set the attribute.  Short circuit directly to
            # object's __setattr__, as that's where the attribute
            # actually gets its new value set.
##            print "%s.__setattr__: setting %s = %s" % (self, attr, val)
            object.__setattr__(self, attr, val)
            if attr in write:
                setattr(self, mupdated, True)
        dict.setdefault('__setattr__', __setattr__)

        def __new__(cls, *args, **kws):
            # Get a bound super object.
            sup = getattr(cls, msuper).__get__(cls)
            # Call base class's __new__() to perform initialization
            # and get an instance of this class.
            obj = sup.__new__(cls, *args, **kws)
            # Add a default for this class's __updated attribute.
            setattr(obj, mupdated, False)
            return obj
        dict.setdefault('__new__', __new__)

        slots = list(dict.get('__slots__', []))
        for slot in read + write + [mupdated]:
            slots.append(slot)
        dict['__slots__'] = tuple(slots)

        return super(mark_update, cls).__new__(cls, name, bases, dict)

class XMLHelper(object):
    xml_hdr = '<?xml version="1.0" encoding="ISO-8859-1"?>\n'

    def conv_colnames(self, cols):
        "Strip tablename prefix from column name"
        prefix = re.compile(r"[^.]*\.")
        for i in range(len(cols)):
            cols[i] = re.sub(prefix, "", cols[i]).lower()
        return cols

    def xmlify_dbrow(self, row, cols, tag, close_tag=1, extra_attr=None):
        if close_tag:
            close_tag = "/"
        else:
            close_tag = ""
        assert(len(row) == len(cols))
        if extra_attr is not None:
            extra_attr = " " + " ".join(["%s=%s" % (k, self.escape_xml_attr(extra_attr[k]))
                                         for k in extra_attr.keys()])
        else:
            extra_attr = ''
        return "<%s " % tag + (
            " ".join(["%s=%s" % (cols[i], self.escape_xml_attr(row[i]))
                      for i in range(len(cols)) if row[i] is not None])+
            "%s%s>" % (extra_attr, close_tag))

    def escape_xml_attr(self, a):
        # TODO:  Check XML-spec to find out what to quote
        a = str(a).replace('&', "&amp;")
        a = a.replace('"', "&quot;")
        a = a.replace('<', "&lt;")
        a = a.replace('>', "&gt;")
        return '"%s"' % a

# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
Object metaclasses used in database objects.


py:class:`AutoSuper`
--------------------
Classes with an AutoSuper metaclass will automatically have a mangled
``__super`` attribute that points to the next parent class.


py:class:`MarkUpdate`
---------------------
Classes with an AutoSuper metaclass will have custom management of certain
attributes.

Example:

>>> class Breakfast(MarkUpdateMixin):
...     __write_attr__ = ('bread_type',)
...     def get_updated(self):
...         return tuple(self.__updated)
...
>>> class MoreBreakfast(Breakfast):
...     __write_attr__ = ('egg', 'sausage', 'bacon')
...     __read_attr__ = ('spam',)
...     def get_updated(self):
...         return self.__super.get_updated() + tuple(self.__updated)
...
>>> b = MoreBreakfast()
>>> b.bread_type = 'sour dough'
>>> b.spam = False
>>> b.get_updated()
('bread_type',)
>>> b.egg = 7
>>> b.get_updated()
('bread_type', 'egg')
>>> b.spam = True  # cannot modify a read-only attr
Traceback (most recent call last):
    ...
AttributeError: attribute 'spam' is read-only
>>> del b.spam  # read-only attrs can only be updated if they are unset
>>> b.spam = True
>>> b.spam
True
>>> b.egg
7
>>> b.sausage  # we never set this attribute
Traceback (most recent call last):
    ...
AttributeError: 'MoreBreakfast' object has no attribute 'sausage'
>>>

History
-------
py:func:`_mangle_name`, py:class:`AutoSuper` and py:class:`MarkUpdate` has been
moved from ``Cerebrum.Utils``, where they were named ``_mangle_name``,
``auto_super`` and ``mark_update``.

The original implementation of these classes can be seen in:

    Commit: 7ddda8566b45b576ef0e3c288c00a9fed5b215bc
    Date:   Wed Dec 16 11:51:09 2020 +0100
"""
import six


def is_str(x):
    """Checks if a given variable is a string, but not a unicode string."""
    return isinstance(x, bytes)


def _mangle_name(classname, attr):
    """Do 'name mangling' for attribute ``attr`` in class ``classname``."""
    if not (classname and is_str(classname)):
        raise ValueError("Invalid class name string: '%s'" % classname)
    # Attribute name starts with at least two underscores, and
    # ends with at most one underscore and is not all underscores
    if (attr.startswith("__") and
            not attr.endswith("__") and
            classname.count("_") != len(classname)):
        # Strip leading underscores from classname.
        return "_" + classname.lstrip("_") + attr
    return attr


class auto_super(type):  # noqa: N801
    """
    Metaclass adding a private class variable __super, set to super(cls).

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

    def __init__(cls, name, bases, dict):  # noqa: N805
        super(auto_super, cls).__init__(name, bases, dict)
        attr = _mangle_name(name, '__super')
        if hasattr(cls, attr):
            # The class-private attribute slot is already taken; the
            # most likely cause for this is a base class with the same
            # name as the subclass we're trying to create.
            raise ValueError(
                "Found '%s' in class '%s'; name clash with base class?" %
                (attr, name))
        setattr(cls, attr, super(cls))


AutoSuper = auto_super


class AutoSuperMixin(six.with_metaclass(AutoSuper), object):
    """ An object subclass with the AutoSuper metaclass. """
    pass


class mark_update(auto_super):  # noqa: N801
    """
    Metaclass marking objects as 'updated' per superclass.

    This metaclass looks in the class attributes ``__read_attr__`` and
    ``__write_attr__`` (which should be tuples of strings) to
    determine valid attributes for that particular class.  The
    attributes stay valid in subclasses, but assignment to them are
    handled by code objects that live in the class where they were
    defined.

    The following class members are automatically defined for classes
    with this metaclass:

    ``__updated`` (class private variable):
      Set to the empty list initially; see description of ``__setattr__``.

    ``__setattr__`` (Python magic for customizing attribute assignment):
      * When a 'write' attribute has its value changed, the attribute
        name is appended to the list in the appropriate class's
        ``__updated`` attribute.

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

    ``clear'':
      Reset all the ``mark_update''-relevant attributes of an object
      to their default values.
      NOTE: If a class has an explicit definition of ``clear'', that
            class will retain that definition.

    ``__read_attr__`` and ``__write_attr__``:
      Gets overwritten with tuples holding the name-mangled versions
      of the names they initially held.  If there was no initial
      definition, the attribute is set to the empty tuple.

    ``__xerox__``:
      Copy all attributes that are valid for this instance from object
      given as first arg.

    ``__slots__``:
      If a class has an explicit definition of ``__slots__``, this
      metaclass will add names from ``__write_attr__`` and
      ``__read_attr__`` to the class's slots.  Classes without any
      explicit ``__slots__`` are not affected by this.

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
    ...             print('A')
    ...
    >>> class B(A):
    ...     __write_attr__ = ('egg', 'sausage', 'bacon')
    ...     __read_attr__ = ('spam',)
    ...     def print_updated(self):
    ...         if self.__updated:
    ...             print('B')
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
    True
    >>> b.egg
    7
    >>> b.sausage
    Traceback (most recent call last):
      File "<stdin>", line 1, in ?
    AttributeError: sausage
    >>>

    """
    def __new__(cls, name, bases, dict):
        read = [_mangle_name(name, x) for x in
                dict.get('__read_attr__', ())]
        dict['__read_attr__'] = read
        write = [_mangle_name(name, x) for x in
                 dict.get('__write_attr__', ())]
        dict['__write_attr__'] = write
        mupdated = _mangle_name(name, '__updated')
        msuper = _mangle_name(name, '__super')

        # Define the __setattr__ method that should be used in the
        # class we're creating.
        def __setattr__(self, attr, val):  # noqa: N802
            # print "%s.__setattr__:" % name, self, attr, val
            if attr in read:
                # Only allow setting if attr has no previous
                # value.
                if hasattr(self, attr):
                    raise AttributeError("Attribute '%s' is read-only." % attr)
            elif attr in write:
                if hasattr(self, attr) and val == getattr(self, attr):
                    # No change, don't set __updated.
                    return
            elif attr != mupdated:
                # This attribute doesn't belong in this class; try the
                # base classes.
                return getattr(self, msuper).__setattr__(attr, val)
            # We're in the correct class, and we've established that
            # it's OK to set the attribute.  Short circuit directly to
            # object's __setattr__, as that's where the attribute
            # actually gets its new value set.
            # print "%s.__setattr__: setting %s = %s" % (self, attr, val)
            object.__setattr__(self, attr, val)
            if attr in write:
                getattr(self, mupdated).append(attr)
        dict.setdefault('__setattr__', __setattr__)

        def __new__(cls, *args, **kws):  # noqa: N802
            # Get a bound super object.
            sup = getattr(cls, msuper).__get__(cls)
            # Call base class's __new__() to perform initialization
            # and get an instance of this class.
            obj = sup.__new__(cls)
            # Add a default for this class's __updated attribute.
            setattr(obj, mupdated, [])
            return obj
        dict.setdefault('__new__', __new__)

        dont_clear = dict.get('dontclear', ())

        def clear(self):
            getattr(self, msuper).clear()
            for attr in read:
                if hasattr(self, attr) and attr not in dont_clear:
                    delattr(self, attr)
            for attr in write:
                if attr not in dont_clear:
                    setattr(self, attr, None)
            setattr(self, mupdated, [])
        dict.setdefault('clear', clear)

        def __xerox__(self, from_obj, reached_common=False):  # noqa: N802
            """Copy attributes of ``from_obj`` to self (shallowly).

            If self's class is the same as or a subclass of
            ``from_obj``s class, all attributes are copied.  If self's
            class is a base class of ``from_obj``s class, only the
            attributes appropriate for self's class (and its base
            classes) are copied.

            """
            if not reached_common and \
               name in [c.__name__ for c in from_obj.__class__.__mro__]:
                reached_common = True
            try:
                super_xerox = getattr(self, msuper).__xerox__
            except AttributeError:
                # We've reached a base class that doesn't have this
                # metaclass; stop recursion.
                super_xerox = None
            if super_xerox is not None:
                super_xerox(from_obj, reached_common)
            if reached_common:
                for attr in read + write:
                    if hasattr(from_obj, attr):
                        setattr(self, attr, getattr(from_obj, attr))
                setattr(self, mupdated, getattr(from_obj, mupdated))
        dict.setdefault('__xerox__', __xerox__)

        if hasattr(dict, '__slots__'):
            slots = list(dict['__slots__'])
            for slot in read + write + [mupdated]:
                slots.append(slot)
            dict['__slots__'] = tuple(slots)

        return super(mark_update, cls).__new__(cls, name, bases, dict)


MarkUpdate = mark_update


class MarkUpdateMixin(six.with_metaclass(MarkUpdate), object):
    """ An object subclass with the MarkUpdate metaclass.  """

    # The base class that applies MarkUpdate *must* implement clear().
    # TODO: Fix MarkUpdate so that super().clear() is only called if defined.
    def clear(self):
        pass


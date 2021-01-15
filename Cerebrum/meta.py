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


def _mangle_name(classname, attr):
    """Get a *mangled* attribute name for a given class.
    """
    if not (classname and isinstance(classname, str)):
        raise ValueError("Invalid class name string: '%s'" % classname)
    # Attribute name starts with at least two underscores, and
    # ends with at most one underscore and is not all underscores
    if (attr.startswith("__") and
            not attr.endswith("__") and
            classname.count("_") != len(classname)):
        # Strip leading underscores from classname.
        return "_" + classname.lstrip("_") + attr
    return attr


class AutoSuper(type):
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
        super(AutoSuper, cls).__init__(name, bases, dict)
        attr = _mangle_name(name, '__super')
        if hasattr(cls, attr):
            # The class-private attribute slot is already taken; the
            # most likely cause for this is a base class with the same
            # name as the subclass we're trying to create.
            raise ValueError(
                "Found '%s' in class '%s'; name clash with base class?" %
                (attr, name))
        setattr(cls, attr, super(cls))


class AutoSuperMixin(six.with_metaclass(AutoSuper), object):
    """ An object subclass with the AutoSuper metaclass. """
    pass


class MarkUpdate(AutoSuper):
    """
    Metaclass marking objects as 'updated' per superclass.

    This metaclass looks in the class attributes ``__read_attr__`` and
    ``__write_attr__`` (which should be tuples of strings) to
    determine valid attributes for that particular class.  The
    attributes stay valid in subclasses, but assignment to them are
    handled by code objects that live in the class where they were
    defined.

    These special class attributes are used by MarkUpdate:

    ``__read_attr__``
        A tuple of attribute names that should be considered read-only.

        - Read-only attributes cannot be changed (but can be initially set if
          previously undefined).
        - Read-only attributes are cleared when ``clear()`` is called on the
          resulting class.
        - Note that read-only attributes *can* be modified by calling ``del
          <obj>.<attr>`` first.

    ``__write_attr__``
        A tuple of attribute names that should be considered read-write.

        Write-attributes are typically handled by some kind of flush method in
        the class definition.  One example of a flush method is the
        ``write_db()`` method of db-entities.

        - Write-attributes can be changed.  When changed, the attribute name is
          added to the ``__updated`` list.
        - Write-attributes are cleared just like read-attributes.

    ``__updated``
        A list of write-attributes that has been modified.

        Whenever a write-attribute is changed, its attribute name is added to
        the ``__updated`` list.  This ``__updated`` list is typically cleared
        by flush-logic (e.g. ``write_db()`` for db-entities), and is also
        cleared by ``clear()``.

    ``__slots__``
        ``__slots__`` are updated with ``__read_attr__`` and
        ``__write_attr__``.  This only applies for classes that explicitly
        defines ``__slots__``.

    ``dontclear``
        An optional tuple of attribute names to omit when calling ``clear()``.


    MarkUpdate classes also has a few extra methods:

    ``__xerox__``
        Copies read/write attributes from another, similar object.

    ``clear``
        Removes/clears all ``__read_attr__`` and ``__write_attr__`` attributes
        in the object, and empties the ``__updated`` list.

    ``__setattr__``
        Implements the ``__read_attr__``, ``__write_attr__``, and ``__updated``
        logic.

    ``__new__``
        Implements ``__read_attr__``, ``__write_attr__``, and ``__updated``
        initialization.

    Be careful not to override/break these methods when implmenting a class
    with MarkUpdate.

    A quick (and rather nonsensical) example of usage:


    """
    def __new__(cls, name, bases, dct):

        # mangled attribute names:
        read_attrs = dct['__read_attr__'] = tuple(
            _mangle_name(name, attr)
            for attr in dct.get('__read_attr__', ()))

        write_attrs = dct['__write_attr__'] = tuple(
            _mangle_name(name, attr)
            for attr in dct.get('__write_attr__', ()))

        updated_attr = _mangle_name(name, '__updated')
        auto_super_attr = _mangle_name(name, '__super')

        def mark_update_setattr(self, attr, val):
            """ __setattr__ implementation for MarkUpdate classes. """
            if attr in read_attrs:
                if hasattr(self, attr):
                    raise AttributeError("attribute '%s' is read-only" % attr)
            elif attr in write_attrs:
                if hasattr(self, attr) and val == getattr(self, attr):
                    # No change, don't set __updated.
                    return
            elif attr != updated_attr:
                # This attribute doesn't belong in this class; try the
                # base classes.
                return getattr(self, auto_super_attr).__setattr__(attr, val)

            # We're in the correct class, and we've established that
            # it's OK to set the attribute.  Short circuit directly to
            # ``object.__setattr__()``, as that's where the attribute
            # actually gets its new value set.
            object.__setattr__(self, attr, val)
            if attr in write_attrs:
                getattr(self, updated_attr).append(attr)
        dct.setdefault('__setattr__', mark_update_setattr)

        def mark_update_new(cls, *args, **kws):  # noqa: N807
            """ __new__ implementation for MarkUpdate classes. """
            # Get a bound super object:
            super_cls = getattr(cls, auto_super_attr).__get__(cls)
            # Call base class's __new__() to perform initialization
            # and get an instance of this class:
            obj = super_cls.__new__(cls)
            # Initialize a mangled __updated list for this class:
            setattr(obj, updated_attr, [])
            return obj
        dct.setdefault('__new__', mark_update_new)

        dont_clear = dct.get('dontclear', ())

        def mark_update_clear(self):
            """ Clear attributes managed by MarkUpdate. """
            getattr(self, auto_super_attr).clear()

            # clear the __read_attr__ attributes of this class
            for attr in read_attrs:
                if hasattr(self, attr) and attr not in dont_clear:
                    delattr(self, attr)

            # clear the __write_attr__ attributes of this class
            for attr in write_attrs:
                if attr not in dont_clear:
                    setattr(self, attr, None)

            # reset the __updated list of this class
            setattr(self, updated_attr, [])
        dct.setdefault('clear', mark_update_clear)

        def mark_update_xerox(self, from_obj, _reached_common=False):
            """ Copy attributes of ``from_obj`` to self (shallowly).

            If self's class is the same as or a subclass of
            ``from_obj``s class, all attributes are copied.  If self's
            class is a base class of ``from_obj``s class, only the
            attributes appropriate for self's class (and its base
            classes) are copied.

            """
            if (not _reached_common and
                    name in [c.__name__ for c in from_obj.__class__.__mro__]):
                _reached_common = True
            try:
                super_xerox = getattr(self, auto_super_attr).__xerox__
            except AttributeError:
                # We've reached a base class that doesn't have this
                # metaclass; stop recursion.
                super_xerox = None

            if super_xerox is not None:
                super_xerox(from_obj, _reached_common)
            if _reached_common:
                for attr in read_attrs + write_attrs:
                    if hasattr(from_obj, attr):
                        setattr(self, attr, getattr(from_obj, attr))
                setattr(self, updated_attr, getattr(from_obj, updated_attr))
        dct.setdefault('__xerox__', mark_update_xerox)

        if '__slots__' in dct:
            # update __slots__ with relevant attrs
            tmp_slots = list(dct['__slots__'])
            for attr in read_attrs + write_attrs + (updated_attr,):
                if attr not in tmp_slots:
                    tmp_slots.append(attr)
            dct['__slots__'] = tuple(tmp_slots)

        return super(MarkUpdate, cls).__new__(cls, name, bases, dct)


class MarkUpdateMixin(six.with_metaclass(MarkUpdate), object):
    """ An object subclass with the MarkUpdate metaclass.  """

    # The base class that applies MarkUpdate *must* implement clear().
    # TODO: Fix MarkUpdate so that super().clear() is only called if defined.
    def clear(self):
        pass


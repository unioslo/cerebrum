
# -*- coding: utf-8 -*-
#
# Copyright 2017 University of Oslo, Norway
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
Context managers for the entity data.

Keeps objects in a pool, and calls clear() on them.

>>> from Cerebrum.utils.context import entity, entitise
>>> def dostuff(ac):
...     print(ac.entity_id)
>>>
>>> with entity.account.find_by_name(x) as ac:
...     dostuff(ac)
>>> for ac, row in entitise(entity.list_all_with_type(self, co.entity_account),
                            entity.account.find):
...     dostuff(ac)

To use an existing database object, set `entity.db` to point to it.
"""

from Cerebrum.Utils import Factory


class EntityContextManager(object):
    """Context manager that implements the context manager fields."""

    def __init__(self, context, meth, findargs, findkw):
        """Init normally called by EntityContext object.
        :param context: EntityContext object
        :param meth: Method name (e.g. find)
        :param findargs and findkw: args to find method
        """
        self.context = context
        self.meth = meth
        self.args = findargs
        self.kw = findkw
        self.item = None

    def __enter__(self):
        """Enter manager.
        Fetches object from pool, calls the find method and returns the object.
        """
        self.item = item = self.context._get_instance()
        getattr(item, self.meth)(*self.args, **self.kw)
        return item

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit manager.
        On exception, does nothing.
        Otherwise calls clear() and returns object to pool.
        Always returns None so that exceptions are propagated
        """
        if exc_type is None:
            self.item.clear()
            self.context.pool.append(self.item)
        self.item = None


class EntityContext(object):
    """Context manager for entity objects.
    Will make sure clear is called for objects, and only creates
    new instances when needed.
    """

    def __init__(self, classname, db=None):
        """Initialize context manager.
        :classname: Name to call Factory.get() with.
        """
        self.classname = classname
        self.db = db
        self.pool = []
        self.cls = None

    def _get_instance(self):
        """Get object from pool, or create new object."""
        try:
            return self.pool.pop()
        except:
            if self.cls is None:
                self.cls = Factory.get(self.classname)
                if self.db is None:
                    self.db = Factory.get('Database')()
            return self.cls(self.db)

    def __getattr__(self, attr):
        """Returns a function that creates a manager."""
        def context(*args, **kw):
            return EntityContextManager(self, attr, args, kw)
        return context


class ContextPool(object):
    """Manager object to facilitate the use of contexts.

    Used like::

        entity = ContextPool()
        with entity.person.find(42) as person:
            assert person.entity_id == 42
        assert not hasattr(person, 'entity_id')

    Here, person is found in Factory.type_component_map, but one can
    also use Entity, Person, Account, etc., too.

    If you want to use an existing database connection, do::

        Cerebrum.utils.context.entity.db = db
    """

    def __init__(self, db=None):
        self.db = db

    def __getattr__(self, attr):
        val = EntityContext(Factory.type_component_map.get(attr, attr), self.db)
        setattr(self, attr, val)
        return val


entity = ContextPool()


def entitise(iterator, manager=None, key=0):
    """Like enumerate, just for entity.

    The manager should represent a find operation, e.g.
    entity.account.find_by_name.

    :param iterator: Some iterable object, whose items has __getitem__.
    :param manager: A callable, producing a context manager
    :param key: Key into the iterable's item
    :yield: A sequence of bound entities, and row
    """

    if manager is None:
        manager = entity.entity.find
    for item in iterator:
        with manager(item[key]) as obj:
            yield obj, item

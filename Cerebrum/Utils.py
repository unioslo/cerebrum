# -*- coding: utf-8 -*-
#
# Copyright 2002-2026 University of Oslo, Norway
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
This module contains a number of core utilities used everywhere in the tree.

TODO
-----
This module should be removed, and all helpers moved into more suitable
modules:

`NotSet`
    This singleton should probably be moved into a separate module in
    `Cerebrum`, along with other singletons (a few scripts and modules creates
    unique types or objects to be used as a singleton).

`Factory`
    Should have its own module, e.g. `Cerebrum.factory`

`argument_to_sql`
    This should be moved to e.g. `Cerebrum.database.query_utils`.

`prepare_string`
    All use of this function should be replaced by `Pattern` or
    `pattern_helper` from `Cerebrum.database.query_utils`.

`make_timer`
    Should probably relocated to somewhere in `Cerebrum.logutils`.

    This helper has a lot of duplicates with similar functionality in other
    scripts and modules.  All of these should probably be merged together, or
    placed into the same module.

Compatibility imports
    We should find all current use of the compatibility imports, and update to
    the new, canonical placements.


History
-------
Some functionality has already been relocated, but with compatibility imports
here, as they are widely used.

If you're looking for ``log_and_spawn_output``, then this has been replaced by
similar functionality in `Cerebrum.utils.subproc`.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import sys
import time

import six

import cereconf


# Compatibility imports / relocated classes and functions
import Cerebrum.meta
import Cerebrum.utils.module
import Cerebrum.utils.secrets
import Cerebrum.utils.text_compat

if sys.version_info >= (3, 3):
    from collections.abc import Iterable, Sequence, Sized
else:
    from collections import Iterable, Sequence, Sized


class _NotSet(Cerebrum.meta.SingletonMixin):
    """
    An alternative `None`-like singleton.

    This class implements a falsy singleton value.  It's intended as a default
    keyword argument for parameters that assigns a special meaning to `None`.

    Do not use this class directly, you should only need the *NotSet* object
    that is assigned below this class.
    """
    __slots__ = ()

    def __bool__(self):
        return False

    # PY2 backwards compatibility
    __nonzero__ = __bool__


NotSet = _NotSet()


class Factory(object):

    class_cache = {}
    module_cache = {}

    # mapping between entity type codes and Factory.get() components
    # used by Entity.get_subclassed_object
    type_component_map = {
        'ou': 'OU',
        'person': 'Person',
        'account': 'Account',
        'group': 'Group',
        'host': 'Host',
        'disk': 'Disk',
        'email_target': 'EmailTarget',
    }

    @staticmethod
    def get(comp):
        components = {'Entity': 'CLASS_ENTITY',
                      'OU': 'CLASS_OU',
                      'Person': 'CLASS_PERSON',
                      'Account': 'CLASS_ACCOUNT',
                      'Group': 'CLASS_GROUP',
                      'Host': 'CLASS_HOST',
                      'Disk': 'CLASS_DISK',
                      'Database': 'CLASS_DATABASE',
                      'Constants': 'CLASS_CONSTANTS',
                      'CLConstants': 'CLASS_CL_CONSTANTS',
                      'ChangeLog': 'CLASS_CHANGELOG',
                      'DBDriver': 'CLASS_DBDRIVER',
                      'EmailLDAP': 'CLASS_EMAILLDAP',
                      'EmailTarget': 'CLASS_EMAILTARGET',
                      'OrgLDIF': 'CLASS_ORGLDIF',
                      'PosixLDIF': 'CLASS_POSIXLDIF',
                      'PosixUser': 'CLASS_POSIX_USER',
                      'PosixGroup': 'CLASS_POSIX_GROUP',
                      'DistributionGroup': 'CLASS_DISTRIBUTION_GROUP',
                      }

        if comp in Factory.class_cache:
            return Factory.class_cache[comp]

        try:
            conf_var = components[comp]
        except KeyError:
            raise ValueError("Unknown component %r" % comp)

        import_spec = getattr(cereconf, conf_var)
        return Factory.make_class(comp, import_spec, conf_var)

    @staticmethod
    def make_class(name, import_spec, conf_var=None):
        """Assemble the class according to spec.

        :param name: Name of class thing.
        :type name: str, unicode

        :param sequence import_spec: Name of classes to assemble into the
            returned class. Each element of the form ``module/classname``.

        :param string conf_var: Variable in cereconf

        :return: Class
        """
        if name in Factory.class_cache:
            return Factory.class_cache[name]

        if isinstance(import_spec, (tuple, list)):
            bases = []
            for c in import_spec:
                cls = Cerebrum.utils.module.resolve(c)
                # The cereconf.CLASS_* tuples control which classes
                # are used to construct a Factory product class.
                # Order inside such a tuple is significant for the
                # product class's method resolution order.
                #
                # A likely misconfiguration is to list a class A as
                # class_tuple[N], and a subclass of A as
                # class_tuple[N+x], as that would mean the subclass
                # won't override any of A's methods.
                #
                # The following code should ensure that this form of
                # misconfiguration won't be used.
                for override in bases:
                    if issubclass(cls, override):
                        if conf_var:
                            raise RuntimeError("Class %r should appear earlier"
                                               " in cereconf.%s, as it's a"
                                               " subclass of class %r." %
                                               (cls, conf_var, override))
                        else:
                            raise RuntimeError("Class %r should appear earlier"
                                               " than %r as it is a subclass" %
                                               (cls, override))
                bases.append(cls)
            if len(bases) == 1:
                comp_class = bases[0]
            else:
                # Dynamically construct a new class that inherits from
                # all the specified classes.  The name of the created
                # class is the same as the component name with a
                # prefix of "_dynamic_"; the prefix is there to reduce
                # the probability of `auto_super` name collision
                # problems.
                comp_class = type(str('_dynamic_' + name),
                                  tuple(bases), {})
            Factory.class_cache[name] = comp_class
            return comp_class
        else:
            raise ValueError("Invalid import spec for component %s: %r" %
                             (name, import_spec))

    @staticmethod
    def get_logger(name=None):
        """Return THE cerebrum logger.

        Although this method does very little now, we should keep our
        options open for the future.
        """
        import Cerebrum.logutils
        return Cerebrum.logutils.get_logger(name=name, _stacklevel=3)


def argument_to_sql(argument,
                    sql_attr_name,
                    binds,
                    transformation=lambda x: x,
                    negate=False):
    """Help deal with sequences of values for SQL generation.

    On many occasions we want to allow a scalar, many scalars as a sequence,
    or different types for the same scalar as an argument that has to be
    passed to the database backend. This function helps us accomplish that.

    For the purpose of this method a tuple, a list or a set are considered to
    be a 'sequence'. Everything else is considered 'scalar'.

    :type argument: a scalar (of any type) or a sequence thereof.
    :param argument:
        This is the value we want to pass to the database backend and the basis
        for SQL code generation. A single scalar will be turned into SQL
        expression 'x = :x', where x is derived from L{sql_attr_name}. A
        sequence of scalars will be turned into SQL expression 'x IN (:x1, :x2,
        ..., :xN)' where :x_i refers to the i'th element of L{argument} and the
        name x itself is based on L{sql_attr_name}.

        E.g. if argument=(1, 2, 3) and sql_attr_name='foo', the resulting SQL
        code will look like::

            (foo in (:foo0, :foo1, :foo2))

        and L{binds} will contain this dictionary::

            {'foo0': transformation(argument[0]),
             'foo1': transformation(argument[1]),
             'foo2': transformation(argument[2])}

        This way we avoid the possibility of SQL-injection for sequences of
        strings that we want to embed into the generated SQL.

    :type sql_attr_name: basestring
    :param sql_attr_name: Name of the column to match L{argument} to.

    :type binds: dict
    :param binds:
        Contains named parameter bindings to be passed to the SQL backend. This
        function generates new parameter bindings and it will update L{binds}.

    :type transformation: a callable
    :param transformation:
        Since this function generates SQL, we want to avoid SQL-injection by
        converting L{argument} to proper type. Additionally, since Constant
        objects are passed around freely, we want them converted to suitable
        numerical codes before embedding them into SQL. transformation is a
        function (any callable) that converts whatever L{argument} is/consists
        of into something that we can embed into SQL.

    :type negate: bool
    :param negate: Negate the expression (f.i NOT IN)

    :rtype: basestring
    :return:
        SQL expression that can be safely embedded into SQL code to be passed
        to the backend. The corresponding bindings are registered in L{binds}.
    """

    # replace . with _, to not confuse the printf-like syntax when joining
    # the safe SQL string from this function with the values from L{binds}.
    binds_name = sql_attr_name.replace('.', '_')
    compare_set = 'NOT IN' if negate else 'IN'
    compare_scalar = '!=' if negate else '='
    if (isinstance(argument, (Sized, Iterable)) and
            not isinstance(argument, six.string_types)):
        assert len(argument) > 0, "List can not be empty."
        if len(argument) == 1 and isinstance(argument, Sequence):
            # Sequence with only one scalar, let's unpack and treat as scalar.
            # Has no real effect, but the SQL looks prettier.
            argument = argument[0]
        # The binds approach is very slow when argument contains lots of
        # entries, so then skip it. Also the odds for hitting the sql-query
        # cache diminishes rapidly, which is what binds is trying to aid.
        elif len(argument) > 8:
            return '(%s %s (%s))' % (
                sql_attr_name,
                compare_set,
                ', '.join(map(str, map(transformation, argument))))
        else:
            tmp = dict()
            for index, item in enumerate(argument):
                name = binds_name + str(index)
                assert name not in binds
                tmp[name] = transformation(item)

            binds.update(tmp)
            return '(%s %s (%s))' % (
                sql_attr_name,
                compare_set,
                ', '.join([':' + x for x in tmp.keys()]))

    assert binds_name not in binds
    binds[binds_name] = transformation(argument)
    return "(%s %s :%s)" % (sql_attr_name, compare_scalar, binds_name)


def prepare_string(value, transform=six.text_type.lower):
    """Prepare a string for being used in SQL.

    @type value: basestring
    @param value:
      The value we want to transform from regular glob search syntax to
      the special SQL92 glob syntax.

    @type transform: a callable or None
    @param transform
      By default we lowercase the search string so we can compare with
      LOWER(column) to get case insensitive comparison.

      Send in None or some other callable to override this behaviour.
    """

    value = value.replace("*", "%")
    value = value.replace("?", "_")

    if transform:
        return transform(value)

    return value


def make_timer(logger, msg=None):
    # t = make_timer(message) logs the message and starts a stop watch.
    # t(message) logs that message and #seconds since last message.
    def timer(msg):
        prev = timer.start
        timer.start = time.time()
        timer.logger.debug("%s (%d seconds)", msg, timer.start - prev)
    if msg:
        logger.debug(msg)
    timer.start = time.time()
    timer.logger = logger
    return timer


# Compatibility names
#
# These names were historically defined in Cerebrum.Utils, but have been moved
# to different modules and given PEP-8 compatible names.
#
auto_super = Cerebrum.meta.AutoSuper
mark_update = Cerebrum.meta.MarkUpdate
read_password = Cerebrum.utils.secrets.legacy_read_password
dyn_import = Cerebrum.utils.module.import_item
unicode2str = Cerebrum.utils.text_compat.to_str

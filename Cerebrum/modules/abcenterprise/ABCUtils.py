# -*- coding: utf-8 -*-
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

from __future__ import unicode_literals
import cerebrum_path
import cereconf
import abcconf

from Cerebrum.Utils import dyn_import
from Cerebrum.extlib.doc_exception import DocstringException
from Cerebrum.extlib.doc_exception import ProgrammingError


class ABCConfigError(DocstringException):
    """Error in config."""

class ABCTypesError(DocstringException):
    """Error in arguments."""

class ABCDataError(DocstringException):
    """We have errors or conflicts in our data."""

class ABCNotSupportedError(DocstringException):
    """Function not supported."""

class ABCFactory(object):
    def get(comp):
        # Mostly cut 'n paste from Factory
        components = {'Settings': 'CLASS_SETTINGS',
                      'PreParser': 'CLASS_PREPARSER',
                      'Analyzer': 'CLASS_ANALYZER',
                      'Processor': 'CLASS_PROCESSOR',
                      'EntityIterator': 'CLASS_ENTITYITERATOR',
                      'PropertiesParser': 'CLASS_PROPERTIESPARSER',
                      'PersonParser': 'CLASS_PERSONPARSER',
                      'OrgParser': 'CLASS_ORGPARSER',
                      'OUParser': 'CLASS_OUPARSER',
                      'GroupParser': 'CLASS_GROUPPARSER',
                      'RelationParser': 'CLASS_RELATIONPARSER',
                      'Object2Cerebrum': 'CLASS_OBJ2CEREBRUM'}

        try:
            conf_var = components[comp]
        except KeyError:
            raise ValueError, "Unknown component %r" % comp
        import_spec = getattr(abcconf, conf_var)
        if not isinstance(import_spec, (tuple, list)):
            raise ValueError, \
                  "Invalid import spec for component %s: %r" % (comp,
                                                                import_spec)
        bases = []
        for c in import_spec:
            (mod_name, class_name) = c.split("/", 1)
            mod = dyn_import(mod_name)
            cls = getattr(mod, class_name)
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
                    raise RuntimeError, \
                          ("Class %r should appear earlier in"
                           " abcconf.%s, as it's a subclass of"
                           " class %r." % (cls, conf_var, override))
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
            comp_class = type('_dynamic_' + comp, tuple(bases), {})
        return comp_class
    get = staticmethod(get)


class ABCTypes(object):
    def get_type(type, args):
        if not isinstance(args, tuple):
            raise ProgrammingError, "'args' is not a tuple."
        lenght = len(args)
        for t, vals in (("addresstype", 2), ("contacttype", 2),
                        ("orgidtype", 1), ("orgnametype", 1),
                        ("ouidtype", 1), ("ounametype", 1),
                        ("personidtype", 1), ("groupidtype", 1),
                        ("relationtype", 3), ("tagtype", 2)):
            if type == t:
                if not vals == lenght:
                    raise ABCTypesError, "wrong length on list: '%s':'%d' should be '%d' - %s" % (t, lenght, vals, args)
                lists = abcconf.TYPES[type]
                for lst in lists:
                    if lst[:vals] == args:
                        if not len(lst[vals:]) == 1:
                            raise ABCConfigError
                        return lst[vals:][0]
        raise ABCTypesError, "type '%s' not found: '%s'" % (type, args)
    get_type = staticmethod(get_type)


    def get_name_type(type):
        try:
            return abcconf.NAMETYPES[type]
        except KeyError:
            raise ABCTypesError, "wrong name type: %s" % type
    get_name_type = staticmethod(get_name_type)


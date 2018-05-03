#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2006 University of Oslo, Norway
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
import procconf

from Cerebrum.Utils import dyn_import


# TBD: It is stupid to define this several places with only components
# different. Define an aux Factory for programs using Mixins?
class ProcFactory(object):
    def get(comp):
        # Mostly cut 'n paste from Factory
        components = {'BatchRunner': 'CLASS_BATCH',
                      'Handler': 'CLASS_HANDLER'}
        
        try:
            conf_var = components[comp]
        except KeyError:
            raise ValueError("Unknown component %r".format(comp))
        import_spec = getattr(procconf, conf_var)
        if not isinstance(import_spec, (tuple, list)):
            raise ValueError("Invalid import spec for component {}: {!r}"
                             .format(comp, import_spec))
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
                    raise RuntimeError(
                        "Class {!r} should appear earlier in procconf.{}, "
                        "as it's a subclass of class {!r}."
                        .format(cls, conf_var, override)
                    )
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

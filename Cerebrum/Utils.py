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

def dyn_import(name):
    """Dynamically import python module NAME."""
    try:
        mod = __import__(name)
        components = name.split(".")
        for comp in components[1:]:
            mod = getattr(mod, comp)
        return mod
    except AttributeError, mesg:
        raise ImportError, mesg

def this_module():
    'Return module object of the caller.'
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
    """Separate `rows' into (keep, reject) tuple based on `predicates'.

    The `rows' argument should be a sequence of db_row.py-generated
    objects.  Each predicate in `predicate' should be a (key, value)
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
    "Return the `keep' part of separate_entries() return value."
    return separate_entries(rows, *predicates)[0]

def reject_entries(rows, *predicates):
    "Return the `reject' part of separate_entries() return value."
    return separate_entries(rows, *predicates)[1]

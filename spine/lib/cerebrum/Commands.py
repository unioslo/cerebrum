# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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


from SpineLib.SpineClass import SpineClass
from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['Commands']

class Commands(SpineClass):
    """Collection of 'static' methods.

    This is the main class for 'static' methods in the cerebrum core
    like create_<core-class>. Since we dont support static methods on
    objects servered over corba, we create command-classes which
    contains those 'static' methods.

    This class should not implement methods specific to other classes,
    instead use Registry.get_registry().register_method().
    """

    def __new__(self, *args, **vargs):
        return SpineClass.__new__(self, cache=None)

registry.register_class(Commands)

# arch-tag: 71417222-2307-47cd-b582-9f793a502e6a

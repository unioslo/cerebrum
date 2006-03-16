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

from SpineLib import Builder
from SpineLib import Transaction
from SpineLib.SpineExceptions import NotFoundError
from SpineLib.Date import Date


from Types import CodeType

for cls in Builder.get_builder_classes(CodeType):
    method_name = 'get_' + Transaction.convert_name(cls.__name__)

    def blipp(cls):
        def get_method(self, name):
            return cls(self.get_database(), name=name)
        return get_method
    m = blipp(cls)
    args = [('name', str)]

    method = Builder.Method(method_name, cls, args, exceptions=[NotFoundError])
    Transaction.Transaction.register_method(method, m)

# arch-tag: 79265054-583c-4ead-ae5b-3720b9d72810

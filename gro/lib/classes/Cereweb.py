# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

from GroBuilder import GroBuilder
from DatabaseClass import DatabaseAttr, DatabaseClass

__all__ = ['CerewebOption','CerewebMotd']

class CerewebOption(DatabaseClass, GroBuilder):
    table = "[:table schema=cerebrum name=cereweb_option]"
    primary = [DatabaseAttr('option_id', 'long', table, from_db=long)]
    slots = primary + [DatabaseAttr('entity_id', 'long', table, from_db=long),
                       DatabaseAttr('key', 'string', table, write=True),
                       DatabaseAttr('value', 'string', table, write=True)]

    def build_methods(cls):
        super(CerewebOption, cls).build_methods()
        super(DatabaseClass, cls).build_methods()

    build_methods = classmethod(build_methods)

class CerewebMotd(DatabaseClass, GroBuilder):
    table = "cereweb_motd"
    primary = [DatabaseAttr('motd_id','long', table, from_db=long)]
    slots = primary + [DatabaseAttr('create_date', 'string', table),
                       DatabaseAttr('creator', 'long', table, from_db=long),
                       DatabaseAttr('subject', 'string', table),
                       DatabaseAttr('message','string', table)]

    def build_methods(cls):
        super(CerewebMotd, cls).build_methods()
        super(DatabaseClass, cls).build_methods()

    build_methods = classmethod(build_methods)


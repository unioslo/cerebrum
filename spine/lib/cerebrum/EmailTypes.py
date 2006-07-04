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

from SpineLib.DatabaseClass import DatabaseAttr
from SpineLib import Registry
from Types import CodeType

__all__ = []

registry = Registry.get_registry()

# XXX We should fix CodeType to automagically do this from name+table
for name, table in [
    ('EmailTargetType', 'email_target_code'),
    ('EmailDomainCategory', 'email_domain_cat_code'),
    ('EmailSpamAction', 'email_spam_action_code'),
    ('EmailServerType', 'email_server_type_code'),
    ('EmailVirusFound', 'email_virus_found_code'),
    ('EmailVirusRemoved', 'email_virus_removed_code'),
    ]:

    exec 'class %s(CodeType):\n pass\ncls=%s' % (name, name)

    cls.primary = (
        DatabaseAttr('id', table, int),
    )
    cls.slots = (
        DatabaseAttr('name', table, str),
        DatabaseAttr('description', table, str)
    )
    cls.db_attr_aliases = {
        table:{
            'id':'code',
            'name':'code_str'
        }
    }
            
    registry.register_class(cls)
    __all__.append(name)


table = 'email_spam_level_code'
class EmailSpamLevel(CodeType):
    primary = (
        DatabaseAttr('id', table, int),
    )
    slots = (
        DatabaseAttr('level', table, int),
        DatabaseAttr('name', table, str),
        DatabaseAttr('description', table, str)
    )
    db_attr_aliases = {
        table: {
            'id':'code',
            'name':'code_str'
        }
    }

registry.register_class(EmailSpamLevel)
__all__.append(EmailSpamLevel)


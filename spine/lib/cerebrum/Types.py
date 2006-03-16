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

from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr
from SpineLib.SpineExceptions import NotFoundError, TooManyMatchesError
from SpineLib import Registry

registry = Registry.get_registry()

__all__ = ['CodeType']
class CodeType(DatabaseClass):
    _ignore_CodeType = True

    def __new__(cls, db, id=None, name=None, **args):
        if id is None and name is not None:
            s = cls.search_class(db)
            s.set_name(name)
            results = s.search()
            if not len(results):
                raise NotFoundError('No match for %s(%s)' % (cls.__name__, name))
            elif len(results) > 1:
                raise TooManyMatchesError('Multiple matches for %s(%s)' % (cls.__name__, name))
            return results[0]
        else:
            return super(CodeType, cls).__new__(cls, db, id=id, name=name, **args)

    def create_primary_key(cls, db, id=None, name=None, **args):
        assert type(id) in (int, long)

        return super(CodeType, cls).create_primary_key(db, id, name, **args)

    create_primary_key = classmethod(create_primary_key)

for name, table in [('AccountType', 'account_code'),
                    ('EntityType', 'entity_type_code'),
                    ('AddressType', 'address_code'),
                    ('ContactInfoType', 'contact_info_code'),
                    ('GenderType', 'gender_code'),
                    ('SourceSystem', 'authoritative_system_code'),
                    ('NameType', 'person_name_code'),
                    ('AuthenticationType', 'authentication_code'),
                    ('Spread', 'spread_code'),
                    ('GroupMemberOperationType', 'group_membership_op_code'),
                    ('GroupVisibilityType', 'group_visibility_code'),
                    ('QuarantineType', 'quarantine_code'),
                    ('OUPerspectiveType', 'ou_perspective_code'),
                    ('HomeStatus', 'home_status_code'),
                    ('PersonAffiliationType', 'person_affiliation_code'),
                    ('ValueDomain', 'value_domain_code'),
                    ('LanguageType', 'language_code'),
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

# Add entity type slot to Spread
Spread.slots += (DatabaseAttr('entity_type', 'spread_code', EntityType), )

table = 'entity_external_id_code'
class EntityExternalIdType(CodeType):
    primary = (
        DatabaseAttr('id', table, int),
    )
    slots = (
        DatabaseAttr('type', table, EntityType),
        DatabaseAttr('name', table, str),
        DatabaseAttr('description', table, str)
    )
    db_attr_aliases = {
        table:{
            'id':'code',
            'name':'code_str',
            'type':'entity_type'
        }
    }

registry.register_class(EntityExternalIdType)
__all__.append(EntityExternalIdType)

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
        table:{
            'id':'code',
            'name':'code_str',
        }
    }

registry.register_class(EmailSpamLevel)
__all__.append(EmailSpamLevel)


# arch-tag: 965b1b0a-4526-4189-b507-2459e1ed646d

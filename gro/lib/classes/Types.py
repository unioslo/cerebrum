import Cerebrum.Entity

from Cerebrum.gro.Cerebrum_core import Errors

from Builder import Builder, Attribute
from db import db

__all__ = ['AddressType', 'ContactInfoType', 'GenderType', 'EntityType',
           'SourceSystem', 'NameType', 'AuthenticationType', 'Spread',
           'GroupMemberOperationType', 'GroupVisibilityType']

class CodeType(Builder):
    primary = [Attribute('id', 'long')]
    slots = primary + [Attribute('name', 'string'),
                       Attribute('description', 'string')]

    def getByName(cls, name):
        rows = db.query('''SELECT code, description
                           FROM %s WHERE code_str = %s''' % (cls._tableName, `name`)) # ugh. stygg escaping
        if not rows:
            raise Errors.NoSuchNodeError('%s %s not found' % (cls.__name__, name))
        row = rows[0]

        id = int(row['code'])
        description = row['description']

        return cls(id, name=name, description=description)

    getByName = classmethod(getByName)

    def load(self):
        rows = db.query('''SELECT code_str, description
                           FROM %s WHERE code = %s''' % (self._tableName, self.id))
        if not rows:
            raise Errors.NoSuchNodeError('%s %s not found' % (self.__class__.__name__, self.id))
        row = rows[0]

        self._name = row['code_str']
        self._description = row['description']

class AddressType(CodeType):
    _tableName = 'address_code'

class ContactInfoType(CodeType):
    _tableName = 'contact_info_code'

class GenderType(CodeType):
    _tableName = 'gender_code'

class AffiliationType(CodeType):
    _tableName = 'person_affiliation_code'

class EntityType(CodeType):
    _tableName = 'entity_type_code'

class SourceSystem(CodeType):
    _tableName = 'authoritative_system_code'

class NameType(CodeType):
    _tableName = 'person_name_code'

class AuthenticationType(CodeType):
    _tableName = 'authentication_code'

class GroupMemberOperationType(CodeType):
    _tableName = 'group_membership_op_code'

class GroupVisibilityType(CodeType):
    _tableName = 'group_visibility_code'

class QuarantineType(CodeType):
    _tableName = 'quarantine_code'

class Spread(CodeType):
    _tableName = 'spread_code'

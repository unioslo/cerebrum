# -*- coding: iso-8859-1 -*-
from Cerebrum import DatabaseAccessor
from Cerebrum import Constants

class _FieldTypeCode(Constants._CerebrumCode):
    "Mappings stored in the field_type_code table"
    _lookup_table = '[:table schema=cerebrum name=dns_field_type_code]'

class _EntityNoteCode(Constants._CerebrumCode):
    "Mappings stored in the entity_note_code table"
    _lookup_table = '[:table schema=cerebrum name=dns_entity_note_code]'

class _HinfoCode(Constants._CerebrumCode):
    "Mappings stored in the field_type_code table"
    _lookup_table = '[:table schema=cerebrum name=dns_hinfo_code]'
    _key_size = 2
    
    # TODO: the caching done by __new__ don't seem to work, or is very
    # slow when looking up by code=int.
    def __init__(self, code, cpu=None, os=None):
        """When called with two arguments (os=None), try to lookup an
        existing value by cpu=code and os=cpu.  If code is int, lookup
        by numerical value."""
        if os is None:
            if isinstance(code, int):
                code = self.sql.query_1("""
                SELECT code FROM %s WHERE code=:code""" % (
                    self._lookup_table), {'code': code})
            else:
                if cpu is None:
                    code = self.sql.query_1("""
                    SELECT code FROM %s WHERE code_str=:code_str""" % (
                        self._lookup_table), {'code_str': code})
                else:
                    code = self.sql.query_1("""
                    SELECT code FROM %s WHERE cpu=:cpu and os=:os""" % (
                        self._lookup_table), {'cpu': code, 'os': cpu})
        super(_HinfoCode, self).__init__(code, None)
        if cpu is not None:
            self.cpu = cpu
            self.os = os
        else:
            self.cpu, self.os = self.sql.query_1("""
            SELECT cpu, os FROM %s WHERE %s=:code""" % (
                self._lookup_table, self._lookup_code_column), {
                'code': int(self) })

    def insert(self):
        self.sql.execute("""
        INSERT INTO %(code_table)s
          (%(code_col)s, %(str_col)s, cpu, os)
        VALUES
          (%(code_seq)s, :str, :cpu, :os)""" % {
            'code_table': self._lookup_table,
            'code_col': self._lookup_code_column,
            'str_col': self._lookup_str_column,
            'cpu': self.cpu,
            'os': self.os,
            'code_seq': self._code_sequence},
                         {'cpu': self.cpu,
                          'str': self.str,
                          'os': self.os})

    def list(db):
        return db.query("""
        SELECT %(code_col)s, %(str_col)s, cpu, os
        FROM %(code_table)s"""  % {
            'code_table': _HinfoCode._lookup_table,
            'code_col': _HinfoCode._lookup_code_column,
            'str_col': _HinfoCode._lookup_str_column})
    list = staticmethod(list)

class Constants(Constants.Constants):
    entity_dns_cname = Constants._EntityTypeCode(
        'cname',
        'cname - see table "cerebrum.cname_info" and friends.')
    entity_dns_host = Constants._EntityTypeCode(  # name-clash with existing entity_type
        'dns_host',
        'dns_host - see table "cerebrum.dns_host_info" and friends.')
    entity_dns_a_record = Constants._EntityTypeCode(
        'a_record',
        'a_record - see table "cerebrum.a_record_info" and friends.')
    entity_dns_owner = Constants._EntityTypeCode(
        'dns_owner',
        'dns_owner - see table "cerebrum.dns_owner" and friends.')
#    dns_owner_namespace = Constants._ValueDomainCode('dns_owner_ns',
#                                                     'Domain for dns_owners')

    spread_uio_machine_netgroup = Constants._SpreadCode(
        'NIS_mng@uio', Constants.Constants.entity_group,
        'Machine netgroup in NIS domain "uio"')

    field_type_txt = _FieldTypeCode('TXT', 'TXT Record')
    note_type_contact = _EntityNoteCode('CONTACT', 'Contact information')
    note_type_comment = _EntityNoteCode('COMMENT', 'A comment')

    #hi = _HinfoCode("auto1", "I86", "LINUX")

    FieldTypeCode = _FieldTypeCode
    HinfoCode = _HinfoCode
    EntityNoteCode = _EntityNoteCode

# arch-tag: 05900130-fb6f-4186-97d0-ded361bdfd88

# -*- coding: iso-8859-1 -*-
from Cerebrum import DatabaseAccessor
from Cerebrum import Constants

class _FieldTypeCode(Constants._CerebrumCode):
    "Mappings stored in the field_type_code table"
    _lookup_table = '[:table schema=cerebrum name=dns_field_type_code]'

class _EntityNoteCode(Constants._CerebrumCode):
    "Mappings stored in the entity_note_code table"
    _lookup_table = '[:table schema=cerebrum name=dns_entity_note_code]'

class _DnsZoneCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=dns_zone]'

    _lookup_code_column = 'zone_id'
    _lookup_str_column = 'name'
    _lookup_desc_column = 'postfix'

    def _get_name(self):
        return self.str
    name = property(_get_name, None, None, "the name")

    def _get_zone_id(self):
        return int(self)
    zone_id = property(_get_zone_id, None, None, "the zone_id")

    def _get_postfix(self):
        if not hasattr(self, '_postfix'):
            self._postfix = self._get_description()
        return self._postfix
    postfix = property(_get_postfix, None, None, "the postfix")

class Constants(Constants.Constants):
    """``DnsConstants.Constants(Constants.Constants)`` defines
    constants used by the dns module"""
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
    dns_owner_namespace = Constants._ValueDomainCode('dns_owner_ns',
                                                     'Domain for dns_owners')

    spread_uio_machine_netgroup = Constants._SpreadCode(
        'NIS_mng@uio', Constants.Constants.entity_group,
        'Machine netgroup in NIS domain "uio"')

    field_type_txt = _FieldTypeCode('TXT', 'TXT Record')
    note_type_contact = _EntityNoteCode('CONTACT', 'Contact information')
    note_type_comment = _EntityNoteCode('COMMENT', 'A comment')

    FieldTypeCode = _FieldTypeCode
    EntityNoteCode = _EntityNoteCode

    uio_zone = _DnsZoneCode("uio", ".uio.no.")
    other_zone = _DnsZoneCode("other", None)
    DnsZone = _DnsZoneCode


# arch-tag: 05900130-fb6f-4186-97d0-ded361bdfd88

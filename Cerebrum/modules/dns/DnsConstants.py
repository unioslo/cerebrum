# -*- coding: iso-8859-1 -*-
from Cerebrum import DatabaseAccessor
from Cerebrum import Constants
from Cerebrum.modules.CLConstants import _ChangeTypeCode

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
    entity_dns_ip_number = Constants._EntityTypeCode(
        'dns_ip_number',
        'dns_ip_number - see table "cerebrum.dns_ip_number" and friends.')
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

    # ChangeLog constants
    a_record_add = _ChangeTypeCode(
        'host', 'a_rec_add', 'add a-record %(subject)s -> %(dest)s')
    a_record_del = _ChangeTypeCode(
        'host', 'a_rec_del', 'del a-record %(subject)s -> %(dest)s')
    a_record_update = _ChangeTypeCode(
        'host', 'a_rec_upd', 'update a-record %(subject)s -> %(dest)s')
    cname_add = _ChangeTypeCode(
        'host', 'cname_add', 'add cname %(subject)s -> %(dest)s')
    cname_del = _ChangeTypeCode(
        'host', 'cname_del', 'del cname %(subject)s -> %(dest)s')
    cname_update = _ChangeTypeCode(
        'host', 'cname_upd', 'update cname %(subject)s -> %(dest)s')
    dns_owner_add = _ChangeTypeCode(
        'host', 'dns_owner_add', 'add dns-owner %(subject)s')
    dns_owner_update = _ChangeTypeCode(
        'host', 'dns_owner_upd', 'update dns-owner %(subject)s')
    dns_owner_del = _ChangeTypeCode(
        'host', 'dns_owner_del','del dns-owner %(subject)s')
    general_dns_record_add = _ChangeTypeCode(
        'host', 'gen_dns_rec_add', 'add record for %(subject)s',
        ('%(int:field_type)s=%(string:data)s',))
    general_dns_record_del = _ChangeTypeCode(
        'host', 'gen_dns_rec_del', 'del record for %(subject)s',
        ('type=%(int:field_type)s',))
    general_dns_record_update = _ChangeTypeCode(
        'host', 'gen_dns_rec_upd', 'update record for %(subject)s',
        ('%(int:field_type)s=%(string:data)s',))
    host_info_add = _ChangeTypeCode(
        'host', 'host_info_add', 'add %(subject)s',
        ('hinfo=%(string:hinfo)s',))
    host_info_update = _ChangeTypeCode(
        'host', 'host_info_upd', 'update %(subject)s',
        ('hinfo=%(string:hinfo)s',))
    host_info_del = _ChangeTypeCode(
        'host', 'host_info_del', 'del %(subject)s')
    ip_number_add = _ChangeTypeCode(
        'host', 'ip_number_add', 'add %(subject)s',
        ('a_ip=%(string:a_ip)s',))
    ip_number_update = _ChangeTypeCode(
        'host', 'ip_number_upd', 'update %(subject)s',
        ('a_ip=%(string:a_ip)s',))
    ip_number_del = _ChangeTypeCode(
        'host', 'ip_number_del', 'del %(subject)s')
    rev_override_add = _ChangeTypeCode(
        'host', 'rev_ovr_add', 'add rev-override %(subject)s -> %(dest)s')
    rev_override_del = _ChangeTypeCode(
        'host', 'rev_ovr_del', 'del rev-override for %(subject)s')
    rev_override_update = _ChangeTypeCode(
        'host', 'rev_ovr_upd', 'update rev-override %(subject)s -> %(dest)s')
    srv_record_add = _ChangeTypeCode(
        'host', 'srv_rec_add', 'add srv-record %(subject)s -> %(dest)s')
    srv_record_del = _ChangeTypeCode(
        'host', 'srv_rec_del', 'del srv-record %(subject)s -> %(dest)s')

# arch-tag: 05900130-fb6f-4186-97d0-ded361bdfd88

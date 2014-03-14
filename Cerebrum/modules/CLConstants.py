# -*- coding: iso-8859-1 -*-
# Copyright 2003, 2012 University of Oslo, Norway
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

import cereconf
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum import Constants
from Cerebrum.Constants import _CerebrumCode

class _ChangeTypeCode(_CerebrumCode):
    _lookup_code_column = 'change_type_id'
    # _lookup_str_column = 'status_str'
    _lookup_table = '[:table schema=cerebrum name=change_type]'
    # _insert_dependency = _PersonAffiliationCode
    _lookup_desc_column = 'msg_string'
    _key_size = 2

    """Identifies the type of change in the change-log.  category +
    type identifies the type of change.  The split is done to emulate
    the behaviour of the two-parts bofh commands.

    msg_string is a string that can be used to format a textly
    representation of the change (typically for showing a user).  It
    may contain %%(subject)s and %%(dest)s where the names of these
    entities should be inserted.

    format may contain information about how information from
    change_params should be displayed.  It contains a tuple of strings
    that may contain %%(type:key)s, which will result in key being
    formatted as type.
    """
    # TODO: the formatting is currently done by bofhd_uio_cmds.py.  It
    # would make more sense to do it here, but then we need some
    # helper classes for efficient conversion from entity_id to names
    # etc.

    # The constructor accepts the numeric code value, or a pair
    # of strings (category, type) identifying the constant code.
    def __init__(self, category, type=None, msg_string=None, format=None):
        if type is None:
            # Not the category, but the numeric code value
            try:
                # Handle PgNumeric etc.
                self.int = int(category)
            except ValueError:
                raise TypeError, ("Must pass integer when initialising "
                                  "from code value")
            self.category, self.type = self.sql.query_1(
                """SELECT category, type
                FROM %s
                WHERE %s = :code""" % (self._lookup_table,
                                       self._lookup_code_column),
                {'code': self.int})
        else:
            self.category = category
            self.type = type
            if not hasattr(self, "int"):
                self.int = None

        # The code object may have been initialised explicitly
        # already.  If we initialise the object based on code value
        # alone, don't nuke those extra attributes.
        if not hasattr(self, "msg_string") or msg_string is not None:
            self.msg_string = msg_string
        if not hasattr(self, "format") or format is not None:
            self.format = format
        super(_ChangeTypeCode, self).__init__(category, type)

    def __str__(self):
        return "%s:%s" % (self.category, self.type)

    def __int__(self):
        if self.int is None:
            self.int = int(self.sql.query_1("""
            SELECT change_type_id FROM [:table schema=cerebrum name=change_type]
            WHERE category=:category AND type=:type""", {
                'category': self.category,
                'type': self.type}))
        return self.int

    def insert(self):
        self._pre_insert_check()
        self.sql.execute("""
        INSERT INTO %(code_table)s
          (%(code_col)s, category, type ,%(desc_col)s)
        VALUES
          ( %(code_seq)s, :category, :type, :desc)""" % {
            'code_table': self._lookup_table,
            'code_col': self._lookup_code_column,
            'desc_col': self._lookup_desc_column,
            'code_seq': self._code_sequence},
                         {'category': self.category,
                          'type': self.type,
                          'desc': self.msg_string})


class CLConstants(Constants.Constants):

    """Singleton whose members make up all needed coding values.

    Defines a number of variables that are used to get access to the
    string/int value of the corresponding database key."""

    ChangeType = _ChangeTypeCode

    group_add = _ChangeTypeCode('e_group', 'add',
                                'added %(subject)s to %(dest)s')
    group_rem = _ChangeTypeCode('e_group', 'rem',
                                'removed %(subject)s from %(dest)s')
    group_create = _ChangeTypeCode('e_group', 'create',
                                   'created %(subject)s')
    group_mod = _ChangeTypeCode('e_group', 'mod',
                                'modified %(subject)s')
    group_destroy = _ChangeTypeCode('e_group', 'destroy',
                                    'destroyed %(subject)s')

    account_create =  _ChangeTypeCode('e_account', 'create',
                                      'created %(subject)s')
    account_delete = _ChangeTypeCode('e_account', 'delete',
                                     'deleted %(subject)s')
    account_mod =  _ChangeTypeCode('e_account', 'mod',
                                   'modified %(subject)s',
                                   ("new owner=%(entity:owner_id)s",
                                    "new expire_date=%(date:expire_date)s"))
    account_password =  _ChangeTypeCode('e_account', 'password',
                                        'new password for %(subject)s')
    account_password_token = _ChangeTypeCode('e_account', 'passwordtoken',
                                        'password token sent for %(subject)s',
                                        ('phone_to=%(string:phone_to)s',))
    account_destroy = _ChangeTypeCode('e_account', 'destroy',
                                    'destroyed %(subject)s')
    # TODO: account_move is obsolete, remove it
    account_move =  _ChangeTypeCode(
        'e_account', 'move', '%(subject)s moved',
        ('from=%(string:old_host)s:%(string:old_disk)s, '+
         'to=%(string:new_host)s:%(string:new_disk)s,',))
    account_home_updated = _ChangeTypeCode(
        'e_account', 'home_update', 'home updated for %(subject)s',
        ('old=%(homedir:old_homedir_id)s',
         'old_home=%(string:old_home)s',
         'old_disk_id=%(disk:old_disk_id)s',
         'spread=%(spread_code:spread)s'))
    account_home_added = _ChangeTypeCode('e_account', 'home_added',
                                         'home added for %(subject)s',
                                         ('spread=%(spread_code:spread)s',
                                          'home=%(string:home)s'))
    account_home_removed = _ChangeTypeCode('e_account', 'home_removed',
                                           'home removed for %(subject)s',
                                           ('spread=%(spread_code:spread)s',
                                            'home=%(string:home)s'))
    spread_add =  _ChangeTypeCode(
        'spread', 'add', 'add spread for %(subject)s',
        ('spread=%(spread_code:spread)s',))
    spread_del =  _ChangeTypeCode(
        'spread', 'delete', 'delete spread for %(subject)s',
        ('spread=%(spread_code:spread)s',))
    account_type_add = _ChangeTypeCode(
        'ac_type', 'add', 'ac_type add for account %(subject)s',
        ('ou=%(ou:ou_id)s, aff=%(affiliation:affiliation)s, pri=%(int:priority)s',))
    account_type_mod = _ChangeTypeCode(
        'ac_type', 'mod', 'ac_type mod for account %(subject)s',
        ('old_pri=%(int:old_pri)s, old_pri=%(int:new_pri)s',))
    account_type_del = _ChangeTypeCode(
        'ac_type', 'del', 'ac_type del for account %(subject)s',
        ('ou=%(ou:ou_id)s, aff=%(affiliation:affiliation)s',))
    homedir_remove = _ChangeTypeCode(
        'homedir', 'del', 'homedir del for account %(subject)s',
        ('id=%(int:homedir_id)s',))
    homedir_add = _ChangeTypeCode(
        'homedir', 'add', 'homedir add for account %(subject)s',
        ('id=%(int:homedir_id)s', 'home=%(string:home)s'))
    homedir_update = _ChangeTypeCode(
        'homedir', 'update', 'homedir update for account %(subject)s',
        ('id=%(int:homedir_id)s',
         'home=%(string:home)s', 'status=%(home_status:status)s'))
    disk_add = _ChangeTypeCode('disk', 'add', 'new disk %(subject)s')
    disk_mod = _ChangeTypeCode('disk', 'mod', 'update disk %(subject)s')
    disk_del = _ChangeTypeCode('disk', 'del', "delete disk %(subject)s")
    host_add = _ChangeTypeCode('host', 'add', 'new host %(subject)s')
    host_mod = _ChangeTypeCode('host', 'mod', 'update host %(subject)s')
    host_del = _ChangeTypeCode('host', 'del', 'del host %(subject)s')
    ou_create = _ChangeTypeCode('ou', 'create', 'created OU %(subject)s')
    ou_mod = _ChangeTypeCode('ou', 'mod', 'modified OU %(subject)s')
    ou_unset_parent = _ChangeTypeCode(
        'ou', 'unset_parent', 'parent for %(subject)s unset',
        ('perspective=%(int:perspective)s',))
    ou_set_parent = _ChangeTypeCode(
        'ou', 'set_parent', 'parent for %(subject)s set to %(dest)s',
        ('perspective=%(int:perspective)s',))
    ou_del = _ChangeTypeCode('ou', 'del', 'deleted OU %(subject)s')
    person_create = _ChangeTypeCode('person', 'create', 'created %(subject)s')
    person_update = _ChangeTypeCode('person', 'update', 'update %(subject)s')
    person_name_del = _ChangeTypeCode(
        'person', 'name_del', 'del name for %(subject)s',
        ('src=%(source_system:src)s, '+
         'variant=%(name_variant:name_variant)s',))
    person_name_add = _ChangeTypeCode(
        'person', 'name_add', 'add name for %(subject)s',
        ('name=%(string:name)s, src=%(source_system:src)s, ' +
         'variant=%(name_variant:name_variant)s',))
    person_name_mod = _ChangeTypeCode(
        'person', 'name_mod', 'mod name for %(subject)s',
        ('name=%(string:name)s, src=%(source_system:src)s, ' +
         'variant=%(name_variant:name_variant)s',))
    entity_ext_id_del = _ChangeTypeCode(
        'entity', 'ext_id_del', 'del ext_id for %(subject)s',
        ('src=%(source_system:src)s, type=%(extid:id_type)s',))
    entity_ext_id_mod = _ChangeTypeCode(
        'entity', 'ext_id_mod', 'mod ext_id for %(subject)s',
        ('value=%(string:value)s, src=%(source_system:src)s, '+
         'type=%(extid:id_type)s',))
    entity_ext_id_add = _ChangeTypeCode(
        'entity', 'ext_id_add', 'add ext_id for %(subject)s',
        ('value=%(string:value)s, src=%(source_system:src)s, '+
         'type=%(extid:id_type)s',))
    person_aff_add = _ChangeTypeCode('person', 'aff_add', 'add aff for %(subject)s')
    person_aff_mod = _ChangeTypeCode('person', 'aff_mod', 'mod aff for %(subject)s')
    person_aff_del = _ChangeTypeCode('person', 'aff_del', 'del aff for %(subject)s')
    person_aff_src_add = _ChangeTypeCode('person', 'aff_src_add',
                                         'add aff_src for %(subject)s')
    person_aff_src_mod = _ChangeTypeCode('person', 'aff_src_mod',
                                         'mod aff_src for %(subject)s')
    person_aff_src_del = _ChangeTypeCode('person', 'aff_src_del',
                                         'del aff_src for %(subject)s')
    quarantine_add = _ChangeTypeCode(
        'quarantine', 'add', 'add quarantine for %(subject)s',
        ('type=%(quarantine_type:q_type)s',))
    quarantine_mod = _ChangeTypeCode(
        'quarantine', 'mod', 'mod quarantine for %(subject)s',
        ('type=%(quarantine_type:q_type)s',))
    quarantine_del = _ChangeTypeCode(
        'quarantine', 'del', 'del quarantine for %(subject)s',
        ('type=%(quarantine_type:q_type)s',))
    quarantine_refresh = _ChangeTypeCode('quarantine', 'refresh',
                                         'refresh quarantine for %(subject)s')

    # email change types and categories
    #
    # email domain
    email_dom_add = _ChangeTypeCode('email_domain', 'add_domain', 
                                    'add email domain %(subject)s',
                                    ('name=%(string:new_domain_name)'))
    email_dom_rem = _ChangeTypeCode('email_domain', 'rem_domain', 
                                    'remove email domain %(subject)s',
                                    ('name=%(string:del_domain'))
    # either domain name or domain description has been changed
    # TODO: these two actions should be splitt? 
    email_dom_mod = _ChangeTypeCode('email_domain', 'mod_domain', 
                                    'modify email domain %(subject)s',
                                    ('name=%(string:new_domain_name)',
                                     'desc=%(string:new_domain_desc'))
    email_dom_addcat = _ChangeTypeCode('email_domain', 'addcat_domain', 
                                       'add category in email domain %(subject)s',
                                       ('cat=%(int:cat)'))
    email_dom_remcat = _ChangeTypeCode('email_domain', 'remcat_domain', 
                                       'remove category in email domain %(subject)s',
                                       ('cat=%(int:cat)'))
    # email target
    email_target_add = _ChangeTypeCode('email_target', 'add_target', 
                                       'add email target %(subject)s',
                                       )
    email_target_rem = _ChangeTypeCode('email_target', 'rem_target', 
                                       'remove email target %(subject)s')
    email_target_mod = _ChangeTypeCode('email_target', 'mod_target', 
                                       'modify email target %(subject)s',
                                       ('type=%(int:target_type)',
                                        'server=%(int:server_id)'))
    email_address_add = _ChangeTypeCode('email_address', 'add_address', 
                                        'add email address %(subject)s',
                                        ('lp=%(string:lp)s',
                                         'domain=%(int:dom_id)s'))
    email_address_rem = _ChangeTypeCode('email_address', 'rem_address', 
                                        'remove email address %(subject)s',
                                        ('lp=%(string:lp)s',
                                         'domain=%(int:dom_id)s'))
    # email entity domain affiliation
    email_entity_dom_add = _ChangeTypeCode('email_entity_dom', 'add_entdom',
                                           'add domain aff for %(subject)s',
                                           ('affiliation=%(int:aff)'))
    email_entity_dom_rem = _ChangeTypeCode('email_entity_dom', 'rem_entdom',
                                           'remove domain aff for %(subject)s')
    email_entity_dom_mod = _ChangeTypeCode('email_entity_dom', 'mod_entdom',
                                           'modify domain aff for %(subject)s',
                                           ('affiliation=%(int:aff)'))
    # email quota (subject here is an email_target)
    email_quota_add = _ChangeTypeCode('email_quota', 'add_quota', 
                                      'add quota for %(subject)s',
                                      ('soft=%(int:soft)',
                                       'hard=%(int:hard)'))
    email_quota_rem = _ChangeTypeCode('email_quota', 'rem_quota', 
                                      'remove quota for %(subject)s')
    email_quota_mod = _ChangeTypeCode('email_quota', 'mod_quota', 
                                      'modify quota for %(subject)s',
                                      ('soft=%(int:soft)',
                                       'hard=%(int:hard)'))
    # email target filter
    email_tfilter_add = _ChangeTypeCode('email_tfilter', 'add_filter',
                                        'add tfilter for %(subject)s',
                                        ('filter=%(int:filter)'))
    email_tfilter_rem = _ChangeTypeCode('email_tfilter', 'rem_filter',
                                        'remove tfilter for %(subject)s',
                                        ('filter=%(int:filter)'))
    # email spam_filter
    email_sfilter_add = _ChangeTypeCode('email_sfilter', 'add_sfilter', 
                                        'add sfilter for %(subject)s',
                                        ('level=%(int:level)',
                                         'action=%(int:action)'))
    email_sfilter_mod = _ChangeTypeCode('email_sfilter', 'mod_sfilter', 
                                        'modify sfilter for %(subject)s',
                                        ('level=%(int:level)',
                                         'action=%(int:action)'))
    # email virus scan
    email_scan_add = _ChangeTypeCode('email_scan', 'add_scan', 
                                     'add scan for %(subject)s',
                                     ('found=%(int:found)',
                                      'removed=%(int:removed)',
                                      'enable=%(int:enable)'))
    email_scan_mod = _ChangeTypeCode('email_scan', 'mod_scan', 
                                     'modify scan for %(subject)s')
    # email forward (subject here is an email_target)
    email_forward_add = _ChangeTypeCode('email_forward', 'add_forward', 
                                        'add forward for %(subject)s',
                                        ('forward=%(string:forward)',
                                         'enable=%(string:enable)'))
    email_forward_rem = _ChangeTypeCode('email_forward', 'rem_forward', 
                                        'remove forward for %(subject)s',
                                        ('forward=%(string:forward)'))
    email_forward_enable = _ChangeTypeCode('email_forward', 'enable_forward', 
                                           'enable forward for %(subject)s',
                                           ('forward=%(string:forward)',
                                            'cat=%(int:cat)'))
    email_forward_disable = _ChangeTypeCode('email_forward', 'disable_forward', 
                                            'disable forward for %(subject)s',
                                           ('forward=%(string:forward)',
                                            'cat=%(int:cat)'))
    # email vacation (subject here is an email_target)
    # TBD: should we bother to log this? I don't think so, vacation 
    # msg will be moved to exchange
    email_vacation_add = _ChangeTypeCode('email_vacation', 'add_vacation', 
                                         'add vacation for %(subject)s')
    email_vacation_rem = _ChangeTypeCode('email_vacation', 'rem_vacation', 
                                        'remove vacation for %(subject)s')
    email_vacation_enable = _ChangeTypeCode('email_vacation', 'enable_vaca', 
                                           'enable vacation msg for %(subject)s')
    email_vacation_disable = _ChangeTypeCode('email_vacation', 'disable_vaca', 
                                            'disable vacation msg for %(subject)s')
    # email primary address target (subject here is an email_target)
    email_primary_address_add = _ChangeTypeCode('email_primary_address', 'add_primary', 
                                                'add primary address for %(subject)s',
                                                ('primary=%(int:addr_id)'))
    email_primary_address_rem = _ChangeTypeCode('email_primary_address', 'rem_primary', 
                                                'remove primary address for %(subject)s',
                                                ('primary=%(int:addr_id)'))
    email_primary_address_mod = _ChangeTypeCode('email_primary_address', 'mod_primary', 
                                                'modify primary address for %(subject)s',
                                                ('primary=%(int:addr_id)'))
    # email server (subject here is an e-mail server)
    email_server_add = _ChangeTypeCode('email_server', 'add_server', 
                                       'add email server %(subject)s',
                                       ('type=%(int:server_type)'))
    email_server_rem = _ChangeTypeCode('email_server', 'rem_server', 
                                       'remove email server %(subject)s',
                                       ('type=%(int:server_type)'))
    email_server_mod = _ChangeTypeCode('email_server', 'mod_server', 
                                       'modify email server %(subject)s',
                                       ('type=%(int:server_type)'))
    # entity changes
    entity_add = _ChangeTypeCode('entity', 'add', 'add entity %(subject)s')
    entity_del = _ChangeTypeCode('entity', 'del', 'del entity %(subject)s')
    entity_name_add = _ChangeTypeCode(
        'entity_name', 'add', 'add entity_name for %(subject)s',
        ('domain=%(value_domain:domain)s, name=%(string:name)s',))
    entity_name_mod = _ChangeTypeCode(
        'entity_name', 'mod', 'mod entity_name for %(subject)s',
        ('domain=%(value_domain:domain)s, name=%(string:name)s',))
    entity_name_del = _ChangeTypeCode(
        'entity_name', 'del', 'del entity_name for %(subject)s',
        ('domain=%(value_domain:domain)s, name=%(string:name)s',))
    entity_cinfo_add = _ChangeTypeCode('entity_cinfo', 'add',
                                       'add entity_cinfo for %(subject)s')
    entity_cinfo_del = _ChangeTypeCode('entity_cinfo', 'del',
                                       'del entity_cinfo for %(subject)s')
    entity_addr_add = _ChangeTypeCode('entity_addr', 'add',
                                      'add entity_addr for %(subject)s')
    entity_addr_del = _ChangeTypeCode('entity_addr', 'del',
                                      'del entity_addr for %(subject)s')

    entity_note_add = _ChangeTypeCode(
        'entity_note', 'add', 'add entity_note for %(subject)s',
        ('note_id=%(int:note_id)s',))
    entity_note_del = _ChangeTypeCode(
        'entity_note', 'del', 'del entity_note for %(subject)s',
        ('note_id=%(int:note_id)s',))

    # TBD: Is it correct to have posix_demote in this module?
    posix_demote =  _ChangeTypeCode(
        'posix', 'demote', 'demote posix %(subject)s',
        ('uid=%(int:uid)s, gid=%(int:gid)s',))
    posix_group_demote = _ChangeTypeCode(
        'posix', 'group-demote', 'group demote posix %(subject)s',
        ('gid=%(int:gid)s',))
    posix_promote =  _ChangeTypeCode(
        'posix', 'promote', 'promote posix %(subject)s',
        ('uid=%(int:uid)s, gid=%(int:gid)s',))
    posix_group_promote = _ChangeTypeCode(
        'posix', 'group-promote', 'group promote posix %(subject)s',
        ('gid=%(int:gid)s',))

    # Guest functionality
    guest_create = _ChangeTypeCode(
        'guest', 'create', 'created guest %(dest)s',
        ('mobile=%(string:mobile)s, name=%(string:name)s, owner_id=%(string:owner)s',))

    # AD functionality
    ad_attr_add = _ChangeTypeCode(
        'ad_attr', 'add', 'added AD-attribute for %(subject)s',
        ('spread=%(string:spread)s, attr=%(string:attr)s, value=%(string:value)s',))

    ad_attr_del = _ChangeTypeCode(
        'ad_attr', 'del', 'removed AD-attribute for %(subject)s',
        ('spread=%(string:spread)s, attr=%(string:attr)s',))

def main():
    from Cerebrum.Utils import Factory
    from Cerebrum import Errors

    Cerebrum = Factory.get('Database')()
    co = CLConstants(Cerebrum)

    skip = dir(Cerebrum)
    skip.append('map_const')
    for x in filter(lambda x: x[0] != '_' and not x in skip, dir(co)):
        try:
            print "co.%s: %s = %d" % (x, getattr(co, x), getattr(co, x))
        except Errors.NotFoundError:
            print "NOT FOUND: co.%s" % x

if __name__ == '__main__':
    main()


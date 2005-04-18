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

from SpineLib.Builder import Attribute, Method
from SpineLib.SpineClass import SpineClass
from SpineLib.DumpClass import Struct

from SpineLib import Registry
registry = Registry.get_registry()

from Types import Spread

class AccountView(SpineClass):
    slots = [
        Attribute('entity_id', int),
        Attribute('entity_name', str),
        Attribute('posix_uid', int),
        Attribute('gecos', str),
        Attribute('shellname', str),
        Attribute('shell', str),
        Attribute('groupname', str),
        Attribute('posix_gid', int),
        Attribute('home', str),
        Attribute('diskhost', str),
        Attribute('diskpath', str),
        Attribute('passwd_md5', str),
        Attribute('passwd_des', str),
        Attribute('fullname', str)
    ]

    def __new__(self, *args, **vargs):
        return SpineClass.__new__(self, cache=None, *args, **vargs)

registry.register_class(AccountView)

sql = '''
SELECT en.entity_name, ei.entity_id, pu.posix_uid, pu.gecos,
ps.code_str AS shellname, ps.shell, gn.entity_name AS groupname,
pg.posix_gid, ah.home, hi.name as diskhost, di.path as diskpath,
aa_md5.auth_data as passwd_md5, aa_des.auth_data as passwd_des,
pn_full.name as fullname
FROM entity_info ei
  JOIN entity_name en ON (ei.entity_id = en.entity_id)
  JOIN account_info ai ON (ei.entity_id = ai.account_id)
  JOIN entity_spread es ON (ei.entity_id = es.entity_id)
  JOIN spread_code sc ON (es.spread = sc.code AND sc.code = :spread_id)
  LEFT JOIN account_home ah ON (ah.account_id = ai.account_id AND ah.spread = es.spread)
  LEFT JOIN (disk_info di 
     JOIN host_info hi ON (di.host_id = hi.host_id))
     ON (ah.disk_id = di.disk_id)
  LEFT JOIN (posix_user pu
    JOIN posix_shell_code ps ON (ps.code = pu.shell)
    JOIN group_info gi ON (gi.group_id = pu.gid)
    JOIN entity_name gn ON (gn.entity_id = pu.gid)
    LEFT JOIN posix_group pg ON (pg.group_id = gi.group_id))
    ON (ai.account_id = pu.account_id)
  LEFT JOIN account_authentication aa_md5 ON (aa_md5.method = (SELECT code FROM authentication_code WHERE code_str = 'MD5-crypt') AND aa_md5.account_id = ai.account_id)
  LEFT JOIN account_authentication aa_des ON (aa_des.method = (SELECT code FROM authentication_code WHERE code_str = 'crypt3-DES') AND aa_des.account_id = ai.account_id)
  LEFT JOIN (person_info pi
    LEFT JOIN person_name pn_full ON (pn_full.person_id = pi.person_id AND                                                                                                     pn_full.name_variant=(SELECT code FROM person_name_code WHERE code_str='FULL') AND pn_full.source_system=(SELECT code FROM authoritative_system_code WHERE code_str='Cached')))
  ON (pi.person_id = ai.owner_id)

'''

class AccountViewSearcher(SpineClass):
    primary = [
        Attribute('spread', Spread, write=True)
    ]
    slots = []

    method_slots = [
        Method('search', [Struct(AccountView)], write=True)
    ]

    def __new__(self, *args, **vargs):
        return SpineClass.__new__(self, cache=None, *args, **vargs)

    def search(self):
        db = self.get_database()

        result = []
        for row in db.query(sql, {'spread_id':self.get_spread().get_id()}):
            result.append(dict(row._items()))

        return result

registry.register_class(AccountViewSearcher)

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

from SpineLib.Builder import Builder, Attribute, Method
from SpineLib.DatabaseClass import DatabaseTransactionClass
from SpineLib.DumpClass import Struct, KeyValue

from SpineLib import Registry
registry = Registry.get_registry()

from Types import Spread
from Date import Date

# Account
# FIXME: ad_account er fjernet her.
account = '''
SELECT en.entity_name, ei.entity_id, pu.posix_uid, pu.gecos,
ps.code_str AS shellname, ps.shell, gn.entity_name AS groupname,
pg.posix_gid, hd.home, hi.name as diskhost, di.path as diskpath,
aa_md5.auth_data as passwd_md5, aa_des.auth_data as passwd_des,
pn_full.name as fullname
FROM entity_info ei
  JOIN entity_name en ON (ei.entity_id = en.entity_id)
  JOIN account_info ai ON (ei.entity_id = ai.account_id)
  JOIN entity_spread es ON (ei.entity_id = es.entity_id)
  JOIN spread_code sc ON (es.spread = sc.code AND sc.code = :spread_id)
  LEFT JOIN account_home ah ON (ah.account_id = ai.account_id
        AND ah.spread = es.spread)
  LEFT JOIN homedir hd ON (ah.homedir_id = hd.homedir_id)
  LEFT JOIN (disk_info di
     JOIN host_info hi ON (di.host_id = hi.host_id))
     ON (hd.disk_id = di.disk_id)
  LEFT JOIN (posix_user pu
    JOIN posix_shell_code ps ON (ps.code = pu.shell)
    JOIN group_info gi ON (gi.group_id = pu.gid)
    JOIN entity_name gn ON (gn.entity_id = pu.gid)
    LEFT JOIN posix_group pg ON (pg.group_id = gi.group_id))
    ON (ai.account_id = pu.account_id)
  LEFT JOIN account_authentication aa_md5 ON
        (aa_md5.method = (SELECT code FROM authentication_code
        WHERE code_str = 'MD5-crypt') AND aa_md5.account_id = ai.account_id)
  LEFT JOIN account_authentication aa_des ON
        (aa_des.method = (SELECT code FROM authentication_code
        WHERE code_str = 'crypt3-DES') AND aa_des.account_id = ai.account_id)
  LEFT JOIN (person_info pi
    LEFT JOIN person_name pn_full ON (pn_full.person_id = pi.person_id AND
      pn_full.name_variant=(SELECT code FROM person_name_code
        WHERE code_str='FULL') AND
        pn_full.source_system=(SELECT code FROM authoritative_system_code
        WHERE code_str='Cached')))
  ON (pi.person_id = ai.owner_id)
'''

account_quarantine = '''
SELECT
ai.account_id, qc.code_str AS type
FROM
entity_quarantine eq
  JOIN quarantine_code qc ON (qc.code = eq.quarantine_type)
  JOIN account_info ai ON (ai.account_id = eq.entity_id
    OR ai.owner_id = eq.entity_id)
  JOIN entity_spread es ON (ai.account_id = es.entity_id)
  JOIN spread_code sc ON (es.spread = sc.code AND sc.code = :spread_id)
WHERE
eq.start_date < now() AND
(eq.end_date > now() OR eq.end_date IS NULL) AND
(eq.disable_until < now() OR eq.disable_until IS NULL)
'''

# TODO: ad.entity -> ou_id. Vil ikke mappe alle studenter til Ou.
# AD-OUer har da ingenting med faktiske organisasjonsenheter å gjøre!

# GROUP

group = '''
SELECT gn.entity_name AS name,
gi.group_id AS id,
pg.posix_gid,
gi.*
FROM group_info gi
  JOIN entity_name gn ON (gi.group_id = gn.entity_id)
  JOIN entity_spread es ON (gi.group_id = es.entity_id)
  JOIN spread_code sc ON (es.spread = sc.code AND sc.code = :spread_id)
  LEFT JOIN posix_group pg ON (pg.group_id = gi.group_id)
WHERE
gi.visibility = (SELECT code FROM group_visibility_code WHERE code_str='A')
'''

#  JOIN change_log cl ON (cl.dest_entity = gi.group_id AND cl.change_id > 42)

# Person

person = '''
SELECT
pn.name AS full_name, 
pfn.name AS first_name,
pln.name AS last_name,
pi.birth_date,
pi.person_id,
pi.export_id as national_id
FROM person_info pi
  JOIN entity_spread es ON (pi.person_id = es.entity_id)
  JOIN spread_code sc ON (es.spread = sc.code AND sc.code = :spread_id)
  LEFT JOIN person_name pn ON (pn.person_id = pi.person_id
    AND pn.name_variant=(SELECT code FROM person_name_code
      WHERE code_str='FULL')
    AND pn.source_system=(SELECT code FROM authoritative_system_code
      WHERE code_str='Cached'))
  LEFT JOIN person_name pfn ON (pfn.person_id = pi.person_id
    AND pfn.name_variant=(SELECT code FROM person_name_code
      WHERE code_str='FIRST')
    AND pfn.source_system=(SELECT code FROM authoritative_system_code
      WHERE code_str='Cached'))
  LEFT JOIN person_name pln ON (pln.person_id = pi.person_id
    AND pln.name_variant=(SELECT code FROM person_name_code
      WHERE code_str='LAST')
    AND pln.source_system=(SELECT code FROM authoritative_system_code
      WHERE code_str='Cached'))
'''

# affiliation
#primary_user

primary_user = '''
SELECT
pa.person_id, pac.code_str AS affiliation, oi.acronym, oi.display_name
FROM person_affiliation pa
  JOIN ou_info oi ON (oi.ou_id = pa.ou_id)
  JOIN person_affiliation_code pac ON (pac.code = pa.affiliation)
'''


# OU
# Hvor mange adresser trenger vi?

ou = '''
SELECT
ou.ou_id, ou.name, ou.acronym, ou.short_name, ou.display_name, ou.sort_name,
ea.address_text, ea.p_o_box, ea.postal_number, ea.city, ea.country
FROM ou_info ou
  JOIN entity_spread es ON (ou.ou_id = es.entity_id)
  JOIN spread_code sc ON (es.spread = sc.code AND sc.code = 0)
  LEFT JOIN entity_address ea ON (ea.entity_id = ou.ou_id
    AND ea.source_system = (SELECT code FROM authoritative_system_code
      WHERE code_str='Cached')
    AND ea.address_type = (SELECT code FROM address_code WHERE code_str='POST'))
  LEFT JOIN entity_contact_info eci ON (eci.entity_id = ou.ou_id
    AND eci.contact_type = (SELECT code FROM contact_info_code
      WHERE code_str='PHONE')
    AND eci.source_system = (SELECT code FROM authoritative_system_code
      WHERE code_str='Cached')
    AND eci.source_system = (SELECT code FROM authoritative_system_code
      WHERE code_str='Cached'))
'''

# telefon
#Fra kjernen:


class View(DatabaseTransactionClass):
    def __init__(self, *args, **vargs):
        super(View, self).__init__(spread=None, *args, **vargs)

    slots = [
        Attribute('spread', Spread, write=True)
    ]

    method_slots = [
        Method('test', [[Struct(KeyValue)]]),
        Method('account', [[Struct(KeyValue)]]),
        Method('account_quarantine', [[Struct(KeyValue)]]),
        Method('group', [[Struct(KeyValue)]]),
        Method('person', [[Struct(KeyValue)]]),
        Method('primary_user', [[Struct(KeyValue)]]),
        Method('ou', [[Struct(KeyValue)]])
    ]

    def _convert(self, rows):
        result = []
        for row in rows:
            result.append([KeyValue.make(key, value) for key, value in row.items()])
        return result

    def _execute(self, sql, args=None):
        if args is None:
            args = {}

        spread = self.get_spread()
        if spread is not None and 'spread_id' not in args:
            args['spread_id'] = spread.get_id()

        db = self.get_database()
        result = db.query(sql, args)
        return self._convert(result)

    def test(self):
        db = self.get_database()

        test = [
            {'a':'b', 'b':1, 'c':None},
            {}
        ]

        return self._convert(test)

    def account(self):
        return self._execute(account)

    def account_quarantine(self):
        return self._execute(account_quarantine)

    def group(self):
        return self._execute(group)

    def person(self):
        return self._execute(person)

    def primary_user(self):
        return self._execute(primary_user)

    def ou(self):
        return self._execute(ou)

registry.register_class(View)

# arch-tag: 83956c70-b01a-11d9-9b05-d2defbe82553

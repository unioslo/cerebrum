#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-
# Copyright 2009 University of Oslo, Norway
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

import os, sys, socket, time, md5

import cerebrum_path

import cereconf

import Cerebrum.lib
from Cerebrum.lib.spinews.spinews_services import *
from Cerebrum.lib.spinews.SignatureHandler import SignatureHandler
from Cerebrum import Errors

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

from ZSI.wstools import logging
from ZSI.ServiceContainer import AsServer
from ZSI.ServiceContainer import ServiceSOAPBinding
from ZSI.ServiceContainer import ServiceContainer
from ZSI.dispatch import SOAPRequestHandler
from ZSI import ParsedSoap, SoapWriter
from ZSI import _get_element_nsuri_name
from ZSI.wstools.Namespaces import OASIS, DSIG

from M2Crypto import SSL
from M2Crypto import X509


import time
import cerebrum_path
from Cerebrum.Utils import Factory
db=Factory.get("Database")(client_encoding='UTF-8')
db.cl_init(change_program="spinews")

co=Factory.get("Constants")()
group=Factory.get("Group")(db)
account=Factory.get("Account")(db)
host=Factory.get("Host")(db)
from Cerebrum.Entity import EntityQuarantine


ca_cert = None

def int_or_none(i):
    if i is None:
        return None
    else:
        return int(i)

class AuthenticationError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)



def search_persons(personspread=None, changelog_id=None):
    select=["person_info.person_id AS id",
            "person_info.export_id AS export_id",
            "person_full_name.name AS full_name",
            "person_first_name.name AS first_name",
            "person_last_name.name AS last_name",
            "person_work_title.name AS work_title",
            
            "contact_email.contact_value AS email",
            "contact_url.contact_value AS url",
            "contact_phone.contact_value AS phone",

            "person_info.birth_date AS birth_date",
            "person_nin.external_id AS nin",
            "entity_address.address_text AS address_text",
            "entity_address.postal_number AS postal_number",
            "entity_address.city AS city"
            ]
    tables=["person_info"]
    order_by=""
    binds={ "externalid_nin": co.externalid_fodselsnr,
            "nin_source": co.system_bdb,
            "system_cached": co.system_cached,
            "system_bdb": co.system_bdb,
            "address_source": co.system_fs,
            "name_first": co.name_first,
            "name_last": co.name_last,
            "name_full": co.name_full,
            "name_display": co.name_display,
            "name_personal_title": co.name_personal_title,
            "name_work_title": co.name_work_title,
            "contact_email": co.contact_email,
            "contact_url": co.contact_url,
            "contact_phone": co.contact_phone,
            "contact_email": co.contact_email,
            "contact_post_address": co.address_post,
            }
            
        

    if changelog_id is not None:
        tables.append("""JOIN change_log
                   ON (change_log.subject_entity = person_info.person_id
                     AND change_log.change_id > :changelog_id)""")
        binds["changelog_id"] = changelog_id
        order_by="ORDER BY change_log.change_id"

    if personspread is not None:
        tables.append("""JOIN entity_spread person_spread
        ON (account_spread.spread = :person_spread
          AND account_spread.entity_id = account_info.account_id)""")
        binds.append("person_spread", person_spread)

    tables.append("""LEFT JOIN entity_external_id person_nin
    ON (person_nin.entity_id = person_info.person_id
      AND person_nin.id_type = :externalid_nin
      AND person_nin.source_system = :nin_source )
    LEFT JOIN person_name person_first_name
      ON ((person_first_name.person_id = person_info.person_id)
        AND (person_first_name.source_system = :system_cached)
        AND (person_first_name.name_variant = :name_first))
    LEFT JOIN person_name person_last_name
    ON ((person_last_name.person_id = person_info.person_id)
      AND (person_last_name.source_system = :system_cached)
      AND (person_last_name.name_variant = :name_last))
    LEFT JOIN person_name person_full_name
    ON ((person_full_name.person_id = person_info.person_id)
      AND (person_full_name.source_system = :system_cached)
      AND (person_full_name.name_variant = :name_full))
    LEFT JOIN person_name person_display_name
    ON ((person_display_name.person_id = person_info.person_id)
      AND (person_display_name.source_system = :system_cached)
      AND (person_display_name.name_variant = :name_display))
    LEFT JOIN person_name person_personal_title
    ON ((person_personal_title.person_id = person_info.person_id)
      AND (person_personal_title.source_system = :system_cached)
      AND (person_personal_title.name_variant = :name_personal_title))
    LEFT JOIN person_name person_work_title
    ON ((person_work_title.person_id = person_info.person_id)
      AND (person_work_title.source_system = :system_cached)
      AND (person_work_title.name_variant = :name_work_title))
    LEFT JOIN entity_contact_info contact_email
    ON (contact_email.entity_id = person_info.person_id
      AND contact_email.contact_type = :contact_email
      AND contact_email.source_system = :system_bdb)
    LEFT JOIN entity_contact_info contact_url
    ON (contact_url.entity_id = person_info.person_id
      AND contact_url.contact_type = :contact_url
      AND contact_url.source_system = :system_cached) 
    LEFT JOIN entity_contact_info contact_phone
    ON (contact_phone.entity_id = person_info.person_id
      AND contact_phone.contact_type = :contact_phone
      AND contact_phone.source_system = :system_cached) 
    LEFT JOIN entity_address entity_address
    ON (entity_address.entity_id = person_info.person_id
      AND entity_address.source_system = :address_source
      AND entity_address.address_type = :contact_post_address)""")

    where=["(person_info.deceased_date IS NULL)"]
    sql = "SELECT " + ",\n".join(select)
    sql += " FROM " + "\n".join(tables)
    sql += " WHERE " + " AND ".join(where)
    sql += order_by

    return db.query(sql, binds)
               



# Merge this with Account.search()....
def search_accounts(account_spread, changelog_id=None, auth_type="MD5-crypt"):
    home=posix=owner=True
    
    select=["account_info.account_id AS id",
            "account_info.owner_id AS owner_id",
            "account_name.entity_name AS name",
            "account_authentication.auth_data AS passwd",
            ]
    tables=["account_info"]
    where=["""(account_info.expire_date > now()
              OR account_info.expire_date IS NULL)"""]
    order_by=""
    binds={'account_namespace': co.account_namespace,
           'group_namespace': co.group_namespace,
           'host_namespace': co.group_namespace,
           'name_display': co.name_display,
           'system_cached': co.system_cached,
           }
    binds['authentication_method'] = co.Authentication(auth_type)
    binds['account_spread'] = co.Spread(account_spread)

    if changelog_id is not None:
       tables.append("""JOIN change_log
         ON (change_log.subject_entity = account_info.account_id
            AND change_log.change_id > :changelog_id)""")
       order_by=" ORDER BY change_log.change_id"
       binds['changelog_id'] = changelog_id
    
    tables.append("""
    JOIN entity_spread account_spread
      ON (account_spread.spread = :account_spread
        AND account_spread.entity_id = account_info.account_id)
    JOIN entity_name account_name
      ON (account_info.account_id = account_name.entity_id
        AND account_name.value_domain = :account_namespace)
    LEFT JOIN account_authentication
      ON (account_authentication.method = :authentication_method
        AND account_authentication.account_id = account_info.account_id)
    """)

    if home:
        select.append("""
        homedir.home AS home,
        disk_info.path AS disk_path,
        disk_host_name.entity_name AS disk_host
        """)
        tables.append("""
        LEFT JOIN account_home
          ON (account_home.spread = :account_spread
            AND account_home.account_id = account_info.account_id)
        LEFT JOIN homedir
          ON (homedir.homedir_id = account_home.homedir_id)
        LEFT JOIN disk_info
          ON (disk_info.disk_id = homedir.disk_id)
        LEFT JOIN entity_name disk_host_name
          ON (disk_host_name.entity_id = disk_info.host_id
            AND disk_host_name.value_domain = :host_namespace)
        """)
    if posix:
        select.append("""
        posix_user.gecos AS gecos,
        posix_user.posix_uid AS posix_uid,
        posix_shell.shell AS shell,
        posix_shell.code_str AS shell_name,
        posix_group.posix_gid AS posix_gid,
        group_name.entity_name AS primary_group
        """)
        tables.append("""
        LEFT JOIN posix_user
          ON (account_info.account_id = posix_user.account_id)
        LEFT JOIN posix_shell_code posix_shell
          ON (posix_shell.code = posix_user.shell)
        LEFT JOIN group_info
          ON (group_info.group_id = posix_user.gid)
        LEFT JOIN posix_group
          ON (group_info.group_id = posix_group.group_id)
        LEFT JOIN entity_name group_name
          ON (group_info.group_id = group_name.entity_id
            AND group_name.value_domain = :group_namespace)
        """)
        
    if owner:
        select.append("""
        owner_group_name.entity_name AS owner_group_name,
        person_name.name AS full_name
        """)
        tables.append("""
        LEFT JOIN group_info owner_group_info
          ON (owner_group_info.group_id = account_info.owner_id)
        LEFT JOIN person_info
          ON (person_info.person_id = account_info.owner_id)
        LEFT JOIN entity_name owner_group_name
          ON (owner_group_name.entity_id = owner_group_info.group_id
            AND owner_group_name.value_domain = :group_namespace)
        LEFT JOIN person_name
          ON (person_name.person_id = person_info.person_id
            AND person_name.name_variant = :name_display
            AND person_name.source_system = :system_cached)
        """)

    sql = "SELECT " + ",\n".join(select)
    sql += " FROM " + "\n".join(tables)
    sql += " WHERE " + " AND ".join(where)
    sql += order_by

    return db.query(sql, binds)



# Groups -- merge into Group.search()
def search_groups(group_spread, changelog_id=None):
    posix=True

    select=["group_info.group_id AS id",
            "group_name.entity_name AS name"]
    tables=["group_info"]
    where = ["((group_info.expire_date > now() OR group_info.expire_date IS NULL)",
             "(group_info.visibility = :group_visibility_all))"]

    binds={'group_visibility_all': co.group_visibility_all}
    binds['group_spread'] = co.Spread(group_spread)
    order_by=""
    
    if changelog_id is not None:
        tables.append("""JOIN change_log
          ON (change_log.subject_entity = group_info.group_id
            AND change_log.change_id > :changelog_id)""")
        order_by=" ORDER BY change_log.change_id"
        binds['changelog_id'] = changelog_id

    tables.append("""
      JOIN entity_spread group_spread
      ON (group_spread.spread = :group_spread
        AND group_spread.entity_id = group_info.group_id)
      JOIN entity_name group_name
        ON (group_name.entity_id = group_info.group_id)""")
      
    if posix:
        select += ["posix_group.posix_gid AS posix_gid"]
        tables.append("""LEFT JOIN posix_group
          ON (posix_group.group_id = group_info.group_id)""")
        
    sql = "SELECT " + ",\n".join(select)
    sql += " FROM " + "\n".join(tables)
    sql += " WHERE " + " AND ".join(where)
    sql += order_by
    
    return db.query(sql, binds)



def search_ous(changelog_id=None):
    stedkode=True
    contactinfo=True
    select=["ou_info.ou_id AS id",
            "ou_info.name AS name",
            "ou_info.acronym AS acronym",
            "ou_info.short_name AS short_name",
            "ou_info.display_name AS display_name",
            "ou_info.sort_name AS sort_name",
            "ou_structure.parent_id AS parent_id",
            ]
    tables = ["ou_info"]
    order_by=""
    binds={"perspective": co.perspective_kjernen}

    if changelog_id is not None:
        tables.append("""JOIN change_log
         ON (change_log.subject_entity = ou_info.ou_id
           AND change_log.change_id > :changelog_id)""")
        order_by=" ORDER BY change_log.change_id"
        

    tables.append("""JOIN ou_structure
      ON (ou_structure.ou_id = ou_info.ou_id
        AND ou_structure.perspective = :perspective)""")
                  

    if stedkode:
        tables.append("""LEFT JOIN stedkode
          ON (stedkode.ou_id = ou_info.ou_id)
        LEFT JOIN stedkode stedkode_parent
          ON (stedkode_parent.ou_id = ou_structure.parent_id)""")

        select.append("""to_char(stedkode.landkode,'FM000')||
             to_char(stedkode.institusjon,'FM00000')||
             to_char(stedkode.fakultet,'FM00')||
             to_char(stedkode.institutt,'FM00')||
             to_char(stedkode.avdeling,'FM00') AS stedkode""")
        select.append("""to_char(stedkode_parent.landkode,'FM000')||
             to_char(stedkode_parent.institusjon,'FM00000')||
             to_char(stedkode_parent.fakultet,'FM00')||
             to_char(stedkode_parent.institutt,'FM00')||
             to_char(stedkode_parent.avdeling,'FM00') AS parent_stedkode""")
             
    if contactinfo:
        select+=["contact_email.contact_value AS email",
                 "contact_url.contact_value AS url",
                 "contact_phone.contact_value AS phone",
                 "contact_fax.contact_value AS fax",
                 "contact_address.contact_value AS post_address",
                 ]
        tables.append("""LEFT JOIN entity_contact_info contact_email
          ON (contact_email.entity_id = ou_info.ou_id
            AND contact_email.source_system = :system_kjernen
            AND contact_email.contact_type = :contact_email)
        LEFT JOIN entity_contact_info contact_url
          ON (contact_url.entity_id = ou_info.ou_id
            AND contact_url.source_system = :system_kjernen
            AND contact_url.contact_type = :contact_url)
        LEFT JOIN entity_contact_info contact_phone
          ON (contact_phone.entity_id = ou_info.ou_id
            AND contact_phone.source_system = :system_kjernen 
            AND contact_phone.contact_type = :contact_phone)
        LEFT JOIN entity_contact_info contact_fax
          ON (contact_fax.entity_id = ou_info.ou_id
            AND contact_fax.source_system = :system_kjernen
            AND contact_fax.contact_type = :contact_fax)
        LEFT JOIN entity_contact_info contact_address
          ON (contact_address.entity_id = ou_info.ou_id
            AND contact_address.source_system = :system_kjernen
            AND contact_address.contact_type = :contact_post_address)""")
        binds["contact_url"]=co.contact_url
        binds["contact_email"]=co.contact_email
        binds["contact_phone"]=co.contact_phone
        binds["contact_fax"]=co.contact_fax
        binds["contact_post_address"]=co.address_post
        binds["system_cached"]=co.system_cached
        binds["system_kjernen"]=co.system_kjernen

    sql = "SELECT " + ",\n".join(select)
    sql += " FROM " + "\n".join(tables)
    sql += order_by
    
    return db.query(sql, binds)




class group_members:
    def __init__(self, db, types=[int(co.entity_account)]):
        self.types=types
        
        memberships=db.query("""
        SELECT gm.group_id AS group_id,
        gm.member_type AS member_type,
        gm.member_id AS member_id,
        en.entity_name AS member_name
        FROM group_member gm
        LEFT OUTER JOIN entity_name en
           ON (en.entity_id = gm.member_id)
        WHERE
        en.value_domain = CASE
        WHEN gm.member_type=:entity_account THEN :account_namespace
        WHEN gm.member_type=:entity_group   THEN :group_namespace
        WHEN gm.member_type=:entity_host    THEN :host_namespace
        END
        """, { 'entity_account': int(co.entity_account),
               'entity_group': int(co.entity_group),
               'entity_host': int(co.entity_host),
               'account_namespace': int(co.account_namespace),
               'group_namespace': int(co.group_namespace),
               'host_namespace': int(co.host_namespace),
               })
        
        self.group_members={}
        self.member_names={}
        for m in memberships:
            if not m['group_id'] in self.group_members:
                self.group_members[m['group_id']]=[]
            self.group_members[m['group_id']].append((m['member_type'],
                                                      m['member_id']))
            self.member_names[m['member_id']]=m['member_name']

    def _get_members(self, id, groups, members, type, types):
        if type==None or type==co.entity_group:
            if not id in self.group_members:
                return 
            for t, i in self.group_members[id]:
                if not i in groups:
                    groups.add(i)
                    self._get_members(i, groups, members, t, types)
        elif type in types:
            members.append(id)
    
    def get_members(self, id, type=None, types=None):
        members=[]
        groups=set()
        if types==None: types=self.types
        self._get_members(id, groups, members, type, types)
        return members
    
    def get_members_name(self, id):
        return [self.member_names[i] for i in self.get_members(id)]
    def addto_group(self, d):
        d['members']=self.get_members_name(d['id'])
        return d


def search_aliases(changelog_id=None):
    select=["email_address.local_part AS local_part",
            "email_domain.domain AS domain",
            "email_target.target_id AS target_id",
            "email_target.target_type AS target_type",
            "email_address.address_id AS address_id",
            "email_primary_address.address_id AS primary_address_id",
            "primary_address.local_part AS primary_address_local_part",
            "primary_address_domain.domain AS primary_address_domain",
            "host_name.entity_name AS server_name",
            "account_info.account_id AS account_id",
            "account_name.entity_name AS account_name",
            ]
    tables=["email_address"]
    order_by=""
    
    if changelog_id is not None:
        tables.append("""JOIN change_log
        ON (change_log.subject_entity = email_address.address_id
            AND change_log.change_id > :changelog_id)""")
        order_by=" ORDER BY change_log.change_id"
        binds["changelog_id"]=changelog_id
        
        
    tables.append("""JOIN email_domain
  ON (email_domain.domain_id = email_address.domain_id)
JOIN email_target
  ON (email_address.target_id = email_target.target_id)
LEFT JOIN email_primary_address
  ON (email_primary_address.target_id = email_target.target_id)
LEFT JOIN entity_name host_name
  ON (host_name.entity_id = email_target.server_id
      AND host_name.value_domain = :host_namespace)
LEFT JOIN account_info
  ON (account_info.account_id = email_target.target_entity_id)
LEFT JOIN entity_name account_name
  ON (account_name.entity_id = account_info.account_id
      AND account_name.value_domain = :account_namespace)
LEFT JOIN email_address primary_address
  ON (primary_address.address_id = email_primary_address.address_id)
LEFT JOIN email_domain primary_address_domain
  ON (primary_address_domain.domain_id = primary_address.domain_id)
""")
    binds={
        'account_namespace': co.account_namespace,
        'host_namespace': co.host_namespace,
        }
        
    
    sql = "SELECT " + ",\n".join(select)
    sql += " FROM " + "\n".join(tables)
    sql += order_by

    return db.query(sql, binds)


def search_homedirs(hostname, status):
    include_posix=True

    binds={'account_namespace': co.account_namespace}
    binds['status']=int(co.AccountHomeStatus(status))

    host.clear()
    host.find_by_name(hostname)
    binds['host_id']=host.entity_id

    select =["homedir.homedir_id AS homedir_id",
             "homedir.home AS home",
             "disk.path AS disk_path",
             "account_name.entity_name AS account_name"]
    tables=["""disk_info disk
      JOIN homedir homedir ON (homedir.disk_id = disk.disk_id)
      LEFT JOIN entity_name account_name
        ON (account_name.entity_id = homedir.account_id
          AND account_name.value_domain = :account_namespace)
    """]
    where=["homedir.status = :status", "disk.host_id = :host_id"]

    if include_posix:
        select+=["posix_user.posix_uid AS posix_uid",
                 "posix_group.posix_gid AS posix_gid"]
        tables.append("""
          LEFT JOIN posix_user posix_user
            ON (posix_user.account_id = homedir.account_id)
          LEFT JOIN posix_group posix_group
            ON (posix_group.group_id = posix_user.gid)
        """)

    sql = "SELECT " + ",\n".join(select)
    sql += " FROM " + "\n".join(tables)
    sql += " WHERE " + " AND ".join(where)
    return db.query(sql, binds)

class quarantines:    
    def __init__(self):
        quarantines = {}
        quarantines_has = quarantines.has_key
        eq = EntityQuarantine(db)
        for quarantine in eq.list_entity_quarantines(only_active=True):
            id = quarantine["entity_id"]
            qtype = str(co.Quarantine(quarantine["quarantine_type"]))
            
            if quarantines_has(id):
                quarantines[id].append(qtype)
            else:
                quarantines[id] = [qtype]
        self.quarantines = quarantines

    def get_quarantines(self, id):
        return self.quarantines.get(id, [])


class DTO(object):
    def __init__(self, row, atypes):
        self._attrs = {}
        for key, value in row.dict().items():
            if key in atypes:
                atype = atypes[key]
                if value is not None:
                    self._attrs[key] = value

class GroupDTO(DTO):
    def __init__(self, row, atypes):
        super(GroupDTO, self).__init__(row, atypes)

class AccountDTO(DTO):
    def __init__(self, row, atypes):
        super(AccountDTO, self).__init__(row, atypes)
        self._attrs["homedir"] = account.resolve_homedir(
            account_name=row['name'],
            disk_path=row['disk_path'],
            home=row['home'])
        # TDB: extend get_gecos() to do this job.
        if not row["gecos"]:
            if row["full_name"]:
                self._attrs["gecos"] = row["full_name"]
            elif row["owner_group_name"]:
                self._attrs["gecos"] = "%s user (%s)" % (
                    row["name"], row["owner_group_name"])
            else:
                self._attrs["gecos"] = "%s user" % row["name"]
        self._quarantine = quarantines


class PersonDTO(DTO):
    def __init__(self, row, atypes):
        super(PersonDTO, self).__init__(row, atypes)

class OUDTO(DTO):
    def __init__(self, row, atypes):
        super(OUDTO, self).__init__(row, atypes)

class AliasDTO(DTO):
    def __init__(self, row, atypes):
        super(AliasDTO, self).__init__(row, atypes)

class HomedirDTO(DTO):
    def __init__(self, row, atypes):
        super(HomedirDTO, self).__init__(row, atypes)
        self._attrs["homedir"] = account.resolve_homedir(
            account_name=row['account_name'],
            disk_path=row['disk_path'],
            home=row['home'])

def get_node_value(node):
    if not node:
        return None
    value = None
    valueNode = node._get_firstChild()
    if valueNode:
        value = valueNode._get_nodeValue()
    if value:
        value.strip()
    return value
 
def get_element(elements, namespace, localname):
    for elt in elements:
        ns, name = _get_element_nsuri_name(elt)
        if ns == namespace and name == localname:
            return elt
    return None

def get_auth_values(ps):

    headerElements = ps.GetMyHeaderElements()
    securityElement = get_element(headerElements, OASIS.WSSE, 'Security')
    if not securityElement:
        raise RuntimeError('Unauthorized, missing Security-element in header')

    secChildren = securityElement._get_childNodes()
    if len(secChildren) == 0:
        raise RuntimeError('Unauthorized, Security-element has no children')
    
    usernameToken = get_element(secChildren, OASIS.WSSE, 'UsernameToken')
    if not usernameToken:
        raise RuntimeError('Unauthorized, UsernameToken not present')

    tokenChildren = usernameToken._get_childNodes()
    if len(tokenChildren) == 0:
        raise RuntimeError('Unauthorized, UsernameToken has no children')

    username = get_node_value(get_element(tokenChildren, OASIS.WSSE,
                                'Username'))
    if not username:
        raise RuntimeError('Unauthorized, Username not present')

    password = get_node_value(get_element(tokenChildren, OASIS.WSSE,
                                'Password'))
    if not password:
        raise RuntimeError('Unauthorized, Password not present')

    created = get_node_value(get_element(tokenChildren, OASIS.UTILITY,
                                'Created'))
    if not created:
        raise RuntimeError('Unauthorized, Created not present')
    return username, password, created

def check_created(created):
    gmCreated= time.strptime(created, '%Y-%m-%dT%H:%M:%SZ')
    ## allow timeout up to 10 secs.
    gmNow = time.gmtime((time.time() - 10))
    if gmCreated < gmNow:
        raise RuntimeError('Unauthorized, UsernameToken is expired')
    
def check_username_password(username, password):
    account.clear()
    try:
        account.find_by_name(str(username))
    except Errors.NotFoundError:
        raise AuthenticationError('Unauthorized, wrong username or password')
    if not account.verify_auth(password):
        raise AuthenticationError('Unauthorized, wrong username or password')


def authenticate(ps):
    debug = True
    username, password, created = get_auth_values(ps)
    check_created(created)
    if debug:
        print 'username =', username
        print 'password =', md5.new(password).hexdigest()
        print 'created =', created
    check_username_password(username, password)
    return username

class spinews(ServiceSOAPBinding):
    #_wsdl = "".join(open("spinews.wsdl").readlines())
    soapAction = {}
    root = {}

    def __init__(self, post='/', **kw):
        ServiceSOAPBinding.__init__(self, post)

    def set_homedir_status(self, ps):
        username = authenticate(ps)
        request = ps.Parse(setHomedirStatusRequest.typecode)
        status = str(request._status) 
        homedir_id = str(request._homedir_id)
        response = setHomedirStatusResponse()
        self.set_homedir_status_impl(homedir_id, status)
        return response

    def get_homedirs(self, ps):
        username = authenticate(ps)
        request = ps.Parse(getHomedirsRequest.typecode)
        status = str(request._status) 
        hostname = str(request._hostname)
        response = getHomedirsResponse()
        atypes = response.typecode.ofwhat[0].attribute_typecode_dict
        response._homedir = self.get_homedirs_impl(atypes, hostname, status)
        return response

    def get_aliases(self, ps):
        username = authenticate(ps)
        request = ps.Parse(getAliasesRequest.typecode)
        incremental_from = int_or_none(request._incremental_from)
        response = getAliasesResponse()
        atypes = response.typecode.ofwhat[0].attribute_typecode_dict
        response._alias = self.get_aliases_impl(atypes, incremental_from)
        return response

    def get_ous(self, ps):
        username = authenticate(ps)
        request = ps.Parse(getOUsRequest.typecode)
        incremental_from = int_or_none(request._incremental_from)
        response = getOUsResponse()
        atypes = response.typecode.ofwhat[0].attribute_typecode_dict
        response._ou = self.get_ous_impl(atypes, incremental_from)
        return response
        

    def get_groups(self, ps):
        username = authenticate(ps)
        request = ps.Parse(getGroupsRequest.typecode)
        groupspread = str(request._groupspread)
        accountspread = str(request._accountspread)
        incremental_from = int_or_none(request._incremental_from)
        response = getGroupsResponse()
        atypes = response.typecode.ofwhat[0].attribute_typecode_dict
        response._group = self.get_groups_impl(atypes,
                                               groupspread,
                                               accountspread,
                                               incremental_from)
        return response

    def get_accounts(self, ps):
        username = authenticate(ps)
        request = ps.Parse(getAccountsRequest.typecode)
        accountspread = str(request._accountspread)
        auth_type = str(request._auth_type)
        incremental_from = int_or_none(request._incremental_from)
        response = getAccountsResponse()
        atypes = response.typecode.ofwhat[0].attribute_typecode_dict
        response._account = self.get_accounts_impl(atypes,
                                                   accountspread,
                                                   auth_type,
                                                   incremental_from)
        return response


    def get_persons(self, ps):
        username = authenticate(ps)
        request = ps.Parse(getPersonsRequest.typecode)
        personspread = request._personspread
        incremental_from = int_or_none(request._incremental_from)
        response = getPersonsResponse()
        atypes = response.typecode.ofwhat[0].attribute_typecode_dict
        response._account = self.get_persons_impl(atypes,
                                                  personspread,
                                                  incremental_from)
        return response

    root[(getGroupsRequest.typecode.nspname,
          getGroupsRequest.typecode.pname)] = 'get_groups'
    root[(getPersonsRequest.typecode.nspname,
          getPersonsRequest.typecode.pname)] = 'get_persons'
    root[(getAccountsRequest.typecode.nspname,
          getAccountsRequest.typecode.pname)] = 'get_accounts'
    root[(getOUsRequest.typecode.nspname,
          getOUsRequest.typecode.pname)] = 'get_ous'
    root[(getAliasesRequest.typecode.nspname,
          getAliasesRequest.typecode.pname)] = 'get_aliases'
    root[(getHomedirsRequest.typecode.nspname,
          getHomedirsRequest.typecode.pname)] = 'get_homedirs'
    root[(setHomedirStatusRequest.typecode.nspname,
          setHomedirStatusRequest.typecode.pname)] = 'set_homedir_status'

    def get_persons_impl(self, atypes, personspread=None, changelog_id=None):
        persons=[]
        q=quarantines()
        for row in search_persons(personspread, changelog_id):
            p=PersonDTO(row, atypes)
            p.quarantines = q.get_quarantines(row['id'])
            persons.append(p)
        db.rollback()
        return persons
        

    def get_accounts_impl(self, atypes, accountspread, auth_type, changelog_id=None):
        accounts=[]
        q=quarantines()
        for row in search_accounts(accountspread, changelog_id, auth_type):
            a=AccountDTO(row, atypes)
            a.quarantines = (q.get_quarantines(row['id']) +
                             q.get_quarantines(row['owner_id']))
            accounts.append(a)
        db.rollback()
        return accounts

    def get_groups_impl(self, atypes, groupspread, accountspread, changelog_id=None): 
        groups=[]
        members=group_members(db)
        q=quarantines()
        for row in search_groups(groupspread, changelog_id):
            g=GroupDTO(row, atypes)
            g.members = members.get_members_name(row['id'])
            g.quarantines = q.get_quarantines(row['id'])
            groups.append(g)
        db.rollback()
        return groups

    def get_ous_impl(self, atypes, changelog_id=None):
        ous=[]
        q=quarantines()
        for row in search_ous(changelog_id):
            o=OUDTO(row, atypes)
            o.quarantines = q.get_quarantines(row['id'])
            ous.append(o)
        db.rollback()
        return ous

    def get_aliases_impl(self, atypes, changelog_id=None):
        aliases=[]
        for row in search_aliases(changelog_id):
            a=AliasDTO(row, atypes)
            aliases.append(a)
        db.rollback()
        return aliases

    def get_homedirs_impl(self, atypes, hostname, status):
        homedirs=[]
        for row in search_homedirs(hostname, status):
            h=HomedirDTO(row, atypes)
            homedirs.append(h)
        db.rollback()
        return homedirs

    def set_homedir_status_impl(self, homedir_id, status):
        status=int(co.AccountHomeStatus(status))
        account.clear()
        r=account.get_homedir(homedir_id)
        account.find(r['account_id'])
        account.set_homedir(current_id=homedir_id, status=status)
        db.commit()


def test_impl(fun, *args):
    import time
    t=time.time()
    r=fun(*args)
    if r is not None:
        l=len(r)
    else:
        l=None
    t=time.time()-t
    return fun.__name__, l, t

def test_soap(fun, cl, cattr, **kw):
    #fun=root[(cl.typecode.nspname, cl.typecode.pname)]
    o=cl()
    for k,w in kw.items():
        setattr(o,"_"+k,w)
    t=time.time()
    s=str(SoapWriter().serialize(o))
    ps=ParsedSoap(s)
    print ps.GetMyHeaderElements()
    rps=fun(ps)
    t1=time.time()-t
    if cattr is not None:
        l=len(getattr(rps, cattr))
    else:
        l=None
    rs=str(SoapWriter().serialize(rps))
    open("/tmp/log.%s" % fun.__name__, 'w').write(rs)
    #rps=ParsedSoap(rs)
    t2=time.time()-t
    return fun.__name__, l, t1, t2
    



def test():
    sp=spinews()
    print test_soap(sp.set_homedir_status, setHomedirStatusRequest, None,
                    homedir_id=85752, status="not_created")
    print test_soap(sp.get_homedirs, getHomedirsRequest, "_homedir",
                    hostname="jak.itea.ntnu.no", status="not_created")
    print test_soap(sp.get_ous, getOUsRequest, "_ou")
    print test_soap(sp.get_accounts, getAccountsRequest, "_account",
                    accountspread="user@stud")
    print test_soap(sp.get_aliases, getAliasesRequest, "_alias")
    print test_soap(sp.get_groups, getGroupsRequest, "_group",
                    accountspread="user@stud", groupspread="group@ntnu")

    print test_impl(sp.get_persons_impl, {})
    print test_impl(sp.set_homedir_status_impl, 85752L, "not_created")
    print test_impl(sp.get_homedirs_impl, {}, "jak.itea.ntnu.no", "not_created")
    print test_impl(sp.get_aliases_impl, {})
    print test_impl(sp.get_ous_impl, {})
    print test_impl(sp.get_accounts_impl, {}, "user@stud", "MD5-crypt")
    print test_impl(sp.get_groups_impl, {}, "group@ntnu", "user@stud")


class SecureServiceContainer(ServiceContainer):
    def _init__(self, server_address, services=[], RequestHandlerClass=SOAPRequestHandler):
        ServiceContainer.__init__(self, server_address, services, RequestHandlerClass)

    def server_bind(self):
        ## override the default methid and make
        ## a socket with SSL/TLS
        ctx = init_ssl()
        self.socket = SSL.Connection(ctx)
        self.socket.set_client_CA_list_from_context()
        if self.allow_reuse_address:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.server_address)
        host, port = self.socket.getsockname()[:2]
        self.server_name = socket.getfqdn(host)
        self.server_address = self.socket.getsockname()
        self.server_port = port

    def get_request(self):
        (conn, addr ) = self.socket.accept()
        ## check the peer's certificate
        ## should we check certificates here?
        client_cert = conn.get_peer_cert()
        if client_cert:
            client_subject  = client_cert.get_subject()
            ## print '@@@@@@@@@@@@@@@@@@@@@@@@@@@@@', client_subject.CN
            ## check if the certificate have been signed by CA
            ## more checks?
            if client_cert.verify(ca_cert.get_pubkey()):
                return (conn, addr)
        conn.clear()
        return( conn, addr )

def RunAsServer(port=80, services=(), fork=False):
    address = ('', port)
    sc = SecureServiceContainer(address, services=services)
    if fork:
        pass
    sc.serve_forever()


def phrase_callback(v,prompt1='Enter passphrase:',prompt2='Verify passphrase:'):
    return cereconf.SSL_KEY_FILE_PASSWORD

def init_ssl(debug=None):
    ctx = SSL.Context('sslv23')
    ## certificate and private-key in the same file
    ctx.load_cert(cereconf.SSL_KEY_FILE, callback=phrase_callback)
    ctx.load_verify_info(cafile=cereconf.SSL_CA_FILE)
    ctx.load_client_ca(cereconf.SSL_CA_FILE)
    ## do not use sslv2
    ctx_options = SSL.op_no_sslv2
    ctx.set_options(ctx_options)
    ## always verify the peer's certificate
    ctx.set_verify(SSL.verify_peer, 9)
    ctx.set_session_id_ctx('ceresync_srv')
    return ctx

test()
print "starting..."
ca_cert = X509.load_cert(cereconf.SSL_CA_FILE)
RunAsServer(port=cereconf.SPINEWS_PORT, services=[spinews(),])

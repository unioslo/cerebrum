from ZSI.wstools import logging
from ZSI.ServiceContainer import AsServer

import cerebrum_path
import Cerebrum.lib
from Cerebrum.lib.spinews.spinews_services import *
from ZSI.ServiceContainer import ServiceSOAPBinding



import time
import cerebrum_path
from Cerebrum.Utils import Factory
db=Factory.get("Database")()
co=Factory.get("Constants")()
group=Factory.get("Group")(db)
account=Factory.get("Account")(db)
from Cerebrum.Entity import EntityQuarantine



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
       order_by="ORDER BY change_log.change_id"
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
        order_by="ORDER BY change_log.change_id"
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
        order_by="ORDER BY change_log.change_id"
        

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


def search_alias(changelog_id=None):
    



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


class GroupDTO:
    def __init__(self, row, members=[], quarantines=[]):
        self._attrs = {}
        self._attrs["name"] = row["name"]
        self._attrs["posix_gid"] = row["posix_gid"]
        self._member = members
        self._quarantine = quarantines

class AccountDTO:
    def __init__(self, row, quarantines=[]):
        self._attrs={}
        self._attrs["name"] = row["name"]
        self._attrs["passwd"] = row["passwd"]
        self._attrs["home"] = row["home"]
        self._attrs["disk_host"] = row["disk_host"]
        self._attrs["disk_path"] = row["disk_path"]
        self._attrs["gecos"] = row["gecos"]
        self._attrs["shell"] = row["shell"]
        self._attrs["shell_name"] = row["shell_name"]
        self._attrs["posix_uid"] = row["posix_uid"]
        self._attrs["posix_gid"] = row["posix_gid"]
        self._attrs["primary_group"] = row["primary_group"]
        self._attrs["full_name"] = row["full_name"]
        self._attrs["owner_group_name"] = row["owner_group_name"]
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


class OUDTO:
    def __init__(self, row, quarantines=[]):
        self._attrs["id"] = row["id"]
        self._attrs["name"] = row["name"]
        self._attrs["acronym"] = row["acronym"]
        self._attrs["short_name"] = row["short_name"]
        self._attrs["display_name"] = row["display_name"]
        self._attrs["sort_name"] = row["sort_name"]
        self._attrs["parent_id"] = row["parent_id"]
        self._attrs["stedkode"] = row["stedkode"]
        self._attrs["parent_stedkode"] = row["parent_stedkode"]
        self._attrs["email"] = row["email"]
        self._attrs["url"] = row["url"]
        self._attrs["phone"] = row["phone"]
        self._attrs["fax"] = row["fax"]
        self._attrs["post_address"] = row["post_address"]
        self._quarantine = quarantines

class AliasDTO:
    def __init__(self, row):
        


class spinews(ServiceSOAPBinding):
    #_wsdl = "".join(open("spinews.wsdl").readlines())
    soapAction = {}
    root = {}

    def __init__(self, post='/', **kw):
        ServiceSOAPBinding.__init__(self, post)


    def get_groups(self, ps):
        request = ps.Parse(getGroupsRequest.typecode)
        response = getGroupsResponse()
        response._group = self.get_groups_impl()
        return response

    def get_accounts(self, ps):
        request = ps.Parse(getAccountsRequest.typecode)
        response = getAccountsResponse()
        response._account = self.get_accounts_impl()
        return response

    soapAction[''] = 'get_groups'
    soapAction[''] = 'get_accounts'
    root[(getGroupsRequest.typecode.nspname,
          getGroupsRequest.typecode.pname)] = 'get_groups'
    root[(getAccountsRequest.typecode.nspname,
          getAccountsRequest.typecode.pname)] = 'get_accounts'


    def get_groups_foo(self):
        return [GroupDTO("foo", 42),
                GroupDTO("bar", 66,
                      members=["steinarh", "laa"], 
                      quarantines=["badboy"])]
   
    def get_accounts_impl(self):
        accounts=[]
        q=quarantines()
        for row in search_accounts("user@stud"):
            a=AccountDTO(row)
            a.quarantines = (q.get_quarantines(row['id']) +
                             q.get_quarantines(row['owner_id']))
            accounts.append(a)
        return accounts

    def get_groups_impl(self): 
        groups=[]
        members=group_members(db)
        q=quarantines()
        for row in search_groups("group@ntnu"):
            g=GroupDTO(row)
            g.members = members.get_members_name(row['id'])
            g.quarantines = q.get_quarantines(row['id'])
            groups.append(g)
        return groups


    def get_ous_impl(self):
        ous=[]
        q=quarantines()
        for row in search_ous():
            o=OUDTO(row)
            o.quarantines = q.get_quarantines(row['id'])
            ous.append(o)
        return ous

    def get_groups_impl2(self):
        pass

def test_impl(fun):
    import time
    t=time.time()
    l=len(fun())
    t=time.time()-t
    return fun.__name__, l, t
    
def test():
    sp=spinews()
    print test_impl(sp.get_ous_impl)
    print test_impl(sp.get_accounts_impl)
    print test_impl(sp.get_groups_impl)

test()
AsServer(port=8669, services=[spinews(),])

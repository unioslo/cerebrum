from SpineLib.DumpClass import DumpClass, Struct
from SpineLib.Builder import Attribute, Builder
from SpineLib.DatabaseClass import DatabaseTransactionClass
from SpineLib.Date import Date
from SpineLib import Registry
from Types import Spread, OUPerspectiveType, AuthenticationType, SourceSystem
registry = Registry.get_registry()

import sets
import cerebrum_path
#import Cerebrum.spine
from Cerebrum.Utils import Factory
from Cerebrum.modules.EntityTrait import EntityTrait
from Cerebrum.Entity import EntityQuarantine

co = Factory.get('Constants')()


# Accountviews are accounts as "seen from" a spread, and may contain
# spread-spesific data.  They are tailored for efficient dumping of
# all data related to a spread.

# restricts accounts to:
# 1. Only accounts
# 2. With name
# 3. With relevant spread
# 4. Not expired


"""
class PasswdView(Builder):
    slots = [
        Attribute('type', str),
        Attribute('value', str)
        ]

class PhoneView(Builder):
    slots = [
        Attribute('type', str),
        Attribute('number', str)
        ]

class AdressView(Builder):
    slots = [
        Attribute('type', str),
        Attribute('street', str)
        ]
"""

class AccountView(DumpClass):
    slots = (
        Attribute('name', str),
        Attribute('passwd', str),
        
        Attribute('homedir', str),
        Attribute('home', str),
        Attribute('disk_path', str),
        Attribute('disk_host', str),

        Attribute('gecos', str),
        Attribute('posix_uid', int),
        Attribute('shell', str),
        Attribute('shell_name', str),

        Attribute('posix_gid', int),
        Attribute('primary_group', str),

        Attribute('owner_group_name', str),
        Attribute('full_name', str),
        
        Attribute('quarantines', [str]),
        )

account_search = """
-- SELECT count(account_info), count(posix_user)
SELECT
account_info.account_id AS id,
account_name.entity_name AS name,
account_authentication.auth_data AS passwd,
-- homedir
homedir.home AS home,
disk_info.path AS disk_path,
disk_host_name.entity_name AS disk_host,
-- posix
posix_user.gecos AS gecos,
posix_user.posix_uid AS posix_uid,
posix_shell.shell AS shell,
posix_shell.code_str AS shell_name,
posix_group.posix_gid AS posix_gid,
group_name.entity_name AS primary_group,
-- owner
owner_group_name.entity_name AS owner_group_name,
person_name.name AS full_name
--
FROM account_info
%s -- insert changelog here
JOIN entity_spread account_spread
ON (account_spread.spread = :account_spread
  AND account_spread.entity_id = account_info.account_id)
JOIN entity_name account_name
ON (account_info.account_id = account_name.entity_id
  AND account_name.value_domain = :account_namespace)
LEFT JOIN account_authentication
ON (account_authentication.method = :authentication_method
  AND account_authentication.account_id = account_info.account_id)
-- homedir
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
-- posix
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
-- owner
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
WHERE (account_info.expire_date > now() OR account_info.expire_date IS NULL)
"""

account_search_cl = """
JOIN change_log
ON (change_log.subject_entity = account_info.account_id AND change_log.change_id > :changelog_id)
"""

account_search_cl_o = """
ORDER BY change_log.change_id
"""

# Groupviews are groups as seen from a spread.
# They are tailored for efficient dumping of all data related to a spread.

class GroupView(Builder):
    slots = (
        Attribute('name', str),
        Attribute('posix_gid', int),
        Attribute('members', [str]),
        #Attribute('members_tree', [str]),
        Attribute('quarantines', [str])
        )

group_search="""
SELECT
group_info.group_id AS id,
group_name.entity_name AS name,
posix_group.posix_gid AS posix_gid
FROM group_info
%s
JOIN entity_spread group_spread
ON (group_spread.spread = :group_spread
  AND group_spread.entity_id = group_info.group_id)
JOIN entity_name group_name
ON (group_name.entity_id = group_info.group_id)
LEFT JOIN posix_group
ON (posix_group.group_id = group_info.group_id)
WHERE ((group_info.expire_date > now() OR group_info.expire_date IS NULL)
  AND (group_info.visibility = :group_visibility_all))
"""
group_search_cl = """
JOIN change_log
ON (change_log.subject_entity = group_info.group_id AND change_log.change_id > :changelog_id)
"""

group_search_cl_o = """
ORDER BY change_log.change_id
"""

class group_members:
    def __init__(self, db, types=[int(co.entity_account)]):
        self.types=types
        
        memberships=db.query("""
        SELECT gm.group_id, gm.operation, gm.member_type, gm.member_id,
        en.entity_name AS member_name
        FROM group_member gm, entity_name en
        WHERE
        en.entity_id = gm.member_id AND
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
        
        class member_group:
            def __init__(self):
                self.union=[]
                self.difference=[]
                self.intersection=[]
                
        opt={
            int(co.group_memberop_union): "union",
            int(co.group_memberop_intersection): "intersection",
            int(co.group_memberop_difference): "difference"
            }
        
        self.groups={}
        self.member_names={}
        for m in memberships:
            getattr(self.groups.setdefault(m[0], member_group()),
                    opt[m[1]]).append((m[2], m[3]))
            self.member_names[m[3]]=m[4]
    
    def get_members(self, id, type=None, types=None):
        if types==None: types=self.types
        #print "get_members(%d, %s, %s)" % (id, type, types)
        if type==None or type==co.entity_group:
            members=sets.Set()
            intersection=sets.Set()
            difference=sets.Set()
            if not id in self.groups:
                return members # no members
            for t, i in self.groups[id].union:
                members.union_update(self.get_members(i, t, types))
                union=members.copy()
            if self.groups[id].intersection:
                for t, i in self.groups[id].intersection:
                    intersection.union_update(self.get_members(i, t, types))
                members.intersection_update(intersection)
            if self.groups[id].difference:
                for t, i in self.groups[id].difference:
                    difference.union_update(self.get_members(i, t, types))
                members.difference_update(difference)
            #print union, intersection, difference
            #print "get_members(%d) =" % id, members
            return members
        elif type in types:
            #print "get_members(%d) =" % id, [id]
            return [id]
        else:
            #print "get_members(%d) =" % id, []
            return []
    
    def get_members_name(self, id):
        return [self.member_names[i] for i in self.get_members(id)]
    def addto_group(self, d):
        d['members']=self.get_members_name(d['id'])
        return d
    

class OUView(Builder):
    slots = (
        Attribute('id', int),
        Attribute('name', str),
        Attribute('acronym', str),
        Attribute('short_name', str),
        Attribute('display_name', str),
        Attribute('sort_name', str),
        Attribute('parent_id', int),
        Attribute('email', str),
        Attribute('url', str),
        Attribute('phone', str),
        Attribute('fax', str),
        Attribute('post_address', str),
        Attribute('stedkode', str),
        Attribute('parent_stedkode', str),
        Attribute('quarantines', [str]),
    )

ou_search="""
SELECT
ou_info.ou_id AS id,
ou_info.name AS name,
ou_info.acronym AS acronym,
ou_info.short_name AS short_name,
ou_info.display_name AS display_name,
ou_info.sort_name AS sort_name,
ou_structure.parent_id AS parent_id,
contact_email.contact_value AS email,
contact_url.contact_value AS url,
contact_phone.contact_value AS phone,
contact_fax.contact_value AS fax,
contact_address.contact_value AS post_address,
-- stedkode
lpad(stedkode.landkode,3,'0')||lpad(stedkode.institusjon,5,'0')||lpad(stedkode.fakultet,2,'0')||lpad(stedkode.institutt,2,'0')||lpad(stedkode.avdeling,2,'0') AS stedkode,
lpad(stedkode_parent.landkode,3,'0')||lpad(stedkode_parent.institusjon,5,'0')||lpad(stedkode_parent.fakultet,2,'0')||lpad(stedkode_parent.institutt,2,'0')||lpad(stedkode_parent.avdeling,2,'0') AS parent_stedkode
--
FROM ou_info
%s
JOIN ou_structure
ON (ou_structure.ou_id = ou_info.ou_id AND ou_structure.perspective = :perspective)
-- stedkode
LEFT JOIN stedkode
  ON (stedkode.ou_id = ou_info.ou_id)
LEFT JOIN stedkode stedkode_parent
  ON (stedkode_parent.ou_id = ou_structure.parent_id)
-- contacts
LEFT JOIN entity_contact_info contact_email
  ON (contact_email.entity_id = ou_info.ou_id
    AND contact_email.source_system = :system_cached
    AND contact_email.contact_type = :contact_email)
LEFT JOIN entity_contact_info contact_url
  ON (contact_url.entity_id = ou_info.ou_id
    AND contact_url.source_system = :system_cached
    AND contact_url.contact_type = :contact_url)
LEFT JOIN entity_contact_info contact_phone
  ON (contact_phone.entity_id = ou_info.ou_id
    AND contact_phone.source_system = :system_cached 
    AND contact_phone.contact_type = :contact_phone)
LEFT JOIN entity_contact_info contact_fax
  ON (contact_fax.entity_id = ou_info.ou_id
    AND contact_fax.source_system = :system_cached
    AND contact_fax.contact_type = :contact_fax)
LEFT JOIN entity_contact_info contact_address
  ON (contact_address.entity_id = ou_info.ou_id
    AND contact_address.source_system = :system_cached
    AND contact_address.contact_type = :contact_post_address)
"""

ou_search_cl = """
JOIN change_log
ON (change_log.subject_entity = ou_info.ou_id AND change_log.change_id > :changelog_id)
"""

ou_search_cl_o = """
ORDER BY change_log.change_id
"""



# PersionView contains NIN, so access should be somewhat strict.

# restricts persons to:
# 1. Only persons
# 2. Only persons with NIN
# 3. Not deceased



class PersonView(Builder):
    slots = (
        Attribute('id', int),
        Attribute('export_id', str),
        Attribute('full_name', str),
        Attribute('first_name', str),
        Attribute('last_name', str),
        Attribute('work_title', str),
        
        Attribute('email', str),
        Attribute('url', str),
        Attribute('phone', str),

        Attribute('primary_account', int),
        Attribute('primary_account_name', str),
        
        Attribute('birth_date', Date),
        Attribute('nin', str),
        Attribute('address_text', str),
        Attribute('postal_number', int),
        Attribute('city', str),

        Attribute('affiliations', [int]),
        Attribute('traits', [int]),
        Attribute('quarantines', [str]),
    )

person_search="""
SELECT
person_info.person_id AS id,
person_info.export_id AS export_id,
person_full_name.name AS full_name,
person_first_name.name AS first_name,
person_last_name.name AS last_name,
person_work_title.name AS work_title,

contact_email.contact_value AS email,
contact_url.contact_value AS url,
contact_phone.contact_value AS phone,

account_type.account_id AS primary_account,
account_name.entity_name AS primary_account_name,

person_info.birth_date AS birth_date,
person_nin.external_id AS nin,
entity_address.address_text AS address_text,
entity_address.postal_number AS postal_number,
entity_address.city AS city

FROM person_info
%s
LEFT JOIN entity_external_id person_nin
ON (person_nin.entity_id = person_info.person_id
  AND person_nin.id_type = :externalid_nin
  AND person_nin.source_system = :nin_source )
-- names & titles
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
LEFT JOIN person_name person_personal_title
ON ((person_personal_title.person_id = person_info.person_id)
  AND (person_personal_title.source_system = :system_cached)
  AND (person_personal_title.name_variant = :name_personal_title))
LEFT JOIN person_name person_work_title
ON ((person_work_title.person_id = person_info.person_id)
  AND (person_work_title.source_system = :system_cached)
  AND (person_work_title.name_variant = :name_work_title))
-- contactinfo
LEFT JOIN entity_contact_info contact_email
ON (contact_email.entity_id = person_info.person_id
  AND contact_email.contact_type = :contact_email
  AND contact_email.source_system = :system_cached) 
LEFT JOIN entity_contact_info contact_url
ON (contact_url.entity_id = person_info.person_id
  AND contact_url.contact_type = :contact_url
  AND contact_url.source_system = :system_cached) 
LEFT JOIN entity_contact_info contact_phone
ON (contact_phone.entity_id = person_info.person_id
  AND contact_phone.contact_type = :contact_phone
  AND contact_phone.source_system = :system_cached) 
-- address
LEFT JOIN entity_address entity_address
ON (entity_address.entity_id = person_info.person_id
  AND entity_address.source_system = :address_source
  AND entity_address.address_type = :contact_post_address)
-- primary_account
LEFT JOIN account_type account_type
ON (account_type.person_id = person_info.person_id
  AND account_type.priority IN
    (SELECT min(priority) FROM account_type
      WHERE person_id = account_type.person_id))
LEFT JOIN entity_name account_name
ON (account_name.entity_id = account_type.account_id
  AND account_name.value_domain = :account_namespace)
-- Only need living people
WHERE (person_info.deceased_date IS NULL)
"""
person_search_cl = """
JOIN change_log
ON (change_log.subject_entity = person_info.person_id AND change_log.change_id > :changelog_id)
"""

person_search_cl_o = """
ORDER BY change_log.change_id
"""


class View(DatabaseTransactionClass):
    def __init__(self, *args, **vargs):
        super(View, self).__init__(spread=None, *args, **vargs)

        self.acc = Factory.get('Account')(self.get_database())
        self.person = Factory.get('Person')(self.get_database())
        self.db = self.get_database()

        self.query_data = {
            "account_namespace": co.account_namespace,
            "group_namespace": co.group_namespace,
            "host_namespace": co.host_namespace,
            "system_cached": co.system_cached,
            "name_display": co.name_display,
            "name_full": co.name_full,
            "name_first": co.name_first,
            "name_last": co.name_last,
            "name_personal_title": co.name_personal_title,
            "name_work_title": co.name_work_title,
            "externalid_nin": co.externalid_fodselsnr,
            "nin_source": co.system_kjernen,
            "group_visibility_all": co.group_visibility_all,
            "contact_url": co.contact_url,
            "contact_email": co.contact_email,
            "contact_phone": co.contact_phone,
            "contact_fax": co.contact_fax,
            "contact_post_address": co.address_post,
            "address_source": co.system_fs,
            "perspective": co.perspective_kjernen,
        }
        
    def extend_account(self, d):
        d["homedir"] = self.acc.resolve_homedir(account_name=d['name'],
                                                disk_path=d['disk_path'],
                                                home=d['home'])
        # TDB: extend get_gecos() to do this job.
        if not d["gecos"]:
            if d["full_name"]:
                d["gecos"] = d["full_name"]
            elif d["owner_group_name"]:
                d["gecos"] = "%s user (%s)" %(d["name"], d["owner_group_name"])
            else:
                d["gecos"] = "%s user" % d["name"]
        return d

    def extend_persons(self, rows):
        persons = []

        traits = {}
        traits_has = traits.has_key
        for trait in EntityTrait(self.db).list_traits():
            pid = trait[0]
            tid = trait[1]

            if traits_has(pid):
                traits[pid].append(tid)
            else:
                traits[pid] = [tid]
    
        affiliations = {}
        affiliations_has = affiliations.has_key
        for affiliation in self.person.list_affiliations():
            pid = affiliation[0]
            aid = affiliation[1]

            if affiliations_has(pid):
                affiliations[pid].append(aid)
            else:
                affiliations[pid] = [aid]

        for row in rows:
            row = row.dict()
            pid = row['id']
            if traits_has(pid):
                row['traits'] = traits[pid]
            if affiliations_has(pid):
                row['affiliations'] = affiliations[pid]

            persons.append(row)
        return persons


    def add_quarantines(self, entities):
        quarantines = {}
        quarantines_has = quarantines.has_key
        eq = EntityQuarantine(self.db)
        for quarantine in eq.list_entity_quarantines(only_active=True):
            id = quarantine["entity_id"]
            qtype = str(co.Quarantine(quarantine["quarantine_type"]))
            
            if quarantines_has(id):
                quarantines[id].append(qtype)
            else:
                quarantines[id] = [qtype]

        for e in entities:
            e["quarantines"] = quarantines.get(e["id"], [])
    
        return entities

    # Allow the user to define spreads.
    # These must be set 'globally' because membership-type
    # attributes will need more than one spread.
    
    def set_authentication_method(self, method):
        self.query_data["authentication_method"]=method.get_id()
    set_authentication_method.signature = None
    set_authentication_method.signature_args = [AuthenticationType]
    set_authentication_method.signature_auth_attr = 0
    def set_account_spread(self, spread):
        self.query_data["account_spread"]=spread.get_id()
    set_account_spread.signature = None
    set_account_spread.signature_args = [Spread]
    set_account_spread.signature_auth_attr = 0
    def set_group_spread(self, spread):
        self.query_data["group_spread"]=spread.get_id()
    set_group_spread.signature=None
    set_group_spread.signature_args=[Spread]
    set_group_spread.signature_auth_attr = 0
    def set_perspective(self, perspective):
        self.query_data["perspective"]=perspective.get_id()
    set_perspective.signature=None
    set_perspective.signature_args=[OUPerspectiveType]
    def set_changelog(self, id):
        self.query_data["changelog_id"]=id
    set_changelog.signature=None
    set_changelog.signature_args=[int]
    def set_source_system(self, source):
        self.query_data["source_system"]=source
    set_source_system.signature=None
    set_source_system.signature_args=[SourceSystem]
    
    

    def get_accounts(self):
        db = self.get_database()
        rows=db.query(account_search % "", self.query_data)
        return self.add_quarantines([self.extend_account(r.dict())
                                     for r in rows])
    get_accounts.signature = [Struct(AccountView)]
    def get_accounts_cl(self):
        db = self.get_database()
        rows=db.query(account_search % account_search_cl + account_search_cl_o,
                      self.query_data)
        return self.add_quarantines([self.extend_account(r.dict())
                                     for r in rows])
    get_accounts_cl.signature = [Struct(AccountView)]
    def get_groups(self):
        db = self.get_database()
        members=group_members(db)
        rows=db.query(group_search % "", self.query_data)
        return self.add_quarantines([members.addto_group(r.dict())
                                     for r in rows])
    get_groups.signature = [Struct(GroupView)]
    def get_groups_cl(self):
        db = self.get_database()
        members=group_members(db)
        rows=db.query(group_search % group_search_cl + group_search_cl_o,
                      self.query_data)
        return self.add_quarantines([members.addto_group(r.dict())
                                     for r in rows])
    get_groups_cl.signature = [Struct(GroupView)]
    def get_ous(self):
        db = self.get_database()
        rows=db.query(ou_search % "", self.query_data)
        return self.add_quarantines([r.dict() for r in rows])
    get_ous.signature = [Struct(OUView)]
    def get_ous_cl(self):
        db = self.get_database()
        rows=db.query(ou_search % ou_search_cl + ou_search_cl_o,
                      self.query_data)
        return self.add_quarantines([r.dict() for r in rows])
    get_ous_cl.signature = [Struct(OUView)]
    def get_persons(self):
        db = self.get_database()
        rows=db.query(person_search % "", self.query_data)
        return self.add_quarantines(self.extend_persons(rows))
    get_persons.signature = [Struct(PersonView)]
    def get_persons_cl(self):
        db = self.get_database()
        rows=db.query(person_search % person_search_cl +person_search_cl_o,
                      self.query_data)
        return self.add_quarantines(self.extend_persons(rows))
    get_persons_cl.signature = [Struct(PersonView)]
registry.register_class(View)

"""
v=tr.get_view()
v.set_authentication_method(tr.get_authentication_type("MD5-crypt"))
v.set_account_spread(tr.get_spread("user@stud"))
v.set_group_spread(tr.get_spread("group@ntnu"))
v.set_changelog(90000)
"""

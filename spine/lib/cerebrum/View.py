from SpineLib.DumpClass import DumpClass, Struct
from SpineLib.Builder import Attribute, Builder
from SpineLib.DatabaseClass import DatabaseTransactionClass
from SpineLib import Registry
registry = Registry.get_registry()

import cerebrum_path
import Cerebrum.spine
from Cerebrum.Utils import Factory
db = Factory.get('Database')()

# Accountviews are accounts as "sefen from" a spread, and may contain
# spread-spesific data.  They are tailored for efficient dumping of
# all data related to a spread.

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
        
        #Attribute('quarantenes', [str])
        )

account_search = """
-- SELECT count(account_info), count(posix_user)
SELECT
account_info.account_id AS id
account_name.entity_name AS name,
account_authentication.auth_data AS passwd,
-- homedir
homedir.home AS homedir,
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
JOIN entity_spread account_spread
ON (account_spread.spread = 173 AND account_spread.entity_id = account_info.account_id)
JOIN entity_name account_name
ON (account_info.account_id = account_name.entity_id AND account_name.value_domain = 363)
LEFT JOIN account_authentication
ON (account_authentication.method = 405 AND account_authentication.account_id = account_info.account_id)
-- homedir
LEFT JOIN account_home
ON (account_home.spread = 173 AND account_home.account_id = account_info.account_id)
LEFT JOIN homedir
ON (homedir.homedir_id = account_home.homedir_id)
LEFT JOIN disk_info
ON (disk_info.disk_id = homedir.disk_id)
LEFT JOIN entity_name disk_host_name
ON (disk_host_name.entity_id = disk_info.host_id)
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
ON (group_info.group_id = group_name.entity_id AND group_name.value_domain = 364)
-- owner
LEFT JOIN group_info owner_group_info
ON (owner_group_info.group_id = account_info.owner_id)
LEFT JOIN entity_name owner_group_name
ON (owner_group_name.entity_id = owner_group_info.group_id AND owner_group_name.value_domain = 364)
LEFT JOIN person_info
ON (person_info.person_id = account_info.owner_id)
LEFT JOIN person_name
ON (person_name.person_id = person_info.person_id AND person_name.name_variant = 220 AND person_name.source_system = 288)
WHERE (account_info.expire_date > now() OR account_info.expire_date IS NULL)
"""

account_search_cl = """
JOIN change_log
ON (change_log.subject_entity = account_info.account_id AND change_log.change_id > 88700)
"""



# Groupviews are groups as seen from a spread.
# They are tailored for efficient dumping of all data related to a spread.


class GroupView(Builder):
    slots = [
        Attribute('name', str),
        Attribute('posix_gid', int),
        #Attribute('members_flat', [str]),
        #Attribute('members_tree', [str]),
        #Attribute('quarantenes', [str])
        ]

group_search="""
SELECT
group_info.group_id AS id
group_name.name AS name
posix_group.posix_gid AS posix_gid
FROM group_info
JOIN entity_spread group_spread
ON (group_spread.spread = 157 AND group_spread.entity_id = group_info.account_id)
JOIN entity_name group_name
ON (group_name.entity_id = group_info.group_id)
LEFT JOIN posix_group
ON (posix_group.group_id = group_info.group_id)
WHERE ((group_info.expire_date > now() OR group_info.expire_date IS NULL)
  AND (group_info.visibility = 331))
"""



class OUView(Builder):
    slots = [
        Attribute('name', str), # XXX
        Attribute('acronym', str),
        Attribute('short_name', str),
        Attribute('display_name', str),
        Attribute('sort_name', str),
        
        Attribute('adresses', [str, Struct(AdressView)]),
        Attribute('phones', [str, str]),
        
        Attribute('name_path', [str])
        ]

ou_search="""
SELECT
ou_info.ou_id AS id
ou_info.name AS name
ou_info.acronym AS acronym
ou_info.short_name AS short_name
ou_info.display_name AS display_name
ou_info.sort_name AS sort_name

-- stedkode
FROM ou_info
JOIN ou_structure
ON (ou_structure.ou_id = ou_info.ou_id AND ou_perspective = 418)
-- stedkode
LEFT JOIN stedkode
ON (stedkode.ou_id = ou_info.ou_id)
"""

# PersionView contains NIN, so access should be somewhat strict.


class PersonView(Builder):
    slots = [
        Attribute('export_id', str)
        Attribute('full_name', str),
        Attribute('first_name', str),
        Attribute('last_name', str),
        
        Attribute('birthdate', str),
        Attribute('nin', str)
        ]

person_search="""
SELECT
person_info.export_id AS export_id
person_info.birthdate AS birthdate
person_first_name.name AS first_name
person_last_name.name AS last_name
person_full_name.name AS full_name
person_nin.external_id AS nin
FROM person_info
JOIN entity_external_id person_nin
ON (person_nin.entity_id = person_info.person_id
  AND person_nin.id_type = 176)
LEFT JOIN person_name person_first_name
ON ((person_first_name.person_id = person_info.person_id)
  AND (person_first_name.source_system = 288)
  AND (person_first_name.name_variant = 219))
LEFT JOIN person_name person_last_name
ON ((person_last_name.person_id = person_info.person_id)
  AND (person_last_name.source_system = 288)
  AND (person_last_name.name_variant = 221))
LEFT JOIN person_name person_full_name
ON ((person_full_name.person_id = person_info.person_id)
  AND (person_full_name.source_system = 288)
  AND (person_full_name.name_variant = 220))
LEFT JOIN person_name person_personal_title
ON ((person_personal_title.person_id = person_info.person_id)
  AND (person_personal_title.source_system = 288)
  AND (person_personal_title.name_variant = 220))
LEFT JOIN person_name person_work_title
ON ((person_work_title.person_id = person_info.person_id)
  AND (person_work_title.source_system = 288)
  AND (person_work_title.name_variant = 220))
WHERE (not person_info.deceased_date)
"""

SELECT *
class View(DatabaseTransactionClass):
    def __init__(self, *args, **vargs):
        super(View, self).__init__(spread=None, *args, **vargs)
        
    # Allow the user to define spreads.
    # These must be set 'globally' because membership-type
    # attributes will need more than one spread.
    
    def set_account_spread(self, spread):
        self._account_spread=spread
    set_account_spread.signature=None
    set_account_spread.signature_args=[str]
    def set_group_spread(self, spread):
        self._group_spread=spread
    set_group_spread.signature=None
    set_group_spread.signature_args=[str]
    def set_perspective(self, perspective):
        self._perspective=perspective
    set_perspective.signature=None
    set_perspective.signature_args=[str]
    
    set_group_spread.signature=None
    set_group_spread.signature_args=[str]
    
    def get_accounts(self):
        db = self.get_database()
        rows=db.query(account_search)
        return [r.dict() for r in rows]
    get_accounts.signature = [Struct(AccountView)]
registry.register_class(View)



foo = """
account_spread=tr.get_spread('user@stud')
authentication_type=tr.get_authentication_type('MD5-crypt')
changes_since=88700

accounts = tr.get_account_searcher()

accounts_spread = tr.get_entity_spread_searcher()
accounts_spread.set_spread(account_spread)
accounts.add_join('', accounts_spread, 'entity')

disks = tr.get_disk_searcher()
home_directories = tr.get_home_directory_searcher()
home_directories.add_left_join('disk', disks, '')
accounts_home = tr.get_account_home_searcher()
accounts_home.set_spread(account_spread)
accounts_home.add_left_join('homedir', home_directories, '')
accounts.add_left_join('', accounts_home, 'account')

accounts_auth = tr.get_account_authentication_searcher()
accounts_auth.set_method(authentication_type)
accounts.add_left_join('', accounts_auth, 'account')

shells = tr.get_posix_shell_searcher()
accounts.add_left_join('shell', shells, '')

primary_groups = tr.get_group_searcher()
accounts.add_left_join('primary_group', primary_groups, '')

owner_groups = tr.get_group_searcher()
accounts.add_left_join('owner', owner_groups, '')

owner_persons = tr.get_person_searcher()
accounts.add_left_join('owner', owner_persons, '')

changes = tr.get_change_log_searcher()
changes.set_id_more_than(changes_since)
changes.add_join('subject_entity', accounts, 'id') # hack!
"""

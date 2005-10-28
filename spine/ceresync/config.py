import os
path = os.path.dirname(os.path.realpath(__file__))

# Corba
url = 'http://pointy.itea.ntnu.no/~erikgors/spine.ior'
username = 'bootstrap_account'
password = 'blapp'

# SSL
use_ssl = False
ssl_ca_file = 'CA.crt'
ssl_key_file = 'client.pem'
ssl_password = 'client'

# IDL
idl_path = os.path.join(path, 'tmp')
idl_file = os.path.join(path, 'SpineIDL.idl')
md5_file = os.path.join(path, 'SpineIDL.md5')
automatic = True

# sync
unix_type = 'bsd'

"""
# Connection details for ldap sync
# (preliminary example)
[ldap]
host: ldap-master.ntnu.no
base: dc=ntnu,dc=no
user_base: ou=users,%(base)s
group_base: ou=groups,%(base)s
people_base: ou=people,%(base)s
realm: ntnu.no
bind: cn=Manager,dc=ntnu,dc=no
password: password
tls: yes
# Supported hash-typer: sha-1,ssha,md5,smd5,crypt,cleartext
hash: md5
#Uri overrised host/tls-settings
uri: ldaps://ldap-master.ntnu.no
# Support for SASL/other authentication mechanisms will be added later.
# Only simple authentication is supported at this stage.
"""

class Constants(object):
    def __init__(self, tr):
        self.account_type = tr.get_entity_type('account')
        self.group_type = tr.get_entity_type('group')
        self._person_type = tr.get_entity_type('person')

        self.full_name = tr.get_name_type('FULL')
        self.first_name = tr.get_name_type('FIRST')
        self.last_name = tr.get_name_type('LAST')
        self.source_system = tr.get_source_system('Cached')
        self.password_type = tr.get_authentication_type('MD5-crypt')

        self.union_type = tr.get_group_member_operation_type('union')
        self.intersection_type = tr.get_group_member_operation_type('intersection')
        self.difference_type = tr.get_group_member_operation_type('difference')


class UnixConstants(Constants):
    def __init__(self, tr):
        super(UnixConstants, self).__init__(tr)

#        self.account_spread = tr.get_spread('user@stud')
        self.account_spread = tr.get_spread('user@chembio')
        self.group_spread = tr.get_spread('group@ntnu')
        self.person_spread = None #tr.get_spread('person@ntnu')

        self.group_format = '%(groupname)s:*:%(gid)s:%(members)s\n'

        if unix_type == 'shadow':
            self.passwd_files = {
                'passwd':'%(username)s:*:%(uid)s:%(gid)s:%(gecos)s:%(home)s:%(shell)s\n',
                'shadow':'%(username)s:%(password)s:%(last)s:%(may)s:%(must)s:%(warn)s:%(expire)s:%(disable)s:%(reserved)s\n'
            }
        elif unix_type == 'classic':
            self.passwd_files = {
                'passwd':'%(username)s:%(password)s:%(uid)s:%(gid)s:%(gecos)s:%(home)s:%(shell)s\n'
            }
        elif unix_type == 'bsd':
            self.passwd_files = {
                'master.passwd':'%(username)s:%(password)s:%(uid)s:%(gid)s:%(class)s:%(change)s:%(expire)s:%(gecos)s:%(home)s:%(shell)s\n'
            }

        # self.passwd_files['smbpasswd'] = '%(username)s:%(uid)s:%(lmhash)s:%(nthash)s:%(nthome)s:%(ntshell)s\n'
        # self.passwd_files['aliases'] = '%(address)s: %(mod)s %(to)s\n'

# arch-tag: 917620ca-47f8-11da-9bec-051db1a99478

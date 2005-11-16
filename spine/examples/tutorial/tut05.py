import Spine
session = Spine.login()
tr = session.new_transaction()

import SpineClient
search = SpineClient.Search(tr)

# contants
full_name = tr.get_name_type('FULL')
source = tr.get_source_system('Cached')

# create the search objects
accounts = search.account('account')
shells = search.posix_shell('shell')
names = search.person_name('full_name', name_variant=full_name, source_system=source)

# join them
accounts.add_join('shell', shells, '')
accounts.add_join('owner', names, 'person')

# order by name
accounts.order_by(names, 'name')
accounts.set_search_limit(20, 0)

for i in search.dump(accounts):
    uid = i['account'].posix_uid
    username = i['account'].name
    name = i['full_name'].name
    shell = i['shell'].shell
    print 'name: %-15s uname: %-10s uid: %-5s shell: %s ' % (name, username, uid, shell)

# arch-tag: e3bea7ca-56ae-11da-950e-eea089a2b0cf

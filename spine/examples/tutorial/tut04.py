import Spine
session = Spine.login()
tr = session.new_transaction()

# get the first 20 accounts whos name contains a 'b'

s = tr.get_account_searcher()
s.set_name_like('*b*')
s.set_search_limit(20, 0) # 0 is the offset!

# this time we dump

for account in s.dump():
    uid = account.posix_uid
    name = account.name
    shell = account.shell.get_shell()
    print 'name: %-10s uid: %-5s shell: %s ' % (name, uid, shell)

# notice we still have one call left: shell.get_shell()
# this can be solved by caching it, since there wont be that many shells.
#
# Example:
# shells = {}
#
# try:
#    shell = shells[account.shell]
# except:
#    shell = account.shell.get_shell()
#    shells[account.shell] = shell

# arch-tag: e331abd6-56ae-11da-9946-ce9ec9cd2c85

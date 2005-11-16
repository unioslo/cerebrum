import Spine
session = Spine.login()
tr = session.new_transaction()

# get the first 20 accounts whos name contains a 'b'

s = tr.get_account_searcher()
s.set_name_like('*b*')
s.set_search_limit(20, 0) # 0 is the offset!

# note that every method call requires _one_ corba call to the server
# meaning latency will most likly be a problem with big datasets

for account in s.search():
    uid = account.get_posix_uid()
    name = account.get_name()
    shell = account.get_shell().get_shell()
    print 'name: %-10s uid: %-5s shell: %s ' % (name, uid, shell)

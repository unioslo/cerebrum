import Spine
session = Spine.login()

# get a new transaction
tr = session.new_transaction()

# get objects by their primary keys
accountType = tr.get_entity_type('account')
print 'accountType: %s - %s' % (accountType.get_name(), accountType.get_description())

tcsh = tr.get_posix_shell('tcsh')
print 'path for tcsh:', tcsh.get_shell()

## everything can be fetched by doing tr.get_<cls>(<primary key>)
##
## Example:
# g = tr.get_group(89)
# a = tr.get_account(40)
# s = tr.get_spread('user@stud')
#
## or when the cls doesnt have any primary keys:
# cmd = tr.get_commands()               # tut02.py
# searcher = tr.get_group_searcher()    # tut03.py

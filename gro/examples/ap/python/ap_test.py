from Cerebrum.gro import ServerConnection

from omniORB.any import from_any, to_any

gro = ServerConnection.connect()
ap = gro.get_ap_handler('username', 'password')

for group in ap.getTypeByName('EntityType', 'group').getChildren():
    print 'Group:', from_any(group.get('name'))

print '---'

for account in ap.getTypeByName('EntityType', 'account').getChildren():
    print 'Account:', from_any(account.get('name'))

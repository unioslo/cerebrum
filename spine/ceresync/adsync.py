# Preliminary adsync for demo purpose

import sync
from win32com.client import GetObject
ou = GetObject("LDAP://ou=Brukere,dc=twin,dc=itea,dc=ntnu,dc=no")
print "Deleting existing users in AD"
for user in ou:
    ou.delete("user", user.name)

print "Adding accounts from Spine"
s = sync.Sync()
for account in s.get_accounts():
    user = ou.create("user", "cn=%s" % account.name)
    # NT4 compatible "short name"
    user.saMAccountName = account.name
    try:
        # Must save early to be able to set the rest of the attributes
        user.setInfo()
    except:
        print "Could not add user", account.name
    else:
        print "Added user", account.name
        user.accountDisabled = False
        # Should fetch this from Person 
        if account.gecos:
            user.fullName = account.gecos
        # FIXME: Must be cleartext password to work!
        # (Should really get pre-hashed passwords compatible with AD
        # from Spine) 
        user.setPassword(account.password)    
        user.setInfo()
        
group_ou = GetObject("LDAP://ou=Grupper,dc=twin,dc=itea,dc=ntnu,dc=no")
print "Deleting existing groups in AD"
for adgroup in group_ou:
    group_ou.delete("group", adgroup.name)

for group in s.get_groups():
    adgroup = group_ou.create("group", "cn=%s" % group.name)
    # NT4 compatible "short name"
    adgroup.sAMAccountName = group.name
    # A security group is type 0x80000000, or -2147483646
    adgroup.groupType = -2147483646
    try:
        adgroup.setInfo()
    except:
        print "Could not add group", group.name    
    else:
        print "Added group", group.name
    
    # Add members
    for member in group.membernames:
        members = adgroup.members()
        try:
            adgroup.add("LDAP://cn=%s,ou=Brukere,dc=twin,dc=itea,dc=ntnu,dc=no" % member)
        except:
            print "Could not add member",member 
        else:
            print "Added member",member 


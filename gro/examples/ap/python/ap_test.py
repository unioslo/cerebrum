#!/usr/bin/env python
import cerebrum_path

from Cerebrum.gro import ServerConnection

from omniORB.any import from_any, to_any

gro = ServerConnection.connect()
version = gro.get_version()
print "Connected to Gro version %s.%s"%(version.major, version.minor)
print

ap = gro.get_ap_handler('username', 'password')

groups = ap.getTypeByName('EntityType', 'group').getChildren()
print 'found', len(groups), 'groups'
print

for group in groups:
    group.lockForReading()
    print 'Group:', group.getString('name')
    for groupMember in from_any(group.get('members')):
        groupMember.lockForReading()
        member = from_any(groupMember.get('member'))
        operation = from_any(groupMember.get('operation'))
        member.lockForReading()
        print 'member leselås:', member.isReadLockedByMe()
        a = member.getString('name')
        b = operation.getString('name')
        print '\t- %s (%s)' % (a, b)
        print 'member leselås:', member.isReadLockedByMe()
        member.unlock()
        print 'member leselås:', member.isReadLockedByMe()
        groupMember.unlock()
        print 'member leselås:', member.isReadLockedByMe()
    group.unlock()

print '---'

persons = ap.getTypeByName('EntityType', 'person').getChildren()
print 'found', len(persons), 'persons'
print

for person in persons:
    person.lockForReading()
    print 'Person: [%s]' % person.getString('name')
    for account in from_any(person.get('accounts')):
        account.lockForReading()
        print '\t- ', account.getString('name')
        account.unlock()
    person.unlock()

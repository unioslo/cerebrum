#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

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

# arch-tag: 551b810d-a617-4ccf-88cb-99da108cf4f5

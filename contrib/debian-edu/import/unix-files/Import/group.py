#!/usr/bin/env python
"""
handles groups
"""

import os
import time
import sys
import string

import cerebrum_path
import cereconf

from Cerebrum import Group
from Cerebrum import Entity
from Cerebrum import Errors
from Cerebrum.modules import PosixGroup
from Cerebrum.Utils import Factory
from Cerebrum.Constants import _SpreadCode

from import_base import ImportBase

class GroupImport(ImportBase):

    def __init__(self, db, dryrun, spread):
        ImportBase.__init__(self, db, dryrun)

        self.spread             = spread

        self.account_member     = Factory.get('Account')(db)
        self.group              = Factory.get('Group')(db)
        self.group_member       = Factory.get('Group')(db)
        self.posixgroup         = PosixGroup.PosixGroup(db)

    def checkFileConsistency(self, infile):
        """
        see if there are several lines with identical group names
        or gids.
        """
        line_count = 0
        corrupt = False
        names = {}
        members = {}
        gids = {}

        stream = open(infile, 'r')
        for line in stream:

            line_count += 1

            fields = string.split(line.strip(), ":")
            if len(fields) != 4:
                print "Line %s corrupted: %s" %(line_count, line)
                corrupt = True
                continue

            name, passwd, gid, members_raw = fields

            if not name:
                print "No group name in line %s: %s" %(line_count, line)
                corrupt = True
                continue

            gid_corrupt = False
            if gids.has_key(gid):
                gid_corrupt = True
                corrupt = True
            gids[ gid ] = { line_count : fields }
            if gid_corrupt:
                print "Collision: %s" % ( gids[gid] )



            if members_raw:
                for member in string.split(members_raw.strip(),","):
                    members[ member ] = line_count

            name_corrupt = False
            if names.has_key(name):
                name_corrupt = True
                corrupt = True

            names[ name ] = { line_count : fields,
                                      "members"  : members,
                                      "gid"      : gid }
            if name_corrupt:
                print "Collision: %s" % ( names[name] )


        stream.close()

        if corrupt:
            sys.exit(0)

        return members, names


    def createGroups(self, groups):
        """
        based on a dictionary (groupname and gid) as input, the groups
        are created by calling process_group() for each one.
        """

        commit_count = 0
        commit_limit = 1000

        if self.spread:
            print self.spread
        for group_name, group_data in groups.iteritems():

            commit_count += 1
            print "Processing group: |%s|" % group_name
            
            gid = group_data['gid']
            
            self.processGroup(group_name, gid)

            if commit_count % commit_limit == 0:
                self.attemptCommit()



    def processGroup(self, name, gid ):
        """
        Check whether a group with name is registered in Cerebrum, if not
        create (as normal group). If necessary assign spread and membership.
        """
        try:
            self.posixgroup.clear()
            self.posixgroup.find_by_name(name)
            print("Group |%s| exists.", name)
        except Errors.NotFoundError:
            self.posixgroup.populate(self.default_creator_id,
                                     self.constants.group_visibility_all,
                                     name,
                                     None,
                                     time.strftime("%Y-%m-%d",
                                                   time.localtime()),
                                     None,
                                     int(gid))
            self.posixgroup.write_db()
            print("Created group |%s|.", name)

            try:
                self.group.clear()
                self.group.find_by_name(name)
                if self.spread:
                    if not group.has_spread(self.spread):
                        self.group.add_spread(self.spread)
                        print("Added spread |%s| to group |%s|.", self.spread, name)
                self.group.write_db()

            except Errors.NotFoundError:
                print("Group |%s| not found!", name)

    def addMembersToGroups(self, groups):
        """
        based on a dictionary (group_name, members) as input, the groups
        are created by calling process_members() for each one.
        """

        commit_count = 0
        commit_limit = 1000

        for group_name, group_data in groups.iteritems():

            commit_count += 1
            member_list = group_data['members']

            if member_list:
                print("Adding members to group |%s|" % (group_name) )
                self.processMembers( group_name, member_list )

            if commit_count % commit_limit == 0:
                self.attemptCommit()


    def processMembers(self, group_name, member_list):
        """
        Assign membership for groups and users.
        """

        self.group.clear()
        self.group.find_by_name(group_name)
        for member in member_list:
            try:
                self.account_member.clear()
                self.account_member.find_by_name(member)
                if not self.group.has_member(self.account_member.entity_id,
                                             self.constants.entity_account,
                                             self.constants.group_memberop_union):
                    self.group.add_member(account_member.entity_id,
                                          self.constants.entity_account,
                                          self.constants.group_memberop_union)
    #           else:
    #               print("User |%s| alredy a member of |%s|.", member, group_name)
                self.group.write_db()
                print "Added account |%s| to group |%s|." % (member, group_name)
            except Errors.NotFoundError:
                print "User |%s| not found!" % member
                if member == group_name:
                    print("Bang! Cannot continue adding members \
                           because a group cannot be its own member.")
                    continue
                try:
                    self.group_member.clear()
                    self.group_member.find_by_name(member)
                    if not self.group.has_member(self.group_member.entity_id,
                                                 self.constants.entity_group,
                                                 self.constants.group_memberop_union):
                        self.group.add_member(self.group_member.entity_id,
                                              self.constants.entity_group,
                                              self.constants.group_memberop_union)
                        self.group.write_db()
                        print "Added group |%s| to group |%s|." % (member, group_name)
                except Errors.NotFoundError:
                    print "Group |%s| not found!" % member
                print "Trying to assign membership to a non-existing entity |%s|" % ( member)
                continue




    def verifySpread(self, spread_selected ):
        spreads_list = constants.fetch_constants(_SpreadCode)
        if spreads_list:
            if spread in ( spreads_list ):
                self.spread = spread
                return True
            else:
                print spreads_list
        return False


# arch-tag: 33dfb670-a6a3-4b10-8663-fb4b2acfe87d

#!/usr/bin/env python
"""
handles the passwd file
"""

import sys
import string

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup

from import_base import ImportBase

class PasswdImport(ImportBase):

    def __init__(self, db, dryrun):
        ImportBase.__init__(self, db, dryrun)

        self.posixuser          = PosixUser.PosixUser(db)
        self.posixgroup         = PosixGroup.PosixGroup(db)

    def checkFileConsistency(self, infile):
        """
        see if there are several lines with identical group names
        or gids.
        """
        line_count = 0
        corrupt = False
        uids = {}
        names = {}

        stream = open(infile, 'r')
        for line in stream:
            line_count += 1

            fields = string.split(line.strip(), ":")
            if len(fields) != 7:
                print "Line %s corrupted: %s" % ( line_count, line )
                corrupt = True
                continue

            name, passwd, uid, gid, description, home_dir, shell = fields

            if not name:
                print "Line %s corrupted: %s" % ( line_count, line )
                corrupt = True
                continue


            name_corrupt = False
            if names.has_key(name):
                name_corrupt = True
                corrupt = True
                

            names[ name ] = { line_count    : fields,
                                        "uid"         : uid,
                                        "gid"         : gid,
                                        "home_dir"    : home_dir,
                                        "description" : description,
                                        "shell"       : shell }
            if name_corrupt:
                print "Collision: %s" % ( names[name] )


            uid_corrupt = False
            if uids.has_key(uid):
                uid_corrupt = True
                corrupt = True

            uids[ uid ] = { line_count : fields }
            if uid_corrupt:
                print "Collision: %s" % uids[uid]


        stream.close()

        if corrupt:
            sys.exit(0)

        return names



    def createUsers(self, users):
        """
        Scan all lines in INFILE and set password for user in Cerebrum.
        """

        commit_count = 0
        commit_limit = 1000

        # Iterate over all persons:
        for user_name, user_data in users.iteritems():
            commit_count += 1
            print "Processing user %s" % user_name

            user_id = self.processUser(user_name, user_data["uid"], user_data["gid"], "dummer user" )

            if commit_count % commit_limit == 0:
                self.attemptCommit()
            # fi
        # od
    # end createUser


    def processUser(self, user_name, uid, gid, gecos):
        """
        Set uid/gid for user.
        """

        print "types: uid: %s, gid: %s" %(type( uid) , type(gid))
        try:
            self.posixgroup.clear()
            self.posixgroup.find_by_gid(gid)
            print "Found group with gid: %s" % gid
        except Errors.NotFoundError:
            self.posixgroup.clear()
            # FixMe: what is this gid == 1000 thing?!?
            print "Group not found: %s continue with gid: %s" % ( gid, 1000 )
            self.posixgroup.find_by_gid(1000)
        # yrt


        try:
            self.posixuser.clear()
            self.posixuser.find_by_name(user_name)
            print "User %s exists in Cerebrum" % user_name
        except Errors.NotFoundError:
            # we may have an account-object lying around.
            owner = None
            try:
                self.account.clear()
                self.account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
                owner = self.account.entity_id
            except Errors.NotFoundError:
                # No account found owner = None still.
                pass
            
            self.posixuser.clear()
            print "entity_id %s" % self.posixgroup.entity_id
            self.posixuser.populate(uid,
                                    self.posixgroup.entity_id,
                                    None,
                                    self.constants.posix_shell_bash,
                                    name=user_name,
                                    creator_id = owner,
                                    owner_id = self.posixgroup.entity_id,
                                    owner_type = self.constants.entity_group,
                                    np_type = int(self.constants.account_system) )
            self.posixuser.write_db()
            self.db.commit()
            print "User %s promoted with uid: %s" % (user_name, uid)
        # yrt
          
        try:
            self.posixuser.clear()
            self.posixuser.find_by_uid(int(uid))
            if self.posixuser.account_name == user_name:
                print "User %s exists as PosixUser in Cerebrum" % user_name
            else:
                print "User %s exists with uid: %s. We have: %s." % \
                            (self.posixuser.account_name,
                             self.posixuser.posix_uid,
                             uid)
            return
        except Errors.NotFoundError:
            pass

        try:
            self.posixuser.clear()
            self.posixuser.find(self.account.entity_id)
            if int(self.posixuser.posix_uid) == int(uid):
                print "User %s exists as PosixUser in Cerebrum" % ( user_name)
            else:
                print "User %s exists with uid: %s. Will leave alone." % (user_name,
                            self.posixuser.posix_uid)
            return
        except Errors.NotFoundError:
            self.posixuser.clear()
            self.posixuser.populate(uid,
                                    self.posixgroup.entity_id,
                                    None,
                                    self.constants.posix_shell_tcsh,
                                    parent=self.account)
            self.posixuser.write_db()
            print "User %s promoted with uid: %s" % (user_name, uid)
        # yrt
    # end process_user

# arch-tag: 01c0009c-4028-418b-acf4-8c299da00fed

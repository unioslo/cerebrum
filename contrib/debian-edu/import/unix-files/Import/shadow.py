#!/usr/bin/env python
"""
this takes care of the password hashes in the shadow file
"""

import sys
import string

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory

from import_base import ImportBase

class ShadowImport(ImportBase):

    def __init__(self, db, dryrun):
        ImportBase.__init__(self, db, dryrun)


    def checkFileConsistency(self, infile):
        """
        see if there are several lines with identical group names
        or gids.
        """
        line_count = 0
        corrupt = False
        names = {}

        stream = open(infile, 'r')
        for line in stream:
            line_count += 1

            fields = string.split(line.strip(), ":")
            if len(fields) != 9:
                print "Line %s currupted: %s" % (line_count, line.strip())
                corrupt = True
                continue

            name, passwd, date1, date2, date3, date4, date5, date6, dontcare = fields

            if not name:
                print "Line %s corrupted: %s" % ( line_count, line )
                corrupt = True
                continue
            # fi

            name_corrupt = False
            if names.has_key(name):
                name_corrupt = True
                corrupt = True


            names[ name ] = { line_count : fields,
                                        "passwd" : passwd}
            if name_corrupt:
                print "Collision: %s" % ( names[name] )

        stream.close()

        if corrupt:
            sys.exit(0)

        return names



    def addUserPasswd( self, users ):
        """
        Scan all lines in INFILE and set password for user in Cerebrum.
        """

        commit_count = 0
        commit_limit = 1000

        # Iterate over all persons:
        for user_name, user_data in users.iteritems():
            commit_count += 1
            print "Processing user %s", user_name

            self.processUser(user_name, user_data["passwd"])

            if commit_count % commit_limit == 0:
                self.attemptCommit()
            # fi
        # od
    # end process_line


    def processUser(self, user_name, pwd):
        """
        Set passwd-crypt for user.
        """

        hash_type = self.classifyHash(pwd)
        if hash_type == "md5":
            auth_type = self.constants.auth_type_md5_crypt
        elif hash_type == "des":
            auth_type = self.constants.auth_type_crypt3_des
        else:
            self.logger.warn("Unknown hash type %s for user %s.", pwd, user_name)
            return

        try:
            self.account.clear()
            self.account.find_by_name(user_name)
            self.logger.debug3("User %s exists in Cerebrum", user_name)
            self.account.affect_auth_types(auth_type,)
            self.account.populate_authentication_type(auth_type, pwd)
            self.account.write_db()
            self.logger.debug3("User %s got passwd inserted: %s", user_name, pwd)
        except Errors.NotFoundError:
            self.logger.warn("User %s not found. Skipping.", user_name)
        # yrt
    # end process_user



    def classifyHash( self, passwd_hash ):

        if passwd_hash == "*":
            return None
        elif passwd_hash == "!":
            return None
        elif passwd_hash.__len__() == 10:
            return "des"
        elif passwd_hash.__getslice__(0,3) == "$1$":
            return "md5"
        else:
            print "unknown passwd hash type: %s" % passwd_hash

        return None

# arch-tag: 54c00d3b-9bec-4e2f-bc78-6d6c9c707f3f

# Copyright 2002 University of Oslo, Norway
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

"""The PosixUser module is used as a mixin-class for Account, and
contains additional parameters that are required for building password
maps used in Unix.  This includes UID, GID, Shell, gecos and home
directory.

The module in itself does not define which domain the entity_name
representing the username is stored in, as the module cannot know
which domain is currently being processed.  The routines generating
the password map, and building new users have this information.

If no posix username is defined for a given domain, the user is
considered to not be a member of the given domain.  That is, the
default username from Account is NOT used.

When the gecos field is not set, it is automatically extracted from
the name variant DEFAULT_GECOS_NAME (what about non-person accounts?).
SourceSystems are evaluated in the order defined by
POSIX_GECOS_SS_ORDER"""

import random
from Cerebrum import Person,Constants,Errors
from Cerebrum import cereconf

class PosixUser(object):
    "Mixin class for Account"

    def clear(self):
        super(PosixUser, self).clear()
        self.user_uid = None
        self.gid = None
        self.gecos = None
        self.home = None
        self.shell = None

    def __eq__(self, other):
        assert isinstance(other, PosixUser)

        if (self.user_uid != other.user_uid or
            self.gid   != other.gid or
            self.gecos != other.gecos or
            self.home  != other.home or
            self.shell != other.shell):
            return False

        return True

    def populate_posix_user(self, user_uid, gid, gecos, home, shell):
        self.user_uid = user_uid
        self.gid = gid
        self.gecos = gecos
        self.home = home
        self.shell = shell
        self.__write_db = True  # TODO: Tramper vi nå i Account's navnerom?

    def write_db(self, as_object=None):
        assert self.__write_db

        if as_object is None:
            self.execute("""
            INSERT INTO cerebrum.posix_user (account_id, user_uid, gid,
                gecos, home, shell)
            VALUES (:a_id, :u_id, :gid, :gecos, :home, :shell)""",
                         {'a_id' : self.account_id, 'u_id' : self.user_uid,
                          'gid' : self.gid, 'gecos' : self.gecos,
                          'home' : self.home, 'shell' : int(self.shell)})
        else:
            self.execute("""
            UPDATE cerebrum.posix_user SET account_id=:a_id, user_uid=:u_id, gid=:gid,
                gecos=:gecos, home=:home, shell=:shell)
            WHERE account_id=:orig_account_id""",
                         {'a_id' : self.account_id, 'u_id' : self.user_uid,
                          'gid' : self.gid, 'gecos' : self.gecos,
                          'home' : self.home, 'shell' : int(self.shell),
                          'orig_account_id' : as_object.account_id})
        self.__write_db = False

    def find_posixuser(self, account_id):
        self.find(account_id)

        (self.account_id, self.user_id, self.gid, self.gecos,
         self.home, self.shell) = self.query_1(
            """SELECT account_id, user_uid, gid, gecos, home, shell
               FROM cerebrum.posix_user
               WHERE account_id=:a_id""", {'a_id' : account_id})

    def get_all_posix_users(self):
        return self.query("SELECT account_id FROM posix_user")

    def get_free_uid(self):
        # TODO: This needs an implementation
        return random.randint(0,1000000)

    def get_gecos(self):
        assert self.owner_type == int(self.const.entity_person)
        p = Person.Person(self._db)
        p.find(self.owner_id)
        for ss in cereconf.POSIX_GECOS_SS_ORDER:
            try:
               ret = p.get_name(getattr(self.const, ss),
                                getattr(self.const, cereconf.DEFAULT_GECOS_NAME))
               return ret
            except Errors.NotFoundError:
                pass
        return "Unknown"  # Raise error?

    def suggest_unames(self, fname, lname):
        goal = 15
        potuname = ()
        complete_name = conv_name("%s %s" % (fname, lname), 1)

        # Remember just the first initials.
        m = re.search('^(.*)[ -]+(\S+)\s+(\S+)$', complete_name)
        firstinit = None
        if m != None:
            # at least three names
    	firstinit = m.group(0)
     	firstinit = re.sub(r'([- ])(\S)[^- ]*', r'\1\2', firstinit)
     	firstinit = re.sub(r'^(\S).*?($|[- ])', r'\1', firstinit)
     	firstinit = re.sub(r'[- ]', '', firstinit)

        # Remove hyphens.  People called "Geir-Ove Johnsen Hansen" generally
        # prefer "geirove" to just "geir".

        complete_name = re.sub(r'-', '', complete_name)

        m = re.search(r'(\S+)?(.*\s+(\S)\S*)?\s+(\S+)?$', complete_name)
        fname = m.group(1)[0:8]
        initial = m.group(3)
        lname = m.group(4)[0:8]

        if lname == '': fname = lname	# Sane behaviour if only one name.

        # For people with many names, we prefer to use all initials:
        # Example:  Geir-Ove Johnsen Hansen
        #           ffff fff i       llllll
        # Here, firstinit is "GO" and initial is "J".
        #
        # gohansen gojhanse gohanse gojhans ... gojh goh
        # ssllllll ssilllll sslllll ssillll     ssil ssl
        #
        # ("ss" means firstinit, "i" means initial, "l" means last name)

        if firstinit and len(firstinit) > 1:
    	i = len (firstinit)
    	llen = len (lname)
            if llen > 8 - i: llen = 8 - i 
            for j in range(llen, 0, -1):
                un = firstinit + lname[0:j]
                if self.validate_new_uname(un): potuname += (un, )

                if j > 1 and initial:
                    un = firstinit + initial + lname[0:j-1]
                    if self.validate_new_uname(un): potuname += (un, )
                    if len(potuname) >= goal: break
        

        # Now try different substrings from first and last name.
        #
        # geiroveh,
        # fffffffl
        # geirovh geirovha geirovjh,
        # ffffffl ffffffll ffffffil
        # geiroh geirojh geiroha geirojha geirohan,
        # fffffl fffffil fffffll fffffill ffffflll
        # geirh geirjh geirha geirjha geirhan geirjhan geirhans
        # ffffl ffffil ffffll ffffill fffflll ffffilll ffffllll
        # ...
        # gjh gh gjha gha gjhan ghan ... gjhansen ghansen
        # fil fl fill fll filll flll     fillllll fllllll

        flen = len(fname)
        if flen > 7: flen = 7

        for i in range(flen, 0, -1):
    	llim = len(lname)
            if llim > 8 - i: llim = 8 - i 
            for j in range(1, llim):
                if initial:
    		# Is there room for an initial?
                    if j == llim and i + llim < 8:
                        un = fname[0:i] + initial + lname[0:j]
                        if self.validate_new_uname(un): potuname += (un, )
    		# Is there room for an initial if we chop a letter off
    		# last name?
                    if j > 1:
                        un = fname[0:i] + initial + lname[0:j-1]
                        if self.validate_new_uname(un): potuname += (un, )
    	    un = fname[0:i] + lname[0:j]
                if self.validate_new_uname(un): potuname += (un, )
            if len(potuname) >= goal: break

        # Absolutely last ditch effort:  geirov1, geirov2 etc.

        i = 1
        if flen > 6: flen = 6

        while len(potuname) < goal and i < 100:
            un = "%s%d" % (fname[0:flen], i)
            i += 1
            if self.validate_new_uname(un): potuname += (un, )

        return ()

    def validate_new_uname(self, uname):
        print "V: %s" % uname
        return 1

    def make_passwd(self, uname):
        pot = '-+?=*()/&%#\'_!,;.:abcdefghijklmnopqrstuvwxyABCDEFGHIJKLMNOPQRSTUVWXY0123456789'
        while 1:
            r = ''
            while(len(r) < 8):
                r += pot[random.randint(0, len(pot)-1)]
            if self.goodenough(uname, r): break
        return r

    def goodenough(self, uname, passwd):
        return 1

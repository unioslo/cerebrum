# Copyright 2002, 2003 University of Oslo, Norway
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

Like the PosixGroup module, the user name is inherited from the
superclass, which here is Account.

When the gecos field is not set, it is automatically extracted from
the name variant DEFAULT_GECOS_NAME (what about non-person accounts?).
SourceSystems are evaluated in the order defined by
POSIX_GECOS_SOURCE_ORDER"""

import random
import re
import string

import cereconf
from Cerebrum import Person
from Cerebrum import Errors
from Cerebrum import Account
from Cerebrum import Constants
from Cerebrum import Disk
from Cerebrum.modules import PosixGroup


## Module spesific constant.  Belongs somewhere else
class _PosixShellCode(Constants._CerebrumCode):
    "Mappings stored in the posix_shell_code table"
    _lookup_table = '[:table schema=cerebrum name=posix_shell_code]'
    _lookup_desc_column = 'shell'
    pass

class Constants(Constants.Constants):
    posix_shell_bash = _PosixShellCode('bash', '/bin/bash')

class PosixUser(Account.Account):
    """Posix..."""

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('posix_uid', 'gid', 'gecos', 'shell')

    def clear(self):
        super(PosixUser, self).clear()
        for attr in PosixUser.__read_attr__:
            if hasattr(self, attr):
                delattr(self, attr)
        for attr in PosixUser.__write_attr__:
            setattr(self, attr, None)
        self.__updated = False

    def __eq__(self, other):
        assert isinstance(other, PosixUser)
        if (self.posix_uid == other.posix_uid and
            self.gid   == other.gid and
            self.gecos == other.gecos and
            int(self.shell) == int(other.shell)):
            return self.__super.__eq__(other)
        return False

    def populate(self, posix_uid, gid, gecos, shell, home=None, disk_id=None, name=None,
                 owner_type=None, owner_id=None, np_type=None,
                 creator_id=None, expire_date=None, parent=None):
        """Populate PosixUser instance's attributes without database access."""
        if parent is not None:
            self.__xerox__(parent)
        else:
            # super(PosixUser, self).populate(name, owner_type,
            # owner_id, np_type, creator_id, expire_date)
            Account.Account.populate(self, name, owner_type, owner_id,
                                     np_type, creator_id, expire_date,
                                     home=home, disk_id=disk_id)
        self.__in_db = False
        self.posix_uid = posix_uid
        self.gid = gid
        self.gecos = gecos
        self.shell = shell

    def write_db(self):
        """Write PosixUser instance to database."""
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        primary_group = PosixGroup.PosixGroup(self._db)
        primary_group.find(self.gid)
        if not primary_group.has_member(self.entity_id, self.entity_type,
                                        self.const.group_memberop_union):
            primary_group.add_member(self.entity_id,
                                     self.entity_type, self.const.group_memberop_union)
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=posix_user]
              (account_id, posix_uid, gid, gecos, shell)
            VALUES (:a_id, :u_id, :gid, :gecos, :shell)""",
                         {'a_id': self.entity_id,
                          'u_id': self.posix_uid,
                          'gid': self.gid,
                          'gecos': self.gecos,
                          'shell': int(self.shell)})
            self._db.log_change(self.entity_id, self.const.a_create,
                                None)  # TBD: const.pa_create
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=posix_user]
            SET account_id=:a_id, posix_uid=:u_id, gid=:gid, gecos=:gecos,
                shell=:shell
            WHERE account_id=:orig_account_id""",
                         {'a_id': self.entity_id,
                          'u_id': self.posix_uid,
                          'gid': self.gid,
                          'gecos': self.gecos,
                          'shell': int(self.shell),
                          'orig_account_id': as_object.account_id})
        del self.__in_db
        self.__in_db = True
        self.__updated = False
        return is_new

    def find(self, account_id):
        """Connect object to PosixUser with ``account_id`` in database."""
        self.__super.find(account_id)
        (self.account_id, self.posix_uid, self.gid, self.gecos,
         self.shell) = self.query_1("""
         SELECT account_id, posix_uid, gid, gecos, shell
         FROM [:table schema=cerebrum name=posix_user]
         WHERE account_id=:account_id""", locals())
        self.__in_db = True
        self.__updated = False

    def list_posix_users(self):
        """Return account_id of all PosixUsers in database"""
        return self.query("""
        SELECT account_id
        FROM [:table schema=cerebrum name=posix_user]""")

    def get_free_uid(self):
        """Returns the next free uid from ``posix_uid_seq``"""
        while 1:
            uid = self.nextval("posix_uid_seq")
            try:
                self.query_1("""
                SELECT posix_uid
                FROM [:table schema=cerebrum name=posix_user]
                WHERE posix_uid=:uid""", locals())
            except Errors.NotFoundError:
                return int(uid)

    def get_gecos(self):
        """Returns the gecos string of this object.  If self.gecos is
        not set, gecos is determined by searching for
        DEFAULT_GECOS_NAME in POSIX_GECOS_SOURCE_ORDER"""
        assert self.owner_type == int(self.const.entity_person)
        if self.gecos is not None:
            return self.gecos
        p = Person.Person(self._db)
        p.find(self.owner_id)
        for ss in cereconf.POSIX_GECOS_SOURCE_ORDER:
            try:
               ret = p.get_name(getattr(self.const, ss),
                                getattr(self.const,
                                        cereconf.DEFAULT_GECOS_NAME))
               return ret
            except Errors.NotFoundError:
                pass
        return "Unknown"  # Raise error?

    def get_home(self):
        """Returns the full path to the users homedirectory"""

        if self.home is not None:
            return self.home
        disk = Disk.Disk(self._db)
        try:
            disk.find(self.disk_id)
        except Errors.NotFoundError:
            return None
        return "%s/%s" % (disk.path, self.account_name)

    def suggest_unames(self, domain, fname, lname):
        """Returns a tuple with 15 (unused) username suggestions based
        on the persons first and last name"""
        goal = 15
        potuname = ()
        if re.search(r'^\s*$', fname) is not None or re.search(r'^\s*$', lname) is not None:
            raise ValueError,\
                  "Currently only fullname supported, got '%s', '%s'" % (fname, lname)
        complete_name = self._conv_name("%s %s" % (fname, lname), 1)

        # Remember just the first initials.
        m = re.search('^(.*)[ -]+(\S+)\s+(\S+)$', complete_name)
        firstinit = None
        if m is not None:
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

        if lname == '': lname = fname	# Sane behaviour if only one name.

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
                if self.validate_new_uname(domain, un): potuname += (un, )

                if j > 1 and initial:
                    un = firstinit + initial + lname[0:j-1]
                    if self.validate_new_uname(domain, un): potuname += (un, )
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
                        if self.validate_new_uname(domain, un):
                            potuname += (un, )
		# Is there room for an initial if we chop a letter off
		# last name?
                    if j > 1:
                        un = fname[0:i] + initial + lname[0:j-1]
                        if self.validate_new_uname(domain, un):
                            potuname += (un, )
                un = fname[0:i] + lname[0:j]
                if self.validate_new_uname(domain, un): potuname += (un, )
            if len(potuname) >= goal: break

        # Absolutely last ditch effort:  geirov1, geirov2 etc.

        i = 1
        if flen > 6: flen = 6

        while len(potuname) < goal and i < 100:
            un = "%s%d" % (fname[0:flen], i)
            i += 1
            if self.validate_new_uname(domain, un): potuname += (un, )

        return potuname

    def validate_new_uname(self, domain, uname):
        """Check that the requested username is legal and free"""
        try:
            # Delayed import to prevent python from barfing
            from Cerebrum import Account
            acc = Account.Account(self._db)
            acc.find_by_name(uname, domain=domain)
            return 0
        except Errors.NotFoundError:
            return 1

    def make_passwd(self, uname):
        """Generate a random password with 8 characters"""
        pot = ('-+?=*()/&%#\'_!,;.:'
               'abcdefghijklmnopqrstuvwxyABCDEFGHIJKLMNOPQRSTUVWXY0123456789')
        while 1:
            r = ''
            while(len(r) < 8):
                r += pot[random.randint(0, len(pot)-1)]
            try:
                if self.goodenough(uname, r): break
            except:
                pass  # Wasn't good enough
        return r

    def _conv_name(self, s, alt=0):
        """Convert string so that it only contains characters that are
        legal in a posix username"""
        xlate = {'Æ' : 'ae', 'æ' : 'ae', 'Å' : 'aa', 'å' : 'aa'}
        if alt:
            s = string.join(map(lambda x:xlate.get(x, x), s), '')

        tr = string.maketrans(
           'ÆØÅæø¿åÀÁÂÃÄÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝàáâãäçèéêëìíîïñòóôõöùúûüý{[}]|¦\\',
           'AOAaooaAAAAACEEEEIIIINOOOOOUUUUYaaaaaceeeeiiiinooooouuuuyaAaAooO')
        s = string.translate(s, tr)

        xlate = {}
        for y in range(0200, 0377): xlate[chr(y)] = 'x'
        xlate['Ð'] = 'Dh'
        xlate['ð'] = 'dh'
        xlate['Þ'] = 'Th'
        xlate['þ'] = 'th'
        xlate['ß'] = 'ss'
        s = string.join(map(lambda x:xlate.get(x, x), s), '').lower()
        s = re.sub(r'[^a-z0-9 ]', '', s)
        return s

    # TODO: These don't belong here
    msgs = {
        'not_null_char': ("Please don't use the null character in your"
                          " password."),
        'atleast8': "The password must be at least 8 characters long.",
        '8bit': ("Don't use 8-bit characters in your password (æøå),"
                 " it creates problems when using some keyboards."),
        'space': ("Don't use a space in the password.  It creates"
                  " problems for the POP3-protocol (Eudora and other"
                  " e-mail readers)."),
        'mix_needed8': ("A valid password must contain characters from at"
                        " least three of these four character groups:"
                        " Uppercase letters, lowercase letters, numbers and"
                        " special characters.  If the password only contains"
                        " one uppercase letter, this must not be at the start"
                        " of the password.  If the first 8 characters only"
                        " contains one number or special character, this must"
                        " not be in position 8."),
        'mix_needed': ("A valid password must contain characters from at"
                       " least three of these four character groups:"
                       " Uppercase letters, lowercase letters, numbers and"
                       " special characters."),

        'was_like_old': ("That was to close to an old password.  You must"
                         " select a new one."),
        'dict_hit': "Don't use words in a dictionary."
        }
    words = ("huge.sorted.txt",)
    dir = "/u2/dicts"

    def check_password_history(self, uname, passwd):
        """Check wether uname had this passwd earlier.  Raises a
        TODOError if this is true"""
        if 0:
            raise msgs['was_like_old']
        return 1

    def look(FH, key, dict, fold):
        """Quick port of look.pl (distributed with perl)"""
        blksize = os.statvfs(FH.name)[0]
        if blksize < 1 or blksize > 65536: blksize = 8192
        if dict: key = re.sub(r'[^\w\s]', '', key)
        if fold: key = key.lower()
        max = int(os.path.getsize(FH.name) / blksize)
        min = 0
        while (max - min > 1):
            mid = int((max + min) / 2)
            FH.seek(mid * blksize, 0)
            if mid: line = FH.readline()  # probably a partial line
            line = FH.readline()
            line.strip()
            if dict: line = re.sub(r'[^\w\s]', '', line)
            if fold: line = line.lower()
            if line < key:
                min = mid
            else:
                max = mid
        min = min * blksize
        FH.seek(min, 0)
        if min: FH.readline()
        while 1:
            line = FH.readline()
            if line is None: break
            line.strip()
            if dict: line = re.sub(r'[^\w\s]', '', line)
            if fold: line = line.lower()
            if line >= key: break
            min = FH.tell()
        FH.seek(min, 0)
        return min

    def goodenough(self, uname, passwd):
        """Perform a number of checks on a password to see if it is
        random enough.  This is done by checking the mix of
        upper/lowercase letters and special characers, as well as
        checking a database."""

        # TODO:  This needs more work.
        msgs = self.msgs
        passwd = passwd[0:8]

        if re.search(r'\0', passwd):
            raise msgs['not_null_char']

        if len(passwd) < 8:
            raise msgs['atleast8']


        if re.search(r'[\200-\376]', passwd):
            raise msgs['8bit']

        if re.search(r' ', passwd):
            raise msgs['space']

        # I'm not sure that the below is very smart.  If this rule
        # causes most users to include a digit in their password, one
        # has managed to reduce the password space by 26*2/10 provided
        # that a hacker performs a bruteforce attack

        good_try = variation = 0
        if re.search(r'[a-z]', passwd): variation += 1
        if re.search(r'[A-Z][^A-Z]{7}', passwd): good_try += 1
        if re.search(r'[A-Z]', passwd[1:8]): variation += 1
        if re.search(r'[^0-9]{7}[0-9]', passwd): good_try += 1

        if re.search(r'[0-9]', passwd[0:7]): variation += 1
        if re.search(r'[A-Za-z0-9]{7}[^A-Za-z0-9]', passwd): good_try += 1
        if re.search(r'[^A-Za-z0-9]', passwd[0:7]): variation += 1

        if variation < 3:
            if good_try:
                raise msgs['mix_needed8']
            else:
                raise msgs['mix_needed']

        # Too much like the old password?

        self.check_password_history(uname, passwd)   # Will raise on error

        # Is it in one of the dictionaries?

        if re.search(r'^[a-zA-Z]', passwd):
            chk = passwd.lower()
            # Truncate common suffixes before searching dict.

            even = ''
            chk = re.sub(r'\d+$', '', chk)
            chk = re.sub(r'\(', '', chk)

            chk = re.sub('s$', '', chk)
            chk = re.sub('ed$', '', chk)
            chk = re.sub('er$', '', chk)
            chk = re.sub('ly$', '', chk)
            chk = re.sub('ing$', '', chk)

            # We'll iterate over several dictionaries.

            for d in self.words:
                print "Check %s in %s" % (chk, d)
                f = file("%s/%s" % (self.dir, d))
                look(f, chk, 1, 1)

                # Do the lookup (dictionary order, case folded)
                while (1):
                    line = f.readline()
                    print "r: %s" % line
                    if line is None: break
                    line = line.lower()
                    if line[0:len(chk)] != chk: break
                    raise msgs['dict_hit']
        return 1

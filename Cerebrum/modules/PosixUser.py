# -*- coding: iso-8859-1 -*-
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

"""The PosixUser module implements a specialisation of the `Account'
core class.  The specialisation supports the additional parameters
that are needed for building password maps usable on Unix systems.
These parameters include UID, GID, shell, gecos and home directory.

The specialisation lives in the class PosixUser.PosixUser, which is a
subclass of the core class Account.  If Cerebrum has been configured
to use any mixin classes for Account objects, these classes will also
be among PosixUser.PosixUser superclasses.

Like the PosixGroup class, a user's name is inherited from the
superclass.

When the gecos field is not set, it is automatically extracted from
the name variant DEFAULT_GECOS_NAME (what about non-person accounts?).
SourceSystems are evaluated in the order defined by
POSIX_GECOS_SOURCE_ORDER.

Note that PosixUser.PosixUser itself is not a transparent Account
mixin class, as its populate() method requires other arguments than
the populate() method of Account.

"""

import random
import re
import string

import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum import Constants
from Cerebrum.modules import PosixGroup


## Module spesific constant.  Belongs somewhere else
class _PosixShellCode(Constants._CerebrumCode):
    "Mappings stored in the posix_shell_code table"
    _lookup_table = '[:table schema=cerebrum name=posix_shell_code]'
    _lookup_desc_column = 'shell'
    pass

class Constants(Constants.Constants):
    posix_shell_bash = _PosixShellCode('bash', '/bin/bash')
    posix_shell_csh = _PosixShellCode('csh', '/bin/csh')
    posix_shell_false = _PosixShellCode('false', '/bin/false')
    posix_shell_nologin = _PosixShellCode('nologin', '/bin/nologin')
    posix_shell_sh = _PosixShellCode('sh', '/bin/sh')
    posix_shell_tcsh = _PosixShellCode('tcsh', '/bin/tcsh')
    posix_shell_zsh = _PosixShellCode('zsh', '/bin/zsh')

Account_class = Factory.get("Account")
class PosixUser(Account_class):
    """'POSIX user' specialisation of core class `Account'.

    This class is not meant to be a transparent mixin class
    (i.e. included in the return value of Utils.Factory.get()) for
    `Account', but rather should be instantiated explicitly.

    """

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('posix_uid', 'gid_id', 'gecos', 'shell')

    def clear(self):
        super(PosixUser, self).clear()
        self.clear_class(PosixUser)
        self.__updated = []

    def __eq__(self, other):
        assert isinstance(other, PosixUser)
        if (self.posix_uid == other.posix_uid and
            self.gid_id   == other.gid_id and
            self.gecos == other.gecos and
            int(self.shell) == int(other.shell)):
            return self.__super.__eq__(other)
        return False

    def populate(self, posix_uid, gid_id, gecos, shell, home=None, disk_id=None, name=None,
                 owner_type=None, owner_id=None, np_type=None,
                 creator_id=None, expire_date=None, parent=None):
        """Populate PosixUser instance's attributes without database access."""
        if parent is not None:
            self.__xerox__(parent)
            self.home=home
            self.disk_id=disk_id
        else:
            super(PosixUser, self).populate(name, owner_type, owner_id,
                                            np_type, creator_id, expire_date,
                                            home=home, disk_id=disk_id)
        self.__in_db = False
        self.posix_uid = posix_uid
        self.gid_id = gid_id
        self.gecos = gecos
        self.shell = shell

    def write_db(self):
        """Write PosixUser instance to database."""
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        primary_group = PosixGroup.PosixGroup(self._db)
        primary_group.find(self.gid_id)
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
                          'gid': self.gid_id,
                          'gecos': self.gecos,
                          'shell': int(self.shell)})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=posix_user]
            SET posix_uid=:u_id, gid=:gid, gecos=:gecos,
                shell=:shell
            WHERE account_id=:a_id""",
                         {'a_id': self.entity_id,
                          'u_id': self.posix_uid,
                          'gid': self.gid_id,
                          'gecos': self.gecos,
                          'shell': int(self.shell)})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, account_id):
        """Connect object to PosixUser with ``account_id`` in database."""
        self.__super.find(account_id)
        (self.posix_uid, self.gid_id, self.gecos, self.shell) = self.query_1("""
         SELECT posix_uid, gid, gecos, shell
         FROM [:table schema=cerebrum name=posix_user]
         WHERE account_id=:account_id""", locals())
        self.__in_db = True
        self.__updated = []

    def list_posix_users(self):
        """Return account_id of all PosixUsers in database"""
        return self.query("""
        SELECT account_id
        FROM [:table schema=cerebrum name=posix_user]""")

    def list_extended_posix_users(self, 
				  auth_method=Constants.auth_type_crypt3_des, 
				  spread=None, include_quarantines=0):
        """Returns data required for building a password map.  It is
        not recommended to use this method.  If you do, be prepared to
        update your code when the API changes"""
        efrom = ewhere = ecols = ""
        if include_quarantines:
            efrom += """\
            LEFT JOIN [:table schema=cerebrum name=entity_quarantine] eq
              ON pu.account_id=eq.entity_id"""
            ecols += """, eq.quarantine_type, eq.start_date,
            eq.disable_until, eq.end_date"""
        if spread is not None:
            efrom += """  JOIN [:table schema=cerebrum name=entity_spread] es
            ON pu.account_id=es.entity_id AND es.spread=:spread"""
        # TBD: should we LEFT JOIN with account_authentication so that
        # users without passwords of the given type are returned?
        return self.query("""
        SELECT ai.account_id, posix_uid, shell, gecos, entity_name, ai.home,
          ai.disk_id, aa.auth_data, pg.posix_gid, pn.name %s
        FROM
          [:table schema=cerebrum name=posix_user] pu
          %s
          JOIN [:table schema=cerebrum name=account_info] ai
            ON ai.account_id=pu.account_id
          LEFT JOIN  [:table schema=cerebrum name=person_name] pn
            ON pn.person_id=ai.owner_id AND pn.source_system=:pn_ss AND
               pn.name_variant=:pn_nv
          JOIN [:table schema=cerebrum name=posix_group] pg
            ON pu.gid=pg.group_id
          LEFT JOIN [:table schema=cerebrum name=account_authentication] aa
            ON aa.account_id=pu.account_id AND aa.method=:auth_method
          JOIN [:table schema=cerebrum name=entity_name] en
            ON en.entity_id=pu.account_id AND en.value_domain=:vd
          ORDER BY ai.account_id""" % (ecols, efrom),
                          {'vd': int(self.const.account_namespace),
                           'auth_method': int(auth_method),
                           'spread': spread,
                           'pn_ss': int(self.const.system_cached),
                           'pn_nv': int(self.const.name_full)},
                          fetchall = False)

    def list_extended_posix_users_test(self, auth_method, spread=None,
                                  a_id=None,include_quarantines=0):
        """This is a test-version and is going to be rebuild. """
        efrom = ewhere = ecols = espread = ""
        if include_quarantines:
            efrom = """ LEFT JOIN [:table schema=cerebrum name=entity_quarantine] eq
                           ON pu.account_id=eq.entity_id"""
            ecols = ", eq.quarantine_type"
        if spread is not None:
            spread1 = int(spread[0])
            spread.remove(spread1)
            if spread:
                for entry in spread:
                    espread += " OR es.spread=%s" % (int(entry))
            efrom += """  JOIN [:table schema=cerebrum name=entity_spread] es
            ON pu.account_id=es.entity_id AND (es.spread=%s %s)""" % (spread1,espread)
        if a_id is None:
            ecols += ", shell"
        if a_id is not None:
            ewhere += """ AND pu.account_id=:a_id
            LEFT JOIN [:table schema=cerebrum name=posix_shell_code] psc
                ON pu.shell=psc.code
            LEFT JOIN [:table schema=cerebrum name=disk_info] di
                ON ai.disk_id=di.disk_id"""
            ecols += ", di.path, psc.shell"
        # TBD: should we LEFT JOIN with account_authentication so that
        # users without passwords of the given type are returned?
        return self.query("""
        SELECT ai.account_id, posix_uid, gecos, entity_name, ai.home,
          ai.disk_id, aa.auth_data, pg.posix_gid, pn.name %s
        FROM
          [:table schema=cerebrum name=posix_user] pu
          %s
          JOIN [:table schema=cerebrum name=account_info] ai
            ON ai.account_id=pu.account_id
          LEFT JOIN  [:table schema=cerebrum name=person_name] pn
            ON pn.person_id=ai.owner_id AND pn.source_system=:pn_ss AND
               pn.name_variant=:pn_nv
          JOIN [:table schema=cerebrum name=posix_group] pg
            ON pu.gid=pg.group_id
          LEFT JOIN [:table schema=cerebrum name=account_authentication] aa
            ON aa.account_id=pu.account_id AND aa.method=(SELECT MAX(method)
                FROM [:table schema=cerebrum name=account_authentication] aa2
                WHERE aa2.account_id=pu.account_id)
          JOIN [:table schema=cerebrum name=entity_name] en
            ON en.entity_id=pu.account_id AND en.value_domain=:vd
          %s ORDER BY ai.account_id
          """ % (ecols, efrom, ewhere),
                          {'vd': int(self.const.account_namespace),
                           #'auth_method': int(auth_method),
                           'spread': spread,
			   'pn_ss': int(self.const.system_cached),
                           'pn_nv': int(self.const.name_full),
                           'a_id': a_id})

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
        not set, gecos is a washed version of the persons cached fullname"""
        assert self.owner_type == int(self.const.entity_person)
        if self.gecos is not None:
            return self.gecos
        p = Factory.get("Person")(self._db)
        p.find(self.owner_id)
        try:
            ret = p.get_name(self.const.system_cached,
                             self.const.name_full)
            return self._conv_name(ret, as_gecos=1)
        except Errors.NotFoundError:
            pass
        return "Unknown"  # Raise error?

    def get_fullname(self):
        """The GECOS contains the full name the user wants to be
        associated with POSIX account.  If the official name of the
        person is needed, look up the Person object explicitly."""
        return self.get_gecos()

    def get_home(self):
        """Returns the full path to the users homedirectory"""

        if self.home is not None:
            return self.home
        disk = Factory.get("Disk")(self._db)
        try:
            disk.find(self.disk_id)
        except Errors.NotFoundError:
            return None
        return "%s/%s" % (disk.path, self.account_name)

    def list_shells(self):
        return self.query("""
        SELECT code, shell
        FROM [:table schema=cerebrum name=posix_shell_code]""")

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
            firstinit = m.group(1)
            firstinit = re.sub(r'([- ])(\S)[^- ]*', r'\1\2', firstinit)
            firstinit = re.sub(r'^(\S).*?($|[- ])', r'\1', firstinit)
            firstinit = re.sub(r'[- ]', '', firstinit)

        # Remove hyphens.  People called "Geir-Ove Johnsen Hansen" generally
        # prefer "geirove" to just "geir".

        complete_name = re.sub(r'-', '', complete_name)

        m = re.search(r'(\S+)?(.*\s+(\S)\S*)?\s+(\S+)?$', complete_name)
        # Avoid any None values returned by m.group(N).
        fname = (m.group(1) or "")[0:8]
        initial = (m.group(3) or "")
        lname = (m.group(4) or "")[0:8]

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
            acc = Account_class(self._db)
            acc.find_by_name(uname, domain=domain)
            return 0
        except Errors.NotFoundError:
            return 1

    def _conv_name(self, s, alt=0, as_gecos=0):
        """Convert string so that it only contains characters that are
        legal in a posix username.  If as_gecos=1, it may also be
        used for the gecos field"""

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
        s = string.join(map(lambda x:xlate.get(x, x), s), '')
        if as_gecos:
            s = re.sub(r'[^a-zA-Z0-9 ]', '', s)
            return s
        s = s.lower()
        s = re.sub(r'[^a-z0-9 ]', '', s)
        return s

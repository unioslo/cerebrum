# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003, 2004 University of Oslo, Norway
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

    PosixShell = _PosixShellCode

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

    def delete_posixuser(self):
        """Demotes this PosixUser to a normal Account."""
        if self.entity_id is None:
            raise Errors.NoEntityAssociationError, \
                  "Unable to determine which entity to delete."
        self._db.log_change(self.entity_id, self.const.posix_demote,
                            None, change_params={'uid': int(self.posix_uid),
                                                 'gid': int(self.gid_id)})
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=posix_user]
        WHERE account_id=:e_id""", {'e_id': self.entity_id})

    def populate(self, posix_uid, gid_id, gecos, shell, name=None,
                 owner_type=None, owner_id=None, np_type=None,
                 creator_id=None, expire_date=None, parent=None):
        """Populate PosixUser instance's attributes without database access."""
        if parent is not None:
            self.__xerox__(parent)
        else:
            super(PosixUser, self).populate(name, owner_type, owner_id,
                                            np_type, creator_id, expire_date)
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

    def find_by_uid(self, uid):
        account_id = self.query_1("""
        SELECT account_id
        FROM [:table schema=cerebrum name=posix_user]
        WHERE posix_uid=:uid""", locals())
        self.find(account_id)


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
            if isinstance(spread, (tuple, list)):
                spreads = spread
            else:
		spreads = []
		spreads.append(spread)
	    esprd = ' AND (' + ' OR '.join(['es.spread=%i' % x for x \
			in spreads]) + ')'
            asprd = ' AND (' + ' OR '.join(['ah.spread=%i' % x for x \
			in spreads]) + ')'
            ecols += ", ah.home, ah.disk_id"
            efrom += """
            JOIN [:table schema=cerebrum name=entity_spread] es
              ON pu.account_id=es.entity_id %s
            LEFT JOIN [:table schema=cerebrum name=account_home] ah
              ON es.entity_id=ah.account_id %s""" % (esprd, asprd)
        # TBD: should we LEFT JOIN with account_authentication so that
        # users without passwords of the given type are returned?
        return self.query("""
        SELECT ai.account_id, posix_uid, shell, gecos, entity_name, 
          aa.auth_data, pg.posix_gid, pn.name %s
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
        if self.gecos is not None:
            return self.gecos
        if self.owner_type == int(self.const.entity_group):
            return self.simplify_name(
                "%s user" % self.account_name, as_gecos=1)
        assert self.owner_type == int(self.const.entity_person)
        p = Factory.get("Person")(self._db)
        p.find(self.owner_id)
        try:
            ret = p.get_name(self.const.system_cached,
                             self.const.name_full)
            return self.simplify_name(ret, as_gecos=1)
        except Errors.NotFoundError:
            pass
        return "Unknown"  # Raise error?

    def get_fullname(self):
        """The GECOS contains the full name the user wants to be
        associated with POSIX account.  If the official name of the
        person is needed, look up the Person object explicitly."""
        if self.gecos is not None:
            return self.gecos
        return self.__super.get_fullname()

    def get_posix_home(self, spread):
        """Returns the full path to the users homedirectory"""
        tmp = self.__super.get_home(spread)
        if tmp['home'] is not None:
            return tmp['home']
        disk = Factory.get("Disk")(self._db)
        try:
            disk.find(tmp['disk_id'])
        except Errors.NotFoundError:
            return None
        return "%s/%s" % (disk.path, self.account_name)

    def list_shells(self):
        return self.query("""
        SELECT code, shell
        FROM [:table schema=cerebrum name=posix_shell_code]""")

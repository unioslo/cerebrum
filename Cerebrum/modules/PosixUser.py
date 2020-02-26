# -*- coding: utf-8 -*-
#
# Copyright 2002-2020 University of Oslo, Norway
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
"""
The PosixUser module implements a specialisation of the `Account' core class.

The specialisation supports the additional parameters
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
import cereconf

from Cerebrum.Utils import Factory, argument_to_sql
from Cerebrum.utils import transliterate
from Cerebrum import Errors
from Cerebrum.modules import PosixGroup

__version__ = "1.1"


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
        if (
                self.posix_uid == other.posix_uid and
                self.gid_id == other.gid_id and
                self.gecos == other.gecos and
                int(self.shell) == int(other.shell)):
            return self.__super.__eq__(other)
        return False

    def delete_posixuser(self):
        """Demotes this PosixUser to a normal Account."""
        if self.entity_id is None:
            raise Errors.NoEntityAssociationError(
                "Unable to determine which entity to delete.")
        if hasattr(super(PosixUser, self), 'delete_posixuser'):
            super(PosixUser, self).delete_posixuser()
        binds = {'account_id': self.entity_id}
        exists_stmt = """
          SELECT EXISTS (
            SELECT 1
            FROM [:table schema=cerebrum name=posix_user]
            WHERE account_id=:account_id
          )"""
        if not self.query_1(exists_stmt, binds):
            # False positive
            return
        delete_stmt = """
        DELETE FROM [:table schema=cerebrum name=posix_user]
        WHERE account_id=:account_id"""
        self.execute(delete_stmt, binds)
        self._db.log_change(self.entity_id, self.clconst.posix_demote,
                            None, change_params={'uid': int(self.posix_uid),
                                                 'gid': int(self.gid_id),
                                                 'shell': int(self.shell),
                                                 'gecos': self.gecos})

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

    def map_user_spreads_to_pg(self, group=None):
        """Syncs self's spreads to default group's spreads.
        This uses mappings implemented in subclasses. """

    def write_db(self):
        """Write PosixUser instance to database."""
        self.__super.write_db()
        if not self.__updated:
            return None
        is_new = not self.__in_db
        primary_group = PosixGroup.PosixGroup(self._db)
        primary_group.find(self.gid_id)
        # TBD: should Group contain a utility function to add a member
        # if it's not a member already?  There are many occurences of
        # code like this, and but none of them implement all the
        # robustness below.
        binds = {'a_id': self.entity_id,
                 'u_id': self.posix_uid,
                 'gid': self.gid_id,
                 'gecos': self.gecos,
                 'shell': int(self.shell)}
        if not primary_group.has_member(self.entity_id):
            primary_group.add_member(self.entity_id)
        if is_new:
            insert_stmt = """
            INSERT INTO [:table schema=cerebrum name=posix_user]
              (account_id, posix_uid, gid, gecos, shell)
            VALUES (:a_id, :u_id, :gid, :gecos, :shell)
            """
            self.execute(insert_stmt, binds)
            self._db.log_change(self.entity_id,
                                self.clconst.posix_promote,
                                None,
                                change_params={'uid': int(self.posix_uid),
                                               'gid': int(self.gid_id),
                                               'shell': int(self.shell),
                                               'gecos': self.gecos})
        else:
            exists_stmt = """
              SELECT EXISTS (
                SELECT 1
                FROM [:table schema=cerebrum name=posix_user]
                WHERE (gecos is NULL AND :gecos is NULL OR gecos=:gecos) AND
                       posix_uid=:u_id AND
                       gid=:gid AND
                       shell=:shell AND
                       account_id=:a_id
              )
            """
            if not self.query_1(exists_stmt, binds):
                # True positive
                update_stmt = """
                UPDATE [:table schema=cerebrum name=posix_user]
                SET posix_uid=:u_id, gid=:gid, gecos=:gecos, shell=:shell
                WHERE account_id=:a_id
                """
                self.execute(update_stmt, binds)
                self._db.log_change(self.entity_id,
                                    self.clconst.posix_promote,
                                    None,
                                    change_params={'uid': int(self.posix_uid),
                                                   'gid': int(self.gid_id),
                                                   'shell': int(self.shell),
                                                   'gecos': self.gecos})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, account_id):
        """Connect object to PosixUser with ``account_id`` in database."""
        self.__super.find(account_id)
        (self.posix_uid, self.gid_id, self.gecos, self.shell) = self.query_1(
            """
         SELECT posix_uid, gid, gecos, shell
         FROM [:table schema=cerebrum name=posix_user]
         WHERE account_id=:account_id""", locals())
        self.__in_db = True
        self.__updated = []

    def find_by_uid(self, uid):
        """Find posix user by posix_uid"""
        account_id = self.query_1("""
        SELECT account_id
        FROM [:table schema=cerebrum name=posix_user]
        WHERE posix_uid=:uid""", locals())
        self.find(account_id)

    def list_posix_users(self, spread=None, filter_expired=False):
        """Return account_id of all PosixUsers in database. Filters
        are spread which can be a single spread or a tuple or list of
        spreads. filter_expired also removes expired accounts."""
        efrom, ewhere, bind = "", "", {}
        if spread is not None:
            efrom += """JOIN [:table schema=cerebrum name=entity_spread] es
              ON pu.account_id=es.entity_id AND
              """ + argument_to_sql(spread, 'es.spread', bind, int)
        if filter_expired:
            ewhere = "WHERE ai.expire_date IS NULL OR ai.expire_date > [:now]"
            efrom += """JOIN [:table schema=cerebrum name=account_info] ai
                      ON ai.account_id=pu.account_id"""
        return self.query("""
        SELECT pu.account_id, pu.posix_uid, pu.gid, pu.gecos, pu.shell
        FROM [:table schema=cerebrum name=posix_user] pu %s %s
        """ % (efrom, ewhere), bind)

    def get_free_uid(self):
        """Returns the next free uid from ``posix_uid_seq``"""
        while 1:
            # We pick an UID
            uid = self.nextval("posix_uid_seq")
            # We check if the UID is in any of the reserved ranges.
            # If it is, we'll skip past the range (call setval), and
            # pick a new UID that is past the reserved range.
            for x in sorted(cereconf.UID_RESERVED_RANGE):
                # TODO: Move this check to some unit-testing stuff sometime
                if x[1] < x[0]:
                    raise Errors.ProgrammingError(
                        'Wrong order in cereconf.UID_RESERVED_RANGE')
                if x[0] <= uid <= x[1]:
                    self._db.setval('posix_uid_seq', x[1])
                    uid = self.nextval("posix_uid_seq")
            # If the UID is not in use, we return it, else, we try over.
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
        default_gecos_name = getattr(self.const, cereconf.DEFAULT_GECOS_NAME)
        if self.gecos is not None:
            return self.gecos
        if self.owner_type == self.const.entity_group:
            return transliterate.for_gecos("{} user".format(self.account_name))
        assert self.owner_type == self.const.entity_person
        p = Factory.get("Person")(self._db)
        p.find(self.owner_id)
        try:
            ret = p.get_name(self.const.system_cached,
                             default_gecos_name)
            return transliterate.for_gecos(ret)
        except Errors.NotFoundError:
            pass
        return "Unknown"  # Raise error?

    def get_fullname(self):
        """The GECOS contains the full name the user wants to be
        associated with POSIX account. This method's return value will
        also be used to generate an email-address if the posix account
        is not owned by an actual person."""
        if self.owner_type != int(self.const.entity_person):
            if self.gecos is not None:
                return self.gecos
            raise Errors.NotFoundError('Name (GECOS) not set for'
                                       'non-personal PosixUser.')
        return self.__super.get_fullname()

    def get_posix_home(self, spread):
        """Returns the full path to the users homedirectory"""
        tmp = self.__super.get_home(spread)
        try:
            return self.resolve_homedir(disk_id=tmp['disk_id'],
                                        home=tmp['home'],
                                        spread=spread)
        except Exception:
            return None

    def list_shells(self):
        """Returns all shells"""
        return self.query(
            """
              SELECT code, shell
              FROM [:table schema=cerebrum name=posix_shell_code]
            """)

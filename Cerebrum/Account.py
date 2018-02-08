# -*- coding: utf-8 -*-
# Copyright 2002-2018 University of Oslo, Norway
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

"""The Account module stores information about an account of
arbitrary type.  Extentions like PosixUser are used for additional
parameters that may be required by the requested backend.

Usernames are stored in the table entity_name.  The domain that the
default username is stored in is yet to be determined.
"""

import crypt
import string
import re
import mx
import hashlib
import base64

import six

from Cerebrum import Utils, Disk
from Cerebrum.Entity import (EntityName,
                             EntityQuarantine,
                             EntityContactInfo,
                             EntityExternalId,
                             EntitySpread)
from Cerebrum import Errors
from Cerebrum.Utils import (NotSet,
                            argument_to_sql,
                            prepare_string)
from Cerebrum.modules.pwcheck.checker import (check_password,
                                              PasswordNotGoodEnough)
from Cerebrum.modules.password_generator.generator import PasswordGenerator

import cereconf


class AccountType(object):

    """The AccountType class does not use populate logic as the only
    data stored represent a PK in the database"""

    def get_account_types(self, all_persons_types=False, owner_id=None,
                          filter_expired=True):
        """Return dbrows of account_types for the given account.

        @type all_persons_types: bool
        @param all_persons_types: If True, returns all the account_types by the
            owner's (person)'s accounts, and not just this account's types.

        @type owner_id: int
        @param owner_id: If set, returns all the account_types for all accounts
            that has the given owner_id as their owner.

        @type filter_expired: bool
        @param filter_expired: If expired accounts should be ignored. Note that
            this does not check if the affiliation or account_type is expired!

        @rtype: db-rows
        @return: Each row is an account type, containing the person_id, ou_id,
            affiliation, account_id and priority.

        """
        if all_persons_types or owner_id is not None:
            col = 'person_id'
            if owner_id is not None:
                val = owner_id
            else:
                val = self.owner_id
        else:
            col = 'account_id'
            val = self.entity_id
        tables = ["[:table schema=cerebrum name=account_type] at"]
        where = ["at.%s = :%s" % (col, col)]
        if filter_expired:
            tables.append("[:table schema=cerebrum name=account_info] ai")
            where.append("""(ai.account_id = at.account_id AND
                             (ai.expire_date IS NULL OR
                              ai.expire_date > [:now]))""")
        return self.query("""
        SELECT person_id, ou_id, affiliation, at.account_id, priority
        FROM """ + ", ".join(tables) + """
        WHERE """ + " AND ".join(where) + """
        ORDER BY priority""",
                          {col: val})

    def set_account_type(self, ou_id, affiliation, priority=None):
        """Insert or update the given account type.

        :type priority: int
        :param priority:
            Priorities the account type if the account has more than one. The
            highest priority, i.e. lowest value, is the primary affiliation.
            Defaults to 5 higher than highest value amongst existing account
            type priorities.

        :rtype: tuple

        """
        all_pris = {}
        orig_pri = None
        max_pri = 0
        for row in self.get_account_types(all_persons_types=True,
                                          filter_expired=False):
            all_pris[int(row['priority'])] = row
            if(ou_id == row['ou_id'] and affiliation == row['affiliation'] and
               self.entity_id == row['account_id']):
                orig_pri = row['priority']
            if row['priority'] > max_pri:
                max_pri = row['priority']
        if priority is None:
            priority = max_pri + 5
        if orig_pri is None:
            if priority in all_pris:
                self._set_account_type_priority(
                    all_pris, priority, priority + 1)
            cols = {'person_id': int(self.owner_id),
                    'ou_id': int(ou_id),
                    'affiliation': int(affiliation),
                    'account_id': int(self.entity_id),
                    'priority': priority}
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=account_type] (%(tcols)s)
            VALUES (%(binds)s)""" % {'tcols': ", ".join(cols.keys()),
                                     'binds': ", ".join(
                                         [":%s" % t for t in cols.keys()])},
                         cols)
            self._db.log_change(self.entity_id, self.const.account_type_add,
                                None, change_params={
                                    'ou_id': int(ou_id),
                                    'affiliation': int(affiliation),
                                    'priority': int(priority)})
            return 'add', priority
        else:
            if orig_pri != priority:
                self._set_account_type_priority(all_pris, orig_pri, priority)
                return 'mod', priority

    def _set_account_type_priority(self, all_pris, orig_pri, new_pri):
        """Recursively insert the new priority, increasing parent
        priority with one if there is a conflict"""
        if new_pri in all_pris:
            self._set_account_type_priority(all_pris, new_pri, new_pri + 1)
        orig_pri = int(orig_pri)
        cols = {'person_id': all_pris[orig_pri]['person_id'],
                'ou_id': all_pris[orig_pri]['ou_id'],
                'affiliation': all_pris[orig_pri]['affiliation'],
                'account_id': all_pris[orig_pri]['account_id'],
                'priority': new_pri}
        self.execute("""
        UPDATE [:table schema=cerebrum name=account_type]
        SET priority=:priority
        WHERE %s""" % " AND ".join(["%s=:%s" % (x, x)
                                    for x in cols.keys() if x != "priority"]),
                     cols)
        self._db.log_change(self.entity_id, self.const.account_type_mod,
                            None, change_params={'new_pri': int(new_pri),
                                                 'old_pri': int(orig_pri)})

    def del_account_type(self, ou_id, affiliation):
        cols = {'person_id': self.owner_id,
                'ou_id': ou_id,
                'affiliation': int(affiliation),
                'account_id': self.entity_id}
        where = ' AND '.join(('{} = :{}'.format(x, x) for x in cols.keys()))
        priority = self.query_1(
            """SELECT priority FROM [:table schema=cerebrum name=account_type]
            WHERE {}""".format(where), cols)
        self.execute("""
                     DELETE FROM [:table schema=cerebrum name=account_type]
                     WHERE {}""".format(where), cols)
        self._db.log_change(self.entity_id, self.const.account_type_del,
                            None,
                            change_params={'ou_id': int(ou_id),
                                           'affiliation': int(affiliation),
                                           'priority': int(priority)})

    def delete_ac_types(self):
        """Delete all the AccountTypes for the account."""

        self.execute("""
        DELETE FROM [:table schema=cerebrum name=account_type]
        WHERE account_id=:a_id""", {'a_id': self.entity_id})

    def list_accounts_by_type(self, ou_id=None, affiliation=None,
                              status=None, filter_expired=True,
                              account_id=None, person_id=None,
                              primary_only=False, person_spread=None,
                              account_spread=None, fetchall=True,
                              exclude_account_id=None):
        """Return information about the matching accounts.

        TODO: Add rest of the parameters.

        @type filter_expired: bool
        @param filter_expired:
            If accounts marked as expired should be filtered away from the
            output.

        @type primary_only: bool
        @param primary_only:
            If only the primary account for each person should be returned.

        @param exclude_account_id: Filter out account(s) with given account_id.
        @type exclude_account_id: Integer, list, tuple, set


        @rtype: db-rows
        @return: Each row is an account type, containing the person_id, ou_id,
            affiliation, account_id and priority.
        """
        binds = {'ou_id': ou_id,
                 'status': status,
                 'account_id': account_id}
        join = extra = ""
        if affiliation is not None:
            if isinstance(affiliation, (list, tuple)):
                affiliation = "IN (%s)" % \
                    ", ".join(map(str, map(int, affiliation)))
            else:
                affiliation = "= %d" % int(affiliation)
            extra += " AND at.affiliation %s" % affiliation
        if status is not None:
            extra += " AND pas.status=:status"
        if ou_id is not None:
            extra += " AND at.ou_id=:ou_id"
        if person_id is not None:
            extra += " AND " + argument_to_sql(person_id,
                                               "at.person_id",
                                               binds,
                                               int)
        if filter_expired:
            extra += " AND (ai.expire_date IS NULL OR ai.expire_date > [:now])"
        if account_id:
            extra += " AND ai.account_id=:account_id"
        if person_spread is not None and account_spread is not None:
            raise Errors.CerebrumError('Illegal to use both person and '
                                       'account spread in query')
        if person_spread is not None:
            if isinstance(person_spread, (list, tuple)):
                person_spread = "IN (%s)" % \
                                ", ".join(map(str, map(int, person_spread)))
            else:
                person_spread = "= %d" % int(person_spread)
            join += " JOIN [:table schema=cerebrum name=entity_spread] es" \
                    " ON es.entity_id = at.person_id" \
                    " AND es.spread " + person_spread
        if account_spread is not None:
            if isinstance(account_spread, (list, tuple)):
                account_spread = "IN (%s)" % \
                    ", ".join(map(str, map(int, account_spread)))
            else:
                account_spread = "= %d" % int(account_spread)
            join += " JOIN [:table schema=cerebrum name=entity_spread] es" \
                    " ON es.entity_id = at.account_id" \
                    " AND es.spread " + account_spread
        if exclude_account_id is not None and len(exclude_account_id):
            extra += " AND NOT " + argument_to_sql(exclude_account_id,
                                                   "ai.account_id",
                                                   binds,
                                                   int)
        rows = self.query("""
        SELECT DISTINCT at.person_id, at.ou_id, at.affiliation, at.account_id,
                        at.priority
        FROM [:table schema=cerebrum name=person_affiliation_source] pas,
             [:table schema=cerebrum name=account_info] ai,
             [:table schema=cerebrum name=account_type] at
             %s
        WHERE at.person_id=pas.person_id AND
              at.ou_id=pas.ou_id AND
              at.affiliation=pas.affiliation AND
              ai.account_id=at.account_id
              %s
        ORDER BY at.person_id, at.priority""" % (join, extra),
                          binds, fetchall=fetchall)
        if primary_only:
            ret = []
            prev = None
            for row in rows:
                person_id = int(row['person_id'])
                if person_id != prev:
                    ret.append(row)
                    prev = person_id
            return ret
        return rows
    # end list_accounts_by_type


class AccountHome(object):
    """AccountHome keeps track of where the user's home directory is.

    A different home dir for each defined home spread may exist.
    A home is identified either by a disk_id, or by the string
    represented by home.

    Whenever a users account_home or homedir is modified, we changelog
    the new path of the users homedirectory as a string.  For
    convenience, we also log this path when the entry is deleted.

    """

    def resolve_homedir(self, account_name=None, disk_id=None,
                        disk_path=None, home=None, spread=None):
        """Constructs and returns the users homedir-path.  Subclasses
        should override with spread spesific behaviour."""
        path_separator = '/'
        if not account_name:
            account_name = self.account_name
        if disk_id:
            disk = Disk.Disk(self._db)
            disk.find(disk_id)
            disk_path = disk.path
        if home:
            if not disk_path:
                return home
            return disk_path + path_separator + home
        if not disk_path:
            return None
        return disk_path + path_separator + account_name

    def delete(self):
        """Removes all homedirs for an account"""

        # TODO: This should either call its super class, which should rather be
        # Account or Entity, or it should be renamed to delete_home, to avoid
        # breaking the mro.

        self.execute("""
        DELETE FROM [:table schema=cerebrum name=account_home]
        WHERE account_id=:a_id""", {'a_id': self.entity_id})
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=homedir]
        WHERE account_id=:a_id""", {'a_id': self.entity_id})

    def clear_home(self, spread):
        """Clears home for a spread. Removes homedir if no other
        home uses it."""
        try:
            ah = self.get_home(spread)
        except Errors.NotFoundError:
            return
        old_home = self.resolve_homedir(disk_id=ah['disk_id'],
                                        home=ah['home'],
                                        spread=spread)
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=account_home]
        WHERE account_id=:account_id AND spread=:spread""", {
            'account_id': self.entity_id,
            'spread': int(spread)})
        self._db.log_change(
            self.entity_id, self.const.account_home_removed, None,
            change_params={'spread': int(spread),
                           'home': old_home,
                           'homedir_id': ah['homedir_id']})

        # If no other account_home.homedir_id points to this
        # homedir.homedir_id, remove it to avoid dangling unused data
        count = self.query_1("""SELECT count(*) AS count
        FROM [:table schema=cerebrum name=account_home]
        WHERE homedir_id=:homedir_id""", {'homedir_id': ah['homedir_id']})
        if count < 1:
            self._clear_homedir(ah['homedir_id'])

    def set_homedir(self, current_id=NotSet, home=NotSet, disk_id=NotSet,
                    status=NotSet):
        """Adds or updates an entry in the homedir table.

        If current_id=NotSet, insert a new entry.  Otherwise update
        the values != NotSet for the given homedir_id=current_id.

        Returns the homedir_id for the affetcted row.

        Whenever current_id=NotSet, the caller should follow-up by
        calling set_home on the returned homedir_id to assert that we
        do not end up with homedir rows without corresponding
        account_home entries.
        """
        binds = {'account_id': self.entity_id,
                 'home': home,
                 'disk_id': disk_id,
                 'status': status
                 }

        if current_id is NotSet:
            # Allocate new id
            binds['homedir_id'] = long(self.nextval('homedir_id_seq'))

            # Specify None as default value for create
            for key, value in binds.items():
                if value is NotSet:
                    binds[key] = None

            sql = """
            INSERT INTO [:table schema=cerebrum name=homedir]
              (%s)
            VALUES (%s)""" % (
                ", ".join(binds.keys()),
                ", ".join([":%s" % t for t in binds]))

            change_type = self.const.homedir_add
        else:
            # Leave previous value alone if update
            for key, value in binds.items():
                if value is NotSet:
                    del binds[key]

            binds['homedir_id'] = current_id

            sql = """
            UPDATE [:table schema=cerebrum name=homedir]
              SET %s
            WHERE homedir_id=:homedir_id""" % (
                ", ".join(["%s=:%s" % (t, t) for t in binds]))

            change_type = self.const.homedir_update

        self.execute(sql, binds)

        if binds.get('disk_id') or binds.get('home'):
            tmp = {'home': self.resolve_homedir(disk_id=binds.get('disk_id'),
                                                home=binds.get('home'))}
        else:
            tmp = {}
        tmp['homedir_id'] = binds['homedir_id']
        if 'status' in binds:
            tmp['status'] = binds['status']
        self._db.log_change(self.entity_id,
                            change_type,
                            None,
                            change_params=tmp)

        return binds['homedir_id']

    def _clear_homedir(self, homedir_id):
        """Called from clear_home. Removes actual homedir."""
        tmp = self.get_homedir(homedir_id)
        tmp = self.resolve_homedir(disk_id=tmp['disk_id'],
                                   home=tmp['home'])
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=homedir]
        WHERE homedir_id=:homedir_id""",
                     {'homedir_id': homedir_id})
        self._db.log_change(
            self.entity_id, self.const.homedir_remove, None,
            change_params={'homedir_id': homedir_id,
                           'home': tmp})

    def get_homedir(self, homedir_id):
        return self.query_1("""
        SELECT homedir_id, account_id, home, disk_id, status
        FROM [:table schema=cerebrum name=homedir]
        WHERE homedir_id=:homedir_id""",
                            {'homedir_id': homedir_id})

    def get_homepath(self, spread):
        tmp = self.get_home(spread)
        return self.resolve_homedir(disk_id=tmp["disk_id"], home=tmp["home"])

    def set_home(self, spread, homedir_id):
        """Set the accounts account_home to point to the given
        homedir_id for the given spread.
        """
        binds = {'account_id': self.entity_id,
                 'spread': int(spread),
                 'homedir_id': homedir_id
                 }
        tmp = self.get_homedir(homedir_id)
        tmp = self.resolve_homedir(disk_id=tmp['disk_id'],
                                   home=tmp['home'],
                                   spread=spread)
        try:
            old = self.get_home(spread)
            self.execute("""
            UPDATE [:table schema=cerebrum name=account_home]
            SET homedir_id=:homedir_id
            WHERE account_id=:account_id AND spread=:spread""", binds)
            self._db.log_change(
                self.entity_id, self.const.account_home_updated, None,
                change_params={
                    'spread': int(spread),
                    'home': tmp,
                    'homedir_id': homedir_id
                })
            # Remove old homedir entry if no account_home points to it anymore
            if int(old['homedir_id']) not in [
                    int(row['homedir_id']) for row in self.get_homes()]:
                self._clear_homedir(old['homedir_id'])
        except Errors.NotFoundError:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=account_home]
              (account_id, spread, homedir_id)
            VALUES
              (:account_id, :spread, :homedir_id)""", binds)
            self._db.log_change(
                self.entity_id, self.const.account_home_added, None,
                change_params={'spread': int(spread),
                               'home': tmp,
                               'homedir_id': homedir_id})

    def get_home(self, spread):
        return self.query_1("""
        SELECT ah.homedir_id, disk_id, home, status, spread
        FROM [:table schema=cerebrum name=account_home] ah,
             [:table schema=cerebrum name=homedir] ahd
        WHERE ah.homedir_id=ahd.homedir_id AND ah.account_id=:account_id
          AND spread=:spread""",
                            {'account_id': self.entity_id,
                             'spread': int(spread)})

    def get_homes(self):
        """Return a list of all the given account's registered homes."""
        return self.query("""
        SELECT ah.homedir_id, ahd.disk_id, ahd.home, ahd.status, ah.spread
        FROM [:table schema=cerebrum name=account_home] ah,
             [:table schema=cerebrum name=homedir] ahd
        WHERE ah.homedir_id=ahd.homedir_id AND ah.account_id=:account_id""",
                          {'account_id': self.entity_id})


Entity_class = Utils.Factory.get("Entity")


class Account(AccountType, AccountHome, EntityName, EntityQuarantine,
              EntityExternalId, EntityContactInfo, EntitySpread, Entity_class):

    __read_attr__ = ('__in_db', '__plaintext_password', 'created_at'
                     # TODO: Get rid of these.
                     )
    __write_attr__ = ('account_name', 'owner_type', 'owner_id',
                      'np_type', 'creator_id', 'expire_date', 'description',
                      '_auth_info', '_acc_affect_auth_types')

    def deactivate(self):
        """Deactivate is commonly thought of as removal of spreads and setting
        of expire_date < today. in addition a deactivated account should not
        have any group memberships."""
        group = Utils.Factory.get("Group")(self._db)
        self.expire_date = mx.DateTime.now()
        for s in self.get_spread():
            self.delete_spread(int(s['spread']))
        for row in group.search(member_id=self.entity_id):
            group.clear()
            group.find(row['group_id'])
            group.remove_member(self.entity_id)
            group.write_db()
        self.write_db()

    def delete(self):
        """Really, really remove the account, homedir, account types and the
        password history."""

        if self.__in_db:
            # Homedir needs to be removed first
            AccountHome.delete(self)

            # Remove the account types
            self.delete_ac_types()

            self.execute("""
            DELETE FROM [:table schema=cerebrum name=account_authentication]
            WHERE account_id=:a_id""", {'a_id': self.entity_id})
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=account_info]
            WHERE account_id=:a_id""", {'a_id': self.entity_id})

            # Remove name of account from the account namespace.
            self.delete_entity_name(self.const.account_namespace)
            self._db.log_change(
                self.entity_id,
                self.const.account_destroy,
                None)

        # AccountHome is the class "breaking" the MRO-delete() "chain".
        # self.__super.delete()
        # ... call will stop right at AccountHome. I.e. EntityName, etc won't
        # have their respective delete()s called with __super/super() in this
        # particular case.
        super(AccountHome, self).delete()

    def terminate(self):
        """Deletes the account and all data related to it. The different
        instances should subclass it and feed it with what they need to delete
        before the account could be fully removed from the database.

        Note that also change_log entries are removed, so you don't get any log
        entry when executing this method. However, change_log events where the
        given entity_id is in L{change_by} is not removed, as the API does not
        know what to do with such events, as they are for other entities. If
        such events occur, a db constraint will complain.

        It works by first removing related data, before it runs L{delete},
        which deletes the account itself.
        """
        if not self.entity_id:
            raise RuntimeError('No account set')
        e_id = self.entity_id

        # Deactivating the account first. This is not an optimal solution, but
        # it solves race conditions like for update_email_addresses, which
        # recreates EmailTarget and e-mail addresses for the account until it
        # is deactivated. Makes termination a bit slower.
        self.deactivate()

        # Have to write latest change_log entries, to be able to remove them:
        self._db.write_log()
        for row in self._db.get_log_events(any_entity=e_id):
            # TODO: any_entity or just subject_entity?
            self._db.remove_log_event(int(row['change_id']))

        # Add this if we put it in Entity as well:
        # self.__super.terminate()
        self.delete()
        self.clear()

        # Remove the log changes from the deletion too:
        self._db.write_log()
        for row in self._db.get_log_events(any_entity=e_id):
            # TODO: any_entity or just subject_entity?
            self._db.remove_log_event(int(row['change_id']))

    def clear(self):
        super(Account, self).clear()
        self.clear_class(Account)
        self.__updated = []

        # TODO: The following attributes are currently not in
        #       Account.__slots__, which means they will stop working
        #       once all Entity classes have been ported to use the
        #       mark_update metaclass.
        self._auth_info = {}
        self._acc_affect_auth_types = []

    def __eq__(self, other):
        assert isinstance(other, Account)

        if (self.account_name != other.account_name or
                int(self.owner_type) != int(other.owner_type) or
                self.owner_id != other.owner_id or
                self.np_type != other.np_type or
                self.creator_id != other.creator_id or
                self.expire_date != other.expire_date or
                self.description != other.description):
            return False
        return True

    def populate(self, name, owner_type, owner_id, np_type, creator_id,
                 expire_date, description=None, parent=None):
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity_class.populate(self, self.const.entity_account)
        # If __in_db is present, it must be True; calling populate on
        # an object where __in_db is present and False is very likely
        # a programming error.
        #
        # If __in_db in not present, we'll set it to False.
        try:
            if not self.__in_db:
                raise RuntimeError("populate() called multiple times.")
        except AttributeError:
            self.__in_db = False
        self.owner_type = int(owner_type)
        self.owner_id = owner_id
        self.np_type = np_type
        self.creator_id = creator_id
        self.expire_date = expire_date
        self.description = description
        self.account_name = name

    def affect_auth_types(self, *authtypes):
        self._acc_affect_auth_types = list(authtypes)

    def populate_authentication_type(self, type, value):
        self._auth_info[int(type)] = value
        self.__updated.append('password')

    def wants_auth_type(self, method):
        """Returns True if this authentication type should be stored
        for this account."""
        return True

    def set_password(self, plaintext):
        """Updates all account_authentication entries with an
        encrypted version of the plaintext password.  The methods to
        be used are determined by AUTH_CRYPT_METHODS.

        Note: affect_auth_types is automatically extended to contain
        these methods.
        """
        notimplemented = []
        for method_name in cereconf.AUTH_CRYPT_METHODS:
            method = self.const.Authentication(method_name)
            if method not in self._acc_affect_auth_types:
                self._acc_affect_auth_types.append(method)
            if not self.wants_auth_type(method):
                # affect_auth_types is set above, so existing entries
                # which are unwanted for this account will be removed.
                #
                # HOWEVER, removing a method from AUTH_CRYPT_METHODS
                # will not cause deletion of the associated auth_data
                # upon next password change, the auth_data for that
                # method will stick around as stale data.
                #
                # So to stop storing a method, you'll either have to
                # clean it out from the database manually, or you'll
                # have to decline it in wants_auth_data until it's all
                # gone.
                continue
            try:
                enc = self.encrypt_password(method, plaintext)
            except Errors.NotImplementedAuthTypeError as e:
                notimplemented.append(str(e))
            else:
                self.populate_authentication_type(method, enc)
        try:
            # Allow multiple writes, even though this is a __read_attr__
            del self.__plaintext_password
        except AttributeError:
            pass
        finally:
            self.__plaintext_password = plaintext

        if notimplemented:
            raise Errors.NotImplementedAuthTypeError("\n".join(notimplemented))

    def encrypt_password(self, method, plaintext, salt=None, binary=False):
        """Returns the plaintext hashed according to the specified
        method.  A mixin for a new method should not call super for
        the method it handles.

        This should be fixed for python3

        :type method: Constants.AccountAuthentication
        :param method: Some auth_type_x constant

        :type plaintext: String (str or unicode)
        :param plaintext: The plaintext to hash

        :type salt: String
        :param salt: Salt for hashing

        :type binary: bool
        :param binary: Treat plaintext as binary data
        """
        # TODO: Temporary (and ugly) fix for CRB-162
        # Strings should be represented as unicode objects everywhere
        # in the entire system
        unicode_plaintext = plaintext
        if not isinstance(unicode_plaintext, unicode):
            try:
                unicode_plaintext = unicode(plaintext, 'UTF-8')
            except:
                unicode_plaintext = unicode(plaintext, 'ISO-8859-1')
        if binary:
            utf8_plaintext = plaintext  # a small lie
        else:
            utf8_plaintext = unicode_plaintext.encode('UTF-8')
        if method in (self.const.auth_type_md5_crypt,
                      self.const.auth_type_crypt3_des,
                      self.const.auth_type_sha256_crypt,
                      self.const.auth_type_sha512_crypt,
                      self.const.auth_type_ssha):
            if salt is None:
                saltchars = string.ascii_letters + string.digits + "./"
                if method == self.const.auth_type_md5_crypt:
                    salt = "$1$" + Utils.random_string(8, saltchars)
                elif method == self.const.auth_type_sha256_crypt:
                    salt = "$5$" + Utils.random_string(16, saltchars)
                elif method == self.const.auth_type_sha512_crypt:
                    salt = "$6$" + Utils.random_string(16, saltchars)
                else:
                    salt = Utils.random_string(2, saltchars)
            if method == self.const.auth_type_ssha:
                # encodestring annoyingly adds a '\n' at the end of
                # the string, and OpenLDAP won't accept that.
                # b64encode does not, but it requires Python 2.4
                return base64.encodestring(
                    hashlib.sha1(
                        utf8_plaintext + salt).digest() + salt).strip()
            return crypt.crypt(plaintext if method ==
                               self.const.auth_type_crypt3_des
                               else utf8_plaintext, salt)
        elif method == self.const.auth_type_md4_nt:
            # Do the import locally to avoid adding a dependency for
            # those who don't want to support this method.
            import smbpasswd
            return smbpasswd.nthash(unicode_plaintext)
        elif method == self.const.auth_type_plaintext:
            return plaintext
        elif method == self.const.auth_type_md5_unsalt:
            return hashlib.md5(utf8_plaintext).hexdigest()
        elif method == self.const.auth_type_ha1_md5:
            s = ":".join(
                [self.account_name,
                 cereconf.AUTH_HA1_REALM,
                 utf8_plaintext])
            return hashlib.md5(s).hexdigest()
        raise Errors.NotImplementedAuthTypeError(
            "Unknown method %r" % method)

    def decrypt_password(self, method, cryptstring):
        """Returns the decrypted plaintext according to the specified
        method.  If decryption is impossible, NotImplementedError is
        raised.  A mixin for a new method should not call super for
        the method it handles.
        """
        if method in (self.const.auth_type_md5_crypt,
                      self.const.auth_type_ha1_md5,
                      self.const.auth_type_crypt3_des,
                      self.const.auth_type_sha256_crypt,
                      self.const.auth_type_sha512_crypt,
                      self.const.auth_type_md4_nt):
            raise NotImplementedError("Can't decrypt %s" % method)
        elif method == self.const.auth_type_plaintext:
            return cryptstring
        raise ValueError("Unknown method %r" % method)

    def verify_password(self, method, plaintext, cryptstring):
        """Returns True if the plaintext matches the cryptstring,
        False if it doesn't.  If the method doesn't support
        verification, NotImplemented is returned.
        """
        if method in (self.const.auth_type_md5_crypt,
                      self.const.auth_type_ha1_md5,
                      self.const.auth_type_crypt3_des,
                      self.const.auth_type_md4_nt,
                      self.const.auth_type_ssha,
                      self.const.auth_type_sha256_crypt,
                      self.const.auth_type_sha512_crypt,
                      self.const.auth_type_plaintext):
            salt = cryptstring
            if method == self.const.auth_type_ssha:
                salt = base64.decodestring(cryptstring)[20:]
            return (self.encrypt_password(method, plaintext, salt=salt) ==
                    cryptstring or self.encrypt_password(method, plaintext,
                                                         salt=salt,
                                                         binary=True) ==
                    cryptstring)
        raise ValueError("Unknown method %r" % method)

    def verify_auth(self, plaintext):
        """Try to verify all authentication data stored for an
        account.  Authentication data from methods not listed in
        AUTH_CRYPT_METHODS are ignored.  Returns True if all stored
        authentication methods which are able to confirm a plaintext,
        do.  If no methods are able to confirm, or one method reports
        a mismatch, return False.

        """
        success = []
        failed = []
        for m in cereconf.AUTH_CRYPT_METHODS:
            method = self.const.Authentication(m)
            try:
                auth_data = self.get_account_authentication(method)
            except Errors.NotFoundError:
                # No credentials set by the given method for the given account.
                # This is normally okay, as we could create new methods without
                # requiring all users to set new passwords. However, at least
                # one auth method has to succeed.
                continue
            status = self.verify_password(method, plaintext, auth_data)
            if status is NotImplemented:
                continue
            if status is True:
                success.append(m)
            else:
                failed.append(m)
        # If you both pass and fail various crypt methods, it is normally an
        # error:
        if success and failed:
            if hasattr(self, 'logger'):
                self.logger.warn('Cred mismatch for %s, success: %s, fail: %s',
                                 self.account_name, success, failed)

        if not success and not failed:
            if hasattr(self, 'logger'):
                self.logger.warn('Nothing to authenticate agaist for %s',
                                 self.account_name)
            return False

        return success and not failed

    def illegal_name(self, name):
        """Return a string with error message if username is illegal"""
        return False

    def write_db(self):
        self.__super.write_db()
        if not self.__updated:
            return
        if 'account_name' in self.__updated:
            tmp = self.illegal_name(self.account_name)
            if tmp:
                raise self._db.IntegrityError, "Illegal username: %s" % tmp

        is_new = not self.__in_db
        # make dict of changes to send to changelog
        newvalues = {}
        for key in self.__updated:
            # "password" is not handled by mark_update, so getattr
            # won't work.  _auth_info and _acc_affect_auth_types
            # should not be logged.
            # TBD: Why are they in __updated?
            if key == 'np_type':
                newvalues[key] = int(getattr(self, key))
            elif key not in ['_auth_info',
                             '_acc_affect_auth_types',
                             'password']:
                newvalues[key] = getattr(self, key)

        # mark_update will not change the value if the new value is
        # __eq__ to the old.  in other words, it's impossible to
        # convert it from _CerebrumCode-instance to an integer.
        if self.np_type is None:
            np_type = None
        else:
            np_type = int(self.np_type)
        if is_new:
            cols = [('entity_type', ':e_type'),
                    ('account_id', ':acc_id'),
                    ('owner_type', ':o_type'),
                    ('owner_id', ':o_id'),
                    ('np_type', ':np_type'),
                    ('creator_id', ':c_id')]
            # Columns that have default values through DDL.
            if self.expire_date is not None:
                cols.append(('expire_date', ':exp_date'))
            if self.description is not None:
                cols.append(('description', ':desc'))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=account_info] (%(tcols)s)
            VALUES (%(binds)s)""" % {'tcols': ", ".join([x[0] for x in cols]),
                                     'binds': ", ".join([x[1] for x in cols])},
                         {'e_type': int(self.const.entity_account),
                          'acc_id': self.entity_id,
                          'o_type': int(self.owner_type),
                          'c_id': self.creator_id,
                          'o_id': self.owner_id,
                          'np_type': np_type,
                          'exp_date': self.expire_date,
                          'desc': self.description})
            self._db.log_change(self.entity_id, self.const.account_create,
                                None, change_params=newvalues)
            self.add_entity_name(
                self.const.account_namespace,
                self.account_name)
        else:
            cols = [('owner_type', ':o_type'),
                    ('owner_id', ':o_id'),
                    ('np_type', ':np_type'),
                    ('creator_id', ':c_id'),
                    ('description', ':desc'),
                    ('expire_date', ':exp_date')]
            self.execute("""
            UPDATE [:table schema=cerebrum name=account_info]
            SET %(defs)s
            WHERE account_id=:acc_id""" % {'defs': ", ".join(
                ["%s=%s" % x for x in cols])},
                {'o_type': int(self.owner_type),
                 'c_id': self.creator_id,
                 'o_id': self.owner_id,
                 'np_type': np_type,
                 'exp_date': self.expire_date,
                 'desc': self.description,
                 'acc_id': self.entity_id})
            self._db.log_change(self.entity_id, self.const.account_mod,
                                None, change_params=newvalues)
            if 'account_name' in self.__updated:
                self.update_entity_name(self.const.account_namespace,
                                        self.account_name)
        # We store the plaintext password in the changelog so that
        # other systems that need it may get it.  The changelog
        # handler should remove the plaintext password using some
        # criteria.
        try:
            password_str = self.__plaintext_password
            del password_str
        except AttributeError:
            # TODO: this is meant to catch that self.__plaintext_password is
            # unset, trying to use hasattr() instead will surprise you
            pass
        else:
            # self.__plaintext_password is set.  Put the value in the
            # changelog if the configuration tells us to.
            change_params = None
            if cereconf.PASSWORD_PLAINTEXT_IN_CHANGE_LOG:
                change_params = {'password': self.__plaintext_password}
            self._db.log_change(self.entity_id,
                                self.const.account_password,
                                None,
                                change_params=change_params)
        # Store the authentication data.
        for k in self._acc_affect_auth_types:
            k = int(k)
            what = 'insert'
            if self.__in_db:
                try:
                    dta = self.get_account_authentication(k)
                    if dta != self._auth_info.get(k, None):
                        what = 'update'
                    else:
                        what = 'nothing'
                except Errors.NotFoundError:
                    # insert
                    pass
            if self._auth_info.get(k, None) is not None:
                if what == 'insert':
                    self.execute("""
                    INSERT INTO
                      [:table schema=cerebrum name=account_authentication]
                      (account_id, method, auth_data)
                    VALUES (:acc_id, :method, :auth_data)""",
                                 {'acc_id': self.entity_id, 'method': k,
                                  'auth_data': self._auth_info[k]})
                elif what == 'update':
                    self.execute("""
                    UPDATE [:table schema=cerebrum name=account_authentication]
                    SET auth_data=:auth_data
                    WHERE account_id=:acc_id AND method=:method""",
                                 {'acc_id': self.entity_id, 'method': k,
                                  'auth_data': self._auth_info[k]})
            elif self.__in_db and what == 'update':
                self.execute("""
                DELETE FROM [:table schema=cerebrum name=account_authentication]
                WHERE account_id=:acc_id AND method=:method""",
                             {'acc_id': self.entity_id, 'method': k})

        try:
            del self.__plaintext_password
        except AttributeError:
            pass

        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def new(self, name, owner_type, owner_id, np_type, creator_id,
            expire_date, description=None):
        self.populate(name, owner_type, owner_id, np_type, creator_id,
                      expire_date, description=description)
        self.write_db()
        self.find(self.entity_id)

    def find(self, account_id):
        self.__super.find(account_id)

        (self.owner_type, self.owner_id,
         self.np_type, self.creator_id,
         self.expire_date, self.description) = self.query_1("""
        SELECT owner_type, owner_id, np_type,
               creator_id, expire_date, description
        FROM [:table schema=cerebrum name=account_info]
        WHERE account_id=:a_id""", {'a_id': account_id})
        self.account_name = self.get_name(self.const.account_namespace)
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def find_by_name(self, name, domain=None):
        if domain is None:
            domain = int(self.const.account_namespace)
        EntityName.find_by_name(self, name, domain)

    def get_account_authentication_methods(self):
        """Return a list of the authentication methods the account has."""
        binds = {'a_id': self.entity_id}

        return self.query("""
        SELECT method
        FROM [:table schema=cerebrum name=account_authentication]
        WHERE account_id=:a_id""", binds)

    def get_account_authentication(self, method):
        """Return the authentication data for the given method.  Raise
        an exception if missing."""

        return self.query_1("""
        SELECT auth_data
        FROM [:table schema=cerebrum name=account_authentication]
        WHERE account_id=:a_id AND method=:method""",
                            {'a_id': self.entity_id,
                             'method': int(method)})

    def get_account_expired(self):
        """Return expire_date if account expire date is overdue, else False"""
        try:
            return self.query_1("""
            SELECT expire_date
            FROM [:table schema=cerebrum name=account_info]
            WHERE expire_date < [:now] AND account_id=:a_id""",
                                {'a_id': self.entity_id})
        except Errors.NotFoundError:
            return False

    # TODO: is_reserved and list_reserved_users belong in an extended
    # version of Account
    def is_reserved(self):
        """We define a reserved account as an account with no
        expire_date and no spreads"""
        if (not self.is_expired()) and (not self.get_spread()):
            return True
        return False

    def is_deleted(self):
        """We define a deleted account as an account with
        expire_date < now() and no spreads"""
        if self.is_expired() and not self.get_spread():
            return True
        return False

    def is_expired(self):
        now = mx.DateTime.now()
        if self.expire_date is None or self.expire_date >= now:
            return False
        return True

    def list(self, filter_expired=True, fetchall=True):
        """Returns all accounts"""
        where = []
        if filter_expired:
            where.append("(ai.expire_date IS NULL OR ai.expire_date > [:now])")
        if where:
            where = "WHERE %s" % " AND ".join(where)
        else:
            where = ""
        return self.query("""
        SELECT *
        FROM [:table schema=cerebrum name=account_info] ai %s""" % where,
                          fetchall=fetchall)

    def list_account_home(self, home_spread=None, account_spread=None,
                          disk_id=None, host_id=None, include_nohome=False,
                          filter_expired=True):
        """List users with homedirectory, optionally filtering the
        results on home/account spread, disk/host.

        If include_nohome=True, users without home will be included in
        the search-result when filtering on home_spread.  Should not
        be used in combination with filter on disk/host."""

        where = ['en.entity_id=ai.account_id']
        where.append('ei.entity_id=ai.account_id')
        tables = ['[:table schema=cerebrum name=entity_name] en']
        tables.append(', [:table schema=cerebrum name=entity_info] ei')
        if account_spread is not None:
            # Add this table before account_info for correct left-join syntax
            where.append("es.entity_id=ai.account_id")
            where.append("es.spread=:account_spread")
            tables.append(", [:table schema=cerebrum name=entity_spread] es")

        tables.append(', [:table schema=cerebrum name=account_info] ai')
        if filter_expired:
            where.append("(ai.expire_date IS NULL OR ai.expire_date > [:now])")

        # We must perform a left-join or inner-join depending on
        # whether or not include_nohome is True.
        if include_nohome:
            if home_spread is not None:
                tables.append(
                    ('LEFT JOIN [:table schema=cerebrum name=account_home] ah '
                     ' ON ah.account_id=ai.account_id AND '
                     'ah.spread=:home_spread'))
            else:
                tables.append(
                    'LEFT JOIN [:table schema=cerebrum name=account_home] ah' +
                    '  ON ah.account_id=ai.account_id')
            tables.append(
                ('LEFT JOIN ([:table schema=cerebrum name=homedir] hd '
                 'LEFT JOIN [:table schema=cerebrum name=disk_info] d '
                 'ON d.disk_id = hd.disk_id) '
                 'ON hd.homedir_id=ah.homedir_id'))
        else:
            tables.extend([
                ', [:table schema=cerebrum name=account_home] ah ',
                ', [:table schema=cerebrum name=homedir] hd ' +
                '    LEFT JOIN [:table schema=cerebrum name=disk_info] d ' +
                '         ON d.disk_id = hd.disk_id'])
            where.extend(["ai.account_id=ah.account_id",
                          "ah.homedir_id=hd.homedir_id"])
            if home_spread is not None:
                where.append("ah.spread=:home_spread")

        if disk_id is not None:
            where.append("hd.disk_id=:disk_id")
        if host_id is not None:
            where.append("d.host_id=:host_id")
        where = " AND ".join(where)
        tables = "\n".join(tables)

        return self.query("""
        SELECT ai.account_id, en.entity_name, hd.home,
               ah.spread AS home_spread, d.path, hd.homedir_id, ai.owner_id,
               hd.status, ai.expire_date, ai.description, ei.created_at,
               d.disk_id, d.host_id
        FROM %s
        WHERE %s""" % (tables, where), {
            'home_spread': int(home_spread or 0),
            'account_spread': int(account_spread or 0),
            'disk_id': disk_id,
            'host_id': host_id
        })

    def list_reserved_users(self, fetchall=True):
        """Return all reserved users"""
        return self.query("""
        SELECT *
        FROM [:table schema=cerebrum name=account_info] ai
        WHERE ai.expire_date IS NULL AND NOT EXISTS (
          SELECT 'foo' FROM [:table schema=cerebrum name=entity_spread] es
          WHERE es.entity_id=ai.account_id)""",
                          fetchall=fetchall)

    def list_deleted_users(self):
        """Return all deleted users"""
        return self.query("""
        SELECT *
        FROM [:table schema=cerebrum name=account_info] ai
        WHERE ai.expire_date < [:now] AND NOT EXISTS (
          SELECT 'foo' FROM [:table schema=cerebrum name=entity_spread] es
          WHERE es.entity_id=ai.account_id)""")

    def list_accounts_by_owner_id(self, owner_id, owner_type=None,
                                  filter_expired=True):
        """Return a list of account-ids, or None if none found."""
        if owner_type is None:
            owner_type = self.const.entity_person
        where = "owner_id = :o_id AND owner_type = :o_type"
        if filter_expired:
            where += " AND (expire_date IS NULL OR expire_date > [:now])"
        return self.query("""
            SELECT account_id
            FROM [:table schema=cerebrum name=account_info]
            WHERE """ + where, {'o_id': int(owner_id),
                                'o_type': int(owner_type)})

    def list_account_authentication(self, auth_type=None, filter_expired=True,
                                    account_id=None, spread=None):
        binds = dict()
        tables = []
        where = []
        if auth_type is None:
            auth_type = self.const.auth_type_md5_crypt
        aa_method = argument_to_sql(auth_type, 'aa.method', binds, int)
        if spread is not None:
            tables.append('[:table schema=cerebrum name=entity_spread] es')
            where.append('ai.account_id=es.entity_id')
            where.append(argument_to_sql(spread, 'es.spread', binds, int))
            where.append(argument_to_sql(self.const.entity_account,
                                         'es.entity_type', binds, int))
        if filter_expired:
            where.append("(ai.expire_date IS NULL OR ai.expire_date > [:now])")
        if account_id:
            where.append(argument_to_sql(account_id, 'ai.account_id',
                                         binds, int))
        where.append('ai.account_id=en.entity_id')
        where = " AND ".join(where)
        if tables:
            tables = ','.join(tables) + ','
        else:
            tables = ''
        return self.query("""
        SELECT ai.account_id, en.entity_name, aa.method, aa.auth_data
        FROM %s
             [:table schema=cerebrum name=entity_name] en,
             [:table schema=cerebrum name=account_info] ai
             LEFT JOIN [:table schema=cerebrum name=account_authentication] aa
               ON ai.account_id=aa.account_id AND %s
        WHERE %s""" % (tables, aa_method, where), binds)

    def get_account_name(self):
        return self.account_name

    def make_passwd(self, uname, phrase=False, checkers=None):
        """Generate a random password"""
        password_generator = PasswordGenerator()
        for attempt in range(10):
            # try with 10 random passwords before giving up
            if phrase:
                r = password_generator.generate_dictionary_passphrase()
            else:
                r = password_generator.generate_password()
            try:
                check_password(r, self, checkers=checkers)
                return r
            except PasswordNotGoodEnough:
                if attempt == 9:  # last attempt
                    # raise PasswordNotGoodEnough(
                    #     '(after 10 attempts) ' + str(e))

                    # Keep the old behaviour and let the caller handle the bad
                    # password.
                    # Should not happen unless the configured password rules
                    # are too restrictive or min_length > MAKE_PASSWORD_LENGTH
                    return r  # give up and return the last password
                continue  # make a new attempt

    def suggest_unames(self, domain, fname, lname, maxlen=8, suffix=""):
        """Returns a tuple with 15 (unused) username suggestions based
        on the person's first and last name.

        domain: value domain code
        fname:  first name (and any middle names)
        lname:  last name
        maxlen: maximum length of a username (incl. the suffix)
        suffix: string to append to every generated username
        """
        goal = 15       # We may return more than this
        maxlen -= len(suffix)
        assert maxlen > 0, "maxlen - suffix = no characters left"
        potuname = ()

        lastname = self.simplify_name(lname, alt=1)
        if lastname == "":
            raise ValueError(
                "Must supply last name, got '%s', '%s'" % (fname, lname))

        fname = self.simplify_name(fname, alt=1)
        lname = lastname

        if fname == "":
            # This is a person with no first name.  We "fool" the
            # algorithm below by switching the names around.  This
            # will always lead to suggesting names with numerals added
            # to the end since there are only 8 possible usernames for
            # a name of length 8 or more.  (assuming maxlen=8)
            fname = lname
            lname = ""

        # We ignore hyphens in the last name, but extract the
        # initials from the first name(s).
        lname = lname.replace('-', '').replace(' ', '')
        initials = [n[0] for n in re.split(r'[ -]', fname)]

        # firstinit is set to the initials of the first two names if
        # the person has three or more first names, so firstinit and
        # initial never overlap.
        firstinit = ""
        initial = None
        if len(initials) >= 3:
            firstinit = "".join(initials[:2])
        # initial is taken from the last first name.
        if len(initials) > 1:
            initial = initials[-1]

        # Now remove all hyphens and keep just the first name.  People
        # called "Geir-Ove Johnsen Hansen" generally prefer "geirove"
        # to just "geir".

        fname = fname.replace('-', '').split(" ")[0][0:maxlen]

        # For people with many (more than three) names, we prefer to
        # use all initials.
        # Example:  Geir-Ove Johnsen Hansen
        #           ffff fff i       llllll
        # Here, firstinit is "GO" and initial is "J".
        #
        # gohansen gojhanse gohanse gojhanse ... goh gojh
        # ssllllll ssilllll sslllll ssilllll     ssl ssil
        #
        # ("ss" means firstinit, "i" means initial, "l" means last name)

        if len(firstinit) > 1:
            llen = min(len(lname), maxlen - len(firstinit))
            for j in range(llen, 0, -1):
                un = firstinit + lname[0:j] + suffix
                if self.validate_new_uname(domain, un):
                    potuname += (un, )

                if initial and len(firstinit) + 1 + j <= maxlen:
                    un = firstinit + initial + lname[0:j] + suffix
                    if self.validate_new_uname(domain, un):
                        potuname += (un, )

                if len(potuname) >= goal:
                    break

        # Now try different substrings from first and last name.
        #
        # geiroveh,
        # fffffffl
        # geirovjh geirovh geirovha,
        # ffffffil ffffffl ffffffll
        # geirojh geiroh geirojha geiroha geirohan,
        # fffffil fffffl fffffill fffffll ffffflll
        # geirjh geirh geirjha geirha geirjhan geirhan geirhans
        # ffffil ffffl ffffill ffffll ffffilll fffflll ffffllll
        # ...
        # gjh gh gjha gha gjhan ghan ... gjhansen ghansen
        # fil fl fill fll filll flll     fillllll fllllll

        flen = min(len(fname), maxlen - 1)
        for i in range(flen, 0, -1):
            llim = min(len(lname), maxlen - i)
            for j in range(1, llim + 1):
                if initial:
                    # Is there room for an initial?
                    if j < llim:
                        un = fname[0:i] + initial + lname[0:j] + suffix
                        if self.validate_new_uname(domain, un):
                            potuname += (un, )
                un = fname[0:i] + lname[0:j] + suffix
                if self.validate_new_uname(domain, un):
                    potuname += (un, )
            if len(potuname) >= goal:
                break

        # Try prefixes of the first name with nothing added.  This is
        # the only rule which generates usernames for persons with no
        # _first_ name.
        #
        # geirove, geirov, geiro, geir, gei, ge

        flen = min(len(fname), maxlen)
        for i in range(flen, 1, -1):
            un = fname[0:i] + suffix
            if self.validate_new_uname(domain, un):
                potuname += (un, )
            if len(potuname) >= goal:
                break

        # Absolutely last ditch effort:  geirov1, geirov2 etc.
        i = 1
        prefix = (fname + lname)[:maxlen - 2]

        while len(potuname) < goal and i < 100:
            un = prefix + str(i) + suffix
            i += 1
            if self.validate_new_uname(domain, un):
                potuname += (un, )
        return potuname

    def validate_new_uname(self, domain, uname):
        """Check that the requested username is legal and free"""
        try:
            # We instantiate EntityName directly because find_by_name
            # calls self.find() whose result may depend on the class
            # of self
            en = EntityName(self._db)
            en.find_by_name(uname, domain)
            return False
        except Errors.NotFoundError:
            return True

    _simplify_name_cache = [None] * 4

    def simplify_name(self, s, alt=0, as_gecos=0):
        """Convert string so that it only contains characters that are
        legal in a posix username.  If as_gecos=1, it may also be
        used for the gecos field"""

        try:
            # make sure that s contains only latin1 compatible characters
            s.encode('ISO_8859-1')
        except UnicodeEncodeError:
            self.logger.error(
                u'latin1 incompatible characters detected in '
                u'simplify_name for: {name}'.format(
                    name=s))
            raise ValueError('latin1 incompatible characters detected')
        key = bool(alt) + (bool(as_gecos) * 2)
        try:
            (tr, xlate_subst, xlate_match) = self._simplify_name_cache[key]
        except TypeError:
            xlate = {u'Ð': u'Dh',
                     u'ð': u'dh',
                     u'Þ': u'Th',
                     u'þ': u'th',
                     u'ß': u'ss'}
            if alt:
                xlate.update({u'Æ': u'ae',
                              u'æ': u'ae',
                              u'Å': u'aa',
                              u'å': u'aa'})
            xlate_subst = re.compile(r'[^a-zA-Z0-9 -]').sub

            def xlate_match(match):
                return xlate.get(match.group(), u'')
            tr = dict(zip(map(six.unichr, xrange(0200, 0400)), (u'x',) * 0200))
            tr.update(dict(zip(
                u'ÆØÅæø¿åÀÁÂÃÄÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝàáâãäçèéêëìíîïñòóôõöùúûüýÿ'
                u'{[}]|¦\\¨­¯´',
                u'AOAaooaAAAAACEEEEIIIINOOOOOUUUUYaaaaaceeeeiiiinooooouuuuyy'
                u'aAaAooO"--\'')))
            for ch in filter(lambda x: x in tr, xlate):
                del tr[ch]
            if not as_gecos:
                # lowercase the result
                xlate = dict(zip(xlate.keys(), map(six.text_type.lower,
                                                   xlate.values())))
            self._simplify_name_cache[key] = (tr, xlate_subst, xlate_match)

        # this is intended to be a replacement for s.translate until Python3
        for key, value in tr.items():
            s = s.replace(key, value)
        if not as_gecos:
            s = s.lower()

        xlated = xlate_subst(xlate_match, s)

        # normalise whitespace and hyphens: only ordinary SPC, only
        # one of them between words, and none leading or trailing.
        xlated = re.sub(r'\s+', u' ', xlated)
        xlated = re.sub(r' ?-+ ?', u'-', xlated).strip(u' -')
        try:
            xlated.encode('ascii')
        except UnicodeEncodeError:
            self.logger.error(
                u'ASCII incompatible output produced in '
                u'simplify_name for: {output}'.format(
                    output=xlated))
            raise ValueError('ASCII incompatible output produced')
        return xlated

    def search(self,
               spread=None,
               name=None,
               owner_id=None,
               owner_type=None,
               expire_start='[:now]',
               expire_stop=None,
               exclude_account_id=None):
        """Retrieves a list of Accounts filtered by the given criterias.
        If no criteria is given, all non-expired accounts are returned.

        If expire_start and expire_stop is used, accounts with expire_date
        between expire_start and expire_stop is returned.

        @param spread: Return entities that has this spread
        @type spread: Either be integer or string. A string with wildcards *
        and ? are expanded for "any chars" and "one char".

        @param name: Return only entities that matches name
        @type name: String. Wildcards * and ? are expanded for "any chars" and
        "one char".

        @param owner_id: Return entities that is owned by the owner_id(s)
        @type owner_id: Integer, list, tuple, set

        @param owner_type: Return entities where owners type is of owner_type
        @type owner_type: Integer

        @param expire_start: Filter on expire_date. If not specified use
        current time. If specified then filter on expire_date>=expire_start.
        If expire_start is None, don't apply a start_date filter.
        @type expire_start: Date. Either a string on format 'YYYY-mm-dd' or a
        mx.DateTime object

        @param expire_stop: Filter on expire_date. If None, don't apply a
        stop filter on expire_date. If other than None, filter on
        expire_date<expire_stop.
        @type expire_stop: Date. Either a string on format 'YYYY-mm-dd' or a
        mx.DateTime object

        @param exclude_account_id: Filter out account(s) with given account_id.
        @type exclude_account_id: Integer, list, tuple, set

        @return a list of tuples with the info (account_id,name,owner_id,
        owner_type,expire_date).
        """

        tables = []
        where = []
        tables.append("[:table schema=cerebrum name=account_info] ai")
        tables.append("[:table schema=cerebrum name=entity_name] en")
        where.append("en.entity_id=ai.account_id")
        where.append("en.value_domain=:vdomain")
        binds = {"vdomain": int(self.const.account_namespace)}

        if spread is not None:
            tables.append("[:table schema=cerebrum name=entity_spread] es")
            where.append("ai.account_id=es.entity_id")
            where.append("es.entity_type=:entity_type")
            try:
                spread = int(spread)
            except (TypeError, ValueError):
                spread = prepare_string(spread)
                tables.append("[:table schema=cerebrum name=spread_code] sc")
                where.append("es.spread=sc.code")
                where.append("LOWER(sc.code_str) LIKE :spread")
            else:
                where.append("es.spread=:spread")
            binds['spread'] = spread
            binds['entity_type'] = int(self.const.entity_account)

        if name is not None:
            name = prepare_string(name)
            where.append("LOWER(en.entity_name) LIKE :name")
            binds['name'] = name

        if owner_id is not None:
            where.append(argument_to_sql(owner_id, "ai.owner_id", binds, int))

        if owner_type is not None:
            where.append("ai.owner_type=:owner_type")
            binds['owner_type'] = owner_type

        if expire_start and expire_stop:
            where.append(
                ("(ai.expire_date>=:expire_start "
                 "and ai.expire_date<:expire_stop)"))
            binds['expire_start'] = expire_start
            binds['expire_stop'] = expire_stop
        elif expire_start and expire_stop is None:
            where.append(
                "(ai.expire_date>=:expire_start or ai.expire_date IS NULL)")
            binds['expire_start'] = expire_start
        elif expire_start is None and expire_stop:
            where.append("ai.expire_date<:expire_stop")
            binds['expire_stop'] = expire_stop

        if exclude_account_id is not None and len(exclude_account_id):
            where.append("NOT " + argument_to_sql(exclude_account_id,
                                                  "ai.account_id",
                                                  binds,
                                                  int))
        where_str = ""
        if where:
            where_str = "WHERE " + " AND ".join(where)

        return self.query("""
        SELECT DISTINCT ai.account_id AS account_id, en.entity_name AS name,
                        ai.owner_id AS owner_id, ai.owner_type AS owner_type,
                        ai.expire_date AS expire_date, ai.description AS
                        description,
                        ai.np_type AS np_type
        FROM %s %s""" % (','.join(tables), where_str), binds)

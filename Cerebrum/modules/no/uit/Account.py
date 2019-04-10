#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2003, 2004 University of Oslo, Norway
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
Account mixin for UiT.

TODO:
- Move everything related to generating usernames into a separate class.
"""
from __future__ import unicode_literals

import base64
import hashlib
import logging
import re

import six

import cereconf

from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Entity import EntityName
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.modules.legacy_users import LegacyUsers
from Cerebrum.utils import transliterate

logger = logging.getLogger(__name__)


def enc_auth_type_md5_crypt_hex(plaintext, salt=None):
    """
    Unsalted md5 hex-digest for UiT.

    Added by kennethj, 2005-08-03
    """
    plaintext = plaintext.rstrip("\n")
    m = hashlib.md5()
    m.update(plaintext)
    encrypted = m.hexdigest()
    return encrypted


def enc_auth_type_md5_b64(plaintext, salt=None):
    """
    Unsalted md5 b64-digest for UiT.

    Added by kennethj, 2005-08-03
    """
    m = hashlib.md5()
    m.update(plaintext.encode('utf-8'))
    foo = m.digest()
    encrypted = base64.encodestring(foo)
    encrypted = encrypted.rstrip()
    return encrypted


def generate_homedir(account_name):
    """
    Generate an appropriate homedir for a given username.
    """
    path_prefix = cereconf.UIT_DEFAULT_HOMEPATH_PREFIX
    return '%s/%s/%s/%s' % (path_prefix,
                            account_name[0],
                            account_name[0:2],
                            account_name)


def update_homedir(account, spread):
    """
    Auto-configure homedir for a given account and spread.
    """
    new_path = generate_homedir(account.account_name)

    try:
        old_home = account.get_home(spread)
    except Errors.NotFoundError:
        homedir_id = account.set_homedir(
            home=new_path,
            status=account.const.home_status_not_created)
        account.set_home(spread, homedir_id)
        logger.debug('added homedir %s for account_id=%r',
                     new_path, account.entity_id)
    else:
        old_path = old_home['home']
        old_id = old_home['homedir_id']
        if old_path != new_path:
            account.set_homedir(current_id=old_id, home=new_path)
            logger.debug('updated homedir %s -> %s for account_id=%r',
                         old_path, new_path, account.entity_id)


class AccountUiTMixin(Account.Account):
    """
    Account mixin class providing functionality specific to UiT.

    The methods of the core Account class that are overridden here,
    ensure that any Account objects generated through
    Cerebrum.Utils.Factory.get() provide functionality that reflects
    the policies of the University of Tromsoe.

    kort forklart:
    den siste write_db() er den
    som kjøres. den kaller opp foreldrenes write_db. de kaller igjen opp
    sine foreldre(grunnet self.__super.write_db()) til
    man til slutt kaller Account sin write_db(). når den returnerer så
    fortsetter metodene der de kallte super()
    Man har bare en write_db() i
    hele Account etter at man har inkludert Mixins, men man før tak i
    foreldrene ved å bruke super()
    """

    #
    # Override username generator in core Account.py
    # Do it the UiT way!
    #
    def suggest_unames(self, ssn, fname, lname):
        full_name = "%s %s" % (fname, lname)
        return [UsernamePolicy(self._db).get_uit_uname(ssn, full_name)]

    def encrypt_password(self, method, plaintext, salt=None):
        """
        Support UiT added encryption methods, for other methods call super()
        """

        if method == self.const.auth_type_md5_crypt_hex:
            return enc_auth_type_md5_crypt_hex(plaintext)
        elif method == self.const.auth_type_md5_b64:
            return enc_auth_type_md5_b64(plaintext)
        else:
            return super(AccountUiTMixin, self).encrypt_password(method,
                                                                 plaintext,
                                                                 salt=salt)

    def decrypt_password(self, method, cryptstring):
        """
        Support UiT added encryption methods, for other methods call super()
        """
        if method in (self.const.auth_type_md5_crypt_hex,
                      self.const.auth_type_md5_b64):
            raise NotImplementedError("Cant decrypt %s" % repr(method))
        return super(AccountUiTMixin, self).decrypt_password(method,
                                                             cryptstring)

    def verify_password(self, method, plaintext, cryptstring):
        """ Verify a password against a cryptstring.

        Returns True if the plaintext matches the cryptstring, False if it
        doesn't.  Raises a ValueError if the method is unsupported.
        """
        if method in (
                self.const.auth_type_md5_crypt,
                self.const.auth_type_md5_b64,
                self.const.auth_type_ha1_md5,
                self.const.auth_type_crypt3_des,
                self.const.auth_type_md4_nt,
                self.const.auth_type_ssha,
                self.const.auth_type_sha256_crypt,
                self.const.auth_type_sha512_crypt,
                self.const.auth_type_plaintext,
        ):
            salt = cryptstring
            return self.encrypt_password(method,
                                         plaintext,
                                         salt=salt) == cryptstring
        raise ValueError("Unknown method %r" % method)

    def set_home_dir(self, spread):
        """
        Auto-configure a homedir for a given spread.
        """
        update_homedir(self, spread)

    def list_all(self, spread=None, filter_expired=False):
        """
        List all users.

        optionally filtering the results on account spread and expiry.
        """
        where = ["en.entity_id=ai.account_id and en.entity_id=ei.entity_id"]
        tables = ['[:table schema=cerebrum name=entity_name] en']
        params = {}
        if spread is not None:
            # Add this table before account_info for correct left-join syntax
            where.append("es.entity_id=ai.account_id")
            where.append("es.spread=:account_spread")
            tables.append(", [:table schema=cerebrum name=entity_spread] es")
            params['account_spread'] = spread

        tables.append(', [:table schema=cerebrum name=account_info] ai')
        tables.append(', [:table schema=cerebrum name=entity_info] ei')
        if filter_expired:
            where.append("(ai.expire_date IS NULL OR ai.expire_date > [:now])")

        where = " AND ".join(where)
        tables = "\n".join(tables)

        sql = """
        SELECT ai.account_id, en.entity_name, ai.expire_date, ei.created_at
        FROM %s
        WHERE %s""" % (tables, where)

        return self.query(sql, params)

    def getdict_accid2mailaddr(self, filter_expired=True):
        ret = {}
        ed = Email.EmailDomain(self._db)
        binds = {
            'targ_type': int(self.const.email_target_account),
            'namespace': int(self.const.account_namespace),
        }
        stmt = """
          SELECT en.entity_id, ea.local_part, ed.domain
          FROM [:table schema=cerebrum name=account_info] ai
          JOIN [:table schema=cerebrum name=entity_name] en
            ON en.entity_id = ai.account_id
          JOIN [:table schema=cerebrum name=email_target] et
            ON et.target_type = :targ_type AND
               et.target_entity_id = ai.account_id
          JOIN [:table schema=cerebrum name=email_primary_address] epa
            ON epa.target_id = et.target_id
          JOIN [:table schema=cerebrum name=email_address] ea
            ON ea.address_id = epa.address_id
          JOIN [:table schema=cerebrum name=email_domain] ed
            ON ed.domain_id = ea.domain_id
          WHERE en.value_domain = :namespace
        """
        if filter_expired:
            stmt += " AND (ai.expire_date IS NULL OR ai.expire_date > [:now])"
        for row in self.query(stmt, binds):
            ret[row['entity_id']] = '@'.join((
                row['local_part'],
                ed.rewrite_special_domains(row['domain'])))
        return ret

    # TODO: check this method, may probably be done better
    def _update_email_server(self):
        es = Email.EmailServer(self._db)
        et = Email.EmailTarget(self._db)
        if self.is_employee():
            server_name = 'postboks'
        else:
            server_name = 'student_placeholder'
        es.find_by_name(server_name)
        try:
            et.find_by_email_target_attrs(target_entity_id=self.entity_id)
        except Errors.NotFoundError:
            et.populate(self.const.email_target_account,
                        self.entity_id,
                        self.const.entity_account)
            et.write_db()
        if not et.email_server_id:
            et.email_server_id = es.entity_id
            et.write_db()
        return et

    def is_employee(self):
        for r in self.get_account_types():
            if r['affiliation'] == self.const.affiliation_ansatt:
                return True
        return False


class UsernamePolicy(DatabaseAccessor):
    """
    Object to generate available usernames for UiT.
    """

    def _get_person_by_extid(self, id_type, id_value):
        pe = Factory.get('Person')(self._db)
        pe.find_by_external_id(id_type, id_value)
        return pe

    def _find_legacy_username(self, person, ssn, legacy_type):
        new_ac = Factory.get('Account')(self._db)
        valid_uname_re = re.compile('^[a-z]{3}[0-9]{3}$')

        for row in sorted(
                LegacyUsers(self._db).search(ssn=ssn, type=legacy_type),
                key=lambda r: (r['source'], r['user_name'])):
            legacy_username = row['user_name']
            if not valid_uname_re.match(legacy_username):
                logger.debug('skipping invalid legacy_username %r',
                             legacy_username)
                continue

            # valid username found in legacy for this ssn
            # check that its not already used in BAS!
            new_ac.clear()
            try:
                new_ac.find_by_name(legacy_username)
            except Errors.NotFoundError:
                logger.debug('Found free legacy username %r', legacy_username)
                return legacy_username

            # legacy_username tied to fnr already used in BAS. We have an
            # error situation!
            if new_ac.owner_id == person.entity_id:
                raise RuntimeError(
                    "Person %s already has account %s in BAS!"
                    % (ssn, new_ac.account_name))
            else:
                # and used by another person!
                # raise Errors.IntegrityError("Legacy account %s not owned
                # by person %s in BAS!" (legacy_username,fnr))
                logger.warning(
                    "Legacy account %s not owned by person %s in BAS,"
                    " continue with next (if any) legacy username",
                    legacy_username, ssn)
                continue
        raise Errors.NotFoundError("No avaliable legacy username found")

    def get_sito_uname(self, fnr, name):
        """
        Generate a SITO account_name.

        SITO accounts have their own namespace. SITO usernames are named
        "XXXNNN-s", where:

            XXX = letters generated based on *name*
            NNN = unique numeric identifier
            s = The letter s
        """
        cstart = 0
        step = 1

        co = Factory.get('Constants')(self._db)
        try:
            self._get_person_by_extid(co.externalid_fodselsnr, fnr)
        except Errors.NotFoundError:
            raise Errors.ProgrammingError(
                "Trying to create account for person:%s that does not exist!"
                % fnr)

        # getting here implies that person does not have a previous account in
        # BAS create a new username
        inits = self.get_initials(name)
        sito_post = cereconf.USERNAME_POSTFIX['sito']
        return self.get_serial(inits, cstart, step=step, postfix=sito_post)

    def get_uit_uname(self, fnr, name, regime=None):
        """
        UiT function that generates a username.

        Generate a regular UiT account_name.  Accounts are named "XXXNNN",
        where:

            XXX = letters generated based on *name*
            NNN = unique numeric identifier

        This method will also check for pre-existing, available usernames for
        the owner identified by *fnr*, as usernames from legacy systems may be
        recorded in the *LegacyUsers* module.  If more than one legacy username
        exists, the first found will be used.  If no legacy usernames exists, a
        new one will be generated.

        :param fnr:
            Norwegian national id of the account owner, 11 digits
        :param name:
            Name of the account owner
        :param: regime:
            Optional account type (affects numeric identifiers for "ADMIN"
            accounts).

        :returns:
            A username on the form 'abc012' <three letters><tree digits>
        """
        if regime == "ADMIN":
            cstart = 999
            step = -1
            legacy_type = 'SYS'
        else:
            cstart = 0
            step = 1
            legacy_type = 'P'

        co = Factory.get('Constants')(self._db)

        for id_type in (co.externalid_fodselsnr, co.externalid_sys_x_id):
            try:
                pe = self._get_person_by_extid(id_type, fnr)
                break
            except Errors.NotFoundError:
                continue
        else:
            raise RuntimeError(
                "Trying to create account for person:%s that "
                "does not exist!" % fnr)

        try:
            return self._find_legacy_username(pe, fnr, legacy_type)
        except Errors.NotFoundError:
            inits = self.get_initials(name)
            return self.get_serial(inits, cstart, step=step)

    def get_serial(self, inits, cstart, step=1, postfix=None):
        """
        Generate a new, numbered username.
        """
        lu = LegacyUsers(self._db)
        en = EntityName(self._db)
        found = False
        postfix = postfix or ''
        while cstart <= 999 and cstart >= 0:
            # xxx999 is reserved for admin use
            uname = "%s%03d%s" % (inits, cstart, postfix)
            if en.entity_name_exists(uname) or lu.exists(uname):
                cstart += step
            else:
                found = True
                break

        if not found:
            raise RuntimeError(
                "Unable to find serial using inits=%r, cstart=%r, step=%r" %
                (inits, cstart, step))
        return six.text_type(uname)

    def get_initials(self, full_name):
        """
        Generate a set of three-letter initials for a name
        """
        # Gets the first 3 letters based upon the name of the user.
        full_name = transliterate.for_posix(full_name)
        name = full_name.replace('.', ' ').replace('\'', '').split()
        name_length = len(name)

        if name_length == 1:
            inits = name[0][0:3]
        else:
            inits = name[0][0:1] + name[-1][0:2]

        # sanity check
        p = re.compile('^[a-z]{3}$')
        if p.match(inits):
            return inits
        else:
            raise RuntimeError(
                "Generated invalid initials %r for %r" % (inits, full_name))

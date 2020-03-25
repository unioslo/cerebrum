# -*- coding: utf-8 -*-
# Copyright 2003-2008, 2013, 2016 University of Oslo, Norway
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
"""HiOf specific mixin functionality for the Account class"""
import re
import time
import cPickle

import cereconf

from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email


class AccountHiOfMixin(Account.Account):
    """Account mixin class providing functionality specific to HiOf.

    The methods of the core Account class that are overridden here,
    ensure that any Account objects generated through
    Cerebrum.Utils.Factory.get() provide functionality that reflects
    the policies at HiOf.

    """

    def __init__(self, db):
        """
        Override __init__ to set up AD spesific constants.
        """
        self.__super.__init__(db)
        # Setup AD spread constants
        if not hasattr(cereconf, 'AD_ACCOUNT_SPREADS'):
            raise Errors.CerebrumError(
                "Missing AD_ACCOUNT_SPREADS in cereconf")
        self.ad_account_spreads = [self.const.Spread(
            spread) for spread in cereconf.AD_ACCOUNT_SPREADS]
        # Setup defined ad traits
        if not hasattr(cereconf, 'AD_TRAIT_TYPES'):
            raise Errors.CerebrumError("Missing AD_TRAIT_TYPES in cereconf")
        self.ad_trait_types = []
        for trait_str in cereconf.AD_TRAIT_TYPES:
            self.ad_trait_types.append(self.const.EntityTrait(trait_str))

    def illegal_name(self, name):
        """HiOf specific illegal names."""
        # Avoid circular import dependency
        from Cerebrum.modules.PosixUser import PosixUser

        if isinstance(self, PosixUser):
            # TODO: Kill the ARsystem user to limit range and legal characters
            if len(name) > 8:
                return "too long (%s)" % name
            if re.search("^[^A-Za-z]", name):
                return "must start with a character (%s)" % name
            if re.search(r"[^A-Za-z0-9\-_]", name):
                return "contains illegal characters (%s)" % name
        return super(AccountHiOfMixin, self).illegal_name(name)

    def update_email_addresses(self):
        """Update email addresses"""
        # Find, create or update a proper EmailTarget for this
        # account.
        et = Email.EmailTarget(self._db)
        if self.is_deleted() or self.is_reserved():
            target_type = self.const.email_target_deleted
        else:
            target_type = self.const.email_target_account
        try:
            et.find_by_email_target_attrs(target_entity_id=self.entity_id)
            et.email_target_type = target_type
        except Errors.NotFoundError:
            # We don't want to create e-mail targets for reserved or
            # deleted accounts, but we do convert the type of existing
            # e-mail targets above.
            if target_type == self.const.email_target_deleted:
                return
            et.populate(target_type, self.entity_id, self.const.entity_account)
        et.write_db()
        # For deleted/reserved users, set expire_date for all of the
        # user's addresses, and don't allocate any new addresses.
        ea = Email.EmailAddress(self._db)
        if target_type == self.const.email_target_deleted:
            expire_date = self._db.DateFromTicks(time.time() +
                                                 60 * 60 * 24 * 180)
            for row in et.get_addresses():
                ea.clear()
                ea.find(row['address_id'])
                if ea.email_addr_expire_date is None:
                    ea.email_addr_expire_date = expire_date
                ea.write_db()
            return
        # if an account without email_server_target is found assign
        # the appropriate server
        acc_types = self.get_account_types()
        entity = Factory.get("Entity")(self._db)
        try:
            entity.clear()
            entity.find(self.owner_id)
        except Errors.NotFoundError:
            pass

        if not et.email_server_id:
            # This updates email servers for employees and students
            if entity.entity_type != self.const.entity_group:
                self._update_email_server('epost.hiof.no')

        # Figure out which domain(s) the user should have addresses
        # in.  Primary domain should be at the front of the resulting
        # list.
        # if the only address found is in EMAIL_DEFAULT_DOMAINS
        # don't set default address. This is done in order to prevent
        # adresses in default domain being sat as primary
        # TODO: account_types affiliated to OU's  without connected
        # email domain don't get a default address
        primary_set = False
        ed = Email.EmailDomain(self._db)
        ed.find(self.get_primary_maildomain())
        domains = [ed.email_domain_name]

        # Add the default domains if missing
        for domain in Email.get_default_email_domains():
            if domain not in domains:
                domains.append(domain)

        # Iterate over the available domains, testing various
        # local_parts for availability.  Set user's primary address to
        # the first one found to be available.
        try:
            self.get_primary_mailaddress()
        except Errors.NotFoundError:
            pass
        epat = Email.EmailPrimaryAddressTarget(self._db)
        for domain in domains:
            if ed.email_domain_name != domain:
                ed.clear()
                ed.find_by_domain(domain)
            # Check for 'cnaddr' category before 'uidaddr', to prefer
            # 'cnaddr'-style primary addresses for users in
            # maildomains that have both categories.
            ctgs = [int(r['category']) for r in ed.get_categories()]
            local_parts = []
            if int(self.const.email_domain_category_cnaddr) in ctgs:
                local_parts.append(self.get_email_cn_local_part(
                    given_names=1, max_initials=1))
                local_parts.append(self.account_name)
            elif int(self.const.email_domain_category_uidaddr) in ctgs:
                local_parts.append(self.account_name)
            for lp in local_parts:
                lp = self.wash_email_local_part(lp)
                # Is the address taken?
                ea.clear()
                try:
                    ea.find_by_local_part_and_domain(lp, ed.entity_id)
                    if ea.email_addr_target_id != et.entity_id:
                        # Address already exists, and points to a
                        # target not owned by this Account.
                        continue
                    # Address belongs to this account; make sure
                    # there's no expire_date set on it.
                    ea.email_addr_expire_date = None
                except Errors.NotFoundError:
                    # Address doesn't exist; create it.
                    ea.populate(lp, ed.entity_id, et.entity_id, expire=None)
                ea.write_db()
                # HiØ do not want the primary adress to change automatically
                if not primary_set:
                    epat.clear()
                    try:
                        epat.find(ea.email_addr_target_id)
                    except Errors.NotFoundError:
                        epat.clear()
                        epat.populate(ea.entity_id, parent=et)
                        epat.write_db()
                    primary_set = True

    def _update_email_server(self, server_name):
        es = Email.EmailServer(self._db)
        et = Email.EmailTarget(self._db)
        es.find_by_name(server_name)
        try:
            et.find_by_email_target_attrs(target_entity_id=self.entity_id)
        except Errors.NotFoundError:
            # Not really sure about this. it is done at UiO, but maybe it is
            # not
            # right to make en email_target if one is not found??
            et.clear()
            et.populate(self.const.email_target_account,
                        self.entity_id,
                        self.const.entity_account)
            et.write_db()
        et.email_server_id = es.entity_id
        et.write_db()
        return et

    def _calculate_homedir(self):
        r"""Calculate what a user should get as its HomeDirectory in AD,
        according to the specifications. Note that this only returns what
        _would_ be set, but the specification also says that it should not be
        changed after first set.

        The rules are:

        - Employees and affiliated should get \\LS01.hiof.no\HomeA\USERNAME
        - Students should get \\LS02.hiof.no\HomeS\USERNAME
        - The rest should not get anything.
        """
        is_student = False
        for row in self.get_account_types():
            affiliation = row['affiliation']
            if affiliation in (self.const.affiliation_ansatt,
                               self.const.affiliation_tilknyttet):
                # Highest priority, could be returned at once
                return r'\\LS01.hiof.no\HomeA\{}'.format(self.account_name)
            if affiliation == self.const.affiliation_student:
                is_student = True
        return r'\\LS02.hiof.no\HomeS\{}'.format(
            self.account_name) if is_student else r''

    def _calculate_scriptpath(self):
        """Calculate what a user should get as its ScriptPath in AD, according
        to the specifications. Note that this only returns what _would_ be set,
        but the specification also says that it should not be changed after
        first set.

        The rules are:

        - Employees and affiliated should get "ansatt-LS01.bat"
        - Students should get "student-LS02.bat"
        - The rest should not get anything.

        """
        is_student = False
        for row in self.get_account_types():
            affiliation = row['affiliation']
            if affiliation in (
                    self.const.affiliation_ansatt,
                    self.const.affiliation_tilknyttet):
                # Highest priority, could be returned at once
                return 'ansatt-LS01.bat'
            if affiliation == self.const.affiliation_student:
                is_student = True
        return 'student-LS02.bat' if is_student else ''

    def update_ad_attributes(self):
        """Check and update the AD attributes for the account."""
        spread = self.const.spread_ad_account
        # No need to set if user does not have an AD spread:
        if int(spread) not in (int(r['spread']) for r in self.get_spread()):
            return

        for atr, func in ((self.const.ad_attribute_homedir,
                           self._calculate_homedir),
                          (self.const.ad_attribute_scriptpath,
                           self._calculate_scriptpath)):
            val = func()
            if val is None:
                continue
            # Not change if already set:
            if not self.list_ad_attributes(self.entity_id, spread, atr):
                self.set_ad_attribute(spread, atr, func())

    def add_spread(self, spread):
        """Update AD attributes when an AD-spread is set."""
        ret = self.__super.add_spread(spread)
        if spread == self.const.spread_ad_account:
            self.update_ad_attributes()
        return ret

    def delete_spread(self, spread):
        """
        If the spread that is deleted is an AD account spread, any AD
        attributes in Cerebrum belonging to that spread should also be
        removed.
        """
        if spread in self.ad_account_spreads:
            self.delete_ad_attrs(spread=spread)
        ret = self.__super.delete_spread(spread)
        return ret

    def set_account_type(self, *args, **kwargs):
        """Update AD attributes when an account type is set.

        This is in case the user had no account types to begin with, in which
        it could have blank attribute values.
        """
        ret = self.__super.set_account_type(*args, **kwargs)
        self.update_ad_attributes()
        return ret

    # Methods for manipulation accounts AD-attributes.
    # AD attributes OU, Homedir and Profile Path are stored in
    # entity_traits. The methods make it easier to get and set
    # these attributes.

    # TODO: The methods for updating traits for old AD-attributes should be
    # removed after the new AD sync is in production and the old ones are
    # removed.

    def get_ad_attrs(self):
        """
        Return all AD attrs for account

        @rtype: dict
        @return: {spread : {attr_type:attr_val, ...}, ...}
        """
        ret = {}
        # It's quicker to get all traits at once instead of picking
        # one at the time
        traits = self.get_traits()
        # We only want the relevant ad traits
        for trait_type, entity_trait in traits.items():
            if trait_type in self.ad_trait_types:
                attr_type = str(trait_type)
                unpickle_val = cPickle.loads(str(entity_trait['strval']))
                # unpickle_val is a spread -> attribute value mapping
                for spread, attr_val in unpickle_val.items():
                    spread = int(spread)
                    if spread not in ret:
                        ret[spread] = {}
                    ret[spread][attr_type] = attr_val
        return ret

    def get_ad_attrs_by_spread(self, spread):
        """
        Return account's AD attributes given by spread.

        @param spread: account ad spread
        @type  spread: int OR _SpreadCode
        @rtype: dict
        @return: {attr_type : attr_value, ...}
        """
        assert spread in self.ad_account_spreads
        tmp = self.get_ad_attrs()
        return tmp.get(int(spread), {})

    def get_ad_attrs_by_type(self, trait_type):
        """
        Return accounts's AD attributes of given type.

        @param trait_type: ad trait type
        @type  trait_type: str OR _EntityTraitCode
        @rtype: dict
        @return: {spread : attr_value, ...}
        """
        tmp = self.get_trait(trait_type)
        if tmp:
            return cPickle.loads(str(tmp['strval']))
        return None

    def populate_ad_attrs(self, trait_type, ad_attr_map):
        """
        Store given AD attribute values as a entity_trait. Assert that
        ad_attr_map is a spread -> value mapping.

        @param trait_type: ad trait type
        @type  trait_type: str OR _EntityTraitCode
        @param ad_attr_map: spread -> attr value mapping
        @type  ad_attr_map: dict
        """
        doit = False
        for k in ad_attr_map:
            for spread in self.ad_account_spreads:
                if k == int(spread):
                    doit = True
        if doit:
            self.populate_trait(trait_type, strval=cPickle.dumps(ad_attr_map))

    def delete_ad_attrs(self, spread=None):
        """
        Delete ad_attrs in entity trait for given spread, or for all
        ad spreads if None given.

        @param spread: ad account spread
        @type  spread: int OR _SpreadCode
        """
        for trait_type in self.ad_trait_types:
            # If spread is None simply delete all ad_traits for this user
            if not spread:
                self.delete_trait(trait_type)
                continue
            # Spread is given, then we must modify the traits
            tmp = self.get_ad_attrs_by_type(trait_type)
            if tmp and int(spread) in tmp:
                # If this spread is the only one, delete the trait
                if len(tmp) == 1:
                    self.delete_trait(trait_type)
                else:
                    del tmp[spread]
                    # Populate the remaining mapping
                    self.populate_ad_attrs(trait_type, tmp)

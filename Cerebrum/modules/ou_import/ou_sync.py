# -*- coding: utf-8 -*-
#
# Copyright 2022 University of Oslo, Norway
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
Org unit import routine.

This module provides utilities to update org unit metadata (external ids,
contact info, addresses, etc...).  These utilities will also create new org
units, and disable old org units.

The will *not* populate or modify the ou perspective info (parent org unit, org
unit tree).  Any new org units will be dangling (i.e. not be included in any
perspectives) unless a separate routine is used to update ou pespective info.

This will typically run on all org units present in a given source system
*before* the org tree is updated, to ensure that each org unit exists as an
object in Cerebrum, and is up-to-date.

TODO
----
We should remove our dependence on location code (stedkode, sko) - currently
this id is required for finding existing org units, and creating new org units.
See the py:mod:`Cerebrum.modules.ou_import` module for more details.
"""
import datetime
import logging

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory

from Cerebrum.modules.import_utils.syncs import (
    AddressSync,
    ContactInfoSync,
    ExternalIdSync,
    NameLanguageSync,
    pretty_const,
)

logger = logging.getLogger(__name__)


class OuWriter(object):
    """
    This object stores any PreparedOrgUnit object it is given.
    """

    # See `default_spreads`:
    usage_to_spread = cereconf.OU_USAGE_SPREAD

    # Institution for Stedkode ids
    institution = cereconf.DEFAULT_INSTITUSJONSNR

    # Name variants that are "owned" by this import
    #
    # Only these names can be imported/assigned to OU objects by this import.
    # If any of these are missing in OrgUnit objects, they will be removed from
    # the database
    #
    # This is required because EntityNameWithLanguage isn't stored by source
    # system - if we have other name variants from other sources or import
    # routines, we don't want to touch those.
    name_types = ('OU acronym', 'OU short', 'OU display', 'OU name', 'OU long')

    def __init__(self, db, source_system, publish_all=False):
        """
        :param db: a cerebrum database connection/transaction
        :param source_system: source system for ou data
        :param publish_all: if true, overrides the is_visible attribute
        """
        self.db = db
        self.source_system = source_system
        self.publish_all = publish_all

        self._sync_ids = ExternalIdSync(self.db, source_system)
        self._sync_cinfo = ContactInfoSync(self.db, source_system)
        self._sync_addrs = AddressSync(self.db, self.source_system)

        const = Factory.get('Constants')(db)
        name_types = tuple(const.get_constant(const.EntityNameCode, t)
                           for t in self.name_types)
        self._sync_names = NameLanguageSync(self.db, name_types)

    @property
    def creator_id(self):
        """ creator_id for db changes that requires an owner/creator. """
        try:
            self._creator_id
        except AttributeError:
            ac = Factory.get("Account")(self._db)
            ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
            self._creator_id = ac.entity_id
        return self._creator_id

    @property
    def default_spreads(self):
        """
        Prepared translation of usage to default-spreads mapping.
        """
        # a map of <usage-tag> -> <spread-const>
        try:
            self._default_spreads
        except AttributeError:
            const = Factory.get('Constants')(self.db)
            self._default_spreads = {}
            for usage, spread_str in self.usage_to_spread.items():
                spread = const.get_constant(const.Spread, spread_str)
                self._default_spreads[usage] = spread
        return self._default_spreads

    def _disable_ou(self, ou):
        """
        Disable org unit (i.e. set quarantine).

        :param ou: Populated OU object.
        :returns bool: True if object actually was modified (disabled)
        """
        disable_quar = ou.const.quarantine_ou_notvalid
        exists = list(ou.get_entity_quarantine(qtype=disable_quar))
        if exists:
            # TODO: Should maybe ensure that:
            # - start_date is set appropriately
            # - disable_until is not set
            return False

        # set quarantine on ou
        ou.add_entity_quarantine(
            qtype=disable_quar,
            creator=self.creator_id,
            description=__name__,
            start=datetime.date.today())
        return True

    def _enable_ou(self, ou):
        """ Enable org unit (i.e. remove quarantines).

        :param ou: Populated OU object.
        :returns bool: True if object actually was modified (enabled)
        """
        disable_quars = (
            ou.const.quarantine_ou_notvalid,
            ou.const.quarantine_ou_remove,
        )
        did_enable = False
        for row in ou.get_entity_quarantine():
            if row['quarantine_type'] in disable_quars:
                ou.delete_entity_quarantine(row['quarantine_type'])
                did_enable = True
        return did_enable

    def _update_spreads(self, ou, prepared_ou):
        """
        Add/remove managed spreads.

        Managed spreads includes any spread defined in
        ``cereconf.OU_USAGE_SPREAD``, as well as the ``publishable_ou`` spread.

        If a spread is removed from ``OU_USAGE_SPREAD``, it will *not* be
        removed from org units during sync.  If a managed spread needs to be
        removed from all org units, it must remain a *managed* spread (i.e.
        exist in ``cereconf.OU_USAGE_SPREAD``).  To do this, map an *invalid*
        usage name (i.e. a tag/usage name that won't occur in sources) to the
        given spread.

        :type ou: Cerebrum.OU.OU
        :param ou: populated ou object to update

        :type prepared_ou: .ou_model.PreparedOrgUnit
        :param prepared_ou: ou data to use in update

        :rtype: tuple
        :returns:
            Returns any changes done by this function in two sets:

            - the first set contains spreads that were added (if any)
            - the second set contains spreads that were removed (if any)
        """
        is_valid = prepared_ou.is_valid
        is_visible = prepared_ou.is_visible or self.publish_all

        # spreads that this routine adds/removes
        managed_spreads = (set((ou.const.spread_ou_publishable,))
                           | set(self.default_spreads.values()))

        curr_spreads = set(ou.const.Spread(r['spread'])
                           for r in ou.get_spread())

        need_spreads = set()
        if is_valid:
            if is_visible:
                need_spreads.add(ou.const.spread_ou_publishable)
            for usage in prepared_ou.usage_codes:
                spread = self.default_spreads.get(usage)
                if spread is None:
                    logger.debug('unknown usage code for ou %s: %r',
                                 repr(prepared_ou), usage)
                    # unknown usage code / no spread for usage code
                    continue
                need_spreads.add(spread)

        to_add = need_spreads - curr_spreads
        to_rem = managed_spreads.intersection(curr_spreads) - need_spreads

        for spread in to_add:
            ou.add_spread(spread)
        for spread in to_rem:
            ou.delete_spread(spread)
        logger.info('spread changes for entity_id=%d, add=%r, remove=%r',
                    ou.entity_id, pretty_const(to_add), pretty_const(to_rem))
        return to_add, to_rem

    def _create_ou(self, prepared_ou):
        """
        create new ou object with a given location code.

        :type prepared_ou: .ou_model.PreparedOrgUnit
        :param prepared_ou: ou data with location code

        :rtype: Cerebrum.OU.OU
        :returns: The created ou object
        """
        ou = Factory.get('OU')(self.db)
        sko_support = hasattr(ou, 'find_stedkode')
        if not sko_support:
            raise NotImplementedError("missing support for location code")

        sko = prepared_ou.location_t
        if not sko:
            raise NotImplementedError("no location code in "
                                      + repr(prepared_ou))
        ou.populate(sko[0], sko[1], sko[2],
                    institusjon=self.institution)
        ou.write_db()
        return ou

    def _update_ou(self, ou, prepared_ou):
        """
        update existing ou object from given ou data.

        :type ou: Cerebrum.OU.OU
        :param ou: populated ou object to update

        :type prepared_ou: .ou_model.PreparedOrgUnit
        :param prepared_ou: ou data to use in update
        """
        # Do not touch name information for an OU that has been expired. It
        # may not conform to all of our requirements.
        changes = {
            'external_id': self._sync_ids(ou, prepared_ou.external_ids),
            'contact_info': self._sync_cinfo(ou, prepared_ou.contact_info),
            'addresses': self._sync_addrs(ou, prepared_ou.addresses),
            'names': self._sync_names(ou, prepared_ou.names),
            'spreads': self._update_spreads(ou, prepared_ou),
        }

        if prepared_ou.is_valid:
            if self._enable_ou(ou):
                logger.info('enabled ou %s (entity_id=%r)',
                            repr(prepared_ou), ou.entity_id)
                changes['active'] = (True,)
        else:
            if self._disable_ou(ou):
                logger.info('disabled ou %s (entity_id=%r)',
                            repr(prepared_ou), ou.entity_id)
                changes['active'] = (True,)
        ou.write_db()
        logger.info('changed: %r',
                    [k for k, v in sorted(changes.items()) if any(v)])
        return changes

    def find_ou(self, prepared_ou):
        """
        Find existing OU in database.

        :type prepared_ou: .ou_model.PreparedOrgUnit

        :rtype: Cerebrum.OU.OU
        """
        # TODO: requires a location_code from the source system/in the prepared
        # ou data.  Should implement a generic lookup that also checks for
        # external_id matches.
        ou = Factory.get('OU')(self.db)
        sko_support = hasattr(ou, 'find_stedkode')
        if not sko_support:
            raise NotImplementedError("missing support for location code")

        sko = prepared_ou.location_t
        if not sko:
            raise NotImplementedError("no location code in "
                                      + repr(prepared_ou))

        try:
            ou.find_stedkode(sko[0], sko[1], sko[2],
                             institusjon=self.institution)
            logger.info('found ou for %s: entity_id=%r',
                        repr(prepared_ou), ou.entity_id)
            return ou
        except Errors.NotFoundError:
            logger.info('no matching ou for %s', repr(prepared_ou))
            return None

    def sync_ou(self, prepared_ou):
        """
        Sync data for a given source org unit.

        :type prepared_ou: .ou_model.PreparedOrgUnit
        :param prepared_ou: ou data to sync

        :rtype: Cerebrum.OU.OU
        :returns: The update ou object, if any.
        """
        ou_repr = repr(prepared_ou)
        is_valid = prepared_ou.is_valid
        logger.info('store_ou: %s', ou_repr)

        ou = self.find_ou(prepared_ou)

        if ou is None and not is_valid:
            # no ou in db, source invalid or expired
            logger.info('store_ou: ignoring inactive ou %s', ou_repr)
        elif ou and not is_valid:
            # ou in db, but source invalid or expired
            # TODO: should we check if the ou has already been disabled and
            # ignore any changes after that?
            logger.info('store_ou: clearing ou %r', ou_repr)
            # TODO: do we need to do anything other than update the ou?
            self._update_ou(ou, prepared_ou)
        elif ou is None and is_valid:
            # no ou in db, but source says there should be
            logger.info('store_ou: creating ou %r', ou_repr)
            ou = self._create_ou(prepared_ou)
            self._update_ou(ou, prepared_ou)
        else:
            # ou in db, source valid - may need update
            logger.info('store_ou: updating ou %r', ou_repr)
            self._update_ou(ou, prepared_ou)
        return ou

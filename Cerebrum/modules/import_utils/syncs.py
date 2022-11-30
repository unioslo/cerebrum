# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
Common utils for updating entity info from a given source system.

This module generally consists of classes that implements affect + populate
logic for all data types (including those that are missing this)
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import abc
import logging

import six

from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum.Utils import Factory

logger = logging.getLogger(__name__)

# Extra loggger for debugging (potentially sensitive personal information)
# values.  This logger is disabled by default, but can be enabled by calling
# `enable_debug_log` or by setting *propagate* in logger config.
debug_log = logger.getChild('debug')
debug_log.propagate = False
debug_log.addHandler(logging.NullHandler())


def enable_debug_log():
    """
    Enable debug logging of input values.

    Note: This should generally not be used in production code.  Prefer adding
    config of `__name__ + '.debug'` to logger config.
    """
    debug_log.propagate = True


def pretty_const(value):
    """ Format a CerebrumCode, or sequence of CerebrumCode values. """
    if isinstance(value, (list, tuple, set)):
        return tuple(sorted(six.text_type(c) for c in value))
    return six.text_type(value)


def pretty_const_pairs(value):
    """ Format a CerebrumCode, or sequence of CerebrumCode values. """
    return tuple(sorted((six.text_type(a) + '/' + six.text_type(b))
                        for a, b in value))


class _BaseSync(six.with_metaclass(abc.ABCMeta)):
    """ Abstract sync class.

    Subclasses need to implement:

    - set a <subclass>.name
    - __call__(entity, values) -> update entity to values
    """

    # Human readable name of this sync, for log messages and errors
    name = None

    def __init__(self, db):
        if not type(self).name:
            raise NotImplementedError('abstract sync (no name)')
        self.db = db
        self.const = Factory.get('Constants')(db)

    def __repr__(self):
        return '<{name}>'.format(name=type(self).__name__)

    @abc.abstractmethod
    def __call__(self, entity, source_values):
        pass


class _SourceSystemSync(_BaseSync):
    """ Abstract sync with source_system. """

    def __init__(self, db, source_system):
        super(_SourceSystemSync, self).__init__(db)
        co = self.const
        self.source_system = self.const.get_constant(co.AuthoritativeSystem,
                                                     source_system)

    def __repr__(self):
        return '<{name}[{source}]>'.format(
            name=type(self).__name__,
            source=six.text_type(self.source_system))


class _KeyValueSync(_SourceSystemSync):
    """ Abstract sync of key/value tuples.

    Abstract, re-usable class for implementing simple (source-system,
    CerebrumCode type) to value updaters.

    Subclasses need to implement:

    - set a <subclass>.name and a <subclass>.type_cls
    - fetch_current() -> get (current key, current value) pairs from entity
    - apply_changes() -> update database with entity changes
    """
    # A constant type (or attribute to fetch from Factory.get('Constants'))
    type_cls = None

    def __init__(self, db, source_system, affect_types=None):
        if not type(self).type_cls:
            raise NotImplementedError('abstract sync (no type_cls)')
        super(_KeyValueSync, self).__init__(db, source_system)
        if affect_types:
            self.affect_types = tuple(self.get_type(t) for t in affect_types)
        else:
            self.affect_types = None

    def get_type(self, value):
        return self.const.get_constant(self.type_cls, value)

    @abc.abstractmethod
    def fetch_current(self, entity):
        """ Fetch all current key/value pairs.

        Fetches all current values in Cerebrum (regardless of affect_types).

        :param entity: an entity to fetch current values for
        :returns: an iterable of (int-code, value) pairs
        """
        pass

    @abc.abstractmethod
    def apply_changes(self, entity, values, to_add, to_update, to_remove):
        """ Apply changes to entity.

        :param entity: an entity to update
        :param dict values: a map of (type -> value) for values to add/update
        :param to_add: a set of types to add
        :param to_update: a set of types to update
        :param to_remove: a set of types to remove

        Note that set(values) must be (to_add | to_update)
        """
        pass

    def __call__(self, entity, pairs):
        """ Sync entity with key/value pairs.

        :param entity:
            An Entity object to sync

        :param pairs:
            A sequence of (CerebrumCode, value) pairs to sync

            The sequence should be the current values from a given source
            system.
        """
        entity_id = int(entity.entity_id)
        debug_log.debug('%s(%d, %s)', repr(self), entity_id, repr(pairs))

        new_pairs = set((self.get_type(key), value) for key, value in pairs)
        new_types = set(t[0] for t in new_pairs)
        logger.debug('%s(%d, <%s>)', repr(self), entity_id,
                     pretty_const(new_types))
        if len(new_types) != len(new_pairs):
            raise ValueError('duplicate %s type given' % (self.name,))

        if self.affect_types is not None:
            invalid_types = set(t for t in new_types
                                if t not in self.affect_types)
            if invalid_types:
                raise ValueError('invalid %s types: %s (must be one of %s)'
                                 % (self.name,
                                    pretty_const(invalid_types),
                                    pretty_const(self.affect_types)))

        curr_pairs = set((self.get_type(k), v)
                         for k, v in self.fetch_current(entity)
                         if self.affect_types is None
                         or k in self.affect_types)
        curr_types = set(t[0] for t in curr_pairs)

        to_add = new_types - curr_types
        to_remove = curr_types - new_types
        to_update = set(t[0] for t in (new_pairs - curr_pairs)) - to_add

        logger.info('%s changes for entity_id=%d, add=%r, update=%r, '
                    'remove=%r', self.name, entity_id,
                    pretty_const(to_add), pretty_const(to_update),
                    pretty_const(to_remove))

        self.apply_changes(entity, dict(new_pairs),
                           to_add, to_update, to_remove)
        return (to_add, to_update, to_remove)


class PersonNameSync(_KeyValueSync):
    """
    Callable to update names for a person.

    Note that PersonName typically includes name_variants that aren't actually
    person names.  You would typically want to use affect_types to restrict
    this sync class to a subset of valid PersonName types.

    See _KeyValueSync.__init__ for details.
    """

    name = 'person name'
    type_cls = Constants._PersonNameCode

    def fetch_current(self, entity):
        for row in entity.get_names(source_system=self.source_system):
            yield (row['name_variant'], row['name'])

    def apply_changes(self, entity, values, to_add, to_update, to_remove):
        changes = (to_add | to_remove | to_update)
        if not changes:
            return

        entity.affect_names(self.source_system, *changes)
        for name_type in (to_add | to_update):
            entity.populate_name(name_type, values[name_type])
        entity.write_db()


class ExternalIdSync(_KeyValueSync):
    """ Callable to update external ids for an entity. """

    name = 'external id'
    type_cls = Constants._EntityExternalIdCode

    def fetch_current(self, entity):
        for row in entity.get_external_id(source_system=self.source_system):
            yield (row['id_type'], row['external_id'])

    def apply_changes(self, entity, values, to_add, to_update, to_remove):
        changes = (to_add | to_remove | to_update)
        if not changes:
            return

        # TODO/TBD: We should probably check and warn if there are any
        # external ids of the *same type* but with a *different value* from
        # other source systems.  E.g. a entity has two different NO_BIRTHNO
        # values from two different systems.
        entity.affect_external_id(self.source_system, *changes)
        for id_type, id_value in values.items():
            entity.populate_external_id(self.source_system, id_type, id_value)
        entity.write_db()


class ContactInfoSync(_KeyValueSync):
    """ Callable to update contact info for an entity. """

    name = 'contact info'
    type_cls = Constants._ContactInfoCode

    def fetch_current(self, entity):
        for row in entity.get_contact_info(source=self.source_system):
            yield (row['contact_type'], row['contact_value'])

    def apply_changes(self, entity, values, to_add, to_update, to_remove):
        changes = (to_add | to_remove | to_update)
        if not changes:
            return

        # populate_contact_info() is not suitable here, as we don't care about
        # contact_pref in a simple key/value sync.  A very different sync class
        # is needed to support multiple, different values for each type.
        for ctype in (to_remove | to_update):
            entity.delete_contact_info(source=self.source_system,
                                       contact_type=ctype)
        for ctype in (to_update | to_add):
            entity.add_contact_info(source=self.source_system,
                                    type=ctype,
                                    value=values[ctype])


class AffiliationSync(_SourceSystemSync):
    """ Callable to update affiliations info for a person. """

    name = 'affiliation'

    def __call__(self, person_obj, aff_tuples):
        """
        Update affiliations for a given person.

        :type person_obj: Cerebrum.Person.Person
        :param aff_tuples:
            A sequence of (aff_status, ou_id) pairs.

            The sequence should be the current values from the given source
            system.
        """
        person_id = int(person_obj.entity_id)
        debug_log.debug('%s(%d, %s)', repr(self), person_id, repr(aff_tuples))

        new_affiliations = set()
        for aff_value, ou_id in aff_tuples:
            aff, status = self.const.get_affiliation(aff_value)
            if status is None:
                raise ValueError('invalid affiliation/status: '
                                 + repr(aff_value))

            try:
                ou = Factory.get('OU')(self.db)
                ou.find(int(ou_id))
            except (ValueError, Errors.NotFoundError):
                raise ValueError('invalid ou_id: ' + repr(ou_id))

            new_affiliations.add((ou_id, aff, status))
        logger.debug('%s(%d, <%s>)', repr(self), person_id,
                     pretty_const(tuple(t[2] for t in new_affiliations)))

        curr_affiliations = set()
        for row in person_obj.list_affiliations(
                person_id=person_id,
                source_system=self.source_system):
            ou_id = row['ou_id']
            aff = self.const.PersonAffiliation(row['affiliation'])
            status = self.const.PersonAffStatus(row['status'])
            curr_affiliations.add((ou_id, aff, status))

        to_add = new_affiliations - curr_affiliations
        to_update = new_affiliations & curr_affiliations
        to_remove = curr_affiliations - new_affiliations

        # populate_affiliation() is not suitable here, as we don't have a way
        # to delete *all* affiliations (if we never call
        # populate_affiliation(), no affiliations are removed)
        for ou_id, aff, status in to_remove:
            person_obj.delete_affiliation(ou_id, aff, self.source_system)
            logger.info('removed affiliation for person_id=%d: %s @ ou_id=%d',
                        person_id, status, ou_id)

        for ou_id, aff, status in new_affiliations:
            person_obj.add_affiliation(ou_id, aff, self.source_system, status)
            if (ou_id, aff, status) in to_add:
                logger.info('added affiliation for person_id=%d: %s @ '
                            'ou_id=%d', person_id, status, ou_id)
            else:
                logger.info('renewed affiliation for person_id=%d: %s @ '
                            'ou_id=%d', person_id, status, ou_id)

        return (to_add, to_update, to_remove)


class AddressSync(_KeyValueSync):
    """
    Callable to update address info for an entity.

    Similar to other key/value syncs, like ContactInfoSync, but note that the
    *value* is a dict-like object with entity_address columns (and valid
    arguments for ``EntityAddress.add_entity_address()``).
    """

    name = 'address'
    type_cls = Constants._AddressCode

    def __normalize_addr(self, addr_dict):
        """ Normalize an address dict.

        Since address dicts are un-hashable, we need to make them into a
        tuple, for comparing in sets.
        """
        country = addr_dict.get('country') or None
        if country:
            country = self.const.get_constant(self.const._CountryCode,
                                              country)
        return (
            ('address_text', addr_dict.get('address_text')),
            ('p_o_box', addr_dict.get('p_o_box')),
            ('postal_number', addr_dict.get('postal_number')),
            ('city', addr_dict.get('city')),
            ('country', country),
        )

    def __call__(self, entity, pairs):
        # normalize values
        pairs = tuple(
            (addr_type, self.__normalize_addr(addr_value))
            for addr_type, addr_value in pairs
        )
        return super(AddressSync, self).__call__(entity, pairs)

    def fetch_current(self, entity):
        for row in entity.get_entity_address(source=self.source_system):
            addr_t = self.__normalize_addr(dict(row))
            yield (row['address_type'], addr_t)

    def apply_changes(self, entity, values, to_add, to_update, to_remove):
        changes = (to_add | to_remove | to_update)
        if not changes:
            return

        for address_type in (to_remove | to_update):
            entity.delete_entity_address(source_type=self.source_system,
                                         a_type=address_type)

        for address_type in (to_update | to_add):
            addr_info = dict(values[address_type])
            entity.add_entity_address(source=self.source_system,
                                      type=address_type,
                                      **addr_info)


class NameLanguageSync(_BaseSync):
    """
    Callable to update localized names for an entity.

    Updates EntityNameWithLanguage entities with localized names.  This is
    similar to the _KeyValueSync, but the key is a combination of
    (_EntityNameCode, _LanguageCode).

    Note that EntityNameWithLanguage doesn't store values per source system -
    you would almost always want to set affect_types when using this class.
    """

    name = 'localized name'

    def __init__(self, db, affect_types=None):
        """
        :param affect_types: A sequence of _EntityNameCode types to affect.
        """
        super(NameLanguageSync, self).__init__(db)
        if affect_types:
            self.affect_types = tuple(self.get_type(t) for t in affect_types)
        else:
            self.affect_types = None

    def get_type(self, value):
        return self.const.get_constant(Constants._EntityNameCode, value)

    def get_subtype(self, value):
        return self.const.get_constant(Constants._LanguageCode, value)

    def fetch_current(self, entity):
        for row in entity.search_name_with_language(
                entity_id=int(entity.entity_id)):
            yield (row['name_variant'], row['name_language'], row['name'])

    def __call__(self, entity, triplets):
        """ Sync localized name triplets.

        :param entity:
            An Entity object to sync

        :param triplets:
            A sequence of triplets to sync

            The sequence should be the current (_EntityNameCode, _LanguageCode,
            name) values to set.
        """
        entity_id = int(entity.entity_id)
        debug_log.debug('%s(%d, %s)', repr(self), entity_id, repr(triplets))

        new_pairs = set(
            (self.get_type(key), self.get_subtype(subkey), value)
            for key, subkey, value in triplets)
        new_types = set(t[:2] for t in new_pairs)
        logger.debug('%s(%d, <%s>)', repr(self), entity_id,
                     pretty_const_pairs(new_types))
        if len(new_types) != len(new_pairs):
            raise ValueError('duplicate %s type given' % (self.name,))

        if self.affect_types is not None:
            invalid_types = set(t for t in new_types
                                if t[0] not in self.affect_types)
            if invalid_types:
                raise ValueError('invalid %s types: %s (must be one of %s)'
                                 % (self.name,
                                    pretty_const_pairs(invalid_types),
                                    pretty_const(self.affect_types)))

        curr_pairs = set((self.get_type(key), self.get_subtype(subkey), value)
                         for key, subkey, value in self.fetch_current(entity)
                         if self.affect_types is None
                         or key in self.affect_types)
        curr_types = set(t[:2] for t in curr_pairs)

        to_add = new_types - curr_types
        to_remove = curr_types - new_types
        to_update = set(t[:2] for t in (new_pairs - curr_pairs)) - to_add

        logger.info('%s changes for entity_id=%d, add=%r, update=%r, '
                    'remove=%r', self.name, entity_id,
                    pretty_const_pairs(to_add),
                    pretty_const_pairs(to_update),
                    pretty_const_pairs(to_remove))

        values = {t[:2]: t[2] for t in new_pairs}
        self.apply_changes(entity, values,
                           to_add, to_update, to_remove)
        return (to_add, to_update, to_remove)

    def apply_changes(self, entity, values, to_add, to_update, to_remove):
        changes = (to_add | to_remove | to_update)
        if not changes:
            return

        # populate_contact_info() is not suitable here, as we don't care about
        # contact_pref in a simple key/value sync.  A very different sync class
        # is needed to support multiple, different values for each type.
        for name_type, name_lang in to_remove:
            entity.delete_name_with_language(name_variant=name_type,
                                             name_language=name_lang)

        for name_type, name_lang in (to_update | to_add):
            name_value = values[name_type, name_lang]
            entity.add_name_with_language(name_variant=name_type,
                                          name_language=name_lang,
                                          name=name_value)

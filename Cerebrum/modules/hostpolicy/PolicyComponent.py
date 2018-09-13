#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011, 2012 University of Oslo, Norway
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
This module handles all functionality related to 'roles' and 'atoms', as used
in Cfengine-configuration.
"""

import re

from Cerebrum import Errors
from Cerebrum.Utils import Factory, prepare_string, argument_to_sql
from Cerebrum.Entity import EntityName

Entity_class = Factory.get("Entity")


class PolicyComponent(EntityName, Entity_class):
    """Base class for policy component, i.e. roles and atoms."""

    __read_attr__ = ('__in_db', 'created_at')
    __write_attr__ = ('component_name', 'description', 'foundation',
                      'foundation_date')

    def __init__(self, db):
        super(PolicyComponent, self).__init__(db)

    def clear(self):
        """Clear all data residing in this component instance."""
        self.__super.clear()
        self.clear_class(PolicyComponent)
        self.__updated = []

    def populate(self, entity_type, component_name, description, foundation,
                 foundation_date=None):
        """Populate a component instance's attributes."""
        Entity_class.populate(self, entity_type)
        # If __in_db is present, it must be True; calling populate on an
        # object where __in_db is present and False is very likely a
        # programming error.
        #
        # If __in_db is not present, we'll set it to False.
        try:
            if not self.__in_db:
                raise RuntimeError("populate() called multiple times.")
        except AttributeError:
            self.__in_db = False

        self.entity_type = entity_type
        self.component_name = component_name
        self.description = description
        self.foundation = foundation
        if not self.__in_db or foundation_date is not None:
            self.foundation_date = foundation_date

    def write_db(self):
        """Write component instance to database.

        If this instance has a ``entity_id`` attribute (inherited from
        class Entity), this Component entity is already present in the
        Cerebrum database, and we'll use UPDATE to bring the instance
        in sync with the database.

        Otherwise, a new entity_id is generated and used to insert
        this object.
        """
        self.__super.write_db()
        if not self.__updated:
            return

        # validate data
        if 'component_name' in self.__updated:
            tmp = self.illegal_name(self.component_name)
            if tmp:
                raise self._db.IntegrityError(
                    "Illegal component name: %s" % tmp)
        if 'description' in self.__updated:
            tmp = self.illegal_attr(self.description)
            if tmp:
                raise self._db.IntegrityError("Illegal description: %s" % tmp)
        if 'foundation' in self.__updated:
            tmp = self.illegal_attr(self.foundation)
            if tmp:
                raise self._db.IntegrityError("Illegal foundation: %s" % tmp)

        is_new = not self.__in_db

        if is_new:
            if self.entity_type == self.const.entity_hostpolicy_atom:
                event = self.clconst.hostpolicy_atom_create
            elif self.entity_type == self.const.entity_hostpolicy_role:
                event = self.clconst.hostpolicy_role_create
            else:
                raise RuntimeError('Unknown entity_type=%s for entity_id=%s' %
                                   (self.entity_type, self.entity_id))
            cols = [('entity_type', ':e_type'),
                    ('component_id', ':component_id'),
                    ('description', ':description'),
                    ('foundation', ':foundation'), ]
            if self.foundation_date is not None:
                cols.append(('foundation_date', ':foundation_date'))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=hostpolicy_component]
                (%(tcols)s)
            VALUES (%(binds)s)""" % {'tcols': ", ".join([x[0] for x in cols]),
                                     'binds': ", ".join([x[1] for x in cols])},
                                    {'e_type': int(self.entity_type),
                                     'component_id': self.entity_id,
                                     'description': self.description,
                                     'foundation': self.foundation,
                                     'foundation_date': self.foundation_date})
            self._db.log_change(self.entity_id, event, None)
            self.add_entity_name(self.const.hostpolicy_component_namespace,
                                 self.component_name)
        else:
            if self.entity_type == self.const.entity_hostpolicy_atom:
                event = self.clconst.hostpolicy_atom_mod
            elif self.entity_type == self.const.entity_hostpolicy_role:
                event = self.clconst.hostpolicy_role_mod
            else:
                raise RuntimeError('Unknown entity_type=%s for entity_id=%s' %
                                   (self.entity_type, self.entity_id))
            cols = [('description', ':description'),
                    ('foundation', ':foundation'), ]
            if self.foundation_date is not None:
                cols.append(('foundation_date', ':foundation_date'))
            self.execute("""
            UPDATE [:table schema=cerebrum name=hostpolicy_component]
            SET %(defs)s
            WHERE component_id=:component_id""" %
                         {'defs': ", ".join(["%s=%s" % x for x in cols])},
                         {'component_id': self.entity_id,
                          'description': self.description,
                          'foundation': self.foundation,
                          'foundation_date': self.foundation_date})
            self._db.log_change(
                self.entity_id, event, None, change_params={
                    'description': self.description,
                    'foundation': self.foundation,
                    'foundation_date': str(self.foundation_date),
                })
            if 'component_name' in self.__updated:
                self.update_entity_name(
                    self.const.hostpolicy_component_namespace,
                    self.component_name)
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def delete(self):
        """Deletes this policy component from DB."""
        if self.__in_db:
            # TODO: if component is in any relationship or is used as a policy,
            # what should be done?
            #
            #  1. raise exception self._db.IntegrityError
            #
            #  2. Delete the relationships and/or connection to host
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=hostpolicy_component]
            WHERE component_id=:component_id""",
                         {'component_id': self.entity_id})
            if self.entity_type == self.const.entity_hostpolicy_atom:
                event = self.clconst.hostpolicy_atom_delete
            elif self.entity_type == self.const.entity_hostpolicy_role:
                event = self.clconst.hostpolicy_role_delete
            else:
                raise RuntimeError(
                    "Unknown entity_type=%s for entity_id=%s" % (
                        self.entity_type, self.entity_id))
            self._db.log_change(self.entity_id, event, None)
        self.__super.delete()

    def find(self, component_id):
        """Fill this component instance with data from the database."""
        self.__super.find(component_id)
        (self.description, self.foundation,
         self.foundation_date, self.component_name) = self.query_1(
            """SELECT
                co.description, co.foundation,
                co.foundation_date, en.entity_name
            FROM
                [:table schema=cerebrum name=hostpolicy_component] co,
                [:table schema=cerebrum name=entity_name] en
            WHERE
                en.entity_id = co.component_id AND
                en.value_domain = :domain AND
                co.component_id = :component_id
            """, {'component_id': component_id,
                  'domain': self.const.hostpolicy_component_namespace, })
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        # drop changes, since we got them from db:
        self.__updated = []

    def find_by_name(self, component_name):
        self.__super.find_by_name(
            component_name, self.const.hostpolicy_component_namespace)

    def illegal_name(self, name):
        """Validate if a component's name is valid.

        According to the specification: only lowercase alpha numeric characters
        and dash ('-') is allowed."""
        if re.search('[^a-zA-Z0-9_]', name):
            return "name contains illegal characters (%s)" % name
        return False

    def illegal_attr(self, attribute, attr_type=None):
        """Validate if an attribute is valid.

        According to the specification can the attributes not contain semi
        colons."""
        if attribute.find(';') != -1:
            return "semi colons ';' not allowed"
        return False

    def illegal_date(self, date):
        """Check if a date is valid."""
        return 'feil feil'

    def add_to_host(self, dns_owner_id):
        """Add this instance as a policy to a given dns_owner_id (host)."""

        # TODO: check that mutex constraints are fullfilled!

        # TODO: other checks before executing the change?

        self.execute("""
            INSERT INTO [:table schema=cerebrum name=hostpolicy_host_policy]
              (dns_owner_id, policy_id)
            VALUES (:dns_owner, :policy_id)""",
                     {'dns_owner': int(dns_owner_id),
                      'policy_id': self.entity_id})
        self._db.log_change(dns_owner_id, self.clconst.hostpolicy_policy_add,
                            self.entity_id)

    def remove_from_host(self, dns_owner_id):
        """Remove this policy from a given dns_owner_id (host)."""
        # TODO: anything to check before executing the change?
        self.execute("""
            DELETE FROM [:table schema=cerebrum name=hostpolicy_host_policy]
            WHERE
                policy_id = :policy AND
                dns_owner_id = :dns_owner""",
                     {'policy': self.entity_id,
                      'dns_owner': dns_owner_id})
        self._db.log_change(dns_owner_id, self.clconst.hostpolicy_policy_remove,
                            self.entity_id)

    def search_hostpolicies(self, policy_id=None, policy_type=None,
                            dns_owner_id=None, host_name=None,
                            indirect_relations=False):
        """Search for hostpolicy relationships matching given criterias. By
        relationships we here mean policies "attached" to hosts.

        If a criteria is None, it will be ignored. Calling the method without
        any argument will simply return all hostpolicy relationships from the
        database.

        @type policy_id: int or a sequence of ints
        @param policy_id:
            The policy component IDs to search for. Only hostpolicies related
            to the given policies will be returned.

            Note that if indirect_relations is True, the given policies' parent
            policies are included in the search, since the given policies could
            be indirectly related to hosts through their parents.

        @type policy_type: int/EntityType or a sequence of ints/EntityTypes
        @param policy_type:
            Filter the result by policies type. Useful if you for instance only
            are interested in atoms and not roles.

        @type dns_owner_id: int or sequence of ints
        @param dns_owner_id:
            Filter the search to only return hostpolicies related to the given
            host IDs.

            Note that if indirect_relations is set to True, the hosts'
            policies' children are also searched through, since these are
            indirectly related to the given hosts.

        @type host_name: string
        @param host_name:
            A string for matching host's entity_name.

        @type indirect_relations: bool
        @param indirect_relations:
            If the search should find matches recursively. If this is True and
            policy_id is set, it will also search through the given policies'
            parents - useful for getting a list of hosts which has the given
            policy eiter as a direct or indirect policy. If dns_owner_id is
            given, it will search through the given host's policies and these
            policies' children - useful for getting a complete list of all
            policies attached to given hosts.

            TODO: can both policy id and dns_owner_id be given when searching
            indirectly?

        @rtype: generator of db-rows
        @return:
            A generator yielding successive db-rows. The keys for the db-rows
            are:

                - entity_type - The policy's entity type
                - policy_id
                - policy_name
                - dns_owner_id
                - dns_owner_name
        """
        where = ['co.component_id = hp.policy_id',
                 'hp.dns_owner_id = dnso.dns_owner_id',
                 'en1.entity_id = hp.dns_owner_id',
                 'en2.entity_id = hp.policy_id', ]
        binds = dict()

        if policy_id is not None:
            if indirect_relations:
                # Search recursively by just adding all policy_ids of policies
                # that contains the given policy_ids.

                if not isinstance(policy_id, (tuple, set, list)):
                    policy_id = (policy_id,)
                # making it a set to avoid searching for same policy twice
                policy_id = set(policy_id)

                policy_id.update(
                    row['source_id'] for row in self.search_relations(
                        target_id=policy_id,
                        relationship_code=self.const.hostpolicy_contains,
                        indirect_relations=True))
            where.append(
                argument_to_sql(policy_id, 'hp.policy_id', binds, int))
        if dns_owner_id is not None:
            if indirect_relations:
                # One way to do this is to fetch all the policies directly
                # attached to the given host(s), and then get their children.
                # How can this be given correctly?
                #
                # TODO: How to do this recursively?
                #
                raise Exception(
                    'Recursive search by host is not implemented yet')
            where.append(
                argument_to_sql(dns_owner_id, 'hp.dns_owner_id', binds, int))
        if host_name is not None:
            if indirect_relations:
                # TODO: How to do this recursively?
                raise Exception(
                    'Recursive search by host is not implemented yet')
            where.append('(LOWER(en1.entity_name) LIKE :host_name)')
            binds['host_name'] = prepare_string(host_name)
        if policy_type is not None:
            where.append(argument_to_sql(policy_type, 'co.entity_type', binds,
                                         int))
        return self.query("""
            SELECT DISTINCT
                co.entity_type AS entity_type,
                hp.dns_owner_id AS dns_owner_id,
                en1.entity_name AS dns_owner_name,
                en2.entity_name AS policy_name,
                hp.policy_id AS policy_id
            FROM
              [:table schema=cerebrum name=hostpolicy_component] co,
              [:table schema=cerebrum name=hostpolicy_host_policy] hp,
              [:table schema=cerebrum name=dns_owner] dnso,
              [:table schema=cerebrum name=entity_name] en1,
              [:table schema=cerebrum name=entity_name] en2
            WHERE
                %(where)s""" % {'where': ' AND '.join(where)}, binds)

    def search(self, entity_id=None, entity_type=None, description=None,
               name=None, create_start=None, create_end=None, foundation=None,
               foundation_start=None, foundation_end=None):
        """Search for components that satisfy given criteria.

        @type component_id: int or sequence of ints.
        @param component_id:
            Component ids to search for. If given, only the given components
            are returned.

        @type entity_type: int or sequence of ints.
        @param entity_type:
            If given, only components of the given type(s) are returned.

        @type description: basestring
        @param description:
            Filter the results by their description. May contain SQL wildcard
            characters.

        @type foundation: basestring
        @param foundation:
            Filter the results by their foundation variable. May contain SQL
            wildcard characters.

        @rtype: iterable db-rows
        @return:
            An iterable with db-rows with information about each component
            that matched the given criterias.
        """
        # TODO: add fetchall as an option?
        where = ['en.entity_id = co.component_id']
        where.append('ei.entity_id = co.component_id')
        binds = dict()

        # TODO: what about the namespace?

        if entity_type is not None:
            where.append(argument_to_sql(entity_type, 'co.entity_type',
                                         binds, int))
        if description is not None:
            where.append('(LOWER(co.description) LIKE :description)')
            binds['description'] = prepare_string(description)
        if foundation is not None:
            where.append('(LOWER(co.foundation) LIKE :foundation)')
            binds['foundation'] = prepare_string(foundation)
        if name is not None:
            where.append('(LOWER(en.entity_name) LIKE :name)')
            binds['name'] = prepare_string(name)
        if create_start is not None:
            where.append("(ei.created_at >= :create_start)")
            binds['create_start'] = create_start
        if create_end is not None:
            where.append("(ei.created_at <= :create_end)")
            binds['create_end'] = create_end
        if foundation_start is not None:
            where.append("(co.foundation_date >= :foundation_start)")
            binds['foundation_start'] = foundation_start
        if foundation_end is not None:
            where.append("(co.foundation_date <= :foundation_end)")
            binds['foundation_end'] = foundation_end
        return self.query("""
            SELECT DISTINCT co.entity_type AS entity_type,
                            co.component_id AS component_id,
                            co.description AS description,
                            co.foundation AS foundation,
                            ei.created_at AS created_at,
                            co.foundation_date AS foundation_date,
                            en.entity_name AS name
            FROM
              [:table schema=cerebrum name=hostpolicy_component] co,
              [:table schema=cerebrum name=entity_name] en,
              [:table schema=cerebrum name=entity_info] ei
            WHERE
              %(where)s
            """ % {'where': ' AND '.join(where)}, binds)

    def search_relations(self, source_id=None, target_id=None,
                         relationship_code=None, indirect_relations=False):
        """Search for relationships betweeen policies by different criterias.

        @type source_id: int or sequence of ints
        @param source_id:
            If given, all relations that has the given components as source
            are returned.

            If indirect_relations is True, all children (targets) of the given
            source_ids are returned.

        @type target_id: int or sequence of ints
        @param target_id:
            If given, all relations that has the given components as targets
            are returned.

            If indirect_relations is True, all parents (sources) of the given
            target_ids are returned.

        @type relationship_code: int or sequence of ints
        @param relationship_code:
            If given, only relations of the given type(s) are returned.

        @type indirect_relations: bool
        @param indirect_relations:
            If True, relationships will be search for recursively, either their
            parents or their children, depending on if source_id or target_id
            is given.

            Note that if indirect_relations is True and both source_id and
            target_id is specified, you will not necessarily get what you
            expect, since source and target are searched for individually. Try
            to avoid this usage.

        @rtype: iterable with db-rows
        @return:
            An iterator with db-rows with data about each relationship. The
            db-rows contain the elements:

              - source_id
              - source_entity_type
              - source_name
              - target_id
              - target_entity_type
              - target_name
              - relationship_id
              - relationship_str

        """
        # An effective helper function, copied from Cerebrum/Group.py
        def search_transitive_closure(start_id_set, searcher, field):
            """Collect the transitive closure of L{ids} by using the search
            strategy specified by L{searcher}. Relation loops are not
            a problem.

            L{searcher} is simply a tailored search-call which should not go
            recursively.

            L{field} is the key to extract from db-rows returned by the
            L{searcher}. Occasionally we need group_id and other times
            member_id. These are the two permissible values.
            """
            result = set()
            if isinstance(start_id_set, (tuple, set, list)):
                workset = set(start_id_set)
            else:
                workset = set((start_id_set,))
            while workset:
                new_set = set([x[field] for x in searcher(workset)])
                result.update(workset)
                workset = new_set.difference(result)
            return result
        # end search_transitive_closure

        binds = dict()
        tables = [
            '[:table schema=cerebrum name=hostpolicy_component] co1',
            '[:table schema=cerebrum name=hostpolicy_component] co2',
            '[:table schema=cerebrum name=entity_name] en1',
            '[:table schema=cerebrum name=entity_name] en2',
            '[:table schema=cerebrum name=hostpolicy_relationship] re',
            '[:table schema=cerebrum name=hostpolicy_relationship_code] rc']
        where = ['(re.relationship = rc.code)',
                 '(en1.entity_id = re.source_policy)',
                 '(en2.entity_id = re.target_policy)',
                 '(co1.component_id = re.source_policy)',
                 '(co2.component_id = re.target_policy)']
        if source_id is not None:
            if indirect_relations:
                source_id = search_transitive_closure(
                    source_id,
                    lambda ids: self.search_relations(
                        source_id=ids,
                        indirect_relations=False,
                        relationship_code=relationship_code),
                    'target_id')
            where.append(
                argument_to_sql(source_id, 're.source_policy', binds, int))
        if target_id is not None:
            if indirect_relations:
                target_id = search_transitive_closure(
                    target_id,
                    lambda ids: self.search_relations(
                        target_id=ids,
                        indirect_relations=False,
                        relationship_code=relationship_code),
                    'source_id')
            where.append(
                argument_to_sql(target_id, 're.target_policy', binds, int))
        if relationship_code is not None:
            where.append(
                argument_to_sql(
                    relationship_code, 're.relationship', binds, int))
        return self.query("""
            SELECT DISTINCT co1.entity_type AS source_entity_type,
                            co2.entity_type AS target_entity_type,
                            en1.entity_name AS source_name,
                            en2.entity_name AS target_name,
                            rc.code_str AS relationship_str,
                            re.source_policy AS source_id,
                            re.target_policy AS target_id,
                            re.relationship AS relationship_id
            FROM %(tables)s
            WHERE %(where)s
            """ % {'where': ' AND '.join(where),
                   'tables': ', '.join(tables)},
                binds)


class Role(PolicyComponent):
    """A PolicyComponent that is a Role. Roles can, in contrast to atoms, have
    members."""
    def populate(self, component_name, description, foundation,
                 foundation_date=None):
        self.__super.populate(
            self.const.entity_hostpolicy_role, component_name,
            description, foundation, foundation_date)

    def find_by_name(self, component_name):
        self.__super.find_by_name(component_name)
        if self.entity_type != self.const.entity_hostpolicy_role:
            self.clear()
            raise Errors.NotFoundError('Could not find role with name: %s' %
                                       component_name)

    def _illegal_membership_loop(self, source_id, member_id):
        """Check that the given member doesn't have the active role as a
        source, which would cause infinite loops. This does not affect atoms,
        since they can't have members."""
        for row in self.search_relations(
                source_id=member_id,
                relationship_code=self.const.hostpolicy_contains,
                indirect_relations=True):
            if row['target_id'] == source_id:
                return True
        return False

    def illegal_relationship(self, relationship_code, member_id):
        """Check if a new relationship is allowed, e.g. if all mutexes are okay,
        and that the member doesn't have the active role as a member (infinite
        loops)."""
        mem = Entity_class(self._db)
        mem.find(member_id)
        if (mem.entity_type == self.const.entity_hostpolicy_role and
                self._illegal_membership_loop(self.entity_id, member_id)):
                return True
        # TODO: mutex checks are not ready yet...
        return False

    def add_relationship(self, relationship_code, target_id):
        """Add a relationship of given type between this role and a target
        component (atom or role).

        @type relationship_code: int
        @param relationship_code:
            The relationship constant that defines the kind of relationship the
            source and target will have.
        """
        if self.illegal_relationship(relationship_code, target_id):
            # TODO: is ProgrammingError the correct exception to raise here?
            # Frontends should be able to give better feedbacks
            raise Errors.ProgrammingError('Illegal relationship')
        self.execute("""
            INSERT INTO [:table schema=cerebrum name=hostpolicy_relationship]
              (source_policy, relationship, target_policy)
            VALUES (:source, :rel, :target)""",
                     {'source': self.entity_id,
                      'rel': int(relationship_code),
                      'target': target_id})
        self._db.log_change(self.entity_id,
                            self.clconst.hostpolicy_relationship_add, target_id)

    def remove_relationship(self, relationship_code, target_id):
        """Remove a relationship of given type between this role and a target
        component (atom or role)."""
        # TODO: check that the relationship actually exists? Group.remove_member
        # doesn't do that, so don't know what's correcty for the API.
        self.execute("""
            DELETE FROM [:table schema=cerebrum name=hostpolicy_relationship]
            WHERE
                source_policy = :source AND
                target_policy = :target AND
                relationship  = :rel""", {'source': self.entity_id,
                                          'target': target_id,
                                          'rel': relationship_code})
        self._db.log_change(self.entity_id,
                            self.clconst.hostpolicy_relationship_remove,
                            target_id)

    def search(self, *args, **kwargs):
        """Sarch for roles by different criterias."""
        return self.__super.search(
            entity_type=self.const.entity_hostpolicy_role,
            *args, **kwargs)


class Atom(PolicyComponent):
    """A Component that is an Atom."""
    def populate(self, component_name, description, foundation,
                 foundation_date=None):
        self.__super.populate(
            self.const.entity_hostpolicy_atom, component_name,
            description, foundation, foundation_date)

    def find_by_name(self, component_name):
        self.__super.find_by_name(component_name)
        if self.entity_type != self.const.entity_hostpolicy_atom:
            self.clear()
            raise Errors.NotFoundError('Could not find atom with name: %s' %
                                       component_name)

    def search(self, *args, **kwargs):
        """Search for atoms by different criterias."""
        return self.__super.search(
            entity_type=self.const.entity_hostpolicy_atom,
            *args, **kwargs)


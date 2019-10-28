#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2005, 2013 University of Oslo, Norway
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
"""Module for handling information about a DNS host, e.g. a hardware box.

A host is connected to a DnsOnwer, and contains information like L{HINFO} and
L{TTL}.

HostInfo was previously referenced to as "mreg" at UiO. You should be aware of
this looking in the documentation.
"""

from Cerebrum.Entity import Entity
from Cerebrum.Utils import argument_to_sql
from Cerebrum.modules.dns.DnsOwner import DnsOwner


class HostInfo(Entity):
    """``HostInfo(Entity)`` is used to store information
    about machines in the dns_host_info table.  It uses the standard
    Cerebrum populate logic for handling updates.
    """

    __read_attr__ = ('__in_db', 'name')
    __write_attr__ = ('dns_owner_id', 'ttl', 'hinfo')

    # Note that CnameRecord, HostInfo and ARecord stores a name in the
    # class even though this information is stored in DnsOwner.  This
    # is only for convenience.  The value may not be updated.

    def clear(self):
        super(HostInfo, self).clear()
        self.clear_class(HostInfo)
        self.__updated = []

    def populate(self, dns_owner_id, hinfo, name=None, ttl=None, parent=None):
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity.populate(self, self.const.entity_dns_host)
        try:
            if not self.__in_db:
                raise RuntimeError("populate() called multiple times")
        except AttributeError:
            self.__in_db = False
        for k in locals().keys():
            if k != 'self':
                setattr(self, k, locals()[k])

    def __eq__(self, other):
        assert isinstance(other, HostInfo)
        if (
                self.primary_arecord != other.primary_arecord or
                self.hinfo != other.hinfo or
                self.ttl != other.ttl):
            return False
        return True

    def write_db(self):
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        if len(self.hinfo.split("\t")) != 2:
            raise ValueError("Illegal HINFO (missing tab)")
        binds = {'entity_type': int(self.const.entity_dns_host),
                 'host_id': self.entity_id,
                 'dns_owner_id': self.dns_owner_id,
                 'hinfo': self.hinfo,
                 'ttl': self.ttl}
        defs = {'tc': ', '.join(x for x in sorted(binds)),
                'tb': ', '.join(':{0}'.format(x) for x in sorted(binds)),
                'ts': ', '.join('{0}=:{0}'.format(x) for x in binds
                                if x != 'host_id')}
        if is_new:
            insert_stmt = """
            INSERT INTO [:table schema=cerebrum name=dns_host_info] (%(tc)s)
            VALUES (%(tb)s)""" % defs
            self.execute(insert_stmt, binds)
            self._db.log_change(self.entity_id,
                                self.clconst.host_info_add,
                                None,
                                change_params={'hinfo': self.hinfo})
        else:
            exists_stmt = """
              SELECT EXISTS (
                SELECT 1
                FROM [:table schema=cerebrum name=dns_host_info]
                WHERE (ttl is NULL AND :ttl is NULL OR ttl=:ttl) AND
                      (hinfo is NULL AND :hinfo is NULL OR hinfo=:hinfo) AND
                      host_id=:host_id AND
                      entity_type=:entity_type AND
                      dns_owner_id=:dns_owner_id
              )
            """ % defs
            if not self.query_1(exists_stmt, binds):
                update_stmt = """
                UPDATE [:table schema=cerebrum name=dns_host_info]
                SET %(ts)s
                WHERE host_id=:host_id""" % defs
                self.execute(update_stmt, binds)
                self._db.log_change(self.entity_id,
                                    self.clconst.host_info_update,
                                    None,
                                    change_params={'hinfo': self.hinfo})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, host_id):
        self.__super.find(host_id)
        (self.dns_owner_id, self.ttl, self.hinfo) = self.query_1("""
        SELECT dns_owner_id, ttl, hinfo
        FROM [:table schema=cerebrum name=dns_host_info]
        WHERE host_id=:host_id""", {'host_id': host_id})
        dns = DnsOwner(self._db)
        dns.find(self.dns_owner_id)
        self.name = dns.name
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def find_by_name(self, name):
        # Will result in a number of queries, but it is not expected
        # that find_by_name will be used in performance-intesive
        # queries.
        dns = DnsOwner(self._db)
        dns.find_by_name(name)
        self.find_by_dns_owner_id(dns.entity_id)

    def find_by_dns_owner_id(self, dns_owner_id):
        host_id = self.query_1("""
        SELECT host_id
        FROM [:table schema=cerebrum name=dns_host_info]
        WHERE dns_owner_id=:dns_owner_id""", {'dns_owner_id': dns_owner_id})
        self.find(host_id)

    def list(self, zone=None):
        where = ['hi.dns_owner_id=d.dns_owner_id']
        if zone is not None:
            where.append("d.zone_id=:zone")
            zone = int(zone)
        where = " AND ".join(where)
        return self.query("""
        SELECT host_id, hi.dns_owner_id, ttl, hinfo
        FROM [:table schema=cerebrum name=dns_host_info] hi,
             [:table schema=cerebrum name=dns_owner] d
        WHERE %s""" % where, {'zone': zone})

    def list_ext(self, dns_owner_id=None):
        return self.query("""
        SELECT host_id, dns_owner_id, ttl, hinfo
        FROM [:table schema=cerebrum name=dns_host_info]
        WHERE dns_owner_id=:dns_owner_id""", {'dns_owner_id': dns_owner_id})

    def _delete(self):
        """Deletion in host_info should be done through the DnsHelper
        class to avoid leaving entries in dns_owner that has no FKs to
        it"""
        binds = {'e_id': self.entity_id}
        exists_stmt = """
          SELECT EXISTS (
            SELECT 1
            FROM [:table schema=cerebrum name=dns_host_info]
            WHERE host_id=:e_id
          )
        """
        if self.query_1(exists_stmt, binds):
            # True positive
            stmt = """
            DELETE FROM [:table schema=cerebrum name=dns_host_info]
            WHERE host_id=:e_id"""
            self.execute(stmt, binds)
            self._db.log_change(self.entity_id,
                                self.clconst.host_info_del,
                                None)
        self.__super.delete()

    def search(self, spread=None, host_id=None, dns_owner_id=None,
               dns_owner_spread=None):
        """A search method for hosts.

        To be expanded in the future with more functionality when needed, e.g.
        to filter by zone_id(s) and name. Also DnsOwners has a an
        L{expire_date}, which we in some situations might want to filter by.

        @type spread: int or sequence thereof or None
        @param spread:
            If not None, only hosts with at least one of the given spreads will
            be returned.

        @type host_id: int or sequence thereof or None
        @param host_id:
            Filter the result by the given host_id(s).

        @type dns_owner_id: int or sequence thereof or None
        @param dns_owner_id:
            Filter the result by the given dns owner id(s).

        @type dns_owner_spread: int or sequence thereof or None
        @param dns_owner_spread:
            Filter the result by what spreads the dns owner has.

        @rtype: iterable (yielding db-rows with host information)
        @return:
            The search result, filtered by the given search criterias. Each
            yielded db row contains the keys:

                - host_id
                - dns_owner_id
                - name
                - ttl
                - hinfo
                - mx_set_id
                - zone_id

        """
        tables = []
        tables.append("[:table schema=cerebrum name=dns_host_info] hi")
        tables.append("[:table schema=cerebrum name=entity_name] en")
        tables.append("[:table schema=cerebrum name=dns_owner] dno")
        where = ['dno.dns_owner_id=hi.dns_owner_id',
                 'en.entity_id=dno.dns_owner_id']
        binds = dict()
        if spread is not None:
            tables.append("[:table schema=cerebrum name=entity_spread] es")
            where.append('es.entity_id=hi.host_id')
            where.append(argument_to_sql(spread, 'es.spread', binds, int))
        if dns_owner_spread is not None:
            tables.append("[:table schema=cerebrum name=entity_spread] es2")
            where.append('es2.entity_id=dno.dns_owner_id')
            where.append(argument_to_sql(spread, 'es2.spread', binds, int))
        if host_id is not None:
            where.append(argument_to_sql(host_id, 'dno.host_id', binds, int))
        if dns_owner_id is not None:
            where.append(argument_to_sql(dns_owner_id, 'dno.dns_owner_id',
                                         binds, int))
        where_str = " AND ".join(where)
        return self.query("""
        SELECT DISTINCT hi.host_id, hi.dns_owner_id, hi.ttl, hi.hinfo,
                        en.entity_name AS name, dno.mx_set_id, dno.zone_id
        FROM %s WHERE %s""" % (','.join(tables), where_str), binds)

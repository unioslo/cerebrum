# -*- coding: utf-8 -*-

from Cerebrum import Utils
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Entity import Entity, EntityName, EntitySpread
from Cerebrum.modules.dns.DnsConstants import _DnsZoneCode
from Cerebrum import Group


class MXSet(DatabaseAccessor):
    """``DnsOwner.MXSet(DatabaseAccessor)`` handles the dns_mx_set and
    dns_mx_set_members tables.  It uses the standard Cerebrum populate
    logic for handling updates."""

    __metaclass__ = Utils.mark_update

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('name', 'mx_set_id')

    def __init__(self, database):
        super(MXSet, self).__init__(database)
        self.clear()

    def clear_class(self, cls):
        for attr in cls.__read_attr__:
            if hasattr(self, attr):
                if attr not in getattr(cls, 'dontclear', ()):
                    delattr(self, attr)
        for attr in cls.__write_attr__:
            if attr not in getattr(cls, 'dontclear', ()):
                setattr(self, attr, None)

    def clear(self):
        self.clear_class(MXSet)
        self.__updated = []

    def populate(self, name):
        try:
            if not self.__in_db:
                raise RuntimeError("populate() called multiple times")
        except AttributeError:
            self.__in_db = False
        self.name = name

    def __eq__(self, other):
        assert isinstance(other, MXSet)
        return self.name == other.name

    def write_db(self):
        if not self.__updated:
            return None
        is_new = not self.__in_db
        if is_new:
            self.mx_set_id = int(self.nextval('ip_number_id_seq'))
        binds = {'mx_set_id': self.mx_set_id,
                 'name': self.name}
        if is_new:
            # Use same sequence as for ip-numbers for simplicity
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=dns_mx_set]
              (mx_set_id, name)
            VALUES (:mx_set_id, :name)""", binds)
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=dns_mx_set]
            SET name=:name
            WHERE mx_set_id=:mx_set_id""", binds)
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, mx_set_id):
        self.mx_set_id, self.name = self.query_1("""
        SELECT mx_set_id, name
        FROM [:table schema=cerebrum name=dns_mx_set]
        WHERE mx_set_id=:mx_set_id""", {'mx_set_id': mx_set_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def find_by_name(self, name):
        mx_set_id = self.query_1("""
        SELECT mx_set_id
        FROM [:table schema=cerebrum name=dns_mx_set]
        WHERE name=:name""", {'name': name})
        self.find(mx_set_id)

    def list(self):
        return self.query("""
        SELECT mx_set_id, name
        FROM [:table schema=cerebrum name=dns_mx_set]""")

    def list_mx_sets(self, mx_set_id=None, target_id=None):
        where = ['mxs.target_id=d.dns_owner_id',
                 'mxs.target_id=en.entity_id']
        if mx_set_id:
            where.append('mxs.mx_set_id=:mx_set_id')
        if target_id:
            where.append('target_id=:target_id')
        defs = {'where': ' AND '.join(where),
                'select': ', '.join(['mxs.mx_set_id', 'ttl', 'pri',
                                     'target_id',
                                     'en.entity_name AS target_name'])}
        binds = {'mx_set_id': mx_set_id,
                 'target_id': target_id}
        return self.query("""
        SELECT (%(select)s)
        FROM [:table schema=cerebrum name=dns_mx_set_member] mxs,
             [:table schema=cerebrum name=dns_owner] d,
             [:table schema=cerebrum name=entity_name] en
        WHERE (%(where)s)
        ORDER BY mxs.mx_set_id, pri, target_id""" % defs, binds)

    def add_mx_set_member(self, ttl, pri, target_id):
        binds = {'mx_set_id': self.mx_set_id,
                 'ttl': ttl,
                 'pri': pri,
                 'target_id': target_id}
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=dns_mx_set_member] (%s)
        VALUES (%s)""" % (", ".join(binds.keys()),
                          ", ".join([":%s" % k for k in binds])),
                     binds)

    def del_mx_set_member(self, target_id):
        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=dns_mx_set_member]
        WHERE mx_set_id=:mx_set_id AND target_id=:target_id""", {
            'mx_set_id': self.mx_set_id, 'target_id': target_id})

    def update_mx_set_member(self, ttl, pri, target_id):
        return self.execute("""
        UPDATE [:table schema=cerebrum name=dns_mx_set_member]
        SET ttl=:ttl, pri=:pri
        WHERE mx_set_id=:mx_set_id AND target_id=:target_id""", {
            'mx_set_id': self.mx_set_id, 'target_id': target_id,
            'ttl': ttl, 'pri': pri})

    def list_mx_set_dns_owner_members(self, mx_set_id=None, dns_owner_id=None):
        """List dns_owners and mx_sets defined in dns_owner."""
        where = ["mxs.mx_set_id=d.mx_set_id",
                 "d.dns_owner_id=en.entity_id"]
        if mx_set_id:
            where.append('mx_set_id=:mx_set_id')
        if dns_owner_id:
            where.append('dns_owner_id=:dns_owner_id')
        where = " AND ".join(where)
        return self.query("""
        SELECT mxs.mx_set_id, name, dns_owner_id, entity_name as host_name
        FROM [:table schema=cerebrum name=dns_mx_set] mxs,
             [:table schema=cerebrum name=dns_owner] d,
             [:table schema=cerebrum name=entity_name] en
        WHERE %s
        ORDER BY dns_owner_id, name""" % where, {
            'mx_set_id': mx_set_id,
            'dns_owner_id': dns_owner_id})

    def delete(self):
        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=dns_mx_set]
        WHERE mx_set_id=:mx_set_id""", {
            'mx_set_id': self.mx_set_id})


class GeneralDnsRecord(object):
    """``DnsOwner.GeneralDnsRecord(object)`` is a mix-in class for
    additional TTL-enabled data like TXT records."""

    def __fill_coldata(self, coldata):
        binds = coldata.copy()
        del binds['self']
        binds['field_type'] = int(binds['field_type'])
        cols = [("%s" % x, ":%s" % x) for x in binds.keys()]
        return cols, binds

    def get_general_dns_record(self, dns_owner_id, field_type):
        stmt = """
        SELECT ttl, data
        FROM [:table schema=cerebrum name=dns_general_dns_record]
        WHERE dns_owner_id=:dns_owner_id AND field_type=:field_type"""
        return self.query_1(stmt, locals())

    def add_general_dns_record(self, dns_owner_id, field_type, ttl, data):
        cols, binds = self.__fill_coldata(locals())
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=dns_general_dns_record]
        (%(tcols)s)
        VALUES (%(binds)s)""" % {'tcols': ", ".join([x[0] for x in cols]),
                                 'binds': ", ".join([x[1] for x in cols])},
                     binds)
        self._db.log_change(dns_owner_id, self.clconst.general_dns_record_add,
                            None, change_params={'field_type': int(field_type),
                                                 'data': data})

    def delete_general_dns_record(self, dns_owner_id, field_type):
        where = " AND ".join(['dns_owner_id=:dns_owner_id',
                              'field_type=:field_type'])
        exists_stmt = """
          SELECT EXISTS (
            SELECT 1
            FROM [:table schema=cerebrum name=dns_general_dns_record]
            WHERE  %s
          )
        """ % where
        if not self.query_1(exists_stmt, locals()):
            # False positive
            return
        delete_stmt = """
          DELETE FROM [:table schema=cerebrum name=dns_general_dns_record]
          WHERE  %s """ % where
        self.execute(delete_stmt, locals())
        self._db.log_change(dns_owner_id,
                            self.clconst.general_dns_record_del,
                            None,
                            change_params={'field_type': int(field_type)})

    def update_general_dns_record(self, dns_owner_id, field_type, ttl, data):
        cols, binds = self.__fill_coldata(locals())
        defs = {'set_defs': ", ".join(["%s=%s" % x for x in cols]),
                'where_defs': " AND ".join(["%s=%s" % x for x in cols])}
        exists_stmt = """
        SELECT EXISTS (
        SELECT 1
        FROM [:table schema=cerebrum name=dns_general_dns_record]
        WHERE dns_owner_id=:dns_owner_id AND
              field_type=:field_type AND
              %(where_defs)s
        )
        """ % defs
        if self.query_1(exists_stmt, binds):
            # False positive
            return
        update_stmt = """
        UPDATE [:table schema=cerebrum name=dns_general_dns_record]
        SET %(set_defs)s
        WHERE dns_owner_id=:dns_owner_id AND field_type=:field_type
        """ % defs
        self.execute(update_stmt, binds)
        self._db.log_change(dns_owner_id,
                            self.clconst.general_dns_record_update,
                            None,
                            change_params={'field_type': int(field_type),
                                           'data': data})

    def list_general_dns_records(self, field_type=None,
                                 dns_owner_id=None, zone=None):
        where = ['d.dns_owner_id=gdns.dns_owner_id']
        if field_type is not None:
            field_type = int(field_type)
            where.append("field_type=:field_type")
        if dns_owner_id is not None:
            where.append("gdns.dns_owner_id=:dns_owner_id")
        if zone is not None:
            where.append("d.zone_id=:zone")
            zone = int(zone)
        where = " AND ".join(where)
        return self.query("""
        SELECT gdns.dns_owner_id, gdns.field_type, gdns.ttl, gdns.data
        FROM [:table schema=cerebrum name=dns_general_dns_record] gdns,
             [:table schema=cerebrum name=dns_owner] d
        WHERE %s""" % where, locals())


Entity_class = Utils.Factory.get("Entity")


class DnsOwner(GeneralDnsRecord, EntityName, EntitySpread, Entity_class):
    """``DnsOwner(GeneralDnsRecord, Entity)`` primarily updates the
    DnsOwner table using the standard Cerebrum populate framework.

    The actual name of the machine is stored using EntityName.  Names
    are stored as fully-qualified, including the trailing dot, and all
    share the same namespace (const.dns_namespace).  This makes
    netgroup handling easier.

    The only purpose of the dns_zone table is to group which hosts
    should be included in the forward-map (in the reverse-map this is
    deduced from the ip-number).
    """

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('name', 'mx_set_id', 'zone')

    def clear(self):
        super(DnsOwner, self).clear()
        self.clear_class(DnsOwner)
        self.__updated = []

    def populate(self, zone, name, mx_set_id=None, parent=None):
        """zone may either be a number or a DnsZone constant"""
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity.populate(self, self.const.entity_dns_owner)
        try:
            if not self.__in_db:
                raise RuntimeError("populate() called multiple times")
        except AttributeError:
            self.__in_db = False
        self.name = name
        self.mx_set_id = mx_set_id
        self.zone = zone

    def __eq__(self, other):
        assert isinstance(other, DnsOwner)
        return (self.name == other.name and
                self.mx_set_id == other.mx_set_id)

    def write_db(self):
        self.__super.write_db()
        if not self.__updated:
            return None
        is_new = not self.__in_db
        binds = {
            'e_id': self.entity_id,
            'e_type': int(self.const.entity_dns_owner),
            'name': self.name,
            'mx_set_id': self.mx_set_id}
        # Do some primitive checks to assert that name is a FQDN, and
        # that the zone matches the DN.
        if not self.name[-1] == '.':
            raise ValueError("hostname must be fully qualified")
        if isinstance(self.zone, _DnsZoneCode):
            if (
                    self.zone.postfix is not None and
                    not self.name.endswith(self.zone.postfix)):
                raise ValueError("Zone mismatch for %s" % self.name)
            binds['zone_id'] = self.zone.zone_id
        else:
            binds['zone_id'] = self.zone
        if is_new:
            insert_stmt = """
            INSERT INTO [:table schema=cerebrum name=dns_owner]
              (dns_owner_id, entity_type, mx_set_id, zone_id)
            VALUES (:e_id, :e_type, :mx_set_id, :zone_id)"""
            self.execute(insert_stmt, binds)
            self.add_entity_name(self.const.dns_owner_namespace, self.name)
            self._db.log_change(self.entity_id,
                                self.clconst.dns_owner_add,
                                None)
        else:
            exists_stmt = """
              SELECT EXISTS (
                SELECT 1
                FROM [:table schema=cerebrum name=dns_owner]
                WHERE dns_owner_id=:e_id AND
                      mx_set_id=:mx_set_id AND
                      zone_id=:zone_id
              )
            """
            if not self.query_1(exists_stmt, binds):
                # True positive
                update_stmt = """
                  UPDATE [:table schema=cerebrum name=dns_owner]
                  SET mx_set_id=:mx_set_id, zone_id=:zone_id
                  WHERE dns_owner_id=:e_id"""
                self.execute(update_stmt, binds)
                if 'name' in self.__updated:
                    self.update_entity_name(self.const.dns_owner_namespace,
                                            self.name)
                self._db.log_change(self.entity_id,
                                    self.clconst.dns_owner_update,
                                    None)
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, host_id):
        self.__super.find(host_id)
        self.zone, self.mx_set_id = self.query_1("""
        SELECT zone_id, mx_set_id
        FROM [:table schema=cerebrum name=dns_owner]
        WHERE dns_owner_id=:e_id""", {'e_id': self.entity_id})
        self.name = self.get_name(self.const.dns_owner_namespace)
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def find_by_name(self, name):
        EntityName.find_by_name(self, name, self.const.dns_owner_namespace)

    def delete(self):
        for r in self.list_srv_records(owner_id=self.entity_id):
            self.delete_srv_record(
                r['service_owner_id'], r['pri'], r['weight'], r['port'])
        g = Group.Group(self._db)
        for row in g.search(member_id=self.entity_id, indirect_members=False):
            g.clear()
            g.find(row['group_id'])
            g.remove_member(self.entity_id)
        binds = {'dns_owner_id': self.entity_id}
        exists_stmt = """
          SELECT EXISTS (
            SELECT 1
            FROM [:table schema=cerebrum name=dns_owner]
            WHERE dns_owner_id=:dns_owner_id
          )
        """
        if self.query_1(exists_stmt, binds):
            # True positive
            delete_stmt = """
              DELETE FROM [:table schema=cerebrum name=dns_owner]
              WHERE dns_owner_id=:dns_owner_id"""
            self.execute(delete_stmt, binds)
            self._db.log_change(self.entity_id,
                                self.clconst.dns_owner_del,
                                None)
        self.__super.delete()

    def list(self, zone=None):
        return self.search(zone=zone)

    def search(self, name_like=None, zone=None, fetchall=False):
        """Search for owner"""
        where = ['d.dns_owner_id=en.entity_id']
        if name_like is not None:
            expr, name_like = self._db.sql_pattern("en.entity_name", name_like,
                                                   ref_name='name_like')
            where.append(expr)
        if zone is not None:
            where.append("d.zone_id=:zone")
            zone = int(zone)
        where = " AND ".join(where)
        return self.query("""
        SELECT d.dns_owner_id, d.mx_set_id, d.zone_id, en.entity_name AS name
        FROM [:table schema=cerebrum name=dns_owner] d,
             [:table schema=cerebrum name=entity_name] en
        WHERE %s""" % where, locals(), fetchall=fetchall)

    # TBD: Should we have the SRV methods in a separate class?  The
    # methods are currently not connected with the object in any way.

    def __fill_coldata(self, coldata):
        binds = coldata.copy()
        del binds['self']
        cols = [("%s" % x, ":%s" % x) for x in binds.keys()]
        return cols, binds

    def add_srv_record(self, service_owner_id, pri, weight, port, ttl,
                       target_owner_id):
        """add crv record"""
        cols, binds = self.__fill_coldata(locals())
        ret_value = self.execute("""
        INSERT INTO [:table schema=cerebrum name=dns_srv_record] (%(tcols)s)
        VALUES (%(binds)s)""" % {'tcols': ", ".join([x[0] for x in cols]),
                                 'binds': ", ".join([x[1] for x in cols])},
                                 binds)
        self._db.log_change(service_owner_id, self.clconst.srv_record_add,
                            target_owner_id)
        return ret_value

    def delete_srv_record(self, service_owner_id, pri, weight, port,
                          target_owner_id):
        """delete all srv records"""
        cols, binds = self.__fill_coldata(locals())
        where = " AND ".join(["%s=%s" % (x[0], x[1]) for x in cols])
        exists_stmt = """
        SELECT EXISTS (
        SELECT 1
        FROM [:table schema=cerebrum name=dns_srv_record]
        WHERE %s
        )
        """ % where
        if not self.query_1(exists_stmt, binds):
            # False positive
            return
        delete_stmt = """
        DELETE FROM [:table schema=cerebrum name=dns_srv_record]
        WHERE %s""" % where
        self.execute(delete_stmt, binds)
        self._db.log_change(service_owner_id,
                            self.clconst.srv_record_del,
                            target_owner_id)

    def list_srv_records(self, owner_id=None, target_owner_id=None, zone=None,
                         pri=None, weight=None, port=None):
        """List all srv records"""
        where = ['srv.target_owner_id=d_tgt.dns_owner_id',
                 'srv.service_owner_id=d_own.dns_owner_id',
                 'srv.target_owner_id=en_tgt.entity_id',
                 'srv.service_owner_id=en_own.entity_id']
        if owner_id is not None:
            where.append("service_owner_id=:owner_id")
        if target_owner_id is not None:
            where.append("target_owner_id=:target_owner_id")
        if zone is not None:
            where.append("d_own.zone_id=:zone")
            zone = int(zone)
        if pri is not None:
            where.append("srv.pri=:pri")
            pri = int(pri)
        if weight is not None:
            where.append("srv.weight=:weight")
            weight = int(weight)
        if port is not None:
            where.append("srv.port=:port")
            port = int(port)
        where = " AND ".join(where)
        return self.query("""
        SELECT service_owner_id, pri, weight, port, ttl,
               target_owner_id, en_tgt.entity_name AS target_name,
               en_own.entity_name AS service_name
        FROM [:table schema=cerebrum name=dns_srv_record] srv,
             [:table schema=cerebrum name=dns_owner] d_own,
             [:table schema=cerebrum name=dns_owner] d_tgt,
             [:table schema=cerebrum name=entity_name] en_own,
             [:table schema=cerebrum name=entity_name] en_tgt
        WHERE %s
        ORDER BY pri, weight, target_owner_id""" % where, {
            'owner_id': owner_id,
            'target_owner_id': target_owner_id,
            'zone': zone,
            'pri': pri,
            'weight': weight,
            'port': port})

    # We don't support a general update_srv_record as the PK is too wide.
    def update_srv_record_ttl(self, owner_id, ttl):
        """Update srv record (ttl only!)"""
        return self.execute("""
        UPDATE [:table schema=cerebrum name=dns_srv_record]
        SET ttl=:ttl
        WHERE service_owner_id=:owner_id""", {
            'owner_id': owner_id, 'ttl': ttl})

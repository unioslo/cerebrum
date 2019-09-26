# -*- coding: utf-8 -*-
from Cerebrum.Entity import Entity
from Cerebrum.modules.dns.DnsOwner import DnsOwner


class AAAARecord(Entity):
    """``AAAARecord(Entity)`` is used to store information
    about AAAA-records in the dns_a_record table.  It uses the standard
    Cerebrum populate logic for handling updates.

    It does not perform sany checks on the updates.  Use the Helper
    class for this.
    """
    __read_attr__ = ('__in_db', 'name')
    __write_attr__ = ('ip_number_id', 'ttl', 'mac', 'dns_owner_id')

    def clear(self):
        super(AAAARecord, self).clear()
        self.clear_class(AAAARecord)
        self.__updated = []

    def populate(self, dns_owner_id, ipv6_number_id, name=None,
                 ttl=None, mac=None, parent=None):
        """Set either dns_owner_id or name"""
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity.populate(self, self.const.entity_dns_aaaa_record)
        try:
            if not self.__in_db:
                raise RuntimeError("populate() called multiple times.")
        except AttributeError:
            self.__in_db = False
        for k in locals().keys():
            if k != 'self':
                setattr(self, k, locals()[k])

    def __eq__(self, other):
        assert isinstance(other, AAAARecord)
        if (
                self.dns_owner_id != other.dns_owner_id or
                self.ipv6_number_id != other.ipv6_number_id or
                self.ttl != other.ttl or
                self.mac != other.mac):
            return False
        return True

    def write_db(self):
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        binds = {'aaaa_record_id': self.entity_id,
                 'entity_type': int(self.const.entity_dns_aaaa_record),
                 'dns_owner_id': self.dns_owner_id,
                 'ipv6_number_id': self.ipv6_number_id,
                 'ttl': self.ttl,
                 'mac': self.mac}
        defs = {'tc': ', '.join(x for x in binds),
                'tb': ', '.join(':{0}'.format(x) for x in binds),
                'ts': ', '.join('{0}=:{0}'.format(x) for x in binds
                                if x != 'aaaa_record_id'),
                'tw': ' AND '.join('{0}=:{0}'.format(x) for x in binds)}
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=dns_aaaa_record] (%(tc)s)
            VALUES (%(tb)s)""" % defs, binds)
            self._db.log_change(self.dns_owner_id,
                                self.clconst.aaaa_record_add,
                                self.ipv6_number_id)
        else:
            exists_stmt = """
              SELECT EXISTS (
                SELECT 1
                FROM [:table schema=cerebrum name=dns_aaaa_record]
                WHERE %(tw)s
              )
            """ % defs
            if not self.query_1(exists_stmt, binds):
                # True positive
                execute_stmt = """
                  UPDATE [:table schema=cerebrum name=dns_aaaa_record]
                  SET %(ts)s
                  WHERE aaaa_record_id=:aaaa_record_id""" % defs
                self.execute(execute_stmt, binds)
                self._db.log_change(self.dns_owner_id,
                                    self.clconst.aaaa_record_update,
                                    self.ipv6_number_id)
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find_by_name(self, name):
        """Find DNS by owner's name"""
        # Will result in a number of queries, but it is not expected
        # that find_by_name will be used in performance-intesive
        # queries.
        dns = DnsOwner(self._db)
        dns.find_by_name(name)
        self.find_by_dns_owner_id(dns.entity_id)

    def find_by_dns_owner_id(self, dns_owner_id):
        """Find DNS by owner_id"""
        # May throw TooManyRows error, which callee should handle
        aaaa_record_id = self.query_1("""
        SELECT aaaa_record_id
        FROM [:table schema=cerebrum name=dns_aaaa_record]
        WHERE dns_owner_id=:dns_owner_id""", {'dns_owner_id': dns_owner_id})
        self.find(aaaa_record_id)

    def find_by_ip(self, ipv6_number_id):
        """Find DNS by IPv6"""
        # May throw TooManyRows error, which callee should handle
        aaaa_record_id = self.query_1("""
        SELECT aaaa_record_id
        FROM [:table schema=cerebrum name=dns_aaaa_record]
        WHERE ipv6_number_id=:ipv6_number_id""",
                                      {'ipv6_number_id': ipv6_number_id})
        self.find(aaaa_record_id)

    def find_by_owner_and_ip(self, ipv6_number_id, dns_owner_id):
        """Find DNS by owner_id and IPv6"""
        aaaa_record_id = self.query_1("""
        SELECT aaaa_record_id
        FROM [:table schema=cerebrum name=dns_aaaa_record]
        WHERE dns_owner_id=:dns_owner_id AND ipv6_number_id=:ipv6_number_id""",
                                      {'dns_owner_id': dns_owner_id,
                                       'ipv6_number_id': ipv6_number_id})
        self.find(aaaa_record_id)

    def find(self, aaaa_record_id):
        self.__super.find(aaaa_record_id)
        (self.ipv6_number_id,
         self.ttl, self.mac,
         self.dns_owner_id) = self.query_1("""
        SELECT ipv6_number_id, ttl, mac, dns_owner_id
        FROM [:table schema=cerebrum name=dns_aaaa_record]
        WHERE aaaa_record_id=:aaaa_record_id""",
                                           {'aaaa_record_id': aaaa_record_id})
        dns = DnsOwner(self._db)
        dns.find(self.dns_owner_id)
        self.name = dns.name
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def _delete(self):
        """Deletion of aaaa-records should be done through the
        IntegrityHelper to avoid leaving entries in ipv6_number that has
        no FKs to it"""
        binds = {'aaaa_record_id': self.entity_id}
        exists_stmt = """
          SELECT EXISTS (
          SELECT 1
          FROM [:table schema=cerebrum name=dns_aaaa_record]
          WHERE aaaa_record_id=:aaaa_record_id
        )
        """
        if self.query_1(exists_stmt, binds):
            # True positive
            delete_stmt = """
            DELETE FROM [:table schema=cerebrum name=dns_aaaa_record]
            WHERE aaaa_record_id=:aaaa_record_id"""
            self.execute(delete_stmt, binds)
            self._db.log_change(self.dns_owner_id,
                                self.clconst.aaaa_record_del,
                                self.ipv6_number_id)
        self.__super.delete()

    def list_ext(self, ip_number_id=None, dns_owner_id=None, start=None,
                 stop=None, zone=None):
        where = ['a.dns_owner_id=d.dns_owner_id',
                 'a.ipv6_number_id=i.ipv6_number_id',
                 'd.dns_owner_id=en.entity_id']
        if ip_number_id is not None:
            where.append("i.ipv6_number_id=:ipv6_number_id")
        if dns_owner_id is not None:
            where.append("d.dns_owner_id=:dns_owner_id")
        if zone is not None:
            where.append("d.zone_id=:zone")
            zone = int(zone)
        where = " AND ".join(where)
        return self.query("""
        SELECT a.aaaa_record_id, a.ipv6_number_id, i.aaaa_ip, a.ttl,
               a.mac, en.entity_name AS name, d.dns_owner_id, i.mac_adr
        FROM [:table schema=cerebrum name=dns_aaaa_record] a,
             [:table schema=cerebrum name=dns_ipv6_number] i,
             [:table schema=cerebrum name=dns_owner] d,
             [:table schema=cerebrum name=entity_name] en
        WHERE %s
        ORDER BY aaaa_record_id""" % where,
                          {'ipv6_number_id': ip_number_id,
                           'dns_owner_id': dns_owner_id,
                           'start': start, 'stop': stop,
                           'zone': zone})

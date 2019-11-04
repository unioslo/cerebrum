# -*- coding: utf-8 -*-
from Cerebrum.Entity import Entity
from Cerebrum.modules.dns.DnsOwner import DnsOwner


class ARecord(Entity):
    """``ARecord(Entity)`` is used to store information
    about A-records in the dns_a_record table.  It uses the standard
    Cerebrum populate logic for handling updates.

    It does not perform sany checks on the updates.  Use the Helper
    class for this.
    """
    __read_attr__ = ('__in_db', 'name')
    __write_attr__ = ('ip_number_id', 'ttl', 'mac', 'dns_owner_id')

    def clear(self):
        super(ARecord, self).clear()
        self.clear_class(ARecord)
        self.__updated = []

    def populate(self, dns_owner_id, ip_number_id, name=None,
                 ttl=None, mac=None, parent=None):
        """Set either dns_owner_id or name"""
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity.populate(self, self.const.entity_dns_a_record)
        try:
            if not self.__in_db:
                raise RuntimeError("populate() called multiple times.")
        except AttributeError:
            self.__in_db = False
        for k in locals().keys():
            if k != 'self':
                setattr(self, k, locals()[k])

    def __eq__(self, other):
        assert isinstance(other, ARecord)
        if (
                self.dns_owner_id != other.dns_owner_id or
                self.ip_number_id != other.ip_number_id or
                self.ttl != other.ttl or
                self.mac != other.mac):
            return False
        return True

    def write_db(self):
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        binds = {'a_record_id': self.entity_id,
                 'entity_type': int(self.const.entity_dns_a_record),
                 'dns_owner_id': self.dns_owner_id,
                 'ip_number_id': self.ip_number_id,
                 'ttl': self.ttl,
                 'mac': self.mac}
        defs = {'tc': ', '.join(x for x in sorted(binds)),
                'tb': ', '.join(':{0}'.format(x) for x in sorted(binds)),
                'ts': ', '.join('{0}=:{0}'.format(x) for x in binds
                                if x != 'a_record_id')}
        if is_new:
            insert_stmt = """
            INSERT INTO [:table schema=cerebrum name=dns_a_record] (%(tc)s)
            VALUES (%(tb)s)""" % defs
            self.execute(insert_stmt, binds)
            self._db.log_change(self.dns_owner_id, self.clconst.a_record_add,
                                self.ip_number_id)
        else:
            exists_stmt = """
              SELECT EXISTS (
                SELECT 1
                FROM [:table schema=cerebrum name=dns_a_record]
                WHERE a_record_id=:a_record_id AND
                      entity_type=:entity_type AND
                     (ttl is NULL AND :ttl is NULL OR ttl=:ttl) AND
                     (dns_owner_id is NULL AND :dns_owner_id is NULL OR
                       dns_owner_id=:dns_owner_id) AND
                     (ip_number_id is NULL AND :ip_number_id is NULL OR
                       ip_number_id=:ip_number_id) AND
                     (mac is NULL AND :mac is NULL OR
                       mac=:mac)
              )
            """
            if not self.query_1(exists_stmt, binds):
                # True positive
                update_stmt = """
                UPDATE [:table schema=cerebrum name=dns_a_record]
                SET %(ts)s
                WHERE a_record_id=:a_record_id""" % defs
                self.execute(update_stmt, binds)
                self._db.log_change(self.dns_owner_id,
                                    self.clconst.a_record_update,
                                    self.ip_number_id)
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find_by_name(self, name):
        # Will result in a number of queries, but it is not expected
        # that find_by_name will be used in performance-intesive
        # queries.
        dns = DnsOwner(self._db)
        dns.find_by_name(name)
        self.find_by_dns_owner_id(dns.entity_id)

    def find_by_dns_owner_id(self, dns_owner_id):
        # May throw TooManyRows error, which callee should handle
        a_record_id = self.query_1("""
        SELECT a_record_id
        FROM [:table schema=cerebrum name=dns_a_record]
        WHERE dns_owner_id=:dns_owner_id""", {'dns_owner_id': dns_owner_id})
        self.find(a_record_id)

    def find_by_ip(self, ip_number_id):
        # May throw TooManyRows error, which callee should handle
        a_record_id = self.query_1("""
        SELECT a_record_id
        FROM [:table schema=cerebrum name=dns_a_record]
        WHERE ip_number_id=:ip_number_id""", {'ip_number_id': ip_number_id})
        self.find(a_record_id)

    def find_by_owner_and_ip(self, ip_number_id, dns_owner_id):
        a_record_id = self.query_1("""
        SELECT a_record_id
        FROM [:table schema=cerebrum name=dns_a_record]
        WHERE dns_owner_id=:dns_owner_id AND ip_number_id=:ip_number_id""", {
            'dns_owner_id': dns_owner_id,
            'ip_number_id': ip_number_id})
        self.find(a_record_id)

    def find(self, a_record_id):
        self.__super.find(a_record_id)

        (self.ip_number_id,
         self.ttl,
         self.mac,
         self.dns_owner_id) = self.query_1("""
         SELECT ip_number_id, ttl, mac, dns_owner_id
         FROM [:table schema=cerebrum name=dns_a_record]
         WHERE a_record_id=:a_record_id""", {'a_record_id': a_record_id})
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
        """Deletion of a-records should be done through the
        IntegrityHelper to avoid leaving entries in ip_number that has
        no FKs to it"""
        binds = {'e_id': self.entity_id}
        exists_stmt = """
          SELECT EXISTS (
            SELECT 1
            FROM [:table schema=cerebrum name=dns_a_record]
            WHERE a_record_id=:e_id
          )
        """
        if not self.query_1(exists_stmt, binds):
            # False positive
            return
        delete_stmt = """
          DELETE FROM [:table schema=cerebrum name=dns_a_record]
          WHERE a_record_id=:e_id"""
        self.execute(delete_stmt, binds)
        self._db.log_change(self.dns_owner_id, self.clconst.a_record_del,
                            self.ip_number_id)
        self.__super.delete()

    def list_ext(self, ip_number_id=None, dns_owner_id=None, start=None,
                 stop=None, zone=None):
        """List out extended information about ARecords.

        @type ip_number_id: int
        @param ip_number_id: Limit the return to only the given IP number.

        @type dns_owner_id: int
        @param dns_owner_id: Limit the return to only the given dns owner's
            entity_id.

        @type start: int
        @param start:
            Limit the return to only IP numbers that are equal to or higher
            than the given start number. Note that the IP number is in this
            case considered in a 32-bit format and not as a string.

        @type stop: int
        @param stop:
            Limit the return to only IP numbers that are equal to or lower than
            the given stop number. Note that the IP number is in this case
            considered in a 32-bit format and not as a string.

        @type zone: int or DnsZoneCode
        @param zone: Limit the return to the given DNS zone.

        @rtype: list of db-rows
        @return: All ARecords that match the given criterias. Each db-row has
            the elements: a_record_id, ip_number_id, ttl, mac, the DNS owner's
            entity_name, and the IPNumber's a_ip, ipnr and mac_adr.

        """
        where = ['a.dns_owner_id=d.dns_owner_id',
                 'a.ip_number_id=i.ip_number_id',
                 'd.dns_owner_id=en.entity_id']
        if ip_number_id is not None:
            where.append("i.ip_number_id=:ip_number_id")
        if dns_owner_id is not None:
            where.append("d.dns_owner_id=:dns_owner_id")
        if start is not None:
            where.append("i.ipnr >= :start")
        if stop is not None:
            where.append("i.ipnr <= :stop")
        if zone is not None:
            where.append("d.zone_id=:zone")
            zone = int(zone)
        where = " AND ".join(where)
        return self.query("""
        SELECT a.a_record_id, a.ip_number_id, i.a_ip, i.ipnr, a.ttl,
               a.mac, en.entity_name AS name, d.dns_owner_id, i.mac_adr
        FROM [:table schema=cerebrum name=dns_a_record] a,
             [:table schema=cerebrum name=dns_ip_number] i,
             [:table schema=cerebrum name=dns_owner] d,
             [:table schema=cerebrum name=entity_name] en
        WHERE %s
        ORDER BY a_record_id""" % where, {
            'ip_number_id': ip_number_id,
            'dns_owner_id': dns_owner_id,
            'start': start, 'stop': stop,
            'zone': zone})

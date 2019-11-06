# -*- coding: utf-8 -*-

from Cerebrum.Entity import Entity
from Cerebrum.modules.dns.DnsOwner import DnsOwner


class CNameRecord(Entity):
    """``CNameRecord.CNameRecord(Entity)`` is used to
    store information about CName-records in the dns_cname_record
    table.  It uses the standard Cerebrum populate logic for handling
    updates.

    It does not perform sany checks on the updates.  Use the Helper
    class for this.
    """
    __read_attr__ = ('__in_db', 'name')
    __write_attr__ = ('cname_owner_id', 'ttl', 'target_owner_id')

    def clear(self):
        super(CNameRecord, self).clear()
        self.clear_class(CNameRecord)
        self.__updated = []

    def populate(self, cname_owner_id, target_owner_id, ttl=None,
                 parent=None):
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity.populate(self, self.const.entity_dns_cname)
        try:
            if not self.__in_db:
                raise RuntimeError("populate() called multiple times.")
        except AttributeError:
            self.__in_db = False
        for k in locals().keys():
            if k != 'self':
                setattr(self, k, locals()[k])

    def __eq__(self, other):
        assert isinstance(other, CNameRecord)
        if (
                self.cname_owner_id != other.cname_owner_id or
                self.ttl != other.ttl or
                self.target_owner_id != other.target_owner_id):
            return False
        return True

    def write_db(self):
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        binds = {'entity_type': int(self.const.entity_dns_cname),
                 'cname_id': self.entity_id,
                 'cname_owner_id': self.cname_owner_id,
                 'ttl': self.ttl,
                 'target_owner_id': self.target_owner_id}
        defs = {'tc': ', '.join(x for x in sorted(binds)),
                'tb': ', '.join(':{0}'.format(x) for x in sorted(binds)),
                'ts': ', '.join('{0}=:{0}'.format(x) for x in binds
                                if x != 'cname_id')}
        if is_new:
            insert_stmt = """
            INSERT INTO [:table schema=cerebrum name=dns_cname_record] (%(tc)s)
            VALUES (%(tb)s)""" % defs
            self.execute(insert_stmt, binds)
            self._db.log_change(self.cname_owner_id, self.clconst.cname_add,
                                self.target_owner_id)
        else:
            exists_stmt = """
              SELECT EXISTS (
                SELECT 1
                FROM [:table schema=cerebrum name=dns_cname_record]

                WHERE cname_id=:cname_id AND
                      entity_type=:entity_type AND
                     (ttl is NULL AND :ttl is NULL OR ttl=:ttl) AND
                     (cname_owner_id is NULL AND :cname_owner_id is NULL OR
                       cname_owner_id=:cname_owner_id) AND
                     (target_owner_id is NULL AND :target_owner_id is NULL OR
                       target_owner_id=:target_owner_id)
              )
            """
            if not self.query_1(exists_stmt, binds):
                # True positive
                update_stmt = """
                UPDATE [:table schema=cerebrum name=dns_cname_record]
                SET %(ts)s
                WHERE cname_id=:cname_id""" % defs
                self.execute(update_stmt, binds)
                self._db.log_change(self.cname_owner_id,
                                    self.clconst.cname_update,
                                    self.target_owner_id)
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, cname_id):
        """Find by cname_id"""
        self.__super.find(cname_id)
        (self.cname_owner_id,
         self.ttl,
         self.target_owner_id) = self.query_1("""
         SELECT cname_owner_id, ttl, target_owner_id
         FROM [:table schema=cerebrum name=dns_cname_record]
         WHERE cname_id=:cname_id""", {'cname_id': cname_id})
        dns = DnsOwner(self._db)
        dns.find(self.cname_owner_id)
        self.name = dns.name
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def find_by_name(self, name):
        """Find by name"""
        dns = DnsOwner(self._db)
        dns.find_by_name(name)
        self.find_by_cname_owner_id(dns.entity_id)

    def find_by_cname_owner_id(self, cname_owner_id):
        """Find by cname_owner_id"""
        cname_id = self.query_1("""
        SELECT cname_id
        FROM [:table schema=cerebrum name=dns_cname_record]
        WHERE cname_owner_id=:cname_owner_id""",
                                {'cname_owner_id': cname_owner_id})
        self.find(cname_id)

    def list_ext(self, target_owner=None, cname_owner=None, zone=None):
        where = ['c.cname_owner_id=d_own.dns_owner_id',
                 'c.target_owner_id=d_tgt.dns_owner_id',
                 'c.cname_owner_id=en_own.entity_id',
                 'c.target_owner_id=en_tgt.entity_id']
        if target_owner:
            where.append("c.target_owner_id=:target_owner_id")
        if cname_owner:
            where.append("c.cname_owner_id=:cname_owner_id")
        if zone is not None:
            where.append("d_own.zone_id=:zone")
            zone = int(zone)
        where = " AND ".join(where)
        return self.query("""
        SELECT c.cname_id, c.cname_owner_id, c.ttl, c.target_owner_id,
            en_own.entity_name AS name, en_tgt.entity_name AS target_name
        FROM [:table schema=cerebrum name=dns_cname_record] c,
             [:table schema=cerebrum name=dns_owner] d_own,
             [:table schema=cerebrum name=dns_owner] d_tgt,
             [:table schema=cerebrum name=entity_name] en_own,
             [:table schema=cerebrum name=entity_name] en_tgt
        WHERE %s ORDER BY en_own.entity_name""" % where, {
            'target_owner_id': target_owner,
            'cname_owner_id': cname_owner,
            'zone': zone})

    def _delete(self):
        """Deletion in cname_record should be done through the DnsHelper
        class to avoid leaving entries in dns_owner that has no FKs to
        it"""
        binds = {'e_id': self.entity_id}
        exists_stmt = """
          SELECT EXISTS (
            SELECT 1
            FROM [:table schema=cerebrum name=dns_cname_record]
            WHERE cname_id=:e_id
          )
        """
        if not self.query_1(exists_stmt, binds):
            # False positive
            return
        delete_stmt = """
          DELETE FROM [:table schema=cerebrum name=dns_cname_record]
          WHERE cname_id=:e_id
        """
        self.execute(delete_stmt, binds)
        self._db.log_change(self.cname_owner_id, self.clconst.cname_del,
                            self.target_owner_id)
        self.__super.delete()

# -*- coding: iso-8859-1 -*-

from Cerebrum.Entity import Entity
from Cerebrum.modules.dns.EntityNote import EntityNote
from Cerebrum.modules.dns.DnsOwner import DnsOwner

class CNameRecord(EntityNote, Entity):
    """``CNameRecord.CNameRecord(EntityNote, Entity)`` is used to
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
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        for k in locals().keys():
            if k != 'self':
                setattr(self, k, locals()[k])

    def __eq__(self, other):
        assert isinstance(other, CNameRecord)
        if (self.cname_owner_id != other.cname_owner_id or
            self.ttl != other.ttl or 
            self.target_owner_id != other.target_owner_id):
            return False
        return True

    def write_db(self):
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        cols = [('entity_type', ':e_type'),
                ('cname_id', ':e_id'),
                ('cname_owner_id', ':cname_owner_id'),
                ('ttl', ':ttl'),
                ('target_owner_id', ':target_owner_id')]
        binds = {'e_type' : int(self.const.entity_dns_cname),
                 'e_id': self.entity_id,
                 'cname_owner_id': self.cname_owner_id,
                 'ttl' : self.ttl,
                 'target_owner_id' : self.target_owner_id}
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=dns_cname_record] (%(tcols)s)
            VALUES (%(binds)s)""" % {'tcols': ", ".join([x[0] for x in cols]),
                                     'binds': ", ".join([x[1] for x in cols])},
                         binds)
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=dns_cname_record]
            SET %(defs)s
            WHERE cname_id=:e_id""" % {'defs': ", ".join(
                ["%s=%s" % x for x in cols])},
                         binds)
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, cname_id):
        self.__super.find(cname_id)
        (self.cname_owner_id, self.ttl, self.target_owner_id
         ) = self.query_1("""
        SELECT cname_owner_id, ttl, target_owner_id
        FROM [:table schema=cerebrum name=dns_cname_record]
        WHERE cname_id=:cname_id""", {'cname_id' : cname_id})
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
        dns = DnsOwner(self._db)
        dns.find_by_name(name)
        self.find_by_cname_owner_id(dns.entity_id)

    def find_by_cname_owner_id(self, cname_owner_id):
        cname_id = self.query_1("""
        SELECT cname_id
        FROM [:table schema=cerebrum name=dns_cname_record]
        WHERE cname_owner_id=:cname_owner_id""", {'cname_owner_id': cname_owner_id})
        self.find(cname_id)

    def list_ext(self, target_owner=None, cname_owner=None):
        where = ['c.cname_owner_id=d_own.dns_owner_id',
                 'c.target_owner_id=d_tgt.dns_owner_id',
                 'c.cname_owner_id=en_own.entity_id',
                 'c.target_owner_id=en_tgt.entity_id']
        if target_owner:
            where.append("c.target_owner_id=:target_owner_id")
        if cname_owner:
            where.append("c.cname_owner_id=:cname_owner_id")            
        where = " AND ".join(where)
        return self.query("""
        SELECT c.cname_id, c.cname_owner_id, c.ttl, c.target_owner_id,
            en_own.entity_name AS name, en_tgt.entity_name AS target_name
        FROM [:table schema=cerebrum name=dns_cname_record] c,
             [:table schema=cerebrum name=dns_owner] d_own,
             [:table schema=cerebrum name=dns_owner] d_tgt,
             [:table schema=cerebrum name=entity_name] en_own,
             [:table schema=cerebrum name=entity_name] en_tgt
        WHERE %s""" % where, {
               'target_owner_id': target_owner,
               'cname_owner_id': cname_owner} )

    def _delete(self):
        """Deletion in cname_record should be done through the DnsHelper
        class to avoid leaving entries in dns_owner that has no FKs to
        it"""
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=dns_cname_record]
        WHERE cname_id=:e_id""", {'e_id': self.entity_id})
        self.delete_entity_note()
        self.__super.delete()

# arch-tag: 1f20a221-a237-420b-b4b3-2e12be8a06ce

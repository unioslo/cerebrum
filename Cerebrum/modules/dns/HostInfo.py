# -*- coding: iso-8859-1 -*-

#from Cerebrum.DatabaseAccessor import DatabaseAccessor
#from Cerebrum import Utils
#from Cerebrum.Database import Errors
#from Cerebrum.Entity import Entity, EntityName
#import socket
#import string
#import struct

from Cerebrum.modules.dns.EntityNote import EntityNote
from Cerebrum.Entity import Entity

from Cerebrum.modules.dns.DnsOwner import DnsOwner


class HostInfo(EntityNote, Entity):
    """``HostInfo(EntityNote, Entity)`` is used to store information
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
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        hinfo = int(hinfo)
        for k in locals().keys():
            if k != 'self':
                setattr(self, k, locals()[k])

    def __eq__(self, other):
        assert isinstance(other, HostInfo)
        if (self.primary_arecord != other.primary_arecord or
            self.hinfo != other.hinfo or
            self.ttl != other.ttl):
            return False
        return True

    def write_db(self):
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db

        cols = [('entity_type', ':e_type'),
                ('host_id', ':e_id'),
                ('dns_owner_id', ':dns_owner_id'),
                ('ttl', ':ttl'),
                ('hinfo', ':hinfo')]
        binds = {'e_type' : int(self.const.entity_dns_host),
                 'e_id': self.entity_id,
                 'dns_owner_id': self.dns_owner_id,
                 'hinfo': int(self.hinfo),
                 'ttl' : self.ttl}
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=dns_host_info] (
               %(tcols)s) VALUES (%(binds)s)""" % {
                'tcols': ", ".join([x[0] for x in cols]),
                'binds': ", ".join([x[1] for x in cols])},
                         binds)
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=dns_host_info]
            SET %(defs)s
            WHERE host_id=:e_id""" % {'defs': ", ".join(
                ["%s=%s" % x for x in cols])},
                         binds)
        del self.__in_db
        
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, host_id):
        self.__super.find(host_id)

        (self.dns_owner_id, self.ttl, self.hinfo) = self.query_1("""
        SELECT dns_owner_id, ttl, hinfo
        FROM [:table schema=cerebrum name=dns_host_info]
        WHERE host_id=:host_id""", {'host_id' : host_id})
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

    def list(self):
        return self.query("""
        SELECT host_id, dns_owner_id, ttl, hinfo
        FROM [:table schema=cerebrum name=dns_host_info]""")

    def _delete(self):
        """Deletion in host_info should be done through the DnsHelper
        class to avoid leaving entries in dns_owner that has no FKs to
        it"""
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=dns_host_info]
        WHERE host_id=:e_id""", {'e_id': self.entity_id})
        self.delete_entity_note()
        self.__super.delete()

# arch-tag: f414513c-94a4-433f-942c-6b80222098c2

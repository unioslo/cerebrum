# -*- coding: iso-8859-1 -*-

import struct
import socket

from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum import Utils

class IPNumber(DatabaseAccessor):
    """``IPNumber.IPNumber(DatabaseAccessor)`` primarely updates the
    dns_ip_number table.  It also has methods for handling the
    reverse-map entries in dns_override_reversemap.  It uses the
    standard Cerebrum populate logic for handling updates."""

    __metaclass__ = Utils.mark_update

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('ip_number_id', 'a_ip', 'ipnr', 'aaaa_ip')

    def __init__(self, database):
        super(IPNumber, self).__init__(database)
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
        self.clear_class(IPNumber)
        self.__updated = []

    def populate(self, a_ip, aaaa_ip=None):
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        for k in locals().keys():
            if k != 'self':
                setattr(self, k, locals()[k])
        self.ipnr = struct.unpack(
            '!L', socket.inet_aton(a_ip))[0]

    def __eq__(self, other):
        assert isinstance(other, IPNumber)
        if (self.a_ip != other.a_ip or
            self.aaaa_ip != other.aaaa_ip):
            return False
        return True

    def write_db(self):
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.ip_number_id = int(self.nextval('ip_number_id_seq'))
        if 'a_ip' in self.__updated:  # numeric ipnr can only be calculated
            self.ipnr = struct.unpack(
                '!L', socket.inet_aton(self.a_ip))[0]

        cols = [('ip_number_id', ':ip_number_id'),
                ('a_ip', ':a_ip'),
                ('aaaa_ip', ':aaaa_ip'),
                ('ipnr', ':ipnr')]
        binds = {'ip_number_id': self.ip_number_id,
                 'a_ip': self.a_ip,
                 'aaaa_ip': self.aaaa_ip,
                 'ipnr': self.ipnr}

        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=dns_ip_number] (%(tcols)s)
            VALUES (%(binds)s)""" % {'tcols': ", ".join([x[0] for x in cols]),
                                     'binds': ", ".join([x[1] for x in cols])},
                         binds)
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=dns_ip_number]
            SET %(defs)s
            WHERE ip_number_id=:ip_number_id""" % {'defs': ", ".join(
                ["%s=%s" % x for x in cols])}, binds)
        del self.__in_db
        
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, ip_number_id):

        (self.ip_number_id, self.a_ip, self.aaaa_ip, self.ipnr
         ) = self.query_1("""
        SELECT ip_number_id, a_ip, ipnr, aaaa_ip
        FROM [:table schema=cerebrum name=dns_ip_number]
        WHERE ip_number_id=:ip_number_id""", {'ip_number_id' : ip_number_id})
        #self.hostname = self.get_name(self.const.hostname_namespace)
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def find_by_ip(self, a_ip):
        ip_number_id = self.query_1("""
        SELECT ip_number_id
        FROM [:table schema=cerebrum name=dns_ip_number]
        WHERE a_ip=:a_ip""", {'a_ip': a_ip})
        self.find(ip_number_id)

    def find_in_range(self, start, stop):
        return self.query("""
        SELECT ip_number_id, a_ip, ipnr, aaaa_ip
        FROM [:table schema=cerebrum name=dns_ip_number]
        WHERE ipnr >= :start AND ipnr <= :stop""", {
            'start': start,
            'stop': stop})

    def list(self):
        return self.query("""
        SELECT ip_number_id, a_ip, ipnr, aaaa_ip
        FROM [:table schema=cerebrum name=dns_ip_number]""")

    def delete(self):
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=dns_ip_number]
        WHERE ip_number_id=:ip_number_id""", {'ip_number_id': self.ip_number_id})

    # Now that the actual IP is no longer stored in the a_record
    # table, one might argue that the below methods should be moved to
    # another class

    def __fill_coldata(self, coldata):
        binds = coldata.copy()
        del(binds['self'])            
        cols = [ ("%s" % x, ":%s" % x) for x in binds.keys() ]
        return cols, binds

    def add_reverse_override(self, ip_number_id, dns_owner_id):
        cols, binds = self.__fill_coldata(locals())
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=dns_override_reversemap] (%(tcols)s)
        VALUES (%(binds)s)""" % {'tcols': ", ".join([x[0] for x in cols]),
                                 'binds': ", ".join([x[1] for x in cols])},
                     binds)

    def delete_reverse_override(self, ip_number_id=None):
        if not ip_number_id:
            ip_number_id = self.ip_number_id
        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=dns_override_reversemap]
        WHERE ip_number_id=:ip_number_id""", locals())

    def update_reverse_override(self, ip_number_id, dns_owner_id):
        self.execute("""
        UPDATE [:table schema=cerebrum name=dns_override_reversemap]
        SET dns_owner_id=:dns_owner_id
        WHERE ip_number_id=:ip_number_id""", locals())

    def list_override(self, ip_number_id=None):
        if ip_number_id:
            where = "WHERE ovr.ip_number_id=:ip_number_id"
        else:
            where = ''
        return self.query("""
        SELECT ovr.ip_number_id, ovr.dns_owner_id, d.name
        FROM [:table schema=cerebrum name=dns_override_reversemap] ovr
             LEFT JOIN [:table schema=cerebrum name=dns_owner] d ON
               ovr.dns_owner_id=d.dns_owner_id %s
        """ % where, {'ip_number_id': ip_number_id})

# arch-tag: 8f5892d4-5af8-45a7-acc1-92e91250cbf3

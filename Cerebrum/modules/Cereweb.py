# -*- coding: iso-8859-1 -*-
# Copyright 2009 University of Oslo, Norway
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


__version__ = "1.0"

from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.DatabaseAccessor import DatabaseAccessor

class CerewebMotd(DatabaseAccessor):
    __metaclass__ = Utils.mark_update
    __read_attr__ = ('__in_db', 'motd_id')
    __write_attr__ = ('create_date', 'creator', 'subject', 'message')


    def clear(self):
        self.clear_class(CerewebMotd)
        self.__updated = []

    def __init__(self, database):
        self.__super.__init__(database)
        self.clear()

    def clear_class(self, cls):
        for attr in cls.__read_attr__:
            if hasattr(self, attr):
                if attr not in getattr(cls, 'dontclear', ()):
                    delattr(self, attr)
        for attr in cls.__write_attr__:
            if attr not in getattr(cls, 'dontclear', ()):
                setattr(self, attr, None)

    def populate(self, creator, subject, message, create_date=None):
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        if not self.__in_db or create_date is not None:
            #only set create_date if explicitly set
            self.create_date = create_date
        self.creator = creator
        self.subject = subject
        self.message = message

    def find(self, motd_id):
        ( self.motd_id, self.create_date, self.creator,
          self.subject, self.message ) = self.query_1("""
        SELECT motd_id, create_date, creator, subject, message
        FROM [:table schema=cerebrum name=cereweb_motd]
        WHERE motd_id=:m_id""", {'m_id': motd_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    
    def write_db(self):
        if not self.__updated:
            return
        is_new = not self.__in_db
        cols=[('motd_id', ':motd_id'),
              ('creator', ':creator'),
              ('subject', ':subject'),
              ('message', ':message')]
        if self.create_date is not None:
            cols.append(('create_date', ':create_date'))
              
        if is_new:
            self.motd_id = int(self.nextval('cereweb_seq'))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=cereweb_motd]
              (%(tcols)s)
            VALUES (%(binds)s)""" % {'tcols': ", ".join([x[0] for x in cols]),
                                     'binds': ", ".join([x[1] for x in cols])},
                         { 'motd_id': self.motd_id,
                           'create_date': self.create_date,
                           'creator': self.creator,
                           'subject': self.subject,
                           'message': self.message })
            #self._db.log_change(self.motd_id, self.const.motd_add, None)
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=cereweb_motd]
            SET %(defs)s
            WHERE motd_id=:motd_id""" % {'defs': ", ".join(
                        ["%s=%s" % x for x in cols if x[0] != 'motd_id'])}, 
                         { 'motd_id': self.motd_id,
                           'create_date': self.create_date,
                           'creator': self.creator,
                           'subject': self.subject,
                           'message': self.message })
            #self._db.log_change(self.motd_id, self.const.motd_mod, None)

    def delete(self):
        if self.motd_id is None:
            raise Errors.NoEntityAssociationError("Unable to determine which motd entry to delete.")
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=cereweb_motd]
        WHERE motd_id = :motd_id""", {'motd_id': self.motd_id})
        #self._db.log_change(self.motd_id, self.const.motd_del, None
        self.clear()

    def list_motd(self):
        return self.query("""
        SELECT motd_id, create_date, creator, subject, message
        FROM [:table schema=cerebrum name=cereweb_motd]""")

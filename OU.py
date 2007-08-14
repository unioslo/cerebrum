# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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
UiT implementation of OU
"""
from Cerebrum import Utils
from Cerebrum import Errors

import cereconf
from Cerebrum.OU import OU
from Cerebrum.modules.no.uit.EntityExpire import EntityExpire
from Cerebrum.modules.no.uit.EntityExpire import EntityExpiredError


class OUEntityExpireMixin(EntityExpire, OU):
    """ 
    UiT override of OU. expired_before is added as an extra 
    parameter to the overriden methods in this file. The default
    behaviour is to exclude all entitites that are expired at the
    time of the query."""

    def find(self, ou_id, expired_before=None):
        """
        Overridden method. See L{OU} for functionality.
        
        @param expired_before: See L{EntityExpire.is_expired}.
       
        """

        # Find OU object
        self.__super.find(ou_id)
        
        # If the find doesn't fail, we can assume the OU is found and
        # already in memory. Now check if it's not expired!
        if self.is_expired(expired_before=expired_before):
            tmp_id = self.entity_id
            self.__super.clear()
            raise EntityExpiredError('Entity %s expired.' % tmp_id)
            
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    # Will only find non-expired OUs from non-expired parents
    def find_by_parent(self, acronym, perspective, parent_id, 
                                            expired_before=None):
        """
        Overridden method. See L{OU} for functionality.
        
        @param expired_before: See L{EntityExpire.is_expired}.
       
        """

        if self.is_expired(entity_id=parent_id, 
                           expired_before=expired_before):
           raise EntityExpiredError('Parent entity (%s) expired.' % 
                                                            parent_id)
    
        pid = "AND s.parent_id=:parent_id"
        if parent_id is None:
            pid = "AND s.parent_id IS NULL"
        ou_id = self.query_1("""
        SELECT o.ou_id
        FROM [:table schema=cerebrum name=ou_structure] s,
             [:table schema=cerebrum name=ou_info] o
        WHERE s.ou_id = o.ou_id AND s.perspective=:perspective
             %s AND o.acronym=:acronym""" % pid,
                                 {'perspective': int(perspective),
                                  'acronym': acronym,
                                  'parent_id': parent_id})
        self.find(ou_id, expired_before=expired_before)

    def get_parent(self, perspective, expired_before=None):
        """
        Overridden method. See L{OU} for functionality.
        
        @param expired_before: See L{EntityExpire.is_expired}.
       
        """
        
        parent_id = self.query_1("""
                SELECT parent_id
                FROM [:table schema=cerebrum name=ou_structure]
                WHERE ou_id=:ou_id AND  perspective=:perspective""",
                            {'ou_id': self.entity_id,
                             'perspective': int(perspective)})
            
        if self.is_expired(entity_id=parent_id, 
                           expired_before=expired_before):
           raise EntityExpiredError('Parent entity %s expired.' % 
                                                            parent_id)
        else:
          return parent_id

    def structure_path(self, perspective, expired_before=None):
        """
        Overridden method. See L{OU} for functionality.
        
        @param expired_before: See L{EntityExpire.is_expired}.
       
        """
        temp = self.__class__(self._db)
        temp.find(self.entity_id, expired_before)
        components = []
        visited = []
        while True:
            # Detect infinite loops
            if temp.entity_id in visited:
                raise RuntimeError, "DEBUG: Loop detected: %r" % visited
            visited.append(temp.entity_id)
            # Append this node's acronym (if it is non-NULL) to
            # 'components'.
            # TBD: Is this the correct way to handle NULL acronyms?
            if temp.acronym is not None:
                components.append(temp.acronym)
            # Find parent, end search if parent is either NULL or the
            # same node we're currently at.
            parent_id = temp.get_parent(perspective, expired_before)
            if (parent_id is None) or (parent_id == temp.entity_id):
                break
            temp.clear()
            temp.find(parent_id, expired_before)
        return "/".join(components)

 
    # Will only allow to set a non-expired parent
    def set_parent(self, perspective, parent_id, expired_before=None):
        """
        Overridden method. See L{OU} for functionality.
        
        @param expired_before: See L{EntityExpire.is_expired}.
       
        """
        
        if self.is_expired(entity_id=parent_id, 
                           expired_before=expired_before):
           raise EntityExpiredError('New parent entity (%s) is \
                                            expired.' % parent_id)
        
        try:
            # Doesnt't matter if old entity is expired!
            try:
              old_parent = self.get_parent(perspective, expired_before)
            except EntityExpire.EntityExpiredError:
              pass
              
            if old_parent == parent_id:
                # Don't need to change parent_id to the same parent_id
                return
            self.execute("""
            UPDATE [:table schema=cerebrum name=ou_structure]
            SET parent_id=:parent_id
            WHERE ou_id=:e_id AND perspective=:perspective""",
                      {'e_id': self.entity_id,
                      'perspective': int(perspective),
                      'parent_id': parent_id})
        except Errors.NotFoundError:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=ou_structure]
              (ou_id, perspective, parent_id)
            VALUES (:e_id, :perspective, :parent_id)""",
                         {'e_id': self.entity_id,
                          'perspective': int(perspective),
                          'parent_id': parent_id})
        self._db.log_change(self.entity_id, 
                            self.const.ou_set_parent,
                            parent_id,
                            change_program='set_parent',
                            change_params={
                                'perspective': int(perspective)})


    # Will only list non-expired children of non-expired entities
    def list_children(self, perspective, entity_id=None, 
                                recursive=False, expired_before=None):
        """
        Overridden method. See L{OU} for functionality.
        
        @param expired_before: See L{EntityExpire.is_expired}.
       
        """
                                
        if not entity_id:
            entity_id = self.entity_id
        else:
            if self.is_expired(entity_id=entity_id, 
                               expired_before=expired_before):
                raise EntityExpiredError('Entity %s expired.' %
                                                            entity_id)
        
        sql_expire = '(expire_date >= :expire_date OR \
                      expire_date IS NULL)'
        if expired_before is None:
            sql_expire = '(expire_date >= [:now] OR \
                          expire_date IS NULL)'
        
        ret = []
        tmp = self.query("""
        SELECT ou_id 
        FROM [:table schema=cerebrum name=ou_structure]
        LEFT JOIN [:table schema=cerebrum name=entity_expire] \
        ON entity_id = ou_id
        WHERE parent_id=:e_id AND perspective=:perspective AND %s""" %
                          sql_expire,
                          {'e_id': entity_id,
                           'perspective': int(perspective),
                           'expire_date': expired_before})
        ret.extend(tmp)
        if recursive:
            for r in tmp:
                ret.extend(self.list_children(perspective, r['ou_id'],
                                              recursive,expired_before))
        return ret

    # Will only list non-expired entities
    def list_all(self, filter_quarantined=False, expired_before=None):
    
        sql_expire = '(expire_date >= :expire_date OR \
                      expire_date IS NULL)'
        if expired_before is None:
            sql_expire = '(expire_date >= [:now] OR \
                          expire_date IS NULL)'    
    
        extra = "" 
        if filter_quarantined:
            extra = "NOT EXISTS (" \
                    " SELECT 'x' " \
                    " FROM [:table schema=cerebrum \
                                   name=entity_quarantine] eq" \
                    " WHERE oi.ou_id=eq.entity_id) AND "
        return self.query("""
        SELECT oi.ou_id, oi.name, oi.acronym 
        FROM [:table schema=cerebrum name=ou_info] oi
        LEFT JOIN [:table schema=cerebrum name=entity_expire] ee \
        ON ee.entity_id = oi.ou_id
        WHERE %s %s""" % (extra, sql_expire),
                          {'expire_date': expired_before,})

    def get_structure_mappings(self, perspective, expired_before=None):
        """
        Overridden method. See L{OU} for functionality.
        
        @param expired_before: See L{EntityExpire.is_expired}.
       
        """
        
        sql_expire1 = '(ee1.expire_date >= :expire_date OR \
                       ee1.expire_date IS NULL)'
        sql_expire2 = '(ee2.expire_date >= :expire_date OR \
                       ee2.expire_date IS NULL)'
        if expired_before is None:
            sql_expire1 = '(ee1.expire_date >= [:now] OR \
                           ee1.expire_date IS NULL)'
            sql_expire2 = '(ee2.expire_date >= [:now] OR \
                           ee2.expire_date IS NULL)'
            
        return self.query("""
            SELECT ou_id, parent_id
            FROM [:table schema=cerebrum name=ou_structure]
            LEFT JOIN [:table schema=cerebrum name=entity_expire] ee1 \
            ON ee1.entity_id = ou_id
            LEFT JOIN [:table schema=cerebrum name=entity_expire] ee2 \
            ON ee2.entity_id = parent_id
            WHERE perspective=:perspective AND %s AND %s""" % 
            (sql_expire1, sql_expire2), 
            {'perspective': int(perspective),
              'expire_date':expired_before})

    def root(self, expired_before=None):
        """
        Overridden method. See L{OU} for functionality.
        
        @param expired_before: See L{EntityExpire.is_expired}.
       
        """
        
        sql_expire = '(expire_date >= :expire_date OR \
                      expire_date IS NULL)'
        if expired_before is None:
            sql_expire = '(expire_date >= [:now] OR \
                          expire_date IS NULL)'
        
        return self.query("""
        SELECT ou_id
        FROM [:table schema=cerebrum name=ou_structure]
        LEFT JOIN [:table schema=cerebrum name=entity_expire] \
        ON entity_id = ou_id
        WHERE parent_id IS NULL AND %s""" % sql_expire,
        {'expire_date': expired_before,})

    def search(self, spread=None, name=None, acronym=None,
               short_name=None, display_name=None, sort_name=None,
               expired_before=None):
        """
        Overridden method. See L{OU} for functionality.
        
        @param expired_before: See L{EntityExpire.is_expired}.
       
        """
        
        def prepare_string(value):
            value = value.replace("*", "%")
            value = value.replace("?", "_")
            value = value.lower()
            return value

        tables = []
        where = []
        tables.append("""[:table schema=cerebrum name=ou_info] oi 
                        LEFT JOIN [:table schema=cerebrum \
                                          name=entity_expire] ee \
                        ON ee.entity_id = oi.ou_id""")
        
        if expired_before is None:
            where.append('(ee.expire_date >= [:now] OR \
                          ee.expire_date IS NULL)')
        else:
            where.append('(ee.expire_date >= :expire_date OR \
                          ee.expire_date IS NULL)')
            
        if spread is not None:
            tables.append("[:table schema=cerebrum \
                                   name=entity_spread] es")
            where.append("oi.ou_id=es.entity_id")
            where.append("es.entity_type=:entity_type")
            try:
                spread = int(spread)
            except (TypeError, ValueError):
                spread = prepare_string(spread)
                tables.append("[:table schema=cerebrum \
                                       name=spread_code] sc")
                where.append("es.spread=sc.code")
                where.append("LOWER(sc.code_str) LIKE :spread")
            else:
                where.append("es.spread=:spread")

        if name is not None:
            name = prepare_string(name)
            where.append("LOWER(oi.name) LIKE :name")

        if acronym is not None:
            acronym = prepare_string(acronym)
            where.append("LOWER(oi.acronym) LIKE :acronym")

        if short_name is not None:
            short_name = prepare_string(short_name)
            where.append("LOWER(oi.short_name) LIKE :short_name")

        if display_name is not None:
            display_name = prepare_string(display_name)
            where.append("LOWER(oi.display_name) LIKE :display_name")
        
        if sort_name is not None:
            sort_name = prepare_string(sort_name)
            where.append("LOWER(oi.sort_name) LIKE :sort_name")
            
        where_str = ""
        if where:
            where_str = "WHERE " + " AND ".join(where)

        return self.query("""
        SELECT DISTINCT oi.ou_id, oi.name, oi.acronym, oi.short_name,
                        oi.display_name, oi.sort_name
        FROM %s %s""" % (','.join(tables), where_str),
            {'spread': spread, 'entity_type': int(self.const.entity_ou),
             'name': name, 'acronym': acronym, 'short_name': short_name,
             'display_name': display_name, 'sort_name': sort_name, 
             'expire_date': expired_before})

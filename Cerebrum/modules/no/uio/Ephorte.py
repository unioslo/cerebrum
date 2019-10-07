0#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2007-2018 University of Oslo, Norway
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

from Cerebrum import Constants
from Cerebrum.Constants import _get_code
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Utils import Factory


@Constants._ChangeTypeCode.formatter('rolle_type')
def format_cl_role_type(co, val):
    return _get_code(co.EphorteRole, val)


@Constants._ChangeTypeCode.formatter('perm_type')
def format_cl_perm_type(co, val):
    return _get_code(co.EphortePermission, val)


##
# TBD: Bør denne klassen egentlig være en PersonMixin? Fordi alle
#      disse funksjonene er relative til personer. Da vil det være
#      lettere å få til følgende businesslogikk som nå er
#      implementert litt teit:
#
#        * hvis en person slettes skal dens ephorte-roller,
#          -tilganger og spreads automatisk fjernes
#        * hvis en person mister alle sine roller, skal også
#          tilganger og spread fjernes automatisk.
#        * Hvis en person får en ny rolle og personen ikke har noen
#          standardrolle skal den nye rollen settes som standardrolle

class EphorteRole(DatabaseAccessor):
    def __init__(self, database):
        super(EphorteRole, self).__init__(database)
        self.co = Factory.get('Constants')(database)
        self.clconst = Factory.get('CLConstants')(database)
        self.pe = Factory.get('Person')(database)
        self.ephorte_perm = EphortePermission(database)

    def _add_role(self, person_id, role, sko, arkivdel, journalenhet,
                  rolletittel='', stilling='', standard_role='F',
                  auto_role='T'):
        binds = {
            'person_id': person_id,
            'role_type': role,
            'standard_role': standard_role,
            'auto_role': auto_role,
            'adm_enhet': sko,
            'arkivdel': arkivdel,
            'journalenhet': journalenhet,
            'rolletittel': rolletittel,
            'stilling': stilling
        }
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=ephorte_role]
          (%s) VALUES (%s)""" % (", ".join(binds.keys()),
                                 ", ".join([":%s" % k for k in binds])),
                     binds)
        self._db.log_change(
            person_id, self.clconst.ephorte_role_add, sko,
            change_params={
                'arkivdel': arkivdel and str(arkivdel) or '',
                'rolle_type': str(role)
            })

    # Wrapper for _add_role.
    def add_role(self, person_id, role, sko, arkivdel, journalenhet,
                 rolletittel='', stilling='', standard_role='F',
                 auto_role='T'):
        # If person don't have any roles, set this role as standard_role
        if not self.list_roles(person_id=person_id):
            standard_role = 'T'
        self._add_role(person_id, role, sko, arkivdel, journalenhet,
                       rolletittel, stilling, standard_role, auto_role)

    def set_standard_role_val(self, person_id, role, sko, arkivdel,
                              journalenhet, standard_role):
        binds = {
            'person_id': person_id,
            'role_type': role,
            'adm_enhet': sko,
            'arkivdel': arkivdel,
            'journalenhet': journalenhet,
        }
        query = """
        UPDATE [:table schema=cerebrum name=ephorte_role]
        SET standard_role='%s'
        WHERE %s""" % (standard_role, " AND ".join(
            ["%s=:%s" % (x, x) for x in binds if binds[x]]))
        self.execute(query, binds)
        self._db.log_change(
            person_id, self.clconst.ephorte_role_upd, sko,
            change_params={'standard_role': standard_role})

    def _remove_role(self, person_id, role, sko, arkivdel, journalenhet):
        binds = {
            'person_id': person_id,
            'role_type': role,
            'adm_enhet': sko,
            'arkivdel': arkivdel,
            'journalenhet': journalenhet
        }
        exists_stmt = """
           SELECT EXISTS (
            SELECT 1
            FROM [:table schema=cerebrum name=ephorte_role]
            WHERE %s
          )
        """ % " AND ".join(
            ["%s=:%s" % (x, x) for x in binds if binds[x] is not None] +
            ["%s IS NULL" % x for x in binds if binds[x] is None])
        if not self.query_1(exists_stmt, binds):
            # False positive
            return
        delete_stmt = """
        DELETE FROM [:table schema=cerebrum name=ephorte_role]
        WHERE %s""" % " AND ".join(
            ["%s=:%s" % (x, x) for x in binds if binds[x] is not None] +
            ["%s IS NULL" % x for x in binds if binds[x] is None])
        self.execute(delete_stmt, binds)
        self._db.log_change(
            person_id, self.clconst.ephorte_role_rem, sko,
            change_params={
                'arkivdel': arkivdel and str(arkivdel) or '',
                'rolle_type': str(role)
            })

    # Wrapper for _remove_role.
    # This is a bit hackish, see the class comment for more info.
    def remove_role(self, person_id, role, sko, arkivdel, journalenhet):
        self._remove_role(person_id, role, sko, arkivdel, journalenhet)
        # If person doesn't have any roles left, any ephorte
        # permissions and the ephorte-spread should be removed
        if not self.list_roles(person_id=person_id):
            # This is ugly :(
            # Remove eny permissions before deleting ephorte spread
            for row in self.ephorte_perm.list_permission(person_id=person_id):
                self.ephorte_perm.remove_permission(row["person_id"],
                                                    row["perm_type"],
                                                    row["adm_enhet"])
            # Then remove spread
            self.pe.clear()
            self.pe.find(person_id)
            self.pe.delete_spread(self.co.spread_ephorte_person)

    def get_role(self, person_id, role, sko, arkivdel, journalenhet,
                 standard_role=False):
        binds = {
            'person_id': person_id,
            'role_type': role,
            'adm_enhet': sko,
            'arkivdel': arkivdel,
            'journalenhet': journalenhet
        }
        if standard_role:
            binds['standard_role'] = standard_role
        return self.query("""
        SELECT person_id, role_type, standard_role, adm_enhet,
               arkivdel, journalenhet, rolletittel, stilling,
               start_date, end_date, auto_role
        FROM [:table schema=cerebrum name=ephorte_role]
        WHERE %s""" % " AND ".join(
            ["%s=:%s" % (x, x) for x in binds if binds[x] is not None] +
            ["%s IS NULL" % x for x in binds if binds[x] is None]),
            binds)

    def list_roles(self, person_id=None, filter_expired=False):
        where = []
        if person_id:
            where.append("person_id=:person_id")
        if filter_expired:
            where.append("""(end_date IS NULL OR end_date > [:now])
                         AND (start_date IS NULL OR start_date <= [:now])""")
        if where:
            where = "WHERE %s" % " AND ".join(where)
        else:
            where = ""
        return self.query("""
        SELECT person_id, role_type, standard_role, adm_enhet,
               arkivdel, journalenhet, rolletittel, stilling,
               start_date, end_date, auto_role
        FROM [:table schema=cerebrum name=ephorte_role] %s
        ORDER BY person_id, standard_role DESC, role_type""" % where, {
            'person_id': person_id})

    def is_standard_role(self, person_id, role, sko, arkivdel, journalenhet):
        tmp = self.get_role(person_id, role, sko, arkivdel, journalenhet)
        if tmp and len(tmp) == 1 and tmp[0]['standard_role'] == 'T':
            return True
        return False


class EphortePermission(DatabaseAccessor):
    def __init__(self, database):
        super(EphortePermission, self).__init__(database)
        self.clconst = Factory.get('CLConstants')(database)
        self.pe = Factory.get('Person')(database)

    def add_permission(self, person_id, perm_type, sko, requestee):
        binds = {
            'person_id': person_id,
            'perm_type': perm_type,
            'adm_enhet': sko,
            'requestee_id': requestee
        }
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=ephorte_permission]
          (%s) VALUES (%s)""" % (", ".join(binds.keys()),
                                 ", ".join([":%s" % k for k in binds])),
                     binds)
        self._db.log_change(
            person_id, self.clconst.ephorte_perm_add, sko,
            change_params={
                'adm_enhet': sko or '',
                'perm_type': str(perm_type)
            })

    def remove_permission(self, person_id, perm_type, sko):
        binds = {
            'person_id': person_id,
            'perm_type': perm_type,
            'adm_enhet': sko
        }
        where = " AND ".join(
            ["%s=:%s" % (x, x) for x in binds if binds[x] is not None] +
            ["%s IS NULL" % x for x in binds if binds[x] is None])
        exists_stmt = """
          SELECT EXISTS (
            SELECT 1
            FROM [:table schema=cerebrum name=ephorte_permission]
            WHERE %s
          )
        """ % where
        if not self.query_1(exists_stmt, binds):
            # False positive
            return
        delete_stmt = """
        DELETE FROM [:table schema=cerebrum name=ephorte_permission]
        WHERE %s""" % where
        self.execute(delete_stmt, binds)
        self._db.log_change(
            person_id, self.clconst.ephorte_perm_rem, sko,
            change_params={
                'adm_enhet': sko or '',
                'perm_type': str(perm_type)
            })

    # Some permissions can't be removed, but must be deactivated or
    # expired by setting an end_date
    def expire_permission(self, person_id, perm_type, sko, end_date=None):
        binds = {
            'person_id': person_id,
            'perm_type': perm_type,
            'adm_enhet': sko
        }
        query = """
        UPDATE[:table schema=cerebrum name=ephorte_permission]
        SET end_date=%s
        WHERE %s""" % (
            end_date and ':end_date' or '[:now]', " AND ".join(
                ["%s=:%s" % (x, x) for x in binds if binds[x] is not None] +
                ["%s IS NULL" % x for x in binds if binds[x] is None]))
        if end_date:
            binds['end_date'] = end_date
        self.execute(query, binds)
        # TBD: log change?

    def list_permission(self, person_id=None, perm_type=None, adm_enhet=None,
                        filter_expired=False):
        where = []
        if person_id:
            where.append("person_id=:person_id")
        if perm_type:
            where.append("perm_type=:perm_type")
        if adm_enhet:
            where.append("adm_enhet=:adm_enhet")
        if filter_expired:
            where.append("start_date <= [:now] AND "
                         "(end_date IS NULL OR end_date > [:now])")
        if where:
            where = "WHERE %s" % " AND ".join(where)
        else:
            where = ""
        return self.query("""
        SELECT person_id, perm_type, adm_enhet,
               requestee_id, start_date, end_date
        FROM [:table schema=cerebrum name=ephorte_permission] %s""" % where, {
            'person_id': person_id,
            'perm_type': perm_type,
            'adm_enhet': adm_enhet})

    def has_permission(self, person_id, perm_type, adm_enhet):
        if self.list_permission(person_id, perm_type, adm_enhet):
            return True
        return False

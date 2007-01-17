#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2003, 2004 University of Oslo, Norway
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



import cerebrum_path
import cereconf

from Cerebrum import Utils
from Cerebrum import Person
from Cerebrum import Errors


class UiTPersonMixin(Person.Person):
  """
  This class provides an UiT-specific extension to the core Person class.
  """

  def get_primary_account(self,filter_expired=True):
    """Returns the account_id of SELF.entity_id's primary account"""
    acc = Utils.Factory.get("Account")(self._db)
    # get_account_types returns its results sorted
    accounts = acc.get_account_types(all_persons_types=True,
                                     owner_id=self.entity_id,
                                     filter_expired=filter_expired)
    if accounts:
      return accounts[0]["account_id"]
    else:
      return None



  def list_affiliations(self, person_id=None, source_system=None,
                        affiliation=None, status=None, ou_id=None,
                        include_deleted=False, fetchall = True, include_last=False):
      where = []
      last_field=""
      for t in ('person_id', 'affiliation', 'source_system', 'status', \
                'ou_id'):
          val = locals()[t]
          if val is not None:
              if isinstance(val, (list, tuple)):
                  where.append("%s IN (%s)" %
                               (t, ", ".join(map(str, map(int, val)))))
              else:
                where.append("%s = %d" % (t, val))
      if not include_deleted:
          where.append("(deleted_date IS NULL OR deleted_date > [:now])")
      where = " AND ".join(where)
      if where:
          where = "WHERE " + where
      if include_last:
          last_field = ", last_date"
      return self.query("""
      SELECT person_id, ou_id, affiliation, source_system, status,
      deleted_date, create_date%s
      FROM [:table schema=cerebrum name=person_affiliation_source]
      %s""" % (last_field,where), fetchall = fetchall)

  def _compare_names(self, type, other):
        """Returns True if names are equal.

        self must be a populated object."""
        print "comparing"
        #print ""
        try:
            tmp = other.get_name(self._pn_affect_source, type)
            if tmp ==None:
            #if len(tmp) == 0:
                raise KeyError
        except:
            raise MissingOtherException 
        try:
            myname = self._name_info[type]
        except:
            raise MissingSelfException
#        if isinstance(myname, unicode):
#            return unicode(tmp, 'iso8859-1') == myname
        return tmp == myname


  def set_affiliation_last_date(self, source, ou_id, affiliation, status):
        binds = {'ou_id': int(ou_id),
                 'affiliation': int(affiliation),
                 'source': int(source),
                 'status': int(status),
                 'p_id': self.entity_id,
                 }
        try:
            self.query_1("""
            SELECT 'yes' AS yes
            FROM [:table schema=cerebrum name=person_affiliation_source]
            WHERE
              person_id=:p_id AND
              ou_id=:ou_id AND
              affiliation=:affiliation AND
              source_system=:source""", binds)
            self.execute("""
            UPDATE [:table schema=cerebrum name=person_affiliation_source]
            SET last_date=[:now]
            WHERE
              person_id=:p_id AND
              ou_id=:ou_id AND
              affiliation=:affiliation AND
              source_system=:source""", binds)
            #self._db.log_change(self.entity_id,
            #                    self.const.person_aff_src_mod, None)
        
        except Errors.NotFoundError:
            raise Errors.ProgrammingError, "set_affiliation_last_date() failed. Called before person.populate_affiliations()?"
         
# arch-tag: 07747944-da97-11da-854b-ac67a6778cc2

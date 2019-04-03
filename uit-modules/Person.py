#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
from __future__ import unicode_literals


import cerebrum_path
import cereconf

from Cerebrum import Utils
from Cerebrum import Person
from Cerebrum import Errors


class UiTPersonMixin(Person.Person):
  """
  This class provides an UiT-specific extension to the core Person class.
  """

  # check if a person has an electronic listing reservation
  def has_e_reservation(self):
    # this method may be applied to any Cerebrum-instances that
    # use trait_public_reservation
    r = self.get_trait(self.const.trait_public_reservation)
    if r and r['numval'] == 0:
      return False
    return True

  # We want to raise an error when person.populate is called on a person with
  # deceased_date set in the DB.
  def populate(self, birth_date, gender, description=None, deceased_date=None,
                 parent=None):
    try:
      db_deceased = self.deceased_date
    except AttributeError:
      pass
    else:
      if db_deceased is not None and deceased_date is None:
        raise Errors.CerebrumError('Populate called with deceased_date=None,'\
                                   'but deceased_date already set on person')
    self.__super.populate(birth_date,gender,description,deceased_date,parent)
    

  def list_deceased(self):
      ret = {}
      for row in self.query("""
                            SELECT pi.person_id, pi.deceased_date
                            FROM [:table schema=cerebrum name=person_info] pi
                            WHERE pi.deceased_date IS NOT NULL """):
          ret[int(row['person_id'])] = row['deceased_date']
      return ret


  def _compare_names(self, type, other):
        """Returns True if names are equal.

        self must be a populated object."""
        try:
            tmp = other.get_name(self._pn_affect_source, type)
            if tmp ==None:
            #if len(tmp) == 0:
                raise KeyError
        except:
            raise Person.MissingOtherException 
        try:
            myname = self._name_info[type]
        except:
            raise Person.MissingSelfException
#        if isinstance(myname, unicode):
#            return unicode(tmp, 'iso8859-1') == myname
        return tmp == myname

  def list_persons_name(self, source_system=None, name_type=None):
        type_str = ""
        if name_type == None:
            type_str = "= %d" % int(self.const.name_full)
        elif isinstance(name_type, (list, tuple)):
            type_str = "IN ("
            type_str += ", ".join(["%d" % x for x in name_type])
            type_str += ")"
        else:
            type_str = "= %d" % int(name_type)
        if source_system:
            type_str += " AND source_system = %d" % int(source_system)

        return self.query("""
        SELECT DISTINCT person_id, name_variant, name, source_system
        FROM [:table schema=cerebrum name=person_name]
        WHERE name_variant %s""" % type_str)

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

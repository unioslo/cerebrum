#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2003-2019 University of Oslo, Norway
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
from Cerebrum.Utils import argument_to_sql
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

  def list_names(self, source_system=None, variant=None):
    """Return all names, optionally filtered on source_system or variant"""
    binds = dict()
    where = ''

    if source_system is not None:
      where += 'WHERE ' + argument_to_sql(source_system, 'source_system',
                                          binds, int)
      if variant is not None:
        where += ' AND ' + argument_to_sql(variant, 'name_variant',
                                           binds, int)
    elif variant is not None:
      where += 'WHERE ' + argument_to_sql(variant, 'name_variant',
                                          binds, int)

    return self.query("""
    SELECT *
    FROM [:table schema=cerebrum name=person_name]
    """ + where, binds)

# arch-tag: 07747944-da97-11da-854b-ac67a6778cc2

#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Copyright 2003 University of Oslo, Norway
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



from Cerebrum import Utils
from Cerebrum import Constants
from Cerebrum.DatabaseAccessor import DatabaseAccessor

import cereconf

class FeideGvsConstants(Constants.Constants):

    system_sas = _AuthoritativeSystemCode(
        'SAS'.
        'Skole Administrativt System')
    
    affiliation_pupil = _PersonAffiliationCode(
        'PUPIL'
        'pupil in school')

    affiliation_guardian = _PersonAffiliationCode(
        'GUARDIAN'
        'guardian for a pupil')

    affiliation_guardian = _PersonAffiliationCode(
        'TEACHER'
        'teacher in a school')

class FeideGvsEntity(DatabaseAccessor):
    def clear_class(self, cls):
        for attr in cls.__read_attr__:
            if hasattr(self, attr):
                if attr not in getattr(cls, 'dontclear', ()):
                    delattr(self, attr)
        for attr in cls.__write_attr__:
            if attr not in getattr(cls, 'dontclear', ()):
                setattr(self, attr, None)


    __metaclass__ = Utils.mark_update
    pass

class FeideGvsTeacherSchool(FeideGvsEntity):
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('teacher_id','ou_id')

    def clear(self):
        self.__super.clear()
        self.clear_class(FeideGvsTeacherSchool)
        self.__updated = []

    

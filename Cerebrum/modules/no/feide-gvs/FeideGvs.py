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
from Cerebrum.Constants import _AuthoritativeSystemCode,_PersonAffiliationCode, \
     _PersonExternalIdCode, _PersonAffStatusCode, _SpreadCode, _OUPerspectiveCode, \
     _QuarantineCode


import cereconf

class _FeideGvsGuardianCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=feide_gvs_guardian_code]'

class FeideGvsConstants(Constants.Constants):

    system_sas = _AuthoritativeSystemCode(
        'SAS',
        'Skole Administrativt System')

    externalid_sas_id = _PersonExternalIdCode(
        'SASID',
        'SAS internal id-number')

    affiliation_admin = _PersonAffiliationCode(
        'ADMIN',
        'person in tha administration')

    affiliation_guardian = _PersonAffiliationCode(
        'GUARDIAN',
        'guardian for a pupil')
    
    affiliation_pupil = _PersonAffiliationCode(
        'PUPIL',
        'pupil in school')

    affiliation_teacher = _PersonAffiliationCode(
        'TEACHER',
        'teacher in a school')

    affiliation_status_admin_active = _PersonAffStatusCode(
        affiliation_admin,
        'active',
        'Active member of administration')

    affiliation_status_admin_inactive = _PersonAffStatusCode(
        affiliation_admin,
        'inactive',
        'Inactive member of administration')

    affiliation_status_guardian_active = _PersonAffStatusCode(
        affiliation_guardian,
        'active',
        'Active guardian')

    affiliation_status_guardian_inactive = _PersonAffStatusCode(
        affiliation_guardian,
        'inactive',
        'Inactive guardian')

    affiliation_status_pupil_active = _PersonAffStatusCode(
        affiliation_pupil,
        'active',
        'Active pupil')
    
    affiliation_status_pupil_inactive = _PersonAffStatusCode(
        affiliation_pupil,
        'inactive',
        'Inactive pupil')

    affiliation_status_teacher_active = _PersonAffStatusCode(
        affiliation_teacher,
        'active',
        'Active teacher')

    affiliation_status_teacher_inactive = _PersonAffStatusCode(
        affiliation_teacher,
        'inactive',
        'Inactive teacher')

    spread_cerebrum_user = _SpreadCode(
        'cerebrum_user',
        Constants.Constants.entity_account,
        'User which exists in Cerebrum')

    perspective_sas = _OUPerspectiveCode(
        'SAS',
        'Perspective: SAS')

    feide_gvs_guardian_parent = _FeideGvsGuardianCode(
        'PARENT',
        'A pupils parent.')

    quarantine_generell = _QuarantineCode(
	'generell', 
	'Generell splatt')

    quarantine_teppe = _QuarantineCode(
	'teppe', 
	'Kallt inn på teppet til drift')

    quarantine_system = _QuarantineCode(
	'system', 
	'Systembrukar som ikke skal logge inn')

    quarantine_svakt_passord = _QuarantineCode(
	'svakt_passord', 
	'For dårlig passord')


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


    
class FeideGvsGuardian(FeideGvsEntity):
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('guardian_id','pupil_id', 'relation')

    def clear(self):
        self.__super.clear()
        self.clear_class(FeideGvsGuardian)
        self.__updated = []

    def populate(self, guardian_id, pupil_id, relation):
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        self.guardian_id = guardian_id
        self.pupil_id = pupil_id
        self.relation = relation

    def write_db(self):
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=feide_gvs_guardian_pupil]
              (guardian_id, pupil_id, relation)
            VALUES (:g_id, :p_id, :rel)""",
                         {'g_id': self.guardian_id,
                          'p_id': self.pupil_id,
                          'rel': self.relation})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=feide_gvs_guardian_pupil]
            SET relatian=:rel
            WHERE guardian_id=:g_id AND pupil_id=:p_id""",
                         {'g_id': self.guardian_id,
                          'p_id': self.pupil_id,
                          'rel': self.relation})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

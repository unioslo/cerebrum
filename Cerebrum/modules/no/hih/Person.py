# -*- coding: iso-8859-1 -*-
# Copyright 2010 University of Oslo, Norway
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


from Cerebrum import Person


class PersonHiHMixin(Person.Person):
    """Person mixin class providing functionality specific to HiH.

    The methods of the core Person class that are overridden here,
    ensure that any Person objects generated through
    Cerebrum.Utils.Factory.get() provide functionality that reflects
    the policies as stated by HiH.
    """
    def add_affiliation(self, ou_id, affiliation, source, status,
                        precedence=None):
        # bewator-ids are built as follows
        #
        # affiliation ANSATT and TILKNYTTET:
        # 01221 + free cereconf.BEWATOR_ID_RANGES['ANSATT'/TILKNYTTET] + 0
        #
        # affiliation STUDENT/ekstern:
        # 01221 + free cereconf.BEWATOR_ID_RANGES['STUDENT/ekstern'] + 0
        #
        # affiliation STUDENT:
        # 01221 + studnr from fs + 0

        #
        # if bew_id is found for person, don't generate a new one
        bew_id = self.get_external_id(id_type=self.const.externalid_bewatorid)
        if bew_id == []:
            if not hasattr(self, '_extid_source'):
                self.affect_external_id(self.const.system_manual,
                                        self.const.externalid_bewatorid)
            # if affiliation being added is ansatt or tilknyttet generate
            # bewator_id from the bewatorid_ans_seq
            if int(affiliation) in [int(self.const.affiliation_ansatt),
                                    int(self.const.affiliation_tilknyttet)]:
                bew_id = '01221' + str(self.nextval('bewatorid_ans_seq')) + '0'
                self.populate_external_id(self.const.system_manual,
                                          self.const.externalid_bewatorid,
                                          bew_id)

            if int(affiliation) == int(self.const.affiliation_student):
                if int(status) == int(
                        self.const.affiliation_status_student_ekstern):
                    bew_id = '01221' + str(
                        self.nextval('bewatorid_extstud_seq')) + '0'
                    self.populate_external_id(self.const.system_manual,
                                              self.const.externalid_bewatorid,
                                              bew_id)
                # for other students we usually register bewator_id during
                # FS-import
                else:
                    tmp = self.get_external_id(
                        source_system=self.const.system_fs,
                        id_type=self.const.externalid_studentnr)
                    if tmp:
                        studentnr = "%06d" % int(tmp[0]['external_id'])
                    if not studentnr:
                        # cannot create bewator id for this person
                        return
                    bew_id = '01221' + studentnr + '0'
            self.write_db()
        return self.__super.add_affiliation(ou_id, affiliation, source, status,
                                            precedence)

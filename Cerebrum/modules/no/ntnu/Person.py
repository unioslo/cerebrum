# -*- coding: iso-8859-1 -*-

# Copyright 2006 University of Oslo, Norway
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
from Cerebrum import Errors
from Cerebrum.modules.no import fodselsnr
import cereconf
import re
import sys

# The cached display name defaults to the cached full name, but
# may be overridden by a manually set display name.
# Will display names be imported from other administrative systems
# in the future?

class PersonNTNUMixin(Person.Person):
    def _update_cached_extid(self, extid):
        value=None
        for ss in cereconf.SYSTEM_LOOKUP_ORDER:
            source = getattr(self.const, ss)
            try:
                value=self.get_external_id(source, extid)
            except Errors.NotFoundError:
                continue
        self._set_cached_external_id(extid)
            
    def _update_cached_extids(self):
        for ee in cereconf.UPDATE_CACHE_EXTIDS:
            extid = getattr(self.const, ee)
            self._update_cached_extid(extid)
            
    def _update_cached_names(self):
        self.__super._update_cached_names()
        displayname=None
        for ss in cereconf.SYSTEM_LOOKUP_ORDER:
            source = getattr(self.const, ss)
            try:
                displayname=self.get_name(source, self.const.name_display)
            except Errors.NotFoundError:
                continue
        if displayname is None:
            displayname=self.get_name(self.const.system_cached,
                                      self.const.name_full)
        #if displayname is None:
        #    raise ValueError, "No cacheable display name for %d" % (
        #        self.entity_id)
        self._set_cached_name(self.const.name_display, displayname)
    
    def populate_external_id(self, source_system, id_type, external_id):
        if id_type == self.const.externalid_fodselsnr:
            fodselsnr.personnr_ok(external_id)
        self.__super.populate_external_id(source_system, id_type, external_id)


    # XXX: allow charlist explicitly instead of \w?

    # Use after this from python 2.4:
    person_name_regex=re.compile("^\w([\w '.-]*[\w.])?$", re.UNICODE)
    #person_name_regex=re.compile("^[0-9a-zA-Z\192-\255 '.-]+$")
    #person_name_not_regex=re.compile("[\000-\031!\"#$%&()*+,/:;<=>?@\[\\\]{|}~\127-\159]")

    def populate_name(self, variant, name):
        if not re.match(self.person_name_regex, name):
            raise ValueError, "Malformed name `%s'" % name
        self.__super.populate_name(variant, name)


# This seems to be a bug in python 2.3
if not re.match("\w\w\w", u'æøå', re.UNICODE):
    print >>sys.stdout, """WARNING: re.UNICODE does not work!
If using python 2.3, try setting locale as a workaround!"""

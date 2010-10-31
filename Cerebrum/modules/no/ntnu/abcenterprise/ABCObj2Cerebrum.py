# -*- coding: iso-8859-1 -*-
# Copyright 2005 University of Oslo, Norway
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
import abcconf

from Cerebrum.Utils import Factory
from Cerebrum.extlib.doc_exception import DocstringException
from Cerebrum.modules.abcenterprise.ABCUtils import ABCDataError
from Cerebrum.modules.abcenterprise.ABCUtils import ABCTypesError 
from Cerebrum.modules.abcenterprise.ABCUtils import ABCConfigError
from Cerebrum.modules.abcenterprise.ABCUtils import ABCFactory
from Cerebrum.modules.abcenterprise.ABCObj2Cerebrum import ABCObj2Cerebrum as _ABCObj2Cerebrum
from Cerebrum.modules.no.ntnu.Builder import Builder

class ABCObj2Cerebrum(_ABCObj2Cerebrum):
    """Class for comunicationg with Cerebrum."""

    def __init__(self, settings, logger):
        _ABCObj2Cerebrum.__init__(self, settings, logger)
        self.persons_to_build = []
        account = Factory.get("Account")(self.db)
        account.find_by_name("bootstrap_account")
        self._builder = Builder(self.db, account.entity_id)

    def parse_persons(self, iterator):
        """Iterate over person objects."""
        for person in iterator:
            new_person = self._conv_const_person(person)
            try:
                person_id = self._o2c.store_person(new_person)
                self.persons_to_build.append(person_id)
            except Exception, e:
                self.logger.warning("Error(person): %s, %s" % (e, list(person.iterids())))

    #######################################################################
    #######################################################################
    # TODO: cleanup. and lots of it.
    def parse_relations(self, iterator):
        """Iterate over <relations>.

        <entity> <type of relation> <entities>

        Any form of relation between entities(short of OUs parents)
        must be specified here."""

        # TBD: Mixins for odd relations?
        for rel in iterator:
            s = rel.subject[0][0]
            if s == "org":
                s = "ou"
            sub = None
            try: 
                sub = rel.subject[0][1:]
                if isinstance(sub[0], tuple):
                    # Hack to ignore organizations for now. They are all under one.
                    if len(sub) == 2:
                        sub = sub[1]
                    else:
                        sub = sub[0]
                if abcconf.CONSTANTS.has_key(sub[0]):
                    sub = [abcconf.CONSTANTS[sub[0]], sub[1]]
                else:
                    raise ABCDataError, "subject-type '%s' not found in CONSTANTS" % sub[0]
                # Optional rewrite rule.
                rewrite = getattr(abcconf, "GROUP_REWRITE", None)
                if s == "group" and rewrite:
                    sub[1] = rewrite(sub[1])
            except Exception, e:
                txt = "Error(relations) subject: s: %s, t: %s - %s" % (rel.subject,
                                                                       rel.type, e)
                self.logger.warning(txt)
                continue
            # TBD: object can be empty. deal with it.
            if rel.object == None or len(rel.object) < 1:
                self.logger.warning("Error(relations): No object in '%s'. Skipping." % rel)
                continue
            for obj in rel.object:
                try:
                    if obj[0] is 'org':
                        o = "ou"
                    else:
                        o = obj[0]
                    tmp = abcconf.RELATIONS[s][o][rel.type]
                    type = tmp[0]
                    rest = tmp[1:]
                
                    ob = obj[1:]
                    if ob == []:
                        raise ABCDataError, "no object: %s, %s" % (type, sub)
                    if isinstance(ob[0], tuple):
                        if len(ob) == 2:
                            ob = ob[1]
                        else:
                            ob = ob[0]                      
                    if abcconf.CONSTANTS.has_key(ob[0]):
                        ob = (abcconf.CONSTANTS[ob[0]], ob[1])
                    else:
                        raise ABCDataError, "object-type '%s' not found in CONSTANTS" % ob

                    if type == "memberof":
                        self._o2c.add_group_member(sub, o, ob)
                    elif type == "affiliation":
                        if len(rest) <> 1:
                            raise ABCDataError, "error in 'rest'"
                        ## we are doing it the other way round.
                        ## find affiliation by affiliation-status
                        aff_status = rest[0]
                        aff = aff_status.affiliation
                        ## self._o2c.add_person_affiliation(sub, ob, rest[0], status)
                        self._o2c.add_person_affiliation(sub, ob, aff, aff_status)
                    else:
                        raise ABCNotSupportedError, "'%s' is not supported." % type
                    
                except Exception, e:
                    txt = "Error(relations): s: %s, t: %s, o: %s: %s" % (rel.subject,
                                                                         rel.type,
                                                                         obj, e)
                    self.logger.warning(txt)

    def close(self):
        """Close whatever you need to close and finish your business."""
        for person_id in self.persons_to_build:
            self._builder.build_from_owner(person_id)
        _ABCObj2Cerebrum.close(self)

# arch-tag: fc250d64-6995-11da-8e2e-62c416f986a0

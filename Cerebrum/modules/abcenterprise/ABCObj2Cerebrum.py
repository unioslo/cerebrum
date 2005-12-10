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
from Cerebrum.modules.abcenterprise.ABCUtils import ABCFactory
from Cerebrum.modules.abcenterprise.Object2Cerebrum import Object2Cerebrum

# TODO:
# Denne må oversette fra strenger til konstanter.


class ABCObj2Cerebrum(object):
    """Class for comunicationg with Cerebrum."""

    # TODO: lagre state i dette objektet.

    def __init__(self, settings):
        self.sett = settings
        self.db = Factory.get('Database')()
        self.co = Factory.get('Constants')(self.db)
        self._o2c = Object2Cerebrum(abcconf.SOURCE['source_system'])

    def _conv_cons(self, value):
        """Convert a temporary text constant from ABCEnterprise to a
        real Cerebrum Constant from abcconf. Values passed onto this
        function _should_ be checked and the program should die if
        errors found."""
        try:
            return abcconf.CONSTANTS[value]
        except:
            raise ABCConfigError, "constant mismatch '%s'" % value
        
    def _conv_const_entity(self, entity):
        """Convert temporary text constants to real Constants."""
        for i in entity._ids.keys():
            entity._ids[self._conv_cons(i)] = entity._ids[i]
            del entity._ids[i]
        for i in entity._names.keys():
            entity._names[self._conv_cons(i)] = entity._names[i]
            if not self._conv_cons(i) is i:
                del entity._names[i]
        for i in entity._address.keys():
            entity._address[self._conv_cons(i)] = entity._address[i]
            del entity._address[i]
        for i in entity._contacts.keys():
            entity._contacts[self._conv_cons(i)] = entity._contacts[i]
            del entity._contacts[i]
        return entity

    def _conv_const_person(self, person):
        """Convert temporary text constants to real Constants for person
        objects."""
        person = self._conv_const_entity(person)
        # Person has to have gender
        if person.gender == "unknown":
            person.gender = self.co.gender_unknown
        elif person.gender == "female":
            person.gender = self.co.gender_female
        elif person.gender == "male":
            person.gender = self.co.gender_male
        else:
            # unknown gender
            # raise ABCDataError, "gender unknown: %s" % person.gender
            # TBD: what to do if no gender populated? 
            person.gender = self.co.gender_unknown
        return person

    def _conv_const_ou(self, ou):
        """Convert temporary text constants to real Constants for OU
        objects."""
        ou = self._conv_const_entity(ou)
        # Convert names to standardized OU format
        ou.ou_names = dict()
        if abcconf.OU_NAMES.has_key('name') and \
               ou._names.has_key(abcconf.OU_NAMES['name']):
            ou.ou_names['name'] = ou._names[abcconf.OU_NAMES['name']]
        else:
            raise ABCDataError, "no name for OU"
        for n in ("acronym", "short_name", "display_name", "sort_name"):
            if abcconf.OU_NAMES.has_key(n) and \
                   abcconf.OU_NAMES[n] and \
                   ou._names.has_key(abcconf.OU_NAMES[n]):
                ou.ou_names[n] = ou._names[abcconf.OU_NAMES[n]]
            else:
                ou.ou_names[n] = None
        return ou

    def _conv_const_group(self, group):
        """Placeholder for furure extensions."""
        group = self._conv_const_entity(group)
        return group
        
    def parse_settings(self):
        """Check variables in the imported <properties> tag.
        Verify that the file is an accepted file."""
        
        # Verify the XML-file 
        if self.sett.variables['datasource'] <> abcconf.SOURCE['datasource'] or \
           self.sett.variables['target'] <> abcconf.SOURCE['target']:
            raise ABCConfigError, "datasource and/or target doesn't match." 

    def parse_orgs(self, iterator):
        """Iterate over organizations. Org objects come with an
        iterator for OUs. Structuring parents and children should be
        done at the end of the method. There is no guarantee that
        OUs come in a sorted order."""
        for org in iterator:
            ou_struct = dict()
            new_org = self._conv_const_ou(org)
            (ret, org_e_id) = self._o2c.store_ou(new_org)
            self._o2c.set_ou_parent(org_e_id, abcconf.OU_PERSPECTIVE, None)
            # org.parent is an iterator if there are children
            for ou in org.ou:
                new_ou = self._conv_const_ou(ou)
                (ret, e_id) = self._o2c.store_ou(new_ou)
                if new_ou.parent is None:
                    ou_struct[e_id] = org_e_id
                else:
                    ou_struct[e_id] = new_ou.parent
            for i in ou_struct.keys():
                try:
                    self._o2c.set_ou_parent(i, abcconf.OU_PERSPECTIVE, ou_struct[i])
                except Exception, e:
                    print "Error(ou_parent): %s" % e
                
    def parse_persons(self, iterator):
        """Iterate over person objects."""
        for person in iterator:
            new_person = self._conv_const_person(person)
            try: 
                self._o2c.store_person(new_person)
            except Exception, e:
                print "Error(person): %s" % e
                
    def parse_groups(self, iterator):
        """Iterate over group objects. Note that members follow in
        the <relation> part. There are no group names either, just
        an ID. desc is meant to be informative, not an imformation
        bearer."""
        for group in iterator:
            new_group = self._conv_const_group(group)
            if new_group._ids.has_key(abcconf.GROUP_NAME):
                new_group.name = new_group._ids[abcconf.GROUP_NAME]
            else:
                # TODO: skip this group
                pass
            self._o2c.store_group(new_group)


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
            for obj in rel.object:
                try:
                    if obj[0] is 'org':
                        o = "ou"
                    else:
                        o = obj[0]
                    tmp = abcconf.RELATIONS[s][o][rel.type]
                    type = tmp[0]
                    rest = tmp[1:]
                
                    sub = rel.subject[0][1:]
                    if isinstance(sub[0], tuple):
                        sub = sub[1]
                    sub = (abcconf.CONSTANTS[sub[0]], sub[1])

                    ob = obj[1:]
                    if ob == []:
                        raise ABCDataError, "no object: %s, %s" % (type, sub)
                    if isinstance(ob[0], tuple):
                        ob = ob[0]
                    ob = (abcconf.CONSTANTS[ob[0]], ob[1])
                
                    if type == "memberof":
                        self._o2c.add_group_member(sub, o, ob)
                    elif type == "affiliation":
                        if len(rest) <> 1:
                            raise ABCDataError, "error in 'rest'"
                        status = abcconf.AFF_STATUS[rest[0]]
                        self._o2c.add_person_affiliation(sub, ob, rest[0], status)
                except Exception, e:
                    print "Error(relations): %s" % e


    def close(self):
        """Close whatever you need to close and finish your business."""
        self._o2c.commit()

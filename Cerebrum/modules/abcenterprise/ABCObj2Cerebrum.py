# -*- coding: utf-8 -*-
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

from __future__ import unicode_literals
import cerebrum_path
import cereconf
import abcconf

from Cerebrum.Utils import Factory
from Cerebrum.extlib.doc_exception import DocstringException
from Cerebrum.modules.abcenterprise.ABCUtils import ABCDataError
from Cerebrum.modules.abcenterprise.ABCUtils import ABCTypesError
from Cerebrum.modules.abcenterprise.ABCUtils import ABCConfigError
from Cerebrum.modules.abcenterprise.ABCUtils import ABCFactory

class ABCObj2Cerebrum(object):
    """Class for comunicationg with Cerebrum."""

    # TODO: lagre state i dette objektet.

    def __init__(self, settings, logger):
        self.sett = settings
        self.db = Factory.get('Database')()
        self.co = Factory.get('Constants')(self.db)
        self._o2c = ABCFactory.get('Object2Cerebrum')(abcconf.SOURCE['source_system'],
                                                      logger)
        self.logger = logger

    def _conv_cons(self, value):
        """Convert a temporary text constant from ABCEnterprise to a
        real Cerebrum Constant from abcconf. Values passed onto this
        function _should_ be checked and the program should die if
        errors found."""
        try:
            return abcconf.CONSTANTS[value]
        except:
            raise ABCConfigError("constant mismatch '%s'" % value)

    def _conv_const_entity(self, entity):
        """Convert temporary text constants to real Constants."""
        entity = self._process_tags(entity)
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

    def _process_tags(self, entity):
        """Process known <tag> mechanics. Translate the tagtype into something
        Object2Cerebrum understands."""
        new_tags = dict()
        for i in entity._tags.keys():
            if i == "ADD_SPREAD":
                for s in entity._tags[i]:
                    if abcconf.TAG_REWRITE.has_key(s):
                        new_tags.setdefault(i, []).append(abcconf.TAG_REWRITE[s])
                    else:
                        raise ABCConfigError, "missing TAG_REWRITE rule: %s" % s

            else:
                raise ABCConfigError, "no known action for tag_type: %s" % i
        entity._tags = new_tags
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
        for type, ceretype in (("name", self.co.ou_name),
                               ("acronym", self.co.ou_name_acronym),
                               ("short_name", self.co.ou_name_short),
                               ("display_name", self.co.ou_name_display),
                               ("sort_name", self.co.ou_name_short)):
            if abcconf.OU_NAMES.get(type):
                try:
                    ou.ou_names[ceretype] = ou._names[abcconf.OU_NAMES[type]]
                except KeyError:
                    pass
        # Name must be set
        if not ou.ou_names.get(self.co.ou_name):
            raise ABCDataError("Missing name for OU: %s" % ou._ids)
        return ou

    def _conv_const_group(self, group):
        """Set one of the IDs to the group's name."""
        group = self._conv_const_entity(group)
        rewrite = getattr(abcconf, "GROUP_REWRITE", None)
        for id in group._ids:
            if rewrite:
                group._ids[id] = rewrite(group._ids[id])
            if id in abcconf.GROUP_NAMES:
                group.name = group._ids[id]
        return group

    def parse_settings(self):
        """Check variables in the imported <properties> tag.
        Verify that the file is an accepted file."""

        # Verify the XML-file
        if self.sett.variables['datasource'] != abcconf.SOURCE['datasource'] or \
           self.sett.variables['target'] != abcconf.SOURCE['target']:
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
            if not org.ou:
                continue
            # org.parent is an iterator if there are children
            for ou in org.ou:
                new_ou = self._conv_const_ou(ou)
                (ret, e_id) = self._o2c.store_ou(new_ou)
                if new_ou.parent is None:
                    ou_struct[e_id] = org_e_id
                else:
                    ou_struct[e_id] = (self._conv_cons(new_ou.parent[0]), new_ou.parent[1])
            for i in ou_struct.keys():
                try:
                    self._o2c.set_ou_parent(i, abcconf.OU_PERSPECTIVE, ou_struct[i])
                except Exception, e:
                    self.logger.warning("Error(ou_parent): %s" % e)

    def parse_persons(self, iterator):
        """Iterate over person objects."""
        for person in iterator:
            new_person = self._conv_const_person(person)
            try:
                self._o2c.store_person(new_person)
            except Exception, e:
                self.logger.warning("Error(person): %s, %s" % (e, list(person.iterids())))

    def parse_groups(self, iterator):
        """Iterate over group objects. Note that members follow in
        the <relation> part. There are no group names either, just
        an ID. desc is meant to be informative, not an imformation
        bearer."""
        for group in iterator:
            new_group = self._conv_const_group(group)
            if new_group.name:
                self._o2c.store_group(new_group)
            else:
                self.logger.warning("Error(parse_groups): Group has no name '%s'" % group)

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
                        if len(rest) != 1:
                            raise ABCDataError, "error in 'rest'"
                        status = abcconf.AFF_STATUS[rest[0]]
                        self._o2c.add_person_affiliation(sub, ob, rest[0], status)
                    else:
                        raise ABCNotSupportedError, "'%s' is not supported." % type

                except Exception, e:
                    txt = "Error(relations): s: %s, t: %s, o: %s: %s" % (rel.subject,
                                                                         rel.type,
                                                                         obj, e)
                    self.logger.warning(txt)


    def close(self):
        """Close whatever you need to close and finish your business."""
        if self.sett.variables['dryrun']:
            self._o2c.rollback()
            self.logger.debug("rollback()")
        else:
            self._o2c.commit()
            self.logger.debug("commit()")


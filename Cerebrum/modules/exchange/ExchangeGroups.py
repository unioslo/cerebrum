#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2015 University of Oslo, Norway
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

"""The DistributionGroup module implements a specialisation of the
`Group' core class.  The DistributionGroup-subclass implements group
attributes necessary for establishing distribution groups in Exchange
(as of 2013 version).

Note that distribution groups come in two flavors, based on what kind
of members they accept. For now only accounts and rooms are allowed."""

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.Constants import _LanguageCode
from Cerebrum.modules import Email
from Cerebrum import Errors
from .mixins import SecurityGroupMixin, DistributionGroupMixin


Group_class = Factory.get("Group")

assert issubclass(Group_class, SecurityGroupMixin)
assert issubclass(Group_class, DistributionGroupMixin)


# make ready for adding new functionality specific for
# security groups in exchange (i.e. mail enabled sec groups etc).
class SecurityGroup(Group_class):
    # nothing to do here for now
    pass


class DistributionGroup(Group_class):
    """
    The DistributionGroup module implements a specialisation of the `Group'
    core class.  The DistributionGroup-subclass implements group attributes
    necessary for establishing distribution groups in Exchange (as of 2013
    version).

    """
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('roomlist', 'hidden')

    def clear(self):
        """Clear all object attributes."""
        self.__super.clear()
        self.clear_class(DistributionGroup)
        self.__updated = []

    def populate(self,
                 creator_id=None,
                 visibility=None,
                 name=None,
                 description=None,
                 expire_date=None,
                 group_type=None,
                 roomlist=None,
                 hidden=None,
                 parent=None):
        """Populate Distribution group.

        DistributionGroups may inherit the name and other common details
        from the generic parent group.

        :type creator_id: int
        :param creator_id:

        :type visibility:
        :param visibility:

        :type name:
        :param name:

        :type description:
        :param description:

        :type expire_date:
        :param expire_date:

        :type roomlist:
        :param roomlist:

        :type hidden:
        :param hidden:

        :type parent:
        :param parent:
        """
        if parent is not None:
            self.__xerox__(parent)
        else:
            super(DistributionGroup, self).populate(
                creator_id=creator_id,
                visibility=visibility,
                name=name,
                description=description,
                expire_date=expire_date,
                group_type=group_type,
            )
        self.__in_db = False
        self.roomlist = roomlist
        self.hidden = hidden

    def write_db(self):
        """Write distribution group to database."""
        self.__super.write_db()
        if not self.__updated:
            return
        binds = {'g_id': self.entity_id,
                 'roomlist': self.roomlist,
                 'hidden': self.hidden}
        if not self.__in_db:
            insert_stmt = """
            INSERT INTO [:table schema=cerebrum name=distribution_group]
            (group_id, roomlist, hidden)
            VALUES (:g_id, :roomlist, :hidden)"""
            self.execute(insert_stmt, binds)
            if self.roomlist == 'T':
                self._db.log_change(self.entity_id,
                                    self.clconst.dl_roomlist_create,
                                    None)
            else:
                self._db.log_change(self.entity_id,
                                    self.clconst.dl_group_create,
                                    None)
        else:
            exists_stmt = """
              SELECT EXISTS (
                SELECT 1
                FROM [:table schema=cerebrum name=distribution_group]
                WHERE
                  group_id=:g_id AND
                  roomlist=:roomlist AND
                  hidden=:hidden
              )
            """
            if not self.query_1(exists_stmt, binds):
                # True positive
                update_stmt = """
                UPDATE [:table schema=cerebrum name=distribution_group]
                SET roomlist=:roomlist, hidden=:hidden
                WHERE group_id=:g_id"""
                self.execute(update_stmt, binds)
                # should probably param-log all relevant data!
                self._db.log_change(self.entity_id,
                                    self.clconst.dl_group_modify,
                                    None)
        del self.__in_db
        self.__in_db = True
        self.__updated = []

    def __eq__(self, other):
        assert isinstance(other, DistributionGroup)
        if self.roomlist == other.roomlist and \
           self.hidden == other.hidden:
            return self.__super.__eq__(other)
        return False

    def new(self,
            creator_id,
            visibility,
            name,
            description=None,
            expire_date=None,
            roomlist=None,
            hidden=None):
        """
        """
        DistributionGroup.populate(self,
                                   creator_id=creator_id,
                                   visibility=visibility,
                                   name=name,
                                   description=description,
                                   expire_date=expire_date,
                                   roomlist=roomlist,
                                   hidden=hidden)
        DistributionGroup.write_db(self)

    def find(self, group_id):
        """Look up a DistributionGroup.

        :type group_id: int
        :param group_id: The entity-id of the DistributionGroup."""
        super(DistributionGroup, self).find(group_id)
        (self.roomlist, self.hidden) = self.query_1("""
        SELECT roomlist, hidden
        FROM [:table schema=cerebrum name=distribution_group]
        WHERE group_id=:g_id""", {'g_id': self.entity_id})
        self.__in_db = True
        self.__updated = []

    def list_distribution_groups(self):
        """Return entity-IDs of all DistributionGroups.

        :rtype list(db_row.row)
        :return [(group_id,)]"""
        return self.query("""
        SELECT group_id
        FROM [:table schema=cerebrum name=distribution_group]""")

    def set_roomlist_status(self, roomlist='F'):
        """Set roomlist status for a distribution group.

        This method is used to make a distribution group or a roomlist or vice
        versa. It's also possible to make a distribution group into a roomlist
        and vice versa, but that's not really recommended and the client code
        in bofhd restricts it (but we allow through API as we most likely will
        encounter special cases).

        :type roomlist: basestring
        :param roomlist: 'T' if the DistributionGroup should be a roomlist. 'F'
            otherwise."""
        current_status = self.get_roomlist_status()
        if current_status == roomlist:
            return
        self._db.log_change(self.entity_id, self.clconst.dl_group_room,
                            None, change_params={'roomlist': roomlist})
        stmt = """
          UPDATE [:table schema=cerebrum name=distribution_group]
          SET roomlist=:roomlist
          WHERE
            group_id=:g_id
        """
        self.execute(stmt, {'g_id': self.entity_id,
                            'roomlist': roomlist})

    def get_distribution_group_hidden_status(self):
        """Determine wether DistributionGroup visibility is on or off.

        Returns 'T' for True, 'F' for False """
        binds = {'g_id': self.entity_id,
                 'hidden': 'T'}
        exists_stmt = """
        SELECT EXISTS (
          SELECT 1
          FROM [:table schema=cerebrum name=distribution_group]
          WHERE group_id=:g_id AND hidden=:hidden
        )"""
        return 'T' if self.query_1(exists_stmt, binds) else 'F'

    # change the visibility in address list for a distribution group
    # default is visible
    def set_hidden(self, hidden='F'):
        """Set Distribution Group visibility in Exchanges address book.

        :type hidden: basestring
        :param hidden: 'T' if hidden, 'F' if visible."""
        if hidden == self.get_distribution_group_hidden_status():
            # False positive; status is already correctly set
            return
        binds = {'g_id': self.entity_id, 'hidden': hidden}
        update_stmt = """
          UPDATE [:table schema=cerebrum name=distribution_group]
            SET hidden=:hidden
          WHERE group_id=:g_id"""
        self.execute(update_stmt, binds)
        self._db.log_change(self.entity_id,
                            self.clconst.dl_group_hidden,
                            None,
                            change_params={'hidden': hidden})

    def ret_standard_attr_values(self, room=False):
        return {'roomlist': 'T' if room else 'F',
                'hidden': 'F' if room else  'T'}

    def ret_standard_language(self):
        return 'nb'

    def get_distgroup_attributes_and_targetdata(self,
                                                display_name_lang='nb',
                                                roomlist=False):
        all_data = {}
        ea = Email.EmailAddress(self._db)
        ed = Email.EmailDomain(self._db)
        et = Email.EmailTarget(self._db)
        epat = Email.EmailPrimaryAddressTarget(self._db)
        primary_address = ""
        display_name = ""
        name_language = ""
        addrs = []
        name_variant = self.const.dl_group_displ_name
        if display_name_lang == 'nb' or \
                not hasattr(self.const, 'dl_group_displ_name'):
            # code that uses this methos should probably take
            # care of getting the language right?
            name_language = self.const.language_nb
        else:
            name_language = int(_LanguageCode(display_name_lang))
        display_name = self.get_name_with_language(name_variant,
                                                   name_language,
                                                   default=self.group_name)
        # in roomlists we only care about name, description,
        # displayname and the roomlist-status, the other attributes
        # don't need to be set in Exchange
        if roomlist:
            all_data = {'name': self.group_name,
                        'description': self.description,
                        'displayname': display_name,
                        'group_id': self.entity_id,
                        'roomlist': self.roomlist}
            return all_data

        try:
            et.find_by_target_entity(self.entity_id)
        except Errors.NotFoundError:
            # could not find e-mail target for group. this should
            # normally not happen
            return None
        try:
            epat.find(et.entity_id)
        except Errors.NotFoundError:
            # could not find primary address for the e-mail target
            # this happens from time to time, and we should be able
            # to identify the error
            raise self._db.IntegrityError(
                "No primary address registered for {}".format(self.group_name))
        ea.clear()
        ea.find(epat.email_primaddr_id)
        ed.clear()
        ed.find(ea.email_addr_domain_id)
        primary_address = "%s@%s" % (ea.email_addr_local_part,
                                     ed.email_domain_name)
        for r in et.get_addresses(special=True):
            ad = "%s@%s" % (r['local_part'], r['domain'])
            addrs.append(ad)
        # name is expanded with prefix 'dl-' by the export
        all_data = {'name': self.group_name,
                    'description': self.description,
                    'displayname': display_name,
                    'group_id': self.entity_id,
                    'roomlist': self.roomlist,
                    'hidden': self.hidden,
                    'primary': primary_address,
                    'aliases': addrs}
        return all_data

    # the following three methods could be placed into a separate
    # Email-mixin class for Distribution groups, but as there
    # are no clear plans to expand usage of mail functionality for
    # distribution groups we are, at this time, satisfied to let
    # them be a part of the main DistGroup-class. (Jazz, 2013-13)
    def create_distgroup_mailtarget(self):
        """Make e-mail target for group"""
        et = Email.EmailTarget(self._db)
        target_type = self.const.email_target_dl_group
        if self.is_expired():
            raise self._db.IntegrityError(
                "Cannot make e-mail target for the expired group %s." %
                self.group_name)
        try:
            et.find_by_email_target_attrs(target_entity_id=self.entity_id)
            if et.email_target_type != target_type:
                et.email_target_type = target_type
        except Errors.NotFoundError:
            et.populate(target_type, self.entity_id, self.const.entity_group)
        et.write_db()
        self._create_distgroup_mailaddr(et)

    def _create_distgroup_mailaddr(self, et):
        ea = Email.EmailAddress(self._db)
        # move this to a variable
        # no need to wash the address, group will not be created
        # if the name is not valid for Exchange
        lp = "%s%s" % (cereconf.DISTGROUP_PRIMARY_ADDR_PREFIX,
                       self.group_name)
        dom = Email.EmailDomain(self._db)
        dom.find_by_domain(cereconf.DISTGROUP_DEFAULT_DOMAIN)
        addr_str = lp + '@' + cereconf.DISTGROUP_DEFAULT_DOMAIN
        try:
            ea.find_by_local_part_and_domain(lp, dom.entity_id)
            if ea.email_addr_target_id != et.entity_id:
                raise self._db.IntegrityError(
                    "Address %s is already taken!" % addr_str)
        except Errors.NotFoundError:
            ea.populate(lp, dom.entity_id, et.entity_id, expire=None)
        ea.write_db()
        epat = Email.EmailPrimaryAddressTarget(self._db)
        try:
            epat.find(ea.email_addr_target_id)
            epat.populate(ea.entity_id)
        except Errors.NotFoundError:
            epat.clear()
            epat.populate(ea.entity_id, parent=et)
        epat.write_db()

    def deactivate_dl_mailtarget(self):
        """Set the associated EmailTargets type to deleted."""
        et = Email.EmailTarget(self._db)
        # we are not supposed to remove e-mail targets because
        # of the danger of re-using
        target_type = self.const.email_target_deleted
        try:
            et.find_by_email_target_attrs(target_entity_id=self.entity_id)
            et.email_target_type = target_type
            et.write_db()
        except Errors.NotFoundError:
            # no such target, nothing to do
            # TBD: should we raise an exception?
            # I judge an exception not to be necessary
            # as the situation is not likely to occur at all
            # (Jazz, 2013-12)
            return

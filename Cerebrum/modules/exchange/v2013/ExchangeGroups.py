# -*- coding: iso-8859-1 -*-
# Copyright 2013 University of Oslo, Norway
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
import cerebrum_path
getattr(cerebrum_path, "linter", "is noisy!")
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
    __write_attr__ = ('roomlist', 'mngdby_addrid', 'modenable', 'modby',
                      'deprestr', 'joinrestr', 'hidden')

    def clear(self):
        """Clear all object attributes."""
        self.__super.clear()
        self.clear_class(DistributionGroup)
        self.__updated = []

    def populate(self, creator_id=None, visibility=None, name=None,
                 description=None, create_date=None, expire_date=None,
                 roomlist=None, mngdby_addrid=None, modenable=None,
                 modby=None, deprestr=None, joinrestr=None,
                 hidden=None, parent=None):
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

        :type create_date:
        :param create_date:

        :type expire_date:
        :param expire_date:

        :type roomlist:
        :param roomlist:

        :type mngdby_addrid:
        :param mngdby_addrid:

        :type modenable:
        :param modenable:

        :type modby:
        :param modby:

        :type deprestr:
        :param deprestr:

        :type joinrestr:
        :param joinrestr:

        :type hidden:
        :param hidden:

        :type parent:
        :param parent:
        """
        if parent is not None:
            self.__xerox__(parent)
        else:
            super(DistributionGroup, self).populate(creator_id, visibility,
                                                    name, description,
                                                    create_date,
                                                    expire_date)
        self.__in_db = False
        self.roomlist = roomlist
        self.mngdby_addrid = mngdby_addrid
        self.modenable = modenable
        self.modby = modby
        self.deprestr = deprestr
        self.joinrestr = joinrestr
        self.hidden = hidden

    def write_db(self):
        """Write distribution group to database."""
        self.__super.write_db()
        if not self.__updated:
            return
        if not self.__in_db:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=distribution_group]
              (group_id, roomlist, mngdby_addrid,
               modenable, modby, deprestr,
               joinrestr, hidden)
            VALUES (:g_id, :roomlist, :mngdby_addrid,
                    :modenable, :modby, :deprestr,
                    :joinrestr, :hidden)""",
                         {'g_id': self.entity_id,
                          'roomlist': self.roomlist,
                          'mngdby_addrid': self.mngdby_addrid,
                          'modenable': self.modenable,
                          'modby': self.modby,
                          'deprestr': self.deprestr,
                          'joinrestr': self.joinrestr,
                          'hidden': self.hidden})
            # exchange-relatert-jazz
            if self.roomlist == 'T':
                self._db.log_change(self.entity_id,
                                    self.const.dl_roomlist_create,
                                    None)
            else:
                self._db.log_change(self.entity_id,
                                    self.const.dl_group_create,
                                    None)
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=distribution_group]
            SET roomlist=:roomlist, mngdby_addrid=:mngdby_addrid,
                modenable=:modenable, modby=:modby, deprestr=:deprestr,
                joinrestr=:joinrestr, hidden=:hidden
            WHERE group_id=:g_id""", {'g_id': self.entity_id,
                                      'roomlist': self.roomlist,
                                      'mngdby_addrid': self.mngdby_addrid,
                                      'modenable': self.modenable,
                                      'modby': self.modby,
                                      'deprestr': self.deprestr,
                                      'joinrestr': self.joinrestr,
                                      'hidden': self.hidden})
        # exchange-relatert-jazz
        # should probably param-log all relevant data!
        self._db.log_change(self.entity_id,
                            self.const.dl_group_modify,
                            None)

        del self.__in_db
        self.__in_db = True
        self.__updated = []

    def __eq__(self, other):
        assert isinstance(other, DistributionGroup)
        if self.roomlist == other.roomlist and \
           self.mngdby_addrid == other.mngdby_addrid and \
           self.modenable == other.modenable and \
           self.modby == other.modby and \
           self.deprestr == other.deprestr and \
           self.joinrestr == other.joinrestr and \
           self.hidden == other.hidden:
            return self.__super.__eq__(other)
        return False

    def new(self, creator_id, visibility, name, description=None,
            create_date=None, expire_date=None, roomlist=None,
            mngdby_addrid=None, modenable=None, modby=None,
            deprestr=None, joinrestr=None, hidden=None):
        DistributionGroup.populate(self, creator_id, visibility, name,
                                   description, create_date, expire_date,
                                   roomlist, mngdby_addrid, modenable,
                                   modby, deprestr, joinrestr, hidden)
        DistributionGroup.write_db(self)
        # DistributionGroup.find(self, self.entity_id)

    def find(self, group_id):
        """Look up a DistributionGroup.

        :type group_id: int
        :param group_id: The entity-id of the DistributionGroup."""
        super(DistributionGroup, self).find(group_id)
        (self.roomlist, self.mngdby_addrid, self.modenable,
         self.modby, self.deprestr, self.joinrestr,
         self.hidden) = self.query_1("""
        SELECT roomlist, mngdby_addrid, modenable, modby, deprestr, joinrestr,
            hidden
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

    # assign or remove roomlist status
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
        self._db.log_change(self.entity_id, self.const.dl_group_room,
                            None, change_params={'roomlist': roomlist})
        return self.execute("""
          UPDATE [:table schema=cerebrum name=distribution_group]
            SET roomlist=:roomlist
          WHERE group_id=:g_id""", {'g_id': self.entity_id,
                                    'roomlist': roomlist})

    # set depart/join restrictions for group
    # implementing this as one method as the restriction rule set
    # is the same for both join and depart. if this should change
    # in the future  a re-write may be advisable.
    def set_depjoin_restriction(self, variant="join", restriction="Closed"):
        """Set join and depart restrictions for a Distribution Group.

        :type variant: str
        :param variant: Alter 'join' or 'part' restrictions.

        :type restriction: str
        :param restriction: Set Member[Join|Part]ApprovalRequired to
            'Open', 'Closed' or 'ApprovalRequired'."""
        attribute = None
        cl_type = None
        if variant == 'join':
            attribute = 'joinrestr'
            cl_type = self.const.dl_group_joinre
        elif variant == 'depart':
            attribute = 'deprestr'
            cl_type = self.const.dl_group_depres
        else:
            raise self._db.IntegrityError, \
                "Only join and depart are valid variants"
        self._db.log_change(self.entity_id, cl_type,
                            None,
                            change_params={attribute: restriction})
        return self.execute("""
          UPDATE [:table schema=cerebrum name=distribution_group]
            SET %s=:restriction
          WHERE group_id=:g_id""" % attribute, {'g_id': self.entity_id,
                                                'restriction': restriction})

    def set_managedby(self, emailaddress):
        """Set Distribution Group manager (ManagedBy).

        :type emailaddress: basestring
        :param emailaddress: The E-mail address that should be able to manage
            a Distribution Group in Exchange. The address must exist in
            Cerebrum."""
        ea = Email.EmailAddress(self._db)
        try:
            ea.find_by_address(emailaddress)
        except Errors.NotFoundError:
            raise Errors.CerebrumError, \
                "No address %s found in Cerebrum" % emailaddress
        managedby = ea.entity_id
        self._db.log_change(self.entity_id, self.const.dl_group_manby,
                            None,
                            change_params={'manby': emailaddress})
        return self.execute("""
          UPDATE [:table schema=cerebrum name=distribution_group]
            SET mngdby_addrid=:managedby
          WHERE group_id=:g_id""", {'g_id': self.entity_id,
                                    'managedby': managedby})

    # set modenable, to decide if the dist group will be moderated
    # in Exchange. default is True, but we may make groups
    # non-moderated at will
    def set_modenable(self, enable='T'):
        """Enable moderation of DistributionGroup in Exchange.

        DistributionGroup moderators are removed when moderation is disabled.
        It is considered polite to register moderators, when moderation is
        enabled.

        :type enable: basestring
        :param enable: 'T' enables moderation, 'F' disables moderation."""
        self._db.log_change(self.entity_id, self.const.dl_group_modrt,
                            None,
                            change_params={'modenable': enable})
        if enable == 'F':
            self.set_modby('')
        # this need some thinking. how can we make sure that
        # modby is added when modenable is true?
        # No, it does not, when the data-model is properly designed.
        # TODO: Re-write storage and API.
        return self.execute("""
          UPDATE [:table schema=cerebrum name=distribution_group]
            SET modenable=:enable
          WHERE group_id=:g_id""", {'g_id': self.entity_id,
                                    'enable': enable})

    def set_modby(self, modby):
        """Set DistributionGroup moderators.

        :type modby: basestring
        :param modby: Comma-separated list of usernames."""
        if self.modenable == 'F':
            raise self._db.IntegrityError(
                "Cannot set ModeratedBy for a non-moderated group (%s)" %
                self.group_name)
        self._db.log_change(self.entity_id, self.const.dl_group_modby,
                            None,
                            change_params={'modby': modby})
        return self.execute("""
          UPDATE [:table schema=cerebrum name=distribution_group]
            SET modby=:modby
          WHERE group_id=:g_id""", {'g_id': self.entity_id,
                                    'modby': modby})

    def set_hidden(self, hidden='F'):
        """Set Distribution Group visibility in Exchanges address book.

        :type hidden: basestring
        :param hidden: 'T' if hidden, 'F' if visible."""
        self._db.log_change(self.entity_id, self.const.dl_group_hidden,
                            None,
                            change_params={'hidden': hidden})
        return self.execute("""
          UPDATE [:table schema=cerebrum name=distribution_group]
            SET hidden=:hidden
          WHERE group_id=:g_id""", {'g_id': self.entity_id,
                                    'hidden': hidden})

    def ret_standard_attr_values(self, room=False):
        """Return standard values for Distribution Groups.

        This is a side-effect free utility function.

        :type room: bool
        :param room: Return values for regular DistributionGroups if room is
            false. Else, return special values for Roomlists."""
        if not room:
            return {'roomlist': 'F',
                    'modenable': 'T',
                    'deprestr': 'Closed',
                    'joinrestr': 'Closed',
                    'hidden': 'T'}
        else:
            return {'roomlist': 'T',
                    'modenable': 'F',
                    'deprestr': 'Closed',
                    'joinrestr': 'Closed',
                    'hidden': 'F'}

    # right now the restrictions are the same, but that may
    # change in the future
    def ret_valid_restrictions(self, variant='join'):
        """Return valid restriction types for Distribution Groups.

        This is a side-effect free utility function, altough it might not look
        like it if you use it "incorrectly" :)

        :type variant: basestring
        :param variant: 'join' for MemberJoinApprovalRequired, 'part' for
            MemberPartApprovalRequired."""
        if variant == 'join':
            return ['Open', 'Closed', 'ApprovalRequired']
        elif variant == 'depart':
            return ['Open', 'Closed', 'ApprovalRequired']
        else:
            raise self._db.IntegrityError, \
                "Only join and depart restriction are supported in the schema"

    def ret_standard_language(self):
        """Return standard language for DisplayName in Distribution Groups.

        :rtype: basestring
        :return: 'nb'."""
        return 'nb'

    def get_distgroup_attributes_and_targetdata(self,
                                                display_name_lang='nb',
                                                roomlist=False):
        """Collect information about Distribution Groups.

        :type display_name_lang: basestring
        :param display_name_lang: The language to use for DisplayName
            (default: 'nb').

        :type roomlist: bool
        :param roomlist: If true, returns roomlist-relevant information, else,
            returns Distribution Group relevant information."""
        all_data = {}
        ea = Email.EmailAddress(self._db)
        ed = Email.EmailDomain(self._db)
        et = Email.EmailTarget(self._db)
        epat = Email.EmailPrimaryAddressTarget(self._db)
        mngdby_address = ""
        primary_address = ""
        display_name = ""
        name_language = ""
        addrs = []
        mod_by = []
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

        # Fetch the managers address
        try:
            ea.find(self.mngdby_addrid)
        except Errors.NotFoundError:
            # Could not find the address recorded. this should never happen
            return None
        try:
            ed.find(ea.email_addr_domain_id)
        except Errors.NotFoundError:
            # Could not find the domain recorded. this should never happen
            return None
        mngdby_address = "%s@%s" % (ea.email_addr_local_part,
                                    ed.email_domain_name)

        # in roomlists we only care about name, description,
        # displayname and the roomlist-status, the other attributes
        # don't need to be set in Exchange
        if roomlist:
            all_data = {'name': self.group_name,
                        'description': self.description,
                        'displayname': display_name,
                        'group_id': self.entity_id,
                        'mngdby_address': mngdby_address,
                        'deprestr': self.deprestr,
                        'joinrestr': self.joinrestr,
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
            raise self._db.IntegrityError, \
                "No primary addresse registered for %s" % self.group_name
        ea.clear()
        ea.find(epat.email_primaddr_id)
        ed.clear()
        ed.find(ea.email_addr_domain_id)
        primary_address = "%s@%s" % (ea.email_addr_local_part,
                                     ed.email_domain_name)
        for r in et.get_addresses(special=True):
            ad = "%s@%s" % (r['local_part'], r['domain'])
            addrs.append(ad)
        tmp = self.modby.split(',')
        for x in tmp:
            y = x.strip()
            if y == '':
                continue
            # return a list of moderators
            mod_by.append(y)
        # name is expanded with prefix 'dl-' by the export
        all_data = {'name': self.group_name,
                    'description': self.description,
                    'displayname': display_name,
                    'group_id': self.entity_id,
                    'roomlist': self.roomlist,
                    'mngdby_address': mngdby_address,
                    'modenable': self.modenable,
                    'modby': mod_by,
                    'deprestr': self.deprestr,
                    'joinrestr': self.joinrestr,
                    'hidden': self.hidden,
                    'primary': primary_address,
                    'aliases': addrs}
        return all_data

    # exchange-relatert-jazz
    #
    # the following three methods could be placed into a separate
    # Email-mixin class for Distribution groups, but as there
    # are no clear plans to expand usage of mail functionality for
    # distribution groups we are, at this time, satisfied to let
    # them be a part of the main DistGroup-class. (Jazz, 2013-13)
    def create_distgroup_mailtarget(self):
        """Ensure MailTarget for DistributionGroups."""
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
        """Populate EmailTarget with a primary address for the Distribution Group.

        :type et: Cerebrum.modules.Email.EmailTarget
        :param et: The EmailTarget to auto-create primary address for.
        """
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
                raise self._db.IntegrityError, \
                    "Address %s is already taken!" % addr_str
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

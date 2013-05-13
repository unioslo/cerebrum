#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
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

from Cerebrum.modules.cis.Utils import CisModule, commit_handler, require_id

import cereconf
import cerebrum_path
from Cerebrum import Errors
from Cerebrum.Utils import Factory

# TODO: Note, this is work in progress, it's not complete by any stretch of the
#       imagination

#TODO: Cereconfs
cereconf.ALUMNI_ADMIN = 'fhl'
cereconf.ALUMNI_DEFAULT_OU = (90, 00, 00, 185)


class AlumniAccessor(object):
    """ An alumni accessor object. This object is used to get or set
    alumni-related info about a person / account.
    """
    def __init__(self, db, account_name):
        """ Set up a new accessor object

        @type account: Database
        @param account: A database connection

        @type account_name: str
        @param account_name_: The name of an account
        """
        self.account = Factory.get('Account')(db)
        self.person = Factory.get('Person')(db)
        self.const = Factory.get('Constants')(db)

        self.account.find_by_name(account_name)
        self.person.find(self.account.owner_id)

        # TODO: Maybe we could use this to access FS data as well? If so, we
        # need to make sure that it's read only!
        self.source_system = self.const.system_alumni
        
        # Set name source system and name types
        self.person.affect_names(self.source_system, 
                                 self.const.name_first,
                                 self.const.name_last)

        # This value is only a cache value for is_alumni(). It starts out
        # undefined. If we do something that might change alumni status, reset
        # it to None!
        self._is_alumni = None


    def is_alumni(self):
        """ If this object is defined as an alumni
        @rtype: bool
        @return: True if the object is an alumni, False otherwise
        """
        if self._is_alumni is None:
            self._is_alumni = bool(self.person.list_affiliations(
                person_id=self.person.entity_id,
                affiliation=self.const.affiliation_alumni,
                source_system=self.const.system_alumni,))
        assert self._is_alumni is not None
        return self._is_alumni

    
    def set_alumni(self, ou):
        """ Set alumni affiliation for this alumni """
        assert not self.is_alumni()
        assert self.source_system == self.const.system_alumni
        assert hasattr(ou, 'entity_id')
        self._is_alumni = None
        self.person.add_affiliation(ou.entity_id,
                                    self.const.affiliation_alumni,
                                    self.source_system, 
                                    self.const.affiliation_alumni_tilknyttet)
        self.person.write_db()


    def unset_alumni(self, ou=None):
        """ Unset alumni affiliation for this alumni """
        assert self.is_alumni()
        assert self.source_system == self.const.system_alumni
        assert hasattr(ou, 'entity_id') or ou is None
        self._is_alumni = None
        for aff in self.person.list_affiliations(
                person_id=self.person.entity_id,
                affiliation=self.const.affiliation_alumni,
                source_system=self.source_system):
            if ou is None or aff['ou_id'] == ou.entity_id:
                self.person.delete_affiliation(aff['ou_id'],
                                               aff['affiliation'],
                                               aff['source_system'])
        self.person.write_db()


    def get_name(self, type):
        """ Fetch the given name type for this alumni, if defined

        @type type: _PersonNameCode, or its int/str value
        @param type: The name type to get

        @rtype: str
        @return: The name, or None if no name is set.
        """
        type = self.const.PersonName(type)
        assert type in (self.const.name_first, self.const.name_last)
        try:
            return self.person.get_name(self.source_system, type)
        except Errors.NotFoundError:
            pass
        return None


    def set_name(self, type, name):
        """ Set the given name type for this alumni

        @type type: _PersonNameCode, or its int/str value
        @param type: The name type to set

        @type name: str
        @param name: The name to set
        """
        type = self.const.PersonName(type)
        assert self.is_alumni()
        assert self.source_system == self.const.system_alumni
        assert type in (self.const.name_first, self.const.name_last)
        self.person.populate_name(type, name)
        self.person.write_db()


    def get_contact(self, type):
        """ Fetch the email address of this alumni, if defined

        @rtype: str
        @return: The email address, or None if no email address is
                 set.
        """
        type = self.const.ContactInfo(type)
        assert type in (self.const.contact_email, self.const.contact_mobile_phone)
        try:
            return self.person.get_contact_info(source=self.source_system,
                                                type=type)[0]['contact_value']
        except (IndexError, Errors.NotFoundError):
            pass
        return None


    def set_contact(self, type, value):
        """ Set the email address of this alumni

        @type address: str
        @param address: The email address
        """
        type = self.const.ContactInfo(type)
        assert self.is_alumni()
        assert self.source_system == self.const.system_alumni
        assert type in (self.const.contact_email, self.const.contact_mobile_phone)
        self.person.add_contact_info(self.source_system, type, value)
        self.person.write_db()

    
    def get_address(self, type):
        """ Fetch the postal number or country for the address of this user

        @type type: str
        @param type: 'country' or 'postal_number'

        @rtype: int OR str OR None
        @return: The value of the address, or None if none was found
        """
        assert type in ('country', 'postal_number')
        try:
            addr = self.person.get_entity_address(
                    source=self.co.system_alumni, type=self.co.address_post)[0]
            return addr.get(type, None)
        except (IndexError, Errors.NotFoundError):
            pass
        return None


    def set_address(self, type, val):
        """ Set the postal number or country for the address of this user

        @type type: str
        @param type: 'country' or 'postal_number'

        @type val: int OR str
        @param val: The value to set the address to
        """
        assert type in ('country', 'postal_number')
        assert self.is_alumni()
        assert self.source_system == self.const.system_alumni

        if type == 'country':
            country = str(val)
            number = self.get_address('postal_number')
        elif type == 'postal_number':
            country = self.get_address('country')
            number = int(val)
        else:
            assert False, 'Never reached'
        
        self.person.populate_address(self.source_system, 
                                     type=self.co.address_post,
                                     postal_number=number,
                                     country=country,)
        self.person.write_db()


    def clear_alumni_info(self):
        """ Clear all alumni related info """
        assert self.is_alumni()
        assert self.source_system == self.const.system_alumni

        # TODO: Fjerne medlemsskap i alumni-grupper
        #
        self.unset_alumni()
        self.person.delete_name_with_language()
        self.person.delete_entity_address(self.source_system,
                                          self.co.address_post)
        self.person.delete_contact_info(self.co.source_system,
                                        self.co.contact_email)
        self.person.delete_contact_info(self.co.system_alumni,
                                        self.co.contact_mobile_phone)
    
        self.person.write_db()


    def to_dict(self):
        """ Returns all alumni info as a dictionary. The keys of this dict
        matches the attributes of cerebrum.servers.cis.SoapAlumniServer/Alumni
        """
        ret = {'uname': self.account.account_name,
               'bdate': self.person.birth_date,
               'gender': str(self.co.Gender(self.person.gender)), }

        ret['fname'] = self.get_name(self.const.name_first)
        ret['lname'] = self.get_name(self.const.name_last)
        ret['mobile'] = self.get_contact(self.const.contact_mobile_phone)
        ret['email'] = self.get_contact(self.const.contact_email)
        ret['addr_postal'] = self.get_address('postal_number')
        ret['addr_country'] = self.get_address('country')

        return ret


class FSAccessor(AlumniAccessor):
    # FIXME: Inheritance should be the other way around, maybe

    def __init__(self, db, account_name):
        super(FSAccessor, self).__init__(db, account_name)
        self.source_system = self.const.system_fs
    
    def set_name(self, *args, **kwargs):
        raise NotImplementedError('Not allowed to set name in %s' % self.source_system)

    def set_address(self, *args, **kwargs):
        raise NotImplementedError('Not allowed to set address in %s' % self.source_system)

    def set_contact(self, *args, **kwargs):
        raise NotImplementedError('Not allowed to set contact in %s' % self.source_system)

    def set_alumni(self, *args, **kwargs):
        raise NotImplementedError('Not allowed to set affiliations in %s' % self.source_system)

    def unset_alumni(self, *args, **kwargs):
        raise NotImplementedError('Not allowed to set affiliations in %s' % self.source_system)

    # We need to override this method if there's other constants in use. Also,
    # those constants needs to be added to the assertion in the appropriate
    # get_* method
    #def to_dict(self):
        #tmp = super(FSAccessor, self).to_dict()
        #tmp['mobile'] = self.get_contact(self.const.contact_private_mobile)
        #return tmp


class AlumniControl(CisModule):
    """This is the service interface with Cerebrum for all Alumni-related
    functionality.
    
    Attributes:
        dryrun: If bool(dryrun) is True, nothing gets commited unless
                self.commit is explicitly called.
    """
    dryrun = False
    
    def __init__(self, operator_id=None, dryrun=None):
        """Constructor. Since we are using access control, we need the
        authenticated entity's ID as a parameter.

        """
        super(AlumniControl, self).__init__('cis_alumni')

        self.const_class = Factory.get('Constants')
        self.person_class = Factory.get('Person')
        self.group_class = Factory.get('Group')

        self.co = self.const_class(self.db)

        # TODO: could we save work by only using a single, shared object of
        # the auth class? It is supposed to be thread safe.
        #self.ba = BofhdAuth(self.db)
        #

        self.operator_id = operator_id

        if dryrun is not None:
            dryrun = dryrun


    # TODO: This can't be the best way
    def get_default_ou(self):
        ou = Factory.get('OU')(self.db)
        def_ou = cereconf.ALUMNI_DEFAULT_OU
        ou.find_stedkode(*def_ou)
        return ou


    @require_id
    def is_admin(self):
        group = self.group_class(self.db)
        try:
            group.find_by_name(cereconf.ALUMNI_ADMIN)
        except Errors.NotFoundError:
            self.log.error("Couldn't find admin group '%s'" % cereconf.ALUMNI_ADMIN)
            raise

        return group.has_member(self.operator_id)


    # TODO:
    @require_id
    def is_alumni(self):
        raise NotImplementedError('TODO')
        # Check if self.operator_id is alumni.


    @require_id
    def can_get_alum_info(self, account_id):
        if self.is_admin():
            return True
        elif self.operator_id == account_id:
            return True
        return False


    def lookup_person_info(self, account_name):
        # TODO: Document
        # 
        # Look up operator ID (for use in FS, username?)
        # Return Cerebrum-data from system_cached or whatever

        # TODO: We should use the Alumni object here
        #       First, we must make it possible to change source system
        #       And ensure that all set_* methods ensures source system alumni
        # alumni = FSAccessor(self.db, account_name)
        # alumni.to_dict()
        #
        ret = dict()
        return ret


    @commit_handler(dryrun=dryrun)
    def clear(self, account_name):
        """ Clear all alumni related info """
        alumni = AlumniAccessor(self.db, account_name)
        alumni.clear_alumni_info()


    @commit_handler(dryrun=dryrun)
    def register_alum(self, alumni_info):
        """ New alumni

        alumni_info -> dict from SoapAlumniServer rpc wrapper
        """
        # TODO: Document

        # TODO: Do sanity check on alum input

        alumni = AlumniAccessor(self.db, alumni_info.get('uname'))

        # Already alumni
        if alumni.is_alumni():
            raise Errors.CerebrumRCPException(
                    "User '%s' already alumni" % alumni_info.get('uname'))

        alumni.set_alumni(self.get_default_ou())

        # Mandatory
        #
        alumni.set_name(self.co.name_first, alumni_info.get('fname'))
        alumni.set_name(self.co.name_last, alumni_info.get('lname'))

        alumni.set_address('country', alumni_info.get('addr_country'))
        alumni.set_address('postal_number', alumni_info.get('addr_number'))

        # Optional
        #
        if alumni_info.get('email', None):
            alumni.set_contact(self.co.contact_email, alumni_info.get('email'))

        if alumni_info.get('mobile', None):
            alumni.set_contact(self.co.contact_mobile_phone,
                               alumni_info.get('mobile'))

        # TODO: Group memberships
        #
        return True


    def set_alum_info(self, alumni_changes):
        # TODO: Document
        
        alumni = AlumniAccessor(self.db, alumni_changes.get('uname'))

        new_info = alumni_changes
        old_info = alumni.to_dict()
        diff_info = dict()

        # TODO: Maybe have an Alumni.update(dict)
        #       that does this and returns the changes?

        # FIXME: For now only returns changes
        for key, val in new_info.items():
            if key in ('bdate', 'gender', 'uname'):
                continue
            try:
                if val != old_info.get(key):
                    self.log.debug('Value differs: old (%s), new (%s)' %
                            (repr(old_info.get(key, None)), repr(val)))
                    diff_info[key] = val
            except KeyError:
                self.log.debug("No such attribute, '%s'" % key)

        # Check diff_info: Is operator allowed to change the fields?
        # Check diff_info: Are the fields valid?
        # If checks OK: Store changes
        # If checks bad: Throw error
        return diff_info


    #@require_id
    def get_alum_info(self, uname):
        """ All alumni-related information about a student. 

        @type uname: str
        @param uname: User name of the alumni

        @rtype: dict
        @return: A dictionary with the alumni-related information. All keys in
                 the dict should match a class type and variable in
                 C{Cerebrum.servers.cis.SoapAlumniServer:Alumni}.
        """
        # TODO: Access control
        #
        # TODO: Handle exceptions?
        alumni = AlumniAccessor(self.db, uname)
        return alumni.to_dict()


    # TODO: 
    def search(self, params):
        """ Search for alumnis, and lookup all related information about them.
        """
        raise NotImplementedError("TODO")


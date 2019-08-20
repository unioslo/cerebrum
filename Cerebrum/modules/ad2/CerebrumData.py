# -*- coding: utf-8 -*-
#
# Copyright 2011-2018 University of Oslo, Norway
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
"""
Module for making easier comparison of entities between Cerebrum and AD.

The object types in AD are organized differently than the entities in Cerebrum,
which is why we have the classes in here to cache and use the Cerebrum data for
AD more easily.

Some object types in AD we should be able to update:

- User: Like Users in Cerebrum, but with other attributes.
- Security group: Like Groups in Cerebrum.
- Distribution group: A combination of Groups in Cerebrum and mailing lists.
- Computer: A simple variety of hosts in Cerebrum.
- Contact: TODO

How the caching class(es) should be used:

::

    # 1. Instantiate the class with generic info:
    ent = CerebrumEntity(logger, ad-config, en.entity_id, en.entity_name)

    # 2. Add more data to the cache:
    ent.description = en.description
    ent.active = bool(en.get_quarantines())
    for atr in en.get_ad_attributes():
        ent.set_attribute(atr...)
    ...

    # 3. When syncing, set the L{in_ad} variable to tell that the entity was
    # found in AD.
    ent.in_ad = True

    # 4. Fill the L{ad_data} variable with data from AD if needed later.
    ent.ad_data['dn'] = ad_object['DistinguishedName']

Each class has a calc_ad_attrs method that defines the attributes which are to
be compared with attributes from data objects from AD.
"""

import cereconf

from Cerebrum.Utils import NotSet
from Cerebrum.modules.ad2 import ConfigUtils


class AttrNotFound(Exception):
    """Local exception for attributes that are not found."""
    pass


class CerebrumEntity(object):

    """A representation for a Cerebrum Entity which may be exported to AD.

    This entity cache is for making it easier to compare entities from Cerebrum
    with objects in Active Directory.

    Instances of this class should be given data from Cerebrum that could be
    used to compare with AD, and methods for comparing. In addition it contains
    a variable L{changes}, which contains a list of what should be updated in
    AD, which could at the end be used by an AD-sync for making updates.

    Certain variables are worth mentioning:

    - L{ad_id}: The Id for the object in AD. Use this to reference to the object
      in AD. This is generated from Cerebrum, so the object might not exist in
      AD, though. In powershell, you can reference to an object by:
        - DistinguishedName
        - GUID (objectGUID)
        - SamAccountName - The object will then be searched for in the current
                           OU and downwards.
      The easiest is to use the SamAccountName, as this should be equal to the
      CN in DN. If DN is given, we must know where the object is located. If
      GUID should be used, we must store this Id in Cerebrum to be able to use
      it.

    - L{changes}: A list of changes that should be sent to AD. This is filled
      after the entity has been compared with data from AD.

    - L{ad_data}: Data that is retrieved from AD for later use, e.g. for the
      membership sync that goes after the groups themselves has been synced. It
      is put into its own dict to separate it from what is generated from
      Cerebrum's data.

    TODO: Some reorganisation is needed: The class should do more for the sync.
    My guess is that the logic thing to do is to put all that treats _one_
    entity in here, and let ADSync only do what should be done for all entities.
    """

    def __init__(self, logger, config, entity_id, entity_name):
        """Set up the basic values for the entity.

        :type logger: Cerebrum.logutils.loggers.CerebrumLogger
        :param dict config: A configuration dict
        :param int entity_id: The Cerebrum id of the entity
        :param str entity_name: The Cerebrum name of the entity

        """
        self.logger = logger
        self.config = config

        self.entity_id = entity_id
        self.entity_name = entity_name

        # The Id for the related object in AD:
        nformat = self.config.get('name_format', '%s')
        if callable(nformat):
            self.ad_id = nformat(entity_name)
        else:
            self.ad_id = nformat % entity_name

        # Attributes that are defined in Cerebrum for the entity. The keys are
        # the attribute type, e.g. SamAccountName.
        self.attributes = dict()

        # Default states
        self.active = True      # if not quarantined in Cerebrum
        self.in_ad = False      # if entity exists in AD
        self.ad_new = False     # if entity was just created in AD

        # Variable for being filled with data from AD when syncing, for later
        # use, e.g. for syncing group members.
        self.ad_data = dict()

        # Changes contains attributes that should be updated in AD:
        self.changes = dict()

        # Set the default target OU, to set where the object should be in AD.
        # Subclasses of CerebrumEntity or ADSync could change this, so that
        # different objects are put in various AD OUs.
        self.ou = self.config['target_ou']

        # A list of spreads registered on the entity. Could be used to e.g. give
        # users with spread to Exchange or Lync extra attributes. Might not be
        # filled with spreads if not needed, this depends on the configuration.
        self.spreads = []

        # Other information that _could_ get registered for the entity,
        # depending on what is needed by adconf, and what is hardcoded in the
        # sync's subclasses:

        # Attributes from the AD attribute table in Cerebrum
        self.cere_attributes = dict()
        # Names with language, e.g. for OUs and person titles
        self.entity_name_with_language = dict()
        # Postal addresses
        self.addresses = dict()
        # External IDs, like fnr and student number
        self.external_ids = dict()
        # Traits needed e.g. for attributes
        self.traits = dict()
        self.forwards_data = {}

        # TODO: Move extra settings to subclasses. This should not be here!
        self.update_recipient = False  # run update_Recipients?

    def __str__(self):
        """A string representation of the entity. For debugging."""
        return "%s (%s)" % (self.entity_name, self.entity_id)

    def calculate_ad_values(self):
        """Calculate entity values for AD from Cerebrum data.

        Sets up the automatic AD attributes, for those which hasn't already.
        The object has to be fed with all the needed data from Cerebrum before
        calling this method.

        """
        # Some standard attributes that we don't support setting otherwise:
        self.set_attribute('Name', self.ad_id)
        self.set_attribute('DistinguishedName', self.dn)
        # Attributes defined by the config:
        for atrname, config in self.config['attributes'].iteritems():
            # Some attributes are not configured, but e.g. defined as None in
            # the config. We expect those to be handled by subclasses and ignore
            # them here:
            if not isinstance(config, (ConfigUtils.AttrConfig, list, tuple)):
                continue
            if not isinstance(config, (list, tuple)):
                config = (config,)
            for c in config:
                try:
                    value = self.find_ad_attribute(c)
                except AttrNotFound:
                    continue
                self.set_attribute(atrname, value, c)
                break

    def find_ad_attribute(self, config):
        """Find a given AD attribute in its raw format from the Cerebrum data.

        The configuration says where to find the attribute value, and by what
        filtering, e.g. the prioritised order of source system that should be
        searched first.

        @type config: ConfigUtils.AttrConfig
        @param config:
            The configuration for what value to be fetched from Cerebrum.

        @rtype: mixed
        @return:
            The attribute value, if found. Note that None could also be found
            for an attribute.

        @raise AttrNotFound:
            Raised in cases where the attribute was not set for the entity.

        """
        # TODO: This could be cleaned up, e.g. by one or more helper methods.

        # Check the criterias for the attribute first:
        if getattr(config, 'criterias', False):
            try:
                config.criterias.check(self)
            except ConfigUtils.CriteriaError:
                raise AttrNotFound('Attribute criterias not fullfilled')
        # TODO: Remove this when done migrating to the criteria class:
        if getattr(config, 'spread', False):
            if not any(s in config.spread for s in self.spreads):
                raise AttrNotFound('Attribute criterias not fullfilled')

        if isinstance(config, ConfigUtils.ContactAttr):
            # ContactInfo
            # The dict self.contact_info has the format:
            # contact_info[str(contact_type)][str(source_system)] = value
            for c in config.contact_types:
                if str(c) not in self.contact_info:
                    continue
                sources = self.contact_info[str(c)]
                if config.source_systems:
                    for s in config.source_systems:
                        value = sources.get(str(s))
                        if value:
                            return value
                else:
                    # TODO: now it's not sorted, need to make use of the
                    #       default order from cereconf!
                    for value in sources.itervalues():
                        return value
        elif isinstance(config, ConfigUtils.PersonNameAttr):
            # PersonName
            for vari in config.name_variants:
                vinfos = self.person_names.get(str(vari))
                if vinfos is None:
                    continue
                if config.source_systems:
                    for s in config.source_systems:
                        value = vinfos.get(str(s))
                        if value:
                            return value
                else:
                    # TODO: Use default order for source_systems.
                    for value in vinfos.itervalues():
                        return value
        elif isinstance(config, ConfigUtils.NameAttr):
            # EntityName or PersonName
            for vari in config.name_variants:
                vinfos = self.entity_name_with_language.get(str(vari))
                if vinfos is None:
                    continue
                if getattr(config, 'languages', None):
                    for l in config.languages:
                        name = vinfos.get(str(l))
                        if name:
                            return name
                else:
                    # Not sorted by language, fetch first.
                    # TODO: Need to use a default order for this!
                    for name in vinfos.itervalues():
                        return name
        elif isinstance(config, ConfigUtils.ExternalIdAttr):
            # External IDs
            for itype in config.id_types:
                infos = self.external_ids.get(str(itype))
                if infos is None:
                    continue
                if getattr(config, 'source_systems', None):
                    for s in config.source_systems:
                        sys = infos.get(str(s))
                        if sys:
                            return sys
                else:
                    # TODO: use default sort order from config!
                    for s in infos.itervalues():
                        return s
        elif isinstance(config, ConfigUtils.AddressAttr):
            # Addresses
            for adrtype in config.address_types:
                ainfos = self.addresses.get(str(adrtype))
                if ainfos is None:
                    continue
                if getattr(config, 'source_systems', None):
                    for s in config.source_systems:
                        sys = ainfos.get(str(s))
                        if sys:
                            return sys
                else:
                    # TODO: now it's not sorted, need to make use of the
                    # default order from cereconf!
                    for s in ainfos.itervalues():
                        return s
        elif isinstance(config, ConfigUtils.ADAttributeAttr):
            # AD attributes from Cerebrum's attribute table
            for attr in config.attributes:
                a = self.cere_attributes.get(int(attr))
                if a:
                    return a
        elif isinstance(config, ConfigUtils.TraitAttr):
            # Traits
            for code in config.traitcodes:
                tr = self.traits.get(str(code))
                if tr:
                    return tr
        elif isinstance(config, ConfigUtils.PosixAttr):
            # POSIX data, return all data and let transform set what's needed
            if getattr(self, 'posix', False):
                return self.posix
        elif isinstance(config, ConfigUtils.HomeAttr):
            # Home Directory, set by given home_spread
            if config.home_spread in getattr(self, 'home', {}):
                return self.home[config.home_spread]
        elif isinstance(config, ConfigUtils.EmailAddrAttr):
            # Email Addresses
            adr = self.maildata.get('alias')
            prim = self.maildata.get('primary')
            if adr:
                return {'alias': adr, 'primary': prim}
        elif isinstance(config, ConfigUtils.EmailQuotaAttr):
            # Email Quota
            if 'quota' in self.maildata:
                return self.maildata['quota']
        elif isinstance(config, ConfigUtils.EmailForwardAttr):
            # Email Forward
            if self.maildata.get('forward'):
                return self.maildata['forward']
        elif isinstance(config, ConfigUtils.MemberAttr):
            # Member attribute for groups
            if hasattr(self, 'members_by_spread'):
                # Return only those members who have the spread
                # defined in this attribute
                return [member for member in self.members_by_spread
                        if any(spr in member.spreads
                               for spr in config.member_spreads)]
        elif isinstance(config, ConfigUtils.CallbackAttr):
            # A callback for an attribute
            return config.callback(self)

        # Use default value, if defined by config:
        if (isinstance(config, ConfigUtils.AttrConfig) and
                config.default is not NotSet):
            # Add some substitution data to be used for strings: TODO: Should we
            # include all the attributes for the entity that contains primitive
            # values in here? Would then for instance be able to include
            # 'description' for groups, for instance. The downside is that it is
            # a bit internal, and might change in the future.
            return config.default
        raise AttrNotFound('No attribute found after attr config')

    def set_attribute(self, key, value, config=None, force=False,
                      transform=True):
        """Setting an attribute for the entity.

        An attribute is only set if the key is defined in the config, and could
        normally only be set once, the first set value is used, unless L{force}
        is True. This is so that you could start with setting special values,
        and end with less important values, like default values.

        Some extra data is given to the attribute, e.g. through. string
        substitutions. Also, if the attribute is defined with a L{transform}
        function in the given config, this is called when setting the attribute.

        @type key: string
        @param key: The name of the attribute that wants to be set.

        @type value: str, unicode, tuple or list
        @param value:
            The value of the attribute that wants to be set. Note that str gets
            converted to unicode, to make it easier to compare with AD.

        @type config: ConfigUtils.AttrConfig or None
        @param config:
            If set, the tweaks from the config is used, e.g. L{transform}.

            TODO: We should probably always fetch and use the configuration, if
            set in `adconf`. We might still want to be able to override by this
            parameter, though.

        @type force: bool
        @param force:
            If the attribute should be set even though it has already been set.
            Should be False if values are calculated.

        @type transform: bool
        @param transform:
            If the transform should be called for the input value or not, if it
            is defined in the configuration for the attribute.

        @rtype: bool
        @return: True only if the attribute got set.

        """
        # Skip if attribute is not defined
        # TODO: compare with lowercase only? Not sure how, and when, AD compare
        # with or without case sensitivity, so haven't done so yet.
        if key not in self.config['attributes']:
            return False
        # Skip if attribute is already set
        if not force and key in self.attributes:
            return False

        if isinstance(value, str):
            # This will fail if str contains special characters. Input should
            # rather be in unicode by default, but that is not always as easy to
            # do everywhere. Should rather be using from __future__ import
            # unicode_literals. Remove this when fully migrated to unicode!
            value = unicode(value)

        # Remove whitespace before and after data. AD is stripping this out when
        # saving the value, so if we strip too, the comparing gets easier.
        if isinstance(value, basestring):
            value = value.strip()
            # TODO: also remove double white spaces from all attributes?

        if transform and hasattr(config, 'transform'):
            value = config.transform(value)
        value = self._add_attribute_data(value)
        self.attributes[key] = value
        return True

    def _add_attribute_data(self, value):
        """Add extra common data to a value, i.e. string substitute in elements.

        Some common elements, like the L{ad_id}, L{entity_id} and L{ou} could
        be added in to attribute strings by regular string substitution.

        Example on a given value:

            'group-%(ad_id)s'

        could for different entities be returned as:

            'group-cerebrum'
            'group-root'
            'group-david'

        @type value: mixed
        @param value:
            The given AD attribute that should be set. Only some data types are
            modified. List and tuples are handled recursively.

        @rtype: mixed
        @return:
            Return either the input value or a modified version of the input
            value.

        """
        if isinstance(value, (tuple, list)):
            return tuple(self._add_attribute_data(e) for e in value)
        if isinstance(value, basestring):
            return value % {'entity_name': self.entity_name,
                            'entity_id': self.entity_id,
                            'ad_id': self.ad_id,
                            'ou': self.ou, }
        return value

    @property
    def dn(self):
        """ Return the DistinguishedName for this Entity.

        :rtype: basestring
        :returns: The formatted DistinguishedName.

        """
        return 'CN=%s,%s' % (self.ad_id, self.ou)


class CerebrumUser(CerebrumEntity):
    """A representation for a Cerebrum Account which may be exported to AD.

    An instance contains information about one Account from Cerebrum and
    methods for comparing this information with the data from AD.

    TODO: Some reorganisation is needed.

    """

    def __init__(self, logger, config, entity_id, entity_name, owner_id=None,
                 owner_type=None):
        """ CerebrumUser constructor

        @type owner_id: int
        @param owner_id: The entity_id for the owner of the user, e.g. a person
            or group.

        """
        super(CerebrumUser, self).__init__(logger, config, entity_id,
                                           entity_name)
        self.owner_id = owner_id
        self.owner_type = owner_type
        self.contact_info = {}
        self.external_ids = {}
        self.person_names = {}
        self.is_primary_account = False

        # TODO: Make use of self.email_addresses = {}, or should this be in a
        # subclass?

        # default values
        # self.email_addrs = list()
        # self.contact_objects = list()

    def calculate_ad_values(self):  # exchange=False):
        """Calculate entity values for AD from Cerebrum data.

        TODO: How to calculate AD attr values from Cerebrum data and policy
              must be hardcoded somewhere. Do this here?

        """
        super(CerebrumUser, self).calculate_ad_values()
        self.set_attribute('Enabled', bool(self.active))
        # TODO: how to store ACCOUNT_CONTROL?

    def add_forward(self, forward_addr):
        contact = CerebrumContact(self.ad_attrs["displayName"], forward_addr,
                                  self.config['domain'], )
        self.contact_objects.append(contact)

    def create_dist_group(self):
        name = getattr(cereconf, "AD_FORWARD_GROUP_PREFIX", "") + self.uname
        # TBD: cereconf?
        description = "Forward group for " + self.uname
        dg = CerebrumDistGroup(name, description)
        dg.calc_ad_attrs()


class PosixCerebrumUser(CerebrumUser):
    """A posix user from Cerebrum, implementing extra attributes for POSIX data.

    This is a simple class, only for updating the correct attributes by given
    data. The object must be fed with data inside the object variable L{posix}.

    TODO: This is deprecated, use AttrConfig.PosixAttr instead for setting the
    POSIX values, as that is independent of attribute name and entity type.

    """
    def __init__(self, *args, **kwargs):
        """Making the object ready for posix data."""
        super(PosixCerebrumUser, self).__init__(*args, **kwargs)
        self.posix = dict()


class MailTargetEntity(CerebrumUser):
    """An entity with Mailtarget, which becomes a Mail-object in Exchange.

    This is where the generic mail data from Cerebrum is treated to generate
    Exchange attributes.

    Note that the object's L{spread_to_exchange} must be set to True for the
    Exchange attributes to be set and generated. This is since entities could
    have a mailtarget, but not an Exchange spread.

    """
    def __init__(self, *args, **kwargs):
        """Making the object ready for the mailtarget."""
        super(MailTargetEntity, self).__init__(*args, **kwargs)
        self.maildata = dict()


class CerebrumContact(CerebrumEntity):
    """
    This class contains forward info for a Cerebrum account.

    """
    def __init__(self, name, forward_addr, domain, ou):
        """
        CerebrumContact constructor

        @param name: Owners name
        @type name: str
        @param forward_addr: forward address
        @type forward_addr: str
        """
        CerebrumEntity.__init__(self, domain, ou)
        # forward_attrs contains values calculated from cerebrum data
        self.forward_attrs = dict()
        self.name = name
        self.forward_addr = forward_addr

    def __str__(self):
        return self.name

    def calc_forward_attrs(self):
        """
        Calculate forward attributes for the accounts with forward
        email addresses.
        """
        self.forward_attrs["name"] = "Contact for " + self.name
        self.forward_attrs["displayName"] = "Contact for " + self.name
        self.forward_attrs["mail"] = self.forward_addr
        self.forward_attrs["mailNickname"] = self.forward_addr
        self.forward_attrs["sAMAccountName"] = "contact_for_" + self.forward_addr
        self.forward_attrs["proxyAddresses"] = self.forward_addr
        self.forward_attrs["msExchPoliciesExcluded"] = True
        self.forward_attrs["msExchHideFromAddressLists"] = True
        self.forward_attrs["targetAddress"] = self.forward_addr


class CerebrumGroup(CerebrumEntity):
    """A representation of a Cerebrum group which may be exported to AD.

    An instance contains information from Cerebrum and methods for
    comparing this information with the data from AD.

    TODO: some reorganisation is needed.

    """
    def __init__(self, logger, config, entity_id, entity_name,
                 description=None):
        """CerebrumGroup constructor."""
        super(CerebrumGroup, self).__init__(logger, config, entity_id,
                                            entity_name)
        self.description = description
        self.ad_dn = None

    def calculate_ad_values(self):
        """Calculate entity values for AD from Cerebrum data.

        TODO: How to calculate AD attr values from Cerebrum data and policy
              must be hardcoded somewhere. Do this here?

        """
        super(CerebrumGroup, self).calculate_ad_values()
        self.set_attribute('Description', getattr(self, 'description', None))
        # TODO: any changes to this? Should it be formatted else than
        # DisplayName?


class CerebrumDistGroup(CerebrumGroup):
    """
    This class represent a virtual Cerebrum distribution group that
    contain contact objects.
    """
    def __init__(self, gname, group_id, description, domain, ou):
        """
        CerebrumDistGroup constructor

        @param name: Cerebrum group name
        @type name: str
        @param group_id: Cerebrum id
        @type group_id: int
        @param description: Group description
        @type description: str
        """
        CerebrumGroup.__init__(self, gname, group_id, description, domain, ou)
        # Dist groups should be exposed to Exchange
        self.to_exchange = True

    def add_change(self, attr_type, value):
        """
        Add attribute type and value that is to be synced to AD. Some
        attributes changes must be sent to Exchange also. If that is
        the case set update_recipient to True

        @param attr_type: AD attribute type
        @type attr_type: str
        @param value: AD attribute value
        @type value: varies
        """
        self.changes[attr_type] = value
        # Should update_Recipients be run for this dist group?
        if (not self.update_recipient and
                attr_type in cereconf.AD_DIST_GRP_UPDATE_EX):
            self.update_recipient = True

    def calc_ad_attrs(self):
        """
        Calculate AD attrs from Cerebrum data.

        How to calculate AD attr values from Cerebrum data and policy
        must be hardcoded somewhere. Do this here and try to leave the
        rest of the code general.
        """
        # Read which attrs to calculate from cereconf
        ad_attrs = dict().fromkeys(cereconf.AD_DIST_GRP_ATTRIBUTES, None)
        ad_attrs.update(cereconf.AD_DIST_GRP_DEFAULTS)

        # Do the hardcoding for this sync.
        ad_attrs["name"] = self.gname
        ad_attrs["displayName"] = cereconf.AD_DIST_GROUP_PREFIX + self.gname
        ad_attrs["description"] = self.description or "N/A"
        ad_attrs["displayNamePrintable"] = ad_attrs["displayName"]
        ad_attrs["distinguishedName"] = "CN=%s,%s" % (self.gname, self.ou)
        # TODO: add mail and proxyAddresses, etc

        self.ad_attrs.update(ad_attrs)

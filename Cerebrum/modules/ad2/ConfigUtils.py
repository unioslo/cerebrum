# -*- coding: utf-8 -*-
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
"""Configuration functionality for the Active Directory synchronisation.

The AD sync is a bit configurable, to be able to fulfill most needs without
having to develop complex subclasses for each instance. It tries to be flexible,
at the cost of a bit more thorough and complicated configuration.

Each setting should be well commented in this file, to inform developers and
sysadmin about the usage and consequences of the setting.

The classes in this file is normally instantiated in L{adconf.py}, in each
sync's 'attribute' element.

You have, for now, mainly two types of config classes in this file,
L{AttrConfig} and L{AttrCriterias}. The L{AttrConfig} class adds settings for
how to set and control what a given attribute should contain, and the
L{AttrCriterias} sets the requirements that needs to be fullfilled for the
L{AttrConfig} object it belongs should be used.

Each element in a sync's 'attribute' dict could be defined with L{AttrConfig}
class or a list thereof. A short example on how the config classes are used:

    'attributes': {
        'DisplayName': ConfigUtils.PersonNameAttr(
                            name_variant=co.name_full
                            source_system=co.system_fs),
        'Description': (ConfigUtils.NameAttr(
                            name_variant=(co.personal_title, co.work_title),
                            criterias=ConfigUtils.AttrCriterias(
                                            spread=co.spread_lms)),
                        ConfigUtils.TraitAttr(
                            trait_type=co.trait_description
                            # Traits contain both a strval and a numval:
                            transform=lambda tr: tr['strval'].strip(),
                            default={'strval': 'N/A'),
                        ),
        },

"""

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory, NotSet

# Note that the constants object is not instantiated, as we only need type
# checking in here.
const = Factory.get('Constants')

class ConfigError(Exception):
    """Exception for configuration errors."""
    pass

class CriteriaError(Exception):
    """Exception for when a AttrCriterias is not fullfilled."""
    pass

# TODO: Add classes(?) for setting what default values should be, e.g. "NotSet"
# (elns) for telling that the given attribute should not be overridden in AD if
# this value occurs. This could e.g. be for avoiding to set attributes that
# should only be set for given objects, while all the other objects should keep
# their original value, administrered by the AD administrators - Not sure if we
# should allow this, though - why not set attributes for all entities through
# bofh?

class AttrConfig(object):
    """Configuration settings for an AD attribute.

    This class, and its subclasses, is used to specify what a given attribute
    should contain of information. The configuration is then used by the AD sync
    to feed the given attribute with the values from db that matches these
    criterias.

    """
    def __init__(self, default=NotSet, transform=None, spread=None,
                 source_systems=None, criterias=None):
        """Setting the basic, most used config variables.

        @type default: mixed
        @param default:
            The default value to set for the attribute if no other value is
            found. Note that if this is a string, it is able to use some of the
            basic variables for the entities: 
            
                - entity_name
                - entity_id
                - ad_id
                - ou

            Use these through regular substition, e.g. "%(ad_id)s".

            Also note that default values will also be using the L{transform}
            function for its data, so if you set up a config with special
            elements like dicts, you need to feed the default value with the
            same format.

            Note that L{default} is NOT set if the given criterias is not
            matched for the entity. L{default} is only used if the criterias are
            fullfilled but Cerebrum does not have the needed data for the given
            entity.

        @type transform: function
        @param transform:
            A function, e.g. a lambda, that should process the given value
            before sending it to AD. This could for instance be used to strip
            whitespace, or lowercase strings. For instance:

                lambda x: x[1:].lower()

            though this specific example could be simplified:

                string.lower

        @type spread: SpreadCode or sequence thereof
        @param spread:
            TODO: The spread argument rather belongs to AttrCriterias. Remove
            this when done updating adconf settings.

            If set, defines what spread the entity must have for the value to be
            set. If a sequence is given, the entity must have at least one of
            the spreads. Entitites without any of the given spreads would get
            this attribute blanked out.

            Note that spreads were originally meant to control what systems
            information should get spread to - here we use it for modifying what
            information goes over to a system, which could be discussed if is
            wrong use of the spread definition. Therefore, use with care, to
            avoid complications in the other parts of the business logic.

            TODO: This should be moved into AttrCriterias

        @type criterias: AttrCriterias
        @param criterias:
            A class that sets what criterias must be fullfilled before a value
            could be set according to this ConfigAttr. This object is asked
            before the given config is used. This includes the L{default}
            setting, which is not set if the given criterias is not fullfilled.

        @type source_systems: AuthoritativeSystemCode or sequence thereof
        @param source_systems:
            One or more of the given source systems to retrieve the information
            from, in prioritised order. If None is set, the attribute would be
            given from any source system (TODO: need a default order for such).

        # TODO: Should attributes behave differently when multiple values are
        # accepted? For instance with the contact types.

        """
        self.default = default
        if transform:
            self.transform = transform
        self.source_systems = _prepare_constants(source_systems,
                                                      const.AuthoritativeSystem)
        self.spread = _prepare_constants(spread, const.Spread)
        if criterias and not isinstance(criterias, AttrCriterias):
            raise ConfigError('Criterias is not an AttrCriterias object')
        self.criterias = criterias

def _prepare_constants(input, const_class):
    """Prepare and validate given Cerebrum constant(s).

    @type input: Cerebrum constant or sequence thereof or None
    @param input: The constants that should be used.

    @type const_class: CerebrumCode class or sequence thereof
    @param const_class:
        The class that the given constant(s) must be instances of to be valid.
        If a sequence is given, the constants must be an instance of one of the
        classes.

    @rtype: sequence of Cerebrum constants
    @return: Return the given input, but makes sure that it is iterable.

    """
    if input:
        if not isinstance(input, (list, tuple, set)):
            input = (input,)
        for i in input:
            if not isinstance(i, const_class):
                raise ConfigError('Not a %s: %s (%r)' % (const_class, i, i))
    return input

class ContactAttr(AttrConfig):
    """Configuration for an attribute containing contact info.

    This is used for attributes that should contain data that is stored as
    contact info in Cerebrum. 

    Note that the contact information consist of different elements:

        - contact_value
        - contact_alias
        - contact_pref
        - description

    """
    def __init__(self, contact_types, *args, **kwargs):
        """Initiate a contact info variable.

        @type contact_types: str or sequence thereof
        @param contact_types: One or more of the contact types to use, in
            priority, i.e. the first contact type is used if it exists for an
            entity, otherwise the next one. The contact types are identified by
            their L{code_str}.

        """
        super(ContactAttr, self).__init__(*args, **kwargs)
        self.contact_types = _prepare_constants(contact_types,
                const.ContactInfo)

class NameAttr(AttrConfig):
    """Configuration for attributes that should contain a name.

    This is not the same as entity_name. There are another name table in
    Cerebrum that contains names in different variant, and with different
    languages. Also, persons have their own table - this is used for accounts.

    Since this configuration class both accepts entity names and person names,
    it behaves a bit differently for the entity_types.

    """
    def __init__(self, name_variants, languages=None, *args, **kwargs):
        """Initiate a name attribute.

        @type name_variants: PersonName (constant) or sequence thereof
        @param name_variants: The defined name variants to retrieve.

        @type languages: LanguageCode or sequence thereof
        @param languages: If set, it specifies that only names in these
            languages should be used.

        """
        super(NameAttr, self).__init__(*args, **kwargs)
        self.name_variants = _prepare_constants(name_variants,
                                                     (const.EntityNameCode,
                                                      const.PersonName))
        self.languages = _prepare_constants(languages, const.LanguageCode)

class PersonNameAttr(AttrConfig):
    """Configuration for attributes that should contain person names.

    This is for personal accounts, and it is not the same as entity_name but is
    in its own db table.

    """
    def __init__(self, name_variants, *args, **kwargs):
        """Initiate a person name attribute.

        @type name_variants: PersonName (constant) or sequence thereof
        @param name_variants: The defined name variants to retrieve.

        """
        super(PersonNameAttr, self).__init__(*args, **kwargs)
        self.name_variants = _prepare_constants(name_variants,
                                                     const.PersonName)

class AddressAttr(AttrConfig):
    """Config for attributes with addresses, or parts of an address.

    """
    def __init__(self, address_types, *args, **kwargs):
        """Initiate an address attribute.

        Note that each address is a dict and not a string. You therefore need to
        use L{transform} to set the proper variable(s) you would like. Each
        address consists of the elements:
        
                - address_text
                - p_o_box
                - postal_number
                - city
                - country

        Example on a transform callable::

            lambda adr: adr['postal_number']

        which would for instance return::
        
            0360

        You could also combine elements::

            def adrformat(adr)
                if adr['p_o_box']:
                    return u'%s, %s' % (adr['address_text'], adr['p_o_box'])
                return adr['address_text']

        which could return::

            "Problemveien 1"
            "Problemveien 1, Postboks 120"

        Note that the element "country" is a reference to a Country code::

            lambda adr: co.Country(adr['country']).country

        which would give::

            "Sweden"

        @type address_types: AddressCode or sequence thereof
        @param address_types: What addresses to fetch and use, in prioritised
            order. The first available for an entity is used.

        """
        super(AddressAttr, self).__init__(*args, **kwargs)
        self.address_types = _prepare_constants(address_types,
                                                     const.Address)

class ExternalIdAttr(AttrConfig):
    """Config for attributes using external IDs.

    """
    def __init__(self, id_types, *args, **kwargs):
        """Initiate a config for given external IDs.

        @type id_types: EntityExternalIdCode or sequence thereof
        @param id_types: What external ID types to use, in prioritized order.

        """
        super(ExternalIdAttr, self).__init__(*args, **kwargs)
        self.id_types = _prepare_constants(id_types,
                const.EntityExternalId)

class TraitAttr(AttrConfig):
    """Config for attributes retrieved from traits.

    """
    def __init__(self, traitcodes, *args, **kwargs):
        """Initiate a config for given traits.

        Note that each trait is a dict that contains different elements, like
        strval and numval, and must therefore be wrapped e.g. through
        L{transform}.

        This might be expanded later, if more criterias are needed.

        @type traitcodes: EntityTraitCode or sequence thereof
        @param traitcodes: What trait types to use, in prioritised order.

        """
        super(TraitAttr, self).__init__(*args, **kwargs)
        self.traitcodes = _prepare_constants(traitcodes, const.EntityTrait)

class CallbackAttr(AttrConfig):
    """A special attribute, using callbacks with the entity as the argument.

    This class should normally not be used, as it requires internal knowledge of
    how the entity object works, and it will also make the adconf a bit more
    complex. Use this only if no other alternative is possible. The plus side of
    this, is that we don't have to create subclasses for every single weird
    attribute that is needed.

    Example on usage:

        'DNSHostName': ConfigUtils.CallbackAttr(
                        lambda ent: getattr(ent, 'hostname', '')
                        ),

    """
    def __init__(self, callback, *args, **kwargs):
        """Initiate a config for a callback attribute.

        @type callback: callable
        @param callback: The callable to run for each entity.

        """
        if not callable(callback):
            raise ConfigError("Argument is not callable: %s" % callback)
        super(CallbackAttr, self).__init__(*args, **kwargs)
        self.callback = callback

# TODO: Need to figure out how to implement different config classes for various
# settings that is not related to Cerebrum constants. Should we create one class
# for all small things, e.g. one for UidAttr, and one for GidAttr?

# TODO: Would we be in need of attributes that combines data from different
# elements? E.g. a join of two different traits, the person name and a spread?
# The config does not handles such needs now, would then have to code it into a
# subclass of the AD sync instead.

# Config for the Mail module

class EmailAddrAttr(AttrConfig):
    """Config for all e-mail addresses for an entity from the Email module.

    Note that each given value contains the elements:
    
        - primary (string): The primary e-mail address for the entity.
        - alias (list of strings): A list of all the e-mail aliases for the
          entity.

    You would like to use L{transform} or other methods to set what you want for
    the given attribute.

    """
    pass

class EmailQuotaAttr(AttrConfig):
    """Config for e-mail quota, using the Email module in Cerebrum.

    Note that the mailquota consists of the elements:

        - quota_soft
        - quota_hard

    You would therefore need to e.g. use L{transform}.

    """
    pass

class EmailForwardAttr(AttrConfig):
    """Config for e-mail forward addresses for an entity from the Email module.

    Only active forward addresses are used, i.e. those that has status 'enable'
    set to 'T' and not 'F'. The resulting value is a list of all the forward
    addresses, so you would like to use L{transform} or other methods to set
    what you want for the given attribute.

    """
    pass

class PosixAttr(AttrConfig):
    """Config for POSIX data, like GID, UID, shell and gecos.

    It is possible to sync posix data, like GID, with AD, for instance for
    environments that should support both environments where both UNIX and AD is
    used. Note, however, that AD needs to include an extra schema before the
    posix attributes could be populated.

    This class makes available a dict with the elements:

        - uid: int or empty string
        - gid: int or empty string
        - shell: string, strcode of a PosixShell constant, e.g. "bash"
        - gecos: string, free text

    One of these could for instance be set through the L{transform} method, e.g:

        lamba posix: posix.get('shell', '<N/A>')

    Note that regular Cerebrum PosixGroups does not have anything set else than
    GID.

    """
    # TODO: Should we have some shortcut settings, for making the config easier?
    pass

class HomeAttr(AttrConfig):
    """Config for account's home directories.

    The attribute data generated for the HomeAttr is a dict with information
    about the home registered for the given home spread. The dict contains the
    elements:

        - homedir (str): The full path to the homedir of the account, as how the
                         Account object defines how it should be. Note that if
                         you need the path in a different format, you probably
                         want to subclass the L{account.resolve_homedir} for the
                         given instance instead of tweaking it here with
                         L{transform}.
        - home_spread (int): The spread for the home directory.
        - status (int): The code from the AccountHomeStatus for the homedir,
                        that could e.g. represent that the homedir is created,
                        archived or failed to be created. Use
                        "str(co.AccountHomeStatus(status))" to get a readable
                        status.

    """
    def __init__(self, home_spread, *args, **kwargs):
        """Initiate a config for a home directory attribute.

        @type home_spread: SpreadCode
        @param home_spread:
            The spread for the homedir that should be used. An account is
            allowed to have different home directories per system. Note that
            only one spread is allowed and supported, as only one home directory
            is used per system.

        """
        super(HomeAttr, self).__init__(*args, **kwargs)
        if not isinstance(home_spread, const.Spread):
            raise ConfigError('Not a Spread: %s' % (home_spread,))
        self.home_spread = home_spread

class AttrCriterias(object):
    """Config class for setting criterias for entities' AttrConfigs.

    Each AttrConfig object could be set up with an AttrCriterias for defining
    what criterias that must be fullfilled for the AttrConfig to be set. By
    having the criterias in its own classes, we make it easier to gather the
    exact data that is needed from Cerebrum to check the criterias. The
    criterias will in some situations be too limited, which makes it possible to
    use a callback.

    """
    def __init__(self, spreads=None, callback=None):
        """Set up the initial criterias.

        @type spreads: SpreadCode or list thereof
        @param spreads:
            If set, defines that at least one of the spreads must be set for the
            entity to allow the given AttrConfig to be set.

        @type callback: callable
        @param callback: 
            If flexibility is needed, you could use this callback for generating
            a more specific criteria. The callable must accept one argument, a
            L{CerebrumEntity} object, and must return True to tell that the
            criteria was fullfilled.

            Note however that the sync does not know what data the callable
            needs, so that has to be gathered manually (TODO: or we should
            extend the config to force the retrieval of specific data elements
            from Cerebrum).

            Note that any other given criterias in the object must also be
            fullfilled for the AttrConfig to be set.

        """
        self.spreads = _prepare_constants(spreads, const.Spread)
        if callback:
            if not callable(callback):
                raise ConfigError("Criteria not callable: %s" % callback)
            self.callback = callback

    def check(self, ent):
        """Check all the defined criterias.

        TBD: Should this functionality be in ConfigUtils, or should it be moved
        to CerebrumData or some other place?

        @type ent: CerebrumEntity
        @param ent:
            The given entity which should be checked for criterias.

        @raise CriteriaError:
            Raised if any of the criterias is not fullfilled.

        """
        if self.spreads:
            if not any(s in self.spreads for s in ent.spreads):
                raise CriteriaError('Entity missing required spread')
        if getattr(self, 'callback', False):
            if not self.callback(ent):
                raise CriteriaError('Callback criteria not fullfilled')

class AccountCriterias(AttrCriterias):
    """Account specific criterias for an AttrConfig.

    The class could be extended by more criterias.

    """
    def __init__(self, primary_account=None, *args, **kwargs):
        """Subclass for accounts.

        @type primary_account: True, False or None
        @param primary_account:
            True if a given account must be the primary account. If set to False
            will the AttrConfig be ignored if the account is a primary account.
            Non personal accounts will never be primary accounts, as they don't
            have the affiliations to decide that.

        """
        self.primary_account = primary_account
        super(AccountCriterias, self).__init__(*args, **kwargs)

    def check(self, ent):
        """Subclass with more checks for accounts."""
        super(AccountCriterias, self).check(ent)
        if self.primary_account is not None:
            if bool(self.primary_account) != bool(ent.is_primary_account):
                raise CriteriaError('Primary account mismatch')

def has_config(config, configclass):
    """Helper function for checking if a given attribute is defined.

    Searches recursively, as some attributes could be defined as lists with
    different attribute classes.

    @type config: dict
    @param config: The configuration for all the attributes.

    @type configclass: AttrConfig or list of AttrConfig
    @param configclass:
        The given class or classes that should be searched for. Used simply as
        input to isinstance(config, configclass).

    @rtype: bool
    @return:
        If the given config class is defined and exists in the configuration.

    """
    if isinstance(config, dict):
        # We only need the values, not the attribute names
        config = config.itervalues()
    for c in config:
        if isinstance(c, configclass):
            return True
        if isinstance(c, (list, tuple)):
            if has_config(c, configclass):
                return True
    return False

def get_config_by_type(config, configclass):
    """Helper function for getting all config by a given type.

    Searches recursively, as some attributes could be defined as lists with
    different attribute classes. The result is a flattened list, without the
    attribute names.

    @type config: dict
    @param config: The configuration for all the attributes.

    @type configclass: AttrConfig
    @param configclass: The given class that should be searched for.

    @rtype: list
    @return:
        A flattened list with all the attribute configuration objects of the
        given class type. The attribute names are not returned.

    """
    ret = []
    if isinstance(config, dict):
        # We only need the values, not the attribute names
        config = config.itervalues()
    for c in config:
        if isinstance(c, configclass):
            ret.append(c)
        if isinstance(c, (list, tuple)):
            ret.extend(get_config_by_type(c, configclass))
    return ret

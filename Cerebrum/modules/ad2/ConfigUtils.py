# -*- coding: utf-8 -*-
#
# Copyright 2013-2025 University of Oslo, Norway
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
Attribute configuration for the Active Directory synchronisation.

The AD sync is a bit configurable, to be able to fulfill most needs without
having to develop complex subclasses for each instance. It tries to be
flexible, at the cost of a bit more thorough and complicated configuration.

The classes in this file are typically used to configure individual attributes
in a configuration module, `adconf`.

There are two base confifuration classes:

:class:`.AttrConfig`
    Configures how to set and control what a given attribute should contain

:class:`.AttrCriterias`
    Sets requirements that needs to be fullfilled for a given *AttrConfig*.

Each element in a sync's 'attribute' dict could be defined with a single,
*AttrConfig* object, or a sequence of *AttrConfig* objects:
::

    attributes = {
        'DisplayName': ConfigUtils.PersonNameAttr(
            name_variant=co.name_full
            source_system=co.system_fs,
        ),
        'Description': (
            ConfigUtils.NameAttr(
                name_variant=(co.personal_title, co.work_title),
                criterias=ConfigUtils.AttrCriterias(
                    spread=co.spread_lms,
                ),
            ),
            ConfigUtils.TraitAttr(
                trait_type=co.trait_description
                # Traits contain both a strval and a numval:
                transform=lambda tr: tr['strval'].strip(),
                default={'strval': 'N/A'},
            ),
        ),
    }


If you need to dig into how each attribute is calculated:

1. CerebrumEntity.modules.ad2.ADSync.<Sync>.fetch_cerebrum_entities starts the
    cerebrum lookup of data

2. It will create a bunch of CerebrumEntity objects of type
    `adconf.SYNCS[<sync>][object_classes]`

3. Each object generates attributes through its
    `CerebrumEntity.calculate_ad_values`, which in turn uses these attribute
    config objects to create a dict for comparison

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import six

from Cerebrum.Utils import Factory, NotSet
from Cerebrum import Constants as _constants  # noqa: N813
from Cerebrum.modules.trait.constants import _EntityTraitCode

# *sigh* - global database connection?
db = Factory.get('Database')()

# Note that the constants object is not instantiated, as we only need type
# checking in here.
const = Factory.get('Constants')


class ConfigError(Exception):
    """Exception for configuration errors."""
    pass


class CriteriaError(Exception):
    """Exception for when a AttrCriterias is not fullfilled."""
    pass


class AttrConfig(object):
    """
    Configuration of a given AD attribute.

    Note that the attribute configs themselves won't do any transforms or
    lookups, they are only container objects with config attributes.

    TODO: Some of the logic should be moved/implemented here, rather than
    ``CerebrumData.CerebrumEntity.find_ad_attribute``
    """
    def __init__(self, default=NotSet, transform=None, spread=None,
                 source_systems=None, criterias=None, ad_transform=None):
        """
        :param default:
            The default value to set for the attribute if no other value is
            found.

            For string values, the following printf-style substitutions can be
            used to insert attributes from the *CerebrumEntity*:

            - `entity_name`
            - `entity_id`
            - `ad_id`
            - `ou`

            Use these through regular substition, e.g. "%(ad_id)s".  Also note
            that:

            - default values will be passed through any *transform* function
            - *criterias* must be fulfilled for default values to be set

        :param callable transform:
            A callable that reveices a single attribute value and returns a
            modified value.

            E.g.: `lambda x: x.lower()`

        :type spread: SpreadCode or sequence thereof
        :param spread:
            Deprecated setting - this has the same behaviour as setting
            `criterias=AttrCriterias(spread=...)`.  Use `criterias` if this is
            needed.

            Note that this is also not correct use of spreads - we may want to
            reconsider supporting this type of attribute/spread filtering
            altogether.

        :type criterias: AttrCriterias
        :param AttrCriterias criterias:
            A set of criterias that must be fulfilled by the object before
            setting this attribute.

        :type source_systems: AuthoritativeSystemCode or sequence thereof
        :param source_systems:
            A prioritized list of source systems to fetch data from.

        :param callable ad_transform:
            Transform/normalize the AD value for comparison.

            This is typically used to normalize the AD value in scenarios
            where the value we get from AD looks different from the value we
            set in AD.

        """
        self.default = default
        if transform:
            self.transform = transform
        self.source_systems = _prepare_constants(
            source_systems,
            _constants._AuthoritativeSystemCode,
        )
        self.spread = _prepare_constants(spread, _constants._SpreadCode)
        if criterias and not isinstance(criterias, AttrCriterias):
            raise ConfigError('Criterias is not an AttrCriterias object')
        self.criterias = criterias
        if ad_transform and not callable(ad_transform):
            raise ConfigError('The ad_transform is not callable')
        self.ad_transform = ad_transform


def _prepare_constants(values, const_class):
    """Prepare and validate given Cerebrum constant(s).

    :type input: Cerebrum constant or sequence thereof or None
    :param input:
        One or more constants to validate, or ``None``

    :param const_class:
        One or more classes to limit the given input constants to.

    :returns:
        Returns the input sequence (if valid), or a tuple with the input value
        (if valid), or None if the input was None
    """
    if values:
        if not isinstance(values, (list, tuple, set)):
            values = (values,)
        for i in values:
            if not isinstance(i, const_class):
                raise ConfigError('Not a %s: %s (%r)' % (const_class, i, i))
    return values


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
        self.contact_types = _prepare_constants(
            contact_types,
            _constants._ContactInfoCode,
        )


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
        self.name_variants = _prepare_constants(
            name_variants,
            (_constants._EntityNameCode, _constants._PersonNameCode),
        )
        self.languages = _prepare_constants(
            languages,
            _constants._LanguageCode,
        )


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
        self.name_variants = _prepare_constants(
            name_variants,
            _constants._PersonNameCode,
        )


class AddressAttr(AttrConfig):
    """Config for attributes with addresses, or parts of an address.

    """
    def __init__(self, address_types, *args, **kwargs):
        """Initiate an address attribute.

        Note that each address is a dict and not a string. You therefore need
        to use *transform* to set the proper variable(s) you would like. Each
        address consists of the elements:

        - address_text
        - p_o_box
        - postal_number
        - city
        - country

        Example on a transform callable:
        ::

            lambda adr: adr['postal_number']

        which would for instance return:
        ::

            0360

        You could also combine elements:
        ::

            def adrformat(adr)
                if adr['p_o_box']:
                    return u'%s, %s' % (adr['address_text'], adr['p_o_box'])
                return adr['address_text']

        which could return:
        ::

            "Problemveien 1"
            "Problemveien 1, Postboks 120"

        Note that the element "country" is a reference to a Country code:
        ::

            lambda adr: co.Country(adr['country']).country

        which would give:
        ::

            "Sweden"

        @type address_types: AddressCode or sequence thereof
        @param address_types: What addresses to fetch and use, in prioritised
            order. The first available for an entity is used.

        """
        super(AddressAttr, self).__init__(*args, **kwargs)
        self.address_types = _prepare_constants(
            address_types,
            _constants._AddressCode,
        )


class ADAttributeAttr(AttrConfig):
    """
    Config for attributes fetched from the AD attribute module.

    This module stores AD attributes for a given entity.  The AD attribute
    table stores attributes by spread.  You could for instance have a different
    `RoamingProfile` in two different AD domains.
    """
    def __init__(self, attributes, *args, **kwargs):
        """
        Configure an AD attribute to include.

        The spread is set by the sync profile.  Might want to be able to
        override the spread setting in the future, but that is not an option at
        the moment.

        :type attributes:
            Cerebrum.modules.ad2.Entity/ADAttribute or sequence thereof

        :param attributes:
            The name of the AD attribute constant(s) to use, in prioritized
            order. The first available attribute that is found is used.
        """
        super(ADAttributeAttr, self).__init__(*args, **kwargs)
        self.attributes = _prepare_constants(attributes, const.ADAttribute)


class ExternalIdAttr(AttrConfig):
    """Config for attributes using external IDs.

    """
    def __init__(self, id_types, *args, **kwargs):
        """Initiate a config for given external IDs.

        @type id_types: EntityExternalIdCode or sequence thereof
        @param id_types: What external ID types to use, in prioritized order.

        """
        super(ExternalIdAttr, self).__init__(*args, **kwargs)
        self.id_types = _prepare_constants(
            id_types,
            _constants._EntityExternalIdCode,
        )


class TraitAttr(AttrConfig):
    """
    Config for attributes retrieved from traits.

    Each trait can contain values of different types and use cases (strval,
    numval, date, target_id).  You *must* configure the TraitAttr with a
    ``transform`` function to prepare a scalar value from a trait dict.
    """
    def __init__(self, traitcodes, *args, **kwargs):
        """
        Configure a trait to include.

        This might be expanded later, if more criterias are needed.

        :type traitcodes: EntityTraitCode, list[EntityTraitCode]
        :param traitcodes:
            Trait codes to select, in preferred order.  The first matching
            trait will be used.
        """
        super(TraitAttr, self).__init__(*args, **kwargs)
        self.traitcodes = _prepare_constants(traitcodes, _EntityTraitCode)


class MemberAttr(AttrConfig):
    """Config for Member attribute of groups.

    This is to set up an attribute with different kinds of members, typically
    the Member attribute for group objects, but could also be used e.g. for
    NisNetGroups, which requires user members in one attribute, on a "triple"
    format, and group members in another attribute.

    Example on configuration:

        ConfigUtils.MemberAttr(
               member_spreads=(co.spread_ad_account, co.spread_ad_group),
               transform=lambda x: ('CN=%s,%s' % (m.ad_id, m.ou) for m in x),
        )

    """
    def __init__(self, member_spreads=None, person2primary=False, *args,
                 **kwargs):
        """Initiate a config for fetching group members.

        @type member_spread: SpreadCode or sequence thereof
        @param member_spread:
            What spread(s) the group members should have to be selected.

        @type person2primary: bool
        @param person2primary:
            If set to True, persons are included as members by fetching their
            primary accounts instead. Note that only the primary accounts that
            has one of the given L{member_spreads} will be added.

        """
        super(MemberAttr, self).__init__(*args, **kwargs)
        self.member_spreads = _prepare_constants(
            member_spreads,
            _constants._SpreadCode,
        )
        self.person2primary = person2primary


class CallbackAttr(AttrConfig):
    """
    Configure a generic attribute.

    This special attribute requires the use of a callback to select a scalar
    attribute value.  The callback is presented with the full *Entity* object,
    as fetched from Cerebrum.

    This class should normally not be used, as it requires internal knowledge
    of how the entity object works, and it will also make the adconf a bit more
    complex. Use this only if no other alternative is possible. The plus side
    of this, is that we don't have to create subclasses for every single weird
    attribute that is needed.

    Example use:
    ::

        'DNSHostName': ConfigUtils.CallbackAttr(
            lambda entity: getattr(entity, 'hostname', ''),
        ),

    """
    def __init__(self, callback, *args, **kwargs):
        """Initiate a config for a callback attribute.

        :param callable callback:
            A callback to process the entity into an attribute value

        """
        if not callable(callback):
            raise ConfigError("Argument is not callable: " + repr(callback))
        super(CallbackAttr, self).__init__(*args, **kwargs)
        self.callback = callback


class SimpleMemberAttr(CallbackAttr):

    """ An attribute for AD group memberships in the 'froupsync'.

    All this config does, is to append expected OU to the cerebrum membership
    names, and attempt to fix any case differences in the DN strings.

    NOTE: This class was written for the 'froupsync'. If you use it in other
    syncs, you're doing something wrong!

    """

    def __init__(self, member_ou):
        super(SimpleMemberAttr, self).__init__(
            default=[],
            callback=self._callback,
            ad_transform=self._ad_transform)
        self._member_ou = member_ou

    @staticmethod
    def format_dn(dn):
        def format_part(p):
            # Format each part of the DN
            kv = p.split('=', 1)
            return '%s=%s' % (kv[0].upper(), kv[1].lower())
        try:
            return ','.join(
                [format_part(part) for part in dn.split(',')])
        except IndexError:
            # Formatting failed, return as is and let the comparison fail.
            return dn

    @classmethod
    def _ad_transform(cls, ad_members):
        """ A callback that ensures the casing in AD membership DNs. """
        # TODO: This really should be a generator, but the AD sync doesn't
        # allow that.
        return [cls.format_dn(m) for m in ad_members]

    def _callback(self, crb_object):
        """ A callback to fetch members from a CerebrumGroup object. """
        # TODO: Should we do some uname -> ad_id conversion here, or has that
        # been done elsewhere?
        # TODO: Same as for the _ad_transform result: This should yield.
        return [self.format_dn('CN=%s,%s' % (m.lower(), self._member_ou))
                for m in getattr(crb_object, 'members', [])]


class EmailAddrAttr(AttrConfig):
    """
    E-mail address attribute config (`Cerebrum.modules.Email`).

    You *must* implement a `transform` to select an appropriate address from
    the input given to this attribute config.  The input is a `dict` with:

    primary (string):
        The primary e-mail address for the entity

    alias (list of strings):
        A list of all the valid e-mail address aliases for the entity

    ad_id (string):
        The ad-id of the object.

    entity_id (int):
        The entity id of the object.

    entity_name (str):
        The entity name of the object (if any).

    The typical implementation is `lambda x: x.get('primary')`.
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
    environments that should support both environments where both UNIX and AD
    is used. Note, however, that AD needs to include an extra schema before the
    posix attributes could be populated.

    This class makes available a dict with the elements:

        - uid: int or empty string
        - gid: int or empty string
        - shell: string, strcode of a PosixShell constant, e.g. "bash"
        - gecos: string, free text

    One of these could for instance be set through the L{transform} method,
    e.g:
    ::

        lamba posix: posix.get('shell', '<N/A>')

    Note that regular Cerebrum PosixGroups does not have anything set else than
    GID.

    """
    # TODO: Should we have some shortcut settings, for making the config
    # easier?
    pass


class HomeAttr(AttrConfig):
    """
    Config for account home directories.

    The attribute data generated for the HomeAttr is a dict with information
    about the home registered for the given home spread. The dict contains the
    elements:

    homedir (str)
        The full path to the homedir of the account, as how the Account object
        defines how it should be. Note that if you need the path in a different
        format, you probably want to subclass the ``account.resolve_homedir()``
        for the given instance instead of tweaking it here with *transform*.

    home_spread (int)
        The spread for the home directory.

    status (int)
        The code from the AccountHomeStatus for the homedir, that could e.g.
        represent that the homedir is created, archived or failed to be
        created.
    """
    def __init__(self, home_spread, *args, **kwargs):
        """Initiate a config for a home directory attribute.

        @type home_spread: SpreadCode
        @param home_spread:
            The spread for the homedir that should be used. An account is
            allowed to have different home directories per system. Note that
            only one spread is allowed and supported, as only one home
            directory is used per system.

        """
        super(HomeAttr, self).__init__(*args, **kwargs)
        if not isinstance(home_spread, _constants._SpreadCode):
            raise ConfigError('Not a Spread: %s' % (home_spread,))
        self.home_spread = home_spread


@six.python_2_unicode_compatible
class AlwaysEqual(object):
    """Make value always compare equal to other"""

    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    def __str__(self):
        return "<[writeonly] %s>" % (self.value,)


def noupdate(ad_transform=None, attrclass=AttrConfig, *rest, **kw):
    """Make AttrConfig object (or subclass) only write if not set in AD.

    The attribute is normally only written once, the first time. It could also
    be written if AD-admins blanks out the attribute in AD.

    Examples on how to set up in adconf::

        # Simple writeonce:
        'attr1': noupdate(default='%(entity_name)s'),
        # Using specialized AttrConfig, with passed params
        'attr2': noupdate(
            attrclass=TraitAttr,
            traitcode=co.trait_example,
            transform=lambda x: x['strval'],
            spread=co.spread_exchange,
            default='nah...',
            ),

    :type ad_transform: Callable
    :param ad_transform: See AttrConfig

    :type attrclass: Callable with kw argument ad_transform
    :param attrclass: Should construct some object of type AttrConfig

    :other params: Sent to attrclass

    :return: AttrConfig object
    """

    def transform(advalue):
        return advalue if (advalue is None
                           or advalue == "") else AlwaysEqual(advalue)
    return attrclass(ad_transform=((lambda x: transform(ad_transform(x)))
                                   if ad_transform else transform),
                     *rest,
                     **kw)


class AttrCriterias(object):
    """
    Config class for setting criterias for entities' AttrConfigs.

    Each AttrConfig object could be set up with an AttrCriterias for defining
    what criterias that must be fullfilled for the AttrConfig to be set. By
    having the criterias in its own classes, we make it easier to gather the
    exact data that is needed from Cerebrum to check the criterias. The
    criterias will in some situations be too limited, which makes it possible
    to use a callback.
    """
    def __init__(self, spreads=None, callback=None):
        """
        Set up initial criterias.

        :type spreads: SpreadCode, list[SpreadCode]
        :param spreads:
            If set, then one of the given spreads must be set for the entity to
            allow the given AttrConfig to be set.

        :param callable callback:
            If flexibility is needed, you could use this callback for
            generating a more specific criteria. The callable must accept one
            argument, a L{CerebrumEntity} object, and must return True to tell
            that the criteria was fullfilled.

            Note however that the sync does not know what data the callable
            needs, so that has to be gathered manually (TODO: or we should
            extend the config to force the retrieval of specific data elements
            from Cerebrum).

            Note that any other given criterias in the object must also be
            fullfilled for the AttrConfig to be set.

        """
        self.spreads = _prepare_constants(spreads, _constants._SpreadCode)
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
    def __init__(self, primary_account=None, affiliations=None,
                 *args, **kwargs):
        """Subclass for accounts.

        :type primary_account: True, False or None
        :param primary_account:
            True if a given account must be the primary account. If set to
            False will the AttrConfig be ignored if the account is a primary
            account.  Non personal accounts will never be primary accounts, as
            they don't have the affiliations to decide that.

        :type affiliations: String, list of strings or None
        :param affiliations:
            The affiliation type to filter by. The account must have these
            affiliations for the criteria to be in-spec.

            The following list would require all the following affiliations to
            be present (logical AND). Note that an affiliation can be composed
            of the affiliation itself, the status and an OU, or an combination:

              ['perspective_fs:STUDENT/aktiv@666', 'ANSATT/tekadm',
               'TILKNYTTET', 'perspective_sap:TILKNYTTET@666']

            Perspective must be supplied for OU-matching.

            Doing a logical OR between affiliations, can be achieved by
            chaining instantiation of L{AccountCriteria} in the
            attribute-configuration.
        """
        self.primary_account = primary_account
        self.affiliations = _prepare_constants(affiliations, six.string_types)
        super(AccountCriterias, self).__init__(*args, **kwargs)

    def check(self, ent):
        """Subclass with more checks for accounts."""
        super(AccountCriterias, self).check(ent)
        if self.primary_account is not None:
            if bool(self.primary_account) != bool(ent.is_primary_account):
                raise CriteriaError('Primary account mismatch')
        if self.affiliations is not None:
            from Cerebrum import Errors
            ac = Factory.get('Account')(db)
            co = Factory.get('Constants')(db)

            try:
                ac.find(ent.entity_id)
            except Errors.NotFoundError:
                raise CriteriaError(
                    "Account '%s' does not exist, possible race condition"
                    % ent.entity_id)

            def parse_input_affs(affs):
                """Generator that yields a tuple with elements that should
                   be used in a search."""
                # TODO: Redesign the specification that this implements
                # - Support limiting affiliations to systems
                # - Perspective should be set differently
                # - Better regex
                import re
                for elm in affs:
                    ou = None
                    (ou_perspective, aff, status, ou_str) = (
                        [x if x else None for x in re.match(
                            "^([a-z_]*):?([A-Z]*)/?([a-z]*)@?([0-9]*)", elm
                            ).groups()])
                    try:
                        aff = co.PersonAffiliation(aff)
                    except (TypeError, Errors.NotFoundError):
                        raise ConfigError("Unknown affiliation '%s'" % aff)
                    if status:
                        try:
                            status = co.PersonAffStatus(aff, status)
                        except (TypeError, Errors.NotFoundError):
                            raise ConfigError(
                                "Unknown affiliation status '%s/%s'"
                                % (str(aff), status))
                    if ou_str:
                        try:
                            ou = Factory.get('OU')(db)
                            ou.find_sko(ou_str)
                        except Errors.NotFoundError:
                            raise ConfigError("Stedkode '%s' does not exist"
                                              % ou_str)
                    if ou_perspective:
                        try:
                            perspective = ou_perspective.split('_')[1].upper()
                            ou.perspective = co.OUPerspective(perspective)
                        except Errors.NotFoundError:
                            raise ConfigError(
                                "OUPerspective '%s' does not exist"
                                % ou_perspective)
                    elif ou_str:
                        raise ConfigError(
                            ("Invalid ou_mapping {!r}, cannot have OU"
                             " without perspective").format(elm))

                    yield (aff, status, ou)

            def compare_ou(ou_criteria, candidate_ou):
                """Check if an OU is the same as, or a child of, another OU.

                :type ou_criteria: OU
                :param ou_criteria: The maximum required OU-level.

                :type candidate_ou: int
                :param candidate_ou: The candidates OUs entity id.
                """
                # TODO: Make child-search configurable
                # TODO: Avoid piggybacking perspective on ou_criteria
                children = ou_criteria.list_children(ou_criteria.perspective,
                                                     recursive=True)
                children.append(ou_criteria.entity_id)
                return True if int(candidate_ou) in children else False

            # Check if the comparison is false only if the first arg is defined
            def ne(x, y):
                return None if not x else x == y

            def choose_comparator(left, right):
                """Choose comparator function for left & right."""
                if (isinstance(left, Factory.get('OU')) and
                        hasattr(left, 'perspective')):
                    return compare_ou(left, right)
                else:
                    return False if ne(left, right) is False else True

            # Tuple type for custom field comparison (force choose_comparator
            # usage for Cerebrum Entities).
            t = type(
                str('T'),
                (tuple,),
                {
                    str('__eq__'): lambda x, y: all(
                            choose_comparator(e1, e2)
                            for (e1, e2) in zip(x, y)
                    ),
                },
            )

            def check_account_aff(ac, aff, ou):
                """Check an if the account has an appropriate affiliation.

                :type ac: Account
                :param ac: The account to check.

                :type aff: PersonAffiliation
                :param aff: The affiliation to check against

                :type ou: OU
                :param OU: The OU that the account will be checked against
                """
                ac_types = [(e['affiliation'], e['ou_id']) for e in
                            ac.get_account_types()]
                if t([aff, ou.entity_id if ou else None]) not in ac_types:
                    raise CriteriaError(
                        "Account '%s' with '%s' does not match '%s'"
                        % (ent.entity_id,
                           [aff, ou.entity_id if ou else None],
                           ac_types))

            def check_person_aff(ac, aff, status, ou):
                """Check if the person has the affiliation.

                The OU will match, if the affiliation OU is lower in level that
                L{ou}.

                :type ac: Account
                :param ac: The account to check.

                :type aff: PersonAffiliation
                :param aff: The affiliation to check against

                :type status: PersonAffStatus
                :param status: The status to check against

                :type ou: OU
                :param OU: The OU that the accounts owner (person) will be
                    checked against
                """
                pe = Factory.get('Person')(db)
                try:
                    pe.find(ac.owner_id)
                except Errors.NotFoundError:
                    raise CriteriaError("Owner of account '%s' is not a person"
                                        % ent.entity_id)
                affs = [(e['affiliation'], e['status'], e['ou_id']) for e in
                        pe.get_affiliations()]

                if t([aff, status, ou]) not in affs:
                    raise CriteriaError(
                        "Account '%s' with '%s' does "
                        "not match person affiliations '%s'"
                        % (ent.entity_id,
                           [aff, status, ou.entity_id if ou else None],
                           affs))

            # Perform check of all affiliation criterias
            for (aff, status, ou) in parse_input_affs(self.affiliations):
                if not status:
                    check_account_aff(ac, aff, ou)
                else:
                    check_person_aff(ac, aff, status, ou)


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
        config = six.itervalues(config)
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
        config = six.itervalues(config)
    for c in config:
        if isinstance(c, configclass):
            ret.append(c)
        if isinstance(c, (list, tuple)):
            ret.extend(get_config_by_type(c, configclass))
    return ret

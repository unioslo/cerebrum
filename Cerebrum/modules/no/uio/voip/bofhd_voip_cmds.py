#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2010-2016 University of Oslo, Norway
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
"""This module implements a bofhd extension for the voip module."""

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.Entity import EntityContactInfo

from Cerebrum.modules.no.fodselsnr import personnr_ok
from Cerebrum.modules.no.fodselsnr import InvalidFnrError

from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods

from Cerebrum.modules.bofhd.cmd_param import Command
from Cerebrum.modules.bofhd.cmd_param import FormatSuggestion
from Cerebrum.modules.bofhd.cmd_param import SimpleString
from Cerebrum.modules.bofhd.cmd_param import OU
from Cerebrum.modules.bofhd.cmd_param import YesNo
from Cerebrum.modules.no.uio.voip.cmd_param import MacAddress
from Cerebrum.modules.no.uio.voip.cmd_param import VoipClientInfoCode
from Cerebrum.modules.no.uio.voip.cmd_param import VoipClientTypeCode
from Cerebrum.modules.no.uio.voip.cmd_param import VoipServiceTypeCode
from Cerebrum.modules.no.uio.voip.cmd_param import VoipAddressParameter
from Cerebrum.modules.no.uio.voip.cmd_param import VoipOwnerParameter
from Cerebrum.modules.no.uio.voip.cmd_param import VoipServiceParameter
from Cerebrum.modules.no.uio.voip.cmd_param import PriorityParameter
from Cerebrum.modules.no.uio.voip.cmd_param import ContactTypeParameter
from Cerebrum.modules.no.uio.voip.cmd_param import VoipClientParameter

from Cerebrum.modules.no.uio.voip import bofhd_voip_help
from Cerebrum.modules.no.uio.voip import bofhd_voip_auth

from Cerebrum.modules.no.uio.voip.voipService import VoipService
from Cerebrum.modules.no.uio.voip.voipClient import VoipClient
from Cerebrum.modules.no.uio.voip.voipAddress import VoipAddress

from Cerebrum.modules.bofhd.errors import CerebrumError


class BofhdVoipCommands(BofhdCommonMethods):
    """Bofhd extension with voip commands."""

    all_commands = dict()
    parent_commands = False
    authz = bofhd_voip_auth.BofhdVoipAuth

    @classmethod
    def get_help_strings(cls):
        return (bofhd_voip_help.group_help,
                bofhd_voip_help.command_help,
                bofhd_voip_help.arg_help)

    ########################################################################
    # supporting methods
    #
    def _human_repr2id(self, human_repr):
        """Just like the superclass, except mac addresses are trapped here."""

        if (isinstance(human_repr, (str, unicode)) and
            len(human_repr) == 17 and
            all(x.lower() in "0123456789abcdef: " for x in human_repr)):
            return "mac", human_repr

        return super(BofhdVoipCommands, self)._human_repr2id(human_repr)

    def _get_entity_id(self, designation):
        """Check whetner L{designation} may be interpreted as an entity id.

        Return the id, if possible, or None, when no conversion applies. 

        We consider the following as entity_id:

          + sequence of digits
          + string with sequence of digits
          + string of the form 'id:digits'
        """
        id_type, value = self._human_repr2id(designation)
        if id_type == "id":
            return int(value)
        return None

    def _is_numeric_id(self, value):
        return (isinstance(value, (int, long)) or
                isinstance(value, (str, unicode)) and value.isdigit())

    def _get_constant(self, designation, const_type):
        """Fetch a single constant based on some human designation.

        Return the first match given by 'designation' (see
        Constants.py:fetch_constants).

        FIXME: refactor this to bofhd_core.py ?
        """

        cnst = self.const.fetch_constants(const_type, designation)
        if len(cnst) == 0:
            raise CerebrumError("Unknown %s constant: %s" % 
                                (str(const_type),designation))
        return cnst[0]

    def _get_ou(self, designation):
        """Fetch a single OU identified by designation.

        TODO: extend this method to be generous about what's accepted as
        input.
        TODO: how do we decide if 123456 means sko or entity_id?
        FIXME: compare this with other incarnations of _get_ou. Maybe there
               can be ONE method that covers all the cases with an obvious
               interface? E.g. we should accept things like 33-15-20 as it is
               OBVIOUSLY a sko.
        """

        id_type, value = self._human_repr2id(designation)
        if str(value).isdigit():
            for key in ("ou_id", "stedkode"):
                try:
                    x = super(BofhdVoipCommands, self)._get_ou(
                              **{key: str(value)})
                    return x
                except (Errors.NotFoundError, CerebrumError):
                    pass

        raise CerebrumError("Could not find ou by designation %s" %
                            str(designation))

    def _get_voip_service(self, designation):
        """Locate a specific voip_service.

        We try to be a bit lax when it comes to identifying voip_services. A
        numeric designation is interpreted as entity_id. Everything else is
        interpreted as description.
        """

        service = VoipService(self.db)
        if self._get_entity_id(designation):
            try:
                service.find(self._get_entity_id(designation))
                return service
            except Errors.NotFoundError:
                raise CerebrumError("Could not find voip service with id=%s" %
                                    str(designation))

        ids = service.search_voip_service_by_description(designation,
                                                         exact_match=True)
        if len(ids) == 1:
            service.find(ids[0]["entity_id"])
            return service

        raise CerebrumError("Could not uniquely determine voip_service "
                            "from description %s" % str(designation))

    def _get_voip_address_by_service_description(self, designation):
        try:
            service = self._get_voip_service(designation)
            return self._get_voip_address_by_owner_entity_id(service.entity_id)            
        except (CerebrumError, Errors.NotFoundError):
            return list()

    def _get_voip_address_by_owner_account(self, designation):
        try:
            account = self._get_account(designation)
            return self._get_voip_address_by_owner_entity_id(account.owner_id)
        except (CerebrumError, Errors.NotFoundError):
            return list()

    def _get_voip_address_by_contact_info(self, designation):
        try:
            ids = set(x["entity_id"] for x in
                      self._get_contact_info(designation))
            result = list()
            for x in ids:
                result.extend(self._get_voip_address_by_owner_entity_id(x))
            return result
        except Errors.NotFoundError:
            return list()

        assert False, "NOTREACHED"

    def _get_voip_address_by_owner_entity_id(self, designation):
        if not self._is_numeric_id(designation):
            return list()

        value = int(designation)
        try:
            va = VoipAddress(self.db)
            va.find_by_owner_id(value)
            return [va,]
        except Errors.NotFoundError:
            return list()

        assert False, "NOTREACHED"

    def _get_voip_address_by_entity_id(self, designation):
        """Return all voip_addresses matching the specified entity_id."""

        if not self._is_numeric_id(designation):
            return list()

        value = int(designation)
        try:
            va = VoipAddress(self.db)
            va.find(value)
            return [va,]
        except Errors.NotFoundError:
            return list()

        assert False, "NOTREACHED"

    def _get_voip_address(self, designation, all_matches=False):
        """Collect voipAddress instance(s) matching designation.

        Crap. This turned out to be extremely complicated, since there are so
        many ways we could interpret the meaning of 'give a voip_address for
        <doohickey>'.
        
        @param all_matches:
          Controls whether to collect all possible matches, or just the first
          one. Note that the default case is to collect the single voipAddress
          that matches the first of the search criteria below. Even though
          previous searches may have matched multiple addresses, the first
          search yielding exactly one answer will be used. 
        """

        search_names = ("by_entity_id", "by_owner_entity_id",
                        "by_contact_info", "by_owner_account",
                        "by_service_description",)
        id_type, value =  self._human_repr2id(designation)
        result = list()
        collected_ids = set()
        for partial_name in search_names:
            caller_name = "_get_voip_address_" + partial_name
            caller = getattr(self, caller_name)
            addrs = caller(value)
            # self.logger.debug("Searcher %s returned %d VA(s)", caller_name,
            #                   len(addrs))
            result.extend(x for x in addrs
                          if x.entity_id not in collected_ids)
            collected_ids.update(x.entity_id for x in addrs)
            # If an exact match is requested, grab the first search that yields
            # exactly 1 answer.
            if not all_matches and len(addrs) == 1:
                return addrs[0]

        if len(result) == 0:
            raise CerebrumError("No voip_address matches designation %s" %
                                (designation,))
        if not all_matches and len(result) > 1:
            raise CerebrumError("Cannot uniquely determine voip_address from "
                                "designation %s: matching ids=%s" %
                                (designation, ", ".join(str(x.entity_id)
                                                        for x in result)))
        return result

    def _get_or_create_voip_address(self, owner_id, with_softphone=True):
        """Much like _get_voip_address(), except this one creates it as well
        if it does not exist, rather than failing.

        with_softphone controls whether we want to create a softphone for the
        new voip_address, should voip_address be created.
        """

        address = VoipAddress(self.db)
        try:
            address.find_by_owner_id(owner_id)
        except Errors.NotFoundError:
            address.clear()
            address.populate(owner_id)
            address.write_db()
            address.write_db()

            if with_softphone:
                self._create_default_softphone_client(address.entity_id)
        return address

    def _create_default_softphone_client(self, voip_address_id):
        """Help function to create default softphone client for all addresses
        and services.
        """

        #
        # If it exists, we are done...
        client = VoipClient(self.db)
        if client.search(voip_address_id=voip_address_id,
                         client_type=self.const.voip_client_type_softphone):
            return

        client.populate(voip_address_id,
                        self.const.voip_client_type_softphone,
                        True, # sip_enabled by default
                        None, # softphones don't have MACs
                        self.const.voip_client_info_softphone)
        client.write_db()
        client.set_auth_data(self.const.voip_auth_sip_secret,
                             client.generate_sip_secret())
        self.logger.debug("Automatically generated softphone "
                          "client id=%s for address %s",
                          client.entity_id, voip_address_id)

    def _get_voip_client(self, designation):
        """Locate a voip_client by designation.

        Possible interpretations of designation are:

          + entity_id
          + mac address
        """

        # Don't use _human_repr2id here, since it does not like ':' being part
        # of the identifier (which mac addresses definitely have)
        client = VoipClient(self.db)
        if (isinstance(designation, (int, long)) or
            isinstance(designation, str) and designation.isdigit()):
            try:
                client.find(int(designation))
                return client
            except Errors.NotFoundError:
                pass

        # Try to look up by mac address
        try:
            client.clear()
            client.find_by_mac_address(designation)
            return client
        except (Errors.NotFoundError, AssertionError):
            pass

        raise CerebrumError("Could not uniquely determine voip_client "
                            "from designation %s" % str(designation))

    def _get_voip_person(self, designation):
        """Lookup a person by <something>.
        """

        person = Factory.get("Person")(self.db)
        if self._get_entity_id(designation):
            try:
                person.find(self._get_entity_id(designation))
                return person
            except Errors.NotFoundError:
                pass

        # fnr?
        exc = CerebrumError("No person found for designation %s" %
                            str(designation))
        id_type, value = self._human_repr2id(designation)
        if str(value).isdigit():
            try:
                fnr = personnr_ok(str(value))
                person.find_by_external_id(self.const.externalid_fodselsnr,
                                           fnr)
                return person
            except (InvalidFnrError, Errors.NotFoundError):
                pass

        # account?
        try:
            account = Factory.get("Account")(self.db)
            account.find_by_name(str(value))
            if account.owner_type == self.const.entity_person:
                return self._get_voip_person(account.owner_id)
        except Errors.NotFoundError:
            pass

        # By other external ids? By name?
        raise exc

    def _get_voip_owner(self, designation):
        """Locate the owner of a voip address.

        We try in order to look up voip-service and then person. If the search
        is unsuccessful, throw CerebrumError.

        @param designation:
          Some sort of identification of the owner.

        @return:
          A voipService/Person instance, or raise CerebrumError if nothing
          appropriate is found.
        """

        for method in (self._get_voip_person, self._get_voip_service):
            try:
                return method(designation)
            except CerebrumError:
                pass

        raise CerebrumError("Cannot locate person/voip-service designated "
                            "by %s" % str(designation))

    def _get_contact_info(self, value):
        """Return a sequence of dicts containing entity_contact_info entries
        for the specified contact value.

        We scan system_voip ONLY.

        value is matched both against contact_value and contact_alias.
        """

        result = list()
        eci = EntityContactInfo(self.db)
        for row in eci.list_contact_info(source_system=self.const.system_voip,
                                         contact_value=str(value)):
            result.append(row.dict())

        for row in eci.list_contact_info(source_system=self.const.system_voip,
                                         contact_alias=str(value)):
            result.append(row.dict())

        return result

    def _collect_constants(self, const_type):
        """Return a suitable data structure containing all constants of the
        given type. 
        """

        result = list()
        for cnst in self.const.fetch_constants(const_type):
            result.append({"code": int(cnst),
                           "code_str": str(cnst),
                           "description": cnst.description})
        return sorted(result, key=lambda r: r["code_str"])

    def _typeset_traits(self, trait_sequence):
        """Return a human-friendly version of entity traits.
        """

        traits = list()
        for et in trait_sequence:
            traits.append("%s" % (str(self.const.EntityTrait(et)),))

        return traits

    def _typeset_ou(self, ou_id):
        """Return a human-friendly description of an OU.

        Return something like '33-15-20 USIT'
        """
        ou = self._get_ou(int(ou_id))
        # Use acronym, if available, otherwise use short-name
        acronym = ou.get_name_with_language(self.const.ou_name_acronym,
                                            self.const.language_nb, None)
        short_name = ou.get_name_with_language(self.const.ou_name_short,
                                               self.const.language_nb, None)
        ou_name = acronym and acronym or short_name

        location = "%02d-%02d-%02d (%s)" % (ou.fakultet,
                                            ou.institutt,
                                            ou.avdeling,
                                            ou_name)
        return location

    def _typeset_bool(self, value):
        """Return a human-friendly version of a boolean.
        """

        return bool(value)

    def _assert_unused_service_description(self, description):
        """Check that a description is not in use by any voip_service.
        """
        vs = VoipService(self.db)
        services =  vs.search_voip_service_by_description(description,
                                                          exact_match=True)
        if services:
            raise CerebrumError("Description must be unique. In use by id=%s." \
                                % services[0]['entity_id'])

    ########################################################################
    # voip_service related commands
    #
    all_commands["voip_service_new"] = Command(
        ("voip", "service_new"),
        VoipServiceTypeCode(),
        OU(),
        SimpleString())
    def voip_service_new(self, operator, service_type, ou_tag, description):
        """Create a new voip_service.

        @param service_type: Type of voip_service entry.

        @param ou_tag: OU where the voip_service located (stedkode)

        @param description: service's description. Must be globally unique.
        """

        self.ba.can_create_voip_service(operator.get_entity_id())
        self._assert_unused_service_description(description)
        service = VoipService(self.db)

        ou = self._get_ou(ou_tag)
        service_type = self._get_constant(service_type,
                                          self.const.VoipServiceTypeCode)
        if service_type is None:
            raise CerebrumError("Unknown voip_service_type: %s" %
                                str(service_type))
        service.populate(description, service_type, ou.entity_id)
        service.write_db()

        # Create a corresponding voip_address...
        self._get_or_create_voip_address(service.entity_id)
        return "OK, new voip_service (%s), entity_id=%s" % (str(service_type),
                                                            service.entity_id)
    # end voip_service_new



    all_commands["voip_service_info"] = Command(
        ("voip", "service_info"),
        VoipServiceParameter(),
        fs = FormatSuggestion("Entity id:     %d\n"
                              "Service type:  %s\n"
                              "Description:   %s\n"
                              "Location:      %s\n"
                              "Traits:        %s\n",
                              ("entity_id",
                               "service_type",
                               "description",
                               "location",
                               "traits",)))
    def voip_service_info(self, operator, designation):
        """Return information about a voip_service.

        @param designation: either an entity_id or a description.
        """

        self.ba.can_view_voip_service(operator.get_entity_id())
        service = self._get_voip_service(designation)
        answer = {"entity_id": service.entity_id,
                  "service_type":
                     str(self.const.VoipServiceTypeCode(service.service_type)),
                  "description": service.description,
                  }
        answer["location"] = self._typeset_ou(service.ou_id)
        answer["traits"] = self._typeset_traits(service.get_traits())
        return answer
    # end voip_service_info



    all_commands["voip_service_type_list"] = Command(
        ("voip", "service_type_list"),
        fs=FormatSuggestion("%-32s  %s",
                            ("code_str", "description"),
                            hdr = "%-32s  %s" % ("Type", "Description")))
    def voip_service_type_list(self, operator):
        """List available service_info_code values."""

        return self._collect_constants(self.const.VoipServiceTypeCode)
    # end voip_service_type_list
        


    all_commands["voip_service_delete"] = Command(
        ("voip", "service_delete"),
        VoipServiceParameter())
    def voip_service_delete(self, operator, designation):
        """Delete the specified voip_service.
        
        Caveat: this method assumes that the related voip_address/clients have
        already been deleted. This is by design.
        """

        self.ba.can_create_voip_service(operator.get_entity_id())
        service = self._get_voip_service(designation)
        entity_id, description = service.entity_id, service.description
        service.delete()
        return "OK, deleted voip_service id=%s, %s" % (entity_id,
                                                       description)
    # end voip_service_delete



    all_commands["voip_service_update"] = Command(
        ("voip", "service_update"),
        VoipServiceParameter(),
        SimpleString(optional=True, default=None),
        VoipServiceTypeCode(optional=True, default=None),
        OU(optional=True, default=None))
    def voip_service_update(self, operator, designation, description=None,
                            service_type=None, ou_tag=None):
        """Update information about an existing voip_service.

        Those attributes that are None are left alone.
        """

        self.ba.can_alter_voip_service(operator.get_entity_id())
        service = self._get_voip_service(designation)
        
        if description and service.description != description:
            self._assert_unused_service_description(description)
            service.description = description
        if service_type:
            service_type = self._get_constant(service_type,
                                              self.const.VoipServiceTypeCode)
            if service.service_type != service_type:
                service.service_type = service_type
        if ou_tag:
            ou = self._get_ou(ou_tag)
            if service.ou_id != ou.entity_id:
                service.ou_id = ou.entity_id

        service.write_db()
        return "OK, updated information for voip_service id=%s" % (
            service.entity_id,)
    # end voip_service_update



    all_commands["voip_service_find"] = Command(
        ("voip", "service_find"),
        SimpleString(),
        fs=FormatSuggestion("%8i   %15s   %25s   %8s",
                            ("entity_id", "description", "service_type", "ou"),
                            hdr="%8s   %15s   %25s   %8s" %
                               ("EntityId", "Description",
                                "Type", "Stedkode")))
    def voip_service_find(self, operator, designation):
        """List all voip_services matched in some way by designation.

        This has been requested to ease up looking up voip_services for users.

        designation is used to look up voip_services in the following fashion:
        
          - if all digits -> by entity_id
          - by description (exactly)
          - by description (substring search)
          - if all digits -> by ou_id
          - if all digits -> by stedkode

        All the matching voip_services are collected and returned as a sequence
        so people can pluck out the entities they want and use them in
        subsequent commands. 
        """

        def fold_description(s):
            cutoff = 15
            suffix = "(...)"
            if len(s) > cutoff:
                return s[:(cutoff - len(suffix))] + suffix
            return s
        # end fold_description
        
        self.ba.can_view_voip_service(operator.get_entity_id())
        ident = designation.strip()
        collect = dict()
        vs = VoipService(self.db)

        # let's try by-id lookup first
        if ident.isdigit():
            try:
                vs.find(int(ident))
                collect[vs.entity_id] = (vs.description,
                                         vs.service_type,
                                         vs.ou_id)
            except Errors.NotFoundError:
                pass

        # then by-description...
        for exact_match in (False, True):
            results = vs.search_voip_service_by_description(
                             designation, exact_match=exact_match)
            for row in results:
                collect[row["entity_id"]] = (row["description"],
                                             row["service_type"],
                                             row["ou_id"])

        # then by OU (stedkode and ou_id)
        try:
            ou = self._get_ou(designation)
            for row in vs.search(ou_id=ou.entity_id):
                collect[row["entity_id"]] = (row["description"],
                                             row["service_type"],
                                             row["ou_id"])
        except CerebrumError:
            pass

        # Finally, the presentation layer
        if len(collect) > cereconf.BOFHD_MAX_MATCHES:
            raise CerebrumError("More than %d (%d) matches, please narrow "
                                "search criteria" % (cereconf.BOFHD_MAX_MATCHES,
                                                     len(collect)))

        answer = list()
        for entity_id in collect:
            description, service_type, ou_id = collect[entity_id]
            answer.append({"entity_id": entity_id,
                           "description": fold_description(description),
                           "service_type":
                             str(self.const.VoipServiceTypeCode(service_type)),
                           "ou": self._typeset_ou(ou_id),})
        return answer
    # end voip_service_find

    ########################################################################
    # voip_client related commands

    #
    # voip TODO
    #
    all_commands["voip_client_new"] = Command(
        ("voip", "client_new"),
        VoipOwnerParameter(),
        VoipClientTypeCode(),
        MacAddress(),
        VoipClientInfoCode(),
        YesNo(help_ref='yes_no_sip_enabled', default="Yes"))

    def voip_client_new(self, operator, owner_designation,
                        client_type, mac_address, client_info, sip_enabled=True):
        """Create a new voip_client.

        If the owner (be it voip_service or person) does NOT have a
        voip_address, create that as well.
        """

        self.ba.can_create_voip_client(operator.get_entity_id())
        # Find the owner first...
        owner = self._get_voip_owner(owner_designation)

        if isinstance(sip_enabled, (str, unicode)):
            sip_enabled = self._get_boolean(sip_enabled)

        # Does that mac_address point to something?
        client = None
        try:
            client = self._get_voip_client(mac_address)
        except CerebrumError:
            pass
        # Nasty, as _get_voip_client raises CerebrumError, we can't
        # just raise that in the try clause.
        finally:
            if client:
                raise CerebrumError("Mac address %s is already bound to a "
                                    "voip_client." % str(mac_address))

        # Check that info/type_code make sense...
        ct = self._get_constant(client_type, self.const.VoipClientTypeCode)
        ci = self._get_constant(client_info, self.const.VoipClientInfoCode)

        if not ((ct == self.const.voip_client_type_softphone and not mac_address)
                or
                (ct == self.const.voip_client_type_hardphone and mac_address)):
            raise CerebrumError("Hardphones must have mac; softphones must "
                                "not: %s -> %s" % (str(ct), mac_address))

        # get/create an address for that owner already...
        address = self._get_or_create_voip_address(
            owner.entity_id,
            with_softphone=(ct == self.const.voip_client_type_softphone))

        client = VoipClient(self.db)
        client.populate(address.entity_id, ct, sip_enabled, mac_address, ci)
        client.write_db()
        client.set_auth_data(self.const.voip_auth_sip_secret,
                             client.generate_sip_secret())
        return "OK, created voipClient %s, id=%s" % (str(ct),
                                                     client.entity_id)

    #
    # voip TODO
    #
    all_commands["voip_client_info"] = Command(
        ("voip", "client_info"),
        VoipClientParameter(),
        fs = FormatSuggestion("Entity id:              %d\n"
                              "Client type:            %s\n"
                              "Client info:            %s\n"
                              "Mac address:            %s\n"
                              "sip enabled:            %s\n"
                              "has secret?:            %s\n"
                              "Traits:                 %s\n"
                              "voipAddress id:         %d\n"
                              "voipAddress' owner:     %s\n",
                              ("entity_id",
                               "client_type",
                               "client_info",
                               "mac_address",
                               "sip_enabled",
                               "has_secret",
                               "traits",
                               "voip_address_id",
                               "owner")))

    def voip_client_info(self, operator, designation):
        """Return information about a voip_client.
        """

        self.ba.can_view_voip_client(operator.get_entity_id())
        client = self._get_voip_client(designation)
        address = self._get_voip_address(client.voip_address_id)

        # This is such a bloody overkill... We just need id/name But fuck it,
        # CPU cycles are cheap.
        address_attrs = address.get_voip_attributes()
        client_attrs = client.get_voip_attributes()

        owner = "cn=%s (id=%s)" % (address_attrs["cn"], address.owner_entity_id)
        answer = {"entity_id": client.entity_id,
                  "client_type": client_attrs["sipClientType"],
                  "client_info": client_attrs["sipClientInfo"],
                  "mac_address": client_attrs["sipMacAddress"],
                  "sip_enabled": self._typeset_bool(client_attrs["sipEnabled"]),
                  "has_secret":
                      bool(client.get_auth_data(self.const.voip_auth_sip_secret)),
                  "traits": self._typeset_traits(client.get_traits()),
                  "voip_address_id": client.voip_address_id,
                  "owner": owner,
            }
        return answer

    #
    # voip TODO
    #
    all_commands["voip_client_list_info_code"] = Command(
        ("voip", "client_list_info_code"),
        fs = FormatSuggestion("%-25s  %s",
                              ("code_str", "description"),
                              hdr = "%-25s  %s" % ("Client info code",
                                                   "Description")))

    def voip_client_list_info_code(self, operator):
        """List all possible voip_client info codes."""
        return self._collect_constants(self.const.VoipClientInfoCode)

    #
    # voip TODO
    #
    all_commands["voip_client_list_type_code"] = Command(
        ("voip", "client_list_type_code"),
        fs = FormatSuggestion("%-25s  %s",
                              ("code_str", "description"),
                              hdr = "%-25s  %s" % ("Client type code",
                                                   "Description")))

    def voip_client_list_type_code(self, operator):
        """List all possible voip_client type codes.
        """
        return self._collect_constants(self.const.VoipClientTypeCode)

    #
    # voip TODO
    #
    all_commands["voip_client_delete"] = Command(
        ("voip", "client_delete"),
        VoipClientParameter())

    def voip_client_delete(self, operator, designation):
        """Remove (completely) a voip_client from Cerebrum."""

        self.ba.can_create_voip_client(operator.get_entity_id())
        client = self._get_voip_client(designation)
        entity_id, mac = client.entity_id, client.mac_address
        client.delete()
        return "OK, removed voipClient id=%s (mac=%s)" % (entity_id, mac)

    #
    # voip TODO
    #
    all_commands["voip_client_set_info_code"] = Command(
        ("voip", "client_set_info_code"),
        VoipClientParameter(),
        VoipClientInfoCode())

    def voip_client_set_info_code(self, operator, designation, new_info):
        """Change client_info for a specified client."""
        self.ba.can_alter_voip_client(operator.get_entity_id())

        ci = self._get_constant(new_info, self.const.VoipClientInfoCode)

        client = self._get_voip_client(designation)
        if client.client_type != self.const.voip_client_type_hardphone:
            raise CerebrumError("Can only change hardphones.")

        client.client_info = ci
        client.write_db()
        return "OK, changed for voipClient id=%s" % client.entity_id

    #
    # voip client_sip_enabled <client> yes|no
    #
    all_commands["voip_client_sip_enabled"] = Command(
        ("voip", "client_sip_enabled"),
        VoipClientParameter(),
        YesNo(help_ref='yes_no_sip_enabled'))

    def voip_client_sip_enabled(self, operator, designation, yesno):
        """Set sip_enabled to True/False for a specified client."""

        self.ba.can_alter_voip_client(operator.get_entity_id())

        client = self._get_voip_client(designation)
        status = self._get_boolean(yesno)

        if client.sip_enabled == status:
            return "OK (no changes for client id=%s)" % (client.entity_id)

        client.sip_enabled = status
        client.write_db()
        return "OK (changed sip_enabled to %s for client id=%s)" % (
            client.sip_enabled, client.entity_id)

    #
    # voip client_secrets_reset <client>
    #
    all_commands["voip_client_secrets_reset"] = Command(
        ("voip", "client_secrets_reset"),
        VoipClientParameter())

    def voip_client_secrets_reset(self, operator, designation):
        """Reset all of voip_client's secrets.

        This is useful if a client has been compromised and needs to be reset.
        """

        client = self._get_voip_client(designation)
        self.ba.can_reset_client_secrets(operator.get_entity_id(),
                                         client.entity_id)
        for secret_kind in (self.const.voip_auth_sip_secret,):
            secret = client.generate_sip_secret()
            client.set_auth_data(secret_kind, secret)

        return "OK (reset sip secrets for voip_client id=%s)" % (
            client.entity_id,)
    # end voip_client_secrets_reset

    #
    # voip client_new_secret <client> <secret>
    #
    all_commands["voip_client_new_secret"] = Command(
        ("voip", "client_new_secret"),
        VoipClientParameter(),
        SimpleString())

    def voip_client_new_secret(self, operator, designation, new_secret):
        """Register a new sipSecret for the specified client."""
        client = self._get_voip_client(designation)
        self.ba.can_set_new_secret(operator.get_entity_id(),
                                   client.entity_id)

        # First check the new_secret quality.
        client.validate_auth_data(self.const.voip_auth_sip_secret,
                                  new_secret)
        # Locate current secret
        current_secret = client.get_auth_data(self.const.voip_auth_sip_secret)

        # Register new_secret
        client.set_auth_data(self.const.voip_auth_sip_secret, new_secret)

        return "OK (set new sip secret for voip_client id=%s)" % (
            client.entity_id,)

    ########################################################################
    # voip_address related commands

    #
    # voip address_list_contact_codes
    #
    all_commands["voip_address_list_contact_codes"] = Command(
        ("voip", "address_list_contact_codes"),
        fs=FormatSuggestion(
            "%-25s  %s", ("code_str", "description"),
            hdr="%-25s  %s" % ("Code", "Description")))

    def voip_address_list_contact_codes(self, operator):
        """List all available contact_info_codes.
        """
        return self._collect_constants(self.const.ContactInfo)

    #
    # voip address_add_number <owner> <ctype> <TODO> [TODO]
    #
    all_commands["voip_address_add_number"] = Command(
        ("voip", "address_add_number"),
        VoipOwnerParameter(),
        ContactTypeParameter(),
        SimpleString(help_ref="voip_extension_full"),
        PriorityParameter(optional=True, default=None))

    def voip_address_add_number(self, operator, designation,
                                contact_type, contact_full, priority=None):
        """Add a new phone number to a voip_address at given priority.

        The number is added, assuming that no voip_address already owns either
        full or internal number. internal_number must be set.

        If no priority is specified, one is chosen automatically (it would be
        the lowest possible priority)
        """

        def owner_has_contact(owner, contact_value):
            entity_ids = [
                x["entity_id"] for x in self._get_contact_info(contact_value)]
            return owner.entity_id in entity_ids
        # end owner_has_contact

        def next_priority(owner, priority=None):
            if priority is None:
                so_far = owner.list_contact_info(
                    entity_id=owner.entity_id,
                    source_system=self.const.system_voip)
                result = 1
                if so_far:
                    result = max(x["contact_pref"] for x in so_far) + 1
                return result

            priority = int(priority)
            if priority <= 0:
                raise CerebrumError("Priority must be larger than 0")
            return priority
        # end next_priority

        self.ba.can_alter_number(operator.get_entity_id())

        # Make sure that the number is not in use.
        if self._get_contact_info(contact_full):
            raise CerebrumError("Number %s already in use." % contact_full)

        # Is there an address for that owner already?
        owner = self._get_voip_owner(designation)
        address = self._get_or_create_voip_address(owner.entity_id)

        if contact_type:
            contact_type = self._get_constant(contact_type,
                                              self.const.ContactInfo)
        else:
            contact_type = self.const.contact_voip_extension

        # Deduce 5-digit alias, if contact info is of the proper type.
        contact_alias = None
        if contact_type == self.const.contact_voip_extension:
            contact_alias = contact_full[-5:]

        # Check the numbers for syntax errors
        if not address.contact_is_valid(contact_type,
                                        contact_full, contact_alias):
            raise CerebrumError("(%s, %s) number pair is not a valid number." %
                                (contact_full, contact_alias))

        # Have these numbers already been registered to owner?
        if (owner_has_contact(owner, contact_full)
                or owner_has_contact(owner, contact_alias)):
            raise CerebrumError("%s or %s has already been registered "
                                "for %s." %
                                (contact_full, contact_alias, owner.entity_id))

        # Figure out the priority if it has not been specified
        priority = next_priority(owner, priority)
        owner.add_contact_info(self.const.system_voip,
                               contact_type,
                               contact_full,
                               pref=priority,
                               alias=contact_alias)
        warn = "."
        if contact_alias and not contact_full.endswith(contact_alias):
            warn = " (Short number does not match full number)."

        return "OK, associated %s/%s with owner id=%s%s" % (contact_full,
                                                            contact_alias,
                                                            owner.entity_id,
                                                            warn)

    #
    # voip address_delete_number <TODO> [TODO]
    #
    all_commands["voip_address_delete_number"] = Command(
        ("voip", "address_delete_number"),
        SimpleString(help_ref="voip_extension_full"),
        VoipOwnerParameter(optional=True, default=None))

    def voip_address_delete_number(self, operator, value, owner=None):
        """Delete a previously registered phone number.

        If a phone number is associated with several entities, we cowardly
        refuse, unless owner is specified.

        @param value:
          Contact info string. Could be full or short version of the phone
          number.
        """

        self.ba.can_alter_number(operator.get_entity_id())
        contacts = self._get_contact_info(value)
        if not contacts:
            return "OK, nothing to delete (no record of %s)" % (str(value))

        if owner is not None:
            owner = self._get_voip_owner(owner)

        if len(contacts) > 1 and owner is None:
            raise CerebrumError("Multiple entities have %s registered. You "
                                "must specified entity to update." %
                                (value,))

        eci = EntityContactInfo(self.db)
        victims = set()
        for d in contacts:
            if owner and owner.entity_id != d["entity_id"]:
                continue

            eci.clear()
            eci.find(d["entity_id"])
            eci.delete_contact_info(d["source_system"],
                                    d["contact_type"],
                                    d["contact_pref"])
            victims.add(eci.entity_id)

        return "OK, removed %s from %d entit%s: %s" % (
            str(value), len(victims),
            len(victims) != 1 and "ies" or "y",
            ", ".join("id=%s" % x for x in victims))

    #
    # voip address_info <voip-addr>
    #
    all_commands["voip_address_info"] = Command(
        ("voip", "address_info"),
        VoipAddressParameter(),
        fs=FormatSuggestion("Entity id:              %d\n"
                            "Owner entity id:        %d\n"
                            "Owner type:             %s\n"
                            "cn:                     %s\n"
                            "sipURI:                 %s\n"
                            "sipPrimaryURI:          %s\n"
                            "e164URI:                %s\n"
                            "Extension URI:          %s\n"
                            "Traits:                 %s\n"
                            "Clients:                %s\n",
                            ("entity_id",
                             "owner_entity_id",
                             "owner_entity_type",
                             "cn",
                             "sip_uri",
                             "sip_primary_uri",
                             "e164_uri",
                             "extension_uri",
                             "traits",
                             "clients",)))

    def voip_address_info(self, operator, designation):
        """Display information about ... ?

        The spec says 'all attributes': uname, cn, all URIs, e-mail, etc.

        @param designation:
          uid, id, fnr -- some way of identifying the proper voip-address.
          FIXME: Should be split designation into key:value, where key is one
          of (uname, cn, phone, entity_id/id) and value is the string
          interpreted according to the meaning of the first key.
        """

        address = self._get_voip_address(designation)
        owner = address.get_owner()

        # find the clients
        client = VoipClient(self.db)
        client_ids = sorted(
            [str(x["entity_id"])
             for x in client.search(voip_address_id=address.entity_id)])

        attrs = address.get_voip_attributes()
        result = {
            "entity_id": address.entity_id,
            "owner_entity_id": owner.entity_id,
            "owner_entity_type":
                str(self.const.EntityType(owner.entity_type)),
            "cn": attrs["cn"],
            "sip_uri": attrs["voipSipUri"],
            "sip_primary_uri": attrs["voipSipPrimaryUri"],
            "e164_uri": attrs["voipE164Uri"],
            "extension_uri": attrs["voipExtensionUri"],
            "traits": self._typeset_traits(address.get_traits()),
            "clients": client_ids,
        }

        return result

    #
    # void address_delete <voip-addr>
    #
    all_commands["voip_address_delete"] = Command(
        ("voip", "address_delete"),
        VoipAddressParameter())

    def voip_address_delete(self, operator, designation):
        """Delete a voip_address from Cerebrum.

        This is useful as a precursor to removing a service.
        """

        self.ba.can_alter_voip_address(operator.get_entity_id())
        address = self._get_voip_address(designation)

        # Without this check users risk seeing an internal error, rather than
        # a detailed error message.
        client = VoipClient(self.db)
        clients = list(client.search(voip_address_id=address.entity_id))
        if clients:
            raise CerebrumError("Won't delete address id=%s: "
                                "it has %d voip_client(s)" %
                                (address.entity_id, len(clients)))

        address_id = address.entity_id
        owner = address.get_owner()
        address.delete()
        return "OK, deleted voip_address id=%s (owned by %s id=%s)" % (
            address_id,
            self.const.EntityType(owner.entity_type),
            owner.entity_id)

    #
    # voip address_find <search-param>
    #
    all_commands["voip_address_find"] = Command(
        ("voip", "address_find"),
        SimpleString(),
        fs=FormatSuggestion(
            "%9i %14i %13s %25s",
            ("entity_id",
             "owner_entity_id",
             "owner_type",
             "cn"),
            hdr="%9s %14s %13s %25s" % (
                "EntityId", "OwnerEntityId", "Owner type", "CN")))

    def voip_address_find(self, operator, designation):
        """List all voip_addresses matched in some way by designation.

        This has been requested to ease up searching for specific
        voip_addresses.
        """
        vas = self._get_voip_address(designation, all_matches=True)
        # Finally, the presentation layer
        if len(vas) > cereconf.BOFHD_MAX_MATCHES:
            raise CerebrumError("More than %d (%d) matches, please narrow down"
                                "the search criteria" %
                                (cereconf.BOFHD_MAX_MATCHES, len(vas)))
        answer = list()
        for va in vas:
            # NB! This call is pretty expensive. We may want to revise
            # BOFHD_MAX_MATCHES-cutoff here (and rather replace it with
            # something more stringent)
            voip_attrs = va.get_voip_attributes()
            answer.append({"entity_id": va.entity_id,
                           "owner_entity_id": va.owner_entity_id,
                           "owner_type": str(voip_attrs["owner_type"]),
                           "cn": voip_attrs["cn"],})
        return answer

#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2010-2018 University of Oslo, Norway
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

"""This module implements voip address functionality for voip.

Each voip address in Cerebrum is represented by an entry in voip_address
table, and a number of rows in related tables. This module implements an
interface to these tables, so that voip_address (and associated data) can be
accessed from Python.

voip addresses themselves are a representation of people/locations with regard
to phone numbers. A person has at most one voip-address. A location (called
voip service) has at most one voip-address. A voip-address CANNOT exist
without a corresponding person/voip-service owner.
"""

from __future__ import unicode_literals

import cereconf
from six import text_type

from Cerebrum.modules.no.uio.voip.EntityAuthentication import EntityAuthentication
from Cerebrum.modules.no.uio.voip.voipService import VoipService
from Cerebrum.modules.EntityTrait import EntityTrait
from Cerebrum.Entity import EntityContactInfo
from Cerebrum.Entity import Entity
from Cerebrum.Utils import Factory
from Cerebrum.Utils import argument_to_sql
from Cerebrum.modules import Email
from Cerebrum import Errors


class VoipAddress(EntityAuthentication, EntityTrait):
    """VoIP address interface"""

    __read_attr__ = ("__in_db",)
    __write_attr__ = ("owner_entity_id",)
    _required_voip_attributes = ("voipOwnerId", "uid", "mail", "cn",
                                 "voipSipUri", "voipSipPrimaryUri",
                                 "voipE164Uri", "voipExtensionUri",
                                 "voipSKO",)

    def clear(self):
        """Reset VoipAddress."""
        self.__super.clear()
        self.clear_class(VoipAddress)
        self.__updated = list()

    def populate(self, owner_entity_id):
        """Create a new VoipAddress in memory.

        FIXME: check that owner_entity_type is voip_service/person.
        FIXME: check that owner_entity_id does not own other voipAddresses.
        """
        EntityTrait.populate(self, self.const.entity_voip_address)
        try:
            if not self.__in_db:
                raise RuntimeError("populate() called multiple times.")
        except AttributeError:
            self.__in_db = False
        self.owner_entity_id = owner_entity_id

    def write_db(self):
        """Synchronise the object in memory with the database.

        FIXME: check that owner_entity_type is voip_service/person.
        FIXME: check that owner_entity_id does not own other voipAddresses.
        """

        self.__super.write_db()
        if not self.__updated:
            return

        is_new = not self.__in_db
        binds = {
            "entity_type": self.const.entity_voip_address,
            "entity_id": self.entity_id,
            "owner_entity_id": self.owner_entity_id,
        }
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=voip_address]
            VALUES (:entity_type, :entity_id, :owner_entity_id)
            """, binds)
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=voip_address]
            SET owner_entity_id = :owner_entity_id
            WHERE entity_id = :entity_id
            """, binds)
        # Reset the cerebrum auto_updater magic
        del self.__in_db
        self.__in_db = True
        self.__updated = list()
        return is_new

    def delete(self):
        """Remove a specified entry from the voip_address table.

        Be mindful of the fact that multiple voip_client rows may
        refer to a single voip_address row.
        """
        if self.__in_db:
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=voip_address]
            WHERE entity_id = :entity_id
            """, {"entity_id": self.entity_id})
        self.__super.delete()

    def find(self, entity_id):
        """Locate voipAddress by entity_id."""
        self.__super.find(entity_id)
        self.owner_entity_id = self.query_1("""
            SELECT owner_entity_id
            FROM [:table schema=cerebrum name=voip_address]
            WHERE entity_id = :entity_id
            """, {"entity_id": self.entity_id})
        self.__in_db = True

    def find_by_owner_id(self, owner_id):
        """Locate voipAddress by its owner_id."""

        entity_id = self.query_1("""
        SELECT entity_id
        FROM [:table schema=cerebrum name=voip_address]
        WHERE owner_entity_id = :owner_entity_id
        """, {"owner_entity_id": owner_id})
        self.find(entity_id)

    def find_by_contact_info(self, designation):
        """Locate voip address by a contact info tidbit.

        We filter contact_info entries implicitly by system_voip. Furthermore,
        the contact information is associated with voipAddress' *OWNER*,
        rather than the voipAddress itself.

        L{designation} can be any string.
        """
        entity_id = self.query_1("""
        SELECT va.entity_id
        FROM [:table schema=cerebrum name=voip_address] va,
             [:table schema=cerebrum name=entity_contact_info] eci
        WHERE va.owner_entity_id = eci.entity_id AND
              eci.source_system = [:get_constant name=system_voip] AND
              (eci.contact_value = :value OR eci.contact_alias = :value)
        """, {"value": text_type(designation)})
        self.find(entity_id)

    def search(self, owner_entity_id=None, owner_entity_type=None):
        """Search for voip_addresses matching the filtering criteria."""
        where = ["va.owner_entity_id = ei.entity_id", ]
        binds = dict()
        if owner_entity_id is not None:
            where.append(argument_to_sql(owner_entity_id, "va.owner_entity_id",
                                         binds, int))
        if owner_entity_type is not None:
            where.append(argument_to_sql(owner_entity_type, "ei.entity_type",
                                         binds, int))
        if where:
            where = "WHERE " + " AND ".join(where)
        else:
            where = ""

        return self.query("""
        SELECT va.entity_id,
               va.owner_entity_id, ei.entity_type as owner_entity_type
        FROM [:table schema=cerebrum name=voip_address] va,
             [:table schema=cerebrum name=entity_info] ei
        """ + where, binds)

    def get_owner(self):
        """Return the owner object of the proper type."""
        ent = Entity(self._db)
        ent.find(self.owner_entity_id)
        if ent.entity_type == self.const.entity_voip_service:
            result = VoipService(self._db)
            result.find(self.owner_entity_id)
            return result
        ent.clear()
        return ent.get_subclassed_object(self.owner_entity_id)

    _voip_prefix = "sip:"

    def _voipify(self, value, suffix="@voip.uio.no"):
        prefix = self._voip_prefix
        if suffix and not value.endswith(suffix):
            return prefix + value + suffix
        return prefix + value

    def _voipify_short(self, value, suffix="@uio.no"):
        prefix = self._voip_prefix
        if suffix and not value.endswith(suffix):
            return prefix + value + suffix
        return prefix + value

    def get_voip_attributes(self):
        """Return a dict with all LDAP attributes available for voipAddress.

        The calculation is a bit involved, since we need a lot of crap.

        Specifically, we collect:

        * uid (feide-id) e.g. mape
        * mail (primary email address) e.g. marius.pedersen@usit.uio.no
        * cn (fullt navn - fra cerebrum) e.g. Marius Pedersen
        * voipSipUri (alle gyldige sip urier for denne uid, inkludert sip
          urier som  inneholder extensions og mail-addresser) e.g.

            o sip:+4722852426@voip.uio.no
            o sip:52426@uio.no
            o sip:marius.pedersen@usit.uio.no

        * voipSipPrimaryUri (sip uri generet fra primary email address)
          e.g. sip:marius.pedersen@usit.uio.no

        * voipE164Uri (sip uri generet fra 8-sifret uio-nummer)e.g.
          sip:+4722852426@voip.uio.no

        * voipExtensionUri (sip uri generert fra 5-sifret uio-nummer)
          e.g. sip:52426@uio.no

        * voipSKO (6 digit "stedkode") e.g. 112233
        """
        voipify = self._voipify
        voipify_short = self._voipify_short

        owner = self.get_owner()
        result = dict((key, None) for key in self._required_voip_attributes)
        result.update(self._get_owner_voip_attributes(owner))
        result["owner_type"] = self.const.EntityType(owner.entity_type)

        uris = result.get("voipSipUri") or list()
        for row in owner.get_contact_info(source=self.const.system_voip):
            uris.append(voipify(row["contact_value"]))
            if row["contact_alias"]:
                uris.append(voipify_short(row["contact_alias"]))

        if result["mail"]:
            value = voipify(result["mail"], None)
            result["voipSipPrimaryUri"] = value
            if owner.entity_type != self.const.entity_person:
                uris.append(value)
        result["voipSipUri"] = uris

        e164 = owner.get_contact_info(self.const.system_voip,
                                      self.const.contact_voip_extension)
        if e164:
            result["voipE164Uri"] = voipify(e164[0]["contact_value"])
            if e164[0]["contact_alias"]:
                result["voipExtensionUri"] = voipify_short(
                    e164[0]["contact_alias"])

        return result

    def _get_owner_voip_attributes(self, owner):
        if owner.entity_type == self.const.entity_person:
            return self._get_person_owner_attributes(owner)
        elif owner.entity_type == self.const.entity_voip_service:
            return self._get_voip_service_owner_attributes(owner)
        assert RuntimeError("Unknown voipAddress owner type: %s" %
                            self.const.EntityType(owner.entity_type))

    def _get_voip_service_owner_attributes(self, owner):
        """Return a dict with voip_service tidbits for LDAP.

        FIXME: THIS MUST NOT FAIL with NotFoundError.
        """

        result = dict()
        result["uid"] = text_type(owner.entity_id)
        result["mail"] = result["uid"] + "@usit.uio.no"
        result["cn"] = owner.description
        return result

    def _get_person_owner_attributes(self, owner):
        """Return a dict with person tidbits for LDAP.

        FIXME: THIS MUST NOT FAIL with NotFoundError.
        """

        def extract_email_from_account(account_id):
            try:
                et = Email.EmailTarget(self._db)
                et.find_by_target_entity(account_id)
                return ["%s@%s" % (r['local_part'], r['domain'])
                        for r in et.get_addresses(special=False)]
            except Errors.NotFoundError:
                return []

        result = dict()
        # uid
        try:
            account_id = owner.get_primary_account()
            acc = Factory.get("Account")(self._db)
            acc.find(account_id)
            result["uid"] = acc.account_name
        except Errors.NotFoundError:
            result["uid"] = None

        # ALL unames must go into 'voipSipUri'. And so must all e-mail
        # addresses.
        result["voipSipUri"] = list()
        for row in acc.search(owner_id=owner.entity_id):
            result["voipSipUri"].append(self._voipify(row["name"], None))
            for address in extract_email_from_account(row["account_id"]):
                mangled = self._voipify(address, None)
                result["voipSipUri"].append(mangled)

        # mail - primary e-mail address.
        if result['uid']:
            try:
                et = Email.EmailTarget(self._db)
                et.find_by_target_entity(acc.entity_id)
                epat = Email.EmailPrimaryAddressTarget(self._db)
                epat.find(et.entity_id)
                ea = Email.EmailAddress(self._db)
                ea.find(epat.get_address_id())
                result["mail"] = ea.get_address()
            except Errors.NotFoundError:
                result["mail"] = None

        # cn - grab system cached
        try:
            p_name = owner.get_name(self.const.system_cached,
                                    getattr(self.const,
                                            cereconf.DEFAULT_GECOS_NAME))
        except Errors.NotFoundError:
            p_name = None

        result["cn"] = p_name
        return result

    def contact_is_valid(self, contact_type, value, alias=None):
        """Check if contact value is legal.

        For now, we'll check contact_voip_extension only.

        Accepted syntax for value -- +DDDDDDDDDD
        Accepted syntax for alias -- DDDDD

        Additionally we have a range restriction (specified in cereconf).

        Furthermore, this may come in handy:

        <http://www.npt.no/portal/page/web/PG_NPT_NO_NO/PAG_NPT_NO_HOME/PAG_RESSURSER_TEKST?p_d_i=-121&p_d_c=&p_d_v=47033>
        """

        if contact_type != self.const.contact_voip_extension:
            return True

        # They must be strings...
        if not (isinstance(value, (str, text_type)) and
                isinstance(alias, (str, text_type))):
            return False

        # This is a UiO number -- 8 digits and 5 digits for the internal number.
        prefix, number = value[:3], value[3:]
        if not (len(number) == 8 and len(alias) == 5):
            return False

        # value must start with a + and be followed by digits only
        if not (value[0] == "+" and value[1:].isdigit() and alias.isdigit()):
            return False

        # Norway == +47
        if prefix != "+47":
            return False

        # They must be within proper range
        # ... first check that the number does not match those series that are
        # invalid.
        if any(low <= int(number) <= high
               for (low, high) in
               getattr(cereconf, "VOIP_INVALID_PHONE_RANGES", ())):
            return False

        # ... then check that the number falls within a valid range
        if hasattr(cereconf, "VOIP_VALID_PHONE_RANGES"):
            if not any(low <= int(number) <= high
                       for (low, high) in cereconf.VOIP_VALID_PHONE_RANGES):
                return False

        # Finally, it has to be a valid number.
        return True

    def list_voip_attributes(self, *args):
        """Return a generator over what looks like get_voip_attributes() return
        value.

        *args passes cached look ups from generate_voip_ldif.py to
        _cache_owner_person_attrs.

        This is a speed up function for LDAP export. The idea is to cache all
        the attributes up front, so we don't have to pay a penalty associated
        with multiple database lookups per voipAddress.
        """

        # ou_id -> stedkode
        # Will pass it to the cache functions so we can get stedkode and not OUs back
        ou = Factory.get("OU")(self._db)
        ou2sko = dict((x["ou_id"], "%02d%02d%02d" % (
            x["fakultet"], x["institutt"], x["avdeling"]))
            for x in ou.get_stedkoder())

        owner_data = self._cache_owner_voip_service_attrs(ou2sko)
        owner_data.update(self._cache_owner_person_attrs(ou2sko, *args))
        voipify = self._voipify
        voipify_short = self._voipify_short

        # owner_id -> sequence of contact info (value, alias)-pairs
        owner2contact_info = dict()
        eci = EntityContactInfo(self._db)
        for row in eci.list_contact_info(source_system=self.const.system_voip):
            owner_id = row["entity_id"]
            tpl = (row["contact_value"], row["contact_alias"])
            owner2contact_info.setdefault(owner_id, list()).append(tpl)

        # owner_id -> mobile
        owner2mobiles = dict()
        for row in eci.list_contact_info(
                source_system=self.const.system_sap,
                contact_type=self.const.contact_mobile_phone,
                entity_type=self.const.entity_person):
            owner2mobiles.setdefault(row["entity_id"], list()).append(
                row["contact_value"])

        for row in self.search():
            entry = dict((key, None) for key in self._required_voip_attributes)
            entry["voipOwnerId"] = text_type(row["owner_entity_id"])
            entry["voipSipUri"] = list()
            entry["entity_id"] = row["entity_id"]
            owner_id = row["owner_entity_id"]

            # Why this way? Well, if owner_data has required attributes and they
            # are missing, the LDAP import will fail (by design). We cannot
            # allow that, if the sole reason for missing entry is the fact that
            # owner_data cache dict is out of sync at this point (it takes a
            # while to construct that dict)
            if owner_id not in owner_data:
                continue

            entry.update(owner_data[owner_id])

            # voipSipUri
            for item in owner2contact_info.get(owner_id, list()):
                full, alias = item
                entry["voipSipUri"].append(voipify(full))
                if alias:
                    entry["voipSipUri"].append(voipify_short(alias))
            if entry["mail"]:
                value = self._voipify(entry["mail"], None)
                entry["voipSipPrimaryUri"] = value
                if entry["voipOwnerType"] != "person":
                    entry["voipSipUri"].append(value)

            entry["mobile"] = owner2mobiles.get(owner_id, list())

            # voipE164Uri + voipExtensionUri
            if owner2contact_info.get(owner_id):
                full, alias = owner2contact_info[owner_id][0]
                entry["voipE164Uri"] = voipify(full)
                if alias:
                    entry["voipExtensionUri"] = voipify_short(alias)

            yield entry

    def _cache_owner_voip_service_attrs(self, ou2sko):
        # First cache the constants
        const2str = dict()
        for cnst in self.const.fetch_constants(self.const.VoipServiceTypeCode):
            assert int(cnst) not in const2str
            const2str[int(cnst)] = text_type(cnst)
        # Second the voipServices...
        vp = VoipService(self._db)
        owner_data = dict()
        for row in vp.search():
            uid = text_type(row["entity_id"])
            ou = row["ou_id"]
            owner_data[row["entity_id"]] = {
                "uid": uid,
                "mail": uid + "@usit.uio.no",
                "cn": row["description"],
                "voipOwnerType": "service",
                "voipServiceType": const2str[row["service_type"]],
                "voipSKO": (ou2sko[ou],),
            }
        return owner_data

    def _join_address(self, local_part, domain):
        return "@".join((local_part, domain))

    def _cache_owner_person_attrs(self, ou2sko, voippersons, primary2pid,
                                  sysadm_aid):
        """Preload the person owner attributes (i.e. the ones specific to people)."""

        owner_data = dict()

        # Now the tough part -- people
        p = Factory.get("Person")(self._db)
        for person in voippersons:
            owner_data[person] = {
                "uid": list(),
                "voipOwnerType": "person",
                "voipSKO": set(),
            }

        # Fill out 'cn'
        for row in p.search_person_names(
                person_id=voippersons,
                name_variant=getattr(self.const,
                                     cereconf.DEFAULT_GECOS_NAME,
                                     self.const.name_full),
                source_system=self.const.system_cached):
            owner_data[row["person_id"]]["cn"] = row["name"]

        # Fill out 'uid', 'mail'
        account = Factory.get("Account")(self._db)
        et = Email.EmailTarget(self._db)
        a_id2primary_mail = dict(
            (r["target_entity_id"],
             self._join_address(r["local_part"], r["domain"]))
            for r in et.list_email_target_primary_addresses(
                target_entity_id=primary2pid.keys(),
                target_type=self.const.email_target_account))

        # person -> stedkode
        for row in p.list_affiliations(
                person_id=voippersons,
                source_system=(self.const.system_sap,
                               self.const.system_manual,)):
            owner_data[row["person_id"]]["voipSKO"].add(ou2sko[row["ou_id"]])

        for row in account.search(owner_type=self.const.entity_person,
                                  owner_id=voippersons,
                                  exclude_account_id=sysadm_aid):
            if row["owner_id"] not in owner_data:
                continue
            aid = row["account_id"]
            owner_data[row["owner_id"]]["uid"].append(row["name"])
            if aid not in primary2pid:
                continue
            owner_data[row["owner_id"]]["voipPrimaryUid"] = row["name"]
            pid = primary2pid[aid]
            if pid != row["owner_id"]:
                # This could happen if somebody yanks a person object out of the
                # database while we scan the accounts. Typically --
                # join_persons.py. Another possibility is a manual update of
                # account's owner_id (that may occur, but quite rarely). 
                #
                # The only (?) sensible strategy is to drop the old person_id
                # from owner_data. Even if it's unfair, the next run would yield
                # the proper data.
                # Ideally, there should be a message here somewhere...
                continue
            owner_data[pid]["mail"] = a_id2primary_mail.get(aid)

        del a_id2primary_mail
        return self._cache_owner_person_sip_uris(owner_data)

    def _cache_owner_person_sip_uris(self, owner_data):
        """Preload the person owner sipURI attributes for all voipAddresses."""

        account = Factory.get("Account")(self._db)
        uname2mails = account.getdict_uname2mailaddr(primary_only=False)

        key = 'voipSipUri'
        for person_id in owner_data:
            chunk = owner_data[person_id]
            for uname in chunk["uid"]:
                chunk.setdefault(key, list()).append(
                    self._voipify(uname, None))
                for address in uname2mails.get(uname, ()):
                    chunk[key].append(self._voipify(address, None))

        del uname2mails
        return owner_data

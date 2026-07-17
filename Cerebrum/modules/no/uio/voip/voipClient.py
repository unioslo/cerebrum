# -*- encoding: utf-8 -*-
#
# Copyright 2010-2024 University of Oslo, Norway
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

"""This module implements voip_client functionality for voip.

Each client in voip is an entity capable of being called to/from (such as an
ip-phone device, or a softphone or indeed something completely
different). This module implements an API managing client-related data.

The connection chain between all voip entities looks something like this:

   VoipClient ---[belongs to]---+
                                |
              +-----------------+
              |
              +--> VoipAddress ---[owned by]---> Person or VoipService

Each voip address in Cerebrum is represented by an entry in voip_address
table, and a number of rows in related tables. This module implements an
interface to these tables, so that voip_address (and associated data) can be
accessed from Python.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import random
import string

from collections import defaultdict

import six

import Cerebrum.Constants
from Cerebrum.QuarantineHandler import QuarantineHandler
from Cerebrum.Utils import Factory
from Cerebrum.Utils import argument_to_sql
from Cerebrum.utils import date_compat
from Cerebrum.modules.EntityTrait import EntityTrait
from Cerebrum.modules.bofhd.errors import CerebrumError
from . import EntityAuthentication
from . import Constants as _VoipConstants


SIP_SECRET_ALPHABET = (string.ascii_letters
                       + string.digits
                       + ",.;:-_/!#{}[]+?")
SIP_SECRET_LENGTH = 15


def _validate_sip_secret(auth_data):
    """ Validate sip secret. """
    # Sip secrets have to follow a few rules.
    # all chars are from a preset alphabet
    invalid_chars = set(auth_data) - set(SIP_SECRET_ALPHABET)
    if invalid_chars:
        raise CerebrumError("Invalid chars in sip secret: %s"
                            % ", ".join(sorted(invalid_chars)))

    # secret is at least 15 characters in length
    if len(auth_data) < SIP_SECRET_LENGTH:
        raise CerebrumError("Too short sip secret: length %d (%d required)"
                            % (len(auth_data), SIP_SECRET_LENGTH))


def generate_sip_secret():
    """Generate a new sip secret."""
    alphabet = SIP_SECRET_ALPHABET
    pwd = list()
    while len(pwd) < SIP_SECRET_LENGTH:
        pwd.append(alphabet[random.randint(0, len(alphabet) - 1)])
    # FIXME: call a validate_auth_data here?
    return "".join(pwd)


def _normalize_mac_address(mac_address):
    """
    Normalize mac address to lowercase, ':' separated hex-bytes.

    >>> _normalize_mac_address('aabbccddeeff')
    "aa:bb:cc:dd:ee:ff"
    >>> _normalize_mac_address('aa bb cc dd ee ff')
    "aa:bb:cc:dd:ee:ff"
    >>> _normalize_mac_address('AA:BB:CC:DD:EE:FF')
    "aa:bb:cc:dd:ee:ff"
    """
    if not mac_address:
        return None
    addr = mac_address.replace(" ", "").replace(":", "")
    addr = addr.lower()
    if not all(x in "0123456789abcdef" for x in addr):
        raise CerebrumError("Wrong mac character in " + repr(addr))
    if not len(addr) == 12:
        raise CerebrumError("Wrong mac length for " + repr(addr))
    return ":".join(addr[i:i+2] for i in range(0, 12, 2))


class VoipClient(EntityAuthentication.EntityAuthentication, EntityTrait):
    """VoIP client interface."""

    __read_attr__ = ("__in_db",)
    __write_attr__ = (
        "voip_address_id",  # corresponding VoipAddress
        "client_type",      # soft/hardphone
        "sip_enabled",      # emergency(?) flag (T/F)
        "mac_address",      # syntax -- aa:bb:cc:dd:ee:ff
        "client_info",      # specific model code
    )

    def __init__(self, *rest, **kw):
        super(VoipClient, self).__init__(*rest, **kw)
        self.valid_auth_methods = (self.const.voip_auth_sip_secret,)

    def clear(self):
        super(VoipClient, self).clear()
        self.clear_class(VoipClient)
        self.__updated = list()

    def _assert_mac_rules(self):
        """
        Check that self's *mac_address* is in sync with the business rules.
        """
        if self.client_type == self.const.voip_client_type_softphone:
            assert _normalize_mac_address(self.mac_address) is None
            return

        if self.client_type == self.const.voip_client_type_hardphone:
            assert _normalize_mac_address(self.mac_address)
            return

    def populate(self, voip_address_id, client_type, sip_enabled,
                 mac_address, client_info):
        """Create a new VoipClient in memory."""

        assert sip_enabled in (True, False)
        mac_address = _normalize_mac_address(mac_address)
        super(VoipClient, self).populate(self.const.entity_voip_client)

        try:
            if not self.__in_db:
                raise RuntimeError("populate() called multiple times.")
        except AttributeError:
            self.__in_db = False

        self.voip_address_id = int(voip_address_id)
        self.client_type = int(self.const.VoipClientTypeCode(client_type))
        self.sip_enabled = bool(sip_enabled)
        self.mac_address = mac_address
        self.client_info = int(self.const.VoipClientInfoCode(client_info))
        self._assert_mac_rules()

    def write_db(self):
        """
        Synchronise the object in memory with the database.
        """
        self._assert_mac_rules()
        super(VoipClient, self).write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        binds = {
            "entity_type": int(self.const.entity_voip_client),
            "entity_id": int(self.entity_id),
            "voip_address_id": int(self.voip_address_id),
            "client_type": int(self.client_type),
            "sip_enabled": bool(self.sip_enabled) and 'T' or 'F',
            "mac_address": _normalize_mac_address(self.mac_address),
            "client_info": int(self.client_info),
        }
        if is_new:
            self.execute(
                """
                  INSERT INTO [:table schema=cerebrum name=voip_client]
                  VALUES (:entity_type, :entity_id, :voip_address_id,
                          :client_type, :sip_enabled, :mac_address,
                          :client_info)
                """,
                binds,
            )
        else:
            self.execute(
                """
                  UPDATE [:table schema=cerebrum name=voip_client]
                  SET {}
                  WHERE entity_id = :entity_id
                """.format(", ".join("%s=:%s" % (t, t) for t in binds)),
                binds,
            )

        # Reset the cerebrum auto_updater magic
        del self.__in_db
        self.__in_db = True
        self.__updated = list()
        return is_new

    def delete(self):
        """Remove a specified entry from the voip_client table."""
        if self.__in_db:
            self.execute(
                """
                  DELETE FROM [:table schema=cerebrum name=voip_client]
                  WHERE entity_id = :entity_id
                """,
                {"entity_id": int(self.entity_id)},
            )
        super(VoipClient, self).delete()

    def find(self, entity_id):
        """Locate VoipClient by its entity_id."""
        super(VoipClient, self).find(entity_id)

        (
            self.voip_address_id,
            self.client_type,
            sip_enabled,
            self.mac_address,
            self.client_info,
        ) = self.query_1(
            """
              SELECT voip_address_id, client_type, sip_enabled,
                     mac_address, client_info
              FROM [:table schema=cerebrum name=voip_client]
              WHERE entity_id = :entity_id
            """,
            {"entity_id": int(self.entity_id)},
        )

        # FIXMe: Do we really want the API to fail here?
        assert sip_enabled in ('T', 'F')
        self.sip_enabled = sip_enabled == 'T'
        self.__in_db = True

    def find_by_mac_address(self, mac_address):
        entity_id = self.query_1(
            """
              SELECT entity_id
              FROM [:table schema=cerebrum name=voip_client]
              WHERE mac_address = :mac_address
            """,
            {"mac_address": _normalize_mac_address(mac_address)},
        )
        self.find(entity_id)

    def get_auth_data(self, auth_method):
        """
        Retrieve the corresponding sip secret.

        Only one type is allowed: sip_secret
        """
        assert auth_method in self.valid_auth_methods
        return super(VoipClient, self).get_auth_data(auth_method)

    def set_auth_data(self, auth_method, auth_data):
        """Register a new sip secret."""
        assert auth_method in self.valid_auth_methods
        return super(VoipClient, self).set_auth_data(auth_method, auth_data)

    def validate_auth_data(self, auth_method, auth_data):
        """Check that sip secrets match our rules."""
        if not isinstance(auth_data, six.string_types):
            raise CerebrumError("Invalid type of auth data: %s (expected str)"
                                % (type(auth_data)))

        if auth_method in self.valid_auth_methods:
            _validate_sip_secret(auth_data)
            return True

        return super(VoipClient, self).validate_auth_data(auth_method,
                                                          auth_data)

    def generate_sip_secret(self):
        """Return a freshly generated sip secret."""
        return generate_sip_secret()

    def get_voip_attributes(self):
        """
        Return a dict with all LDAP attributes available for voipClient.
        """
        result = {
            'sipClientInfo': six.text_type(
                self.const.VoipClientInfoCode(self.client_info)
            ),
            'sipClientType': six.text_type(
                self.const.VoipClientTypeCode(self.client_type)
            ),
            'sipEnabled': bool(self.sip_enabled),
            'sipMacAddress': None,
            'sipSecret': self.get_auth_data(self.const.voip_auth_sip_secret),
            'uid': None,
            'voip_address_id': self.voip_address_id,
        }
        if self.mac_address:
            result["sipMacAddress"] = self.mac_address.replace(":", "")
        return result

    def list_voip_attributes(self, voippersons, primary2pid, sysadm_aid):
        """
        Fast version of search() + get_voip_attributes().

        Simply put, with tens of thousands of objects, find() +
        get_voip_attributes() is unfeasible.

        This method returns a generator that yields similar results as the
        above combination for each VoipClient.
        """
        # So, a few things we need to cache
        const2str = dict()
        for i in (Cerebrum.Constants._QuarantineCode,
                  _VoipConstants._VoipClientInfoCode,
                  _VoipConstants._VoipClientTypeCode):
            for cnst in self.const.fetch_constants(i):
                assert int(cnst) not in const2str
                const2str[int(cnst)] = six.text_type(cnst)

        # entity_id -> {<auth type>: <auth_data>}
        client2auth = dict()
        for row in self.list_auth_data(self.const.voip_auth_sip_secret):
            client2auth.setdefault(row['entity_id'],
                                   {})[row['auth_method']] = row['auth_data']

        # person_id -> uname, also cache user ids
        owner2uname = defaultdict(list)
        aid2owner = dict()
        account = Factory.get("Account")(self._db)
        for r in account.search(owner_type=self.const.entity_person,
                                owner_id=voippersons,
                                exclude_account_id=sysadm_aid):
            owner2uname[r["owner_id"]].append(r["name"])
            aid2owner[r["account_id"]] = r["owner_id"]

        # Get account identificators that have a quarantine that should result
        # in the account beeing locked.
        quarantined_accounts = QuarantineHandler.get_locked_entities(
            self._db, entity_ids=set(aid2owner.keys()))

        # Populate account_id -> quarantine information dictionary
        aid2quarantine = dict()
        for row in account.list_entity_quarantines(
                entity_types=self.const.entity_account,
                only_active=True,
                entity_ids=quarantined_accounts):
            aid2quarantine[row["entity_id"]] = (
                "{},{},{}".format(
                    const2str[row['quarantine_type']],
                    date_compat.get_date(row['start_date']).isoformat(),
                    row['description'],
                ))

        # Make a owner2quarantine, to block hardphone is if primary users is
        # blocked
        owner2quarantine = dict()
        for aid in aid2quarantine:
            # Of course some users have missing affiliations, thus no
            # primaryid.  Check if they at least have less than two accounts,
            # then the aid is the primaryid.
            if aid in primary2pid or len(owner2uname[aid2owner[aid]]) < 2:
                owner2quarantine[aid2owner[aid]] = aid2quarantine[aid]

        # uname -> HA1 hashes, only for softphone for Account users aka
        # persons.
        uname2ha1 = dict()
        uname2quarantine = dict()
        for row in account.list_account_authentication(
                self.const.auth_type_ha1_md5,
                account_id=set(aid2owner.keys())):
            if row['account_id'] in aid2quarantine:
                uname2quarantine[row['entity_name']] = aid2quarantine.get(
                    row["account_id"])
            uname2ha1[row['entity_name']] = row['auth_data']

        # Caching complete - generate entries:
        for row in self.search():
            entry = {
                "sipClientType": const2str[row["client_type"]],
                "sipClientInfo": const2str[row["client_info"]],
                "voip_address_id": row["voip_address_id"],
            }
            owner_id = row["owner_entity_id"]
            client_type = row["client_type"]
            if row["sip_enabled"] == 'T':
                entry["sipEnabled"] = "TRUE"
            else:
                entry["sipEnabled"] = "FALSE"

            # Create an extra softphone entry for each account
            if (client_type == self.const.voip_client_type_softphone
                    and row["owner_entity_type"] == self.const.entity_person):
                for uid in owner2uname[owner_id]:
                    e = entry.copy()
                    e["uid"] = six.text_type(uid)
                    if uid in uname2quarantine:
                        e["sipQuarantine"] = uname2quarantine[uid]
                        e["sipEnabled"] = "quarantined"
                    e["ha1MD5password"] = uname2ha1.get(uid) or "missing"
                    # XXX: will be altered in next revision when
                    # voip_softphone/softphone becomes voip_hardhone/softphone.
                    e["sipClientInfo"] = "sbc2phone"
                    yield e

            entry["sipSecret"] = client2auth.get(row["entity_id"], {}).get(
                self.const.voip_auth_sip_secret)

            if row["owner_entity_type"] == self.const.entity_person:
                # Block if primary user is quarantined
                if owner_id in owner2quarantine:
                    entry["sipEnabled"] = "quarantined"
                    entry["sipQuarantine"] = owner2quarantine[owner_id]
                # Block if the person has no valid account
                elif not owner2uname[owner_id]:
                    entry["sipEnabled"] = "noaccount"

            if client_type == self.const.voip_client_type_softphone:
                entry["uid"] = six.text_type(owner_id)
            elif client_type == self.const.voip_client_type_hardphone:
                mac = row["mac_address"]
                mac = mac.replace(":", "")
                entry["sipMacAddress"] = mac
            yield entry

    def search(self, entity_id=None, voip_address_id=None, voip_owner_id=None,
               client_type=None, mac_address=None, client_info=None,
               owner_entity_type=None):
        """
        Search for voip_clients subject to certain filter rules.

        All filters are either None, a scalar, or a sequence of scalars:

        - None means that the filter is not applied
        - A scalar means we are looking for the exact value
        - A sequence (list, tuple, set) of scalars means that we are looking
          for clients matching ANY one of the specified scalars in the filter.

        The filters are self-explanatory.

        :param voip_owner_id:
            This one is a bit special: we are looking for clients where the
            associated *voip_address* rows are owned by the specified
            *voip_owner_id*.  This is useful to answer queries like 'Locate all
            voip_clients belonging to person Foo'.

        :return:
            An iterable of rows with query result.
        """

        binds = dict()
        where = [
              "vc.voip_address_id = va.entity_id",
              "va.owner_entity_id = ei.entity_id",
        ]
        for name, value in (
                ("vc.entity_id", entity_id),
                ("vc.voip_address_id", voip_address_id),
                ("vc.client_type", client_type),
                ("vc.client_info", client_info)):
            if value is not None:
                where.append(
                    argument_to_sql(value, name, binds, int))

        if mac_address is not None:
            where.append(argument_to_sql(mac_address,
                                         "vc.mac_address",
                                         binds, six.text_type))

        if voip_owner_id is not None:
            where.append(argument_to_sql(voip_owner_id,
                                         "va.owner_entity_id",
                                         binds, int))

        if owner_entity_type is not None:
            where.append(argument_to_sql(owner_entity_type,
                                         "ei.entity_type",
                                         binds, int))

        return self.query(
            """
              SELECT vc.entity_type, vc.entity_id, vc.voip_address_id,
                     vc.client_type, vc.sip_enabled, vc.mac_address,
                     vc.client_info, va.owner_entity_id,
                     ei.entity_type as owner_entity_type
              FROM [:table schema=cerebrum name=voip_client] vc,
                   [:table schema=cerebrum name=voip_address] va,
                   [:table schema=cerebrum name=entity_info] ei
              WHERE {}
              ORDER BY vc.entity_id
            """.format(" AND ".join(where)),
            binds,
        )

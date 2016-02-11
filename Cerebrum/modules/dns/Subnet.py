#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009, 2013 University of Oslo, Norway
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
"""This module contains all functionality relating to information about subnets
in Cerebrum.

"""

import re
import math

import cereconf
from Cerebrum.Errors import NotFoundError
from Cerebrum.modules.dns.Errors import SubnetError
from Cerebrum.Entity import Entity

from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.cmd_param import *
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.dns import IPNumber
from Cerebrum.modules.dns.IPUtils import IPCalc, IPUtils
from Cerebrum.modules.bofhd.auth import BofhdAuth, BofhdAuthRole, BofhdAuthOpTarget


class Force(Parameter):
    _type = 'force'
    _help_ref = 'force'


class DnsBofhdAuth(BofhdAuth):
    # TODO: Shouldn't need to repeat it here, but bofhd_dns_cmds is
    # cranky when you try to import it
    def assert_dns_superuser(self, operator, query_run_any=False):
        if (not (self.is_dns_superuser(operator)) and
                not (self.is_superuser(operator))):
            raise PermissionDenied("Currently limited to dns_superusers")

    def is_dns_superuser(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        return self._has_operation_perm_somewhere(
            operator, self.const.auth_dns_superuser)


class Subnet(Entity):
    """Represents subnet-entities."""

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('subnet_ip', 'description', 'name_prefix',
                      'vlan_number', 'no_of_reserved_adr', 'dns_delegated')

    def __init__(self, db):
        super(Subnet, self).__init__(db)
        # The mask of this subnet; calculated from min and max ip's on subnet
        self.subnet_mask = None
        # Set of reserved adresses, represented as longs (i.e. not x.x.x.x)
        self.reserved_adr = set()

    def validate_subnet(subnet):
        """Validates that a subnet specification is correctly
        formatted and with legal values.

        Raises SubnetError if invalid.
        """
        try:
            ip, mask = subnet.split('/')
            mask = int(mask)
        except ValueError:
            raise SubnetError("Not a valid subnet '%s'" % subnet)
        if len(ip.split('.')) == 3:
            ip = ip + ".0"
        elif len(ip.split('.')) != 4:
            raise SubnetError("Invalid number of segments in '%s'. "
                              "Should be 3 or 4" % ip)
        for element in ip.split('.'):
            if int(element) < 0 or int(element) > 255:
                raise SubnetError("Element out of range in '%s': '%s'" % (ip,
                                                                      element))
        if mask < 0 or mask > 32:
            raise SubnetError("Invalid subnet mask '%s'; outside range 0-32" % mask)
        return True

    validate_subnet = staticmethod(validate_subnet)

    def is_valid_subnet(subnet):
        """
        Helper method for giving a simple True/False-result when trying
        to identify an IP/Subnet-string.

        :param subnet: A string that may or may not reference a valid subnet
        :return: True or False
        """
        try:
            Subnet.validate_subnet(subnet)
            return True
        except:
            return False
    is_valid_subnet = staticmethod(is_valid_subnet)

    def calculate_subnet_mask(ip_min, ip_max):
        """Calculates the subnetmask of a subnet based on the highest
        and lowest IP available to on that subnet.

        ip_min & ip_max are the IP's as integers, returns the
        subnetmask as an integer from 0 to 32 (inclusive).

        """
        net_size = ip_max - ip_min + 1
        return int(32 - math.log(net_size, 2))
    calculate_subnet_mask = staticmethod(calculate_subnet_mask)

    def clear(self):
        """Clear all data residing in this Subnet-instance."""
        super(Subnet, self).clear()
        self.clear_class(Subnet)
        self.__updated = []

    def populate(self, subnet, description, vlan=None):
        """Populate subnet instance's attributes.

        @type subnet: string
        @param subnet: A string that represents the subnet. Example:
            10.0.0.0/16. The last '.0' is not required, e.g. 10.0.0/16.

        @type description: string
        @param description: Something that describes the given subnet. It is
            free text, but local policies might use this in a parsable format to
            describe the usage of the given subnet.

        @type vlan: int
        @param vlan: A number that represents what VLAN the subnet corresponds
            to.

        """
        Entity.populate(self, self.const.entity_dns_subnet)
        # If __in_db is present, it must be True; calling populate on
        # an object where __in_db is present and False is very likely
        # a programming error.
        #
        # If __in_db in not present, we'll set it to False.
        try:
            if not self.__in_db:
                raise RuntimeError("populate() called multiple times.")
        except AttributeError:
            self.__in_db = False

        self.subnet_ip, subnet_mask = subnet.split('/')
        self.subnet_mask = int(subnet_mask)
        if len(self.subnet_ip.split('.')) == 3:
            self.subnet_ip = self.subnet_ip + ".0"

        self.ip_min, self.ip_max = IPCalc().ip_range_by_netmask(self.subnet_ip,
                                                                self.subnet_mask)
        self.description = description
        self.vlan = vlan

        max_res = max(cereconf.DEFAULT_RESERVED_BY_NET_SIZE.values())
        self.no_of_reserved_adr = cereconf.DEFAULT_RESERVED_BY_NET_SIZE.get(
            self.subnet_mask, max_res)
        self.calculate_reserved_addresses()

    def check_for_overlaps(self):
        """Checks if there already are subnets in the database that
        overlap with this subnet.

        Overlap is defined as having an ip_min-ip_max range that
        overlaps with an existing (= in DB) subnet's ip_min-ip_max
        range.

        Raises SubnetError if there are overlaps.

        """
        binds = {"min": self.ip_min,
                 "max": self.ip_max}

        overlap_entries = self.query(
            """SELECT subnet_ip, ip_min, ip_max
               FROM [:table schema=cerebrum name=dns_subnet]
               WHERE NOT (:max < ip_min OR :min > ip_max)""", binds)

        if overlap_entries:
            overlaps = ["%s/%s" % (o['subnet_ip'],
                        Subnet.calculate_subnet_mask(o['ip_min'], o['ip_max']))
                        for o in overlap_entries]
            raise SubnetError("Subnet '%s/%s' overlaps with the following subnet(s): '%s'" %
                              (self.subnet_ip, self.subnet_mask, "', '".join(overlaps)))

    def calculate_reserved_addresses(self):
        """TODO: DOC

        """
        # If no_of_reserved_adr is 0, then only the net and broadcast
        # address should be reserved; typically for small, special
        # purpose subnets.
        if self.no_of_reserved_adr == 0:
            self.reserved_adr = set()
            self.reserved_adr.add(self.ip_min)
            # Add the broadcast unless /32 net
            if self.ip_min < self.ip_max:
                self.reserved_adr.add(self.ip_max)
            return

        # First, check that we aren't trying to reserve more addresses
        # than there are in the subnet. Don't count the subnet's
        # address itself, since the number is for counting addresses
        # after it.
        if (self.ip_min + self.no_of_reserved_adr) > self.ip_max:
            raise SubnetError(
                "Trying to reserve %i addresses in a subnet " % self.no_of_reserved_adr +
                "that has %i addresses available. " % (self.ip_max - self.ip_min) +
                "You can't do that! Because it's *wrong*")

        # Designate the first X adresses in subnet (not counting the
        # subnet's address itself) as reserved, where X equals the
        # number specifically set as reserved addresses.
        self.reserved_adr = set([x + self.ip_min + 1 for
                                 x in range(self.no_of_reserved_adr)])

        # Make sure the first (subnet address) and last (broadcast)
        # addresses in the subnet is set as reserved.
        self.reserved_adr.add(self.ip_min)
        self.reserved_adr.add(self.ip_max)

        # /22 and /23 nets have some intermediate adresses reserved in
        # order to ease future netsplits.
        if self.subnet_mask == 22:
            self.reserved_adr.update(x + self.ip_min for x in [255, 256] + [255*2+1, 255*2+2])

        if self.subnet_mask == 23:
            self.reserved_adr.update(x + self.ip_min for x in [255, 256])

    def has_adresses_in_use(self):
        """Check whether or not there are any IPs in use on this subnet.

        Return 'True' if there are.

        """
        # Need to import Utils here, since Utils imports this module,
        # and we cannot have circular module dependencies.
        from Cerebrum.modules.dns.Utils import Find
        default_zone = self.const.DnsZone(getattr(cereconf, 'DNS_DEFAULT_ZONE', 'uio'))
        find = Find(self._db, default_zone)

        if find.find_used_ips(self.subnet_ip):
            return True
        else:
            return False

    def check_reserved_addresses_in_use(self):
        """TODO: DOC

        """
        # Need to import Utils here, since Utils imports this module,
        # and we cannot have circular module dependencies.
        from Cerebrum.modules.dns.Utils import Find
        default_zone = self.const.DnsZone(getattr(cereconf, 'DNS_DEFAULT_ZONE', 'uio'))
        find = Find(self._db, default_zone)

        ip_number = IPNumber.IPNumber(self._db)
        ip_number.clear()

        res_adr_in_use = []

        for row in ip_number.find_in_range(self.ip_min, self.ip_max):
            current_address = long(row['ipnr'])
            if current_address in self.reserved_adr:
                res_adr_in_use.append(IPCalc.long_to_ip(current_address))

        if res_adr_in_use:
            res_adr_in_use.sort()
            raise SubnetError(
                "The following reserved ip's are already in use " +
                "on (new?) subnet %s/%s: " % (self.subnet_ip, self.subnet_mask) +
                "'%s'." % (', '.join(res_adr_in_use)))

    def write_db(self, perform_checks=True):
        """Write subnet instance to database.

        If this instance has a ``entity_id`` attribute (inherited from
        class Entity), this Subnet entity is already present in the
        Cerebrum database, and we'll use UPDATE to bring the instance
        in sync with the database.

        Otherwise, a new entity_id is generated and used to insert
        this object.

        """
        self.__super.write_db()
        if not self.__updated:
            return

        is_new = not self.__in_db

        # With some DB-interfaces (e.g. psycopg 1), DB-booleans may be
        # returned as ints; make sure that dns_delegated truly is a
        # boolean. This should probably be handled more generally
        # than just here, but this is currently the only place
        # DB-booleans are in use.

        # Since self.dns_delegated often is an int when it arrives
        # here, it will need to be "reset" to None before it can be
        # set to a boolean value". Sometimes stuff just works in
        # mysterious ways...
        if self.dns_delegated:
            self.dns_delegated = None
            self.dns_delegated = True
        else:
            self.dns_delegated = None
            self.dns_delegated = False

        if is_new:
            # Only need to check for overlaps when subnet is being
            # added, since a subnet's ip-range is never changed.
            self.check_for_overlaps()

            if perform_checks:
                self.check_reserved_addresses_in_use()

            cols = [('entity_type', ':e_type'),
                    ('entity_id', ':ent_id'),
                    ('subnet_ip', ':subnet_ip'),
                    ('ip_min', ':ip_min'),
                    ('ip_max', ':ip_max'),
                    ('no_of_reserved_adr', ':res_adr'),
                    ('description', ':desc')]
            if self.vlan is not None:
                cols.append(('vlan_number', ':vlan'))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=dns_subnet] (%(tcols)s)
            VALUES (%(binds)s)""" % {'tcols': ", ".join([x[0] for x in cols]),
                                     'binds': ", ".join([x[1] for x in cols])},
                                    {'e_type': int(self.const.entity_dns_subnet),
                                     'ent_id': self.entity_id,
                                     'subnet_ip': self.subnet_ip,
                                     'ip_min': self.ip_min,
                                     'ip_max': self.ip_max,
                                     'desc': self.description,
                                     'res_adr': self.no_of_reserved_adr,
                                     'vlan': self.vlan})
            self._db.log_change(self.entity_id, self.const.subnet_create, None)

        else:
            if perform_checks:
                self.check_reserved_addresses_in_use()

            cols = [('description', ':desc'),
                    ('no_of_reserved_adr', ':res_adr'),
                    ('vlan_number', ':vlan'),
                    ('dns_delegated', ':dns_delegated'),
                    ('name_prefix', ':name_pre')]
            binds = {'e_id': self.entity_id,
                     'desc': self.description,
                     'vlan': self.vlan_number,
                     'dns_delegated': self.dns_delegated,
                     'name_pre': self.name_prefix,
                     'res_adr': self.no_of_reserved_adr
                     }
            self.execute("""
            UPDATE [:table schema=cerebrum name=dns_subnet]
            SET %(defs)s
            WHERE entity_id=:e_id""" % {'defs': ", ".join(
                ["%s=%s" % x for x in cols if x[0] != 'entity_id'])}, binds)
            self._db.log_change(self.entity_id, self.const.subnet_mod, None,
                                change_params=binds)

        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def delete(self, perform_checks=True):
        if perform_checks:
            if self.has_adresses_in_use():
                raise SubnetError(
                    "Subnet '%s/%s' cannot be deleted; it has addresses in use" %
                    (self.subnet_ip, self.subnet_mask))

        # Revoke BofhdAuthRoles associated with subnet
        baot = BofhdAuthOpTarget(self._db)
        bar = BofhdAuthRole(self._db)
        targets = [x['op_target_id'] for x in
                   baot.list(entity_id=self.entity_id)]
        if targets:
            for target in targets:
                for x in bar.list(op_target_id=target):
                    bar.revoke_auth(*x)
            bar.commit()

        # Remove BofhdAuthOpTarget associated with subnet
        for x in targets:
            baot.clear()
            try:
                baot.find(x)
                baot.delete()
                baot.commit()
            except NotFoundError:
                pass

        self._db.log_change(self.entity_id, self.const.subnet_delete, None)
        if self.__in_db:
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=dns_subnet]
            WHERE entity_id=:e_id""", {'e_id': self.entity_id})
        self.__super.delete()

    def new(self):
        """Insert a new subnet into the database."""
        self.populate()
        self.write_db()
        self.find(self.entity_id)

    def find(self, identifier):
        """Find and instantiate the subnet entity with data from the db.

        @type identifier: mixed
        @param identifier:
            The identifier of the Subnet. Note that the DNS module behaves a bit
            differently than other Cerebrum modules, in that this find method
            accepts other input than entity_id. Possibilities are:

                - A string containing the entity_id, prefixed with 'entity_id:'
                  or 'id:'.

                - A string with a subnet address, e.g. '10.0.1.0/16'.

                - A string with an IP address, e.g. '10.0.1.57'.

        """
        binds = {}

        if identifier is None:
            raise SubnetError("Unable to find IPv4 subnet identified by '%s'" % identifier)

        if isinstance(identifier, (str, unicode)) and identifier.count(':') >= 2:
            # This is probably an IPv6 subnet
            raise SubnetError("Unable to find IPv4 subnet identified by '%s'" % identifier)

        if isinstance(identifier, (int, long)):
            # The proper way of running find()
            where_param = "entity_id = :e_id"
            binds['e_id'] = identifier
        elif identifier.startswith('id:') or identifier.startswith('entity_id:'):
            # E.g. 'id:X' or 'entity_id:X';
            where_param = "entity_id = :e_id"
            try:
                binds['e_id'] = int(identifier.split(':')[1])
            except ValueError:
                raise SubnetError("Entity ID must be an integer")
        elif identifier.find('/') > 0:
            # A '/' indicates a subnet spec: just need the ip
            where_param = "subnet_ip = :subnet_ip"
            subnet_ip = identifier.split('/')[0]
            if len(subnet_ip.split(".")) == 3:
                subnet_ip += ".0"
            binds['subnet_ip'] = subnet_ip
        else:
            # Last valid type is simply an IP; need to find correct range
            if len(identifier.split(".")) == 3:
                identifier += ".0"
            where_param = "ip_min <= :ip AND ip_max >= :ip"
            binds['ip'] = IPCalc.ip_to_long(identifier)

        try:
            (eid, self.subnet_ip, self.ip_min, self.ip_max,
             self.description, self.dns_delegated, self.name_prefix,
             self.vlan_number, self.no_of_reserved_adr) = self.query_1(
                 """SELECT entity_id, subnet_ip, ip_min, ip_max, description,
                           dns_delegated, name_prefix, vlan_number,
                           no_of_reserved_adr
                    FROM [:table schema=cerebrum name=dns_subnet]
                    WHERE %s""" % where_param, binds)

            self.__super.find(eid)

            self.subnet_mask = Subnet.calculate_subnet_mask(self.ip_min, self.ip_max)
            self.calculate_reserved_addresses()

        except NotFoundError:
            raise SubnetError("Unable to find IPv4 subnet identified by '%s'" % identifier)

        self.__in_db = True
        self.__updated = []

    def search(self):
        """Search for subnets that satisfy given criteria.

        Currently, no criteria can be given, hence all subnets are
        returned.

        """
        # Need to insert a dummy value as placeholder for subnet_mask,
        # since we later wish to calculate the proper value for it,
        # and db_row won't allow us to insert new keys into the
        # result's rows.
        result = self.query(
            """SELECT entity_id, subnet_ip, 1 AS subnet_mask, ip_min, ip_max,
                      description, dns_delegated, name_prefix, vlan_number, no_of_reserved_adr
               FROM [:table schema=cerebrum name=dns_subnet]""")

        for row in result:
            row["subnet_mask"] = Subnet.calculate_subnet_mask(row['ip_min'], row['ip_max'])

        return result


class SubnetIdentifier(Parameter):
    """Represents subnet-parameters given to bofh"""
    _type = 'subnet_identifier'
    _help_ref = 'subnet_identifier'


class BofhdExtension(BofhdCommandBase):
    """Class to expand bofhd with commands for manipulating subnets."""

    all_commands = {}

    def __init__(self, server, default_zone='uio'):
        super(BofhdExtension, self).__init__(server)
        self.ba = DnsBofhdAuth(self.db)
        self.default_zone = self.const.DnsZone(getattr(cereconf, 'DNS_DEFAULT_ZONE', default_zone))
        # Circular dependencies are bad, m'kay
        from Cerebrum.modules.dns import Utils
        self._find = Utils.Find(server.db, self.default_zone)

    def get_help_strings(self):
        group_help = {
            'subnet': "Commands for handling subnets",
        }

        command_help = {
            'subnet': {
            #'subnet_add': 'Add a new subnet with given description and optional given VLAN',
            #'subnet_remove': 'Remove an existing subnet',
            'subnet_info': 'Provide information about a subnet',
            'subnet_set_vlan': 'Set VLAN-ID for a subnet',
            'subnet_set_description': 'Set description for a subnet',
            'subnet_set_dns_delegated': 'Set subnet zone as delegated to external DNS-server',
            'subnet_set_name_prefix': 'Set name-prefix for a subnet',
            'subnet_set_reserved': 'Set number of reserved addresses for a subnet',
            'subnet_unset_dns_delegated':
                'Set subnet zone as not delegated to external DNS-server',
            }
        }

        arg_help = {
            'subnet_description':
            ['desc', 'Subnet description',
             """Description of what the subnet is intended for."""],

            'subnet_identifier':
            ['subnet', 'Subnet',
             """Subnet identifier, either on format
- ddd.ddd.ddd.ddd/dd                                    OR
- ddd.ddd.ddd.ddd    (for any IP in the subnet's range) OR
- id:<entity-id>"""],

            'subnet_name_prefix':
            ['name_prefix', 'Name prefix',
             """Name-prefix to be used for the given subnet """],

            'subnet_reserved':
            ['#_reserved_adr', 'Number of reserved addresses',
             """Number of adresses to set as reserved at the beginning of the given subnet."""],

            'subnet_vlan':
            ['vlan_id', 'VLAN ID number',
             """ID of the VLAN the subnet uses/represents."""],
        }

        return (group_help, command_help,
                arg_help)

    all_commands['subnet_info'] = Command(
        ("subnet", "info"), SubnetIdentifier(),
        fs=FormatSuggestion([("Subnet:                 %s\n" +
                              "Entity ID:              %s\n" +
                              "Netmask:                %s\n" +
                              "Description:            '%s'\n" +
                              "Name-prefix:            '%s'\n" +
                              "VLAN:                   %s\n" +
                              "DNS delegated:          %s\n" +
                              "IP-range:               %s\n" +
                              "Reserved host adresses: %s\n" +
                              "Reserved addresses:     %s",
                              ("subnet", "entity_id", "netmask", "desc",
                               "name_prefix", "vlan", "delegated",
                               "ip_range", "no_of_res_adr", "res_adr1")),
                             ("                        %s", ('res_adr',)),
                             ("Used addresses:         %s\n" +
                              "Unused addresses:       %s (excluding reserved adr.)",
                              ('used', 'unused'))]))

    def subnet_info(self, operator, identifier):
        """Lists the following information about the given subnet:

        * Subnett
        * Netmask
        * Entity ID
        * Description
        * Name-prefix
        * VLAN number
        * DNS-delegation status
        * Range of IPs on subnet
        * Number of reserved addresses
        * A list of the reserved adresses
        """
        s = Subnet(self.db)
        s.find(identifier)

        if s.dns_delegated:
            delegated = "Yes"
        else:
            delegated = "No"

        data = {
            'subnet': "%s/%s" % (s.subnet_ip, s.subnet_mask),
            'entity_id': str(s.entity_id),
            'netmask': IPCalc.netmask_to_ip(s.subnet_mask),
            'desc': s.description,
            'delegated': delegated,
            'name_prefix': s.name_prefix,
            'no_of_res_adr': str(s.no_of_reserved_adr)
        }

        if s.vlan_number is not None:
            data['vlan'] = str(s.vlan_number)
        else:
            data['vlan'] = "(None)"

        data['ip_range'] = "%s - %s" % (IPCalc.long_to_ip(s.ip_min),
                                        IPCalc.long_to_ip(s.ip_max))

        # Calculate number of used and unused IP-addresses on this subnet
        #                              ^^^^^^ excluding reserved addresses
        data['used'] = str(len(self._find.find_used_ips(s.subnet_ip)))
        try:
            data['unused'] = str(len(self._find.find_free_ip(s.subnet_ip)))
        except CerebrumError:
            data['unused'] = "0"

        reserved_adresses = list(s.reserved_adr)

        if reserved_adresses:
            reserved_adresses.sort()
            data["res_adr1"] = "%s (net)" % IPCalc.long_to_ip(reserved_adresses.pop(0))
        else:
            data["res_adr1"] = "(None)"

        ret = [data, ]

        if reserved_adresses:
            last_ip = reserved_adresses.pop()
            for address in reserved_adresses:
                ret.append({'res_adr': IPCalc.long_to_ip(address)})
            ret.append({'res_adr': "%s (broadcast)" % IPCalc.long_to_ip(last_ip)})

        return ret

    all_commands['subnet_set_vlan'] = Command(
        ("subnet", "set_vlan"),
        SubnetIdentifier(),
        Integer(help_ref="subnet_vlan"))

    def subnet_set_vlan(self, operator, identifier, new_vlan):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        s = Subnet(self.db)
        try:
            int(new_vlan)
        except:
            raise CerebrumError("VLAN must be an integer; '%s' isn't" % new_vlan)
        s.find(identifier)
        old_vlan = s.vlan_number
        s.vlan_number = new_vlan
        s.write_db(perform_checks=False)
        subnet_id = "%s/%s" % (s.subnet_ip, s.subnet_mask)
        return "OK; VLAN for subnet %s updated from '%s' to '%s'" % (subnet_id, old_vlan, new_vlan)

    all_commands['subnet_set_description'] = Command(
        ("subnet", "set_description"),
        SubnetIdentifier(),
        SimpleString(help_ref="subnet_description"))

    def subnet_set_description(self, operator, identifier, new_description):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        s = Subnet(self.db)
        s.find(identifier)
        s.description = new_description
        s.write_db(perform_checks=False)
        subnet_id = "%s/%s" % (s.subnet_ip, s.subnet_mask)
        return "OK; description for subnet %s updated to '%s'" % (subnet_id, new_description)

    all_commands['subnet_set_name_prefix'] = Command(
        ("subnet", "set_name_prefix"),
        SubnetIdentifier(),
        SimpleString(help_ref="subnet_name_prefix"))

    def subnet_set_name_prefix(self, operator, identifier, new_prefix):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        s = Subnet(self.db)
        s.find(identifier)
        old_prefix = s.name_prefix
        s.name_prefix = new_prefix
        s.write_db(perform_checks=False)
        subnet_id = "%s/%s" % (s.subnet_ip, s.subnet_mask)
        return ("OK; name_prefix for subnet %s updated " % subnet_id +
                "from '%s' to '%s'" % (old_prefix, new_prefix))

    all_commands['subnet_set_dns_delegated'] = Command(
        ("subnet", "set_dns_delegated"),
        SubnetIdentifier(), Force(optional=True))

    def subnet_set_dns_delegated(self, operator, identifier, force=False):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        s = Subnet(self.db)
        s.find(identifier)
        subnet_id = "%s/%s" % (s.subnet_ip, s.subnet_mask)

        if s.dns_delegated:
            return ("Subnet %s is already set as " % subnet_id +
                    "being delegated to external DNS server")

        in_use = ""
        if s.has_adresses_in_use():
            if force:
                in_use = "\nNote! Subnet has addresses in use!"
            else:
                raise CerebrumError(
                    "Subnet '%s' has addresses in use; must force to delegate" % subnet_id)

        s.dns_delegated = True
        s.write_db(perform_checks=False)
        return "Subnet %s set as delegated to external DNS server%s" % (subnet_id, in_use)

    all_commands['subnet_unset_dns_delegated'] = Command(
        ("subnet", "unset_dns_delegated"),
        SubnetIdentifier())

    def subnet_unset_dns_delegated(self, operator, identifier):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        s = Subnet(self.db)
        s.find(identifier)
        subnet_id = "%s/%s" % (s.subnet_ip, s.subnet_mask)

        if not s.dns_delegated:
            return ("Subnet %s is already set as not " % subnet_id +
                    "being delegated to external DNS server")

        s.dns_delegated = False
        s.write_db(perform_checks=False)
        return "Subnet %s no longer set as delegated to external DNS server" % subnet_id

    all_commands['subnet_set_reserved'] = Command(
        ("subnet", "set_reserved"),
        SubnetIdentifier(),
        Integer(help_ref="subnet_reserved"))

    def subnet_set_reserved(self, operator, identifier, new_res):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        s = Subnet(self.db)
        try:
            int(new_res)
        except:
            raise CerebrumError("The number of reserved addresses must be " +
                                "an integer; '%s' isn't" % new_res)

        if new_res < 0:
            raise CerebrumError("Cannot set number of reserved addresses to " +
                                "a negative number such as '%s'" % new_res)

        s.find(identifier)
        old_res = s.no_of_reserved_adr

        s.no_of_reserved_adr = int(new_res)
        s.calculate_reserved_addresses()

        in_use = ""
        if new_res > old_res:
            try:
                s.check_reserved_addresses_in_use()
            except SubnetError, se:
                in_use = "\nFYI: %s" % str(se)

        s.write_db(perform_checks=False)
        subnet_id = "%s/%s" % (s.subnet_ip, s.subnet_mask)
        return ("OK; Number of reserved addresses for subnet %s " % subnet_id +
                "updated from '%s' to '%s'%s" % (old_res, new_res, in_use))


if __name__ == '__main__':
    pass

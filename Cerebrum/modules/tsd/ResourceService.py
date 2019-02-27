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
"""Webservice functionality for Resource management in the TSD project.

Resources are registered in Cerebrum, but they are administered by other
systems. For those systems to be able to retrieve the information, we are giving
it through a SOAP webservice.

"""

# TODO: check if something could be removed from here:
import random, hashlib
import string, pickle
from mx.DateTime import RelativeDateTime, now
import twisted.python.log

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import dns

from Cerebrum.modules.cis import Utils
log = Utils.SimpleLogger()

class ResourceService(object):
    """The functionality for the Resource service.

    Note that this main class should be independent of what server we use. It is
    important that each thread gets its own instance of this class, to avoid
    race conditions.

    Another thing to remember is that database connections should be closed.
    This is to avoid having old and idle database connections, as the garbage
    collector can't destroy the instances, due to twisted's reuse of threads.

    """
    # The default DNS zone to use:
    default_zone = 'tsd.usit.no.'

    def __init__(self, operator_id):
        """Constructor. Since we are using access control, we need the
        authenticated entity's ID as a parameter.

        """
        self.db = Factory.get('Database')()
        self.db.cl_init(change_program='resource_service')
        self.co = Factory.get('Constants')(self.db)
        self.finder = dns.Utils.Find(self.db, self.default_zone)
        self.subnet = dns.Subnet.Subnet(self.db)
        self.aaaa = dns.AAAARecord.AAAARecord(self.db)
        self.ip = dns.IPv6Number.IPv6Number(self.db)

        # TODO: could we save work by only using a single, shared object of
        # the auth class? It is supposed to be thread safe.
        #self.ba = BofhdAuth(self.db)
        self.operator_id = operator_id

    def close(self):
        """Explicitly close this instance, as python's garbage collector can't
        close the database connections when Twisted is reusing the threads.

        """
        if hasattr(self, 'db'):
            try:
                self.db.close()
            except Exception, e:
                log.warning("Problems with db.close: %s" % e)
        else:
            # TODO: this could be removed later, when it is considered stable
            log.warning("db doesn't exist")

    def search_mac_addresses(self, hostname, mac_address):
        """Search for hostnames and their MAC addresses."""
        m_id = a_id = None
        if hostname:
            a_id = self.finder.find_a_record(hostname)
            self.aaaa.clear()
            self.aaaa.find(a_id)
            if not self.aaaa.mac:
                return ()
            if mac_address and mac_address != self.aaaa.mac:
                return ()
            return ((self.aaaa.name, self.aaaa.mac),)
        # Return either the complete list of hosts and their MAC addresses, or
        # only the host with the given MAC address:
        # TODO: What is used? The element 'mac' or IPNumber's 'mac_adr'?
        return ((row['name'], row['mac']) for row in self.aaaa.list_ext() if
                row['mac'] and (not mac_address or (row['mac'] == mac_address)))

    def register_mac_address(self, hostname, mac_address):
        """Register a MAC address for a given host."""
        self.aaaa.clear()
        a_id = self.finder.find_a_record(hostname)
        self.aaaa.find(a_id)
        # TODO: do any validation on the MAC address?
        self.aaaa.mac = mac_address
        self.aaaa.write_db()
        self.db.commit()
        return True

    def get_vlan_info(self, hostname):
        """Get the VLAN info about a given host.

        The needed details are VLAN number and net category.

        """
        self.subnet.clear()
        # Check if hostname is rather an IP address or subnet:
        if ':' in hostname:
            self.subnet.find(hostname)
        else:
            a_id = self.finder.find_a_record(hostname)
            self.aaaa.clear()
            self.aaaa.find(a_id)
            self.ip.clear()
            self.ip.find(a_id.ip_number)
            # bah, now we have the ip address
            self.subnet.find(self.ip.aaaa_ip)
        return (self.subnet.vlan_number, self.subnet.subnet_mask)


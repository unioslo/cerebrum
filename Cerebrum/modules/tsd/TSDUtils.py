#!/user/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2014-2018 University of Oslo, Norway
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
""" Utility functions for TSD.

This is where all utils functionality that is specific for TSD and is needed in
different places, but does not belong to a specific Entity class.

More TSD functionality should be put in here, i.e. some refactoring is needed
when the functionality needed by TSD has settled.

"""

import cereconf

from Cerebrum import Errors
from Cerebrum.modules.hostpolicy import PolicyComponent
from Cerebrum.modules.dns.CNameRecord import CNameRecord
from Cerebrum.modules.dns.DnsOwner import DnsOwner
from Cerebrum.Utils import Factory


def add_host_to_policy_component(db, dnsowner_id, policy_name):
    """ Helper method for giving a host a hostpolicy role.

    Note that this method does not fail if the given `policy_name` doesn't
    exist. Hostpolicies could disappear, or be renamed, which we would not want
    to break the system. Instead, unknown policies are simply not added, i.e.
    this method does nothing in such scenarios.

    :param Cerebrum.database.Database db:
        The Cerebrum database connector.

    :param int dnsowner_id:
        The `entity_id` of the host that should get the role.

    :param str policy_name:
        The name of the policy role or atom. If it does not exist, it will not
        be given to the host, but no exception will be raised.

    :rtype: bool
    :return:
        True if the policy was found and registered for the host. False if the
        policy weren't added, e.g. because the policy didn't exist.

    """
    pc = PolicyComponent.PolicyComponent(db)
    try:
        pc.find_by_name(policy_name)
    except Errors.NotFoundError:
        return False
    if not pc.search_hostpolicies(policy_id=pc.entity_id,
                                  dns_owner_id=dnsowner_id):
        pc.add_to_host(dnsowner_id)
    pc.write_db()
    return True


def add_cname_record(db, cname_record_name, target_name, fail_on_exists=True):
    """
    Creates a CNAME-record.

    If fail_on_exists=False, it will simply return without doing anything,
    if the CNAME-record already exists.
    This is due to the method being used by OU._setup_project_hosts, which
    can be run several times for the same project when it is reconfigured.

    :param db: A Cerebrum-database instance
    :type db: Cerebrum.database.Database
    :param cname_record_name: FQDN of the CNAME-record
    :type cname_record_name: str
    :param target_name: FQDN of the target domain
    :type target_name: str
    :param fail_on_exists: True or False
    :type fail_on_exists: bool
    """

    cname = CNameRecord(db)
    dns_owner = DnsOwner(db)
    constants = Factory.get('Constants')

    try:
        dns_owner.find_by_name(target_name)
        proxy_dns_owner_ref = dns_owner.entity_id
    except Errors.NotFoundError:
        raise Errors.NotFoundError('%s does not exist.' % target_name)

    dns_owner.clear()

    try:
        dns_owner.find_by_name(cname_record_name)
    except Errors.NotFoundError:
        dns_owner.populate(constants.DnsZone(cereconf.DNS_DEFAULT_ZONE),
                           cname_record_name)
        dns_owner.write_db()
    cname_dns_owner_ref = dns_owner.entity_id

    try:
        cname.find_by_cname_owner_id(cname_dns_owner_ref)
        if fail_on_exists:
            raise Errors.RealityError('CNAME %s already exists.'
                                      % cname_record_name)
    except Errors.NotFoundError:
        cname.populate(cname_dns_owner_ref,
                       proxy_dns_owner_ref)
        cname.write_db()

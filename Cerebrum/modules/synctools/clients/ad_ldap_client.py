#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2017 University of Oslo, Norway
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
import ldap
from Cerebrum.Utils import read_password


class ADLDAPClient(object):
    def __init__(self, config):
        """
        @param config: ADLDAPConfig
        """
        self.config = config
        self.connection = None
        self.scope_base = ldap.SCOPE_BASE
        self.scope_onelevel = ldap.SCOPE_ONELEVEL
        self.scope_subtree = ldap.SCOPE_SUBTREE
        self.scope_subordinate = ldap.SCOPE_SUBORDINATE

    def connect(self, username=None, password=None):
        if username:
            ldap_user = username
        else:
            ldap_user = self.config.ldap_user
        if password:
            ldap_pass = password
        else:
            ldap_pass = read_password(ldap_user,
                                      self.config.ldap_server)
        self.connection = ldap.initialize('{0}://{1}'.format(
            self.config.ldap_proto,
            self.config.ldap_server
        ))
        self.connection.bind_s(self.config.bind_dn_template.format(ldap_user),
                               ldap_pass)

    def fetch_data(self, dn, scope, filter):
        ctrltype = ldap.controls.SimplePagedResultsControl.controlType
        lc = ldap.controls.SimplePagedResultsControl(True, 1000, '')
        msg_id = self.connection.search_ext(dn,
                                            scope,
                                            filter,
                                            serverctrls=[lc])
        data = []
        while True:
            rtype, rdata, rmsgid, serverctrls = self.connection.result3(msg_id)
            data.extend(rdata)
            paging_ctrls = [c for c in serverctrls
                            if c.controlType == ctrltype]
            if paging_ctrls:
                cookie = paging_ctrls[0].cookie
                if cookie:
                    lc.cookie = cookie
                    msg_id = self.connection.search_ext(dn,
                                                        scope,
                                                        filter,
                                                        serverctrls=[lc])
                else:
                    break
        return data

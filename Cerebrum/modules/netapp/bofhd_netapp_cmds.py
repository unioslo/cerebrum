#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2007 University of Oslo, Norway
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
#
# $Id$

""" This module contains all components and functionality needed for
administrating NetApp servers via bofhd.

More specifically, it offers the following:
- Create a new quota-tree on a given server.
- Resize a quota-tree on a given server.
- Set a quote-tree to be exported to a given group of hosts.
- Set a quote-tree to no longer be exported to a given group of hosts.

"""

__version__ = "$Revision$"

from mx import DateTime

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum import Constants
from Cerebrum import Cache

from Cerebrum.modules.bofhd.cmd_param import Parameter,Command,Integer,SimpleString,GroupName
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.utils import BofhdRequests,_BofhdRequestOpCode

class NetAppServer(Parameter):
    _type = 'netappserver'
    _help_ref = 'netappserver'


class QtreeName(SimpleString):
    _help_ref = 'qtreename'


class QtreeSize(Integer):
    _help_ref = 'qtreesize'


class Constants(Constants.Constants):
    bofh_netapp_create_quotatree = _BofhdRequestOpCode('br_netapp_cr_qt',
                                                       'NetApp create quota-tree')
    bofh_netapp_resize_quotatree = _BofhdRequestOpCode('br_netapp_rs_qt',
                                                       'NetApp resize quota-tree')
    bofh_netapp_add_export = _BofhdRequestOpCode('br_netapp_add_ex',
                                                 'NetApp export QT to NFS')
    bofh_netapp_remove_export = _BofhdRequestOpCode('br_netapp_rem_ex',
                                                    'NetApp de-export QT to NFS')


class BofhdExtension(object):
    """Adds functionality for adminsitrating NetApp servers via bofhd."""
    all_commands = {}


    def __init__(self, server):
        self.server = server
        self.logger = server.logger
        self.db = server.db
        self.constants = Factory.get('Constants')(self.db)
        self.ba = BofhdAuth(self.db)
        
        self.br = BofhdRequests(self.db, self.constants)
        c = self.constants
        self.br.conflicts.update({
            int(c.bofh_netapp_create_quotatree): None,
            int(c.bofh_netapp_resize_quotatree): None,
            int(c.bofh_netapp_add_export): [c.bofh_netapp_remove_export],
            int(c.bofh_netapp_remove_export): [c.bofh_netapp_add_export],
            })
        
        self._cached_client_commands = Cache.Cache(mixins=[Cache.cache_mru,
                                                           Cache.cache_slots,
                                                           Cache.cache_timeout],
                                                   size=500,
                                                   timeout=60*60)

        
    def get_help_strings(self):
        """Returns all help-strings for commands and parameters used
        by this BofhdExtensions.

        """
        
        group_help = {
            'netapp': "Commands for administrating NetApp servers.",
            }

        command_help = {
            'netapp': {
            'netapp_create_qtree': 'Create a new qtree on given NetApp-server.',
            'netapp_resize_qtree': 'Change the size of given qtree.',
            'netapp_add_export': 'Set qtree to be exported to NFS.',
            'netapp_remove_export': 'Set qtree to no longer be exported to NFS.',
            }
            }

        arg_help = {
            'netappserver':
            ['netapp_server', 'Name of NetApp server',
             'Name of the NetApp server the quota-tree is locetd on, e.g. "platon"'],
            'qtreename':
            ['qtreename', 'Name of quote-tree',
             'The full name of the quota-tree, e.g. "/vol/usitusers/bsd-u1"'],
            'qtreesize':
            ['qtreesize', 'Size (in GB)', 'Size of the quota-tree, given in gigabytes'],
            '':
            ['', '', ''],
            }
 
        return (group_help, command_help,
                arg_help)

 
    def get_commands(self, account_id):
        """Returns the full set of commands allowed for a given user
        from this BofhdExtension.

        If previously retrieved, the set will be retrieved form a
        cache; if not, a new set will be assembled.

        """
        try:
            return self._cached_client_commands[int(account_id)]
        except KeyError:
            pass
        
        commands = {}
        for k in self.all_commands.keys():
            commands[k] = self.all_commands[k].get_struct(self)
        self._cached_client_commands[int(account_id)] = commands

        return commands


    def verify_host_group(self, groupname):
        """Utility-method to verify that the name given is a valid
        hostgroup.

        """
        group = Factory.get('Group')(self.db)
        try:
            group.find_by_name(groupname)
        except Errors.NotFoundError:
            raise CerebrumError, "Unable to find group named '%s'" % groupname

        if not group.has_spread(self.constants.spread_uio_machine_netgroup):
            raise CerebrumError, ("Group '%s' does not seem to be a valid " + 
                                  "hostgroup") % groupname

        return group.entity_id


    all_commands['netapp_create_qtree'] = Command(('netapp', 'create_qtree'),
                                                  NetAppServer(), QtreeName(),
                                                  QtreeSize())
    def netapp_create_qtree(self, operator, server, qtree, size):
        """Command for creating a new quota-tree."""
        op = operator.get_entity_id()
        request_parameters = "%s+%s+%s" % (server, qtree, size)
        self.br.add_request(op, DateTime.now(),
                            self.constants.bofh_netapp_create_quotatree,
                            None, None, request_parameters)
        return ("OK, queued creation of '%s' on server '%s'; size: %s GB." %
                (qtree, server, size))


    all_commands['netapp_resize_qtree'] = Command(('netapp', 'resize_qtree'),
                                                  NetAppServer(), QtreeName(),
                                                  QtreeSize())
    def netapp_resize_qtree(self, operator, server, qtree, size):
        """Command for resizing a new quota-tree."""
        op = operator.get_entity_id()
        self.br.add_request(op, DateTime.now(),
                            self.constants.bofh_netapp_resize_quotatree,
                            None, None, request_parameters)
        return "OK, queued resize of '%s' to '%s' GB." % (qtree, size)


    all_commands['netapp_add_export'] = Command(('netapp', 'add_export'),
                                                  NetAppServer(), QtreeName(),
                                                GroupName())
    def netapp_add_export(self, operator, server, qtree, groupname):
        """Command for setting a quote-tree to be exported."""
        op = operator.get_entity_id()        
        group_id = self.verify_host_group(groupname)
        request_parameters = "%s+%s" % (server, qtree)
        
        self.br.add_request(op, DateTime.now(),
                            self.constants.bofh_netapp_add_export,
                            None, group_id, request_parameters)
        return "OK, queued export of '%s' to '%s'." % (qtree, groupname)


    all_commands['netapp_remove_export'] = Command(('netapp', 'remove_export'),
                                                  NetAppServer(), QtreeName(),
                                                   GroupName())
    def netapp_remove_export(self, operator, server, qtree, groupname):
        """Command for setting a quote-tree to no longer be exported."""
        op = operator.get_entity_id()
        group_id = self.verify_host_group(groupname)
        request_parameters = "%s+%s" % (server, qtree)

        self.br.add_request(op, DateTime.now(),
                            self.constants.bofh_netapp_remove_export,
                            None, group_id, request_parameters)
        return "OK, queued removal of export of '%s' to '%s'." % (qtree, groupname)



if __name__ == '__main__':
    pass


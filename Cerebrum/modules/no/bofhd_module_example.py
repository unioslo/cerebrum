# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

# $Id$

# Sample module that extends bofhd with a set of commands

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum import Utils
from Cerebrum import Errors

from Cerebrum.modules.bofhd.cmd_param import Command,AccountName,FormatSuggestion

def format_day(field):
    fmt = "yyyy-MM-dd"                  # 10 characters wide
    return ":".join((field, "date", fmt))

class BofhdExtension(object):
    all_commands = {}

    def __init__(self, server):
        self.server = server
        self.logger = server.logger
        self.db = server.db
        self.ou = Factory.get('OU')(self.db)

    def get_help_strings(self):
        group_help = {
            'user': "User commands",
            }

        # The texts in command_help are automatically line-wrapped, and should
        # not contain \n
        command_help = {
            'user': {
            'user_info': 'Show information about a user',
            },
            }
        
        arg_help = {
            'account_name':
            ['uname', 'Enter account name',
             'Enter the name of the account for this operation'],
            }
        return (group_help, command_help,
                arg_help)

    
    def get_commands(self, uname):
        # TODO: Do some filtering on uname to remove commands
        commands = {}
        for k in self.all_commands.keys():
            commands[k] = self.all_commands[k].get_struct(self)
        return commands

    # user info
    all_commands['user_info'] = Command(
        ("user", "info"), AccountName(),
        fs=FormatSuggestion([("Entity id:     %i\n"+
                              "Expire:        %s",
                              ("entity_id", format_day("expire"))),
                             ("Quarantined:   %s",
                              ("quarantined",))]))
    def user_info(self, operator, accountname):
        account = Utils.Factory.get('Account')(self.db)
        try: 
            account.find_by_name(accountname)
        except Errors.NotFoundError:
            raise CerebrumError, "Could not find user %s" % accountname

        ret = {'entity_id': account.entity_id,
               'expire': account.expire_date}
        if account.get_entity_quarantine():
            ret['quarantined'] = 'Yes'
        return ret

    def get_format_suggestion(self, cmd):
        return self.all_commands[cmd].get_fs()

if __name__ == '__main__':
    Cerebrum = Factory.get('Database')()
    sm = BofhdExtension(Cerebrum)
    print "Ret: %s" % sm.get_stedkode_info('user', '900547')

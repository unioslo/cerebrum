# Copyright 2002 University of Oslo, Norway
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

from cmd_param import Command,Id


class BofhdExtension(object):
    def __init__(self, Cerebrum):
        self.all_commands = {
            'get_stedkode_info': Command(('ou', 'stedkode'), Id())
            }
        self.ou = Factory.get('OU')(Cerebrum)

    def get_commands(self, uname):
        # TODO: Do some filtering on uname to remove commands
        commands = {}
        for k in self.all_commands.keys():
            commands[k] = self.all_commands[k].get_struct()
        return commands

    def get_stedkode_info(self, uname, number):
        fakultetnr, instituttnr, gruppenr = number[0:2], number[2:4], number[4:6]
        self.ou.find_stedkode(fakultetnr, instituttnr, gruppenr)
        self.ou.find(self.ou.ou_id)
        return {
            'name': self.ou.name,
            'acronym': self.ou.acronym,
            'short_name': self.ou.short_name,
            'display_name': self.ou.display_name,
            'sort_name': self.ou.sort_name
            }

    def get_format_suggestion(self, cmd):
        suggestions = {
            'get_stedkode_info':
            "Navn: %s\nAcronym: %s\nShort: %s¤name;acronym;short_name"
            }
        return suggestions.get(cmd)

if __name__ == '__main__':
    Cerebrum = Factory.get('Database')()
    sm = BofhdExtension(Cerebrum)
    print "Ret: %s" % sm.get_stedkode_info('user', '900547')

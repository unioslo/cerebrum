#!/usr/bin/env python2

# $Id$

# Samlple module that extends bofhd with a set of commands

from Cerebrum import Database
from Cerebrum.modules.no.uio import OU

class BofhdExtention:
    def __init__(self, Cerebrum):
        self.all_commands = {
            'get_stedkode_info' : ['ou', 'stedkode', 'number', 1]
            }
        self.ou = OU.OU(Cerebrum)

    def get_commands(self, uname):
        # TODO: Do some filtering on uname to remove commands
        commands = {}
        for k in self.all_commands.keys():
            commands[k] = self.all_commands[k]
        return commands

    def get_stedkode_info(self, uname, number):
        fakultetnr, instituttnr, gruppenr = number[0:2], number[2:4], number[4:6]
        self.ou.find_stedkode(fakultetnr, instituttnr, gruppenr)
        self.ou.find(self.ou.ou_id)
        return {
            'name' : self.ou.name,
            'acronym' : self.ou.acronym,
            'short_name' : self.ou.short_name,
            'display_name' : self.ou.display_name,
            'sort_name' : self.ou.sort_name
            }

    def get_format_suggestion(self, cmd):
        suggestions = {
            'get_stedkode_info' : "Navn: %s\nAconym: %s\nShort: %s¤name;acronym;short_name"
            }
        return suggestions.get(cmd)

if __name__ == '__main__':
    Cerebrum = Database.connect(user="cerebrum")
    sm = BofhdExtention(Cerebrum)
    print "Ret: %s" % sm.get_stedkode_info('user', '900547')

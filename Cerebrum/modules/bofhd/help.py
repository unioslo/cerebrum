#!/usr/bin/env python2.2

# The help is stored in three dicts, which makes it possible to only
# display a subset of the total help-text.

# ah maps the name of a specific command-argument to its actual
# help-text.

# group_help contains the general help text, as well as help for the
# main commands (group, user, misc etc.)

_group_help = {'general': """Hjelp for jbofh.

jbofh er en komandolinje orientert klient for administrasjon av
brukere.  Detaljert hjelp kan finnes på http://.....
For hjelp om en enkelt hovedgruppe, skriv "help <hovedgruppe>".
Tilgjengelige hovedgrupper:
""",
              }

# Help for all commands.  Format:
# ch = {<cmd_group_name>: {<callable_func>: short-help-string} }
# By making the second hash-key point to the command func, the help
# text don't need to be updated if the name of the command changes.

# TBD: We may want to make the hash value = [<short-help-string>,
# <optional-long-help>]
_command_help = {
      }

# Define prompt and help text for each command-argument.  Format:
# <key>: [<arg-text>, <prompt>, <help-text>]
#
# See Help.get_arg_help() for the meaning of a ":" in the key

_arg_help = {
    'account_name': ['uname', 'Enter accountname'],
    'entity_type': ['entity_type', 'Entity type', """Possible values:
 - group
 - account"""],
    'posix_gecos': ['gecos', 'Enter gecos'],
    'string': ['string', 'Enter value'],
    'person_search_type': ['search_type', 'Enter person search type',
                           """Possible values:
  - name
  - birth date (YYYY-MM-DD)
  - person_id"""]
      }

import pprint
pp = pprint.PrettyPrinter(indent=4)

class Help(object):
    def __init__(self, cmd_instances):
        self.group_help = _group_help
        self.command_help = _command_help
        self.arg_help = _arg_help
        for c in cmd_instances:
            gh, ch, ah = getattr(c, "get_help_strings")()
            for k in gh.keys():
                self.group_help[k] = gh[k]
            for k in ch.keys():
                self.command_help[k] = ch[k]
            for k in ah.keys():
                self.arg_help[k] = ah[k]

    def _map_all_commands(self, all_commands):
        """Return a mapping {'maingroup': {'call_func': data}}. 'data'
        is whatever Command.get_struct() returned when the mapping was
        made"""
        ret = {}
        for k in all_commands.keys():
            ret.setdefault(all_commands[k][0][0], {})[k] = all_commands[k]
        return ret

    def get_general_help(self, all_commands, no_filter=0):
        known_commands = self._map_all_commands(all_commands)
        keys = self.group_help.keys()
        keys.sort()
        ret = self.group_help['general']+"\n"
        keys.remove('general')
        for k in keys:
            if no_filter or known_commands.has_key(k):
                ret += "   %-10s - %s\n" % (k, self.group_help[k])
        return ret

    def _cmd_help(self, cmd_struct, call_func):
        args = []
        if (len(cmd_struct) > 1
            and isinstance(cmd_struct[1], (tuple, list))):
            for a in cmd_struct[1]:
                tmp = self.arg_help[a['help_ref']][0]
                if a.has_key('repeat') and a['repeat']:
                    tmp += "+"
                if a.has_key('optional') and a['optional']:
                    tmp = "[%s]" % tmp
                args.append(tmp)
        return cmd_struct[0][1], args, self.command_help[cmd_struct[0][0]][call_func]
        
    def _wrap_cmd_help(self, dta):
        """Try to wrap the help text in a way that looks good.  This
        is not easy to accomplish for long commands... """

        maxlen = [0, 0]
        for d in dta:
            if len(d[0]) > maxlen[0]:
                maxlen[0] = min(len(d[0]), 20)
            tmp = len(" ".join(d[1]))
            if tmp > maxlen[1]:
                maxlen[1] = min(tmp, 40)
        ret = []
        for d in dta:
            tmp = " ".join(d[1])
            line = ("    " + d[0] + " " * (maxlen[0] - len(d[0])) + " " +
                    tmp + " " * (maxlen[1] - len(tmp)))
            help = d[2]
            if 0:
                line += " : "
                rest_space = 80 - len(line)
            else:
                rest_space = 80 - maxlen[0] - 7
                line += "\n"+ " " * (80 - rest_space - 2) + "- "
            while rest_space < len(help):
                idx = help.rfind(" ", 0, rest_space)
                if idx == -1:
                    rest_space += 1
                    continue
                line += help[:idx] + "\n" + " " * (80 - rest_space)
                help = help[idx+1:]
            line += help
            ret.append(line)
        return "\n".join(ret)
        
    # TODO: Need a better way to warn about inconsistency between
    # command-defs and help data
    def get_group_help(self, all_commands, group, no_filter=0):
        if not self.command_help.has_key(group):
            return "Unkown command group: %s" % group
        ret = "   %-10s - %s\n" % (group, self.group_help[group])
        known_commands = self._map_all_commands(all_commands)
        call_func_keys = self.command_help[group].keys()
        call_func_keys.sort()
        not_shown = known_commands[group].keys()
        lines = []
        for call_func in call_func_keys:
            if no_filter or known_commands.get(group, {}).get(call_func, None) != None:
                lines.append(self._cmd_help(all_commands[call_func], call_func))
        return ret + self._wrap_cmd_help(lines)
        
    def get_cmd_help(self, all_commands, maingrp, subgrp, filter=1):
        for call_func in all_commands.keys():
            if all_commands[call_func][0] == (maingrp, subgrp):
                sub_cmd, args, help = self._cmd_help(all_commands[call_func], call_func)
                return "%-8s %-10s - %-30s : %s\n" % (maingrp, sub_cmd, " ".join(args), help)

    def get_arg_help(self, help_ref):
        """Return help string for the arguemtn identified by help_ref.
        If help_ref is something like user_id:current, and no help is
        specified, try returning the help for 'user_id'"""
        if len(self.arg_help[help_ref]) == 3:
            return self.arg_help[help_ref][2]
        if help_ref.find(":") > 0:
            tmp = help_ref[:help_ref.find(":")]
            if len(self.arg_help[tmp]) == 3:
                return self.arg_help[tmp][2]
        return self.arg_help[help_ref][1]
    
    def check_consistency(self, all_commands):
        """Simple consistency check for the help text.  Checks that:
        - all commands have a help text
        - no help text are defined that are not used
        - no help_attrs are defined that are not used.
        Any missing help_attrs would raise a KeyError in
        get_commands(), so this is not checked.

        Note that the check only tests data in all_commands.  Thus
        arg_help entries from prompt_func is not detected."""

        ch = self.command_help.copy()
        used_arg_help = {}
        for k in self.arg_help.keys():
            used_arg_help[k] = 0
        for call_func in all_commands.keys():
            grp = all_commands[call_func][0][0]
            if ch.get(grp, {}).get(call_func, None) != None:
                del(ch[grp][call_func])
            else:
                print "Missing help for %s" % call_func
            if len(all_commands[call_func]) > 1:
                if isinstance(all_commands[call_func][1], (tuple, list)):
                    for arg in all_commands[call_func][1]:
                        used_arg_help[arg['help_ref']] = 1
        for k in used_arg_help.keys():
            if used_arg_help[k]:
                del(used_arg_help[k])
        print "Unused arg_help: %s" % used_arg_help.keys()
        for k in ch.keys():
            if ch[k]:
                print "Unused help for %s" % ch[k].keys()

if __name__ == '__main__':
    import getopt
    import sys

    opts, args = getopt.getopt(sys.argv[1:], 'hga',
                               ['help', 'group', 'arg'])

    gh_keys = group_help.keys()
    gh_keys.sort()
    gh_keys.remove('general')
    for opt, val in opts:
        if opt in ('-h', '--help'):
            print "=========================== General help ==========================="
            get_general_help()
        elif opt in ('-g', '--group'):
            print "\n=========================== Group help ==========================="
            for g in gh_keys:
                get_group_help(g)
        elif opt in ('-a', '--arg'):
            print "\n============================ Arg help ============================"
            for g in gh_keys:
                keys2 = command_help[g].keys()
                keys2.sort()
                print "-------------------- %s --------------------" % g
                for c in keys2:
                    print "%s - %s" % (c, command_help[g][c][0])
                    for argtype in command_help[g][c][2:]:
                        print "   at=%s" % argtype

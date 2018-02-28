#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2018 University of Oslo, Norway
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
""" Help-command functionality for bofhd. """

# TODO: Update and clean this wall of text:

_help_general = """
BOFH help:

BOFH is a command-line application for user administration.

More information about BOFH be viewed at:
    http://www.uio.no/tjenester/it/brukernavn-passord/bofh/

help <<command-group>> shows detailed information about commands in any of the
main command groups.  A plus after an argument in the syntax description means
that more than one argument can be given by putting them inside parentheses.

Additional help is available in form of the commands <<help glossary>>,
<<help intro>> and <<help basics>>.

Available main command groups are:
"""

_help_glossary = """
Glossary of common terms in Cerebrum:
- account: a user account (POSIX or generic user) in Cerebrum
- account authentication: data needed to authenticate a particular
  user throughout the system
- account owner: person or group which holds the ownership of an
  account
- account type: describes the ownership of an non-personal account
  (i.e. system account, software account, group account)
- affilliation: the role a person possess within an organizational unit
- affiliation status code: more precise description of a persons role
  (i.e. affiliation -> STUDENT, affiliation status code -> aktiv)
  within an organizational unit
- authoritative system: source system primarily used to update any
  particular type of data in Cerebrum
- changelog: system for keeping track of modifications to the database
  and making other systems detect changes at sync-time
- core: Cerebrum core API (see http://cerebrum_core...)
- disk: a disk defined on a machine registered in Cerebrum
- entity: an account (user), organizational unit, person or a group
  registered in Cerebrum (abstract concept allowing easy administration
  within Cerebrum)
- entity id: an id assigned to each entity that exist in Cerebrum
- email domain: the domain assignet to each e-mail address in Cerebrum
  (the part of the address after the "@")
- export id: an internal id assigned to each entity used to ease the
  export of Cerebrum-specific data to other systems
- external id: unique id assigned to each person registered in Cerebrum
   (e.g. national social security number)
- group: a collection of users or machines usually used to assign various
  permissions in Cerebrum or other systems
- group visibility:
- home: home directory of a user registered in Cerebrum
- uid: the numeric user ID value space in UNIX
- host: a machine registered in Cerebrum
- ou: Organizational Unit
- ou perspective: decides which ou-structure is to be used
- spread: decides in which parts of the system within the organization an
  entity should be recognized
- quarantine: limitations imposed on entitis in Cerebrum
- quota: the resources available to a user in terms of storage
  (home directory or email) or printing (sheets of paper available
  per week)
"""

_help_intro = """
Although Cerebrum encourages use of automatic processing, a need for
manually done modifications of the contents of the database is usually
present in any large organization. BOFH is a command-line based client
software for Cerebrum developed at the University of Oslo to facilitate
this need. In order to use BOFH authentication is required and privileges
assigned to the account owner calculated (through group membership). All
communication between a BOFH user and the database happens during a
session (which starts when BOFH is started and authentication is
successful). The server logs information about which actions are
performed by which user, and also records the changes made to
interesting attributes of registered users in the system.  This
enables the privileged users of the system to trace the changes and
thus correct errors introduced into the system.  During a session a
user typically executes various commands and some of these (and their
consequences) are temporarily stored in a way that allows the user to
retrace his or her steps.
"""

_help_basics = """
Register a new employee and create an account for them:
Preprocessing:

1. Find the number of the organizational unit they will be affiliated to
2. Find out what kind of affiliation the person is going to have to the OU

1. Check whether the person is registered in Cerebrum
  - jbofh >person find
    Enter person search type >name
    Enter value >Jasmina
    Id Birth Exp-id Name
    *****************************************
    72467 08.11.74 exp-72467 Jasmina Hodzic
    *****************************************
2. Check whether they already have an account at UiO
  - bofh >person accounts
    Enter person id >entity_id:72467
    Id Name
    72470 jazz
    72468 jazztest
    72469 jasminah
3. Check the attributes the account has
  -  jbofh >user info jazz
     Spreads: AD_account,NIS_user@uio
     Affiliations: ANSATT@USIT, GT

This means that Jasmina Hodzic (id 72467) has an account (name jazz) with the
affiliation ANSATT, tekadm to OU 331520 (USIT, GT).
If the person you are looking for is not registered in Cerebrum the search vil
return no id. Use

 - jbofh >person create
   Enter person id >?
   Enter person id as idtype:id.
   If idtype=fnr, the idtype does not have to be specified.
   The currently defined id-types are:
   - fnr : norwegian f?dselsnummer.
   Enter person id >9090909090
   Enter date of birth(YYYY-MM-DD) >1974-11-08
   Enter persons fullname >Pernilla Nyansatt
   Enter OU >331520
   Enter affiliaton >AFFILIATION
   Enter affiliation status >affilition_status_code

Any cryptic error messages mean that you have typed something wrong. In case of
Pernilla the error message is
Error: Cerebrum.modules.no.fodselsnr.InvalidFnrError:Unknown error (a server
error has been logged) which means that the fødselsnummer was wrong :).

4. Create an account:
 - jbofh >user create
   Person identification >?
   Identify account owner (person or group) by entering:
   Birthdate (YYYY-MM-DD)
   Norwegian f?dselsnummer (11 digits)
   Export-ID (exp:exportid)
   External ID (idtype:idvalue)
   Group name (group:name)

Typing ? a any given prompt will provide you with an brief explanation about
the parametar you have to enter.

5. Create a group:
 - jbofh >group create
   Enter the new group name >testgruppe
   Enter description >Jasmina tester.
   Group created as a normal group, internal id: 224995

This means that a Cerebrum group has been created. However, if you want this
group to act as a file group or a net group you also need to make a posix group
of it:
 - jbofh >group promote_posix
   Enter groupname >testgruppe
   Group promoted to PosixGroup, posix gid: 1030

In addition you will need to give this group a spread to make it known to the
rest of the system. This is done by using the command spread add. If you want
to make "testgruppe" a file group you need to execute the following command:
 - jbofh >spread add
   Entity type [account] >group
   Enter id >224995
   Enter spread >NIS_fg@uio

For net groups use the spread "NIS_ng@uio". Groups to be included in Active
Directory have to be given the spread AD_group.

6. Move a user
One of the most common tasks is moving a users home directory to another disk.
This is usually done when a person gets an affiliation to a different OU. The
basic command for this is user move. user move accepts following options:
   1. immediate (immediately move users home directory to another disk)
   2. batch (enqueue the moving request)
   3. nofile (do not move the home directory)
   4. hard_nofile (move user to a non registered disk)
   5. student (find appropriate disk for this user and enquey the request)
   6. student_immediate (find appropriate student disk for this user and
      move home directory)
   7. give (user has lost affiliation to your OU, let someone else take them)
   8. request (ask others for a spesific users)
   9. confirm (take a user given away)
  10. cancel (cancel the move request)

 - jbofh >user move
   Enter move type >give
   Enter accountname >jazztest
   Enter groupname >testgruppe
   Why? >Nytt ansettelsessted.
   OK, 'give' registered

 - jbofh >user move request jasminah
   Enter disk >/usit/saruman/gt-u1
   Why? >Vil ha.
   OK, request registered

"""


# The help is stored in three dicts, which makes it possible to only
# display a subset of the total help-text.

# group_help contains the general help text, as well as help for the
# main commands (group, user, misc etc.)

_group_help = {
    'general': _help_general,
    'glossary': _help_glossary,
    'intro': _help_intro,
    'basics': _help_basics,
}

# Help for all commands.  Format:
# ch = {<cmd_group_name>: {<callable_func>: short-help-string} }
# By making the second hash-key point to the command func, the help
# text don't need to be updated if the name of the command changes.

# TBD: We may want to make the hash value = [<short-help-string>,
# <optional-long-help>]
_command_help = {}

# Define prompt and help text for each command-argument.  Format:
# <key>: [<arg-text>, <prompt>, <help-text>]
#
# See Help.get_arg_help() for the meaning of a ":" in the key

_arg_help = {
    'account_name':
        ['uname', 'Enter accountname'],
    'auth_attribute':
        ['attribute', 'Enter attribute value',
         'Possible values depend on the target\'s entity type.  For hosts, '
         'it is a regular expression matching the last component of a disk '
         'path (\'mn-l.*\'). For OU\'s, it is an affiliation (\'STUDENT\').'],
    'auth_entity_type':
        ['auth_type', 'Authorisation entity type',
         'Possible values:\n'
         ' - disk\n - dns\n - group\n - host\n - maildom\n - ou\n - spread'],
    'auth_target_entity':
        ['entity', 'Enter name of target entity',
         'The object to which access should be given'],
    'auth_group':
        ['group', 'Enter group name',
         'The name of the group which should be given access'],
    'email_address':
        ['address', 'Enter e-mail address'],
    'entity_type':
        ['entity_type', 'Entity type',
         "Possible values:\n - group\n - account"],
    'integer':
        ['number', 'Enter an integral number'],
    'posix_gecos':
        ['gecos', 'Enter gecos'],
    'string':
        ['string', 'Enter value'],
    'group_search_type':
        ['search_type', 'Enter group search type',
         'This should be a hash, so just forget it'],
    'opset':
        ['operation_set', 'Enter name of operation set',
         'Use "access list_opsets" to view a list of valid values'],
    'person_search_type':
        ['search_type', 'Enter person search type',
         'Possible values:\n'
         '- name\n- date (of birth, on format YYYY-MM-DD)\n- person_id'],
}


class PrintLog(object):
    """ Mock logger, prints to stdout. """

    def error(self, msg):
        """ Prints a log entry with level ERROR. """
        print "ERROR: %s" % (msg,)

    def warn(self, msg):
        """ Prints a log entry with level WARNING. """
        print "WARN: %s" % (msg,)

    def info(self, msg):
        """ Prints a log entry with level INFO. """
        print "INFO: %s" % (msg,)

    def debug(self, msg):
        """ Prints a log entry with level DEBUG. """
        print "DEBUG: %s" % (msg,)


def merge_help_strings(*tuples):
    """ Merge tuples with bofhd help_strings. """
    groups, cmds, args = {}, {}, {}
    for g, c, a in tuples:
        # update group descriptions
        groups.update(g)
        # update command descriptions
        for group in c:
            cmds.setdefault(group, {}).update(c[group])
        # update key descriptions
        args.update(a)
    # Filter out any unused groups
    groups = dict((k, v) for k, v in groups.items()
                  if k in cmds)
    return groups, cmds, args


class Help(object):

    def __init__(self, cmd_instances, logger=None):
        """ Initialize the help text generator.

        :param list cmd_instances:
            A list of initialized BofhdCommandBase classes.
        :param logging.Logger logger:
            A PEP-282 compatible python logger.

        """
        self.group_help = _group_help
        self.command_help = _command_help
        self.arg_help = _arg_help
        self.logger = logger or PrintLog()
        for cls in cmd_instances:
            self.update_from_extension(cls)

    def update_from_extension(self, extension_cls):
        u""" Update help data from a BofhdExtension. """
        # TODO: Assert exension_cls type?
        (group_help,
         cmd_help,
         arg_help) = getattr(extension_cls, "get_help_strings",
                             lambda *args: ({}, {}, {}))()
        for grp_name in group_help:
            if grp_name in self.group_help:
                # Don't overwrite existing group help
                continue
            self.group_help[grp_name] = group_help[grp_name]
        for cmd_name in cmd_help:
            self.command_help.setdefault(
                cmd_name, {}).update(cmd_help[cmd_name])
        for arg_ref in arg_help:
            self.arg_help[arg_ref] = arg_help[arg_ref]

    def _map_all_commands(self, all_commands):
        """TODO: Better doctsting.

        Return a mapping {'maingroup': {'call_func': data}}. 'data'
        is whatever Command.get_struct() returned when the mapping was
        made"""
        ret = {}
        for k in all_commands.keys():
            ret.setdefault(all_commands[k][0][0], {})[k] = all_commands[k]
        return ret

    def get_general_help(self, all_commands, no_filter=False):
        """ Get 'general' help string, and a list of all known commands

        :param dict all_commands:
            A dict of all existing BofhCommands.
        :param bool no_filter:
            If the result should return a list of all commands, or a filtered
            set of commands.

        :return str:
            Returns a help string.

        """
        known_commands = self._map_all_commands(all_commands)
        keys = self.group_help.keys()
        keys.sort()
        ret = self.group_help['general'].strip() + "\n"
        keys.remove('general')
        for k in keys:
            if no_filter or k in known_commands:
                ret += "   %-10s - %s\n" % (k, self.group_help[k])
        return ret

    def _cmd_help(self, cmd_struct, call_func):
        """ TODO: Document. """
        args = []
        if (len(cmd_struct) > 1
                and isinstance(cmd_struct[1], (tuple, list))):
            for a in cmd_struct[1]:
                tmp = self.arg_help[a['help_ref']][0]
                if a.get('repeat', None):
                    tmp += "+"
                if a.get('optional', None):
                    tmp = "[%s]" % tmp
                args.append(tmp)
        return (cmd_struct[0][1],
                args,
                self.command_help[cmd_struct[0][0]][call_func])

    def _wrap_cmd_help(self, dta):
        """TODO: Better docstring.

        Try to wrap the help text in a way that looks good.  This
        is not easy to accomplish for long commands...

        """
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
                line += "\n" + " " * (80 - rest_space - 2) + "- "
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
    def get_group_help(self, all_commands, group, no_filter=False):
        """ TODO: Document. """
        if group not in self.command_help:
            if group in self.group_help:
                return self.group_help[group]
            return "Unkown command group: %s" % group
        ret = "   %-10s - %s\n" % (group, self.group_help[group])
        known_commands = self._map_all_commands(all_commands)
        call_func_keys = self.command_help[group].keys()
        call_func_keys.sort()
        if group not in known_commands:
            return "Unkown command group: %s" % group
        lines = []
        for call_func in call_func_keys:
            cmd_group = known_commands.get(group, {})
            if (no_filter or cmd_group.get(call_func, None) is not None):
                lines.append(self._cmd_help(all_commands[call_func],
                                            call_func))
        return ret + self._wrap_cmd_help(lines)

    def get_cmd_help(self, all_commands, maingrp, subgrp, filter=1):
        """ TODO: Document. """
        for call_func in all_commands.keys():
            if all_commands[call_func][0] == (maingrp, subgrp):
                sub_cmd, args, help = self._cmd_help(all_commands[call_func],
                                                     call_func)
                return "%-8s %-10s - %-30s : %s\n" % (maingrp,
                                                      sub_cmd,
                                                      " ".join(args),
                                                      help)

    def get_arg_help(self, help_ref):
        """TODO: Better docstring.

        Return help string for the arguemtn identified by help_ref.
        If help_ref is something like user_id:current, and no help is
        specified, try returning the help for 'user_id'

        """
        if len(self.arg_help[help_ref]) == 3:
            return self.arg_help[help_ref][2]
        if help_ref.find(":") > 0:
            tmp = help_ref[:help_ref.find(":")]
            if len(self.arg_help[tmp]) == 3:
                return self.arg_help[tmp][2]
        return self.arg_help[help_ref][1]

    def check_consistency(self, all_commands):
        """ TODO: Better docstring.

        Simple consistency check for the help text.  Checks that:
        - all commands have a help text
        - no help text are defined that are not used
        - no help_attrs are defined that are not used.
        Any missing help_attrs would raise a KeyError in
        get_commands(), so this is not checked.

        Note that the check only tests data in all_commands.  Thus
        arg_help entries from prompt_func is not detected.

        """
        # Make a semi deep copy of command_help (copy of the main dict is not
        # enough, have to copy the sub elements too):
        ch = dict((group, self.command_help[group].copy())
                  for group in self.command_help)
        used_arg_help = {}
        for k in self.arg_help.keys():
            used_arg_help[k] = 0
        for call_func in all_commands.keys():
            grp = all_commands[call_func][0][0]
            if ch.get(grp, {}).get(call_func, None) is not None:
                del(ch[grp][call_func])
            else:
                self.logger.warn("Missing help for %s" % call_func)
            if len(all_commands[call_func]) > 1:
                if isinstance(all_commands[call_func][1], (tuple, list)):
                    for arg in all_commands[call_func][1]:
                        used_arg_help[arg['help_ref']] = 1
        for k in used_arg_help.keys():
            if used_arg_help[k]:
                del(used_arg_help[k])
        self.logger.debug2("Unused arg_help: %s" % used_arg_help.keys())
        for k in ch.keys():
            if ch[k]:
                self.logger.debug2("Unused help for %s" % ch[k].keys())


def test(args=None):
    """ Test the help structure.

    :rtype: int, str
    :return: 0 on success, non-zero value or error string on failure.

    """
    import argparse

    def get_help(config=None):
        # TODO: Read 'config' file, import and initialize classes?
        bofhd_extensions = []
        return Help(bofhd_extensions)

    def get_all_commands():
        # TODO: Where do we get this from?
        return {}

    def cb_general(args):
        bofhd_help = get_help(args.config)
        print "======================= General help ========================="
        print bofhd_help.get_general_help(get_all_commands())

    def cb_group(args):
        bofhd_help = get_help(args.config)
        print "\n======================== Group help ========================="
        for g in sorted(bofhd_help.group_help.keys()):
            print "-------------------- %s --------------------" % g
            print bofhd_help.get_group_help(get_all_commands(), g)

    def cb_command(args):
        # TODO: This is completely useless without a config...
        bofhd_help = get_help(args.config)
        print "\n========================= Arg help =========================="
        for g in sorted(bofhd_help.command_help.keys()):
            print "-------------------- %s --------------------" % g
            for c in sorted(bofhd_help.command_help[g].keys()):
                print "%s - %s" % (c, bofhd_help.command_help[g][c][0])
                for argtype in bofhd_help.command_help[g][c][2:]:
                    print "   at=%s" % argtype

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config',
                        default=None,
                        metavar='FILE',
                        help='Bofhd config file')

    subparser = parser.add_subparsers()
    general = subparser.add_parser('general', help='General help')
    general.set_defaults(cb=cb_general)
    group = subparser.add_parser('group', help='Help for command groups')
    group.set_defaults(cb=cb_group)
    command = subparser.add_parser('command', help='Help for commands')
    command.set_defaults(cb=cb_command)

    args = parser.parse_args(args)
    args.cb(args)

    return 0


if __name__ == '__main__':
    raise SystemExit(test())

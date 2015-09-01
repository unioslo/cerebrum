#!/usr/bin/env python2
# encoding: utf-8
#
# Copyright 2015 University of Oslo, Norway
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
""" This module contains a password print command for bofhd. """

import cerebrum_path
import cereconf

from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.bofhd.cmd_param import Command
from .printer import LinePrinter
from .tex import prepare_tex
from . import password_letter


class BofhdExtension(BofhdCommonMethods):
    u""" BofhdExtension for printing password sheets. """

    __DEFAULT_PRINTER_STATE = 'default_printer'

    all_commands = {}
    u""" All exposed commands in this extension. """

    def __init__(self, server):
        super(BofhdExtension, self).__init__(server)

    def __get_template(self, selection):
        u""" Get a template or a list of all templates.

        :param str selection:
            If numerical string, get the n-th template.
            Else match it according to the help text.

        :return list,dict: A template dict or list of template descriptions.

        """
        tpl_options = password_letter.list_password_print_options()

        # Numeric selection
        if type(selection) is int:
            try:
                return tpl_options[selection]
            except IndexError:
                raise CerebrumError(
                    u"Invalid template number %d, must be in range 0-%d" %
                    (selection, len(tpl_options)))

        # Text selection
        try:
            lang, ttype = selection.split(':', 1)
            for tpl in tpl_options:
                if tpl.get('lang') == lang and tpl.get('type') == ttype:
                    return tpl
            raise CerebrumError(
                u"No template %r in language %r" % (lang, ttype))
        except ValueError:
            # unpacking of selection.split() failed
            pass
        raise CerebrumError("Invalid template %r" % selection)

    def __get_default_printer(self, session):
        u""" Get the 'default_printer' from session.

        :param BofhdSession session: The current session

        :return str,None: The default printer, or None.

        """
        state = session.get_state(state_type=self.__DEFAULT_PRINTER_STATE)
        if state:
            return state[0]['state_data'] or None
        return None

    def __set_default_printer(self, session, printer):
        u""" Set the 'default_printer' in session.

        :param BofhdSession session: The current session
        :param str printer: The new default printer selection.

        """
        if self.__get_default_printer(session) == printer:
            return
        session.clear_state(state_types=[self.__DEFAULT_PRINTER_STATE, ])
        session.store_state(self.__DEFAULT_PRINTER_STATE, printer)
        self.db.commit()

    def __get_cached_passwords(self, session):
        u""" List all new passwords cached in session. """
        cached_passwds = []
        for r in session.get_state():
            # state_type, entity_id, state_data, set_time
            if r['state_type'] in ('new_account_passwd', 'user_passwd'):
                cached_passwds.append({
                    'username': self._get_entity_name(
                        r['state_data']['account_id'],
                        self.const.entity_account),
                    'password': r['state_data']['password'],
                    'operation': r['state_type']})
        return cached_passwds

    def __select_cached_passwords(self, session, selection):
        u""" Get selection of new passwords cached in session. """
        new_passwds = self.__get_cached_passwords(session)

        def get_index(idx):
            try:
                # Index starts at 1
                return new_passwds[int(idx) - 1]
            except (ValueError, IndexError):
                raise CerebrumError(u"Invalid selection %r" % idx)

        def get_range(r):
            try:
                s, e = str(r).split('-', 1)
                return range(int(s), int(e) + 1)
            except ValueError:
                raise CerebrumError(u"Invalid range %r" % r)

        selection = str(selection)

        ret = []
        groups = selection.split(',')
        for group in groups:
            if group.isdigit():
                ret.append(get_index(group))
            else:
                for i in get_range(group):
                    ret.append(get_index(i))
        if not ret:
            raise CerebrumError("Invalid selection %r" % selection)
        return ret

    def get_help_strings(self):
        u""" Help strings for this bofhd extension. """
        group_help = {
            'misc': 'Misc commands', }

        command_help = {
            'misc': {
                'misc_print_passwords':
                    'Print password sheets or letters', }, }

        arg_help = {
            'print_select_template':
                ['template', 'Select template',
                 ("Choose template by entering its name. The format of "
                  "the template name is: <language>/<type>:<template>. If "
                  "type is 'letter' the password will be sent through "
                  "snail-mail from a central printer.")],
            'print_select_range':
                ['range', 'Select range',
                 ("Select entries by entering a space-separated list of "
                  "numbers. Ranges can be written as '3-15'.")], }

        return (group_help, command_help, arg_help)

    def misc_print_passwords_prompt_func(self, session, *args):
        u""" Validate and prompt for 'misc print_passwords' arguments.

        :param BofhdSession session: The current session

        :return dict,None:
            A dict with prompt-data, or None if all arguments are fetched.

        """
        all_args = list(args[:])

        # Ask for template argument
        if not all_args:
            mapping = [(("Alternatives",), None)]
            n = 1
            for t in password_letter.list_password_print_options():
                mapping.append(((t.get('desc'),), n))
                n += 1
            return {'prompt': "Choose template #",
                    'map': mapping,
                    'help_ref': 'print_select_template'}

        tpl = self.__get_template(all_args.pop(0))

        # Ask for printer argument
        if not tpl.get('lang', '').endswith('letter'):
            if not all_args:
                ret = {'prompt': 'Enter printer name'}
                if self.__get_default_printer(session):
                    ret['default'] = self.__get_default_printer(session)
                return ret
            skriver = all_args.pop(0)
            self.__set_default_printer(session, skriver)

        # Ask for password change from history
        if not all_args:
            n = 1
            mapping = [(("%8s %s", "uname", "operation"), None)]
            for row in self.__get_cached_passwords(session):
                mapping.append(
                    (("%-12s %s", row['username'], row['operation']), n))
                n += 1
            if n == 1:
                raise CerebrumError(u"No new passwords in session")
            return {'prompt': 'Choose user(s)',
                    'last_arg': True,
                    'map': mapping,
                    'raw': True,
                    'help_ref': 'print_select_range',
                    'default': str(n-1)}

    #
    # misc print_passwords [template [printer] [range]]
    #
    # TODO: Should the access to this command be restricted?
    #
    all_commands['misc_print_passwords'] = Command(
        ("misc", "print_passwords"),
        prompt_func=misc_print_passwords_prompt_func)

    def misc_print_passwords(self, operator, *args):
        u""" Print password sheets or letters.

        :param BofhdSession operator: The current session.

        :return str: Lisings of the successful print jobs.

        """
        args = list(args[:])
        tpl_options = password_letter.list_password_print_options()
        tpl_choice = args.pop(0)
        template = None
        destination = None
        passwds = []

        template = tpl_options[tpl_choice]
        if template.get('lang', '').endswith("letter"):
            destination = cereconf.PRINT_PRINTER
        else:
            destination = args.pop(0)

        passwds = self.__select_cached_passwords(operator, args.pop(0))

        print_user = self._get_account(operator.get_entity_id(), idtype='id')
        printer = LinePrinter(
            destination,
            uname=print_user.account_name)

        # TODO: Alter the command based on destination?

        letters = []
        ret = []
        for pwd in passwds:
            letter = password_letter.make_password_letter(
                self._get_account(pwd['username']),
                pwd['password'],
                template)
            if template.get('fmt') == 'tex':
                letter = prepare_tex(letter)
            letters.append(letter)
            ret.append("OK: %s/%s.%s spooled @ %s for %s" % (
                template.get('lang'),
                template.get('type'),
                template.get('fmt'),
                destination,
                pwd['username']))
        printer.spool(*letters)

        return "\n".join(ret)


if __name__ == '__main__':
    del cerebrum_path

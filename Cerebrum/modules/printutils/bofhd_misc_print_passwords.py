#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015-2016 University of Oslo, Norway
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
""" This module contains a password print command for bofhd.

Configuration
-------------
The following `cereconf' values are used in this module:

JOB_RUNNER_LOG_DIR
    A directory for temporary files. This is where we'll keep the generated
    files from our templates.
"""
from __future__ import unicode_literals
import os
import re
import time
import tempfile

import cereconf

from Cerebrum.modules.templates import config as tmpl_config
from Cerebrum.modules.templates import renderers
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.bofhd.cmd_param import Command
from .printer import LinePrinter


class BofhdExtension(BofhdCommonMethods):
    u""" BofhdExtension for printing password sheets. """

    __DEFAULT_PRINTER_STATE = 'default_printer'

    all_commands = {}
    parent_commands = False

    def __get_template(self, selection, template_config):
        u""" Get a template.

        :param str selection:
            If numerical string, get the n-th template.
            Else match it according to the help text.

        :return list,dict: A template dict or list of template descriptions.

        """
        tpl_options = template_config.print_password_templates

        # Numeric selection
        try:
            return tpl_options[int(selection) - 1]
        except IndexError:
            raise CerebrumError(
                u"Invalid template number {}, must be in range 1-{}"
                .format(selection, len(tpl_options)))
        except ValueError:
            # int() failed
            pass
        raise CerebrumError("Invalid template %r" % selection)

    def __get_cached_passwords(self, session):
        u""" List all new passwords cached in session. """
        cached_passwds = []
        for row in session.get_state():
            # state_type, entity_id, state_data, set_time
            if row['state_type'] in ('new_account_passwd', 'user_passwd'):
                cached_passwds.append({
                    'username': self._get_entity_name(
                        row['state_data']['account_id'],
                        self.const.entity_account),
                    'password': row['state_data']['password'],
                    'operation': row['state_type']})
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

        def get_range(rangestr):
            try:
                start, end = str(rangestr).split('-', 1)
                return range(int(start), int(end) + 1)
            except ValueError:
                raise CerebrumError(u"Invalid range %r" % rangestr)

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

    def _get_default_printer(self, session):
        u""" Get a default printer for the prompt.

        This function fetches the previously selected printer.

        :param BofhdSession session: The current session
        :param dict template: The selected template

        :return str,None: The default printer, or None.

        """
        state = session.get_state(state_type=self.__DEFAULT_PRINTER_STATE)
        if state and state[0]['state_data']:
            return state[0]['state_data']
        return None

    def _set_default_printer(self, session, printer):
        u""" Set the 'default_printer' in session.

        :param BofhdSession session: The current session
        :param str printer: The new default printer selection.

        """
        if self._get_default_printer(session) == printer:
            return
        session.clear_state(state_types=[self.__DEFAULT_PRINTER_STATE, ])
        session.store_state(self.__DEFAULT_PRINTER_STATE, printer)
        self.db.commit()

    def _get_printer(self, session, template):
        u""" Get printer preset for a given operator/template.

        :param BofhdSession session: The current session/operator
        :param dict template: The selected template

        :return str,None:
            Returns the printer name, or None if no printer is found.
        """
        return None

    def _can_set_spool_user(self, session, template):
        u""" Check if spool user can be set for a given operator/template.

        :param BofhdSession session: The current session/operator
        :param dict template: The selected template

        :return bool: True if spool user can be set, else False"""
        return False

    def _get_mappings(self, account, password, template):
        raise NotImplementedError

    def _make_password_document(self, tpl, tpl_config, account, password):
        """ Make the password document to print.

        :param str tpl:
            template-config.
        :param Cerebrum.Account account:
            The account to generate a password document for.
        :param str password:
            The new password for the account.
        :param dict tpl:
            The template to use (output from __list_password_print_options).

        :return str: The full path to the generated document.

        """
        self.logger.debug("make_password_document: Selected template %r", tpl)

        # TODO: We should use a <prefix>/var/cache/ or <prefix>/tmp/ dir for
        # this, NOT a logging dir. Also, we should consider the read access to
        # these files.
        tmp_dir = tempfile.mkdtemp(dir=cereconf.JOB_RUNNER_LOG_DIR,
                                   prefix="bofh_spool_{}".format(time.time()))
        self.logger.debug(
            "make_password_document: temp dir=%r template=%r",
            tmp_dir, tpl['file'])

        mappings = self._get_mappings(account, password, tpl)

        # Barcode
        if tpl['type'] == 'letter':
            barcode_file_path = os.path.join(tmp_dir, mappings['barcode_file'])
            renderers.render_barcode(
                tpl_config, account.entity_id, barcode_file_path
            )

        lang = tpl.get('lang')
        static_files = tpl.get('static_files', [])
        pdf_abspath = os.path.join(
            tmp_dir, 'output_{}.pdf'.format(account.entity_id)
        )
        pdf_file = renderers.html_template_to_pdf(
            tpl_config, tmp_dir, tpl['file'], mappings,
            lang, static_files, pdf_abspath
        )
        return pdf_file

    @staticmethod
    def _confirm_msg(account, destination, tpl, print_user):
        u""" Make a confirmation message for the user. """
        return "OK: {} for {} spooled @ {} for {}".format(
            tpl.get('file'),
            account.account_name,
            destination,
            print_user.account_name)

    @classmethod
    def get_help_strings(cls):
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
                  "numbers. Ranges can be written as '3-15'.")],
            'print_enter_print_user':
                ['print_user', 'Enter username',
                 "Enter the username to spool the print job for."]
        }

        return group_help, command_help, arg_help

    def misc_print_passwords_prompt_func(self, session, *args):
        u""" Validate and prompt for 'misc print_passwords' arguments.

        :param BofhdSession session: The current session

        :return dict,None:
            A dict with prompt-data, or None if all arguments are fetched.

        """
        all_args = list(args[:])
        template_config = tmpl_config.get_config()
        # Ask for template argument
        if not all_args:
            mapping = [(("Alternatives",), None)]
            n = 1
            for t in template_config['print_password_templates']:
                mapping.append(((t.get('desc'),), n))
                n += 1
            return {'prompt': "Choose template #",
                    'map': mapping,
                    'help_ref': 'print_select_template'}
        tpl = self.__get_template(all_args.pop(0), template_config)

        # Ask for printer argument
        if not self._get_printer(session, tpl):
            if not all_args:
                ret = {'prompt': 'Enter printer name'}
                if self._get_default_printer(session):
                    ret['default'] = self._get_default_printer(session)
                return ret
            printer = all_args.pop(0)
            self._set_default_printer(session, printer)

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
                    'map': mapping,
                    'raw': True,
                    'help_ref': 'print_select_range',
                    'default': str(n - 1)}
        all_args.pop(0)

        # Ask for print user
        if self._can_set_spool_user(session, tpl):
            if not all_args:
                operator = self._get_account(session.get_entity_id(),
                                             idtype='id')
                return {'prompt': 'Queue print job as user',
                        'default': operator.account_name,
                        'help_ref': 'print_enter_print_user',
                        'last_arg': True}
            all_args.pop(0)

        # Done
        if len(all_args) == 0:
            return {'last_arg': True, }
        raise CerebrumError("Too many arguments: %r" % all_args)

    #
    # misc print_passwords [template [printer] [range] [print_user]]
    #
    # TODO: Should the access to this command be restricted?
    #
    all_commands['misc_print_passwords'] = Command(
        ("misc", "print_passwords"),
        prompt_func=misc_print_passwords_prompt_func)

    def misc_print_passwords(self, operator, *args):
        u""" Print password sheets or letters.

        :param BofhdSession operator: The current session.

        :return str: Listings of the successful print jobs.

        """
        args = list(args[:])
        template_config = tmpl_config.get_config()
        template = self.__get_template(args.pop(0), template_config)
        destination = self._get_printer(operator, template)
        if not destination:
            destination = args.pop(0)
        if not destination or re.search(r'[^-_A-Za-z0-9]', destination):
            raise CerebrumError("Bad printer name %r" % destination)

        passwds = self.__select_cached_passwords(operator, args.pop(0))

        if not args:
            print_user = self._get_account(
                operator.get_entity_id(), idtype='id')
        else:
            print_user = self._get_account(args.pop(0), idtype="name")

        printer = LinePrinter(
            destination,
            uname=print_user.account_name)

        documents = []
        ret = []
        for pwd in passwds:
            account = self._get_account(pwd['username'])
            documents.append(
                self._make_password_document(
                    template,
                    template_config,
                    account,
                    pwd['password']))
            ret.append(
                self._confirm_msg(
                    account, destination, template, print_user))
        printer.spool(*documents)

        return "\n".join(ret)

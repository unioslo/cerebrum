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
u""" Password letter utils.

Configuration
-------------

The following `cereconf' values are used in this module:

BOFHD_TEMPLATES
    A dictionary that lists available letters for each language.

    - The language format is: '<language>/<"letter" or "printer">
    - Each letter is a tuple consisting of (<name>, <format (tex or ps)>,
      <description>)

    Example:
      BOFHD_TEMPLATES = {
        'no_NO/letter': [
            ('password_letter_personal', 'tex',
             'Password letter in Norwegian for personal accounts'),
            ('password_letter_nonpersonal', 'ps',
             'Password letter in Norwegian for non-personal accounts'), ], }

JOB_RUNNER_LOG_DIR
    A directory for temporary files. This is where we'll keep the generated
    files from our templates.

"""
from __future__ import with_statement
import os

import cerebrum_path
import cereconf

from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum.modules.templates.letters import TemplateHandler


def get_logger():
    u"""Fetch logger when needed."""
    return Utils.Factory.get_logger(u'cronjob')


def list_password_print_options():
    u""" Enumerated list of password print selections.

    This can be used in prompt functions to select a valid template, and to
    supply template info to e.g. make_password_letter

    """
    templates = getattr(cereconf, 'BOFHD_TEMPLATES', dict())
    options = list()
    for k, v in templates.iteritems():
        for tpl in v:
            options.append({
                'lang': k,     # e.g. en_GB/printer
                'type': tpl[0],  # e.g. nytt_passord_nn
                'fmt': tpl[1],   # e.g. tex, ps
                'desc': tpl[2]   # e.g. Passordbrev til lokal skriver
            })
    return options


def make_password_letter(account, password, tpl):
    u""" Make a password letter to print.

    :param Cerberum.Account account: The account to make a letter for
    :param str password: The new password for this account
    :param dict tpl: The template to use (see list_password_print_options)

    :return str: Returns the path to the output file.

    """
    # TODO: Should this method be split into different functions for each
    # template type?
    const = Utils.Factory.get('Constants')(account._db)  # Share transaction
    logger = get_logger()

    logger.debug("make_password_letter: Selected template %r", tpl)
    th = TemplateHandler(tpl.get('lang'), tpl.get('type'), tpl.get('fmt'))

    # TODO: We should use a <prefix>/var/cache/ or <prefix>/tmp/ dir for this,
    # NOT a logging dir. Also, we should consider the read access to these
    # files.
    tmp_dir = Utils.make_temp_dir(dir=cereconf.JOB_RUNNER_LOG_DIR,
                                  prefix="bofh_spool")
    tmp_f = os.path.extsep.join([tpl.get('type'), tpl.get('fmt')])
    bar_f = os.path.extsep.join(['barcode_%s' % account.account_name, 'eps'])
    logger.debug("make_password_letter: temp dir=%r, file=%r", tmp_dir, tmp_f)
    output_file = os.path.join(tmp_dir, tmp_f)

    mapping = {'uname': account.account_name,
               'password': password,
               'account_id': account.entity_id,
               'lopenr': ''}

    # Add account owner info to mappings
    if account.owner_type == const.entity_group:
        group = Utils.Factory.get('Group')(account._db)
        group.find(account.owner_id)
        mapping['group'] = group.group_name
    elif account.owner_type == const.entity_person:
        person = Utils.Factory.get('Person')(account._db)
        person.find(account.owner_id)
        mapping['fullname'] = person.get_name(const.system_cached,
                                              const.name_full)
    else:
        raise Errors.CerebrumError("Unsupported account owner type %s" %
                                   account.owner_type)

    # Extra info for password letters.
    #
    # TODO: Too much business logic is tied up to the template 'language'
    if tpl.get('lang', '').endswith('letter'):
        if account.owner_type != const.entity_person:
            raise Errors.CerebrumError(
                "Cannot make letter to non-personal account %s (owner type=%s id=%s)" % (
                    account.account_name,
                    account.owner_type,
                    account.owner_id))

        # Barcode
        mapping['barcode'] = os.path.join(tmp_dir, bar_f)
        logger.debug("make_password_letter: making barcode %r",
                     mapping['barcode'])
        try:
            th.make_barcode(mapping['account_id'], mapping['barcode'])
        except IOError, msg:
            logger.error("make_password_letter: unable to make barcode (%s)",
                         msg)
            raise Errors.CerebrumError(msg)

        # Address
        address = None
        for source, kind in (
                (const.system_sap, const.address_post),
                (const.system_fs, const.address_post),
                (const.system_sap, const.address_post_private),
                (const.system_fs, const.address_post_private)):
            address = person.get_entity_address(source=source, type=kind)
            if address:
                break
        if not address:
            raise Errors.CerebrumError(
                "Couldn't get authoritative address for %s" %
                account.account_name)
        address = address[0]
        alines = address['address_text'].split("\n")+[""]
        mapping['address_line1'] = mapping['fullname']
        if alines:
            mapping['address_line2'] = alines[0]
            mapping['address_line3'] = alines[1]
        else:
            mapping['address_line2'] = ""
            mapping['address_line3'] = ""
        mapping['zip'] = address['postal_number']
        mapping['city'] = address['city']
        mapping['country'] = address['country']
        mapping['birthdate'] = person.birth_date.strftime('%Y-%m-%d')

    # Write template file
    with file(output_file, 'w') as f:
        if th._hdr is not None:
            f.write(th._hdr)
        f.write(th.apply_template('body', mapping, no_quote=('barcode',)))
        if th._footer is not None:
            f.write(th._footer)

    return output_file


if __name__ == '__main__':
    del cerebrum_path

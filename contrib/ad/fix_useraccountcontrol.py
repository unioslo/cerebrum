#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014-2025 University of Oslo, Norway
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
"""
Check and fix UAC for user objects under a given OU.

If users change their passwords in Active Directory (AD), they will expect that
change to be reflected in other systems - which they aren't.  These password
changes may even be overwritten by passwords from Cerebrum!

Because of this, we will usually want User Account Control (UAC) settings to
prevent users from changing their password in AD.  This script goes through all
user accounts in a given OU, and changes UAC settings to:

- UserCannotChangePassword: $true
- PasswordNeverExpires: $true

if they are set to different values.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import logging
import textwrap

import adconf
from Cerebrum.Utils import Factory
from Cerebrum.logutils import autoconf as log_autoconf
from Cerebrum.logutils import options as log_options
from Cerebrum.modules.ad2 import ADUtils
from Cerebrum.modules.ad2 import cli
from Cerebrum.modules.ad2.ADSync import BaseSync
from Cerebrum.modules.ad2.winrm import PowershellException

logger = logging.getLogger(__name__)


class UserAccountControlFix(BaseSync):
    """
    Class for fetching and fixing UserAccountControl settings
    """
    default_ad_object_class = 'user'

    def fix_useraccountcontrol(self):
        """ Sync UAC settings for all user accounts. """
        logger.info("Start UserAccountControl sync")
        logger.debug("Fetching data from AD...")
        ad_cmdid = self.start_fetch_ad_data()
        logger.debug("Processing data from AD...")
        self.process_ad_data(ad_cmdid)
        logger.info("UserAccountControl sync done")
        # TODO: not sure if this is the place to put this, but we must close
        # down connections on the server side:
        self.server.close()

    def start_fetch_ad_data(self, object_class=None, attributes=None):
        """ Send request(s) to AD to start generating the data we need.  """
        attributes = attributes or {}
        if not object_class:
            object_class = self.ad_object_class
        attrs = {
            'CannotChangePassword': None,
            'PasswordNeverExpires': None,
        }
        logger.debug("Fetching %d attributes: %s",
                     len(attrs), ", ".join(sorted(attrs)))

        # Some attributes are readonly, so they shouldn't be put in the list,
        # but we still need to receive them if they are used, like the SID.
        return self.server.start_list_objects(
            ou=self.config['search_ou'],
            attributes=attrs,
            object_class=object_class,
        )

    def process_ad_data(self, commandid):
        """
        Start processing the data from AD.

        Each object from AD is sent through :meth:`.process_ad_object` for
        further processing.

        :param tuple commandid:
            The CommandId for the command that has been executed on the server
            to generate a list of objects.

        :raises PowershellException:
            For instance OUUnknownException if the given OU to search in does
            not exist.
        """
        i = 0
        for ad_object in self.server.get_list_objects(commandid):
            if i == 0:
                self.logger.debug2("Retrieved %d attributes: %s",
                                   len(ad_object),
                                   ', '.join(sorted(ad_object.keys())))
            try:
                self.process_ad_object(ad_object)
            except ADUtils.NoAccessException as e:
                # Access errors could be given to the AD administrators, as
                # Cerebrum are not allowed to fix such issues.
                self.add_admin_message('warning',
                                       'Missing access rights for %s: %s' % (
                                            ad_object['DistinguishedName'], e))
                # TODO: do we need to strip out data from the exceptions? Could
                # it for instance contain passwords?
            except PowershellException as e:
                self.logger.warning("PowershellException for %s: %s",
                                    ad_object['DistinguishedName'], e)
            else:
                i += 1
        logger.info("Received and processed %d objects from AD", i)
        return i

    def process_ad_object(self, ad_object):
        """
        Ensure UserAccountControl settings are set correctly for an AD-object.

        :param dict ad_object:
            A dict with information about the AD object from AD.  The dict
            contains mostly the object's attributes.

        :returns bool:
            True if the AD object is processed and can be processed further.
            False is returned if it should not be processed further either
            because it is in a OU we shouldn't touch, or doesn't exist in
            Cerebrum. Subclasses might still want to process the object in some
            way, but for most cases this is the regular situations where the
            object should not be processed further.

        """
        name = ad_object['Name']
        dn = ad_object['DistinguishedName']

        # Don't touch others than from the subset, if set:
        if self.config.get('subset'):
            # Convert names to comply with 'name_format':
            subset_names = (self._format_name(s)
                            for s in self.config['subset'])
            if name not in subset_names:
                return False

        # Don't touch those in OUs we should ignore:
        if any(dn.endswith(ou) for ou in self.config.get('ignore_ou', ())):
            self.logger.debug('Object in ignore_ou: %s', dn)
            return False

        # Compare attributes:
        changes = self.get_mismatch_attributes(ad_object)
        if changes:
            parameters = {'Identity': dn}
            parameters.update(changes)
            cmd = self.server._generate_ad_command('Set-ADUser', parameters)
            logger.info("Updating UserAccessControl settings for %s", dn)
            if not self.config.get('dryrun'):
                return self.server.run(cmd)
        return True

    def get_mismatch_attributes(self, ad_object):
        """
        Check if relevant UserAccountControl settings are set as expected.

        :param dict ad_object:
            The given attributes from AD for the target object.

        :returns dict:
            A mapping of attributes and values that needs to be set.
        """
        ret = {}
        if not ad_object['PasswordNeverExpires']:
            ret['PasswordNeverExpires'] = True
        if not ad_object['CannotChangePassword']:
            ret['CannotChangePassword'] = True
        return ret


def main(argv=None):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            """ Sync UAC settings for all user accounts. """
        ).lstrip(),
    )
    debug_group = parser.add_argument_group(
        "Debug and development",
        "Various options for debugging in a dev environment. ",
    )
    debug_group.add_argument(
        "-d", "--dryrun",
        action="store_true",
        help="Do not write any changes to AD",
    )

    # Add basic winrm/powershell options
    get_preset = cli.add_sync_subparser(parser)
    log_options.install_subparser(parser)

    args = parser.parse_args(argv)
    log_autoconf("tee", args)

    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    #
    # Validate arguments and build configuration
    #
    configuration = get_preset(adconf.SYNCS, args, dryrun=args.dryrun)
    logger.info("Sync dryrun: %s", repr(configuration.get("dryrun", False)))

    #
    # Start sync
    #
    db = Factory.get('Database')()
    db.cl_init(change_program="ad_sync")
    sync = UserAccountControlFix(db=db, logger=logger.getChild('sync'))
    sync.configure(configuration)

    try:
        sync.fix_useraccountcontrol()
    finally:
        try:
            sync.server.close()
        except Exception:
            # It's probably already closed
            pass
    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()

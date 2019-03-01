#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014 University of Oslo, Norway
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
"""Check user objects under a given OU and make sure they all have
UserCannotChangePassword and PasswordNeverExpires set to True.
Fix if necessary.

"""

import getopt
import sys

import adconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules.ad2 import ADUtils
from Cerebrum.modules.ad2.winrm import PowershellException
from Cerebrum.modules.ad2.ADSync import BaseSync

logger = Factory.get_logger('cronjob')
db = Factory.get('Database')(client_encoding='UTF-8')


class UserAccountControlFix(BaseSync):
    """Class for extraction and fixing of UserAccountControl settings
    of the existing user object in AD.

    """

    default_ad_object_class = 'user'

    def __init__(self, db, logger):
        """Initialize the sync.

        """
        super(UserAccountControlFix, self).__init__(db, logger)

    def fix_useraccountcontrol(self):
        """Do the fixing by checking relevant parameters in AD and then 
        updating AD.


        """
        self.logger.info("Fixing of UserAccountControl started")
        ad_cmdid = self.start_fetch_ad_data()
        self.logger.debug("Process AD data...")
        self.process_ad_data(ad_cmdid)
        self.logger.info('Fixing done')
        # TODO: not sure if this is the place to put this, but we must close
        # down connections on the server side:
        self.server.close()

    def start_fetch_ad_data(self, object_class=None, attributes=dict()):
        """Send request(s) to AD to start generating the data we need.

        """
        if not object_class:
            object_class = self.ad_object_class
        attrs = {'CannotChangePassword': None, 'PasswordNeverExpires': None} 
        self.logger.debug2("Try to fetch %d attributes: %s", len(attrs),
                           ', '.join(sorted(attrs)))
        # Some attributes are readonly, so they shouldn't be put in the list,
        # but we still need to receive them if they are used, like the SID.
        return self.server.start_list_objects(ou = self.config['search_ou'],
                                              attributes = attrs,
                                              object_class = object_class)

    def process_ad_data(self, commandid):
        """Start processing the data from AD. Each object from AD is sent
        through L{process_ad_object} for further processing.

        @type commandid: tuple
        @param commandid: The CommandId for the command that has been executed
            on the server to generate a list of objects.

        @raise PowershellException: For instance OUUnknownException if the given
            OU to search in does not exist.

        """
        i = 0
        for ad_object in self.server.get_list_objects(commandid):
            if i == 0:
                self.logger.debug2("Retrieved %d attributes: %s",
                                   len(ad_object), 
                                   ', '.join(sorted(ad_object.keys())))
            try:
                self.process_ad_object(ad_object)
            except ADUtils.NoAccessException, e:
                # Access errors could be given to the AD administrators, as
                # Cerebrum are not allowed to fix such issues.
                self.add_admin_message('warning',
                                       'Missing access rights for %s: %s' % (
                                       ad_object['DistinguishedName'], e))
                # TODO: do we need to strip out data from the exceptions? Could
                # it for instance contain passwords?
            except PowershellException, e:
                self.logger.warn("PowershellException for %s: %s" %
                                 (ad_object['DistinguishedName'], e))
            else:
                i += 1
        self.logger.debug("Received and processed %d objects from AD" % i)
        return i

    def process_ad_object(self, ad_object):
        """Check UserAccountControl setting of an AD-object and update AD 
        if necessary.

        @type ad_object: dict
        @param ad_object: A dict with information about the AD object from AD.
            The dict contains mostly the object's attributes.

        @rtype bool:
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
            subset_names = (self._format_name(s) for s in self.config['subset'])
            if name not in subset_names:
                #self.logger.debug("Ignoring due to subset: %s", name)
                return False

        # Don't touch those in OUs we should ignore:
        if any(dn.endswith(ou) for ou in self.config.get('ignore_ou', ())):
            self.logger.debug('Object in ignore_ou: %s' % dn)
            return False

        # Compare attributes:
        changes = self.get_mismatch_attributes(ad_object)
        if changes:
            parameters = {'Identity': dn}
            parameters.update(changes)
            cmd = self.server._generate_ad_command('Set-ADUser', parameters)
            self.logger.debug("Updating UserAccessControl settings for %s" % dn)
            if not self.config.get('dryrun'):
                return self.server.run(cmd)
        return True

    def get_mismatch_attributes(self, ad_object):
        """Check if relevan UserAccountControl settings are set to True.

        :type ad_object: dict
        :param ad_object:
            The given attributes from AD for the target object.

        :rtype: dict
        :return:
            The list of attributes that are set to False and should be set to
            True. The key is the name of the attribute, and the value is True.

        """
        ret = {}
        if ad_object['PasswordNeverExpires'] == False:
            ret['PasswordNeverExpires'] = True
        if ad_object['CannotChangePassword'] == False:
            ret['CannotChangePassword'] = True 
        return ret

def usage(exitcode=0):
    print """Usage: fix_useraccountcontrol.py [OPTIONS] --type TYPE

    %(doc)s

    Sync options:

    --type TYPE     Configuration of what type of AD-sync has to be used. The
                    sync has to be defined in the config file.

    -d, --dryrun    Do not write changes back to AD, but log them. Usable for
                    testing. Note that the sync is still reading data from AD.

    --logger-level LEVEL What log level should it start logging. This is handled
                         by Cerebrum's logger. Default: DEBUG.

    --logger-name NAME   The name of the log. Default: ad_sync. Could be
                         specified to separate different syncs, e.g. one for
                         users and one for groups. The behaviour is handled by
                         Cerebrum's logger.

                         Note that the logname must be defined in logging.ini.

    -h, --help      Show this and quit.

    """ % {'doc': __doc__}

    sys.exit(exitcode)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   "hd",
                                   ["help",
                                    "dryrun",
                                    "type="])
    except getopt.GetoptError, e:
        print e
        usage(1)

    encrypted = True
    sync_type = None
    sync_classes = []

    # The configuration for the sync
    configuration = dict()

    for opt, val in opts:
        # General options
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('-d', '--dryrun'):
            configuration['dryrun'] = True
        elif opt == '--type':
            if val not in adconf.SYNCS:
                print "Sync type '%s' not found in config" % val
                print "Defined sync types:"
                for typ in adconf.SYNCS:
                    print '  %s' % typ
                sys.exit(2)
            sync_type = configuration['sync_type'] = val
        else:
            print "Unknown option: %s" % opt
            usage(1)

    if not sync_type:
        print "Need to specify what sync type to perform"
        usage(1)

    # Make use of config file settings, if not set otherwise by arguments
    for key, value in adconf.SYNCS[sync_type].iteritems():
        if not configuration.has_key(key):
            configuration[key] = value

    sync_class = type("_dynamic", (UserAccountControlFix, ), {})
    sync = sync_class(db=db, logger=logger)
    sync.configure(configuration)
    
    try:
        sync.fix_useraccountcontrol()
    finally:
        try:
            sync.server.close()
        except Exception:
            # It's probably already closed
            pass

if __name__ == '__main__':
    main()

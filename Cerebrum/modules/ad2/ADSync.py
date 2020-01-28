#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011-2017 University of Oslo, Norway
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

"""Generic module for basic synchronisation with Active Directory.

A synchronisation script must create an instance of such a sync class from this
file, or an instance' subclass. It should then feed it with configuration
variables before the synchronisation should start. Example::

  sync = BaseSync.get_class(sync_type)(db, logger)
  sync.configure(config_args)
  sync.fullsync() # or: sync.quicksync(change_key)

Subclasses should be made when:

- Active Directory for the instance has extra functionality which requires more
  than just new attributes. Examples: Exchange, home directories and maybe
  Lync.

- An instance has special needs which the base sync is not flexible enough to
  support.

The classes should be designed so that they're easy to subclass and change most
of its behaviour.

Some terms:

- entity is an account/group/OU or anything else in Cerebrum - this corresponds
  to an object in AD.

- Entities in quarantine are often referred to as deactivated. In AD is this
  called disabled.

"""

import time
import uuid

import adconf

from Cerebrum import Entity, Errors
from Cerebrum.modules import CLHandler, Email
from Cerebrum.modules.EntityTrait import EntityTrait
from Cerebrum.Utils import unicode2str, Factory, dyn_import, NotSet
from Cerebrum.utils import json
from Cerebrum.utils.email import sendmail

from Cerebrum.modules.ad2 import ADUtils, ConfigUtils
from Cerebrum.modules.ad2.CerebrumData import CerebrumEntity
from Cerebrum.modules.ad2.ConfigUtils import ConfigError
from Cerebrum.modules.ad2.winrm import CommandTooLongException
from Cerebrum.modules.ad2.winrm import PowershellException
from Cerebrum.modules.gpg.data import GpgData
from Cerebrum.QuarantineHandler import QuarantineHandler


class BaseSync(object):

    """Class for the generic AD synchronisation functionality.

    All the AD-synchronisation classes should subclass this one.

    The sync's behaviour:

    1. Configuration:
        - All config is set - subclasses could add more settings.
        - The config is checked - subclasses could override this.
    2. At fullsync:
        - AD is asked to start generating a list of objects
        - Data from Cerebrum gets cached:
            - All entities in Cerebrum to sync is listed. Each entity is
              represented as an instance of L{CerebrumEntity}.
            - Quarantined entities gets marked as deactive.
            - Attributes as stored in Cerebrum.
            - Subclasses could cache more.
        - Each entity's AD-attributes get calculated.
        - Process each object retrieved from AD:
            - Gets ignored if in an OU we should not touch.
            - Gets removed/disabled in AD if no entity match the object.
            - If not active in Cerebrum, disable/move object in AD, according
              to what the config says.
            - Gets moved to correct OU if put somewhere else, but only if
              config says so.
            - Attributes gets compared. Those in AD not equal to Cerebrum gets
              updated.
            - Subclasses could add more functionality.
        - Remaining entities that was not found in AD gets created in AD.
    3. At quicksync:
        - Get all unhandled events from the ChangeLog
        - Process each unhandled event
        - If successfully processed, mark the event as handled

    Subclasses could of course make changes to this behaviour.

    """

    # What class to make an instance of for talking with the AD server:
    server_class = ADUtils.ADclient

    # List of messages that should be given to the administrators of the AD
    # domain. Such messages are errors that could not be fixed by Cerebrum's
    # sysadmins, unless they have admin privileges in the AD domain.
    _ad_admin_messages = []

    # The required settings. If any of these settings does not exist in the
    # config for the given AD-sync, an error will be triggered. Note that
    # subclasses must define their own list for their own settings.
    settings_required = ('sync_type', 'domain', 'server', 'target_ou',
                         'search_ou', 'object_classes')

    # Settings with default values. If any of these settings are not defined in
    # the config for the given AD-sync, they will instead get their default
    # value. Note that subclasses must define their own list for their own
    # values.
    settings_with_default = (('dryrun', False),
                             ('mock', False),
                             ('encrypted', True),
                             ('auth_user', 'cereauth'),
                             ('domain_admin', 'cerebrum_sync'),
                             ('move_objects', False),
                             ('subset', None),
                             ('ad_admin_message', ()),
                             ('name_format', '%s'),
                             ('ignore_ou', ()),
                             ('create_ous', False),
                             ('attributes', {}),
                             ('useraccountcontrol', {}),
                             ('store_sid', False),
                             ('handle_unknown_objects', ('ignore', None)),
                             ('handle_deactivated_objects', ('ignore', None)),
                             ('gpg_recipient_id', None),
                             ('language', ('nb', 'nn', 'en')),
                             ('changes_too_old_seconds', 60*60*24*365),
                             ('group_type', 'security'),
                             ('group_scope', 'global'),
                             ('ou_mappings', []),
                             ('script', {}),
                             )

    # A mapping from the entity_type to the correct externalid_type. Note that
    # the mapping gets converted to CerebrumConstants at startup.
    sidtype_map = {'account': 'AD_ACCSID',
                   'group':   'AD_GRPSID'}

    def __init__(self, db, logger):
        """Initialize the sync.

        A superclass is connecting to the given AD agent. TODO: or should we
        only use ADclient directly in this class instead? Depends on how
        complicated things are getting.

        :type db: Cerebrum.CLDatabase.CLDatabase
        :type logger: Cerebrum.logutils.loggers.CerebrumLogger
        """
        super(BaseSync, self).__init__()

        self.db = db
        self.logger = logger
        self.co = Factory.get("Constants")(self.db)
        self.clconst = Factory.get("CLConstants")(self.db)
        self.ent = Factory.get('Entity')(self.db)
        self._ent_extid = Entity.EntityExternalId(self.db)
        self._entity_trait = EntityTrait(self.db)

        # Where the sync configuration should go:
        self.config = dict()
        # Where the entities to work on should go. Keys should be entity_names:
        self.entities = dict()
        # Where entity_ids of entities currently exempt from a sync should go.
        self.exempt_entities = list()
        # A mapping from entity_id to the entities.
        self.id2entity = dict()
        # A mapping from AD-id to the entities. AD-id is per default
        # SamAccountName, but could be set otherwise in the config.
        self.adid2entity = dict()

    @classmethod
    def get_class(cls, sync_type='', classes=None):
        """Build a synchronisation class out of given class names.

        This works like Factory.get() but you could specify the list of class
        names yourself. The point of this is to be able to dynamically create a
        synchronisation class with the features that is needed without having
        to hardcode it.

        All the given class names gets imported before a new class is created
        out of them. Note that this class is automatically inherited in the
        list.

        Note that the order of the classes are important if they are related to
        each others by subclassing. You can not list class A before subclasses
        of the class A, as that would mean the subclass won't override any of
        A's methods. The method would then raise an exception.

        @type sync_type: string
        @param sync_type:
            The name of a AD-sync type which should be defined in the AD
            configuration. If given, the classes defined for the given type
            will be used for setting up the sync class. This parameter gets
            ignored if L{classes} is set.

        @type classes: list or tuple
        @param classes:
            The names of all the classes that should be used in the sync class.
            If this is specified, the L{sync_type} parameter gets ignored.
            Example on classes:

            - Cerebrum.modules.ad2.ADSync/UserSync
            - Cerebrum.modules.no.uio.ADSync/UiOUserSync

        """
        assert classes or sync_type, "Either sync_type or classes needed"
        if not classes:
            if sync_type not in adconf.SYNCS:
                raise Exception('Undefined AD-sync type: %s' % sync_type)
            conf = adconf.SYNCS[sync_type]
            classes = conf.get('sync_classes')
            if not classes:
                raise Exception('No sync class defined for sync type %s' %
                                sync_type)
        return cls._generate_dynamic_class(classes,
                                           '_dynamic_adsync_%s' % sync_type)

    def _format_name(self, name_to_format):
        """Adjust the name of the object according to the sync's configuration.
        The type of adjustment is defined by the type of 'name_format'
        configuration parameter.

        @type name_to_format: string
        @param name_to_format: the name of the object. It can be either
            just adjusted according to some string formatting, or become
            an input parameter to a function, that performs more complex
            transformation.

        """

        nformat = self.config.get('name_format', '%s')
        if callable(nformat):
            # There is a transformation function defined in the config
            return nformat(name_to_format)
        else:
            # This is a string formatting in the configuration
            return nformat % name_to_format

    def configure(self, config_args):
        """Read configuration options from given arguments and config file.

        The configuration is for how the ADsync should behave and work. Could
        be subclassed to support more settings for subclass functionality.

        Defined basic configuration settings:

        - target_spread: Either a Spread constant or a list of Spread
          constants. Used to find what entities from Cerebrum to sync with AD.

        - root_ou (string): The root OU that should be searched for objects in
          AD.

        - target_ou (string): What OU in AD that should be set as the default
          OU for the objects.

        - handle_unknown_objects: What to do with objects that are not found in
          Cerebrum. Could either be missing spread, that they're deleted, or if
          they have never existed in Cerebrum. Entities in quarantine but with
          the correct target_spread are not affected by this.
          Values:
            ('disable', None)   # Deactivate object. This is the default.
            ('move', OU)        # Deactivate object and move to a given OU.
            ('delete', None)    # Delete the object. Can't be restored.
            ('ignore', None)    # Do not do anything with these objects.

        - move_objects (bool): If objects in the wrong OU should be moved to
          the target_ou, or being left where it is. Other attributes are still
          updated for the object. Defaults to False.

        - attributes: The attributes to sync. Must be a dict with the name of
          the attributes as keys and the values is further config for the given
          attribute. The configuration is different per attribute.

        @type config_args: dict
        @param config_args:
            Configuration data that should be set. Overrides any settings that
            is found from config file (adconf). Unknown keys in the dict is not
            warned about, as it could be targeted at subclass configuration.

        """
        # Required settings. Will fail if not defined in the config:
        for key in self.settings_required:
            try:
                self.config[key] = config_args[key]
            except KeyError:
                raise Exception('Missing required config variable: %s' % key)
        # Settings which have default values if not set:
        for key, default in self.settings_with_default:
            self.config[key] = config_args.get(key, default)

        # Set what object class type in AD to use, either the config or what is
        # set in any of the subclasses of the ADSync. Most subclasses should
        # set a default object class.
        self.ad_object_class = config_args.get('ad_object_class',
                                               self.default_ad_object_class)

        # The object class is generated dynamically, depending on the given
        # list of classes:
        self.logger.debug2("Using object classes: %s",
                           ', '.join(config_args['object_classes']))
        self._object_class = self._generate_dynamic_class(
            config_args['object_classes'],
            '_dynamic_adobject_%s' % self.config['sync_type'])
        if not issubclass(self._object_class, CerebrumEntity):
            raise ConfigError(
                'Given object_classes not subclass of %s' % CerebrumEntity)

        # Calculate target spread and target entity_type, depending on what
        # settings that exists:
        if config_args.get('target_spread'):
            # Explicitly set target spreads will override the other settings
            spread = self.co.Spread(config_args['target_spread'])
            self.config['target_spread'] = spread
            self.config['target_type'] = spread.entity_type
        else:
            # Otherwise we use the set 'sync_type' for finding the spread:
            spread = self.co.Spread(self.config['sync_type'])
            try:
                int(spread)
            except Errors.NotFoundError:
                if 'target_type' in config_args:
                    self.config['target_type'] = config_args['target_type']
                    self.config['target_spread'] = None
                else:
                    raise ConfigUtils.ConfigError(
                        'Either sync name must be a spread, or target_type '
                        'must be defined')
            else:
                self.config['target_spread'] = spread
                self.config['target_type'] = spread.entity_type

        # Convert the entity_type into the type constant
        self.config['target_type'] = self.co.EntityType(
            self.config['target_type'])

        # Languages are changed into the integer of their constants
        self.config['language'] = tuple(int(self.co.LanguageCode(l)) for l in
                                        self.config['language'])
        # Change-types are changed into their constants
        self.config['change_types'] = tuple(self.clconst.ChangeType(*t) for t in
                                            config_args.get('change_types',
                                                            ()))
        # Set the correct port
        if 'port' in config_args:
            self.config['port'] = config_args['port']
        else:
            self.config['port'] = 5986
            if not self.config['encrypted']:
                self.config['port'] = 5985

        if config_args.get('dc_server'):
            self.config['dc_server'] = config_args['dc_server']

        if self.config['subset']:
            self.logger.info("Sync will only be run for subset: %s",
                             self.config['subset'])
        # Log if in dryrun
        if self.config['dryrun']:
            self.logger.info('In dryrun mode, AD will not be updated')

        if self.config['mock']:
            self.logger.info('In mock mode, AD will not be connected to')
            from Cerebrum.modules.ad2 import ADMock
            self.server_class = ADMock.ADclientMock
            # We'll need to set mock mode for all sync configurations, since
            # the sync will instantiate clients with other configurations, in
            # order to collect necessary AD attributes.
            for key in adconf.SYNCS:
                adconf.SYNCS[key]['mock'] = True

        # Messages for AD-administrators should be logged if the config says
        # so, or if there are no other options set:
        self.config['log_ad_admin_messages'] = False
        if (not self.config['ad_admin_message'] or
                any(o in (None, 'log') for o in
                    self.config['ad_admin_message'])):
            self.config['log_ad_admin_messages'] = True

        if self.config['store_sid']:
            converted = dict((self.co.EntityType(e_type),
                              self.co.EntityExternalId(sid_type))
                             for e_type, sid_type
                             in self.sidtype_map.iteritems())
            self.sidtype_map = converted

        # We define the group scope and type for new groups.
        # This should probably be moved to UiADistGroupSync, and so should the
        # code that touches new_group_scope in the create_object-method (in
        # this class).
        self.new_group_scope = self.config['group_scope'].lower()
        self.new_group_type = self.config['group_type'].lower()

        # Check the config
        self.config_check()

    def config_check(self):
        """Check that the basic configuration is okay."""
        if not isinstance(self.config['ignore_ou'], (tuple, list)):
            raise Exception("ignore_ou must be list/tuple")
        if not self.config['target_ou'].endswith(self.config['search_ou']):
            self.logger.warn('target_ou should be under the search_ou')

        # Check the attributes:

        # Attributes that shouldn't be defined:
        for n in ('dn', 'Dn', 'sn', 'Sn'):
            if n in self.config['attributes']:
                self.logger.warn('Bad attribute defined in config: %s' % n)
        # The admin message config:
        for opt in self.config['ad_admin_message']:
            if opt[0] not in ('mail', 'file', 'log', None):
                self.logger.warn("Unknown option in ad_admin_message: %s", opt)
            if opt[1] not in ('error', 'warning', 'info', 'debug'):
                self.logger.warn("Unknown level in ad_admin_message: %s", opt)
            # some ways
            if opt[0] in ('mail', 'file'):
                if len(opt) <= 2:
                    self.logger.warn("Missing setting in ad_admin_message: %s",
                                     opt)

        # If name_format is string, it should include the '%s' for
        # the entity_name to be put in.
        nformat = self.config.get('name_format', '%s')
        if not callable(nformat) and '%s' not in nformat:
            self.logger.warn("Missing '%s' in name_format, name not included")

        for handl in ('handle_unknown_objects', 'handle_deactivated_objects'):
            var = self.config[handl]
            if var[0] not in ('ignore', 'disable', 'move', 'delete'):
                raise Exception(
                    "Bad configuration of %s - set to: %s" % (handl, var))

        # Check that all the defined change_types exists:
        for change_type in self.config.get('change_types', ()):
            int(change_type)

        # TODO: move the instantiation of the server to somewhere else!
        self.setup_server()

    @staticmethod
    def _generate_dynamic_class(classes, class_name='_dynamic'):
        """Generate a dynamic class out of the given classes.

        This is doing parts of what L{Utils.Factory.get} does, but without the
        dependency of cereconf.

        @type classes: list of str
        @param classes:
            The list of classes that should get combined and turned into a
            dynamic class. The classes are represented by strings, starting
            with the module path, ending with the class name in the module.
            Example:

                Cerebrum.modules.ad2.ADSync/UserSync
                Cerebrum.modules.ad2.ADSync/PosixUserSync

            Note that the order in the list is important. The last element is
            the superclass, and everyone before is subclasses. This also means
            that you if add related classes, subclasses must be added before
            the superclasses.

        @type class_name: str
        @param class_name:
            The name of the new class, e.g. represented by
            L{__main__._dynamic}. Not used if only one class is given, as that
            is then used directly - no need to create a new class that is
            exactly the same as input.

        @rtype: dynamic class
        @return:
            A dynamically generated class.

        """
        bases = []
        for c in classes:
            mod_name, cname = c.split("/", 1)
            mod = dyn_import(mod_name)
            claz = getattr(mod, cname)
            for override in bases:
                if issubclass(claz, override):
                    raise Exception(
                            "Class %r should appear earlier in the list, as "
                            "it's a subclass of class %r." % (claz, override))
            bases.append(claz)
        if len(bases) == 1:
            return bases[0]
        # Dynamically construct the new class that inherits from all the given
        # classes:
        return type(class_name, tuple(bases), {})

    def setup_server(self):
        """Instantiate the server class to use for WinRM."""
        self.server = self.server_class(
            logger=self.logger,
            host=self.config['server'],
            port=self.config.get('port'),
            auth_user=self.config.get('auth_user'),
            domain_admin=self.config.get('domain_admin'),
            domain=self.config.get('domain'),
            encrypted=self.config.get('encrypted', True),
            ca=self.config.get('ca'),
            client_cert=self.config.get('client_cert'),
            client_key=self.config.get('client_key'),
            dryrun=self.config['dryrun'])
        if 'dc_server' in self.config:
            self.server.set_domain_controller(self.config['dc_server'])

    def add_admin_message(self, level, msg):
        """Add a message to be given to the administrators of the AD domain.

        The messages should at the end be given to the administrators according
        to what the confiuration says.

        @type level: string
        # TODO: make use of log constants instead?
        @param level: The level of the given message to log. Used to separate
            out what messages that should be given to the AD-administrators and
            not.

        @type msg: string
        @param msg: The message that should be logged. Must not contain
            sensitive data, like passwords, as it could be sent by mail.

        """
        self.logger.info("AD-message: %s: %s", level, msg)
        self._ad_admin_messages.append((level, msg))
        if self.config['log_ad_admin_messages']:
            func = getattr(self.logger, level)
            func(msg)

    def send_ad_admin_messages(self):
        """Send the messages for the AD-administrators, if any.

        The way the messages should be sent is decided by the configuration.

        """
        if not self._ad_admin_messages:
            self.logger.debug("No AD-admin messages to send")
            return
        self.logger.debug('Found %d AD-admin messages to send',
                          len(self._ad_admin_messages))
        txt = '\n'.join('%s: %s' % (x[0].upper(), unicode2str(x[1])) for x in
                        self._ad_admin_messages)
        for opt in self.config['ad_admin_message']:
            if opt[0] in (None, 'log'):
                # Messages already logged when added.
                pass
            elif opt[0] == 'mail':
                for address in opt[2:]:
                    self.logger.info("Sending %d messages to %s",
                                     len(self._ad_admin_messages), address)
                    try:
                        sendmail(address, 'cerebrum@usit.uio.no',
                                 'AD-sync messages for %s at %s' % (
                                     self.config['sync_type'],
                                     self.config['domain']),
                                 txt, charset='utf-8',
                                 debug=self.config['dryrun'])
                    except Exception as e:
                        self.logger.warn("Error sending AD-messages to %s: %s",
                                         address, e)
            elif opt[0] == 'file':
                self.logger.warn(
                    "Sending AD-admin messages to file not implemented")
                # TODO
            else:
                self.logger.warn("Unknown way to send AD-messages: %s" % opt)
        self._ad_admin_messages = []
        self.logger.debug('Sending AD-admin messages done...')

    def fullsync(self):
        """Do the fullsync by comparing AD with Cerebrum and then update AD.

        In subclasses, you should rather override the methods that this method
        calls instead of overriding all of this method, unless you of course
        want to do the fullsync completely different.

        """
        self.logger.info("Fullsync started")
        self.logger.debug("Pre-sync processing...")
        self.pre_process()
        ad_cmdid = self.start_fetch_ad_data()
        self.logger.debug("Fetching cerebrum data...")
        self.fetch_cerebrum_data()
        self.logger.debug("Calculate AD values...")
        self.calculate_ad_values()
        self.logger.debug("Process AD data...")
        self.process_ad_data(ad_cmdid)
        self.logger.debug("Process entities not in AD...")
        self.process_entities_not_in_ad()
        self.logger.debug("Post-sync processing...")
        self.post_process()
        self.logger.info('Fullsync done')
        self.send_ad_admin_messages()
        # TODO: not sure if this is the place to put this, but we must close
        # down connections on the server side:
        self.server.close()

    def quicksync(self, changekey=None, change_ids=None):
        """Do a quicksync, by sending the latest changes to AD.

        All events of the given change_types are processed generically, and in
        chronologically order.

        Subclasses should rather override the methods that this method calls
        instead of overring all of this method, as that is easier. Unless, of
        course, you want to completely rewrite the behaviour of the quicksync.

        The quicksync is going through L{change_log} for new events that has
        not been marked as commited by the given L{changekey}. The list is
        processed in reverse, so that equal events are only processed once.

        :type changekey: string
        :param changekey:
            The change-log key to mark the events as commited or not. Must be
            unique per job, unless you're in for race conditions and skipped
            events.

        :type change_ids: list or None
        :param change_ids:
            If specified, only the given change ids will be attempted executed.
            The given IDs will be run no matter if they are considered finished
            by the L{CLHandler}.

        """
        self.logger.info("Quicksync started")
        cl = CLHandler.CLHandler(self.db)
        changetypes = self.config['change_types']
        already_handled = set()  # Changes that has been processed

        # Avoid changes that are too old:
        too_old = time.time() - int(self.config['changes_too_old_seconds'])

        # generator to get events from changekey in correct order
        def _events_for_change_key(k, t):
            for e in reversed(cl.get_events(k, t)):
                yield e

        # generator to get events from change_ids in correct order
        def _events_for_change_ids(ids):
            for i in reversed(sorted(ids)):
                rows = self.db.get_log_events(start_id=i, max_id=i)
                try:
                    yield rows.next()
                except StopIteration:
                    self.logger.warn("No change_id %s", i)

        # Re-writeable functions for cl.confirm and cl.commit
        confirm = lambda e: cl.confirm_event(e)
        commit = lambda dryrun: None if dryrun else cl.commit_confirmations()

        if changekey:
            self.logger.debug("Processing changekey: %s", changekey)
            events = _events_for_change_key(changekey, changetypes)
        elif change_ids:
            self.logger.debug("Processing given change_ids: %s", change_ids)
            events = _events_for_change_ids(change_ids)
            # Do not commit to CLHandler -- that won't work if cl is not set up
            # with a changekey
            commit = lambda r: None
            confirm = lambda d: None
        else:
            raise Exception("Missing changekey or change_ids")

        stats = dict(seen=0, processed=0, skipped=0, failed=0)
        for row in events:
            timestamp = int(row['tstamp'])
            handle_key = tuple((int(row['change_type_id']),
                                row['subject_entity'],
                                row['dest_entity']))
            change_type = self.clconst.ChangeType(int(row['change_type_id']))
            stats['seen'] += 1

            # Ignore too old changes:
            if timestamp < too_old:
                stats['skipped'] += 1
                self.logger.info("Skipping too old change_id: %s",
                                 row['change_id'])
                confirm(row)
                continue
            # Ignore seen (change_type, subject, dest) tuples
            if handle_key in already_handled:
                stats['skipped'] += 1
                self.logger.info(
                    "Skipping change_id %s: Already handled change type %s"
                    " for subject=%s, dest=%s", row['change_id'],
                    str(change_type), row['subject_entity'],
                    row['dest_entity'])
                confirm(row)
                continue

            self.logger.debug(
                "Processing change_id %s (%s), from %s subject_entity: %s",
                row['change_id'], change_type, timestamp,
                row['subject_entity'])
            already_handled.add(handle_key)
            try:
                if self.process_cl_event(row):
                    stats['processed'] += 1
                    confirm(row)
                else:
                    stats['skipped'] += 1
                    self.logger.debug(
                        "Unable to process %s for subject=%s dest=%s",
                        change_type, row['subject_entity'], row['dest_entity'])
            except Exception:
                stats['failed'] += 1
                self.logger.error(
                    "Failed to process cl_event %s (%s) for %s",
                    row['change_id'], change_type, row['subject_entity'],
                    exc_info=1)
            else:
                commit(self.config['dryrun'])
        commit(self.config['dryrun'])
        self.logger.info("Handled %(seen)d events, processed: %(processed)d,"
                         " skipped: %(skipped)d, failed: %(failed)d", stats)
        self.logger.info("Quicksync done")
        self.send_ad_admin_messages()

    def process_cl_event(self, row):
        """Process a given ChangeLog event.

        This is normally called by the L{quicksync} method. Log changes that is
        not set in L{adconf.SYNCS[<sync_type>][change_types]} will not be
        called.

        Subclasses should override for handling their own change types. The
        Basesync only handles quite generic change types, and not e.g. account
        specific changes.

        @type row: dict of db-row
        @param row:
            A db-row, as returned from L{changelog.get_events()}. This is the
            row that should be processed.

        @rtype: bool
        @return:
            The result from the handler. Should be True if the sync succeeded
            or there was no need for the change to be synced, i.e. the log
            change could be confirmed. Should only return False if the change
            needs to be redone.

        @raise UnhandledChangeTypeError?
            TODO: Should we have our own exception class that is used if the
            method does not know what to do with a given change type? Could
            then be used by subclasses.

        @raise TODO:
            TODO: What exceptions is expected here?

        """
        # TODO: Add functionality for generic changes here!
        self.logger.warn("Change type not handled: %s",
                         self.clconst.ChangeType(row['change_type_id']))
        # TODO: Or rather raise an UnhandledChangeTypeError?
        return False

    def fetch_cerebrum_data(self):
        """Get basic data from Cerebrum.

        Subclasses could extend this by getting more information from Cerebrum.

        should first populate L{self.entities} with the entities
        data, before calling this method from this superclass. This is because
        this class does not populate the dict, but updates only the existing
        entities with basic data, like quarantines.

        """
        self.fetch_cerebrum_entities()
        self.logger.debug("Fetched %d cerebrum entities" % len(self.entities))
        # Make a mapping from entity_id to the entity:
        self.id2entity = dict((self.entities[e].entity_id, self.entities[e])
                              for e in self.entities)
        # Make a mapping from entity_name to the entity:
        self.name2entity = dict((self.entities[e].entity_name,
                                 self.entities[e]) for e in self.entities)
        # Make a mapping from ad_id to the entity:
        self.adid2entity = dict((self.entities[e].ad_id.lower(),
                                 self.entities[e]) for e in self.entities)
        if len(self.entities) != len(self.adid2entity):
            self.logger.warn("Mismatch in mapping of ad_id -> entity_id")
        self.fetch_quarantines()
        self.fetch_spreads()
        self.fetch_attributes()
        if self.config['store_sid']:
            self.fetch_sids()

    def fetch_cerebrum_entities(self):
        """Get and cache all the entities from Cerebrum.

        This method MUST be created by the subclasses, to get the proper
        entities to synchronize with AD.

        """
        raise Exception('Must be defined in the proper subclass')

    def fetch_quarantines(self):
        """Get all quarantines from Cerebrum and update L{self.entities} with
        this. Called after the entities should have been retrieved from
        Cerebrum, so all in quarantine gets tagged as deactivated.

        """
        self.logger.debug("Fetch quarantines...")

        # Limit the search to the entity_type the target_spread is meant for:
        target_type = self.config['target_type']
        ids = None
        if self.config['subset']:
            ids = self.id2entity.keys()

        quarantined_accounts = QuarantineHandler.get_locked_entities(
            self.db,
            entity_types=target_type,
            entity_ids=ids)

        for entity_id in quarantined_accounts:
            found = self.id2entity.get(entity_id)
            if found:
                found.active = False

        self.logger.debug("Flagged %d entities as deactivated",
                          len(quarantined_accounts))

    def fetch_spreads(self):
        """Get all spreads from Cerebrum and update L{self.entities} with this.

        The spreads _could_ be used for updating various attributes or not
        depending on if an entity should be available in different AD systems,
        e.g. Exchange, Lync and Sharepoint.

        """
        self.logger.debug("Fetch spreads for target type %s...",
                          self.config['target_type'])
        if not self.config['target_type']:
            # Don't know what spreads to fetch if we don't know the entity type
            return
        # TODO: Need to check what spreads we really need - slow to fetch all
        # spreads for an entity type...
        i = 0
        es = Entity.EntitySpread(self.db)
        for row in es.list_entity_spreads(self.config['target_type']):
            ent = self.id2entity.get(int(row['entity_id']))
            if ent:
                ent.spreads.append(row['spread'])
                i += 1
        self.logger.debug("Fetched %d entity spreads", i)

    def fetch_attributes(self):
        """Get all AD attributes stored in Cerebrum and add them to the cached
        entities.

        """
        # Check if data from the attribute table is needed:
        attrtypes = set()
        for c in ConfigUtils.get_config_by_type(self.config['attributes'],
                                                ConfigUtils.ADAttributeAttr):
            attrtypes.update(c.attributes)
        if not attrtypes:
            return
        self.logger.debug("Fetch from attribute table: %s",
                          ', '.join(str(a) for a in attrtypes))
        ids = None
        if self.config['subset']:
            ids = self.id2entity.keys()
            # Handle empty lists:
            if not ids:
                return
        i = 0
        for row in self.ent.list_ad_attributes(
                entity_id=ids,
                spread=self.config['target_spread'],
                attribute=attrtypes):
            e = self.id2entity.get(row['entity_id'], None)
            if e:
                attr = int(row['attr_code'])
                attrcode = self.co.ADAttribute(attr)
                if attrcode.multivalued:
                    e.cere_attributes.setdefault(attr, []).append(row['value'])
                else:
                    e.cere_attributes[attr] = row['value']
                i += 1
        self.logger.debug("Fetched %d AD attributes from Cerebrum" % i)

    def fetch_sids(self):
        """Get all SIDs stored in Cerebrum and add them to the cached entities.

        Security ID, or SID, is the identifier for objects in AD with
        privileges. Privileges could be set for Users, Groups, Computers and
        probably other object types. The SID is readonly, and is automatically
        set when the object is created. At some instances, we want to store the
        SID for security reasons (auditing).

        A SID can not be reused, so when an object is deleted and recreated, it
        gets a new SID, and thus also all its presiously set privileges.

        TODO: how should SID be stored? We should connect it to spreads, as the
        object could have a different SID in the different AD domains, so we
        can't just be able to store one. It looks we have to store it in the
        table with other AD attributes and don't write it back to AD, as it's
        readonly.

        """
        self.logger.debug("Fetch SIDs...")
        en = Entity.EntityExternalId(self.db)
        id_type = self.co.EntityExternalId(
            self.sidtype_map[self.config['target_type']])
        i = 0
        for row in en.search_external_ids(source_system=self.co.system_ad,
                                          id_type=id_type, fetchall=False):
            # TODO: how should we get it per spread?
            e = self.id2entity.get(row['entity_id'], None)
            if e:
                e.sid = row['external_id']
                i += 1
        self.logger.debug("Fetched %d SIDs from Cerebrum" % i)

    def fetch_names(self):
        """Get all the entity names for the entities from Cerebrum.

        """
        self.logger.debug("Fetch name information...")
        variants = set()
        systems = set()
        languages = set()
        all_systems = False
        # Go through config and see what info needs to be fetched:
        for atr in ConfigUtils.get_config_by_type(self.config['attributes'],
                                                  ConfigUtils.NameAttr):
            variants.update(atr.name_variants)
            if atr.source_systems is None:
                all_systems = True
            else:
                systems.update(atr.source_systems)
            if atr.languages:
                languages.update(atr.languages)
        if not variants:
            return
        self.logger.debug("Fetch names of the types: %s", variants)

        if all_systems or not systems:
            # By setting to None we fetch from all source_systems.
            systems = None
        if not languages:
            # By setting to None we fetch all languages:
            languages = None
        ids = None
        if self.config['subset']:
            ids = self.owner2ent.keys()
        i = 0
        for row in self.ent.search_name_with_language(
                name_variant=variants, entity_id=ids,
                entity_type=self.config['entity_type'],
                name_language=languages):
            for ent in self.owner2ent.get(row['entity_id'], ()):
                vari = str(self.co.EntityNameCode(row['name_variant']))
                lang = str(self.co.LanguageCode(row['name_language']))
                ent.entity_name_with_language.setdefault(
                    vari, {})[lang] = row['name']
                i += 1
        self.logger.debug("Found %d names" % i)

    def calculate_ad_values(self):
        """Use Cerebrum data to calculate the needed attributes.

        """
        for ent in self.entities.itervalues():
            ent.calculate_ad_values()

    def cache_entity(self, entity_id, entity_name, *args, **kwargs):
        """Wrapper method for creating a cache object for an entity.

        The object class is created dynamically, depending on the config and
        what subclasses of the sync is in use. This method returns an object
        out of the correct classes.

        You should call this method for new cache objects instead of creating
        it directly, for easier subclassing.

        @type entity_id: int
        @param entity_id: The entity's entity_id

        @type entity_name: str or unicode
        @param entity_name: The entity's name, normally the entity_name.

        @type *args: mixed
        @param *args: More arguments that should be passed on to the object at
            instantiation.

        @type *kwargs: mixed
        @param *kwargs:
            More arguments that should be passed on to the object at
            instantiation.

        @rtype: Cerebrum.modules.ad2.CerebrumData.CerebrumEntity
        @return: A proper instantiated subclass for L{CerebrumEntity}.

        """
        return self._object_class(self.logger, self.config, entity_id,
                                  entity_name, *args, **kwargs)

    def start_fetch_ad_data(self, object_class=None, attributes=dict()):
        """Send request(s) to AD to start generating the data we need.

        Could be subclassed to get more/other data.

        @type object_class: str
        @param object_class:
            What object class to get from AD, e.g. 'user' or 'group'. If not
            set, use what is defined in config or object.

        @type attributes: list
        @param attributes: Extra attributes that should be retrieved from AD.
            The attributes defined in the config is already set.

        @rtype: string
        @return:
            A CommandId that is the servere reference to later get the data
            that has been generated.

        """
        if not object_class:
            object_class = self.ad_object_class
        attrs = self.config['attributes'].copy()
        if attributes:
            attrs.update(attributes)
        self.logger.debug2("Try to fetch %d attributes: %s", len(attrs),
                           ', '.join(sorted(attrs)))
        # Some attributes are readonly, so they shouldn't be put in the list,
        # but we still need to receive them if they are used, like the SID.
        if self.config['store_sid'] and 'SID' not in attrs:
            attrs['SID'] = None
        return self.server.start_list_objects(ou=self.config['search_ou'],
                                              attributes=attrs,
                                              object_class=object_class)

    def process_ad_data(self, commandid):
        """Start processing the data from AD. Each object from AD is sent
        through L{process_ad_object} for further processing.

        :type commandid: tuple
        :param commandid:
            The CommandId for the command that has been executed on the server
            to generate a list of objects.

        :raise PowershellException:
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
                self.add_admin_message(
                    'warning', 'Missing access rights for %s: %s' % (
                        ad_object['DistinguishedName'], e))
                # TODO: do we need to strip out data from the exceptions? Could
                # it for instance contain passwords?
            except PowershellException as e:
                self.logger.warn("PowershellException for %s: %s" %
                                 (ad_object['DistinguishedName'], e))
            else:
                i += 1
        self.logger.debug("Received and processed %d objects from AD" % i)
        return i

    def process_ad_object(self, ad_object):
        """Compare an AD-object with Cerebrum and update AD with differences.

        Basic functionality for what to do with an object, compared to what is
        stored in Cerebrum. Could be subclassed to add more functionality. This
        command is called both when updating existing objects, but also if an
        entity didn't exist in AD and just got created.

        :type ad_object: dict
        :param ad_object:
            A dict with information about the AD object from AD.  The dict
            contains mostly the object's attributes.

        :rtype bool:
            True if the AD object is processed and can be processed further.
            False is returned if it should not be processed further either
            because it is in a OU we shouldn't touch, or doesn't exist in
            Cerebrum. Subclasses might still want to process the object in some
            way, but for most cases this is the regular situations where the
            object should not be processed further.

        """
        name = ad_object['Name']
        dn = ad_object['DistinguishedName']

        if 'UserAccountControl' in ad_object:
            self.logger.debug3("For %s UAC: %s" % (name,
                               ad_object['UserAccountControl']))

        ent = self.adid2entity.get(name.lower())
        if ent:
            ent.in_ad = True
            if ent.entity_id in self.exempt_entities:
                self.logger.debug3(
                    'Entity {0} marked as exempt, ignoring'.format(
                        ent.entity_id))
                return False
            ent.ad_data['dn'] = dn

        # Don't touch others than from the subset, if set:
        if self.config.get('subset'):
            # Convert names to comply with 'name_format':
            subset_names = (self._format_name(s) for s in
                            self.config['subset'])
            if name not in subset_names:
                self.logger.debug3("Ignoring due to subset: %s", name)
                return False

        # Don't touch those in OUs we should ignore:
        if any(dn.endswith(ou) for ou in self.config.get('ignore_ou', ())):
            self.logger.debug('Object in ignore_ou: %s' % dn)
            return False

        # If not found in Cerebrum, remove the object (according to config):
        if not ent:
            self.logger.debug2("Unknown object %s - %s" % (name, ad_object))
            self.downgrade_object(ad_object,
                                  self.config.get('handle_unknown_objects',
                                                  ('disable', None)))
            return False

        # If not active in Cerebrum, do something (according to config).
        # TODO: If downgrade is set to 'move', it conflicts with moving
        # objects. How to solve this?
        if not ent.active:
            self.downgrade_object(ad_object,
                                  self.config['handle_deactivated_objects'])

        if self.config['move_objects']:
            # Do not move if downgrade is set to move objects:
            if (ent.active or
                    self.config['handle_deactivated_objects'][0] != 'move'):
                self.move_object(ad_object, ent.ou)
                # Updating the DN, for later updates in the process:
                dn = ','.join((ad_object['DistinguishedName'].split(',')[0],
                               ent.ou))
                ad_object['DistinguishedName'] = dn

        # Compare attributes:
        changes = self.get_mismatch_attributes(ent, ad_object)
        if changes:
            # Save the list of changes for possible future use
            ent.changes = changes
            self.server.update_attributes(dn, changes, ad_object)
            self.script('modify_object', ad_object, changes=changes.keys())
        # Store SID in Cerebrum
        self.store_sid(ent, ad_object.get('SID'))
        return True

    def get_mismatch_attributes(self, ent, ad_object):
        """Compare an entity's attributes between Cerebrum and AD.

        If the attributes exists in both places, it should be updated if it
        doesn't match. If it only exists

        The changes gets appended to the entity's change list for further
        processing.

        :type ent: CerebrumEntity
        :param ent:
            The given entity from Cerebrum, with calculated attributes.

        :type ad_object: dict
        :param ad_object:
            The given attributes from AD for the target object.

        :rtype: dict
        :return:
            The list of attributes that doesn't match and should be updated.
            The key is the name of the attribute, and the value is a dict with
            the elements:

            - *add*: For elements that should be added to the attribute in AD.
            - *remove*: For elements that should be removed from the attribute.
            - *fullupdate*: For attributes that should be fully replaced.

            The result could be something like::

                {'Member': {
                        'add': ('userX', 'userY',),
                        'remove': ('userZ',),
                        },
                 'Description': {
                        'fullupdate': 'New description',
                        },
                 }

        """
        ret = {}
        for atr, atrconfig in self.config['attributes'].iteritems():
            value = ent.attributes.get(atr, None)
            ad_value = ad_object.get(atr, None)
            # Filter/convert the value from AD before getting compared:
            if ad_value and isinstance(atrconfig, ConfigUtils.AttrConfig):
                if atrconfig.ad_transform:
                    ad_value = atrconfig.ad_transform(ad_value)
            mismatch, add_elements, remove_elements = \
                self.attribute_mismatch(ent, atr, value, ad_value)
            if mismatch:
                ret[atr] = dict()
                if add_elements or remove_elements:
                    self.logger.debug("Mismatch attr for %s: %s.",
                                      ent.entity_name, atr)
                    if add_elements:
                        self.logger.debug(
                            " - adding: %s",
                            '; '.join('%s (%s)' % (m, type(m)) for m in
                                      add_elements))
                        ret[atr]['add'] = add_elements
                    if remove_elements:
                        self.logger.debug(
                            " - removing: %s",
                            '; '.join('%s (%s)' % (m, type(m)) for m in
                                      remove_elements))
                        ret[atr]['remove'] = remove_elements
                else:
                    self.logger.debug(
                        "Mismatch attr %s for %s: '%s' (%s) -> '%s' (%s)",
                        atr, ent.entity_name, ad_value, type(ad_value),
                        value, type(value))
                    ret[atr]['fullupdate'] = value
        return ret

    def attribute_mismatch(self, ent, atr, c, a):
        """Compare an attribute between Cerebrum and AD.

        This is a generic method. Specific attributes should not be hardcoded
        in this method, but should rather be configurable, or might be
        subclassed even though that should be avoided (try to generalize).

        The attributes are matched in different ways. The order does for
        example not matter for multivalued attributes, i.e. lists.

        :type ent: CerebrumEntity
        :param ent:
            The given entity from Cerebrum, with calculated attributes.

        :type atr: str
        :param atr: The name of the attribute to compare

        :type c: mixed
        :param c: The value from Cerebrum for the given attribute

        :type a: mixed
        :param a: The value from AD for the given attribute

        :rtype: tuple(bool, list, list)
        :return:
            A tuple with three elements::

                (<bool:is_mismatching>, <set:to_add>, <set:to_remove>)

            The first value is True if the attribute from Cerebrum and AD does
            not match and should be updated in AD. If the attribute is a list
            and only some of its elements should be updated, the second and the
            third values list the elements that should be respectively added or
            removed.

        """
        # TODO: Should we care about case sensitivity?

        # Ignore the cases where an attribute is None in Cerebrum and an empty
        # string in AD:
        if c is None and a == '':
            return (False, None, None)
        # TODO: Should we ignore attributes with extra spaces? AD converts
        # double spaces into single spaces, e.g. GivenName='First  Last'
        # becomes in AD 'First Last'. This is issues that should be fixed in
        # the source system, but the error will make the sync update the
        # attribute constantly and make the sync slower.

        # SAMAccountName must be matched case insensitively. TODO: Case
        # sensitivity should rather be configurable.
        if atr.lower() == 'samaccountname':
            if a is None or c.lower() != a.lower():
                return (True, None, None)
        # Order does not matter in multivalued attributes
        seq = (list, tuple, set)
        if isinstance(c, seq) and (isinstance(a, seq) or a is None):
            a = a or list()
            to_add = set(c).difference(a)
            to_remove = set(a).difference(c)

            # Search for objects that might have a similar DN to what Cerebrum
            # expects.  We need to handle this, since people tend to move stuff
            # about in AD :/ Only the objects that have a unique RDN are
            # collected.
            do_not_remove = {}
            for e in to_remove:
                if 'cn' in e:
                    rdn = e[3:e.find(',')]
                    objects = self.server.find_object(
                        attributes={'CN': rdn})
                    if len(objects) == 1:
                        do_not_remove[rdn] = e

            # Remove the objects that have an alternate unique RDN, from the
            # list of attributes to remove.
            c = map(lambda x: do_not_remove.get(x[3:x.find(',')], x), c)
            # Re-calculate the set-difference
            to_remove = set(a).difference(c)

            return (to_add or to_remove, list(to_add), list(to_remove))
        return (c != a, None, None)

    def process_entities_not_in_ad(self):
        """Go through entities that wasn't processed while going through AD.

        This could mean that either the entity doesn't exist in AD and should
        be created, or that the object is in an OU that we are not processing.

        The entities should probably be created in AD, but that is up to a
        subclass to decide.

        """
        # Do a count of how many it is, for debuggin
        self.logger.debug("Found %d entities not found in AD",
                          len(filter(lambda x: not x.in_ad,
                                     self.entities.itervalues())))
        i = 0
        for ent in self.entities.itervalues():
            if ent.in_ad:
                continue

            if ent.entity_id in self.exempt_entities:
                self.logger.debug3(
                    'Entity {0} marked as exempt, ignoring'.format(
                        ent.entity_id))
                i += 1
                continue
            try:
                self.process_entity_not_in_ad(ent)
            except ADUtils.NoAccessException as e:
                # Access errors should be sent to the AD administrators, as
                # Cerebrum can not fix this.
                self.add_admin_message('warning',
                                       'Missing access rights for %s: %s' % (
                                           ent.ad_id, e))
            except PowershellException as e:
                self.logger.warn("PowershellException for %s: %s" %
                                 (ent.entity_name, e))
            else:
                i += 1
        self.logger.debug('Successfully processed %d entities not in AD' % i)

    def process_entity_not_in_ad(self, ent):
        """Process an entity that doesn't exist in AD, yet.

        The entity should be created in AD if active, and should then be
        updated as other, already existing objects.

        @type: CerebrumEntity
        @param: An object representing an entity in Cerebrum.

        """
        if not ent.active:
            if self.config['handle_deactivated_objects'][0] == 'delete':
                self.logger.debug("Inactive entity ignored: %s",
                                  ent.entity_name)
                return
            else:
                self.logger.debug("Not in AD, and also not active: %s",
                                  ent.entity_name)
        try:
            obj = self.create_object(ent)
        except ADUtils.ObjectAlreadyExistsException as e:
            # It exists in AD, but is probably somewhere out of our
            # search_base. Will try to get it, so we could still update it, and
            # maybe even move it to the correct OU.
            self.logger.debug("Entity already exists: %s", ent.entity_name)
            ent.in_ad = True
            attrs = self.config['attributes'].copy()
            if self.config['store_sid'] and 'SID' not in attrs:
                attrs['SID'] = None

            # TODO! Are there more unique attributes that can be used to
            # search? For user objects it seems it is enough with
            # 'SamAccountName' only. See
            # http://blogs.msdn.com/b/openspecification/archive/2009/07/10/\
            # understanding-unique-attributes-in-active-directory.aspx
            search_attributes = dict((u, ent.attributes[u]) for u
                                     in ['SamAccountName']
                                     if ent.attributes.get(u))
            objects = self.server.find_object(
                name=ent.entity_name,
                attributes=search_attributes,
                object_class=self.ad_object_class)
            if len(objects) == 1:
                # Found only one object, and it is most likely the one we need
                obj = objects[0]
                self.logger.debug("Found entity %s (%s)", ent.entity_name,
                                  obj['DistinguishedName'])
            elif len(objects) == 0:
                # Strange, we can't find the object though AD says it exists!
                self.logger.error("Cannot find %s, though AD says it exists",
                                  ent.ad_id)
                return False
            else:
                # Found several objects that satisfy the search criterias.
                # Unfortunately, in this case we can't determine which one
                # we actually need.
                self.logger.error("Ambiguous object %s. Found several with "
                                  "the same name. Cannot determine which "
                                  "one is the right one.", ent.ad_id)
                return False
        except (ADUtils.SetAttributeException,
                CommandTooLongException) as e:
            # The creation of the object may have failed because of entity's
            # attributes. It may have been too many of them and the command
            # became too long, or they contained (yet) invalid paths in AD.
            # In many cases update_attributes function for existing objects
            # can fix attributes problem. So it's good to try to create an
            # object without attributes now and wait until the next round for
            # its attributes to be updated.
            self.logger.warning("""Failed creating %s. """
                              """Trying to create it without attributes"""
                              % ent.ad_id)
            # SamAccountName is needed to be present upon object's creation.
            # It will default to name if it is not present. But if it is --
            # it has to be preserved.
            original_samaccountname = ent.attributes.get('SamAccountName')
            if original_samaccountname:
                ent.attributes = {'SamAccountName': original_samaccountname}
            else:
                ent.attributes = {}
            try:
                obj = self.create_object(ent)
            except Exception:
                # Really failed
                self.logger.exception("Failed creating %s." % ent.ad_id)
                return False
            else:
                ent.ad_new = True
        except Exception:
            # Unforeseen exception; traceback will be logged
            self.logger.exception("Failed creating %s." % ent.ad_id)
            return False
        else:
            ent.ad_new = True
        ent.in_ad = True
        ent.ad_data['dn'] = obj['DistinguishedName']

        if not ent.ad_new:
            # It is an existing object, but under wrong OU (otherwise it would
            # have been fetched earlier). It should be therefore passed to
            # process_ad_object, like it was done before for all found objects.
            # NB! For some upper classes process_ad_object is overridden and
            # performs extra actions. In this case they will not be performed,
            # but the next iteration of sync should fix this.
            self.process_ad_object(obj)
        return obj

    def create_ou(self, dn):
        """Helper method for creating an OU recursively.

        The OUs will only be created if the config says so. TODO: Might want to
        change where this is checked.

        @type dn: str
        @param dn:
            The DistinguishedName of the OU that should be created.

        """
        if not self.config['create_ous']:
            return
        self.logger.info("Creating OU: %s" % dn)
        name, path = dn.split(',', 1)
        if name.lower().startswith('ou='):
            name = name[3:]
        try:
            ou = self.server.create_object(name, path, 'organizationalunit')
        except ADUtils.OUUnknownException:
            self.logger.info("OU was not found: %s", path)
            self.create_ou(path)
            # Then retry creating the original OU:
            ou = self.server.create_object(name, path, 'organizationalunit')
        self.script('new_object', ou)
        return ou

    def create_object(self, ent, **parameters):
        """Create a given entity in AD.

        This is talking with the AD client to create the object properly. You
        should subclass this to e.g. add extra parameters to the creation.

        @type ent: CerebrumEntity
        @param ent: The entity that should be created in AD.

        @type **parameters: mixed
        @param **parameters: Extra data that should be sent to AD when creating
            the object.

        @raise ObjectAlreadyExistsException: If an object with the same name or
            id existed in AD already.

        """
        try:
            if self.ad_object_class == 'group':
                parameters['GroupScope'] = self.new_group_scope
                parameters['GroupCategory'] = self.new_group_type
            new_object = self.server.create_object(
                ent.ad_id, ent.ou, self.ad_object_class,
                attributes=ent.attributes, parameters=parameters)
        except ADUtils.OUUnknownException:
            self.logger.info("OU was not found: %s", ent.ou)
            if not self.config['create_ous']:
                raise
            self.create_ou(ent.ou)
            # Then retry creating the object:
            new_object = self.create_object(ent, **parameters)
        self.script('new_object', new_object)
        return new_object

    def downgrade_object(self, ad_object, action):
        """Do a downgrade of an object in AD.

        The object could for instance be unknown in Cerebrum, or be inactive.
        The AD-object could then be disabled, moved and/or deleted, depending
        on the setting. The configuration says what should be done with such
        objects, as it could be disabled, moved, deleted or something else.

        @type ad_object: dict
        @param: The data about the AD-object to downgrade.

        @type action: tuple
        @param action:
            A two-element tuple, where the first element is a string, e.g.
            'ignore', 'delete', 'move' or 'disable'. The second element
            contains extra information, e.g. to what OU the object should be
            moved to.

        """
        dn = ad_object['DistinguishedName']
        # conf = self.config.get('handle_unknown_objects', ('disable', None))
        if action[0] == 'ignore':
            self.logger.debug2("Downgrade: ignoring AD object: %s", dn)
            return
        elif action[0] == 'disable':
            if not ad_object.get('Enabled'):
                return
            self.disable_object(ad_object)
        elif action[0] == 'move':
            if ad_object.get('Enabled'):
                self.disable_object(ad_object)
            if not dn.lower().endswith(action[1].lower()):
                self.logger.debug("Downgrade: moving from '%s' to '%s'", dn,
                                  action[1])
                # TODO: test if this works as expected!
                self.move_object(ad_object, action[1])
            return True
        elif action[0] == 'delete':
            self.delete_object(ad_object)
        else:
            raise Exception("Unknown config for downgrading object %s: %s" %
                            (ad_object.get('Name'), action))

    def disable_object(self, ad_object):
        """ Disable the given object.

        :param dict ad_object: The object as retrieved from AD.

        """
        self.server.disable_object(ad_object['DistinguishedName'])
        self.script('disable_object', ad_object)

    def enable_object(self, ad_object):
        """ Enable the given object.

        :param dict ad_object: The object as retrieved from AD.

        """
        self.server.enable_object(ad_object['DistinguishedName'])
        # TODO: If we run scripts here, we'll also have to consider
        #   - set_password + enable_object
        #   - quicksync + quarantines
        # self.script('enable_object', ad_object)

    def delete_object(self, ad_object):
        """ Delete the given object.

        :param dict ad_object: The object as retrieved from AD.

        """
        self.server.delete_object(ad_object['DistinguishedName'])
        # TODO: If we run scripts here, we'll also have to consider
        #   - quicksync + quarantines
        # self.script('delete_object', ad_object)

    def move_object(self, ad_object, ou):
        """Move a given object to the given OU.

        It is first checked for if it's already in the correct OU.

        @type ad_object: dict
        @param ad_object: The object as retrieved from AD.

        @type ou: string
        @param ou: The full DN of the OU the object should be moved to.

        """
        dn = ad_object['DistinguishedName']
        self.logger.debug3("Trying to move %s to %s", dn, ou)
        if ou == dn.split(',', 1)[1]:
            # Already in the correct location
            return
        try:
            self.server.move_object(dn, ou)
        except ADUtils.OUUnknownException:
            self.logger.info("OU was not found: %s", ou)
            if not self.config['create_ous']:
                raise
            self.create_ou(ou)
            self.server.move_object(dn, ou)
        # Update the dn, so that it is correct when triggering event
        ad_object['DistinguishedName'] = ','.join((dn.split(',', 1)[0], ou))
        self.script('move_object', ad_object, move_from=dn)

    def pre_process(self):
        """Hock for things to do before the sync starts."""
        self.script('pre_sync')

    def post_process(self):
        """Hock for things to do after the sync has finished."""
        self.script('post_sync')

    def store_sid(self, ent, sid):
        """Store the SID for an entity as an external ID in Cerebrum.

        @type ent: CerebrumEntity
        @param ent: The object of the Cerebrum entity for which the SID should
            be stored.

        @type sid: string
        @param sid: The SID from AD which should be stored.

        """
        if not self.config['store_sid']:
            return
        if getattr(ent, 'sid', '') == sid:
            return
        self.logger.info("Storing SID for entity %s: %s", ent.entity_id, sid)
        en = self._ent_extid
        en.clear()
        en.find(ent.entity_id)
        # Since external_id only works for one type of entities, we need to
        # find out which external_id type to store the SID as:
        sid_type = self.sidtype_map[en.entity_type]
        en.affect_external_id(self.co.system_ad, sid_type)
        en.populate_external_id(self.co.system_ad, sid_type, sid)
        en.write_db()

    def script(self, action, ad_object=None, ent=None, **extra):
        """Check if a script of a given type is defined and execute it.

        The scripts have to be set up by the AD administrators, Cerebrum has
        only the responsibility to fire them up.

        @type action: string
        @param action: The type of event that has occured, and which could be
            triggering a script to be executed. The script location is found in
            the config.

        @type ad_object: dict
        @param ad_object: The data about the object to be targeted by the
            script.

        @type ent: CerebrumEntity
        @param ent: The entity that is targeted by the script. Not always
            needed.

        @type **extra: mixed
        @param **extra: Extra arguments for the script, the arguments are
            transformed into:

                -key1 value1

        """
        if action not in self.config['script']:
            return
        params = {'Action': action, 'UUID': str(uuid.uuid4()), }
        for attr in ('DistinguishedName', 'ObjectGUID'):
            if ad_object and ad_object.get(attr):
                params.update({'Identity': ad_object[attr], })
                break
        if extra:
            params.update(extra)
        try:
            return self.server.execute_script(self.config['script'][action],
                                              **params)
        except PowershellException as e:
            self.logger.warn(
                "Script failed for event %s (%s): %s",
                action, params.get('UUID'), e)
            return False


class UserSync(BaseSync):

    """Sync for Cerebrum accounts in AD.

    This contains generic functionality for handling accounts for AD, to add
    more functionality you need to subclass this.

    A mapping is added by this class: L{owner2ent}, which is a dict with the
    owner's owner_id as key, and the values are lists of entity instances.

    """

    # The default object class of the objects to work on. Used if not the
    # config says otherwise.
    default_ad_object_class = 'user'

    # A mapping of what the different UserAccountControl settings map to,
    # bitwise. The UserAccountControl attribute is returned as a integer, where
    # each bit gives us one setting. This setting should be expanded if new
    # settings are added to AD. Note that the config tells us what settings we
    # should care about and not. The position in this list maps to the bit
    # position, starting from the right. Each string corresponds to the
    # setting's name in the powershell command Set-ADAccountControl.
    # For more info about the UAC settings, see
    # http://msdn.microsoft.com/en-us/library/ms680832(v=vs.85).aspx
    _useraccountcontrol_settings = (
        # 1. If the logon script will be run. Not implemented.
        None,  # 'Script',
        # 2. If the account is disabled. Set by Disable-ADAccount instead.
        None,  # 'AccountDisabled',
        # 3. The home directory is required.
        'HomedirRequired',
        # 4. The account is currently locked out, e.g. by too many failed
        #    password attempts. Gets set and reset automatically by AD DS.
        None,  # 'LockOut',
        # 5. No password is required to log on with the given account.
        'PasswordNotRequired',
        # 6. The user can't change its password.
        'CannotChangePassword',
        # 7. The user can send an encrypted password. Updates the value
        #    which in AD is named ADS_UF_ENCRYPTED_TEXT_PASSWORD_ALLOWED.
        'AllowReversiblePasswordEncryption',
        # 8. The account is for users whose primary account is in another
        #    domain. This account provides local domain access. Also called
        #    "Local user account". Not implemented.
        None,  # 'TempDuplicateAccount',
        # 9. A normal account. This is the default type of an account. Not
        #    implemented.
        None,  # 'NormalAccount',
        # 10. Trusts the account for other domains. Not implemented.
        None,  # 'InterdomainTrustAccount',
        # 11. If set, this is a computer account. Not implemented. Needs to
        #     be set in other ways.
        None,  # 'WorkstationTrustAccount',
        # 12. If set, this is a computer account for a system backup domain
        #     controller that is a member of this domain.
        None,  # 'ServerTrustAccount',
        # 13. Not used
        None,
        # 14. Not used
        None,
        # 15. The password for the account will never expire.
        'PasswordNeverExpires',
        # 16. If set, this is an MNS logon account.
        'MNSLogonAccount',
        # 17. Force user to log on by smart card. Not implemented.
        None,  # 'SmartcardRequired',
        # 18. The service account is trusted for Kerberos delegation. Any
        #     such service can impersonate a client requesting the service.
        'TrustedForDelegation',
        # 19. The service account's security context will not be delegated
        #     to any service.
        'AccountNotDelegated',
        # 20. Restrict account to only use DES encryption types for keys.
        'UseDESKeyOnly',
        # 21. Account does not require Kerberos pre-authentication for
        #     logon.
        'DoesNotRequirePreAuth',
        # 22. The account's password is expired. Automatically set by AD.
        'PasswordExpired',
        # 23. Enabled for delegation of authentication of others.
        #     Warning: This setting enables the account and services running
        #     as the account to authenticate as other users!
        'TrustedToAuthForDelegation',
        # 24. Account is used for read-only DCs, and needs protection.
        None,  # 'PartialSecretsAccount',
        )

    def __init__(self, *args, **kwargs):
        """Instantiate user specific functionality."""
        super(UserSync, self).__init__(*args, **kwargs)
        self.addr2username = {}
        self.ac = Factory.get("Account")(self.db)
        self.pe = Factory.get("Person")(self.db)

    def configure(self, config_args):
        """Override the configuration for setting user specific variables.

        """
        super(UserSync, self).configure(config_args)

        # Check that the UserAccountControl settings are valid:
        for setting in self.config['useraccountcontrol']:
            if setting not in self._useraccountcontrol_settings:
                raise Exception('Unknown UserAccountControl: %s' % setting)

    def start_fetch_ad_data(self, object_class=None, attributes=dict()):
        """Ask AD to start generating the data we need about groups.

        Could be subclassed to get more/other data.

        @rtype: string
        @return: A CommandId that is the reference from the AD service to later
            get the data that has been generated. Could be used for e.g.
            L{process_ad_data}.

        """
        if self.config['useraccountcontrol']:
            attributes['UserAccountControl'] = None
        if 'Enabled' not in attributes:
            attributes['Enabled'] = None
        return super(UserSync, self).start_fetch_ad_data(
            object_class=object_class, attributes=attributes)

    def fetch_cerebrum_data(self):
        """Fetch data from Cerebrum that is needed for syncing accounts.

        What kind of data that will be gathered is up to the attribute
        configuration. Contact info will for instance not be retrieved from
        Cerebrum if it's set for any attributes. Subclasses could however
        override this, if they need such data for other usage.

        """
        super(UserSync, self).fetch_cerebrum_data()

        # No need to fetch Cerebrum data if there are no entities to add them
        # to. Some methods in the Cerebrum API also raises an exception if
        # given an empty list of entities.
        if not self.entities:
            return

        # Create a mapping of owner id to user objects
        self.logger.debug("Fetch owner information...")
        self.owner2ent = dict()
        for ent in self.entities.itervalues():
            self.owner2ent.setdefault(ent.owner_id, []).append(ent)
        self.logger.debug("Mapped %d entity owners", len(self.owner2ent))

        # Set what is primary accounts.
        i = 0
        for row in self.ac.list_accounts_by_type(primary_only=True):
            ent = self.id2entity.get(row['account_id'])
            if ent:
                ent.is_primary_account = True
                i += 1
        self.logger.debug("Found %d primary accounts", i)

        # The different methods decides if their data should be fetched or not,
        # depending on the attribute configuration.
        self.fetch_contact_info()
        self.fetch_names()
        self.fetch_person_names()
        self.fetch_external_ids()
        self.fetch_traits()
        self.fetch_address_info()
        self.fetch_posix()
        self.fetch_homes()
        self.fetch_mail()

    def fetch_cerebrum_entities(self):
        """Fetch the users from Cerebrum that should be compared against AD.

        The configuration is used to know what to cache. All data is put in a
        list, and each entity is put into an object from
        L{Cerebrum.modules.ad2.CerebrumData} or a subclass, to make it easier
        to later compare them with AD objects.

        Could be subclassed to fetch more data about each entity to support
        extra functionality from AD and to override settings, e.g. what contact
        info that should be used.

        @rtype: list
        @return: A list of targeted entities from Cerebrum, wrapped into
            L{CerebrumData} objects.
        """
        # Find all users with defined spread(s):
        self.logger.debug("Fetching users with spread %s" %
                          (self.config['target_spread'],))
        subset = self.config.get('subset')
        if hasattr(self.co, 'trait_account_exempt'):
            for row in self._entity_trait.list_traits(
                    self.co.trait_account_exempt):
                self.exempt_entities.append(int(row['entity_id']))
        for row in self.ac.search(spread=self.config['target_spread']):
            uname = row["name"]
            # For testing or special cases where we only want to sync a subset
            # of entities. The subset should contain the entity names, e.g.
            # usernames or group names.
            if subset and uname not in subset:
                continue
            self.entities[uname] = self.cache_entity(
                int(row['account_id']),
                uname,
                owner_id=int(row['owner_id']),
                owner_type=int(row['owner_type']))
            # This functionality makes it possible to set a different AD-OU
            # based on the type(s) og affiliation(s) (CRB-862)
            ou_mappings = self.config.get('ou_mappings')
            if ou_mappings and isinstance(ou_mappings, list):
                for mapping in ou_mappings:
                    aff_list = mapping.get('affiliations')
                    if not aff_list:
                        raise ConfigUtils.ConfigError(
                            'Missing or invalid affiliations in ou_mappings')
                    validator = ConfigUtils.AccountCriterias(
                        affiliations=aff_list)
                    try:
                        validator.check(self.entities[uname])
                        self.entities[uname].ou = mapping['ou']
                        self.logger.debug3(
                            'Using "ou_mappings". '
                            'OU for account %s (%d) has been set to %s' % (
                                uname,
                                row['account_id'],
                                mapping['ou']))
                        break
                    except ConfigUtils.CriteriaError:  # no match
                        continue
                else:
                    self.logger.debug(
                        'Using "ou_mappings". '
                        'No matching affiliation(s) for account %s (%d). '
                        'Using "target_ou"' % (
                            uname,
                            row['account_id']))

    def fetch_names(self):
        """Fetch all the persons' names and store them for the accounts.

        This overrides the default behaviour of fetching the names registered
        for the given entities, but instead fetches the owner's (person's)
        names.

        The names that is retrieved are first and last names. Titles are
        retrieved in L{fetch_titles}, even though they're stored as names too.
        TODO: change this, and put all in a dict of names instead?

        If there exist personal accounts without first and last names, it gets
        logged.

        """
        self.logger.debug("Fetch name information...")

        # First PersonName:
        variants = set()
        systems = set()
        languages = set()
        all_systems = False
        # Go through config and see what info needs to be fetched:
        for atr in ConfigUtils.get_config_by_type(self.config['attributes'],
                                                  ConfigUtils.NameAttr):
            variants.update(atr.name_variants)
            if atr.source_systems is None:
                all_systems = True
            else:
                systems.update(atr.source_systems)
            if atr.languages:
                languages.update(atr.languages)
        self.logger.debug2("Fetching name variants: %s",
                           ', '.join(str(v) for v in variants))
        self.logger.debug2("Fetching names by languages: %s",
                           ', '.join(str(l) for l in languages))
        self.logger.debug2("Fetching names from sources: %s",
                           ', '.join(str(s) for s in systems))
        if not variants:
            return
        if all_systems or not systems:
            # By setting to None we fetch from all source_systems.
            systems = None
        if not languages:
            languages = None
            # TODO: Or make use of self.config['language'] to get the priority
            # right?

        # If subset is given, we want to limit the db-search:
        ids = None
        if self.config['subset']:
            ids = self.owner2ent.keys()
        i = 0
        # TODO: This is not always for persons! Need to also fetch for e.g.
        # OUs. Do we need to fetch in two rounds? One for the entities and one
        # for the owners?
        for row in self.pe.search_name_with_language(name_variant=variants,
                                                     entity_type=self.co.entity_person,
                                                     entity_id=ids,
                                                     name_language=languages):
            for ent in self.owner2ent.get(row['entity_id'], ()):
                vari = str(self.co.EntityNameCode(row['name_variant']))
                lang = str(self.co.LanguageCode(row['name_language']))
                ent.entity_name_with_language.setdefault(vari, {})[lang] = row['name']
                i += 1
        self.logger.debug("Found %d names" % i)

    def fetch_person_names(self):
        """Fetch all the persons' names and store them for the accounts.

        This overrides the default behaviour of fetching the names registered
        for the given entities, but instead fetches the owner's (person's)
        names.

        The names that is retrieved are first and last names. Titles are
        retrieved in L{fetch_titles}, even though they're stored as names too.
        TODO: change this, and put all in a dict of names instead?

        If there exist personal accounts without first and last names, it gets
        logged.

        """
        self.logger.debug("Fetch person name information...")
        variants = set()
        systems = set()
        #  languages = set()
        all_systems = False
        # Go through config and see what info needs to be fetched:
        for atr in ConfigUtils.get_config_by_type(self.config['attributes'],
                                                  ConfigUtils.PersonNameAttr):
            variants.update(atr.name_variants)
            if atr.source_systems is None:
                all_systems = True
            else:
                systems.update(atr.source_systems)
        self.logger.debug2("Fetching person person name variants: %s",
                           ', '.join(str(v) for v in variants))
        self.logger.debug2("Fetching person names from sources: %s",
                           ', '.join(str(s) for s in systems))
        if not variants:
            return
        if all_systems or not systems:
            # By setting to None we fetch from all source_systems.
            systems = None

        # If subset is given, we want to limit the db-search:
        ids = None
        if self.config['subset']:
            ids = self.owner2ent.keys()

        # Names stored in person table:
        i = 0
        for row in self.pe.search_person_names(source_system=systems,
                                               name_variant=variants,
                                               person_id=ids):
            for ent in self.owner2ent.get(row['person_id'], ()):
                vari = str(self.co.PersonName(row['name_variant']))
                ssys = str(self.co.AuthoritativeSystem(row['source_system']))
                ent.person_names.setdefault(vari, {})[ssys] = row['name']
                i += 1
        self.logger.debug("Found %d person names" % i)

    def fetch_contact_info(self):
        """Fetch all contact information for users, e.g. mobile and telephone.

        Checks the config for what contact info to fetch from Cerebrum, fetches
        it and puts them in each CerebrumEntity's dict L{contact_info}. The
        format of the dict must be matched from this method and the
        CerebrumEntity class. Example on how L{contact_info} could look like:

            {str(contacttypeA):
                                {str(sourcesystemA): str(contactvalue),
                                 str(sourcesystemB): str(contactvalue),
                                 },
             str(contacttypeB):
                                {str(sourcesystemA): str(contactvalue),
                                 str(sourcesystemB): str(contactvalue),
                                 },
             }

        """
        self.logger.debug("Fetch contact info...")
        types = set()
        systems = set()
        all_systems = False
        # Go through config and see what info needs to be fetched:
        for atr in ConfigUtils.get_config_by_type(self.config['attributes'],
                                                  ConfigUtils.ContactAttr):
            types.update(atr.contact_types)
            if atr.source_systems is None:
                all_systems = True
            else:
                systems.update(atr.source_systems)
        self.logger.debug2("Fetching contact-types: %s",
                           ', '.join(str(t) for t in types))
        self.logger.debug2("Fetching contactinfo from sources: %s",
                           ', '.join(str(s) for s in systems))
        if not types:
            return
        if all_systems or not systems:
            # By setting to None we fetch from all source_systems.
            systems = None

        # Limit the db search if only working for a subset
        ids = None
        if self.config['subset']:
            ids = self.owner2ent.keys()

        # Contact info stored on the person:
        i = 0
        for row in self.pe.list_contact_info(source_system=systems,
                                             entity_type=self.co.entity_person,
                                             entity_id=ids,
                                             contact_type=types):
            for ent in self.owner2ent.get(row['entity_id'], ()):
                ctype = str(self.co.ContactInfo(row['contact_type']))
                ssys = str(self.co.AuthoritativeSystem(row['source_system']))
                ent.contact_info.setdefault(ctype, {})[ssys] = row
                i += 1
        # Contact info stored on the account:
        for row in self.ac.list_contact_info(source_system=systems,
                                             entity_type=self.co.entity_account,
                                             entity_id=ids,
                                             contact_type=types):
            ent = self.id2entity.get(row['entity_id'], None)
            if ent:
                ctype = str(self.co.ContactInfo(row['contact_type']))
                ssys = str(self.co.AuthoritativeSystem(row['source_system']))
                ent.contact_info.setdefault(ctype, {})[ssys] = row
                i += 1
        self.logger.debug("Found %d contact data" % i)

    def fetch_external_ids(self):
        """Fetch all external IDs for entities according to config.

        TODO: this should be moved upwards, as it's not only for users.

        """
        types = set()
        systems = set()
        all_systems = False
        # Go through config and see what info needs to be fetched:
        for atr in ConfigUtils.get_config_by_type(self.config['attributes'],
                                                  ConfigUtils.ExternalIdAttr):
            types.update(atr.id_types)
            if atr.source_systems is None:
                all_systems = True
            else:
                systems.update(atr.source_systems)
        if not types:
            return
        self.logger.debug("Fetch external ids...")
        if all_systems or not systems:
            # By setting to None we fetch from all source_systems.
            systems = None
        # Limit the db search if only working for a subset
        ids = None
        if self.config['subset']:
            ids = self.owner2ent.keys()

        i = 0
        # Search person:
        for row in self.pe.search_external_ids(
                source_system=systems, id_type=types, entity_id=ids,
                entity_type=self.co.entity_person):
            for ent in self.owner2ent.get(row['entity_id'], ()):
                itype = str(self.co.EntityExternalId(row['id_type']))
                ssys = str(self.co.AuthoritativeSystem(row['source_system']))
                ent.external_ids.setdefault(itype, {})[ssys] = row['external_id']
                i += 1
        # Search account:
        ids = None
        if self.config['subset']:
            ids = self.id2entity.keys()
        for row in self.ac.search_external_ids(
                source_system=systems, id_type=types, entity_id=ids,
                entity_type=self.co.entity_account):
            ent = self.id2entity.get(row['entity_id'], None)
            if ent:
                itype = str(self.co.EntityExternalId(row['id_type']))
                ssys = str(self.co.AuthoritativeSystem(row['source_system']))
                ent.external_ids.setdefault(itype, {})[ssys] = row['external_id']
                i += 1
        self.logger.debug("Found %d external IDs" % i)

    def fetch_traits(self):
        """Fetch all traits for entities according to config.

        TODO: this should be moved upwards, as it's not only for users.

        """
        types = set()
        # Go through config and see what info needs to be fetched:
        for atr in ConfigUtils.get_config_by_type(self.config['attributes'],
                                                  ConfigUtils.TraitAttr):
            types.update(atr.traitcodes)
        if not types:
            return
        self.logger.debug2("Fetch traits of types: %s",
                           ', '.join(str(t) for t in types))
        ids = NotSet
        if self.config['subset']:
            ids = self.id2entity.keys()
        i = 0
        for row in self.ent.list_traits(code=types, entity_id=ids):
            ent = self.id2entity.get(row['entity_id'], None)
            if ent:
                code = str(self.co.EntityTrait(row['code']))
                ent.traits[code] = row
                i += 1
        self.logger.debug("Found %d traits" % i)
        # TODO: Fetch from person too? Is that needed?

    def fetch_address_info(self):
        """Fetch addresses for users.

        """
        adrtypes = set()
        systems = set()
        all_systems = False
        # Go through config and see what info needs to be fetched:
        for atr in ConfigUtils.get_config_by_type(self.config['attributes'],
                                                  ConfigUtils.AddressAttr):
            adrtypes.update(atr.address_types)
            if atr.source_systems is None:
                all_systems = True
            else:
                systems.update(atr.source_systems)
        if not adrtypes:
            return
        self.logger.debug("Fetch address info...")
        if all_systems or not systems:
            # By setting to None we fetch from all source_systems.
            systems = None

        i = 0
        # Addresses stored on the person:
        if hasattr(self.pe, 'list_entity_addresses'):
            for row in self.pe.list_entity_addresses(
                    source_system=systems,
                    entity_type=self.co.entity_person,
                    address_type=adrtypes):
                for ent in self.owner2ent.get(row['entity_id'], ()):
                    atype = str(self.co.Address(row['address_type']))
                    ssys = str(self.co.AuthoritativeSystem(row['source_system']))
                    ent.addresses.setdefault(atype, {})[ssys] = row
                    i += 1
        # Contact info stored on the account:
        if hasattr(self.ac, 'list_entity_addresses'):
            for row in self.ac.list_entity_addresses(
                    source_system=systems,
                    entity_type=self.co.entity_account,
                    address_type=adrtypes):
                ent = self.id2entity.get(row['entity_id'], None)
                if ent:
                    atype = str(self.co.Address(row['address_type']))
                    ssys = str(self.co.AuthoritativeSystem(row['source_system']))
                    ent.addresses.setdefault(atype, {})[ssys] = row
                    i += 1
        self.logger.debug("Found %d addresses" % i)

    def fetch_mail(self):
        """Fetch all e-mail address for the users.

        This method only fetches the primary addresses. Subclass me if more
        e-mail data is needed, e.g. aliases.

        TODO: We have a problem here, since we store primary mail addresses
        differently for those that uses the Email module and those without it,
        which instead stores it as contact_info. Now we check if methods from
        the email module exists to check how we should fetch it, but we should
        fix this in a better way later.

        """
        if not ConfigUtils.has_config(
                self.config['attributes'],
                (ConfigUtils.EmailQuotaAttr, ConfigUtils.EmailAddrAttr,
                 ConfigUtils.EmailForwardAttr)):
            # No email data is needed, skipping
            return
        self.logger.debug("Fetch mail data...")

        # Limit/speed up db search if only targeting a subset:
        ids = None
        if self.config['subset']:
            ids = self.id2entity.keys()

        # Need a map from EmailTarget's target_id to entity_id:
        targetid2entityid = dict((r['target_id'], r['target_entity_id']) for r
                                 in self.mailtarget.list_email_targets_ext(
                                     target_entity_id=ids))
        for target_id, entity_id in targetid2entityid.iteritems():
            ent = self.entities.get(entity_id)
            if ent:
                ent.maildata['target_id'] = target_id

        # Email quotas
        if ConfigUtils.has_config(self.config['attributes'],
                                  ConfigUtils.EmailQuotaAttr):
            mailquota = Email.EmailQuota(self.db)
            i = 0
            for row in mailquota.list_email_quota_ext():
                if row['target_id'] not in targetid2entityid:
                    continue
                ent = self.id2entity.get(targetid2entityid[row['target_id']])
                if ent:
                    ent.maildata['quota'] = row
                    i += 1
            self.logger.debug("Found %d email quotas" % i)

        # Email addresses
        if ConfigUtils.has_config(self.config['attributes'],
                                  ConfigUtils.EmailAddrAttr):
            ea = Email.EmailAddress(self.db)
            # Need a mapping from address_id for the primary addresses:
            adrid2email = dict()
            i = 0
            # TODO: filter_expired could might be a config setting?
            for row in ea.search(filter_expired=False):
                ent = self.id2entity.get(targetid2entityid.get(row['target_id']))
                if ent:
                    adr = '@'.join((row['local_part'], row['domain']))
                    adrid2email[row['address_id']] = adr
                    ent.maildata.setdefault('alias', []).append(adr)
                    i += 1
                    self.addr2username[adr.lower()] = ent.entity_name
            self.logger.debug("Found %d email addresses", i)

            epat = Email.EmailPrimaryAddressTarget(self.db)
            i = 0
            for row in epat.list_email_primary_address_targets():
                if row['address_id'] not in adrid2email:
                    # Probably expired addresses
                    continue
                ent = self.id2entity.get(targetid2entityid[row['target_id']])
                if ent:
                    ent.maildata['primary'] = adrid2email[row['address_id']]
                    i += 1
            self.logger.debug("Found %d primary email addresses" % i)

        # Email forwards
        if ConfigUtils.has_config(self.config['attributes'],
                                  ConfigUtils.EmailForwardAttr):
            ef = Email.EmailForward(self.db)
            i = 0
            for row in ef.list_email_forwards():
                # Skip not enabled forwards. We should not need those.
                if row['enable'] != 'T':
                    continue
                ent_id = targetid2entityid.get(row['target_id'])
                if not ent_id:
                    continue
                ent = self.id2entity.get(targetid2entityid[row['target_id']])
                if ent:
                    ent.maildata.setdefault('forward', []).append(
                        row['forward_to'])
                    i += 1
            self.logger.debug("Found %d forward addresses" % i)

    def fetch_homes(self):
        """Fetch all home directories for the the users.

        The User objects gets filled with a list of all its home directories in
        the L{home} attribute, which is used according to
        L{ConfigUtils.AttrConfig.HomeAttr}.

        """
        homespreads = set()
        # Go through config and see what info needs to be fetched:
        for atr in ConfigUtils.get_config_by_type(self.config['attributes'],
                                                  ConfigUtils.HomeAttr):
            homespreads.add(atr.home_spread)
        if not homespreads:
            return
        self.logger.debug("Fetch home directories...")
        i = 0
        for sp in homespreads:
            for row in self.ac.list_account_home(
                    home_spread=sp,
                    account_spread=self.config['target_spread']):
                ent = self.id2entity.get(row['account_id'])
                if ent:
                    if not hasattr(ent, 'home'):
                        ent.home = {}
                    tmp = {}
                    tmp['status'] = row['status']
                    tmp['homedir'] = self.ac.resolve_homedir(
                        account_name=row['entity_name'],
                        disk_path=row['path'],
                        home=row['home'],
                        spread=row['home_spread'])
                    ent.home[row['home_spread']] = tmp
                    i += 1
        self.logger.debug("Found %d account home directories" % i)

    def fetch_posix(self):
        """Fetch the POSIX data for users, if needed.

        """
        if not ConfigUtils.has_config(self.config['attributes'],
                                      ConfigUtils.PosixAttr):
            # No need for any posix data
            return
        self.logger.debug("Fetch posix data...")
        pg = Factory.get('PosixGroup')(self.db)
        pu = Factory.get('PosixUser')(self.db)

        # Map from group_id to GID:
        posix_group_id2gid = dict((eid, gid) for eid, gid in
                                  pg.list_posix_groups())
        self.logger.debug("Found %d posix groups", len(posix_group_id2gid))

        i = 0
        for row in pu.list_posix_users():
            ent = self.id2entity.get(row['account_id'], None)
            if ent:
                if not hasattr(ent, 'posix'):
                    ent.posix = {}
                ent.posix['uid'] = int(row['posix_uid']) or ''
                ent.posix['gid'] = posix_group_id2gid.get(row['gid'], '')
                ent.posix['shell'] = str(self.co.PosixShell(row['shell']))
                ent.posix['gecos'] = row['gecos']
                i += 1
        self.logger.debug("Found %d posix users", i)

    def fetch_passwords(self):
        """Fetch passwords for accounts that are new in AD.

        The passwords are stored in L{self.uname2pasw}, and passwords are only
        fetched for entities where the attribute L{in_ad} is False. This should
        therefore be called after the processing of existing entities and
        before processing the entities that doesn't exist in AD yet.

        The passwords are fetched from the changelog, and only the last and
        newest password is used.

        """
        self.logger.debug("Fetching passwords for accounts not in AD")
        self.uname2pasw = {}
        for row in reversed(
                tuple(self.db.get_log_events(
                    types=self.clconst.account_password))):
            try:
                ent = self.id2entity[row['subject_entity']]
            except KeyError:
                # We continue past this event. Since account is not in the
                # list of users who should get their password set.
                continue
            if ent.entity_name in self.uname2pasw:
                # We only need the last password for each acount
                continue
            if ent.in_ad:
                # Account is already in AD
                continue

            # If a GPG recipient ID is set, we fetch the encrypted password
            if self.config.get('gpg_recipient_id', None):
                gpg_db = GpgData(self.db)
                for tag in ('password-base64', 'password'):
                    gpg_data = gpg_db.get_messages_for_recipient(
                        entity_id=ent.entity_id,
                        tag=tag,
                        recipient=self.config['gpg_recipient_id'],
                        latest=True)
                    if gpg_data:
                        break
                else:
                    self.logger.debug2(
                        'No GPG encrypted password found for %s',
                        ent.entity_name)
                    continue
                password = gpg_data[0].get('message')
                self.uname2pasw[ent.entity_name] = (password, tag)
            else:  # we fetch the plaintext from the changelog
                try:
                    password = json.loads(
                        row['change_params'])['password']
                    self.uname2pasw[ent.entity_name] = (password,
                                                        'plaintext')
                except (KeyError, TypeError, IndexError):
                    self.logger.debug2('No plaintext loadable for %s',
                                       ent.entity_name)

    def process_ad_object(self, ad_object):
        """Compare a User object retrieved from AD with Cerebrum.

        Overriden for user specific functionality.

        """
        if not super(UserSync, self).process_ad_object(ad_object):
            return False
        ent = self.adid2entity.get(ad_object['Name'].lower())

        if ent.active:
            if not ad_object.get('Enabled', False):
                self.enable_object(ad_object)

    def process_entities_not_in_ad(self):
        """Start processing users not in AD.

        Depends on the generic superclass' functionality.

        """
        # Cache the passwords for the entities not in AD:
        self.fetch_passwords()
        return super(UserSync, self).process_entities_not_in_ad()

    def process_entity_not_in_ad(self, ent):
        """Process an account that doesn't exist in AD, yet.

        We should create and update a User object in AD for those who are not
        in AD yet. The object should then be updated as normal objects.

        @type: CerebrumEntity
        @param: An object representing an entity in Cerebrum.

        """
        ad_object = super(UserSync, self).process_entity_not_in_ad(ent)
        if not ad_object:
            self.logger.warn("What to do? Got None from super for: %s" %
                             ent.entity_name)
            return
        # TODO: Move this to create_object() instead! Could then add the
        #       password in the creating call - would be faster.
        if ent.ad_new:
            # TODO: Is this OK? Should we diable the object?
            # We collect the password from the cache, as generated by
            # fetch_passwords(). If there is no plaintext available for
            # the user, set an empty one.
            try:
                password, tag = self.uname2pasw[ent.entity_name]
            except KeyError:
                self.logger.warn('No password set for %s' % ent.entity_name)
                return ad_object

            self.logger.debug('Trying to set pw for %s', ent.entity_name)
            if self.server.set_password(ad_object['DistinguishedName'],
                                        password,
                                        password_type=tag):
                # As a security feature, you have to explicitly enable the
                # account after a valid password has been set.
                if ent.active:
                    self.enable_object(ad_object)

        # If more functionality gets put here, you should check if the entity
        # is active, and not update it if the config says so (downgrade).
        return ad_object

    def process_cl_event(self, row):
        """Process a given ChangeLog event for users.

        Overriden to support account specific changes.

        @type row: dict of db-row
        @param row:
            A db-row, as returned from L{changelog.get_events()}. This is the
            row that should be processed.

        @rtype: bool
        @return:
            The result from the handler. Should be True if the sync succeeded
            or there was no need for the change to be synced, i.e. the log
            change could be confirmed. Should only return False if the change
            needs to be redone.

        @raise UnhandledChangeTypeError?
            TODO: Should we have our own exception class that is used if the
            method does not know what to do with a given change type? Could
            then be used by subclasses.

        @raise TODO:
            TODO: What exceptions is expected here?

        """
        # TODO: Should we create a new account instance per call, to support
        # threading?
        self.ac.clear()
        try:
            self.ac.find(row['subject_entity'])
        except Errors.NotFoundError:
            pass
        else:
            if hasattr(self.co, 'trait_account_exempt') and \
               self.co.trait_account_exempt in self.ac.get_traits():
                self.logger.debug('Account {0} has trait {1}, ignoring'.format(
                    self.ac.entity_id, str(self.co.trait_account_exempt)))
                return False

        # TODO: clean up code when more functionality is added!
        if row['change_type_id'] == self.clconst.account_password:
            if self.ac.is_expired():
                self.logger.debug("Account %s is expired, ignoring",
                                  row['subject_entity'])
                return True
            if not self.ac.has_spread(self.config['target_spread']):
                self.logger.debug("Account %s without target_spread, ignoring",
                                  row['subject_entity'])
                return False

            name = self._format_name(self.ac.account_name)

            # If a GPG recipient ID is set, we fetch the encrypted password
            tag = 'plaintext'
            if self.config.get('gpg_recipient_id', None):
                gpg_db = GpgData(self.db)
                for tag in ('password-base64', 'password'):
                    gpg_data = gpg_db.get_messages_for_recipient(
                        entity_id=self.ac.entity_id,
                        tag=tag,
                        recipient=self.config['gpg_recipient_id'],
                        latest=True)
                    if gpg_data:
                        break
                else:
                    self.logger.warn(
                        'Account %s missing GPG encrypted password',
                        row['subject_entity'])
                    return False
                pw = gpg_data[0].get('message')
            else:  # we fetch the plaintext from the changelog
                try:
                    pw = json.loads(row['change_params'])['password']
                except (KeyError, TypeError, IndexError):
                    self.logger.warn("Account %s missing plaintext password",
                                     row['subject_entity'])
                    return False

            if not isinstance(pw, unicode):
                try:
                    pw = unicode(pw, 'UTF-8')
                except UnicodeDecodeError:
                    pw = unicode(pw, 'ISO-8859-1')
            return self.server.set_password(name, pw, password_type=tag)

        elif row['change_type_id'] in (self.clconst.quarantine_add,
                                       self.clconst.quarantine_del,
                                       self.clconst.quarantine_mod,
                                       self.clconst.quarantine_refresh):
            change = self.clconst.ChangeType(row['change_type_id'])

            if not hasattr(self.ac, 'entity_id'):
                self.logger.debug(
                    "Can only handle %s for accounts, entity_id: %s",
                    change, row['subject_entity'])
                # Remove the event, since we can't do anything about it. Also,
                # the fullsync will take care of any weird situations.
                return True
            if not self.ac.has_spread(self.config['target_spread']):
                self.logger.debug("Account %s without target_spread, ignoring",
                                  row['subject_entity'])
                # The fullsync takes care of disabling accounts without AD
                # spread.
                return True

            ent = self.cache_entity(self.ac.entity_id,
                                    self.ac.account_name)

            # TODO/TBD: Should we trigger the enable/disable scripts here? We
            # have no AD-object to pass to the self.script function...
            #     simple_object = dict(DistinguishedName=ent.dn)
            #     self.*able_object(simple_object)

            if QuarantineHandler.check_entity_quarantines(
                    self.db, self.ac.entity_id).is_locked():
                return self.server.disable_object(ent.dn)
            else:
                return self.server.enable_object(ent.dn)

        # Other change types handled by other classes:
        return super(UserSync, self).process_cl_event(row)


class GroupSync(BaseSync):

    """Sync for Cerebrum groups in AD.

    This contains generic functionality for handling groups for AD, to add more
    functionality you need to subclass this.

    TODO: Should subclasses handle distribution and security groups? How should
    we treat those? Need to describe it better the specifications!

    """

    # The default object class of the objects to work on. Used if not the
    # config says otherwise.
    default_ad_object_class = 'group'

    def __init__(self, *args, **kwargs):
        """Instantiate group specific functionality."""
        super(GroupSync, self).__init__(*args, **kwargs)
        self.gr = Factory.get("Group")(self.db)
        self.pe = Factory.get("Person")(self.db)
        self.ac = Factory.get("Account")(self.db)

    def configure(self, config_args):
        """Add extra configuration that is specific for groups.

        @type config_args: dict
        @param config_args:
            Configuration data from cereconf and/or command line options.

        """
        super(GroupSync, self).configure(config_args)

        # Check if the group type is a valid type:
        if self.config['group_type'] not in ('security', 'distribution'):
            raise Exception('Invalid group type: %s' %
                            self.config['group_type'])
        self.new_group_type = self.config['group_type'].lower()
        # Check if the group scope is a valid scope:
        if self.config['group_scope'].lower() not in ('global', 'universal'):
            raise Exception('Invalid group scope: %s' %
                            self.config['group_scope'])
        self.new_group_scope = self.config['group_scope'].lower()

    def process_ad_object(self, ad_object):
        """Process a Group object retrieved from AD.

        Do the basic sync and update the member list for the group.

        """
        if not super(GroupSync, self).process_ad_object(ad_object):
            return False
        # ent = self.adid2entity.get(ad_object['Name'].lower())
        # dn = ad_object['DistinguishedName']  # TBD: or 'Name'?
        # TODO: more functionality for groups?

    def post_process(self):
        """Extra sync functionality for groups."""
        super(GroupSync, self).post_process()

    def fetch_cerebrum_data(self):
        """Fetch data from Cerebrum that is needed for syncing groups.

        What kind of data that should be gathered is up to what attributes are
        set in the config to be exported. There's for instance no need to fetch
        titles if the attribute Title is not used. Subclasses could however
        override this, if they need such data for other usage.

        """
        super(GroupSync, self).fetch_cerebrum_data()
        self.fetch_posix()
        self.fetch_members_by_spread()

    def fetch_cerebrum_entities(self):
        """Fetch the groups from Cerebrum that should be compared against AD.

        The configuration is used to know what to cache. All data is put in a
        list, and each entity is put into an object from
        L{Cerebrum.modules.ad2.CerebrumData} or a subclass, to make it easier
        to later compare with AD objects.

        Could be subclassed to fetch more data about each entity to support
        extra functionality from AD and to override settings.

        """
        self.logger.debug("Fetching groups with spread %s" %
                          (self.config['target_spread'],))
        subset = self.config.get('subset')
        if hasattr(self.co, 'trait_group_exempt'):
            for row in self._entity_trait.list_traits(
                    self.co.trait_group_exempt):
                self.exempt_entities.append(int(row['entity_id']))
        for row in self.gr.search(spread=self.config['target_spread']):
            name = row["name"]
            # For testing or special cases where we only want to sync a subset
            # of entities. The subset should contain the entity names, e.g.
            # usernames or group names.
            if subset and name not in subset:
                continue
            self.entities[name] = self.cache_entity(
                int(row['group_id']),
                name,
                description=row['description'])

    def _configure_group_member_spreads(self):
        """Process configuration and set needed parameters for extracting
        extra AD information about group members with needed spreads.

        """

        self.config['group_member_spreads'] = dict()
        # There is sanity check. All spreads defined in MemberAttr should have
        # their own syncs defined too
        for member_atr in ConfigUtils.get_config_by_type(
                self.config['attributes'], ConfigUtils.MemberAttr):
            for spr in member_atr.member_spreads:
                spr_name = str(spr)
                if spr_name not in adconf.SYNCS:
                    raise Exception(
                        "Illegal spread in 'Member' attribute: %s. Only"
                        " spreads that have their own sync configured can be"
                        " used in the attribute" % spr_name)
                if spr_name == self.config['target_spread']:
                    mem_obj = self
                    mem_config = self.config
                else:
                    mem_obj = self.get_class(sync_type=spr_name)(self.db,
                                                                 self.logger)
                    mem_config = adconf.SYNCS[spr_name].copy()
                    # Drain the list of attributes, to avoid fetching too much
                    # data we don't need when running the sync:
                    mem_config['attributes'] = {}
                    mem_config['sync_type'] = spr_name
                    mem_obj.configure(mem_config)
                self.config['group_member_spreads'][spr_name] = {
                    'config': mem_config,
                    'spread': spr,
                    'sync': mem_obj, }

    def _fetch_group_member_entities(self):
        """Extract entities with needed spreads and make AD objects out of them.

        """
        self.id2extraentity = dict()
        # Need to process spreads one by one, since each has its config
        for spread_var in self.config['group_member_spreads'].itervalues():
            spread = spread_var['spread']
            self.logger.debug("Fetch members for spread: %s", spread)
            mem_sync = spread_var['sync']
            # Fetch Cerebrum data for all sync classes except for self:
            if mem_sync != self:
                self.logger.debug2("Starting member's sync of: %s", mem_sync)
                mem_sync.fetch_cerebrum_data()
                mem_sync.calculate_ad_values()
                self.logger.debug2("Member sync done")
            self.id2extraentity.update(mem_sync.id2entity)

    def _fetch_person2primary_mapping(self):
        """Generate a mapping from person id to its primary account id.

        TODO: This might be moved upwards to the L{BaseSync} if needed in syncs
        of other entity types.

        """
        self.logger.debug2('Fetch mapping of person ids to primary accounts')
        # Only fetch the list once
        if getattr(self, 'personid2primary', False):
            return
        self.personid2primary = dict((r['person_id'], r['account_id'])
                                     for r in self.ac.list_accounts_by_type(
                                         primary_only=True))
        # A small optimisation could be to specify account_spreads for only
        # returning the accounts we really need.
        self.logger.debug2('Found %d persons mapped to a primary account',
                           len(self.personid2primary))

    def _get_group_hierarchy(self, person2primary=False):
        """Get mappings of every group and every membership.

        This is a costly method, as its fetches _all_ groups and _all_ its
        memberships from the database. This took for instance 25 seconds for
        10000 groups in the test environment. The advantage of this is that we
        cache the data you would otherwise need to ask the db about for each
        group.

        TODO: Note that we are, by specifying L{person2primary} here,
        overriding the person2primary setting for all member attributes, and
        does not respect each attribute's setting of this. Might need to handle
        this later, and not set it globally.

        @type person2primary: bool
        @param person2primary:
            If set to True, every person that is a member is swapped out with
            its primary account from the L{self.personid2primary} dict.

        @rtype: tuple(dict, dict)
        @return:
            Two mappings, one from group_id to all its member_ids, and one from
            member_id to all its group_ids. Both dicts contain the same data,
            but both is returned for convenience.

        """
        groups = dict()
        mem2group = dict()
        for row in self.gr.search_members():
            # TODO: Should we skip entities not in either self.id2entity nor
            # self.id2extraentity?
            groups.setdefault(row['group_id'], set()).add(row['member_id'])
            if person2primary and row['member_type'] == self.co.entity_person:
                # Add persons by their primary account. Note that the primary
                # account must also have the correct AD spread to be added.
                account_id = self.personid2primary.get(row['member_id'])
                if account_id:
                    self.logger.debug3("Adding person %s by primary: %s",
                                       row['member_id'], account_id)
                    mem2group.setdefault(account_id,
                                         set()).add(row['group_id'])
                else:
                    self.logger.debug2("Person %s has no primary account",
                                       row['member_id'])
            else:
                mem2group.setdefault(row['member_id'],
                                     set()).add(row['group_id'])
        return groups, mem2group

    def fetch_members_by_spread(self):
        """Fetch the group members by the member spreads defined by the config.

        This method only fetches what is needed. It will not fetch anything if
        no L{MemberAttr} attribute is defined.

        """
        if not ConfigUtils.has_config(self.config['attributes'],
                                      ConfigUtils.MemberAttr):
            # No need for such data
            return
        self.logger.debug("Fetch group members by spreads...")
        self._configure_group_member_spreads()
        self._fetch_group_member_entities()
        person2primary = False
        if any(c.person2primary for c
               in ConfigUtils.get_config_by_type(self.config['attributes'],
                                                 ConfigUtils.MemberAttr)):
            person2primary = True
            self._fetch_person2primary_mapping()
        # Cache all group memberships:
        groups, mem2group = self._get_group_hierarchy(person2primary)
        self.logger.debug2("Mapped %d groups with members", len(groups))
        self.logger.debug2("Mapped %d groups with AD spread",
                           len(filter(lambda x: x in self.id2entity, groups)))
        self.logger.debug2("Mapped %d members in total", len(mem2group))

        def get_parents_in_ad(groupid):
            """Helper method for returning a group's parent AD groups.

            You will get a list of all the groups that is in this AD-sync, i.e.
            has the correct AD spread, and which has the given group as a
            direct or indirect member.

            @type groupid: int
            @param groupid:
                The given group's entity_id.

            @rtype: set
            @return:
                List of all the group-ids of the groups that has the given
                group as a member, either direct or indirect. Could return an
                empty set if no parents were found, or none of the parent
                groups were targeted in the AD sync.

            """
            ret = set()
            for parent in mem2group.get(groupid, ()):
                # Check if already processed, to avoid loops caused by two
                # groups being (indirect) members of each others:
                if parent in ret:
                    continue
                if parent in self.id2entity:
                    ret.add(parent)
                ret.update(get_parents_in_ad(parent))
            return ret

        # Go through all group memberships and add those relevant for AD in the
        # proper groups, either directly or indirectly:
        i = 0
        for group_id, members in groups.iteritems():
            # Target the parent groups if the group is not supposed to be in
            # AD:
            if group_id in self.id2entity:
                target_groups = (group_id,)
            else:
                target_groups = get_parents_in_ad(group_id)
            if not target_groups:
                continue
            # Go through each member in the group and add it to all the parent
            # groups that should be in AD:
            for mem in members:
                # Select the primary account if the member is a person. If the
                # member is some other entity, use the member:
                if getattr(self, 'personid2primary', False):
                    mem = self.personid2primary.get(mem, mem)
                member = self.id2extraentity.get(mem)
                if not member:
                    continue
                for t_id in target_groups:
                    ent = self.id2entity[t_id]
                    if not hasattr(ent, 'members_by_spread'):
                        # TODO: might want a set or something similar:
                        ent.members_by_spread = []
                    ent.members_by_spread.append(member)
                    self.logger.debug3("Added %s to group %s (originally in %s)",
                                       member, ent, group_id)
                    i += 1
        self.logger.debug2("Fetched %d memberships", i)

    def fetch_posix(self):
        """Fetch the POSIX data for groups, if needed.

        """
        if not ConfigUtils.has_config(self.config['attributes'],
                                      ConfigUtils.PosixAttr):
            # No need for any posix data
            return
        self.logger.debug("Fetch posix data...")
        pg = Factory.get('PosixGroup')(self.db)
        i = 0
        for row in pg.list_posix_groups():
            ent = self.id2entity.get(row['group_id'], None)
            if ent:
                if not hasattr(ent, 'posix'):
                    ent.posix = {}
                ent.posix['gid'] = int(row['posix_gid']) or ''
                i += 1
        self.logger.debug("Found %d posix groups", i)

    def start_fetch_ad_data(self, object_class=None, attributes=dict()):
        """Ask AD to start generating the data we need about groups.

        Could be subclassed to get more/other data.

        TODO: add attributes and object_class and maybe other settings as input
        parameters.

        @rtype: string
        @return:
            A CommandId that is the servere reference to later get the data
            that has been generated.

        """
        # TODO: some extra attributes to add?
        return super(GroupSync, self).start_fetch_ad_data(
            object_class=object_class, attributes=attributes)

    def sync_ad_attribute(self, ent, attribute, cere_elements, ad_elements):
        """Compare a given attribute and update AD with the differences.

        This is a generic method for updating any multivalued attribute in AD.
        The given data must be given.

        """
        # TODO
        pass


class HostSync(BaseSync):

    """Sync for Cerebrum hosts to 'computer' objects in AD.

    This contains simple functionality for adding hosts to AD. Note that this
    only creates the Computer object in AD, without connecting it to a real
    host. That normally happens by manually authenticating the computer in the
    domain.

    """

    # The default object class of the objects to work on. Used if not the
    # config says otherwise.
    default_ad_object_class = 'computer'

    def __init__(self, *args, **kwargs):
        """Instantiate host specific functionality."""
        super(HostSync, self).__init__(*args, **kwargs)
        self.host = Factory.get("Host")(self.db)

    def fetch_cerebrum_entities(self):
        """Fetch the entities from Cerebrum that should be compared against AD.

        The configuration is used to know what to cache. All data is put in a
        list, and each entity is put into an object from
        L{Cerebrum.modules.ad2.CerebrumData} or a subclass, to make it easier
        to later compare with AD objects.

        Could be subclassed to fetch more data about each entity to support
        extra functionality from AD and to override settings.
        """
        self.logger.debug("Fetching hosts with spread: %s" %
                          (self.config['target_spread'],))
        subset = self.config.get('subset')
        for row in self.host.search(self.config['target_spread']):
            name = row["name"]
            if subset and name not in subset:
                continue
            self.entities[name] = self.cache_entity(int(row["host_id"]), name,
                                                    row['description'])


class MailTargetSync(BaseSync):

    """Extra sync functionality for getting MailTarget data.

    Entities could be connected to mailtargets in Cerebrum, e.g. with e-mail
    addresses, e-mail quota and spam settings. The retrievement of this data
    should be done in this class.

    """
    def __init__(self, *args, **kwargs):
        """Instantiate the MailTarget objects."""
        super(MailTargetSync, self).__init__(*args, **kwargs)
        self.mailtarget = Email.EmailTarget(self.db)
        self.mailquota = Email.EmailQuota(self.db)

    def fetch_cerebrum_data(self):
        """Fetch the needed mail data for the entities."""
        super(MailTargetSync, self).fetch_cerebrum_data()

        # Map from target_id to entity_id:
        targetid2entityid = dict((r['target_id'], r['target_entity_id']) for r
                                 in self.mailtarget.list_email_targets_ext())
        for target_id, entity_id in targetid2entityid.iteritems():
            ent = self.entities.get(entity_id)
            if ent:
                ent.maildata['target_id'] = target_id

        # E-mail quotas:
        for row in self.mailquota.list_email_quota_ext():
            if row['target_id'] not in targetid2entityid:
                self.logger.debug2("Ignoring quotas for non-cached target: %s",
                                   row['target_id'])
                continue
            ent = self.id2entity.get(targetid2entityid[row['target_id']])
            if ent:
                ent.maildata['quota_soft'] = row['quota_soft']
                ent.maildata['quota_hard'] = row['quota_hard']


class ProxyAddressesCompare(BaseSync):

    """Entities that have ProxyAddresses attribute should have a special
    entity comparison routine.

    """
    def attribute_mismatch(self, ent, atr, c, a):
        """Compare an attribute between Cerebrum and AD.

        Overridden to handle ProxyAddresses specifically.

        The ProxyAddresses attribute is also updated by Office365, with
        addresses starting with x500. We should ignore such attributes when
        comparing, to avoid having to update 20000 objects at each run. We
        should only take care of SMTP addresses.

        TODO: We should rather have this configurable instead of hardcoding it.

        """
        if atr.lower() == 'proxyaddresses' and c and a:
            advalues = list(v for v in a if not v.startswith('x500:'))
            cevalues = list(c)
            to_add = set(cevalues).difference(advalues)
            to_remove = set(advalues).difference(cevalues)
            return (to_add or to_remove, list(to_add), list(to_remove))
        return super(ProxyAddressesCompare, self).attribute_mismatch(ent, atr,
                                                                     c, a)

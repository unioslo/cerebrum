#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 
# Copyright 2011-2013 University of Oslo, Norway
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
  than just new attributes. Examples: Exchange, home directories and maybe Lync.

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
import pickle

import cerebrum_path
import adconf

from Cerebrum.Utils import unicode2str, Factory, dyn_import, sendmail
from Cerebrum import Entity, Errors
from Cerebrum.modules import CLHandler
from Cerebrum.modules import Email

from Cerebrum.modules.ad2 import ADUtils, ConfigUtils
from Cerebrum.modules.ad2.CerebrumData import CerebrumEntity
from Cerebrum.modules.ad2.CerebrumData import CerebrumUser
from Cerebrum.modules.ad2.CerebrumData import CerebrumGroup
from Cerebrum.modules.ad2.CerebrumData import CerebrumDistGroup
from Cerebrum.modules.ad2.winrm import PowershellException

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
            - If not active in Cerebrum, disable/move object in AD, according to
              what the config says.
            - Gets moved to correct OU if put somewhere else, but only if config
              says so.
            - Attributes gets compared. Those in AD not equal to Cerebrum gets
              updated.
            - Subclasses could add more functionality.
        - Remaining entities that was not found in AD gets created in AD.
    3. At quicksync:
        - TODO

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
    settings_required = ('domain', 'server', 'target_type', 'target_ou',
                         'search_ou', 'object_classes')

    # Settings with default values. If any of these settings are not defined in
    # the config for the given AD-sync, they will instead get their default
    # value. Note that subclasses must define their own list for their own
    # values.
    settings_with_default = (('dryrun', False),
                             ('target_spread', None),
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
                             # ('first_run', False), # should we support this?
                             ('store_sid', False),
                             ('handle_unknown_objects', ('disable', None)),
                             ('handle_deactivated_objects', ('disable', None)),
                             ('language', ('nb', 'nn', 'en')),
                             ('changes_too_old_seconds', 60*60*24*365*2), # 2 years
                             # TODO: move these to GroupSync when we have a
                             # solution for it.
                             ('group_type', 'security'),
                             ('group_scope', 'global'),
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

        @type db: Cerebrum.CLDatabase.CLDatabase
        @param db: The Cerebrum database connection that should be used.

        @type logger: Cerebrum.modules.cerelog.CerebrumLogger
        @param logger: The Cerebrum logger to use.

        """
        super(BaseSync, self).__init__()

        self.db = db
        self.logger = logger
        self.co = Factory.get("Constants")(self.db)
        self.ent = Factory.get('Entity')(self.db)
        self._ent_extid = Entity.EntityExternalId(self.db)

        # Where the sync configuration should go:
        self.config = dict()
        # Where the entities to work on should go. Keys should be entity_names:
        self.entities = dict()
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
        synchronisation class with the features that is needed without having to
        hardcode it.

        All the given class names gets imported before a new class is created
        out of them. Note that this class is automatically inherited in the
        list.

        Note that the order of the classes are important if they are related to
        each others by subclassing. You can not list class A before subclasses
        of the class A, as that would mean the subclass won't override any of
        A's methods. The method would then raise an exception.

        @type sync_type: string
        @param sync_type: The name of a AD-sync type which should be defined in the
            AD configuration. If given, the classes defined for the given type
            will be used for setting up the sync class. This parameter gets
            ignored if L{classes} is set.

        @type classes: list or tuple
        @param classes: The names of all the classes that should be used in the
            sync class. If this is specified, the L{sync_type} parameter gets
            ignored. Example on classes:

                Cerebrum.modules.ad2.ADSync/UserSync
                Cerebrum.modules.no.uio.ADSync/UiOUserSync

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
        bases = []
        for c in classes:
            mod_name, class_name = c.split("/", 1)
            mod = dyn_import(mod_name)
            claz = getattr(mod, class_name)
            for override in bases:
                if issubclass(claz, override):
                    raise RuntimeError("Class %r should appear earlier in the "
                            "list, as it's a subclass of class %r." % (claz,
                                                                      override))
            bases.append(claz)
        bases.append(cls)
        if len(bases) == 1:
            return bases[0]
        else:
            # Dynamically construct a new class that inherits from all the
            # specified classes:
            return type('_dynamic_adsync_%s' % sync_type, tuple(bases), {})

    def configure(self, config_args):
        """Read configuration options from given arguments and config file.

        The configuration is for how the ADsync should behave and work. Could be
        subclassed to support more settings for subclass functionality.

        Defined basic configuration settings:

        - target_spread: Either a Spread constant or a list of Spread constants.
          Used to find what entities from Cerebrum to sync with AD.

        - root_ou (string): The root OU that should be searched for objects in
          AD.

        - target_ou (string): What OU in AD that should be set as the default OU
          for the objects.

        - handle_unknown_objects: What to do with objects that are not found in
          Cerebrum. Could either be missing spread, that they're deleted, or if
          they have never existed in Cerebrum. Entities in quarantine but with
          the correct target_spread are not affected by this.
          Values:
            ('deactivate, None) # Deactivate object. This is the default.
            ('move', OU)        # Deactivate object and move to a given OU.
            ('delete', None)    # Delete the object. Can't be restored.
            # TODO: more alternatives?

        - move_objects (bool): If objects in the wrong OU should be moved to the
          target_ou, or being left where it is. Other attributes are still
          updated for the object. Defaults to False.

        - attributes: The attributes to sync. Must be a dict with the name of
          the attributes as keys and the values is further config for the given
          attribute. The configuration is different per attribute.

        @type config_args: dict
        @param config_args: Configuration data that should be set. Overrides any
            settings that is found from config file (adconf). Unknown keys in
            the dict is not warned about, as it could be targeted at subclass
            configuration.

        """
        # Required settings. Will fail if not defined in the config:
        for key in self.settings_required:
            try:
                self.config[key] = config_args[key]
            except KeyError, e:
                raise Exception('Missing required config variable: %s' % key)
        # Settings which have default values if not set:
        for key, default in self.settings_with_default:
            self.config[key] = config_args.get(key, default)
        # The name of the sync:
        self.config['sync_type'] = config_args['sync_type']

        # The object class is generated dynamically, depending on the given list
        # of classes:
        self.logger.debug("Using object classes: %s",
                          ', '.join(config_args['object_classes']))
        bases = []
        for c in config_args['object_classes']:
            mod_name, class_name = c.split("/", 1)
            mod = dyn_import(mod_name)
            claz = getattr(mod, class_name)
            for override in bases:
                if issubclass(claz, override):
                    raise RuntimeError("Class %r should appear earlier in the "
                            "list, as it's a subclass of class %r." % (claz,
                                                                      override))
            bases.append(claz)
        if len(bases) == 1:
            self._object_class = bases[0]
        else:
            # Dynamically construct a new class that inherits from all the
            # specified classes:
            self._object_class = type('_dynamic_adobject_%s' %
                                            self.config['sync_type'],
                                      tuple(bases), {})

        # Spread is changed into the spread constant, if set
        if self.config['target_spread']:
            self.config['target_spread'] = self.co.Spread(
                                                   config_args['target_spread'])
        # Convert the entity_type into the type constant
        self.config['target_type'] = self.co.EntityType(
                                                     self.config['target_type'])
        # Languages are changed into the integer of their constants
        self.config['language'] = tuple(int(self.co.LanguageCode(l)) for l in
                                        self.config['language'])
        # Change-types are changed into their constants
        self.config['change_types'] = tuple(self.co.ChangeType(*t) for t in
                                            config_args.get('change_types', ()))
        # Set the correct port
        if config_args.has_key('port'):
            self.config['port'] = config_args['port']
        else:
            self.config['port'] = 5986
            if not self.config['encrypted']:
                self.config['port'] = 5985

        if self.config['subset']:
            self.logger.info("Sync will only be run for subset: %s",
                             self.config['subset'])
        # Log if in dryrun
        if self.config['dryrun']:
            self.logger.info('In dryrun mode, AD will not be updated')

        # TODO: Check the attributes?

        # Messages for AD-administrators should be logged if the config says so,
        # or if there are no other options set:
        self.config['log_ad_admin_messages'] = False
        if (not self.config['ad_admin_message'] or
                any(o in (None, 'log') for o in
                    self.config['ad_admin_message'])):
            self.config['log_ad_admin_messages'] = True

        if self.config['store_sid']:
            converted = dict()
            for e_type, sid_type in self.sidtype_map.iteritems():
                converted[self.co.EntityType(e_type)] = \
                        self.co.EntityExternalId(sid_type)
            self.sidtype_map = converted

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
        # Check the case of the attributes. They should all start with an
        # uppercased letter, to match how the names are returned from AD.
        # TODO: This might not be correct for all attributes, unfortunately...
        for a in self.config['attributes']:
            if a[0] != a[0].upper():
                self.logger.warn('Attribute not capitalized: %s' % a)
            # TODO: match with ADAttributeConstants?

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

        # The name_format must include the %s for the entity_name to be put in:
        if '%s' not in self.config.get('name_format', '%s'):
            self.logger.warn("Missing '%s' in name_format, name not included")

        for handl in ('handle_unknown_objects', 'handle_deactivated_objects'):
            var = self.config[handl]
            if var[0] not in ('ignore', 'disable', 'move', 'delete'):
                raise Exception("Bad configuration of %s - set to: %s" % (handl,
                                                                          var))

        # Check that all the defined change_types exists:
        for change_type in self.config.get('change_types', ()):
            int(change_type)

        # TODO: add more checks here

        # TODO: move the instantiation of the server to somewhere else!
        self.setup_server()

    def setup_server(self):
        """Instantiate the server class to use for WinRM."""
        self.server = self.server_class(logger=self.logger,
                              host=self.config['server'], 
                              port=self.config.get('port'),
                              auth_user=self.config.get('auth_user'),
                              domain_admin=self.config.get('domain_admin'),
                              encrypted=self.config.get('encrypted', True),
                              ca=self.config.get('ca', None),
                              client_cert=self.config.get('client_cert', None),
                              client_key=self.config.get('client_key', None),
                              dryrun=self.config['dryrun'])

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
                    except Exception, e:
                        self.logger.warn("Error sending AD-messages to %s: %s" %
                                         (address, e))
            elif opt[0] == 'file':
                self.logger.warn("Sending AD-admin messages to file not implemented")
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

    def quicksync(self, changekey):
        """Do a quicksync, by sending the latest changes to AD.

        All events of the given change_types are processed generically, and in
        chronologically order.

        Subclasses should rather override the methods that this method calls
        instead of overring all of this method, as that is easier. Unless, of
        course, you want to completely rewrite the behaviour of the quicksync.

        The quicksync is going through L{change_log} for new events that has not
        been marked as commited by the given L{changekey}. The list is processed
        in reverse, so that equeal events are only processed once.

        @type changekey: string
        @param changekey: The change-log key to mark the events as commited or
            not. Must be unique per job, unless you're in for race conditions
            and skipped events.

        """
        self.logger.info("Quicksync started")
        cl = CLHandler.CLHandler(self.db)
        changetypes = self.config['change_types']
        already_handled = set()

        # Avoid changes that are too old:
        too_old = time.time() - self.config['changes_too_old_seconds']

        int(time.mktime(time.strptime('20120301', '%Y%m%d')))

        # We do it in the correct order, as the changes could be dependend of
        # each other.
        events = cl.get_events(changekey, changetypes)
        self.logger.debug("Found %d of changes to process", len(events))
        nr_processed = 0
        for row in events:
            if int(row['change_type_id']) not in changetypes:
                # TODO: Shouldn't happen - remove this check?
                self.logger.warn("Unknown change_type_id %i" %
                                   row['change_type_id'])
                cl.confirm_event(row)
                continue

            # Skip too old changes:
            if int(row['tstamp']) < too_old:
                cl.confirm_event(row)
                continue

            # TODO: split up the input variables?
            if self.process_cl_event(row):
                nr_processed += 1
                cl.confirm_event(row)
            # TODO: put it inside on a try..except later, when done testing -
            # would then avoid that a small problem blocks for all changes!
            if not self.config['dryrun']:
                cl.commit_confirmations()
        if not self.config['dryrun']:
            cl.commit_confirmations()
            self.logger.info("Commited events for changekey: %s", changekey)
        self.logger.debug("Successfully processed %d events", nr_processed)
        self.logger.info("Quicksync done")
        self.send_ad_admin_messages()

    def process_cl_event(self, row):
        """Process a given event by calling the change type's handler. The
        handlers must be methods in the class with the name format:

            changelog_handle_<category>(self, changetype, db-row)

        If such a method exists, it gets called. If it doesn't exist, it's
        logged as a warning and it returns False, so it could be redone when the
        error is fixed. Log changes that shouldn't be handled should not be put
        in adconf.SYNCS[<sync_type>][change_types].

        @type row: dict of db-row
        @param row: A db-row, as returned from L{changelog.get_events()}. This
            is the row that should be processed.

        @rtype: bool
        @return: The result from the handler. Should be True if the sync
            succeeded or there was no need for the change to be synced, i.e. the
            log change could be confirmed. Should only return False if the
            change needs to be redone.

        """
        ctype = self.co.ChangeType(int(row['change_type_id']))
        func_name = 'changelog_handle_%s' % (ctype.category,)
        method = getattr(self, func_name, None)
        # TODO: if want to get entity and print out name, use
        # cereconf.ENTITY_TYPE_NAMESPACE.
        if not method:
            self.logger.warn("No handler for changelog category: %s", func_name)
            return False
        self.logger.debug("Processing log change %s:%s for entity %s",
                          ctype.category, ctype.type, row['subject_entity'])
        return method(ctype, row)

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
        self.name2entity = dict((self.entities[e].entity_name, self.entities[e])
                              for e in self.entities)
        # Make a mapping from ad_id to the entity:
        self.adid2entity = dict((self.entities[e].ad_id, self.entities[e])
                                for e in self.entities)
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
        # TODO: is it okay to make use of the EntityQuarantine class like this?
        # Or is it okay to add EntityQuarantine to cereconf.CLASS_ENTITY, so we
        # could get it from Factory.get('Entity') instead? We could then ignore
        # deactivation for those instances which doesn't use quarantines.
        ent = Entity.EntityQuarantine(self.db)

        # Limit the search to the entity_type the target_spread is meant for:
        target_type = self.config['target_type']

        i = 0
        for row in ent.list_entity_quarantines(only_active=True,
                                               entity_types=target_type):
            found = self.id2entity.get(int(row['entity_id']))
            if found:
                found.active = False
                i += 1
        self.logger.debug("Flagged %d entities as deactivated" % i)

    def fetch_spreads(self):
        """Get all spreads from Cerebrum and update L{self.entities} with this.

        The spreads _could_ be used for updating various attributes or not
        depending on if an entity should be available in different AD systems,
        e.g. Exchange, Lync and Sharepoint.

        """
        self.logger.debug("Fetch spreads for target type %s...", self.config['target_type'])
        if not self.config['target_type']:
            # Don't know what spreads to fetch if we don't know the entity type.
            return
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
        self.logger.debug("Fetch attributes...")
        i = 0
        # TODO: fetch only the attributes defined in config - would be faster
        for row in self.ent.list_ad_attributes(spread=self.config['target_spread']):
            # TODO: is co caching such attributes? if not, we should prefetch
            # it, or make the new list method support fetching it:
            attr = self.co.ADAttribute(int(row['attr_code']))
            if str(attr) not in self.config['attributes']:
                continue
            e = self.id2entity.get(row['entity_id'], None)
            if e:
                if attr.multivalued:
                    e.attribues.setdefault(str(attr), []).append(row['value'])
                else:
                    e.attributes[str(attr)] = row['value']
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
        for row in en.list_external_ids(source_system=self.co.system_ad,
                                        id_type=id_type):
            # TODO: how should we get it per spread?
            e = self.id2entity.get(row['entity_id'], None)
            if e:
                e.sid = row['external_id']
                i += 1
        self.logger.debug("Fetched %d SIDs from Cerebrum" % i)

    def fetch_names(self):
        """Get all the entity names for the entitites from Cerebrum.

        """
        self.logger.debug("Fetch name information...")
        variants = set()
        systems = set()
        languages = set()
        all_systems = False
        # Go through config and see what info needs to be fetched:
        for atr in self.config['attributes'].itervalues():
            if isinstance(atr, ConfigUtils.NameAttr):
                variants.update(atr.name_variants)
                if atr.source_systems is None:
                    all_systems = True
                else:
                    systems.update(atr.source_systems)
                if atr.languages:
                    languages.update(atr.languages)
        if not variants:
            return
        if all_systems or not systems:
            # By setting to None we fetch from all source_systems.
            systems = None
        if not languages:
            # By setting to None we fetch all languages:
            languages = None
        i = 0
        for row in self.ent.search_name_with_language(name_variant=variants,
                    entity_type=self.config['entity_type'],
                    name_language=languages):
            for ent in self.owner2ent.get(row['entity_id'], ()):
                vari = str(self.co.EntityNameCode(row['name_variant']))
                lang = str(self.co.LanguageCode(row['name_language']))
                ent.entity_name_with_language.setdefault(vari, {})[lang] = row['name']
                i += 1
        self.logger.debug("Found %d names" % i)

    def calculate_ad_values(self):
        """Use Cerebrum data to calculate the needed attributes.

        """
        for ent in self.entities.itervalues():
            ent.calculate_ad_values() # exchange=self.exchange_sync)

    def cache_entity(self, entity_id, entity_name, *args, **kwargs):
        """Wrapper method for creating a cache object for an entity. 
        
        The object class is created dynamically, depending on the config and
        what subclasses of the sync is in use. This method returns an object
        out of the correct classes.

        You should call this method for new cache objects instead of creating it
        directly, for easier subclassing.

        @type entity_id: int
        @param entity_id: The entity's entity_id

        @type entity_name: str or unicode
        @param entity_name: The entity's name, normally the entity_name.

        @type *args: mixed
        @param *args: More arguments that should be passed on to the object at
            instantiation.

        @type *kwargs: mixed
        @param *kwargs: More arguments that should be passed on to the object at
            instantiation.

        @rtype: Cerebrum.modules.ad2.CerebrumData.CerebrumEntity
        @return: A proper instantiated subclass for L{CerebrumEntity}.

        """
        return self._object_class(self.logger, self.config, entity_id,
                                  entity_name, *args, **kwargs)

    def start_fetch_ad_data(self, object_type=None, attributes=dict()):
        """Send request(s) to AD to start generating the data we need.

        Could be subclassed to get more/other data.

        @type object_type: Constant of EntityTypeCode
        @param object_type: The type of objects that should be returned from AD.
            If not set, the value in L{config['target_type']} is used.

        @type attributes: list
        @param attributes: Extra attributes that should be retrieved from AD.
            The attributes defined in the config is already set.

        @rtype: string
        @return: A CommandId that is the servere reference to later get the data
            that has been generated.

        """
        if not object_type:
            object_type = self.config['target_type']
        attrs = self.config['attributes'].copy()
        self.logger.debug2("Want to fetch the AD-attrs: %s", ', '.join(attrs))
        if attributes:
            attrs.update(attributes)
        # Some attributes are readonly, so they shouldn't be put in the list,
        # but we still need to receive them if they are used, like the SID.
        if self.config['store_sid'] and 'SID' not in attrs:
            attrs['SID'] = None
        return self.server.start_list_objects(ou = self.config['search_ou'],
                                              attributes = attrs,
                                              object_type = object_type)

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
                self.logger.debug2("Retrieved attributes: %s", ad_object.keys())
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
        """Compare an AD-object with Cerebrum and update AD with differences.

        Basic functionality for what to do with an object, compared to what is
        stored in Cerebrum. Could be subclassed to add more functionality. This
        command is called both when updating existing objects, but also if an
        entity didn't exist in AD and just got created.

        @type ad_object: dict
        @param ad_object: A dict with information about the AD object from AD.
            The dict contains mostly the object's attributes.

        """
        name = ad_object['Name']
        dn = ad_object['DistinguishedName']

        # TODO: remove when done debugging UAC
        # TODO XXX
        #if 'UserAccountControl' in ad_object:
        #    self.logger.debug("For %s UAC: %s" % (name,
        #                      ad_object['UserAccountControl']))

        ent = self.adid2entity.get(name)
        if ent:
            ent.in_ad = True
            ent.ad_data['dn'] = dn

        # Don't touch others than from the subset, if set:
        if self.config.get('subset'):
            # Convert names to comply with 'name_format':
            format = self.config.get('name_format', '%s')
            if name not in (format % s for s in self.config['subset']):
                #self.logger.debug("Ignoring due to subset: %s", name)
                return

        # Don't touch those in OUs we should ignore:
        if any(dn.endswith(ou) for ou in self.config.get('ignore_ou', ())):
            self.logger.debug('Object in ignore_ou: %s' % dn)
            return

        # If not found in Cerebrum, remove the object (according to config):
        if not ent:
            self.logger.debug2("Unknown object %s - %s" % (name, ad_object))
            self.downgrade_object(ad_object,
                                       self.config.get('handle_unknown_objects',
                                                       ('disable', None)))
            return

        # If not active in Cerebrum, do something (according to config):
        if not ent.active:
            self.downgrade_object(ad_object,
                                  self.config['handle_deactivated_objects'])
        else:
            if not ad_object.get('Enabled', True):
                # TODO: move this to its own method in this class, to be able to
                # modify the behaviour in subclasses.
                self.server.enable_object(dn)
        if self.config['move_objects']:
            self.move_object(ad_object, ent.ou)
            # Updating the DN, for later updates in the process:
            dn = ','.join((ad_object['DistinguishedName'].split(',')[0],
                           ent.ou))
            ad_object['DistinguishedName'] = dn

        # Compare attributes:
        self.compare_attributes(ent, ad_object)
        if ent.changes:
            self.server.update_attributes(dn, ent.changes['attributes'],
                                          ad_object)
        # Store SID in Cerebrum
        self.store_sid(ent, ad_object['SID'])

    def compare_attributes(self, ent, ad_object):
        """Compare entity's attributes between Cerebrum and AD.

        If the attributes exists in both places, it should be updated if it
        doesn't match. If it only exists

        The changes gets appended to the entity's change list for further
        processing.

        """
        for atr in self.config['attributes']:
            self.compare_attribute(ent, atr,
                                   ent.attributes.get(atr, None),
                                   ad_object.get(atr, None))

    def compare_attribute(self, ent, atr, c, a):
        """Compare an attribute between Cerebrum and AD and mark for update.
        """
        # TODO: Some attributes are special, should they be checked for and
        #       ignored here?
        # TODO: Multivalued attributes, how should we compare them? This is not
        # implemented yet.
        # TODO: Should we care about case sensitivity?

        # We can't get None values from AD (yet), so ignore the cases where an
        # attribute is None in Cerebrum and an empty string in AD:
        if c is None and a == '':
            return
        # TODO: Should we ignore attributes with extra spaces? AD converts
        # double spaces into single spaces, e.g. GivenName='First  Last' becomes
        # in AD 'First Last'. This is issues that should be fixed in the source
        # system, but the error will make the sync update the attribute
        # constantly and make the sync slower.

        # Integers are retrieved from AD as strings, so need to compare with
        # Cerebrum as strings:
        if isinstance(c, (int, long, float)) and not isinstance(c, bool):
            c = unicode(c)

        if c != a:
            self.logger.debug("Mismatch attr for %s: %s: '%s' (%s) -> '%s' (%s)"
                              % (ent.entity_name, atr, a, type(a), c, type(c)))
            ent.changes.setdefault('attributes', {})[atr] = c

    def changelog_handle_spread(self, ctype, row):
        """Handler for changelog events of category 'spread'.

        Syncs new changes that affects the spread and its entity. Example on
        change types in this category: add and delete. Not all types might be
        respected, but subclasses could override this.

        """
        en = Entity.EntityName(self.db)
        #self.ent.clear()
        try:
            en.find(row['subject_entity'])
            #self.ent.find(row['subject_entity'])
        except Errors.NotFoundError, e:
            self.logger.warn("Could not find entity: %s. Check if entity is nuked." %
                             row['subject_entity'])
            # TODO: ignore this? Are there other reasons than race conditions
            # when the entity is nuked from the database?

            # TODO: send a downgrade request about the object? Or should we
            # trust the fullsync to do this?
            return False

        # TODO: check the spread type - all other spreads than the target spread
        # gets ignored.

        if ctype == 'add':
            # TODO: create or recreate the object
            pass
        elif ctype == 'delete':
            # TODO: downgrade the object
            pass
        else:
            raise Exception('Unknown spread changetype %s for entity %s' % (
                            ctype, row['subject_entity']))
        return False

    def changelog_handle_quarantine(self, ctype, row):
        """Handler for changelog events of category 'quarantine'.

        Syncs new changes that affects the quarantine's entity. Example on
        change types in this category: add, refresh, mod and del. Not all types
        might be respected, but subclasses could override this.

        """
        en = Entity.EntityName(self.db)
        try:
            en.find(row['subject_entity'])
        except Errors.NotFoundError, e:
            self.logger.warn("Could not find entity: %s. Check if entity is nuked." %
                             row['subject_entity'])
            # TODO: ignore this? Are there other reasons than race conditions
            # when the entity is nuked from the database?

            # TODO: send a downgrade request about the object? Or should we
            # trust the fullsync to do this?
            return False

        # TODO: Check if entity is still in quarantine or not.
        is_quarantined = True
        if ctype == 'add' and is_quarantined:
            # TODO: downgrade object
            return False
        elif ctype == 'del' and not is_quarantined:
            # TODO: activate object
            return False
        # Other change types doesn't say if the entity got quarantined or not,
        # so have to update it in AD anyway.
        if is_quarantined:
            # TODO: downgrade object
            return False
        else:
            # TODO: activate object
            return False
        return False

    def changelog_handle_ad_attr(self, ctype, row):
        """Handler for changelog events of category 'ad_attr'.

        Syncs new changes that affects the attribute and its entity. Example on
        change types in this category: add and del. Not all types might be
        respected, but subclasses could override this.

        """
        # TODO: check if the updated attribute is defined in the config. Ignore
        # if not.

        en = Entity.EntityName(self.db)
        try:
            en.find(row['subject_entity'])
        except Errors.NotFoundError, e:
            self.logger.warn("Could not find entity: %s. Check if entity is nuked." %
                             row['subject_entity'])
            # TODO: ignore this? Are there other reasons than race conditions
            # when the entity is nuked from the database?

            # TODO: send a downgrade request about the object? Or should we
            # trust the fullsync to do this?
            return False

        # TODO: update attribute(s)

        # TODO
        self.logger.warn("change log ad_attr handle not implemented")
        return False

    def process_entities_not_in_ad(self):
        """Go through entities that wasn't processed while going through AD.

        This could mean that either the entity doesn't exist in AD and should be
        created, or that the object is in an OU that we are not processing.

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
            try:
                self.process_entity_not_in_ad(ent)
            except ADUtils.NoAccessException, e:
                # Access errors should be sent to the AD administrators, as
                # Cerebrum can not fix this.
                self.add_admin_message('warning',
                                       'Missing access rights for %s: %s' % (
                                       ent.ad_id, e))
            except PowershellException, e:
                self.logger.warn("PowershellException for %s: %s" %
                                 (ent.entity_name, e))
            else:
                i += 1
        self.logger.debug('Successfully processed %d entities not in AD' % i)

    def process_entity_not_in_ad(self, ent):
        """Process an entity that doesn't exist in AD, yet.

        The entity should be created in AD if active, and should then be updated
        as other, already existing objects.
        
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
            ent.ad_new = True
        except ADUtils.OUUnknownException, e:
            self.logger.info("OU was not found: %s", self.config['target_ou'])
            if not self.config['create_ous']:
                raise e
            ou_name, path = self.config['target_ou'].split(',', 1)
            # TODO: we should probably have helper method for getting data out
            # of paths and OUs
            ou_name = ou_name.replace('OU=', '')
            ou_obj = self.server.create_object(ou_name, path,
                                               object_type=self.co.entity_ou)
            # Then retry creating the object:
            obj = self.create_object(ent)
            ent.ad_new = True
        except ADUtils.ObjectAlreadyExistsException, e:
            # It exists in AD, but is probably somewhere out of our search_base.
            # Will try to get it, so we could still update it, and maybe even
            # move it to the correct OU.
            self.logger.info("Entity already exists: %s", ent.entity_name)
            attrs = self.config['attributes'].copy()
            if self.config['store_sid'] and 'SID' not in attrs:
                attrs['SID'] = None
            obj = self.server.get_object(ent.ad_id,
                                         object_type=self.config['target_type'],
                                         attributes=attrs)
        # TODO: if commands should be executed for the new object now, we should
        # control what DC we connect to. The alternative is to sleep 5 seconds
        # before continuing, which slow the sync too much!

        if ent.ad_new:
            #if ent.ad_new and not self.config['dryrun']:
            #    self.logger.info("Sleeping, wait for AD to sync the controllers...")
            #    time.sleep(5)
            self.script('new_object', obj, ent)
        return obj

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
        # TODO: check if users get "Enabled" when this happens?
        return self.server.create_object(ent.ad_id,
                                         ent.ou,
                                         object_type=self.config['target_type'],
                                         attributes=ent.attributes,
                                         parameters=parameters)

    def downgrade_object(self, ad_object, action):
        """Do a downgrade of an object in AD. 
        
        The object could for instance be unknown in Cerebrum, or be inactive.
        The AD-object could then be disabled, moved and/or deleted, depending on
        the setting. The configuration says what should be done with such
        objects, as it could be disabled, moved, deleted or something else.

        @type ad_object: dict
        @param: The data about the AD-object to downgrade.

        @type action: tuple
        @param action: A two-element tuple, where the first element is a string,
            e.g. 'ignore', 'delete', 'move' or 'disable'. The second element
            contains extra information, e.g. to what OU the object should be
            moved to.

        """
        dn = ad_object['DistinguishedName']
        #conf = self.config.get('handle_unknown_objects', ('disable', None))
        if action[0] == 'ignore':
            # Do nothing
            return
        elif action[0] == 'disable':
            # TODO: note that this only works for accounts!
            if ad_object.get('Enabled') == 'False':
                return # already disabled
            self.server.disable_object(dn)
            self.script('disable_object', ad_object)
        elif action[0] == 'move':
            if ad_object.get('Enabled') != 'False':
                self.server.disable_object(dn)
                self.script('disable_object', ad_object)
            if not dn.endswith(action[1]):
                # TODO: test if this works as expected!
                self.move_object(ad_object, action[1])
            return True
        elif action[0] == 'delete':
            # TODO: danger, this should be tested more carefully!
            self.server.delete_object(dn)
            self.script('delete_object', ad_object)
        else:
            raise Exception("Unknown config for downgrading object %s: %s" %
                            (ad_object.get('Name'), action))

    def move_object(self, ad_object, ou):
        """Move a given object to the given OU.

        It is first checked for if it's already in the correct OU.

        @type ad_object: dict
        @param ad_object: The object as retrieved from AD.

        @type ou: string
        @param ou: The full DN of the OU the object should be moved to.

        """
        dn = ad_object['DistinguishedName']
        if dn.endswith(ou):
            return # Already in the correct location
        try:
            self.server.move_object(dn, ou)
        except ADUtils.OUUnknownException:
            if self.config['create_ous']:
                ou_name, path = ou.split(',', 1)
                ou_name = ou_name.replace('OU=', '')
                self.server.create_object(ou_name, path,
                                          object_type=self.co.entity_ou)
                self.server.move_object(dn, ou)
            else:
                raise
        self.script('move_object', ad_object, move_from=dn, move_to=ou)
        # TODO: update the ad_object with the new dn?

    def post_process(self):
        """Hock for things to do after the sync has finished.

        This could be used by subclasses to add more functionality to the sync.
        For example could a subclass run commands for objects that got updated.

        """
        pass

    def _old_compare_forwards(self, ad_contacts):
        # TODO: Move this to somewhere else?
        """
        Compare forward objects from AD with forward info in Cerebrum.

        @param ad_contacts: a dict of dicts wich maps contact obects
                            name to that objects properties (dict)
        @type ad_contacts: dict
        """
        for acc in self.accounts.itervalues():
            for contact in acc.contact_objects:
                cb_fwd = contact.forward_attrs
                ad_fwd = ad_contacts.pop(cb_fwd['sAMAccountName'], None)
                if not ad_fwd:
                    # Create AD contact object
                    self.create_ad_contact(cb_fwd, self.default_ou)
                    continue
                # contact object is in AD and Cerebrum -> compare OU
                # TBD: should OU's be compared?
                ou = cereconf.AD_CONTACT_OU
                cb_dn = 'CN=%s,%s' % (cb_fwd['sAMAccountName'], ou)
                if ad_fwd['distinguishedName'] != cb_dn:
                    self.move_contact(cb_dn, ou)

                # Compare other attributes
                for attr_type, cb_fwd_attr in fwd.iteritems():
                    ad_fwd_attr = ad_fwd.get(attr_type)
                    if cb_fwd_attr and ad_fwd_attr:
                        # value both in ad and cerebrum => compare
                        result = self.attr_cmp(cb_fwd_attr, ad_fwd_attr)
                        if result: 
                            self.logger.debug("Changing attr %s from %s to %s",
                                              attr, unicode2str(ad_fwd_attr),
                                              unicode2str(cb_fwd_attr))
                            cb_user.add_change(attr, result)
                    elif cb_fwd_attr:
                        # attribute is not in AD and cerebrum value is set => update AD
                        cb_user.add_change(attr, cb_fwd_attr)
                    elif ad_fwd_attr:
                        # value only in ad => delete value in ad
                        # TBD: is this correct behavior?
                        cb_user.add_change(attr,"")

            # Remaining contacts in AD should be deleted
            for ad_fwd in ad_contacts.itervalues():
                self.delete_contact()

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
        # Since external_id only works for one type of entities, we need to find
        # out which external_id type to store the SID as:
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
        params = {'Identity': ad_object.get('DistinguishedName',
                                            ad_object['Name'])}
        if extra:
            params.update(extra)
        try:
            return self.server.execute_script(self.config['script'][action],
                                              **params)
        except PowershellException, e:
            self.logger.warn("Script failed for %s of %s: %s" % (action,
                             ad_object['Name'], e))
            return False

class UserSync(BaseSync):
    """Sync for Cerebrum accounts in AD.

    This contains generic functionality for handling accounts for AD, to add
    more functionality you need to subclass this.

    A mapping is added by this class: L{owner2ent}, which is a dict with the
    owner's owner_id as key, and the values are lists of entity instances.

    """

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
            None, # 'Script',
            # 2. If the account is disabled. Set by Disable-ADAccount instead.
            None, # 'AccountDisabled',
            # 3. The home directory is required.
            'HomedirRequired',
            # 4. The account is currently locked out, e.g. by too many failed
            #    password attempts. Gets set and reset automatically by AD DS.
            None, # 'LockOut',
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
            None, # 'TempDuplicateAccount',
            # 9. A normal account. This is the default type of an account. Not
            #    implemented.
            None, # 'NormalAccount',
            # 10. Trusts the account for other domains. Not implemented.
            None, # 'InterdomainTrustAccount', 
            # 11. If set, this is a computer account. Not implemented. Needs to
            #     be set in other ways.
            None, # 'WorkstationTrustAccount',
            # 12. If set, this is a computer account for a system backup domain
            #     controller that is a member of this domain.
            None, # 'ServerTrustAccount',
            # 13. Not used
            None,
            # 14. Not used
            None,
            # 15. The password for the account will never expire.
            'PasswordNeverExpires',
            # 16. If set, this is an MNS logon account.
            'MNSLogonAccount',
            # 17. Force user to log on by smart card. Not implemented.
            None, # 'SmartcardRequired', 
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
            None, # 'PartialSecretsAccount', 
            )

    def __init__(self, *args, **kwargs):
        """Instantiate user specific functionality."""
        super(UserSync, self).__init__(*args, **kwargs)
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

    def start_fetch_ad_data(self, object_type=None, attributes=dict()):
        """Ask AD to start generating the data we need about groups.

        Could be subclassed to get more/other data.

        @rtype: string
        @return: A CommandId that is the reference from the AD service to later
            get the data that has been generated. Could be used for e.g.
            L{process_ad_data}.

        """
        # TODO: some extra attributes to add?
        if self.config['useraccountcontrol']:
            attributes['UserAccountControl'] = None
        return super(UserSync, self).start_fetch_ad_data(
                                                object_type=object_type,
                                                attributes=attributes)

    def fetch_cerebrum_data(self):
        """Fetch data from Cerebrum that is needed for syncing accounts.

        What kind of data that will be gathered is up to the attribute
        configuration. Contact info will for instance not be retrieved from
        Cerebrum if it's set for any attributes. Subclasses could however
        override this, if they need such data for other usage.

        """
        super(UserSync, self).fetch_cerebrum_data()

        # Create a mapping of owner id to user objects
        self.logger.debug("Fetch owner information...")
        self.owner2ent = dict()
        for ent in self.entities.itervalues():
            self.owner2ent.setdefault(ent.owner_id, []).append(ent)
        self.logger.debug("Mapped %d entity owners", len(self.owner2ent))

        # Set what is primary accounts.
        # TODO: We don't want to fetch this unless we really need the data,
        # since it takes some time to finish. How could be find its usage from
        # the config?
        for row in self.ac.list_accounts_by_type(primary_only=True):
            ent = self.id2entity.get(row['account_id'])
            if ent:
                ent.is_primary_account = True

        # The different methods decides if their data should be fetched or not,
        # depending on the attribute configuration.
        self.fetch_contact_info()
        self.fetch_names()
        self.fetch_external_ids()
        self.fetch_traits()
        self.fetch_address_info()
        self.fetch_mail()

    def fetch_cerebrum_entities(self):
        """Fetch the entities from Cerebrum that should be compared against AD.

        The configuration is used to know what to cache. All data is put in a
        list, and each entity is put into an object from
        L{Cerebrum.modules.ad2.CerebrumData} or a subclass, to make it easier to
        later compare them with AD objects.

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
        for row in self.ac.search(spread=self.config['target_spread']):
            uname = row["name"]
            # For testing or special cases where we only want to sync a subset
            # of entities. The subset should contain the entity names, e.g.
            # usernames or group names.
            if subset and uname not in subset:
                continue
            self.entities[uname] = self.cache_entity(int(row["account_id"]),
                                         uname, owner_id=int(row["owner_id"]),
                                         owner_type=int(row['owner_type']))

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

        # TODO: this first block should be removed when ent.name_first,
        # ent.name_last and ent.name_full is not used anymore, but is instead
        # using the more generic ConfigUtils.NameAttr.
        for row in self.pe.search_person_names(
                                    source_system = self.co.system_cached,
                                    name_variant  = [self.co.name_first,
                                                     self.co.name_last]):
            for ent in self.owner2ent.get(row['person_id'], ()):
                if int(row['name_variant']) == int(self.co.name_first):
                    ent.name_first = row['name']
                elif int(row['name_variant']) == int(self.co.name_last):
                    ent.name_last = row['name']


        variants = set()
        systems = set()
        languages = set()
        all_systems = False
        # Go through config and see what info needs to be fetched:
        for atr in self.config['attributes'].itervalues():
            if isinstance(atr, ConfigUtils.NameAttr):
                variants.update(atr.name_variants)
                if atr.source_systems is None:
                    all_systems = True
                else:
                    systems.update(atr.source_systems)
                if atr.languages:
                    languages.update(atr.languages)
        self.logger.debug2("Fetching person name variants: %s" % (variants,))
        self.logger.debug2("Fetching names by languages: %s" % (languages,))
        self.logger.debug2("Fetching names from sources: %s" % (systems,))
        if not variants:
            return
        if all_systems or not systems:
            # By setting to None we fetch from all source_systems.
            systems = None
        if not languages:
            languages = None
            # TODO: Or make use of self.config['language'] to get the priority
            # right?
            pass

        # Names stored in person table:
        i = 0
        for row in self.pe.search_person_names(source_system=systems,
                                               name_variant=variants):
            for ent in self.owner2ent.get(row['person_id'], ()):
                vari = str(self.co.PersonName(row['name_variant']))
                ssys = str(self.co.AuthoritativeSystem(row['source_system']))
                ent.person_names.setdefault(vari, {})[ssys] = row['name']
                i += 1
        # Names stored in the entity table (with languages):
        for row in self.pe.search_name_with_language(name_variant=variants,
                entity_type=self.co.entity_person, name_language=languages):
            for ent in self.owner2ent.get(row['entity_id'], ()):
                vari = str(self.co.EntityNameCode(row['name_variant']))
                lang = str(self.co.LanguageCode(row['name_language']))
                ent.entity_name_with_language.setdefault(vari, {})[lang] = row['name']
                i += 1
        self.logger.debug("Found %d person names" % i)

    def fetch_contact_info(self):
        """Fetch all contact information for users, e.g. mobile and telephone.

        """
        self.logger.debug("Fetch contact info...")
        types = set()
        systems = set()
        all_systems = False
        # Go through config and see what info needs to be fetched:
        for atr in self.config['attributes'].itervalues():
            if isinstance(atr, ConfigUtils.ContactAttr):
                types.update(atr.contact_types)
                if atr.source_systems is None:
                    all_systems = True
                else:
                    systems.update(atr.source_systems)
        self.logger.debug2("Fetching contact-types: %s" % (types,))
        self.logger.debug2("Fetching contactinfo from sources: %s" % (systems,))
        if not types:
            return
        if all_systems or not systems:
            # By setting to None we fetch from all source_systems.
            systems = None

        # Contact info stored on the person:
        i = 0
        for row in self.pe.list_contact_info(source_system=systems,
                                             entity_type=self.co.entity_person,
                                             contact_type=types):
            for ent in self.owner2ent.get(row['entity_id'], ()):
                ctype = str(self.co.ContactInfo(row['contact_type']))
                ssys = str(self.co.AuthoritativeSystem(row['source_system']))
                ent.contact_info.setdefault(ctype, {})[ssys] = row
                i += 1
        # Contact info stored on the account:
        for row in self.ac.list_contact_info(source_system=systems,
                                             entity_type=self.co.entity_account,
                                             contact_type=types):
            ent = self.id2entity.get(row['entity_id'], None)
            self.logger.debug2("Found contact for %s: %s", ent, row['contact_value'])
            if ent:
                ctype = str(self.co.ContactInfo(row['contact_type']))
                ssys = str(self.co.AuthoritativeSystem(row['source_system']))
                ent.contact_info[ctype][ssys] = row
                i += 1
        self.logger.debug("Found %d contact data" % i)

    def fetch_external_ids(self):
        """Fetch all external IDs for entities according to config.

        TODO: this should be moved upwards, as it's not only for users.

        """
        self.logger.debug("Fetch external ids...")
        types = set()
        systems = set()
        all_systems = False
        # Go through config and see what info needs to be fetched:
        for atr in self.config['attributes'].itervalues():
            if isinstance(atr, ConfigUtils.ExternalIdAttr):
                types.update(atr.id_types)
                if atr.source_systems is None:
                    all_systems = True
                else:
                    systems.update(atr.source_systems)
        if not types:
            return
        if all_systems or not systems:
            # By setting to None we fetch from all source_systems.
            systems = None
        i = 0
        # Search person:
        for row in self.pe.search_external_ids(source_system=systems,
                id_type=types, entity_type=self.co.entity_person):
            for ent in self.owner2ent.get(row['entity_id'], ()):
                itype = str(self.co.EntityExternalId(row['id_type']))
                ssys = str(self.co.AuthoritativeSystem(row['source_system']))
                ent.external_ids.setdefault(itype, {})[ssys] = row['external_id']
                i += 1
        # Search account:
        for row in self.ac.search_external_ids(source_system=systems,
                id_type=types, entity_type=self.co.entity_account):
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
        self.logger.debug("Fetch traits...")
        types = set()
        # Go through config and see what info needs to be fetched:
        for atr in self.config['attributes'].itervalues():
            if isinstance(atr, ConfigUtils.TraitAttr):
                types.update(atr.traitcodes)
        if not types:
            return
        i = 0
        for row in self.ent.list_traits(code=types):
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
        self.logger.debug("Fetch address info...")
        adrtypes = set()
        systems = set()
        all_systems = False
        # Go through config and see what info needs to be fetched:
        for atr in self.config['attributes'].itervalues():
            if isinstance(atr, ConfigUtils.AddressAttr):
                adrtypes.update(atr.address_types)
                if atr.source_systems is None:
                    all_systems = True
                else:
                    systems.update(atr.source_systems)
        if not adrtypes:
            return
        if all_systems or not systems:
            # By setting to None we fetch from all source_systems.
            systems = None

        i = 0
        # Addresses stored on the person:
        if hasattr(self.pe, 'list_entity_addresses'):
            for row in self.pe.list_entity_addresses(source_system=systems,
                                        entity_type=self.co.entity_person,
                                        address_type=adrtypes):
                for ent in self.owner2ent.get(row['entity_id'], ()):
                    atype = str(self.co.Address(row['address_type']))
                    ssys = str(self.co.AuthoritativeSystem(row['source_system']))
                    ent.addresses.setdefault(atype, {})[ssys] = row
                    i += 1
        # Contact info stored on the account:
        if hasattr(self.ac, 'list_entity_addresses'):
            for row in self.ac.list_entity_addresses(source_system=systems,
                                         entity_type=self.co.entity_account,
                                         address_type=adrtypes):
                ent = self.id2entity.get(row['entity_id'], None)
                if ent:
                    atype = str(self.co.Address(row['address_type']))
                    ssys = str(self.co.AuthoritativeSystem(row['source_system']))
                    ent.addresses.setdefault(ctype, {})[ssys] = row
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
        mailconf = (ConfigUtils.EmailQuotaAttr, ConfigUtils.EmailAddrAttr)
        if not any(isinstance(a, mailconf) for a in
                self.config['attributes'].itervalues()):
            # No mail data needed, skipping
            return
        self.logger.debug("Fetch mail data...")

        # Need a map from EmailTarget's target_id to entity_id:
        targetid2entityid = dict((r['target_id'], r['target_entity_id']) for r
                                 in self.mailtarget.list_email_targets_ext())
        for target_id, entity_id in targetid2entityid.iteritems():
            ent = self.entities.get(entity_id)
            if ent:
                ent.maildata['target_id'] = target_id

        # Email quotas
        if any(isinstance(a, ConfigUtils.EmailQuotaAttr) for a in
                self.config['attributes'].itervalues()):
            mailquota = Email.EmailQuota(self.db)
            i = 0
            for row in mailquota.list_email_quota_ext():
                ent = self.id2entity.get(targetid2entityid[row['target_id']])
                if ent:
                    ent.maildata['quota'] = row
                    i += 1
            self.logger.debug("Found %d email quotas" % i)

        # Email addresses
        if any(isinstance(a, ConfigUtils.EmailAddrAttr) for a in
                self.config['attributes'].itervalues()):
            ea = Email.EmailAddress(self.db)
            # Need a mapping from address_id for the primary addresses:
            adrid2email = dict()
            i = 0
            for row in ea.search():
                ent = self.id2entity.get(targetid2entityid[row['target_id']])
                if ent:
                    adr = '@'.join((row['local_part'], row['domain']))
                    adrid2email[row['address_id']] = adr
                    ent.maildata.setdefault('alias', []).append(adr)
                    i += 1
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

    def fetch_passwords(self):
        """Fetch passwords for accounts from changelog.

        Only caches the newest password set. Only caches password for entities
        that does not exist in AD.

        """
        self.uname2pass = {}
        # This should save a small amount of memory, but also slow us down.
        ent_ids = set(x.entity_id for x in self.entities.itervalues()
                      if not x.in_ad)
        answer = reversed(self.db.get_log_events(
                                        types=self.co.account_password))
        for ans in answer:
            try:
                ent = self.id2entity[ans['subject_entity']]
            except KeyError:
                # We continue past this event. Since account is not in the
                # list of users who should get their password set.
                continue

            if self.uname2pass.has_key(ent.entity_name):
                self.logger.debug('Plaintext already loaded for %s' %
                                    ent.entity_name)
            elif (ans['change_type_id'] == self.co.account_password and
                    ans['subject_entity'] in ent_ids):
                try:
                    self.uname2pass[ent.entity_name] = \
                        pickle.loads(str(ans['change_params']))['password']
                    self.logger.debug('Loaded pt for %s' % ent.entity_name)
                # TODO JSAMA: Revise error-list and log.
                except (KeyError, TypeError):
                    self.logger.debug('No plaintext loadable for %s' %
                                        ent.entity_name)
            else:
                self.logger.debug('No plaintext available for %s' %
                                    ent.entity_name)

    def process_entities_not_in_ad(self):
        """Start processing users not in AD.

        Depends on the generic superclass' functionality.

        """
        # Cache the passwords for the entities not in AD:
        self.fetch_passwords()
        return super(UserSync, self).process_entities_not_in_ad()

    def process_entity_not_in_ad(self, ent):
        """Process an account that doesn't exist in AD, yet.

        We should create and update a User object in AD for those who are not in
        AD yet. The object should then be updated as normal objects.

        @type: CerebrumEntity
        @param: An object representing an entity in Cerebrum.

        """
        ret = super(UserSync, self).process_entity_not_in_ad(ent)
        if not ret:
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
                password = self.uname2pass[ent.entity_name]
            except KeyError:
                password = ''
                self.logger.warn('No password set for %s' % ent.entity_name)
                return ret

            self.logger.debug('Trying to set pw for %s', ent.entity_name)
            if self.server.set_password(ret['DistinguishedName'], password):
                # As a security feature, you have to explicitly enable the
                # account after a valid password has been set.
                if ent.active:
                    self.server.enable_object(ret['DistinguishedName'])
        # If more functionality gets put here, you should check if the entity is
        # active, and not update it if the config says so (downgrade).
        return ret

    def changelog_handle_e_account(self, ctype, row):
        """Handler for changelog events of category 'e_account'.

        Syncs new changes that affects the account. Example on change types in
        this category: create, delete, mod, password, passwordtoken, destroy,
        home_added, home_removed, move, home_updated. Not all types might be
        respected, but subclasses could override this.

        Accounts without the target spread gets ignored.

        @type ctype: ChangeType constant
        @param ctype: The change log type.

        @type row: dict (db-row)
        @param row: The row as returned from the database, e.g. from
            L{get_change_log}.

        @rtype: bool
        @return: True if the change should be marked as finished. False only if
            it failed and should be reprocessed later.
        """
        self.ac.clear()
        # TODO: handle NotFoundError here, in case the entity has been nuked.
        try:
            self.ac.find(row['subject_entity'])
        except Errors.NotFoundError, e:
            self.logger.warn("Not found account: %s" % row['subject_entity'])
            # TODO: this might be okay in some cases, e.g. if the change type is
            # 'delete'? Should we always try to remove the entity from AD? We
            # don't have the account name, but the 'change_params' might have
            # something?
            self.logger.debug("Change_params: %s" % (row['change_params'],))
            if row['change_params']:
                self.logger.debug("Change_params: %s" %
                                  (pickle.loads(str(row['change_params'])),))
            return False

        if not self.ac.has_spread(self.config['target_spread']):
            self.logger.debug("Account %s without spread, ignoring",
                              self.ac.account_name)
            return True
        name = self.config.get('name_format', '%s') % self.ac.account_name

        if ctype.type == 'password':
            try:
                pw = pickle.loads(str(row['change_params']))['password']
            except (KeyError, TypeError):
                self.logger.warn("No plaintext password found for: %s", name)
                return False
            # TODO: do we need to unicodify it here, or do we handle it in the
            # ADclient instead?
            #pwUnicode = unicode(pw, 'iso-8859-1')
            return self.server.set_password(name, pw)
        elif ctype.type == 'create':
            try:
                return self.server.create_object(name, self.config['target_ou'],
                                         object_type=self.config['target_type'])
            except Exception, e:
                self.logger.warn(e)
                # TODO: check if it is because the object already exists! If so,
                # return True, as our job is done.
                return False
        elif ctype.type in ('delete', 'destroy'):
            # TODO: downgrade object after what config says
            ad_object = {'Enabled': True, # assume user is active
                         'Name': name,
                         'DistinguishedName': '%s%s' % (name,
                                                      self.config['target_ou'])}
            try:
                return self.downgrade_object(ad_object,
                                          self.config['handle_unknown_objects'])
            except Exception, e:
                self.logger.warn(e)
                # TODO: check if the object is already deleted or deactivated.
                # If so, our job is done.
                return False
        else:
        # TODO: handle type == 'mod'? What is then changed? Should we just
        # resync all of the account, i.e. calculate and sync its attributes,
        # check its location and so on?
            self.logger.warn("Unknown log change of type %s:%s",
                             ctype.category, ctype.type)
        # TODO: change this to True when done with this method? Depending on how
        # we want this to work...
        return False

    # TODO: the rest must be cleaned up first! Old code.

    def fullsync_forward(self):
        # TODO: move this to somewhere else?
        #
        #Fetch ad data
        self.logger.debug("Fetching ad data about contact objects...")
        ad_contacts = self.fetch_ad_data_contacts()
        self.logger.info("Fetched %i ad forwards" % len(ad_contacts))

        # Fetch forward_info
        self.logger.debug("Fetching forwardinfo from cerebrum...")
        self.fetch_forward_info()
        for acc in self.accounts.itervalues():
            for fwd in acc.contact_objects:
                fwd.calc_forward_attrs()
        # Compare forward info 
        self.compare_forwards(ad_contacts)
        
        # Fetch ad dist group data
        self.logger.debug("Fetching ad data about distrubution groups...")
        ad_dist_groups = self.fetch_ad_data_distribution_groups()
        # create a distribution group for each cerebrum user with
        # forward addresses
        for acc in self.accounts.itervalues():
            if acc.contact_objects:
                acc.create_dist_group()
        # Compare dist group info
        # TBD: dist group sync should perhaps be a sub class of group
        # sync?
        #self.compare_dist_groups(ad_dist_groups)
        #self.sync_dist_group_members()

    def fetch_forward_info(self):
        # TODO: move this to somewhere else?
        """
        Fetch forward info for all users with both AD and exchange spread.
        """ 
        from Cerebrum.modules.Email import EmailDomain, EmailTarget, EmailForward
        etarget = EmailTarget(self.db)
        rewrite = EmailDomain(self.db).rewrite_special_domains
        eforward = EmailForward(self.db)

        # We need a email target -> entity_id mapping
        target_id2target_entity_id = {}
        for row in etarget.list_email_targets_ext():
            if row['target_entity_id']:
                te_id = int(row['target_entity_id'])
                target_id2target_entity_id[int(row['target_id'])] = te_id

        # Check all email forwards
        for row in eforward.list_email_forwards():
            te_id = target_id2target_entity_id.get(int(row['target_id']))
            acc = self.get_account(account_id=te_id)
            # We're only interested in those with AD and exchange spread
            if acc.to_exchange:
                acc.add_forward(row['forward_to'])

    def fetch_ad_data_contacts(self):
        # TODO: Move this to somewhere else?
        """
        Returns full LDAP path to AD objects of type 'contact' and prefix
        indicating it is used for forwarding.

        @return: a dict of dicts wich maps contact obects name to that
                 objects properties (dict)
        @rtype: dict
        """
        ret = dict()
        self.server.setContactAttributes(cereconf.AD_CONTACT_FORWARD_ATTRIBUTES)
        ad_contacts = self.server.listObjects('contact', True, self.ad_ldap)
        if ad_contacts:
            # Only deal with forwarding contact objects. 
            for object_name, properties in ad_contacts.iteritems():
                # TBD: cereconf-var?
                if object_name.startswith("Forward_for_"):
                    ret[object_name] = properties
        return ret

    def fetch_ad_data_distribution_groups(self):
        # TODO: Move this to somewhere else?
        """
        Returns full LDAP path to AD objects of type 'group' and prefix
        indicating it is to hold forward contact objects.

        @rtype: dict
        @return: a dict of dict wich maps distribution group names to
                 distribution groupproperties (dict)
        """        
        ret = dict()
        self.server.setGroupAttributes(cereconf.AD_DIST_GRP_ATTRIBUTES)
        ad_dist_grps = self.server.listObjects('group', True, self.ad_ldap)
        if ad_dist_grps:
            # Only deal with forwarding groups. Groupsync deals with other groups.
            for grp_name, properties in ad_dist_grps.iteritems():
                if grp_name.startswith(cereconf.AD_FORWARD_GROUP_PREFIX):
                    ret[grp_name] = properties
        return ret

class GroupSync(BaseSync):
    """Sync for Cerebrum groups in AD.

    This contains generic functionality for handling groups for AD, to add more
    functionality you need to subclass this.

    TODO: Should subclasses handle distribution and security groups? How should
    we treat those? Need to describe it better the specifications!

    """
    def __init__(self, *args, **kwargs):
        """Instantiate group specific functionality."""
        super(GroupSync, self).__init__(*args, **kwargs)
        self.gr = Factory.get("Group")(self.db)
        self.pe = Factory.get("Person")(self.db)
        self.ac = Factory.get("Account")(self.db)

    def configure(self, config_args):
        """Add extra configuration that is specific for groups.

        @type config_args: dict
        @param config_args: Configuration data from cereconf and/or command line
            options.

        """
        super(GroupSync, self).configure(config_args)

        if 'member_spreads' in config_args:
            # Convert the member spread names to spread constants:
            self.config['member_spreads'] = tuple(self.co.Spread(s) for s in
                                                  config_args['member_spreads'])
            # Check if the member spreads have their own sync:
            for s in self.config['member_spreads']:
                if str(s) not in adconf.SYNCS:
                    self.logger.warn("Member_spread without its own AD-sync: %s", s)

        # Check if the group type is a valid type:
        if self.config['group_type'] not in ('security', 'distribution'):
            raise Exception('Invalid group type: %s' %
                            self.config['group_type'])
        # Check if the group scope is a valid scope:
        if self.config['group_scope'] not in ('global', 'universal'):
            raise Exception('Invalid group scope: %s' %
                            self.config['group_scope'])

        return
        # TODO: remove the rest:

        # Sync settings for this module
        for k in ("sec_group_spread", "dist_group_spread", "user_spread"):
            # Group.search() must have spread constant or int to work,
            # unlike Account.search()
            if k in config_args:
                setattr(self, k, self.co.Spread(config_args[k]))

    def process_ad_object(self, ad_object):
        """Process a Group object retrieved from AD.

        Do the basic sync and update the member list for the group.

        """
        super(GroupSync, self).process_ad_object(ad_object)
        ent = self.adid2entity.get(ad_object['Name'])
        if not ent:
            # Already taken care of in the super class
            return
        dn = ad_object['DistinguishedName'] # TBD: or 'Name'?
        if any(dn.endswith(ou) for ou in self.config.get('ignore_ou', ())):
            return
        # TODO: more functionality for groups?

    def post_process(self):
        """Extra sync functionality for groups: syncing members.

        """
        super(GroupSync, self).post_process()
        self.logger.debug("Start syncing members")
        for ent in self.entities.itervalues():
            if ent.active and ent.in_ad:
                try:
                    self.sync_group_members(ent)
                except ADUtils.NoAccessException, e:
                    self.add_admin_message('warning',
                                           u'No access to members of %s: %s' %
                                           (ent.ad_id, e))
                    # TODO: do we need to strip out data from the exceptions? Could
                    # it for instance contain passwords?
                except PowershellException, e:
                    self.logger.warn(u"Trouble with member-sync of %s: %s" %
                                     (ent.ad_id, e))

    def fetch_cerebrum_data(self):
        """Fetch data from Cerebrum that is needed for syncing groups.

        What kind of data that should be gathered is up to what attributes are
        set in the config to be exported. There's for instance no need to fetch
        titles if the attribute Title is not used. Subclasses could however
        override this, if they need such data for other usage.

        """
        super(GroupSync, self).fetch_cerebrum_data()
        # TODO: More data that is needed?
        # For instance what groups are dist groups and sec groups?

    def fetch_cerebrum_entities(self):
        """Fetch the groups from Cerebrum that should be compared against AD.

        The configuration is used to know what to cache. All data is put in a
        list, and each entity is put into an object from
        L{Cerebrum.modules.ad2.CerebrumData} or a subclass, to make it easier to
        later compare with AD objects.

        Could be subclassed to fetch more data about each entity to support
        extra functionality from AD and to override settings.

        """
        self.logger.debug("Fetching groups with spread %s" %
                          (self.config['target_spread'],))
        subset = self.config.get('subset')
        for row in self.gr.search(spread=self.config['target_spread']):
            name = row["name"]
            # For testing or special cases where we only want to sync a subset
            # of entities. The subset should contain the entity names, e.g.
            # usernames or group names.
            if subset and name not in subset:
                continue
            self.entities[name] = self.cache_entity(int(row["group_id"]), name,
                                                    description=row['description'])

    def start_fetch_ad_data(self, object_type=None, attributes=dict()):
        """Ask AD to start generating the data we need about groups.

        Could be subclassed to get more/other data.

        TODO: add attributes and object_type and maybe other settings as input
        parameters.

        @rtype: string
        @return: A CommandId that is the servere reference to later get the data
            that has been generated.

        """
        # TODO: some extra attributes to add?
        return super(GroupSync, self).start_fetch_ad_data(
                                                object_type=object_type,
                                                attributes=attributes)

    def _sync_group_members(self, ent, members, cmdid):
        """Sync the given members to the given AD-object.

        This method handles the member sync with AD and works by getting the
        member list from AD and comparing it with Cerebrum's list. If the group
        contains more members than AD could return (defaults to 1500), the group
        in AD is drained and refilled. TODO: This should in the future be
        changed to refilling a sub group instead, to avoid that the members lose
        access in a minute or so.

        @type ent: CerebrumEntity
        @param ent: The targetet entity to sync the members for.

        @type members: set
        @param members: The list of members that should be the result in AD
            after the sync has finished.

        @type cmdid: tuple
        @param cmdid: The CommandId for a previous call to AD for generating a
            list of all the members of the given group. This is to speed things
            up, by making AD generate its list while we are generating ours.

        @rtype: boolean
        @return: If the sync succeeded or not.

        @raise PowershellException: If a sync command to AD failed and were not
            handled by the method. Could for instance be due to limited access
            privileges.

        """
        dn = ent.ad_data['dn']
        # Shortcut for empty groups - faster to just drain the group of members.
        if not members:
            # Tell AD to stop fetching members:
            self.server.wsman_signal(cmdid[0], cmdid[1])
            return self.server.empty_group(dn)
        # Get the list of members from AD and compare:
        try:
            # Use SamAccountName if it exists, or the Name. Name could sometimes
            # be something else, but the username should not be changed.
            ad_members = set(mem.get('Name', mem['name']) for mem in
                             self.server.get_list_members(cmdid))
        except ADUtils.SizeLimitException, e:
            self.logger.debug("Too many group members of %s: %s", ent.ad_id,
                                                              len(members))
            # TODO: change how this works! Could create sub group and add
            # members to instead, and then remove the old sub group afterwards.
            self.server.empty_group(dn)
            return self.server.add_members(dn, members)
        self.logger.debug("Group had %d members in AD" % len(ad_members))
        mem_add = members - ad_members
        if mem_add:
            self.server.add_members(dn, mem_add)
        mem_remove = ad_members - members
        if mem_remove:
            self.server.remove_members(dn, mem_remove)
        return True

    def get_group_members(self, ent):
        """Get a list of a given entity's members from Cerebrum.

        Note that only the members of the given L{member_spreads} from the
        config is fetched. If groups are found as members, they are included as
        direct members of the entity if they have one of the member spreads. If
        the member group does not have the spread, it sub members are included
        in the entity - i.e. the entity is "flattened".

        Note that the name of the members are by default their entity_name, but
        if the given spread has its own sync and a L{name_format} is defined,
        this is used instead.

        @type ent: CerebrumEntity
        @param ent: The entity for which we should fetch the members of.

        @rtype: set
        @return: A list of members of the entity, filtered by spreads in config.

        """
        mem_spreads = self.config.get('member_spreads', None)

        # Create a mapping from entity_type to name_format, so the names are as
        # in ad_id, e.g. groupnames which ends with '-group'. Default, unknown
        # entity types, are defaulted to its entity_name. TBD: Is this an okay
        # behaviour?
        type2name = dict()
        if mem_spreads:
            for spr in mem_spreads:
                if spr not in adconf.SYNCS:
                    continue
                format = adconf.SYNCS[spr].get('name_format')
                if not format:
                    continue
                sp = self.co.Spread(spr)
                int(sp)
                type2name[int(sp.entity_type)] = format
        else:
            for spr, data in adconf.SYNCS.iteritems():
                sp = self.co.Spread(spr)
                try:
                    int(sp)
                except Exception:
                    continue
                type2name[int(sp.entity_type)] = data.get('name_format', '%s')

        # TODO: gr.search_members by given spreads will not return all groups -
        # we would probably need to do another search_members just for groups,
        # to be able to expand these by including indirect members - or is it
        # possible to expand search_members for this behaviour, or have an own
        # API method for this to make it go faster?

        # TODO: Find out if the search flattens out the member list if sub
        # groups exists in the group. We need to fetch all indirect members of
        # the group too, as subgroups without the AD spread must be flattened.
        cere_members = set()
        for mem in self.gr.search_members(group_id=ent.entity_id,
                                          member_spread=mem_spreads,
                                          include_member_entity_name=True):
            format = type2name.get(mem['member_type'], '%s')
            name = mem['member_name']

            #if mem['member_type'] == self.co.entity_group:
            #    # Special treatment of groups. We want to flatten groups
            #    # that are members of groups that does not have a spread
            #    # to AD.

            #    # TODO: This only works for first level? Is that OK?
            #    self.gr.clear()
            #    self.gr.find(mem['member_id'])
            #    
            #    if self.gr.has_spread(self.config['target_spread']):
            #        name = self.gr.group_name
            #    else:
            #        name = None
            #        for submem in self.gr.search_members(
            #                                group_id=self.gr.entity_id,
            #                                member_spread=mem_spreads,
            #                                include_member_entity_name=True,
            #                                indirect_members=True):
            #            cere_members.add(format % (self.gr.group_name,))

            # Special treatment for persons:
            if mem['member_type'] == self.co.entity_person:
                # TODO: Should we cache person-id → primary account name?
                # Fetching person
                self.pe.clear()
                self.pe.find(mem['member_id'])

                # Getting the primary account, skip if not defined
                a_id = self.pe.get_primary_account()
                if not a_id:
                    self.logger.warn("Person (%d) has no primary account, " \
                                        "skipping" % self.pe.entity_id)
                    continue

                # Fetch account, and retrieve account name
                self.ac.clear()
                self.ac.find(a_id)
                name = self.ac.account_name
            cere_members.add(format % (name,))
        return cere_members

    def sync_group_members(self, ent):
        """Update the members for a given entity, normally groups.

        TODO: Distribution groups are allowed to be members of security groups,
        but not the other way around. This is not checked for, yet.

        @type ent: CerebrumEntity
        @param ent: An instance with information from Cerebrum about the entity.

        """
        self.logger.debug("Syncing members for entity: %s" % ent.ad_id)
        dn = ent.ad_data['dn']
        # Start fetching the member list from AD:
        cmdid = self.server.start_list_members(dn)
        cere_members = self.get_group_members(ent)
        return self._sync_group_members(ent, cere_members, cmdid)

# Gruppa ad_ind590 og ad_dat208 er eksempler hvor det må flates ut

class HostSync(BaseSync):
    """Sync for Cerebrum hosts to 'computer' objects in AD.

    This contains simple functionality for adding hosts to AD. Note that this
    only creates the Computer object in AD, without connecting it to a real
    host. That normally happens by manually authenticating the computer in the
    domain.

    """
    def __init__(self, *args, **kwargs):
        """Instantiate host specific functionality."""
        super(HostSync, self).__init__(*args, **kwargs)
        self.host = Factory.get("Host")(self.db)

    def fetch_cerebrum_entities(self):
        """Fetch the entities from Cerebrum that should be compared against AD.

        The configuration is used to know what to cache. All data is put in a
        list, and each entity is put into an object from
        L{Cerebrum.modules.ad2.CerebrumData} or a subclass, to make it easier to
        later compare with AD objects.

        Could be subclassed to fetch more data about each entity to support
        extra functionality from AD and to override settings.

        """
        self.logger.debug("Fetching hosts with spread %s" %
                          (self.config['target_spread'],))
        subset = self.config.get('subset')
        for row in self.host.search(): # TODO: should specify spread, now we push all!
            name = row["name"]
            if subset and name not in subset:
                continue
            self.entities[name] = self.cache_entity(int(row["host_id"]), name,
                                                    row['description'])

class DistGroupSync(GroupSync):
    """Methods for distribution group sync.

    TODO: Note that this is from the old sync and is not working. It is kept
    here until we know how to solve the sync of distribution groups.

    """
    def _old_configure(self, config_args):
        """
        Read configuration options from args and cereconf to decide
        which data to sync.

        @param config_args: Configuration data from cereconf and/or
                            command line options.
        @type config_args: dict
        """
        self.logger.info("Starting group-sync")
        # Sync settings for this module
        for k in ("sec_group_spread", "dist_group_spread", "user_spread"):
            # Group.search() must have spread constant or int to work,
            # unlike Account.search()
            if k in config_args:
                setattr(self, k, self.co.Spread(config_args[k]))
        for k in ("exchange_sync", "delete_groups", "dryrun", "store_sid",
                  "ad_ldap", "ad_domain", "subset", "name_prefix", "first_run"):
            setattr(self, k, config_args[k])

        # Set which attrs that are to be compared with AD
        self.sync_attrs = cereconf.AD_DIST_GRP_ATTRIBUTES
        self.logger.info("Configuration done. Will compare attributes: %s" %
                         str(self.sync_attrs))

    def _old_fullsync(self):
        """
        This method defines what will be done in the sync.
        """
        # Fetch AD-data 
        self.logger.debug("Fetching AD group data...")
        addump = self.fetch_ad_data()
        if addump is None or addump is False:
            self.logger.critical("No data from AD. Something's wrong!")
            return
        self.logger.info("Fetched %i AD groups" % len(addump))

        #Fetch cerebrum data.
        self.logger.debug("Fetching cerebrum data...")
        self.fetch_cerebrum_data()

        # Compare AD data with Cerebrum data (not members)
        for gname, ad_group in addump.iteritems():
            if gname in self.groups:
                self.groups[gname].ad_dn = ad_group["distinguishedName"]
                self.groups[gname].in_ad = True
                self.compare(ad_group, self.groups[gname])
            else:
                self.logger.debug("Group %s in AD, but not in Cerebrum" % gname)
                # Group in AD, but not in Cerebrum:
                if self.delete_groups:
                    self.delete_group(ad_group["distinguishedName"])

        # Create group if it exists in Cerebrum but is not in AD
        for grp in self.groups.itervalues():
            if grp.in_ad is False and grp.quarantined is False:
                sid = self.create_ad_group(grp.ad_attrs,
                                           self.get_default_ou())
                if sid and self.store_sid:
                    self.store_ext_sid(grp.group_id, sid)
            
        # Update Exchange if needed
        #self.logger.debug("Sleeping for 5 seconds to give ad-ldap time to update") 
        #time.sleep(5)
        for grp in self.groups.itervalues():
            if grp.update_recipient:
                self.update_Exchange(grp.gname)

        #Syncing group members
        self.logger.info("Starting sync of group members")
        self.sync_group_members()
        
        #Commiting changes to DB (SID external ID) or not.
        if self.store_sid:
            if self.dryrun:
                self.db.rollback()
            else:
                self.db.commit()
            
        self.logger.info("Finished group-sync")

    def fetch_ad_data(self):
        """
        Returns full LDAP path to AD objects of type 'group' and prefix
        indicating it is to hold forward contact objects.

        @rtype: dict
        @return: a dict of dict wich maps distribution group names to
                 distribution groupproperties (dict)
        """        
        ret = dict()
        attrs = cereconf.AD_DIST_GRP_ATTRIBUTES + tuple(cereconf.AD_DIST_GRP_DEFAULTS.keys())
        self.server.setGroupAttributes(attrs)
        ad_dist_grps = self.server.listObjects('group', True, self.ad_ldap)
        # Check if we get any dat from AD. If no data the AD service
        # returns None. If we actually expect no data (the option
        # first_run is given), then we want an empty dict rather than
        # None
        if ad_dist_grps is None and self.first_run:
            return ret
        if ad_dist_grps:
            # Only deal with distribution groups. Groupsync deals with security groups.
            dist_group_types = ('2', # Global distribution group
                                '8', # Universal distribution group
                                '2147483656') # Universal distribution group,
                                              # security enabled
            for grp_name, properties in ad_dist_grps.iteritems():
                if not 'groupType' in properties:
                    continue
                if str(properties['groupType']) in dist_group_types:
                    ret[grp_name] = properties
        return ret

    def fetch_cerebrum_data(self):
        """
        Fetch relevant cerebrum data for groups with the given spread.
        Create CerebrumGroup instances and store in self.groups.
        """
        # Fetch name, id and description for security groups
        for row in self.group.search(spread=self.dist_group_spread):
            gname = unicode(row["name"], cereconf.ENCODING)
            self.groups[gname] = self.cb_group(gname, row["group_id"],
                                               row["description"])
        self.logger.info("Fetched %i groups with spread %s",
                         len(self.groups), self.dist_group_spread)
        # Set attr values for comparison with AD
        for g in self.groups.itervalues():
            g.calc_ad_attrs()

    def cb_group(self, gname, group_id, description):
        "wrapper func for easier subclassing"
        return CerebrumDistGroup(gname, group_id, description, self.ad_domain,
                                 self.get_default_ou())

class PosixUserSync(UserSync):
    """Extra sync functionality for posix data about users.

    It is possible to sync posix data, like UID and GID, with AD, for
    environments that should support both environments where both UNIX and AD is
    used. Note, however, that AD needs to include an extra schema before the
    pposix attributes could be populated.

    """
    def __init__(self, *args, **kwargs):
        """Instantiate posix specific functionality."""
        super(PosixUserSync, self).__init__(*args, **kwargs)
        self.pu = Factory.get('PosixUser')(self.db)
        self.pg = Factory.get('PosixGroup')(self.db)

    def fetch_cerebrum_data(self):
        """Fetch the posix data from Cerebrum."""
        super(PosixUserSync, self).fetch_cerebrum_data()

        # Then fetch POSIX data for the user

        # First, we need a mapping between group_id to GID:
        self.posix_group_id2gid = dict((eid, gid) for eid, gid in
                                       self.pg.list_posix_groups())
        self.logger.debug("Number of POSIX groups: %d",
                          len(self.posix_group_id2gid))
        # Then we give each account UID and GID
        # TODO: Should be extended in the future with more attributes. UiO would
        # for instance like to populate "gecos" and primary group.
        for row in self.pu.list_posix_users():
            ent = self.id2entity.get(row['account_id'], None)
            if ent:
                ent.posix['uid'] = int(row['posix_uid']) or ''
                ent.posix['gid'] = self.posix_group_id2gid.get(row['gid'], '')
        self.logger.debug("Number of POSIX users: %d",
                          len(filter(lambda x: len(x.posix) > 0,
                              self.entities.itervalues())))

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
            ent = self.id2entity.get(targetid2entityid[row['target_id']])
            if ent:
                ent.maildata['quota_soft'] = row['quota_soft']
                ent.maildata['quota_hard'] = row['quota_hard']


#!/usr/bin/env python
# -*- encoding: iso-8859-1 -*-

"""Common bofh daemon functionality used across all institutions.

This module contains class, functions, etc. that are common and useful in all
bofhd instances at all installations. This file should only include such
generic functionality. Push institution-specific extensions to
modules/no/<institution>/bofhd_<institution>_cmds.py.
"""

import cerebrum_path
import cereconf

from Cerebrum import Cache
from Cerebrum import Errors
from Cerebrum import Entity
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import CerebrumError



class BofhdCommandBase(object):
    """Base class for bofhd command support.

    This base class contains functionality common to all bofhd extension
    classes everywhere. The functions that go here are of the most generic
    nature (institution-specific code goes to
    modules.no.<inst>.bofhd_<inst>_cmds.py:BofhdExtension).

    FIXME: Some command writing guidelines (format suggestion, registration in
    all_commands, etc.)
    
    In order to be a proper extension, a site specific bofhd extension class
    must:

    - Inherit from this base class
    - Declare its own dictionary of public commands, ``all_commands`` (a class
      attribute), and populate that dict.
    - Define an attribute dealing with authorisation (FIXME: A common class
      for this one as well?) for at least all of the commands implemented.
    - 
    """


    # Each subclass defines its own class attribute containing the relevant
    # commands.
    all_commands = {}



    def __init__(self, server):
        self._cached_client_commands = Cache.Cache(mixins=[Cache.cache_mru,
                                                           Cache.cache_slots,
                                                           Cache.cache_timeout],
                                                   size=500,
                                                   timeout=60*60)
        # 
        # NB! A subclass needs to create its own authenticator.
        self.ba = None

        self.server = server
        self.db = server.db
        self.const = Factory.get("Constants")()
        self.logger = server.logger

        self.OU_class = Factory.get("OU")
        self.Account_class = Factory.get("Account")
        self.Group_class = Factory.get("Group")
    # end __init__



    def get_commands(self, account_id):
        """Fetch all available (public) commands for the specified client.
 
        bofhd distiguishes between two types of commands -- public (declared
        in the ``all_commands`` dict) and hidden (available in the
        ``hidden_commands`` dict). This methods fetches all the public
        commands.

        @type account_id: int
        @param account_id:
          All commands are specified on per-account basis (i.e. superusers get
          a different command set than regular Joes, obviously). account_id
          specifies which account we retrieve the commands for. 

        @rtype: dict of strings (command names) to tuples
        @return:
          Returns a dict mapping command names to tuples with information
          about the command. See cmd_param.py:Command:get_struct()'s
          documentation. 
        """

        try:
            return self._cached_client_commands[int(account_id)]
        except KeyError:
            pass
        commands = {}
        for key in self.all_commands:
            cmd = self.all_commands[key]
            if cmd is not None:
                if cmd.perm_filter:
                    if not getattr(self.ba,
                                   cmd.perm_filter)(account_id, query_run_any=True):
                        continue
                commands[key] = cmd.get_struct(self)

        self._cached_client_commands[int(account_id)] = commands
        return commands
    # end get_commands



    def get_help_strings(self):
        return ({}, {}, {})
    # end get_help_strings



    def get_format_suggestion(self, command):
        """Return a format string for a specific command.

        As bofhd is line oriented and bofh clients are pretty dumb, bofhd
        associates a format suggestion with each command. This method returns
        the format string for the specified command.

        @type command: basestring
        @param command:
          Command name for which the format string is sought.

        @rtype: dict
        @return:
          A dict describing the formatting for the specified command. See
          cmd_param.py:FormatSuggestion.get_format().
        """
        
        return self.all_commands[command].get_fs()
    # end get_format_suggestion



    def _get_boolean(self, onoff):
        """Convert a human-friendly representation of boolean to the proper
        Python object.
        """
        
        if onoff.lower() in ('on', 'true', 'yes', 'y'):
            return True
        elif onoff.lower() in ('off', 'false', 'no', 'n'):
            return False
        raise CerebrumError("Invalid value: 's%'; use one of: on true yes y off false no n" % str(onoff))
    # end _get_boolean



    def _human_repr2id(self, human_repr):
        """Convert a human representation of an id, to a suitable pair.

        We want to treat ids like these:

          - '1234'
          - 'foobar'
          - 'id:1234'
          - 'name:foobar'

        ... uniformly. This method accomplishes that. This is for INTERNAL
        USAGE ONLY.

        @param human_repr: basestring carrying the id.

        @rtype: tuple (of basestr, basestr)
        @return:
          A tuple (id_type, identification), where id_type is one of:
          'name', 'id'. It is the caller's responsibility to
          ensure that the given id_type makes sense in the caller's context.
        """

        if (human_repr is None or human_repr == ""):
            raise CerebrumError("Invalid id: <None>")

        # numbers (either as is, or as strings)
        if isinstance(human_repr, (int, long)):
            id_type, ident = "id", human_repr
        # strings (they could still be numeric IDs, though)
        elif isinstance(human_repr, (str, unicode)):
            if human_repr.isdigit():
                id_type, ident = "id", human_repr
            elif ":" in human_repr:
                id_type, ident = human_repr.split(":", 1)
                assert len(ident) > 0, "Invalid id: %s (type %s)" % (ident,
                                                                     id_type)
            else:
                id_type, ident = "name", human_repr
        else:
            raise CerebrumError("Unknown id type %s for id %s" %
                                (type(human_repr), human_repr))

        if id_type == "id":
            try:
                ident = int(ident)
            except ValueError:
                raise CerebrumError("Non-numeric component for id=%s" %
                                    str(ident))

        return id_type, ident
    # end __human_repr2id



    def _get_entity(self, entity_type=None, ident=None):
        """Return a suitable entity subclass for the specified entity_id.

        This method is useful when we have entity_id only, but want the most
        specific object for that id.
        """

        if ident is None:
            raise CerebrumError("Invalid id")
        if entity_type in ('account', self.const.entity_account):
            return self._get_account(ident)
        if entity_type in ('group', self.const.entity_group):
            return self._get_group(ident)
        if entity_type == 'stedkode':
            return self._get_ou(stedkode=ident)
        if entity_type is None:
            id_type, ident = self._human_repr2id(ident)
            if id_type == "id":
                ent = Entity.Entity(self.db)
                ent.find(ident)
            else: 
                raise CerebrumError("Unknown/unsupported id_type %s for id %s" %
                                    (id_type, str(ident)))

            # The find*() calls give us an entity_id from ident. The call
            # below returns the most specific object for that numeric
            # entity_id.
            entity_id = int(ent.entity_id)
            ent.clear()
            return ent.get_subclassed_object(entity_id)

        raise CerebrumError("Invalid entity type: %s" % str(entity_type))
    # end _get_entity

    

    def _get_ou(self, ou_id=None, stedkode=None):
        """Fetch a specified OU instance.

        Either ou_id or stedkode must be provided.

        @type ou_id: int or None
        @param ou_id:
          ou_id (entity_id) if not None.

        @type stedkode: string (DDDDDD, where D is a digit)
        @param stedkode:
          Stedkode for OU if not None.
        """

        ou = self.OU_class(self.db)
        ou.clear()
        try:
            if ou_id is not None:
                ou.find(ou_id)
            else:
                if len(stedkode) != 6 or not stedkode.isdigit():
                    raise CerebrumError("Expected 6 digits in stedkode <%s>" %
                                        stedkode)
                ou.find_stedkode(stedkode[:2], stedkode[2:4], stedkode[4:],
                                 institusjon=cereconf.DEFAULT_INSTITUSJONSNR)
            return ou
        except Errors.NotFoundError:
            raise CerebrumError("Unknown OU (%s)" %
                                (ou_id and ("id=%s" % ou_id)
                                        or ("sko=%s" % stedkode)))

        assert False, "NOTREACHED"
    # end _get_ou



    def _get_account(self, account_id, idtype=None):
        """Fetch an account identified by account_id.

        Return an Account object associated with the specified
        account_id. Raises an exception if no account matches.

        NB! This method returns a generic Account (rather than, say, a
        PosixUser instance, as is required for some installations)
    
        @type account_id: basestring or int
        @param account_id:
          Account identification for the account we want to retrieve. It could
          be either its entity_id (as string or int), or its name.

        @type idtype: string ('name' or 'id') or None.
        @param idtype:
          ID type for the account_id specified.

        @rtype: self.Account_class instance l
        @return:
          An account associated with the specified id (or an exception is
          raised if nothing suitable matches)
        """

        account = self.Account_class(self.db)
        account.clear()
        try:
            if idtype is None:
                idtype, account_id = self._human_repr2id(account_id)

            if idtype == 'name':
                account.find_by_name(account_id, self.const.account_namespace)
            elif idtype == 'id':
                if isinstance(account_id, str) and not account_id.isdigit():
                    raise CerebrumError("Entity id <%s> must be a number" %
                                        account_id)
                account.find(int(account_id))
            else:
                raise CerebrumError("Unknown idtype: '%s'" % idtype)
        except Errors.NotFoundError:
            raise CerebrumError("Could not find an account with %s=%s" %
                                (idtype, account_id))
        return account
    # end _get_account


    def _get_group(self, group_id, idtype=None):
        """Fetch a group identified by group_id.

        Return a Group object associated with the specified group_id. Raises
        an exception if no such group exists.
    
        @type group_id: basestring or int
        @param group_id:
          Group identification for the account we want to retrieve. It could
          be either its entity_id (as string or int), or its name.

        @type idtype: string ('name' or 'id') or None.
        @param idtype:
          ID type for the group_id specified.

        @rtype: self.Group_class instance.
        @return:
          A group associated with the specified id (or an exception is raised
          if nothing suitable matches)
        """

        group = self.Group_class(self.db)
        try:
            if idtype is None:
                idtype, group_id = self._human_repr2id(group_id)

            if idtype == "name":
                group.find_by_name(group_id)
            elif idtype == "id":
                group.find(group_id)
            else:
                raise CerebrumError("Unknown idtype: '%s'" % idtype)
        except Errors.NotFoundError:
            raise CerebrumError("Could not find a group with %s=%s" %
                                (idtype, group_id))
        return group
    # end _get_group



    def _get_entity_spreads(self, entity_id):
        """Fetch a human-friendly spread nmae for the specified entity.
        """

        entity = self._get_entity(ident=entity_id)
        # FIXME: Is this a sensible default behaviour?
        if not isinstance(entity, Entity.EntitySpread):
            return ""
        
        return ",".join(str(self.const.Spread(x['spread']))
                        for x in entity.get_spread())
    # end _get_entity_spreads
        


    def _get_entity_name(self, entity_id, entity_type=None):
        """Fetch a human-friendly name for the specified entity.

        @type entity_id: int
        @param entity_id:
          entity_id we are looking for.

        @type entity_type: const.EntityType instance (or None)
        @param entity_type:
          Restrict the search to the specifide entity. This parameter is
          really a speed-up only -- entity_id in Cerebrum uniquely determines
          the entity_type. However, should we know it, we save 1 db lookup.

        @rtype: str
        @return:
          Entity's name, obviously :) If none is found a magic string
          'notfound:<entity id>' is returned (it's not perfect, but it's better
          than nothing at all).
        """
        
        if entity_type is None:
            ety = Entity.Entity(self.db)
            try:
                ety.find(entity_id)
                entity_type = self.const.EntityType(ety.entity_type)
            except Errors.NotFoundError:
                return "notfound:%d" % entity_id
        
        if entity_type == self.const.entity_account:
            acc = self._get_account(entity_id, idtype='id')
            return acc.account_name
        elif entity_type == self.const.entity_group:
            group = self._get_group(entity_id, idtype='id')
            return group.group_name

        # Okey, we've run out of good options. Let's try a sensible fallback:
        # many entities have a generic name in entity_name. Let's use that:
        try:
            etname = type("entity_with_name", (Entity.EntityName,
                                               Entity.Entity), dict())
            etname = etname(self.db)
            etname.find(entity_id)
            if etname.get_names():
                # just grab any name. We don't really have a lot of choice.
                return etname.get_names()[0]["name"]
            else:
                # ... and if it does not exist -- return the id. We are out of
                # options at this point.
                return "%s:%s" % (entity_type, entity_id)    
        except Errors.NotFoundError:
            return "notfound:%d" % entity_id

        # NOTREACHED
        assert False
    # end _get_entity_name
# end BofhdCommandBase

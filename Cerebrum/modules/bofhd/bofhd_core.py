# -*- encoding: utf-8 -*-
#
# Copyright 2009-2018 University of Oslo, Norway
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
""" Common bofh daemon functionality used across all institutions.

This module contains class, functions, etc. that are common and useful in all
bofhd instances at all installations. This file should only include such
generic functionality. Push institution-specific extensions to
modules/no/<institution>/bofhd_<institution>_cmds.py.
"""
import time

import six
from mx import DateTime

import cereconf

from Cerebrum import Entity
from Cerebrum import Errors
from Cerebrum.Constants import _CerebrumCode
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.modules.bofhd import cmd_param as cmd
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.utils import BofhdUtils


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
    u""" All available commands. """

    authz = None
    u""" authz implementation. """

    @classmethod
    def get_format_suggestion(cls, command_name):
        """Return a format string for a specific command.

        :param str command_name:
            The `all_commands` command name (key) to fetch the format from.

        :return dict:
            A dict describing the formatting for the specified command.

        :see:
            cmd_param.py:FormatSuggestion.get_format().
        """
        return cls.list_commands('all_commands')[command_name].get_fs()

    @classmethod
    def get_help_strings(cls):
        """ Get help strings dicts.

        :return tuple:
            Returns a tuple with three dicts, containing help text for
            command groups, commands, and arguments.
        """
        # Must be implemented in subclasses
        return ({}, {}, {})

    def __init__(self, db, logger):
        self.__db = db
        self.__logger = logger

        # TODO: Really?
        self.OU_class = Factory.get("OU")
        self.Account_class = Factory.get("Account")
        self.Group_class = Factory.get("Group")
        self.Person_class = Factory.get("Person")

    @property
    def db(self):
        u""" Database connection. """
        # Needs to be read-only
        return self.__db

    @property
    def ba(self):
        u""" BofhdAuth. """
        try:
            return self.__ba
        except AttributeError:
            if self.authz is None:
                return None
            self.__ba = self.authz(self.db)
            return self.__ba

    @property
    def const(self):
        u""" Constants. """
        try:
            return self.__const
        except AttributeError:
            self.__const = Factory.get("Constants")(self.db)
            return self.__const

    @property
    def clconst(self):
        u""" CLConstants. """
        try:
            return self.__clconst
        except AttributeError:
            self.__clconst = Factory.get("CLConstants")(self.db)
            return self.__clconst

    @property
    def logger(self):
        u""" Logger. """
        return self.__logger

    @classmethod
    def list_commands(cls, attr):
        u""" Fetch all commands in all superclasses stored in a given attribute.

        Note:
            If cls.parent_commands is True, this method will try to include
            commands from super(cls) as well.

        :param sting attr:
            The attribute that contains commands.
        """
        gathered = dict()

        def merge(other_commands):
            # Update my_commands with other_commands
            for key, command in other_commands.iteritems():
                if key not in gathered:
                    gathered[key] = command

        # Fetch commands from this class
        merge(getattr(cls, attr, {}))

        if getattr(cls, 'parent_commands', False):
            omit_commands = getattr(cls, 'omit_parent_commands', [])
            try:
                for cand in cls.__bases__:
                    if hasattr(cand, 'list_commands'):
                        cmds = dict(
                            filter(
                                lambda t: t[0] not in omit_commands,
                                cand.list_commands(attr).items()))
                        merge(cmds)
            except IndexError:
                pass
        return gathered

    def get_commands(self, account_id):
        """ Fetch all commands for the specified user and client.

        bofhd distiguishes between two types of commands -- public
        (``all_commands``) and hidden (``hidden_commands``). This method
        fetches all the public commands.

        NOTE: Clients can call any command, regardless of what this function
        returns – but clients can use this function to autodiscover commands.

        :param int account_id:
            All commands are specified on per-account basis (i.e. superusers
            get a different command set than regular Joes, obviously).
            account_id specifies which account we retrieve the commands for.

        :return dict:
            Returns a dict that maps command names to tuples with information
            about the command.

        :see:
            cmd_param.py:Command:get_struct()'s documentation for more on
            the command info tuples.
        """
        visible_commands = dict()
        ident = int(account_id)

        for key, command in self.list_commands('all_commands').iteritems():
            if command is not None:
                if command.perm_filter:
                    try:
                        authz = getattr(self.ba, command.perm_filter)
                        if not authz(ident, query_run_any=True):
                            continue
                    except:
                        self.logger.error("perm_filter issue in %r (%r)",
                                          command.perm_filter,
                                          key,
                                          exc_info=True)
                        continue
                visible_commands[key] = command
        return visible_commands

    def _get_constant(self, code_cls, code_str, code_type="value"):
        c = code_cls(code_str)
        try:
            int(c)
        except Errors.NotFoundError:
            raise CerebrumError("Unknown %s: %r" % (code_type, code_str))
        return c

    @staticmethod
    def _get_boolean(onoff):
        """ String to boolean conversion.

        Convert a human-friendly representation of boolean to the proper Python
        object.
        """
        if isinstance(onoff, bool):
            return onoff
        yes = ('on', 'true', 'yes', 'y')
        no = ('off', 'false', 'no', 'n')
        if onoff.lower() in yes:
            return True
        elif onoff.lower() in no:
            return False
        raise CerebrumError("Invalid value: %r; use one of: %s" %
                            (onoff, ', '.join(yes + no)))

    @staticmethod
    def _human_repr2id(human_repr):
        """ Convert a human representation of an id, to a suitable pair.

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
        elif isinstance(human_repr, basestring):
            if human_repr.isdigit():
                id_type, ident = "id", human_repr
            elif ":" in human_repr:
                id_type, ident = human_repr.split(":", 1)
                assert len(ident) > 0, "Invalid id: %s (type %s)" % (ident,
                                                                     id_type)
            else:
                id_type, ident = "name", human_repr
        else:
            raise CerebrumError("Unknown id type %s for id %r" %
                                (type(human_repr), human_repr))
        if id_type == "id":
            try:
                ident = int(ident)
            except ValueError:
                raise CerebrumError("Non-numeric component for id=%r" % ident)
        return id_type, ident

    def _format_ou_name(self, ou):
        """ Format an OUs name.

        The name is six digits followed by the short name. The digits consists
        of fakultet, institutt and avdeling.
        """
        short_name = ou.get_name_with_language(
            name_variant=self.const.ou_name_short,
            name_language=self.const.language_nb,
            default="")
        return "%02i%02i%02i (%s)" % (ou.fakultet, ou.institutt, ou.avdeling,
                                      short_name)

    def _find_persons(self, arg):
        """ Find persons by a search criteria.

        :type args: str
        :param args: A search criteria:

            - <fnr>
            - fnr:<fnr>
            - exp:<export_id>
            - entity_id:<entity_id>
            - <day>-<month>-<year>

        :rtype: list (of persons)
        :return: A list of persons matching the criteria.
        """
        if arg.isdigit() and len(arg) > 10:  # find persons by fnr
            arg = 'fnr:%s' % six.text_type(arg)
        ret = []
        person = Factory.get('Person')(self.db)
        person.clear()
        if arg.find(":") != -1:
            idtype, value = arg.split(":", 1)
            if not value:
                raise CerebrumError("Unable to parse person id %r" % arg)
            if idtype == 'exp':
                if not value.isdigit():
                    raise CerebrumError("Export id must be a number")
                person.clear()
                try:
                    person.find_by_export_id(value)
                    ret.append({'person_id': person.entity_id})
                except Errors.NotFoundError:
                    raise CerebrumError("Unkown person id %r" % arg)
            elif idtype == 'entity_id':
                if not value.isdigit():
                    raise CerebrumError("Entity id must be a number")
                person.clear()
                try:
                    person.find(value)
                    ret.append({'person_id': person.entity_id})
                except Errors.NotFoundError:
                    raise CerebrumError("Unkown person id %r" % arg)
            elif idtype == 'fnr':
                for ss in cereconf.SYSTEM_LOOKUP_ORDER:
                    try:
                        person.clear()
                        person.find_by_external_id(
                            self.const.externalid_fodselsnr, value,
                            source_system=getattr(self.const, ss))
                        ret.append({'person_id': person.entity_id})
                    except Errors.NotFoundError:
                        pass
        elif arg.find("-") != -1:
            # Find persons by birth date
            ret = person.find_persons_by_bdate(self._parse_date(arg))

        else:
            raise CerebrumError("Unable to parse person id %r" % arg)
        return ret

    def _get_entity(self, entity_type=None, ident=None):
        """ Return a suitable entity subclass for the specified entity_id.

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
        if entity_type == 'person':
            return self._get_person(*self._map_person_id(ident))
        if entity_type is None:
            id_type, ident = self._human_repr2id(ident)
            if id_type == "id":
                ent = Entity.Entity(self.db)
                ent.find(ident)
            else:
                raise CerebrumError("Unknown/unsupported id_type %s for id %r"
                                    % (id_type, ident))
            # The find*() calls give us an entity_id from ident. The call
            # below returns the most specific object for that numeric
            # entity_id.
            entity_id = int(ent.entity_id)
            ent.clear()
            return ent.get_subclassed_object(entity_id)
        raise CerebrumError("Invalid entity type: %s" % str(entity_type))

    def _get_ou(self, ou_id=None, stedkode=None):
        """ Fetch a specified OU instance.

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
                    raise CerebrumError("Expected 6 digits in stedkode %r" %
                                        stedkode)
                ou.find_stedkode(stedkode[:2], stedkode[2:4], stedkode[4:],
                                 institusjon=cereconf.DEFAULT_INSTITUSJONSNR)
            return ou
        except Errors.NotFoundError:
            raise CerebrumError("Unknown OU (%s)" %
                                (ou_id and ("id=%r" % ou_id) or
                                 ("sko=%r" % stedkode)))
        raise Errors.UnreachableCodeError("_get_ou")

    def _get_account(self, account_id, idtype=None, actype="Account"):
        """ Fetch an account identified by account_id.

        Return an Account object associated with the specified
        account_id. Raises an exception if no account matches.

        @type account_id: basestring or int
        @param account_id:
          Account identification for the account we want to retrieve. It could
          be either its entity_id (as string or int), or its name.

        @type idtype: string ('name' or 'id') or None.
        @param idtype:
          ID type for the account_id specified.

        @type actype: str
        @param actype: 'Account' or 'PosixUser'

        @rtype: self.Account_class instance l
        @return:
          An account associated with the specified id (or an exception is
          raised if nothing suitable matches)
        """
        account = None
        if actype == 'Account':
            account = self.Account_class(self.db)
        elif actype == 'PosixUser':
            account = Factory.get('PosixUser')(self.db)
        else:
            raise CerebrumError("Invalid account type %r" % actype)
        account.clear()
        try:
            if idtype is None:
                idtype, account_id = self._human_repr2id(account_id)

            if idtype == 'name':
                account.find_by_name(account_id, self.const.account_namespace)
            elif idtype == 'id':
                if (isinstance(account_id, basestring)
                        and not account_id.isdigit()):
                    raise CerebrumError("Entity id %r must be a number" %
                                        account_id)
                account.find(int(account_id))
            else:
                raise CerebrumError("Unknown idtype: %r" % idtype)
        except Errors.NotFoundError:
            raise CerebrumError("Could not find an account with %s=%r" %
                                (idtype, account_id))
        return account

    def _get_group(self, group_id, idtype=None, grtype='Group'):
        """ Fetch a group identified by group_id.

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
        group = None
        if grtype == 'Group':
            group = self.Group_class(self.db)
        elif grtype == 'PosixGroup':
            group = Factory.get('PosixGroup')(self.db)
        elif grtype == 'DistributionGroup':
            group = Factory.get('DistributionGroup')(self.db)
        else:
            raise CerebrumError("Invalid group type %r" % grtype)
        try:
            if idtype is None:
                idtype, group_id = self._human_repr2id(group_id)
            if idtype == "name":
                group.find_by_name(group_id)
            elif idtype == "id":
                if not (isinstance(group_id, (int, long)) or
                        group_id.isdigit()):
                    raise CerebrumError(
                        "Non-numeric id lookup (%r)" % group_id)
                group.find(group_id)
            elif idtype == "gid" and grtype == 'PosixGroup':
                if not (isinstance(group_id, (int, long)) or
                        group_id.isdigit()):
                    raise CerebrumError(
                        "Non-numeric gid lookup (%r)" % group_id)
                group.find_by_gid(group_id)
            else:
                raise CerebrumError("Unknown idtype: %r" % idtype)
        except Errors.NotFoundError:
            raise CerebrumError("Could not find a %s with %s=%r" %
                                (grtype, idtype, group_id))
        return group

    def _get_entity_spreads(self, entity_id):
        """ Fetch a human-friendly spread name for the specified entity. """
        entity = self._get_entity(ident=entity_id)
        # FIXME: Is this a sensible default behaviour?
        if not isinstance(entity, Entity.EntitySpread):
            return ""
        return u",".join(six.text_type(self.const.Spread(x['spread']))
                         for x in entity.get_spread())

    def _get_person(self, idtype, id):
        """ Get person. """
        # TODO: Normalize the arguments. This should have similar usage to
        # _get_account, _get_group, ...
        # Also, document the idtype/id combinations.
        person = self.Person_class(self.db)
        person.clear()
        try:
            if str(idtype) == 'account_name':
                ac = self._get_account(id, idtype='name')
                id = ac.owner_id
                idtype = "entity_id"
            if isinstance(idtype, _CerebrumCode):
                person.find_by_external_id(idtype, id)
            elif idtype in ('entity_id', 'id'):
                if isinstance(id, basestring) and not id.isdigit():
                    raise CerebrumError("Entity id must be a number")
                person.find(id)
            else:
                raise CerebrumError("Unknown idtype")
        except Errors.NotFoundError:
            raise CerebrumError("Could not find person with %s=%s" % (idtype,
                                                                      id))
        except Errors.TooManyRowsError:
            raise CerebrumError("ID not unique %s=%s" % (idtype, id))
        return person

    def _map_person_id(self, id):
        """ Map <idtype:id> to const.<idtype>, id.

        Recognized fodselsnummer without <idtype>. Also recognizes entity_id.
        """
        # TODO: The way this function is used is kind of ugly.
        #       Typical usage is:
        #         self._get_person(*self._map_person_id(person_id))
        if id.isdigit() and len(id) >= 10:
            return self.const.externalid_fodselsnr, id
        if id.find(":") == -1:
            self._get_account(id)  # We assume this is an account
            return "account_name", id
        id_type, id = id.split(":", 1)
        if id_type not in ('entity_id', 'id'):
            id_type = self.external_id_mappings.get(id_type, None)
        if id_type is not None:
            if len(id) == 0:
                raise CerebrumError("id cannot be blank")
            return id_type, id
        raise CerebrumError("Unknown person_id type")

    def _get_name_from_object(self, entity):
        """Return a human-friendly name for the given entity, if such exists.

        @type entity: Entity
        @param entity:
            The entity from which we should return the human-readable name.
        """
        # optimise for common cases:
        if isinstance(entity, self.Account_class):
            return entity.account_name
        elif isinstance(entity, self.Group_class):
            return entity.group_name
        else:
            # TODO: extend as needed for quasi entity classes like Disk
            return self._get_entity_name(entity.entity_id, entity.entity_type)

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
                return "notfound:%r" % entity_id
        if entity_type == self.const.entity_account:
            acc = self._get_account(entity_id, idtype='id')
            return acc.account_name
        elif entity_type == self.const.entity_ou:
            ou = self._get_ou(ou_id=entity_id)
            return self._format_ou_name(ou)
        elif entity_type in (self.const.entity_group, ):
            group = self._get_group(entity_id, idtype='id')
            return group.group_name
        elif entity_type == self.const.entity_disk:
            disk = Factory.get('Disk')(self.db)
            disk.find(entity_id)
            return disk.path
        elif entity_type == self.const.entity_host:
            host = Factory.get('Host')(self.db)
            host.find(entity_id)
            return host.name
        elif entity_type == self.const.entity_person:
            person = Factory.get('Person')(self.db)
            person.find(entity_id)
            return person.get_name(self.const.system_cached,
                                   self.const.name_full)

        # TODO: This should NOT be put in bofhd_core, as it should not require
        # the Email module! Subclassing? This is only a quickfix:
        if hasattr(self.const, 'entity_email_target'):
            if entity_type == self.const.entity_email_target:
                etarget = Factory.get('EmailTarget')(self.db)
                etarget.find(entity_id)
                return '%s:%s' % (
                    six.text_type(etarget.get_target_type_name()),
                    self._get_entity_name(etarget.get_target_entity_id()))
            elif entity_type == self.const.entity_email_address:
                ea = Email.EmailAddress(self.db)
                ea.find(entity_id)
                return ea.get_address()

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
                return "%s:%s" % (six.text_type(entity_type), entity_id)
        except Errors.NotFoundError:
            return "notfound:%r" % entity_id
        # NOTREACHED
        assert False

    def _parse_date(self, date):
        """Convert a written date into DateTime object.  Possible
        syntaxes are:

            YYYY-MM-DD       (2005-04-03)
            YYYY-MM-DDTHH:MM (2005-04-03T02:01)
            THH:MM           (T02:01)

        Time of day defaults to midnight.  If date is unspecified, the
        resulting time is between now and 24 hour into future.

        """
        if not date:
            # TBD: Is this correct behaviour?  mx.DateTime.DateTime
            # objects allow comparison to None, although that is
            # hardly what we expect/want.
            return None
        if isinstance(date, DateTime.DateTimeType):
            # Why not just return date?  Answer: We do some sanity
            # checks below.
            date = date.Format("%Y-%m-%dT%H:%M")
        if date.count('T') == 1:
            date, time = date.split('T')
            try:
                hour, min = [int(x) for x in time.split(':')]
            except ValueError:
                raise CerebrumError("Time of day must be on format HH:MM")
            if date == '':
                now = DateTime.now()
                target = DateTime.Date(now.year, now.month, now.day, hour, min)
                if target < now:
                    target += DateTime.DateTimeDelta(1)
                date = target.Format("%Y-%m-%d")
        else:
            hour = min = 0
        try:
            y, m, d = [int(x) for x in date.split('-')]
        except ValueError:
            raise CerebrumError("Dates must be on format YYYY-MM-DD")
        # TODO: this should be a proper delta, but rather than using
        # pgSQL specific code, wait until Python has standardised on a
        # Date-type.
        if y > 2050:
            raise CerebrumError("Too far into the future: %r" % date)
        if y < 1800:
            raise CerebrumError("Too long ago: %r" % date)
        try:
            return DateTime.Date(y, m, d, hour, min)
        except:
            raise CerebrumError("Illegal date: %r" % date)

    def _parse_date_from_to(self, date):
        """ Parse two dates, separated by '--'. """
        date_start = self._today()
        date_end = None
        if date:
            tmp = date.split("--")
            if len(tmp) == 2:
                if tmp[0]:  # string could start with '--'
                    date_start = self._parse_date(tmp[0])
                date_end = self._parse_date(tmp[1])
            elif len(tmp) == 1:
                date_end = self._parse_date(date)
            else:
                raise CerebrumError("Incorrect date specification: %r" % date)
        return (date_start, date_end)

    def _today(self):
        """ Get today. """
        return self._parse_date("%d-%d-%d" % time.localtime()[:3])

    def _ticks_to_date(self, ticks):
        """ Ticks to timestamp. """
        if ticks is None:
            return None
        return DateTime.DateTimeFromTicks(ticks)


class BofhdCommonMethods(BofhdCommandBase):
    """Class with common methods that is used by most, 'normal' instances.

    Instances that requires some special care for some methods could subclass
    those in their own institution-specific class
    (modules.no.<inst>.bofhd_<inst>_cmds.py:BofhdExtension).

    The methods are using the BofhdAuth that is defined in the institution's
    subclass - L{BofhdExtension.authz}.

    """

    @property
    def util(self):
        try:
            return self.__util
        except AttributeError:
            self.__util = BofhdUtils(self.db)
            return self.__util

    # Each subclass defines its own class attribute containing the relevant
    # commands.
    # Any command defined in 'all_commands' or 'hidden_commands' are callable
    # from clients.
    all_commands = {}

    ##
    # User methods

    #
    # user delete
    #
    all_commands['user_delete'] = cmd.Command(
        ("user", "delete"),
        cmd.AccountName(),
        perm_filter='can_delete_user')

    def user_delete(self, operator, accountname):
        account = self._get_account(accountname)
        self.ba.can_delete_user(operator.get_entity_id(), account)
        if account.is_deleted():
            raise CerebrumError("User is already deleted")
        account.deactivate()
        account.write_db()
        return u"User %s is deactivated" % account.account_name

    ##
    # Group methods

    #
    # group create
    #
    all_commands['group_create'] = cmd.Command(
        ("group", "create"),
        cmd.GroupName(help_ref="group_name_new"),
        cmd.SimpleString(help_ref="string_description"),
        fs=cmd.FormatSuggestion(
            "Group created, internal id: %i", ("group_id",)
        ),
        perm_filter='can_create_group')

    def group_create(self, operator, groupname, description):
        """ Standard method for creating normal groups.

        BofhdAuth's L{can_create_group} is first checked. The group gets the
        spreads as defined in L{cereconf.BOFHD_NEW_GROUP_SPREADS}.
        """
        self.ba.can_create_group(operator.get_entity_id(),
                                 groupname=groupname)
        g = self.Group_class(self.db)
        # Check if group name is already in use, raise error if so
        duplicate_test = g.search(name=groupname, filter_expired=False)
        if len(duplicate_test) > 0:
            raise CerebrumError("Group name is already in use")
        g.populate(creator_id=operator.get_entity_id(),
                   visibility=self.const.group_visibility_all,
                   name=groupname,
                   description=description)
        g.write_db()
        for spread in cereconf.BOFHD_NEW_GROUP_SPREADS:
            g.add_spread(self.const.Spread(spread))
            g.write_db()
        return {'group_id': int(g.entity_id)}

    #
    # group rename
    #
    all_commands['group_rename'] = cmd.Command(
        ('group', 'rename'),
        cmd.GroupName(help_ref="group_name"),
        cmd.GroupName(help_ref="group_name_new"),
        fs=cmd.FormatSuggestion(
            "Group renamed to %s. Check integrations!", ("new_name",)
        ),
        perm_filter='is_superuser')

    def group_rename(self, operator, groupname, newname):
        """ Rename a Cerebrum group.

        Warning: This creates issues for fullsyncs that doesn't handle state.
        Normally, the old group would get deleted and lose any data attached to
        it, and a shiny new one would be created. Do not use unless you're
        aware of the consequences!

        """
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Only superusers may rename groups, due "
                                   "to its consequences!")
        gr = self._get_group(groupname)
        gr.group_name = newname
        try:
            gr.write_db()
        except gr._db.IntegrityError as e:
            raise CerebrumError("Couldn't rename group: %s" % e)
        return {
            'new_name': gr.group_name,
            'group_id': int(gr.entity_id),
        }

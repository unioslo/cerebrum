# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

class Parameter(object):
    """Defines some properties for an attribute.  If any arguments in
    the __init__ constructor are None, they may be overridden in a
    subclass's definition."""

    def __init__(self, optional=False, default=None, repeat=False,
                 help_ref=None):
        """
        optional   : boolean if argument is optional
        default    : string or callable method to get the default value
                     for this parameter.  If None, the value has no default
                     value
        repeat     : boolean if object is repeatable
        help_ref   : to override the help_ref defined in the class
        """

        for k, v in locals().items():
            attr = '_' + k
            if v is None:
                # If a constructor argument is None, it should only
                # become an instance attribute iff this would not
                # shadow any class attribute with the same name.
                if not hasattr(self, attr):
                    setattr(self, attr, None)
                else:
                    pass
            else:
                setattr(self, attr, v)

    def get_struct(self, bofhd_ref):
        ret = {}
        for k in ('_optional', '_repeat', '_type', '_help_ref'
                  # '_prompt',
                  ):
            if getattr(self, k) is not None and getattr(self, k) != 0:
                ret[k[1:]] = getattr(self, k)
        ret['prompt'] = self.getPrompt(bofhd_ref)
        if self._default is not None:
            if isinstance(self._default, str):
                ret['default'] = self._default
            else:
                ret['default'] = 1  # = call get_default_param
        return ret

    def getPrompt(self, bofhd_ref):
        # print "Get: %s" % self._help_ref
        return bofhd_ref.server.help.arg_help[self._help_ref][1]

class AccountName(Parameter):
    _tab_func = 'tab_foobar'
    _type = 'accountName'
    _help_ref = 'account_name'

class AccountPassword(Parameter):
    _type = 'accountPassword'
    _help_ref = 'account_password'

class Affiliation(Parameter):
    _type = 'affiliation'
    _help_ref = 'affiliation'

class AffiliationStatus(Parameter):
    _type = 'affiliationStatus'
    _help_ref = 'affiliation_status'

class SourceSystem(Parameter):
    _type = 'sourceSystem'
    _help_ref = 'source_system'
    
class Date(Parameter):
    _type = 'date'
    _help_ref = 'date'

class DiskId(Parameter):
    _type = 'disk'
    _help_ref = 'disk'

class EmailAddress(Parameter):
    _type = 'emailAddress'
    _help_ref = 'email_address'
    
class EntityType(Parameter):
    _type = 'entityType'
    _help_ref = 'entity_type'

class GroupName(Parameter):
    # _prompt_func = 'prompt_foobar'
    _type = 'groupName'
    _help_ref = 'group_name'

class GroupSearchType(Parameter):
    _type = 'groupSearchType'
    _help_ref = 'group_search_type'

class GroupOperation(Parameter):
    _tab_func = 'tab_foobar'
    _type = 'groupOperation'
    _help_ref = 'group_operation'

class GroupVisibility(Parameter):
    _tab_func = 'tab_foobar'
    _type = 'groupVisibility'
    _help_ref = 'group_visibility'

class Id(Parameter):
    _tab_func = 'tab_foobar'
    _type = 'id'
    _help_ref = 'id'

class Integer(Parameter):
    _type = 'integer'
    _help_ref = 'integer'

class MoveType(Parameter):
    _type = 'moveType'
    _help_ref = 'move_type'

class OpSet(Parameter):
    _type = 'opSet'
    _help_ref = 'opset'

class OU(Parameter):
    _type = 'ou'
    _help_ref = 'ou'

class PersonId(Parameter):
    _type = 'personId'
    _help_ref = 'person_id'

class PersonName(Parameter):
    _type = 'personName'
    _help_ref = 'person_name'

class PersonNameType(Parameter):
    _type = 'personNameType'
    _help_ref = 'person_name_type'

class PersonSearchType(Parameter):
    _type = 'personSearchType'
    _help_ref = 'person_search_type'

class PosixGecos(Parameter):
    _type = 'posixGecos'
    _help_ref = 'posix_gecos'

class PosixShell(Parameter):
    _type = 'posixShell'
    _help_ref = 'posix_shell'

class QuarantineType(Parameter):
    _type = 'quarantineType'
    _help_ref= 'quarantine_type'
    
class SimpleString(Parameter):
    _type = 'simpleString'
    _help_ref = 'string'

class Spread(Parameter):
    _type = 'spread'
    _help_ref = 'spread'

class UserSearchType(Parameter):
    _type = 'userSearchType'
    _help_ref = 'user_search_type'

class YesNo(Parameter):
    _type = 'yesNo'
    _help_ref = 'yesNo'

class Command(object):
    def __init__(self, cmd, *params, **kw):
        self._cmd = cmd
        if len(params) == 0:
            params = None
        self._params = params
        self._format_suggestion = kw.get('fs', None)
        self._prompt_func = kw.get('prompt_func', None)
        self.perm_filter = kw.get('perm_filter', None)
        assert self._params is None or self._prompt_func is None
        self._default = None

    def get_fs(self):
        if self._format_suggestion is not None:
            return self._format_suggestion.get_format()
        else:
            return None

    def get_struct(self, bofhd_ref):
        if self._params is not None:
            return (self._cmd, [k.get_struct(bofhd_ref) for k in self._params])
        if self._prompt_func is not None:
            return (self._cmd, 'prompt_func')  # Flags that command has prompt_func
        return (self._cmd,)

class FormatSuggestion(object):
    """FormatSuggestion is used by the client to determine how to
    format a return value from a command."""
    
    def __init__(self, string, vars=None, hdr=None):
        """For description of the parameters, see get_format().  The
        only difference is that string may contain format specifiers
        even if it is a plain string, provided that vars is set."""

        if vars is None:
            self._string_vars = string
        else:
            self._string_vars = [(string, vars)]
        self._hdr = hdr

    def get_format(self):
        """Returns a dict with the following keys:

        - str_vars:
        
          - If it is a string, the string is displayed as is. 
          - May also be a list of (string, vars) pairs:
          
            - string is a plain string.  It may contain printf format
              specifiers used by vars.  string may also be a list of
              (string, vars, hdr) pairs.  hdr is optional.  If hdr
              contains the character %, hdr will be used instead of
              string for the first data.
            - vars is a list of variable name who must correspond to
              keys in the dict that the FormatSuggestion should be
              applied to.  If none of the keys are present, the string
              should not be shown.  The ordering of the keys should
              match the printf format specifiedrs in string.

              The key may be prepended with :yyyy-MM-dd to format the
              returned date object.  The format-specifier is the same
              as used by java.text.SimpleDateFormat
        - hdr: an optional header to be displayed before the data.
        """

        ret = {'str_vars': self._string_vars}
        if self._hdr is not None:
            ret['hdr'] = self._hdr
        return ret

if __name__ == '__main__':
    all_commands = {
        ## bofh> account create <accountname> <idtype> <id> \
        ##         <affiliation=> <ou=> [<expire_date>]
        'account_create': Command(('account', 'create'),
                                  AccountName(ptype="new"), PersonIdType(),
                                  PersonId(), Affiliation(default=True),
                                  OU(default=True), Date(optional=True)),
        ## bofh> person find {<name> | <id> [<id_type>] | <birth_date>}
        'person_find': Command(("person", "find"),
                               Id(), PersonIdType(optional=True)),
        ## bofh> group add <entityname+> <groupname+> [<op>]
        'group_add': Command(("group", "add"),
                             GroupName("source", repeat=True),
                             GroupName("destination", repeat=True),
                             GroupOperation(optional=True))
        }

    print all_commands['account_create'].get_struct()

# arch-tag: fdde8173-3d4a-4699-8dd3-4d0972d5765d

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
                 ptype=None, prompt=None):
        """
        optional   : boolean if argument is optional
        default    : string or callable method to get the default value
                     for this parameter.  If None, the value has no default
                     value
        repeat     : boolean if object is repeatable
        prompt     : to override the prompt string defined in the class
        ptype      : 'prompt type', string inserted in the prompt
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

    def get_struct(self):
        ret = {}
        for k in ('_optional', '_repeat', '_type',
                  # '_prompt',
                  ):
            if getattr(self, k) is not None and getattr(self, k) != 0:
                ret[k[1:]] = getattr(self, k)
        ret['prompt'] = self.getPrompt()
        if self._default is not None:
            if isinstance(self._default, str):
                ret['default'] = self._default
            else:
                ret['default'] = 1  # = call get_default_param
        return ret

    def getPrompt(self):
        if self._ptype is not None:
            return self._prompt % (self._ptype+" ")
        try:
            self._prompt.index("%s")
            return self._prompt % ""
        except ValueError:
            pass
        return self._prompt

class AccountName(Parameter):
    _tab_func = 'tab_foobar'
    _type = 'accountName'
    _prompt = "Enter %saccountname"

class AccountPassword(Parameter):
    _type = 'accountPassword'
    _prompt = "Enter password"

class Affiliation(Parameter):
    _type = 'affiliation'
    _prompt = "Enter affiliation"

class AffiliationStatus(Parameter):
    _type = 'affiliationStatus'
    _prompt = "Enter affiliation status"

class Date(Parameter):
    _type = 'date'
    _prompt = "Enter %sdate"

class DiskId(Parameter):
    _type = 'disk'
    _prompt = "Enter %sdisk"

class Description(Parameter):
    _type = 'description'
    _prompt = "Enter description"

class EntityName(Parameter):
    _type = 'entityName'
    _prompt = "Enter %sentity name"

class GroupName(Parameter):
    # _prompt_func = 'prompt_foobar'
    _type = 'groupName'
    _prompt = "Enter %sgroupname"

class GroupOperation(Parameter):
    _tab_func = 'tab_foobar'
    _type = 'groupOperation'
    _prompt = "Enter group operation"

class GroupVisibility(Parameter):
    _tab_func = 'tab_foobar'
    _type = 'groupVisibility'
    _prompt = "Enter visibility"

class Id(Parameter):
    _tab_func = 'tab_foobar'
    _type = 'id'
    _prompt = "Enter id"

class OU(Parameter):
    _type = 'ou'
    _prompt = "Enter OU"

class PersonId(Parameter):
    _type = 'personId'
    _prompt = "Enter person id"

class PersonIdType(Parameter):
    _type = 'personIdType'
    _prompt = "Enter idtype"

class PersonNameType(Parameter):
    _type = 'personNameType'
    _prompt = "Enter nametype"

class PersonName(Parameter):
    _type = 'personName'
    _prompt = "Enter person name"

class PosixHome(Parameter):
    _type = 'posixHome'
    _prompt = "Enter home directory"

class PosixShell(Parameter):
    _type = 'posixShell'
    _prompt = "Enter shell"

class SimpleString(Parameter):
    _type = 'simpleString'
    _prompt = "%s"

class PosixGecos(Parameter):
    _type = 'posixGecos'
    _prompt = "Enter gecos"

class Command(object):
    def __init__(self, cmd, *params, **kw):
        self._cmd = cmd
        if len(params) == 0:
            params = None
        self._params = params
        self._format_suggestion = kw.get('fs', None)
        self._prompt_func = kw.get('prompt_func', None)
        assert self._params is None or self._prompt_func is None
        self._default = None

    def get_fs(self):
        if self._format_suggestion is not None:
            return self._format_suggestion.get_format()
        else:
            return None

    def get_struct(self):
        if self._params is not None:
            return (self._cmd, [k.get_struct() for k in self._params])
        if self._prompt_func is not None:
            return (self._cmd, 'prompt_func')
        return (self._cmd,)

class FormatSuggestion(object):
    def __init__(self, string, vars, hdr=None):
        self._string = string
        self._vars = vars
        self._hdr = hdr

    def get_format(self):
        ret = {'str': self._string, 'var': self._vars}
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

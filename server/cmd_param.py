#!/usr/bin/env python2.2

class Parameter(object):
    """Defines some properties for an attribute.  If any arguments in
    the __init__ constructor are None, they may be overridden in a
    subclass's definition."""

    def __init__(self, name=None, optional=0, default=0, repeat=0, ptype=None,
                 prompt_func=None, tab_func=None, prompt=None):
        self._name = name

        for k in locals().keys():
            if locals()[k] is None:
                if not hasattr(self, '_'+k):
                    setattr(self, '_'+k, None)
                else:
                    pass   # Already set
            else:
                setattr(self, '_'+k, locals()[k])

    def get_struct(self):
        ret = {}
        for k in ('_name', '_optional', '_default', '_repeat', '_type',
                  # '_prompt', '_prompt_func', '_tab_func'
                  ):
            if getattr(self, k) is not None and getattr(self, k) != 0:
                ret[k[1:]] = getattr(self, k)
        return ret

    def getPrompt(self):
        # Should probably flag if type has a %s argument instead
        if self._ptype is not None:
            return self._prompt % self._ptype
        return self._prompt

class AccountName(Parameter):
    _tab_func = 'tab_foobar'
    _type = 'accountName'
    _prompt = "Enter %s accountname"

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
    _prompt = "Enter %s date"

class Description(Parameter):
    _type = 'description'
    _prompt = "Enter description"

class EntityName(Parameter):
    _type = 'entityName'
    _prompt = "Enter entity name"

class GroupName(Parameter):
    _prompt_func = 'prompt_foobar'
    _type = 'groupName'
    _prompt = "Enter %s groupname"

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

class PosixGecos(Parameter):
    _type = 'posixGecos'
    _prompt = "Enter gecos"

class Command(object):
    def __init__(self, cmd, *params, **kw):
        self._cmd = cmd
        self._params = params
        self._format_suggestion = kw.get('fs', None)

    def get_fs(self):
        return self._format_suggestion.get_format()

    def get_struct(self):
        return (self._cmd, [k.get_struct() for k in self._params])

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
        ## bofh> account create <accountname> <idtype> <id> <affiliation= <ou= [<expire_date>]
        'account_create': Command(('account', 'create'), AccountName(ptype="new"), PersonIdType(), PersonId(),
                                  Affiliation(default=1), OU(default=1), Date(optional=1)),
        ## bofh> person find {<name> | <id> [<id_type>] | <birth_date>}
        'person_find': Command(("person", "find") , Id(), PersonIdType(optional=1)),
        ## bofh> group add <entityname+> <groupname+> [<op>]
        'group_add': Command(("group", "add"), GroupName("source", repeat=1),
                             GroupName("destination", repeat=1), GroupOperation(optional=1))
        }
    
    print all_commands['account_create'].get_struct()

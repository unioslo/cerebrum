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

    def getStruct(self):
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

class PersonIdType(Parameter):
    _type = 'personIdType'
    _prompt = "Enter idtype"

class PersonId(Parameter):
    _type = 'personId'
    _prompt = "Enter person id"

class PersonName(Parameter):
    _type = 'personName'
    _prompt = "Enter person name"

class Affiliation(Parameter):
    _type = 'affiliation'
    _prompt = "Enter affiliation"

class Date(Parameter):
    _type = 'date'
    _prompt = "Enter %s date"

class OU(Parameter):
    _type = 'ou'
    _prompt = "Enter OU"

class Id(Parameter):
    _tab_func = 'tab_foobar'
    _type = 'id'
    _prompt = "Enter id"

class GroupName(Parameter):
    _prompt_func = 'prompt_foobar'
    _type = 'groupName'
    _prompt = "Enter %s groupname"

class GroupOperation(Parameter):
    _tab_func = 'tab_foobar'
    _type = 'groupOperation'
    _prompt = "Enter group operation"

class Command(object):
    def __init__(self, cmd, *params):
        self._cmd = cmd
        self._params = params

    def getStruct(self):
        return (self._cmd, [k.getStruct() for k in self._params])

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
    
    print all_commands['account_create'].getStruct()

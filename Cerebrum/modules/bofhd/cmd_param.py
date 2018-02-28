#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2002-2018 University of Oslo, Norway
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

    def get_struct(self, help_ref):
        ret = {}
        for k in ('_optional', '_repeat', '_type', '_help_ref'
                  # '_prompt',
                  ):
            if getattr(self, k) is not None and getattr(self, k) != 0:
                ret[k[1:]] = getattr(self, k)
        ret['prompt'] = self.getPrompt(help_ref)
        if self._default is not None:
            if isinstance(self._default, basestring):
                ret['default'] = self._default
            else:
                ret['default'] = 1  # = call get_default_param
        return ret

    def getPrompt(self, help_ref):
        arg_help = help_ref.arg_help
        if self._help_ref not in arg_help:
            # TODO: Fix
            # bofhd_ref.logger.warn("Missing arg_help item <%s>",
            #                       self._help_ref)
            return ""

        return arg_help[self._help_ref][1]
    # end getPrompt


class AccountName(Parameter):
    _tab_func = 'tab_foobar'
    _type = 'accountName'
    _help_ref = 'account_name'


class AccountPassword(Parameter):
    _type = 'accountPassword'
    _help_ref = 'account_password'


class AddressType(Parameter):
    _type = 'addressType'
    _help_ref = 'address_type'


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


# named DateTimeString due to namespace conflicts with DateTime
# import from mx module.
class DateTimeString(Parameter):
    _type = 'datetime'
    _help_ref = 'datetime'


class DiskId(Parameter):
    _type = 'disk'
    _help_ref = 'disk'


class EmailAddress(Parameter):
    _type = 'emailAddress'
    _help_ref = 'email_address'


class EntityType(Parameter):
    _type = 'entityType'
    _help_ref = 'entity_type'


class ExternalIdType(Parameter):
    _type = 'externalIdType'
    _help_ref = 'external_id_type'


class GroupExchangeAttr(Parameter):
    _type = 'groupExchangeAttr'
    _help_ref = 'group_exchange_attr'


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


class MemberName(Parameter):
    _type = 'memberName'
    _help_ref = 'member_name_src'


class MemberType(Parameter):
    _type = 'memberType'
    _help_ref = 'member_type'


class Id(Parameter):
    _tab_func = 'tab_foobar'
    _type = 'id'
    _help_ref = 'id'


class Integer(Parameter):
    _type = 'integer'
    _help_ref = 'integer'


class Mobile(Parameter):
    """ Mobile phone Parameter. """

    _type = 'mobilePhone'
    _help_ref = 'mobile_phone'


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
    _help_ref = 'quarantine_type'


class SimpleString(Parameter):
    _type = 'simpleString'
    _help_ref = 'string'


class SMSString(Parameter):
    _type = 'simpleString'
    _help_ref = 'string_sms'


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

    def get_struct(self, help_ref):
        if self._params is not None:
            return (self._cmd, [k.get_struct(help_ref) for k in self._params])
        if self._prompt_func is not None:
            # Flag that command has prompt_func:
            return (self._cmd, 'prompt_func')
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

    def __call__(self, response):
        """ Format bofhd return response.

        This is the reference spec for formatting bofh response data.
        It can be used to test that a FormatStuggestion works as expected.

        :param response:
            The de-serialized xml-response (from `xmlrpclib.loads()`).
            Note that any client-specific casts *should* be performed before
            feeding into this method (e.g. convert xmlrpclib.Binary to
            bytestring). This typically implies feeding the response through a
            `xmlrpc_to_native` function.

        :return str:
            Returns a formatted string.
        """
        # This is a copy of the pybofh formatting implementation, from:
        #
        #     ssh://git@bitbucket.usit.uio.no:7999/crb/pybofh.git
        #     Commit f7f0c71295b490c925af635408a8ced8047820f7

        def _fmt_date(fmt):
            """ Simple thing to convert dates """
            #       (subst, with),
            reps = (("yyyy", "%Y"),
                    ("MM", "%m"),
                    ("dd", "%d"),
                    ("HH", "%H"),
                    ("mm", "%M"))
            return reduce(lambda form, rep: form.replace(*rep), reps, fmt)

        def _fmt_field(entry, field):
            field = field.split(":", 2)
            val = entry[field[0]]
            if len(field) == 3:
                if field[1] == 'date':
                    fmt = _fmt_date(field[2])
                else:
                    raise KeyError(field[1])
                if val is not None:
                    return val.strftime(fmt.encode("ascii"))
            if val is None:
                return "<not set>"
            return val

        lines = []
        suggestion = self.get_format()

        if "hdr" in suggestion:
            lines.append(suggestion["hdr"])

        st = suggestion['str_vars']
        if isinstance(st, basestring):
            lines.append(st)
        else:
            for row in st:
                if len(row) == 3:
                    fmt, fields, sub_hdr = row
                    if "%" in sub_hdr:
                        fmt, sub_hdr = sub_hdr, None
                else:
                    fmt, fields = row
                    sub_hdr = None
                if sub_hdr:
                    lines.append(sub_hdr)
                if not isinstance(response, (list, tuple)):
                    response = [response]
                for entry in response:
                    if isinstance(entry, basestring):
                        lines.append(entry)
                        continue
                    try:
                        positions = tuple(_fmt_field(entry, field)
                                          for field in fields)
                    except KeyError:
                        continue
                    lines.append(fmt % positions)
        return '\n'.join(lines)


if __name__ == '__main__':
    all_commands = {
        # bofh> account create <accountname> <id>
        #         <affiliation=> <ou=> [<expire_date>]
        'account_create': Command(
            ('account', 'create'),
            AccountName(ptype="new"),
            PersonId(),
            Affiliation(default=True),
            OU(default=True),
            Date(optional=True)
        ),
        # bofh> person find <search-type> <search-value>
        'person_find': Command(
            ("person", "find"),
            PersonSearchType(),
            SimpleString()
        ),
        # bofh> group add <entityname+> <groupname+> [<op>]
        'group_add': Command(
            ("group", "add"),
            GroupName("source", repeat=True),
            GroupName("destination", repeat=True)
        )
    }

    print all_commands['account_create'].get_struct()

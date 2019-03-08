# -*- coding: utf-8 -*-
# Copyright 2018 University of Oslo, Norway
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

"""Constants for the Consent module"""

from Cerebrum import Constants as cereconst


class _ConsentTypeCode(cereconst._CerebrumCode):
    """Code to represent the type of code.
    Two values should exist: opt-in and opt-out"""
    _lookup_table = '[:table schema=cerebrum name=consent_type_code]'

    # It is really EntityConsentCode that depends on EntityType,
    # But two dependencies is not supported by regular constants.
    # This will do the trick.
    _insert_dependency = cereconst.Constants.EntityType


class _EntityConsentCode(cereconst._CerebrumCodeWithEntityType):
    """The specific consent/agreement.
    Depends on having entity_type, as well as ConsentTypes.
    """
    _insert_dependency = _ConsentTypeCode
    _lookup_table = '[:table schema=cerebrum name=entity_consent_code]'

    def __init__(self, code, entity_type=None, consent_type=None,
                 description=None, lang=None):
        if consent_type is not None:
            if not isinstance(consent_type, _ConsentTypeCode):
                consent_type = _ConsentTypeCode(consent_type)
            self._consent_type = consent_type
        super(_EntityConsentCode, self).__init__(code,
                                                 entity_type=entity_type,
                                                 description=description,
                                                 lang=lang)

    def insert(self):
        """Insert code into database"""
        self.sql.execute("""
        INSERT INTO %(code_table)s
          (consent_type, entity_type, %(code_col)s, %(str_col)s, %(desc_col)s)
        VALUES
          (:consent_type, :entity_type, %(code_seq)s, :str, :desc)""" % {
            'code_table': self._lookup_table,
            'code_col': self._lookup_code_column,
            'str_col': self._lookup_str_column,
            'desc_col': self._lookup_desc_column,
            'code_seq': self._code_sequence},
            {'entity_type': int(self.entity_type),
             'consent_type': int(self.consent_type),
             'str': self.str,
             'desc': self._desc})

    @property
    def consent_type(self):
        """This code's consent type"""
        if not hasattr(self, '_consent_type'):
            self._consent_type = _ConsentTypeCode(self.sql.query_1(
                """
                SELECT consent_type
                FROM %(table)s
                WHERE %(code_col)s = :code
                """ % {'table': self._lookup_table,
                       'code_col': self._lookup_code_column},
                {'code': int(self)}))
        return self._consent_type


class Constants(cereconst.Constants):
    ConsentType = _ConsentTypeCode
    EntityConsent = _EntityConsentCode
    consent_opt_in = _ConsentTypeCode('opt-in', 'Consent actively given')
    consent_opt_out = _ConsentTypeCode('opt-out',
                                       'Consent assumed unless declined')


class CLConstants(cereconst.CLConstants):
    consent_approve = cereconst._ChangeTypeCode(
        'consent', 'approve',
        '%(subject)s gives consent',
        ("type=%(string:consent_string)s", "expiry=%(timestamp:expiry)s",
         "description=%(string:description)s"))
    consent_decline = cereconst._ChangeTypeCode(
        'consent', 'decline',
        '%(subject)s declines consent',
        ("type=%(string:consent_string)s", "expiry=%(timestamp:expiry)s",
         "description=%(string:description)s"))
    consent_remove = cereconst._ChangeTypeCode(
        'consent', 'delete',
        '%(subject)s deletes consent',
        ("type=%(string:consent_string)s", ))

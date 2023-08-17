#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2006-2023 University of Oslo, Norway
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
"""
Module to resolve AD attribute values.

Various helpers to resolve CanonicalName and ProfilePath for Active Directory
at HiOF.  These values can be generated from a location code affiliated with a
given user account.

The module uses different rules for each AD domain.  Most locations *could*
identify department by using a subset of the location code, but as there are a
lot of exceptions, we use a mapping table that looks at the full location code.

Each mapper has three key methods:

getDN(username, location_code)
    Get an appropriate DN for the user account

getProfilePath(username, location_code)
    Get an appropriate ProfilePath for the user account

getHome(username, location_code)
    Get an appropriate Home directory for the user account
"""
import unittest


class MappingError(Exception):
    pass


class Adm(object):

    DOMAIN_NAME = "adm.hiof.no"

    DOMAIN_DN = ""

    # Server for non personal accounts
    non_personal_serv = 'olivia'

    sted_mapping = {
        '00': 'olivia',
        '10': 'olivia',
        '20': 'katta',   # tidligere tana, enda tidligere tora
        '30': 'katta',
        '35': 'katta'
    }

    def getDN(self, uname, sko):  # noqa: N802
        serv = Adm.sted_mapping[sko[-2:]]
        return ("CN=%s,OU=Ansatte %s%s"
                % (uname, serv.capitalize(), Adm.DOMAIN_DN))

    def getProfilePath(self, uname, sko=None):  # noqa: N802
        if sko:
            serv = Adm.sted_mapping[sko[-2:]]
        else:
            serv = Adm.non_personal_serv
        return r"\\%s\home\%s\profile" % (serv, uname)

    def getHome(self, uname, sko=None):  # noqa: N802
        if sko:
            serv = Adm.sted_mapping[sko[-2:]]
        else:
            serv = Adm.non_personal_serv
        return r"\\%s\home\%s" % (serv, uname)


class Fag(object):

    DOMAIN_NAME = "fag.hiof.no"

    DOMAIN_DN = ""

    non_personal_avdeling = 'LU'

    sted_mapping = {
        ('*', '*', '00'): 'Halden',
        ('*', '*', '10'): 'Halden',
        ('*', '*', '20'): 'Sarp',
        ('*', '*', '30'): 'Fredr',
        ('*', '*', '35'): 'Fredr',
        ('*', '*', '40'): 'Fredr',
        ('98', '10', '*'): 'Halden'
    }

    avdeling_mapping = {
        # New: very special employees at Fellestjeneste :-)
        ('00', '*', '00'): {'All': 'LU'},
        ('00', '*', '10'): {'All': 'LU'},
        ('00', '*', '20'): {'All': 'IR'},
        ('00', '*', '30'): {'All': 'HS'},
        # New: very special employees at Fellestjeneste :-)
        ('20', '*', '00'): {'All': 'FT'},
        ('20', '*', '10'): {'All': 'LU'},
        ('20', '*', '20'): {'All': 'IR'},
        ('20', '*', '30'): {'All': 'HS'},
        ('22', '*', '00'): {'All': 'IT'},
        ('22', '*', '10'): {'All': 'IT'},
        ('22', '*', '20'): {'All': 'IR'},
        ('22', '*', '30'): {'All': 'HS'},
        ('22', '99', '10'): {'All': 'LU',
                             'Profile': None},
        ('24', '*', '10'): {'All': 'LU'},
        ('24', '*', '20'): {'All': 'IR'},
        ('24', '*', '30'): {'All': 'HS'},
        ('26', '*', '10'): {'All': 'LU'},
        ('26', '*', '20'): {'All': 'IR'},
        ('26', '*', '30'): {'All': 'HS'},
        ('26', '*', '35'): {'All': 'HS'},
        ('30', '*', '00'): {'All': 'LU'},
        ('30', '*', '10'): {'All': 'LU'},
        ('30', '*', '20'): {'All': 'IR'},
        ('40', '*', '*'): {'All': 'HS'},
        ('50', '*', '*'): {'All': 'IR'},
        ('55', '*', '*'): {'All': 'IT'},
        ('60', '*', '*'): {'All': 'SF'},
        ('70', '*', '*'): {'All': 'SCE'},
        ('80', '*', '*'): {'All': 'SKUT'},
        ('90', '*', '*'): {'All': 'SF'},
        ('98', '00', '10'): {'All': 'LU'},
        ('98', '00', '20'): {'All': 'IR'},
        ('98', '00', '30'): {'All': 'HS'},
        ('98', '00', '35'): {'All': 'SCE'},
        ('98', '10', '*'): {'All': 'SIO'},
        ('98', '15', '20'): {'All': 'IR'},
        ('98', '20', '10'): {'All': 'LU'},
        ('98', '20', '20'): {'All': 'IR'},
        ('98', '20', '30'): {'All': 'HS'},
    }

    def _find_best_match(self, sko, mapping):
        """
        Find best match for a given location code in a given mapping.

        Returns the *most specific* entry, i.e. the entry with the fewest
        wildcards.  If a given location code (sko) is 123456, then
        ``('12','34','*')`` is a better match than ``('12','*','*')``.
        """

        key = (sko[0:2], sko[2:4], sko[4:6])
        best_match_score = -1
        best_match = None
        for k, v in mapping.items():
            matches = True
            match_score = 0
            for n in range(3):
                if(not (k[n] == key[n] or k[n] == '*')):
                    matches = False
                    break
                if k[n] == key[n]:
                    match_score += 1
            if matches and match_score > best_match_score:
                best_match_score = match_score
                best_match = v
        if best_match is None:
            raise MappingError("No map-match for sko='%s'" % sko)
        return best_match

    def _get_sted(self, sko):
        return self._find_best_match(sko, Fag.sted_mapping)

    def _get_avdeling(self, sko):
        return self._find_best_match(sko, Fag.avdeling_mapping)

    def getDN(self, uname, sko):  # noqa: N802
        tmp = self._get_avdeling(sko)
        avdeling = tmp.get('Canon', tmp['All'])
        sted = self._get_sted(sko)
        return ("CN=%s,OU=%s,OU=%s,OU=Ansatte%s"
                % (uname, avdeling, sted, Fag.DOMAIN_DN))

    def getProfilePath(self, uname, sko=None):  # noqa: N802
        avdeling = Fag.non_personal_avdeling
        if sko:
            tmp = self._get_avdeling(sko)
            avdeling = tmp.get('Profile', tmp['All'])
        # Some sko implies no profile path
        if avdeling is None:
            return ""  # Must return empty string, not None
        else:
            return r"\\%s\Profile\%s\%s" % (Fag.DOMAIN_NAME, avdeling, uname)

    def getHome(self, uname, sko=None):  # noqa: N802
        avdeling = Fag.non_personal_avdeling
        if sko:
            tmp = self._get_avdeling(sko)
            avdeling = tmp.get('Home', tmp['All'])
        return r"\\%s\Home\%s\%s" % (Fag.DOMAIN_NAME, avdeling, uname)


class Student(Fag):

    DOMAIN_NAME = "stud.hiof.no"

    DOMAIN_DN = ""

    non_personal_avdeling = 'LU'

    def getDN(self, uname, sko, studieprogram):  # noqa: N802
        tmp = self._get_avdeling(sko)
        avdeling = tmp.get('Profile', tmp['All'])
        return ("CN=%s,OU=%s,OU=%s,OU=Studenter%s"
                % (uname, studieprogram, avdeling, Student.DOMAIN_DN))

    def getProfilePath(self, uname, sko=None):  # noqa: N802
        avdeling = Student.non_personal_avdeling
        if sko:
            tmp = self._get_avdeling(sko)
            avdeling = tmp.get('Profile', tmp['All'])
        return r"\\%s\Profile\%s\%s" % (Student.DOMAIN_NAME, avdeling, uname)

    def getHome(self, uname, sko=None):  # noqa: N802
        avdeling = Student.non_personal_avdeling
        if sko:
            tmp = self._get_avdeling(sko)
            avdeling = tmp.get('Profile', tmp['All'])
        return r"\\%s\Home\%s\%s" % (Student.DOMAIN_NAME, avdeling, uname)


class MappingTests(unittest.TestCase, object):

    def test_fag(self):
        fag = Fag()
        self.assertEqual(
            fag.getDN("uname", "260020"),
            'CN=uname,CN=IR,CN=Sarp,CN=Ansatte,DC=fag,DC=hiof,DC=no')
        self.assertEqual(fag.getProfilePath("uname", "260020"),
                         r'\\fag.hiof.no\Profile\IR\uname')
        self.assertEqual(fag.getHome("uname", "260020"),
                         r'\\fag.hiof.no\Home\IR\uname')

    def test_student(self):
        s = Student()
        self.assertEqual(
            s.getDN("uname", "stprog", "260020"),
            'CN=uname,OU=stprog,OU=IR,OU=Studenter,DC=stud,DC=hiof,DC=no')
        self.assertEqual(s.getProfilePath("uname", "260020"),
                         r'\\stud.hiof.no\Profile\IR\uname')
        self.assertEqual(s.getHome("uname", "260020"),
                         r'\\stud.hiof.no\Home\IR\uname')

    def test_adm(self):
        adm = Adm()
        self.assertEqual(adm.getDN("uname", "983020"),
                         'CN=uname,CN=Ansatte Tora,DC=adm,DC=hiof,DC=no')
        self.assertEqual(adm.getProfilePath("uname", "983020"),
                         r'\\tora\uname\profile')
        self.assertEqual(adm.getHome("uname", "983020"),
                         r'\\tora\uname')


if __name__ == '__main__':
    unittest.main()

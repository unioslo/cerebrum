#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2017 University of Oslo, Norway
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
A dedicated module for username generation
"""
import copy
import re
import string

import six

import cereconf

from Cerebrum import Errors
from Cerebrum.Entity import EntityName
from Cerebrum.modules.username_generator.config import load_config


class UsernameGenerator(object):
    """
    Username-generator class
    """

    _simplify_name_cache = [None] * 4

    def __init__(self, config=None, **kw):
        """
        Constructs a UsernameGenerator.

        :param config: The Configuration-object for the
                       username_generator module.
        :type config: Cerebrum.config.configuration.Configuration or None
        """
        try:
            if config is None:
                self.config = load_config()
            else:
                self.config = config
            self.encoding = kw.get('encoding') or self.config.encoding
            # Maybe part of the config in the future...
            self.mappings = {
                u'Ð': u'Dh',
                u'ð': u'dh',
                u'Þ': u'Th',
                u'þ': u'th',
                u'ß': u'ss'}
            self.alt_mappings = {
                u'Æ': u'ae',
                u'æ': u'ae',
                u'Å': u'aa',
                u'å': u'aa'}
        except Exception as e:
            raise Errors.CerebrumError('Unable to create a UsernameGenerator '
                                       'instance: {error}'.format(error=e))

    def simplify_name(self, s, alt=0, as_gecos=0):
        """
        Convert string so that it only contains characters that are
        legal in a posix username.
        If as_gecos=1, it may also be used for the gecos field
        """
        try:
            # make sure that s contains only latin1 compatible characters
            s = self._encode(s)
        except UnicodeEncodeError:
            raise ValueError(
                '{encoding} incompatible characters detected'.format(
                    encoding=self.encoding))
        key = bool(alt) + (bool(as_gecos) * 2)
        try:
            (tr, xlate_subst, xlate_match) = self._simplify_name_cache[key]
        except TypeError:
            xlate = self._encode_dict(self.mappings)
            if alt:
                xlate.update(self._encode_dict(self.alt_mappings))
            xlate_subst = re.compile(r'[^a-zA-Z0-9 -]').sub

            def xlate_match(match):
                return xlate.get(match.group(), '')

            tr = dict(zip(map(six.int2byte,
                              xrange(0200, 0400)), ('x',) * 0200))
            tr.update(dict(zip(
                self._encode(u'ÆØÅæø¿åÀÁÂÃÄÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝàáâãäçèéêëìíîï'
                             u'ñòóôõöùúûüýÿ{[}]|¦\\¨­¯´'),
                self._encode(u'AOAaooaAAAAACEEEEIIIINOOOOOUUUUYaaaaaceeeeiiiin'
                             u'ooooouuuuyyaAaAooO"--\''))))
            for ch in filter(lambda x: x in tr, xlate):
                del tr[ch]
            tr = string.maketrans(''.join(tr.keys()), ''.join(tr.values()))
            if not as_gecos:
                # lowercase the result
                tr = tr.lower()
                xlate = dict(zip(xlate.keys(),
                                 map(six.binary_type.lower, xlate.values())))
            self._simplify_name_cache[key] = (tr, xlate_subst, xlate_match)

        xlated = xlate_subst(xlate_match, s.translate(tr))

        # normalise whitespace and hyphens: only ordinary SPC, only
        # one of them between words, and none leading or trailing.
        xlated = re.sub(r'\s+', " ", xlated)
        xlated = re.sub(r' ?-+ ?', "-", xlated).strip(" -")
        try:
            return xlated.decode()
        except UnicodeEncodeError:
            raise ValueError('ASCII incompatible output produced')

    def suggest_unames(self,
                       domain,
                       fname,
                       lname,
                       maxlen=8,
                       suffix="",
                       prefix="",
                       validate_func=None):
        """
        Returns a tuple with 15 username suggestions based
        on the person's first and last name.

        :param domain: value domain code
        :type domain: str

        :param fname:  first name (and any middle names)
        :type fname: str

        :param lname:  last name
        :type lname: str

        :param maxlen: maximum length of a username (default: 8)
        :type maxlen: int

        :param suffix: str to append to every generated username (default: '')
        :type suffix: str

        :param prefix: string to add to every generated username (default: '')
        :type prefix: str

        :param validate_func: callable object to use for username validation
                              validate_func takes 1 argument (username)
                              (default: None - no validation will be performed)
        :type validate_func: collections.Callable, None
        """
        goal = 15  # We may return more than this
        maxlen -= len(suffix)
        maxlen -= len(prefix)
        assert maxlen > 0, "maxlen - prefix - suffix = no characters left"
        if validate_func is not None:
            assert callable(validate_func)
        potuname = ()

        lastname = self.simplify_name(lname, alt=1)
        if lastname == "":
            raise ValueError(
                "Must supply last name, got '%s', '%s'" % (fname, lname))

        fname = self.simplify_name(fname, alt=1)
        lname = lastname

        if fname == "":
            # This is a person with no first name.  We "fool" the
            # algorithm below by switching the names around.  This
            # will always lead to suggesting names with numerals added
            # to the end since there are only 8 possible usernames for
            # a name of length 8 or more.  (assuming maxlen=8)
            fname = lname
            lname = ""

        # We ignore hyphens in the last name, but extract the
        # initials from the first name(s).
        lname = lname.replace('-', '').replace(' ', '')
        initials = [n[0] for n in re.split(r'[ -]', fname)]

        # firstinit is set to the initials of the first two names if
        # the person has three or more first names, so firstinit and
        # initial never overlap.
        firstinit = ""
        initial = None
        if len(initials) >= 3:
            firstinit = "".join(initials[:2])
        # initial is taken from the last first name.
        if len(initials) > 1:
            initial = initials[-1]

        # Now remove all hyphens and keep just the first name.  People
        # called "Geir-Ove Johnsen Hansen" generally prefer "geirove"
        # to just "geir".

        fname = fname.replace('-', '').split(" ")[0][0:maxlen]

        # For people with many (more than three) names, we prefer to
        # use all initials.
        # Example:  Geir-Ove Johnsen Hansen
        #           ffff fff i       llllll
        # Here, firstinit is "GO" and initial is "J".
        #
        # gohansen gojhanse gohanse gojhanse ... goh gojh
        # ssllllll ssilllll sslllll ssilllll     ssl ssil
        #
        # ("ss" means firstinit, "i" means initial, "l" means last name)

        if len(firstinit) > 1:
            llen = min(len(lname), maxlen - len(firstinit))
            for j in range(llen, 0, -1):
                un = prefix + firstinit + lname[0:j] + suffix
                if validate_func is None or validate_func(un):
                    potuname += (un, )

                if initial and len(firstinit) + 1 + j <= maxlen:
                    un = prefix + firstinit + initial + lname[0:j] + suffix
                    if validate_func is None or validate_func(un):
                        potuname += (un, )

                if len(potuname) >= goal:
                    break

        # Now try different substrings from first and last name.
        #
        # geiroveh,
        # fffffffl
        # geirovjh geirovh geirovha,
        # ffffffil ffffffl ffffffll
        # geirojh geiroh geirojha geiroha geirohan,
        # fffffil fffffl fffffill fffffll ffffflll
        # geirjh geirh geirjha geirha geirjhan geirhan geirhans
        # ffffil ffffl ffffill ffffll ffffilll fffflll ffffllll
        # ...
        # gjh gh gjha gha gjhan ghan ... gjhansen ghansen
        # fil fl fill fll filll flll     fillllll fllllll

        flen = min(len(fname), maxlen - 1)
        for i in range(flen, 0, -1):
            llim = min(len(lname), maxlen - i)
            for j in range(1, llim + 1):
                if initial:
                    # Is there room for an initial?
                    if j < llim:
                        un = prefix + \
                            fname[0:i] + initial + lname[0:j] + suffix
                        if validate_func is None or validate_func(un):
                            potuname += (un, )
                un = prefix + fname[0:i] + lname[0:j] + suffix
                if validate_func is None or validate_func(un):
                    potuname += (un, )
            if len(potuname) >= goal:
                break

        # Try prefixes of the first name with nothing added.  This is
        # the only rule which generates usernames for persons with no
        # _first_ name.
        #
        # geirove, geirov, geiro, geir, gei, ge

        flen = min(len(fname), maxlen)
        for i in range(flen, 1, -1):
            un = prefix + fname[0:i] + suffix
            if validate_func is None or validate_func(un):
                potuname += (un, )
            if len(potuname) >= goal:
                break

        # Absolutely last ditch effort:  geirov1, geirov2 etc.
        i = 1
        prefix = (fname + lname)[:maxlen - 2]

        while len(potuname) < goal and i < 100:
            un = prefix + str(i) + suffix
            i += 1
            if validate_func is None or validate_func(un):
                potuname += (un, )
        return potuname

    def _encode(self, u):
        """
        Returns an encoded (byte) string of the unicode `u` using
        the defined self.encoding.
        If self.encoding is empty or None or if `u` is not unicode,
        u is returned.
        """
        if not isinstance(u, six.text_type) or not self.encoding:
            return u
        return u.encode(self.encoding)

    def _encode_dict(self, u_dict):
        """
        Returns a *copy* of `u_dict` where all unicode keys and values
        are encoded using self.encoding.
        If self.encoding is empty or None, no encoding is attempted and only
        a copy of `u_dict` is returned.
        """
        assert isinstance(u_dict, dict)
        if not self.encoding:
            return copy.copy(u_dict)
        return dict(
            [(self._encode(k), self._encode(v)) for k, v in u_dict.items()])

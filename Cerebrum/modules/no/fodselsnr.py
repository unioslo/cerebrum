#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2002-2019 University of Oslo, Norway
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
Parse and validate Norwegian national id numbers.

This module can be used to validate Norwegian national id numbers.  The
national id number (fødselsnummer) consists of 11 digits, and follows a format
DDMMYYIIGCC, where:

- DDMMYY is the birth date (fødselsdato)
- IIGCC is a person identifier (personnummer), where
- IIG is the identifier number
- G indicates gender
- CC is a checksum

Most of the functions in this module will raise an InvalidFnrError if given an
invalid national id.

Ported from the perl version written by Gisle Aas <aas@sn.no> (No::PersonNr).
"""
from __future__ import print_function

import re


class InvalidFnrError(ValueError):
    """ Exception on invalid Norwegian national id value. """
    pass


def personnr_ok(nr, _ret_date=0, accept_00x00=True):
    """
    Check if Norwegian national id is valid

    :type nr: int, str
    :param nr: Norwegian national id value

    :param _ret_date:
        INTERNAL USAGE ONLY: if true, return a date tuple

    :param accept_00x00:
        Ignore checksums for national ids on the form: DDMMYY00X00

    :returns:
        Returns an 11 digit national id string.
    """
    SO_NUMBER = False

    re_strip = re.compile(r"[\s\-]", re.DOTALL)
    nr = re.sub(re_strip, "", str(nr))
    if len(nr) == 10:
        nr = "0" + nr
    if len(nr) != 11:
        raise InvalidFnrError("Invalid length (%d) for %s" %
                              (len(nr), repr(nr)))

    if nr != beregn_sjekksum(nr):
        raise InvalidFnrError("Invalid checksum for %s" % repr(nr))

    # Del opp fødselsnummeret i dets enkelte komponenter.
    day, month, year, pnr = (
        int(nr[0:2]), int(nr[2:4]), int(nr[4:6]), int(nr[6:9]))

    # luk ut personnr fra SAP (12345600X00)
    if not accept_00x00 and re.search(r'00\d00$', nr):
        raise InvalidFnrError("Invalid person identifier (00X00)")

    # B-nummer -- midlertidig (max 6 mnd) personnr
    if day > 40:
        day -= 40

    # FS/SO hack for midlertidige nummer.  Urk.
    if month > 50:
        SO_NUMBER = True
        month -= 50

    # The rest of the hack for FS/SO numbers
    if SO_NUMBER:
        if 120 <= pnr <= 199:
            year += 2000
        else:
            import time
            if year in range(int(time.strftime("%y")) + 1, 99 + 1):
                year += 1900            # If year in [now + 1, ... 99] => year
            else:                       # probably be previous century.
                year += 2000            # Will potentially be a problem in 2050

    else:
        # Så var det det å kjenne igjen hvilket hundreår som er det riktige.
        if 000 <= pnr <= 499:
            year += 1900
        elif 500 <= pnr <= 999 and year <= 39:
            year += 2000
        elif 900 <= pnr <= 999 and year >= 40:
            year += 1900
        elif 500 <= pnr <= 749:
            year += 1800

    if not _is_legal_date(year, month, day):
        raise InvalidFnrError("Invalid birth date")
    if not _ret_date:
        return nr
    return (year, month, day)


def _is_legal_date(y, m, d):
    """ Check if a date tuple is a valid date. """
    if d < 1:
        return
    if m < 1 or m > 12:
        return

    mdays = 31
    if m == 2:
        mdays = 28
        if ((y % 4 == 0) and (y % 100 != 0)) or (y % 400 == 0):
            mdays = 29
    elif (m == 4 or m == 6 or m == 9 or m == 11):
        mdays = 30
    if d > mdays:
        return
    return 1


def beregn_sjekksum(fnr):
    """
    calculate checksum for a given national id.

    :type fnr: str
    :param fnr: Norwegian national id value

    :rtype: str
    :return:
        Returns an 11 digit national id with correct checksum values
    """
    # TODO: Kanonikalisering av fnr; må være nøyaktig 11 elementer
    # lang.
    nr = list(fnr)
    idx = 9                             # Første kontrollsiffer
    for vekt in ((3, 7, 6, 1, 8, 9, 4, 5, 2, 1, 0),
                 (5, 4, 3, 2, 7, 6, 5, 4, 3, 2, 1)):
        sum = 0
        for x in range(11):
            #
            # Lag vektet sum av alle siffer, utenom det
            # kontrollsifferet vi forsøker å beregne.
            if x != idx:
                sum = sum + int(nr[x]) * int(vekt[x])
        # Kontrollsifferet har vekt 1; evt. etterfølgende
        # kontrollsiffer har vekt 0.  Riktig kontrollsiffer er det som
        # får den totale kontrollsummen (for hver vekt-serie) til å gå
        # opp i 11.
        kontroll = (11 - (sum % 11)) % 11
        #
        # For noen kombinasjoner av 'DDMMYY' og 'PPP' eksisterer det
        # ingen gyldig sjekksum.
        if kontroll < 0 or kontroll >= 10:
            raise InvalidFnrError(
                  "Gyldig sjekksum for %s eksisterer ikke." % fnr)
        # Vi har funnet riktig siffer; sett det inn og gå videre til
        # neste.
        nr[idx] = kontroll
        idx += 1
    return "".join([str(x) for x in nr])


def er_mann(nr):
    """
    Validate national id and check if gender flag indicates male.

    :type nr: int, str
    :param nr: Norwegian national id value
    """
    nr = personnr_ok(nr)
    return int(nr[8]) % 2


def er_kvinne(nr):
    """
    Validate national id and check if gender flag indicates female.

    :type nr: int, str
    :param nr: Norwegian national id value
    """
    return not er_mann(nr)


def fodt_dato(nr):
    """ Validate national id and return a birth date tuple. """
    return personnr_ok(nr, _ret_date=1)


def del_fnr(fnr):
    """
    Validate and split national id into birth date and person identifier.

    :type fnr: str
    :param fnr: Norwegian national id value

    :rtype: tuple
    :return:
        Returns a tuple with two items.
        - The birth date part, as an integer
        - The person identifier part, as an integer
    """
    fnr = personnr_ok(fnr)
    return (int(fnr[:-5]), int(fnr[-5:]))


def del_fnr_4(fnr):
    """
    Validate and split national id into birth date and person identifier.

    :type fnr: str
    :param fnr: Norwegian national id value

    :rtype: tuple
    :return:
        Returns a tuple with four items.
        - The birth date day of month, as an integer
        - The birth date month, as an integer (1-12)
        - The birth date year, as an integer (0-99)
        - The person identifier part, as an integer
    """
    fnr = personnr_ok(fnr)
    return (int(fnr[0:2]), int(fnr[2:4]), int(fnr[4:6]), int(fnr[6:]))


if __name__ == '__main__':
    import sys
    fnrs = sys.argv[1:]
    for fnr in fnrs:
        sjekksum_fnr = beregn_sjekksum(fnr)
        print("Riktig sjekksum for '%s' er '%s'" % (fnr[:9], sjekksum_fnr[9:]))
        if fnr[9:] != sjekksum_fnr[9:]:
            print("   (Riktig fnr blir da '%s')" % sjekksum_fnr)
        try:
            print("Sjekksum ok for '%s'" % personnr_ok(fnr))
            print("er_mann: %s" % er_mann(fnr))
            print("er_kvinne: %s" % er_kvinne(fnr))
            print("fodt_dato: %s" % str(fodt_dato(fnr)))
        except Exception:
            print("Sjekksum '%s' er ugyldig for '%s'" % (fnr[9:], fnr))

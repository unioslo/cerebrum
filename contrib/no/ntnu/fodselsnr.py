# -*- coding: iso-8859-1 -*-
# Copyright 2002 University of Oslo, Norway
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

"""Check Norwegian Social security numbers.

This documentation is written in Norwegian.

Denne modulen kan brukes for å sjekke norske personnummer.  De 2 siste
siffrene i personnummerene er kontrollsiffre og må stemme overens med
resten for at det skal være et gyldig nummer.  Modulen inneholder også
funksjoner for å bestemme personens kjønn og personens fødselsdato.

Ved ugyldig fødselsnummer reises en InvalidFnrError.

Ported from the perl version written by Gisle Aas <aas@sn.no>"""

import re

class InvalidFnrError(ValueError):
    "Exception som indikerer ugyldig norsk fødselsnummer."
    pass

def personnr_ok(nr, _retDate=0):
    """Returnerer 11-sifret fødselsnummer som str dersom det er gyldig.

    Første argument kan være enten en (long) int eller en str.

    Andre argument, `_retDate', skal kun brukes internt i denne
    modulen.

    """
    re_strip = re.compile(r"[\s\-]", re.DOTALL)
    nr = re.sub(re_strip, "", str(nr))
    if len(nr) == 10:
        nr = "0" + nr
    if len(nr) != 11:
        raise InvalidFnrError, \
              "Ugyldig lengde for fødselsnummer <%s>." % nr

    if nr <> beregn_sjekksum(nr):
        raise InvalidFnrError, \
              "Feil sjekksum for fødselsnummer <%s>." % nr

    # Del opp fødselsnummeret i dets enkelte komponenter.
    day, month, year, pnr = \
         int(nr[0:2]), int(nr[2:4]), int(nr[4:6]), int(nr[6:9])

    # B-nummer -- midlertidig (max 6 mnd) personnr
    if day > 40:
        day -= 40

    # FS/SO hack for midlertidige nummer.  Urk.
    if month > 50:
        month -= 50

    # Så var det det å kjenne igjen hvilket hundreår som er det riktige.
    if pnr < 500:
        year += 1900
    elif pnr >= 900:
        # Nok et FS/SO hack.  Dobbelturk, dette får ting til å gå i
        # stykker når noen født i år 2000 eller senere dukker opp i
        # våre systemer...
        #
        # Hacket er ikke lenger (siden høst 1999) i bruk for
        # _opprettelse_ av nye student-personnummer, men allerede
        # opprettede nummer vil finnes en stund enda.
        year += 1900
    elif year >= 55:
        # eldste person tildelt fødelsnummer er født i 1855.
        year += 1800
    else:
        # vi har et problem igjen etter år 2054.  Det er ikke helt
        # avklart hva løsningen da vil være.
        year += 2000
    if not _is_legal_date(year, month, day):
        raise InvalidFnrError, "ugyldig dato"
    if not _retDate:
        return nr
    return (year, month, day)

def _is_legal_date(y, m, d):
    """Returnerer 1 hvis dato er lovlig"""
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
    """Returner ``fnr`` med korrekt kontrollsifferdel."""
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
            if x <> idx:
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
            raise InvalidFnrError, \
                  "Gyldig sjekksum for %s eksisterer ikke." % fnr
        # Vi har funnet riktig siffer; sett det inn og gå videre til
        # neste.
        nr[idx] = kontroll
        idx += 1
    return "".join([str(x) for x in nr])

def er_mann(nr):
    """Vil returnere 1 hvis nr tilhører en mann."""
    nr = personnr_ok(nr)
    # croak "Feil i personnummer" unless $nr;
    return int(nr[8]) % 2

def er_kvinne(nr):
    """Vil returnere 1 hvis nr tilhører en kvinne."""
    return not er_mann(nr)

def fodt_dato(nr):
    'Returner personens fødselsdato på formen (år, måned, dag).'
    return personnr_ok(nr, _retDate=1)

def del_fnr(fnr):
    """Returner ``fnr`` delt i 2 ints: (dato, personnr).

    Sjekker at ``fnr`` er et gyldig fødselsnummer først; hvis ikke
    raises en InvalidFnrError.

    """
    fnr = personnr_ok(fnr)
    return (int(fnr[:-5]), int(fnr[-5:]))

def del_fnr_4(fnr):
    """Returner ``fnr`` delt i 4 ints: (dag, måned, 2-sifret år, personnr).

    Sjekker at ``fnr`` er et gyldig fødselsnummer først; hvis ikke
    raises en InvalidFnrError.

    """
    fnr = personnr_ok(fnr)
    return (int(fnr[0:2]), int(fnr[2:4]), int(fnr[4:6]), int(fnr[6:]))


if __name__ == '__main__':
    import sys
    fnr = sys.argv[1]
    print "personnr_ok: %s" % `personnr_ok(fnr)`
    print "er_mann: %s" % `er_mann(fnr)`
    print "er_kvinne: %s" % `er_kvinne(fnr)`
    print "fodt_dato: %s" % `fodt_dato(fnr)`

# arch-tag: 2a1021cd-1605-4415-ac20-e61278bf7c3c

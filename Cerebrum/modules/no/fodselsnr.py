#!/usr/bin/python
#
# Check Norwegian Social security numbers
#
# This documentation is written in Norwegian.
#
# Denne modulen kan brukes for å sjekke norske personnummer.  De 2 siste
# siffrene i personnummerene er kontrollsiffre og må stemme overens med
# resten for at det skal være et gyldig nummer.  Modulen inneholder også
# funksjoner for å bestemme personens kjønn og personens fødselsdato.
#
# Ved ugyldig fødselsnummer reises en BAD_FNR feil
#
# Ported from the perl version written by  Gisle Aas <aas@sn.no>

import re

BAD_FNR="IllegalValueError"

def personnr_ok(nr, _retDate=0):
    """Returnerer fødselsnummeret dersom det er lovlig.  _retDate skal
    ikke brukes utenfor modulen"""
    re_strip = re.compile(r"[\s\-]", re.DOTALL)
    nr =  re.sub(re_strip, "", nr)
    if len(nr) != 11:
        nr = "0" + nr
    if len(nr) != 11:
        raise BAD_FNR, "ugyldig lengde"

    for vekt in ([ 3, 7, 6, 1, 8, 9, 4, 5, 2, 1, 0 ],
                 [ 5, 4, 3, 2, 7, 6, 5, 4, 3, 2, 1 ]):
        sum = 0
        for x in range(11):
            sum = sum + int(nr[x]) * int(vekt[x])
        if sum % 11:
            raise BAD_FNR, "sjekksum feil"

    # Extract the date part
    date = [int(nr[4:6]), int(nr[2:4]), int(nr[0:2])]
    pnr = int(nr[6:9])
 
    # B-nummer -- midlertidig (max 6 mnd) personnr
    if date[2] > 40:
        date[2] = date[2] - 40 

    # FS/SO hack for midlertidige nummer.  Urk.
    if date[1] > 50:
        date[1] = date[1] - 50 

    # Så var det det å kjenne igjen hvilket hundreår som er det riktige.
    if (pnr < 500) :
        date[0] = date[0] + 1900
    elif (pnr >= 900):
        # Nok et FS/SO hack.  Dobbelturk, dette får ting til å gå i
        # stykker når noen født i år 2000 eller senere dukker opp i
        # våre systemer...
        #
        # Hacket er ikke lenger (siden høst 1999) i bruk for
        # _opprettelse_ av nye student-personnummer, men allerede
        # opprettede nummer vil finnes en stund enda.
        date[0] = date[0] + 1900
    elif (date[0] >= 55):
        # eldste person tildelt fødelsnummer er født i 1855.
        date[0] = date[0] + 1800
    else:
        # vi har et problem igjen etter år 2054.  Det er ikke helt
        # avklart hva løsningen da vil være.
        date[0] = date[0] + 2000
    if(not _is_legal_date(date)):
        raise BAD_FNR, "ugyldig dato"
    if(not _retDate):
        return nr
    return (date)

def _is_legal_date(date):
    """Returnerer 1 hvis dato er lovlig"""
    (y, m, d) = date
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

def er_mann(nr):
    """Vil returnere 1 hvis nr tilhører en mann."""
    nr = personnr_ok(nr)
    # croak "Feil i personnummer" unless $nr;
    return int(nr[8]) % 2

def er_kvinne(nr):
    """Vil returnere 1 hvis nr tilhører en kvinne."""
    return not er_mann(nr)

def fodt_dato(nr):
    '''Vil returnere personens fødselsdato på formen ().  Rutinen
    returnerer C<""> hvis nummeret er ugyldig.'''
    return personnr_ok(nr, _retDate=1)

if __name__ == '__main__':
    import sys
    print "personnr_ok: %s" % personnr_ok(sys.argv[1])
    print "er_mann: %s" % er_mann(sys.argv[1])
    print "er_kvinne: %s" % er_kvinne(sys.argv[1])
    print "fodt_dato: %s" % fodt_dato(sys.argv[1])

#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2006 University of Oslo, Norway
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

# $Id$


__doc__ = """
This file contains language-specific strings for use by the web-based
password change service.

"""

__version__ = "$Revision$"
# $Source$


supported_languages = (('Bokmål',   'no-bok', 'nb'),
                       ('Nynorsk', 'no-nyn', 'nn'),
                       ('English', 'en'))


def get_text_by_language(lang=None):
        """Factory-method for retrieving the language-class as
        determined by either the user's choice, the browser's default
        or the site's default, as express through the
        'lang'-parameter.

        """
        if lang is None:
            raise RuntimeError("Language lookup error")

        if lang == "en":
            return LanguageEn()
        elif lang == "no-bok":
            return LanguageNoBok()
        elif lang == "no-nyn":
            return LanguageNoNyn()
                                        

class DefaultLanguage(object):
    """Contains all text used by the password service, including
    HTML-template(s). All text is in English, but this can be
    overriden as per the needs for any given site.

    It should at any time be complete, i.e. that any and all strings
    used by the program can be found here.

    """

    sitename = "this site"

    # Keywords for web searches
    webpage_keywords = 'passord,password'
    
    # Field name -> description mapping
    uname = 'Username'
    passw = 'Current password'
    newpass = 'New password'
    newpass2 = 'Confirm new password'

    # 'Change my password now' button
    change = 'Change my password now'
    pw_now = ''

    # HTML page title
    title = 'Password change'

    # Parameters to default_webpage_template
    template_params = ('Editors', 'Document created', 'modified')

    start_body = '''
<h1>Password change at %(sitename)s</h1>

<p>On this web page you can change the password that, among other
things, is used for reading e-mail at %(sitename)s.</p>

<p>In order to change your password, you must perform the following
steps:</p>

<ol>
  <li>Enter your username in the 'Username' field below,
  <li>Enter your current password in the 'Password' field below,
  <li>Enter your new password in the 'New password' field below,
  <li>Confirm your new password by typing it one more time in the
      'Confirm new password' field below,
  <li>Click the 'Change' my password now button below, and wait to
      see if the server accepts your new password.
</ol>

<p>Your new password should contain a mixture of lowercase and uppercase
letters, numbers, and other characters.  It should not contain a word
found in a dictionary and must be at least 8 characters long.</p>

<P>Note that after changing your password, it might take
%(password_spread_delay)s before your new password has been spread to
all systems. You should therefore consider changing your password at
the end of the day, so that the new password will be spread by
tomorrow.

<p>You must change your password at least once every year, preferably
more frequently.  If you have not changed your password within a one
year period, you will receive an e-mail requesting that you do so. If
you still have not changed your password within 1 month, your account
will be closed.  It will still exist, and can receive e-mails, but
no one, including yourself, will be able to log into the account. An
account that has been disabled for more than one year will be assumed
to no longer be in use, and will be deleted automatically.</p>

<p>For security reasons, the username and password entered on this
web page will be encrypted when transfered to the server.</p>

%(additional)s<hr>'''

    password_spread_delay = "a while "

    additional_info_for_start_page = ""

    password_form = '''<form method="POST" action="%s"><div>
 <table>
  <tr><td>%s</td><td><input type="text" name="uname" size=12></td></tr>
  <tr><td>%s</td><td><input type="password" name="pass" size=12></td></tr>
  <tr><td>%s</td><td><input type="password" name="newpass" size=12></td></tr>
  <tr><td>%s</td><td><input type="password" name="newpass2" size=12></td></tr>
 </table>
 <input type="hidden" name="lang" value="%s">
 <input type="submit" name="action" value="%s">%s
</div></form>'''

    try_again = '''
Please go back to the previous page and try again.'''

    probably_try_again = '''
You may go back to the previous page and try again.'''

    try_again_later_fmt = """
A local error happened. Please try again later. If the problem
persists, please contact <a href="mailto:%s">%s</a>. %s"""

    status_webpage_string = ""

    empty_field_fmt = "Field '%s' is emtpy."

    badchar_field_fmt = '''
Bad character(s) %s in field '%s'
(expected ASCII characters except space), but trying anyway...'''

    new_password_mismatch = '''
The passwords you entered in the 'New password' and 'Confirm new
password' fields do not match.'''

    thank_you = '''
Thank you for changing your password.  You may have to wait
%(password_spread_delay)s before the new password has been activated .'''

    operation_failed = 'The operation failed'

    not_success = '<H1>ERROR: Password has NOT been updated</H1>'

    cmdline_bofh_URL_not_https = '''
WARNING: BOFH_URL is not a 'https:' URL.  Passwords will not be encrypted.
'''

    http_bofh_URL_not_https = "Internal server error: Bad BOFH_URL."

    wrong_certificate_mail = '''To: %s
Subject: Warning: Wrong bofh-certificate to %s

The bofh-certificate test failed for URL:
    %s

Bofh server:
    %s
CA certificate file:
    %s

Note that this file is timestamped to avoid too frequent warnings:
    %s
Remove it if you wish to receive any new warnings immediately.

Program:   %s
User name: %s
Environment:

%s'''

    default_webpage_template = '''<html>
<head>
<title>##TITLE##</title>
<meta name="keywords" content="##KEYWORDS##">
</head>
<body>
##BODY##
<hr>
<address>
%s: ##EDITOR.NAME##,
<a href="mailto:##EDITOR@EMAIL##">##EDITOR@EMAIL##</a><br>
%s: 88.88.8888, %s: 99.99.9999
</address>
</body>
</html>'''
    
    bad_template_mail = '''To: %s
Subject: Error in %s

The web page was shown without UHTML, because
    %s
failed.  Error:
    %03d %s
'''


class LanguageEn(DefaultLanguage):
    """To explicitly have an English language definition."""
    pass


class LanguageNoBok(DefaultLanguage):
    """Language strings for Norwegian Bokmål."""
    sitename = 'dette stedet'

    uname = 'Brukernavn'
    passw = 'Nåværende passord'
    newpass = 'Nytt passord'
    newpass2 = 'Gjenta nytt passord'

    change = 'Bytt passordet mitt nå'
    
    title = 'Skifte av passord'

    template_params = ('Redaksjon', 'Dokument opprettet', 'endret')

    start_body = '''
<h1>Skifte av passord ved %(sitename)s</h1>

<p>På denne websiden kan du endre passordet du blant annet bruker for
å få lest e-posten din ved %(sitename)s.</p>

<p>For å endre passord må du gjøre følgende:</p>

<ol>
  <li>Tast inn brukernavnet ditt i feltet 'Brukernavn' nedenfor,
  <li>Tast inn det nåværende passordet ditt i feltet 'Passord'
      nedenfor,
  <li>Tast inn det nye passordet ditt (det du ønsker å bytte til) i
      feltet 'Nytt passord' nedenfor,
  <li>Bekreft det nye passordet ved å taste det en gang til i feltet
      'Gjenta nytt passord' nedenfor,
  <li>Trykk på 'Bytt'-knappen nedenfor, og vent på bekreftelse fra
      serveren om at det nye passordet er godkjent.
</ol>

<p>Nye passord må bestå av en blanding av store og små bokstaver, tall
og andre tegn.  Det bør ikke inneholde ord som finnes i en ordliste,
og må være på minst 8 tegn.</p>

<p>Etter passordskifte vil det kunne ta %(password_spread_delay)s før det nye
passordet er spredt til alle deler av IT-systemet. Det anbefales
derfor å skifte passord på slutten av arbeidsdagen.</p>

<p>Du må bytte passord minst en gang i året, helst oftere.  Dersom du
ikke har byttet passord på over et år, vil du bli varslet om dette i
e-post.  Dersom du en måned etter et slikt varsel fortsatt ikke har
byttet passord, vil kontoen din bli stengt.  Den vil fortsatt kunne
motta e-post, og filene vil bli liggende, men ingen vil kunne bruke
kontoen.  En konto som har vært stengt i mer enn ett år antas å ikke
lenger være i bruk, og vil automatisk bli slettet.</p>

<p>Av sikkerhetshensyn vil all informasjon du registrerer på disse
sidene bli kryptert under overføringen.  </P>

%(additional)s<hr>'''

    password_spread_delay = "en stund"

    additional_info_for_start_page = ""

    try_again = '''
Vennligst gå tilbake til forrige side og prøv igjen.'''

    probably_try_again = '''
Det kan bety at du bør gå tilbake til forrige side og prøve igjen.'''

    try_again_later_fmt = """
En lokal feil skjedde.  Vennligst prøv igjen senere.  Hvis problemet
vedvarer, kontakt <a href="mailto:%s">%s</a>. %s"""

    status_webpage_string = ""

    empty_field_fmt = "Feltet '%s' er tomt."

    badchar_field_fmt = '''
Ugyldig(e) tegn %s in felt '%s'
(forventet ASCII-tegn unntatt mellomrom), men prøver likevel...'''

    new_password_mismatch = '''
Passordene du oppgav i 'Nytt passord'- og 'Gjenta nytt passord'-feltene
stemmer ikke overens.'''

    thank_you = '''
Takk for for at du byttet passordet ditt.  Det vil kunne ta
%(password_spread_delay)s innen det nye passordet ditt er aktivt.'''

    operation_failed = 'Operasjonen feilet'

    not_success = '<H1>Passordet har IKKE blitt byttet</H1>'


class LanguageNoNyn(DefaultLanguage):
    """Language strings for Norwegian Nynorsk."""
    sitename = 'denne staden'

    uname = 'Brukarnamn'
    passw = 'Noverande passord'
    newpass = 'Nytt passord'
    newpass2 = 'Gjenta nytt passord'
    
    change = 'Bytt passordet mitt no'

    title = 'Skifte av passord'

    template_params = ('Redaksjon', 'Dokument oppretta', 'endra')

    start_body = """
<h1>Skifte av passord ved %(sitename)s</h1>

<p>På denne vevsida kan du endre passordet du mellom anna brukar for
å lese e-posten din ved %(sitename)s.</p>

<p>Du må gjere følgjande:</p>

<ol>
  <li>Tast inn brukarnamnet ditt i feltet 'Brukarnamn' nedanfor
  <li>Tast inn det noverende passordet ditt i feltet 'Passord'
  <li>Tast inn det nye passordet ditt (det du ønskjer å bytte til) i
      feltet 'Nytt passord'
  <li>Stadfest det nye passordet ved å taste det éin gong til i feltet
      'Gjenta nytt passord'
  <li>Trykk på 'Bytt'-knappen, og vent på stadfesting frå
      tenaren om at det nye passordet er godkjent.
</ol>

<p>Nye passord må innehalde ei blanding av store og små bokstavar, tal
og andre teikn.  Det bør ikkje innehalde ord som finnest i ei
ordliste, og må vere på minst 8 teikn.</p>

<p>Etter passordskifte vil det kunne ta %(password_spread_delay)s før det nye
passordet er spreidd til alle delar av IT-systemet.  Vi rår deg difor
til å skifte passord på slutten av arbeidsdagen.</p>

<p>Du må bytte passord minst éin gong i året, helst oftare.  Dersom du
ikkje har bytta passord på over eit år, vil du få ei e-postmelding om
at det er på tide å skifte.  Viss du ikkje gjer dette i løpet av ein
månad, vil kontoen din verte stengt.  E-post vil framleis kome fram,
og filene på heimeområdet vert liggjande, men du får ikkje logge inn
og bruke kontoen.  Ein konto som har vore stengt i meir enn eit år er
sjeldan sakna, og vert automatisk sletta.</p>

<p>For å tryggje informasjonen du registrerer på desse sidene vert han
kryptert under overføringa. </p>

%(additional)s<hr>"""

    password_spread_delay = "ein stund"

    additional_info_for_start_page = ""

    try_again = """
Ver venleg og gå attende til forrige side og prøv igjen."""

    probably_try_again = """
Du kan prøve å gå attende til forrige side og prøve igjen."""

    try_again_later_fmt = """
Ein lokal feil skjedde, ver venleg å prøve igjen seinare.  Om
problemet varer lenge, ta kontakt med <a href="mailto:%s">%s</a>. %s"""

    status_webpage_string = ""

    empty_field_fmt = "Feltet '%s' er tomt."

    badchar_field_fmt = """
Ugyldig(e) teikn %s i felt '%s'
(forventa ASCII-tegn unntatt mellomrom), men prøver likevel..."""

    new_password_mismatch = """
Passorda du oppgav i 'Nytt passord'- og 'Gjenta nytt passord'-felta
stemmer ikkje overeins."""

    thank_you = """
Takk for for at du bytta passordet ditt.  Det vil kunne ta
%(password_spread_delay)s innan det nye passordet ditt er aktivt ."""

    operation_failed = 'Operasjonen feila'

    not_success = '<H1>Passordet er IKKJE endra</H1>'

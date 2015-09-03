#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011-2015 University of Oslo, Norway
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

"""Functionality for the Individuation project that is specific to UiO."""

from Cerebrum.modules.cis import Individuation


class Individuation(Individuation.Individuation):
    # The feedback messages
    messages = {
        'error_unknown':
            {'en': u'An unknown error occured',
             'no': u'En ukjent feil oppstod'},
        'person_notfound':
            {'en': u'Some of the data is wrong, please try again.',
             'no': u'Noe av den oppgitte informasjonen er feil, vennligst'
                   u' prøv igjen.'},
        'person_notfound_usernames':
            {'en': u'You are either reserved or have the given wrong information.',
             'no': u'Du er reservert eller har oppgitt feil informasjon.'},
        'person_miss_info':
            {'en': u'Not all your information is available. Please contact your'
                   u' local student office.',
             'no': u'Ikke all din informasjon er tilgjengelig. Vennligst ta'
                   u' kontakt med ditt lokale studentkontor.'},
        'account_blocked':
            {'en': u'This account is inactive. Please contact your local IT.',
             'no': u'Denne brukerkontoen er ikke aktiv. Vennligst ta kontakt'
                   u' med din lokale IT-avdeling.'},
        'account_reserved':
            {'en': u'You are blocked from using this service. Please contact'
                   u' your local IT department.',
             'no': u'Du er blokkert fra å bruke denne tjenesten. Vennligst ta'
                   u' kontakt med din lokale IT-avdeling.'},
        'account_self_reserved':
            {'en': u'You have reserved yourself from using this service. Please'
                   u' contact your local IT department.',
             'no': u'Du har reservert deg fra å bruke denne tjenesten.'
                   u' Vennligst ta kontakt med din lokale IT-avdeling.'},
        'token_notsent':
            {'en': u'Could not send one-time password to your phone',
             'no': u'Kunne ikke sende engangspassord til din telefon'},
        'toomanyattempts':
            {'en': u'Too many attempts. You have temporarily been blocked from'
                   u' this service',
             'no': u'For mange forsøk. Du er midlertidig utestengt fra denne'
                   u' tjenesten'},
        'toomanyattempts_check':
            {'en': u'Too many attempts, one-time password got invalid',
             'no': u'For mange forsøk, engangspassordet er blitt gjort'
                   u' ugyldig'},
        'timeout_check':
            {'en': u'Timeout, one-time password got invalid',
             'no': u'Tidsavbrudd, engangspassord ble gjort ugyldig'},
        'fresh_phonenumber':
            {'en': u'Your phone number has recently been changed,'
                   u' and cannot be used for a few days due to security reasons.'
                   u' Please contact your local IT department.',
             'no': u'Ditt mobilnummer er nylig byttet, og kan av'
                   u' sikkerhetsmessige årsaker ikke benyttes før etter noen'
                   u' dager. Vennligst ta kontakt med din lokale IT-avdeling.'},
        'password_invalid':
            {'en': u'Bad password: %s',
             'no': u'Ugyldig passord: %s'},
    }

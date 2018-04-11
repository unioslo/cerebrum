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

from __future__ import unicode_literals

"""Functionality for the Individuation project that is specific to UiO."""

from Cerebrum.modules.cis import Individuation


class Individuation(Individuation.Individuation):
    # The feedback messages
    messages = {
        'error_unknown': {
            'en': 'An unknown error occured',
            'no': 'En ukjent feil oppstod'},
        'person_notfound': {
            'en': 'Some of the data is wrong, please try again.',
            'no': ('Noe av den oppgitte informasjonen er feil, vennligst'
                   ' prøv igjen.')},
        'person_notfound_usernames': {
            'en': ('You are either reserved or have the given wrong '
                   'information.'),
            'no': 'Du er reservert eller har oppgitt feil informasjon.'},
        'person_miss_info': {
            'en': ('Not all your information is available. Please contact your'
                   ' local student office.'),
            'no': ('Ikke all din informasjon er tilgjengelig. Vennligst ta'
                   ' kontakt med ditt lokale studentkontor.')},
        'account_blocked': {
            'en': 'This account is inactive. Please contact your local IT.',
            'no': ('Denne brukerkontoen er ikke aktiv. Vennligst ta kontakt'
                   ' med din lokale IT-avdeling.')},
        'account_reserved': {
            'en': ('You are blocked from using this service. Please contact'
                   ' your local IT department.'),
            'no': ('Du er blokkert fra å bruke denne tjenesten. Vennligst ta'
                   ' kontakt med din lokale IT-avdeling.')},
        'account_self_reserved': {
            'en': ('You have reserved yourself from using this service. Please'
                   ' contact your local IT department.'),
            'no': ('Du har reservert deg fra å bruke denne tjenesten.'
                   ' Vennligst ta kontakt med din lokale IT-avdeling.')},
        'token_notsent': {
            'en': 'Could not send one-time password to your phone',
            'no': 'Kunne ikke sende engangspassord til din telefon'},
        'toomanyattempts': {
            'en': ('Too many attempts. You have temporarily been blocked from'
                   ' this service'),
            'no': ('For mange forsøk. Du er midlertidig utestengt fra denne'
                   ' tjenesten')},
        'toomanyattempts_check': {
            'en': 'Too many attempts, one-time password got invalid',
            'no': 'For mange forsøk, engangspassordet er blitt gjort ugyldig'},
        'timeout_check': {
            'en': 'Timeout, one-time password got invalid',
            'no': 'Tidsavbrudd, engangspassord ble gjort ugyldig'},
        'fresh_phonenumber': {
            'en': ('Your phone number has recently been changed, and cannot '
                   'be used for a few days due to security reasons. '
                   'Please contact your local IT department.'),
            'no': ('Ditt mobilnummer er nylig byttet, og kan av '
                   'sikkerhetsmessige årsaker ikke benyttes før etter noen '
                   'dager. Vennligst ta kontakt med din lokale IT-avdeling.')},
        'password_invalid': {
            'en': 'Bad password: %s',
            'no': 'Ugyldig passord: %s'},
    }

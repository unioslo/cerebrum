#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2011 University of Oslo, Norway
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

# Messages used by the Individuation Server
messages = {
    'status_inactive':   {'en': 'Inactive',
                          'no': 'Inaktiv'},
    'status_active':     {'en': 'Active',
                          'no': 'Aktiv'},
    'status_passw_quar': {'en': 'Passwordquarantined',
                          'no': 'Passordkarantene'},
    'person_notfound':   {'en': 'Could not find person',
                          'no': 'Kunne ikke finne personen'},
    'person_nophone':    {'en': 'Person has no registered mobile numbers',
                          'no': 'Personen har ingen registrerte mobilnummer'},
    'account_blocked':   {'en': 'Account is blocked',
                          'no': 'Brukerkontoen er blokkert'},
    'account_reserved':  {'en': 'Account is reserved from this service',
                          'no': 'Brukerkontoen er reservert fra denne tjenesten'},
    'token_notsent':     {'en': 'Could not send one time password to phone',
                          'no': 'Kunne ikke sende engangspassord til telefonen'},
    'toomanyattempts_check': {'en': 'Too many attempts, one time password got invalid',
                          'no': 'For mange forsøk, engangspassordet er blitt gjort ugyldig'},
    'timeout_check':     {'en': 'Timeout, one time password got invalid',
                          'no': 'Tidsavbrudd, engangspassord ble gjort ugyldig'},
}


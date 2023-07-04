# -*- coding: utf-8 -*-
#
# Copyright 2011-2023 University of Oslo, Norway
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
CIS - Cerebrum Integration Services

This is a framework for implementing SOAP-services in Cerebrum with *twisted*
and *rpclib*/*spyne*.

Current uses
-------------

PostmasterCommands (or postmaster-ws)
    An API that lets the postmaster at UiO to fetch large groups of email
    addresses.

Previous uses
--------------

Alumni
    API for managing alumni accounts from a proof-of-concept alumni app.
    This service was never in production.

GroupService
    API for creating and moderating groups from the Digeks (digital exams)
    LISP scheduler.

Individuation
    A password reset API for use with the Individuation PHP frontend.

VirthomeService
    An API for creating and configuring groups and accounts from the first
    version of Personreg.  This version used WebID for authentication, and
    needed accounts and groups to be automatically set up.
"""

#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2017 University of Oslo, Norway
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
This package is intended for running (full)syncs/diffs with external systems,
for which Cerebrum is considered an authoritative system.

In order for this module to uphold its usefulness, some guidelines when
implementing a new sync/diff should be followed:

Data from both systems should be put into dicts, with matching
keys/values to be compared.

There are numerous functions for fetching cerebrum-data available in
the base_data_fetchers.py-module. If you are working on a new sync/diff,
and think you have written functionality that may be re-useable in other
syncs/diffs, this functionality should be placed here.

Communication clients to fetch/send data to external systems should be
placed in the clients module-folder, if Cerebrum already does not have
existing clients that can be reused, and it is deemed unlikely that the
client will be reused elsewhere.

###########################
Architecture of a sync/diff
###########################

A sync/diff package should consist of these main modules/components:

__main__; script for actually running the sync/diff, and generating i.e.
changes/events based on the results.

data_fetchers: functions for fetching data from both cerebrum and the external
system. When fetching data from Cerebrum, try to rely on the functionality
present in base_data_fetchers as much as possible, to avoid duplication of
code.

mappers: functions that receive data from Cerebrum and an external system,
and maps it into matching representations in the form of regular dicts, in
order to have a basis for comparing it.

compare: function(s) for comparing entities across Cerebrum and the external
system.

functions: "Glue-functions" that are trigged by the script in __main__, that
relay the fetched data into the corresponding data mappers and run the compare
functions on the data.

See the ad_ldap package for an example implementation of this pattern.
"""
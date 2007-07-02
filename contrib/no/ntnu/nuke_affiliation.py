#! /usr/bin/env python
#
# Copyright 2007 University of Oslo, Norway
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

#
# Helper script to nuke an affiliation from the database.
# Use only as a last resort if makedb --update-codes failes
#
# Use with care.
#

import cerebrum_path
import sys
from Cerebrum.Utils import Factory

db=Factory.get("Database")()

aff=sys.argv[1]
try:
    aff=int(aff)
except:
    aff=db.query_1("SELECT code FROM person_affiliation_code WHERE code_str=:affname", {'affname': aff})
                   
v={'aff': aff}

n=db.query_1("SELECT count(*) FROM person_affiliation_source WHERE affiliation=:aff", v)

print "Will delete %d person affiliations. Are you sure? " % n
answer=sys.stdin.readline()
if not answer.lower() in ("y\n", "yes\n"):
    sys.exit(1)

print "Deleting from account_type"
db.execute("DELETE FROM account_type WHERE affiliation=:aff", v)
print "Deleting from person_affiliation_source"
db.execute("DELETE FROM person_affiliation_source where affiliation=:aff", v)
print "Deleting from person_affiliation"
db.execute("DELETE FROM person_affiliation where affiliation=:aff", v)
print "Deleting from person_aff_status_code"
db.execute("DELETE FROM person_aff_status_code where affiliation=:aff", v)
print "Deleting from person_affiliation_code"
db.execute("DELETE FROM person_affiliation_code where code=:aff", v)
print "Commiting"
db.commit()

#! /usr/bin/env python2.2
# -*- coding: iso8859-1 -*-
#
# Copyright 2003 University of Oslo, Norway
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

This file is part of the Cerebrum framework.

It generates a plain text dump suitable for the student portal project.  The
output generated contains exam registration information.

Beware, this script provides a temporary solution only.

The output file contains one line per exam registration. Each line has 10
fields which are (in order):

Primary user name
Subject code for this exam registration
Examination year
Month number
Program level code (studieprogrammets nivåkode)
Instituion number (it will be 185 at UiO)
Faculty number
Institute number
Group number
Program code (studieprogramkkode)

Each field is separated by the character sequence quote-comma-quote.

The general workflow is pretty simple:

<cerebrum db> --+
                |  
                +--> generate_portal_export.py ===> portal.txt
                |
<FS db> --------+

<cerebrum db> is needed for username extraction.

<FS db> provides the rest (dates, courses, places, etc.)

"""

import getopt
import sys
import string

import cerebrum_path
import cereconf

from Cerebrum import Database
from Cerebrum.Utils import Factory

from Cerebrum.modules.no.uio.access_FS import FS
from Cerebrum.Utils import SimilarSizeWriter

if sys.version >= (2, 3):
    import logging
else:
    from Cerebrum.extlib import logging
# fi


# 
# It looks like there is way too much time spent looking up things. The
# output structure suggests that it might be beneficial to cache
# (no_ssn,uname) mappings
#
no_ssn_cache = {}

def cached_value(key):
    """
    Returns the cached value for key (if it exists) or None. NB! In this
    context, values cannot be None, which is thus safe to use as a sentinel.
    """
    return no_ssn_cache.get(key, None)
# end cached_value

def cache_value(key, value):
    """
    Insert a new pair into the cache.
    """

    # NB! This is potentially very dangerous, as no upper limit is placed on
    # the cache
    no_ssn_cache[key] = value
# end cache_value



def output_row(row, stream, db_person, db_account, constants):
    """
    Write out one portal entry.

    Each entry has these fields in order (names/methods on the rhs)

    uname               db_person.get_primary_account()
    emnekode            row['emnekode']
    eksamensår          row['arstall']
    eksamensmåned       row['manednr']
    nivåkode            row['studienivakode']
    institusjonsnr      row['institusjonsnr_reglement']
    fakultetsnr         row['faknr_reglement']
    instituttnr         row['instituttnr_reglement']
    gruppenr            row['gruppenr_reglement']
    studieprogram       row['studieprogramkode']         
    """

    # This is insane! Why is FS so non-chalant?
    # Force birth dates to be 6-digit by prepending zeros
    birth_date = str(int(row.fodselsdato)).zfill(6)
    no_ssn = birth_date + str(int(row.personnr))

    uname = cached_value(no_ssn)
    if uname is None:

        try:
            db_person.clear()
            db_person.find_by_external_id(constants.externalid_fodselsnr,
                                          no_ssn,
                                          constants.system_fs)
        except:
            # FIXME: report the exception/stacktrace as well?
            logger.error("Could not find NO_SSN (fnr) %s in Cerebrum",
                         no_ssn)
            cache_value(no_ssn, "missing no_ssn")
            return
        # yrt
        
        # If a person has no primary account (i.e. no accounts), we simply skip
        # him
        account_id = db_person.get_primary_account()
        if not account_id:
            logger.warn("Person %s has no accounts", no_ssn)
            cache_value(no_ssn, "missing account")
            return 
        # fi

        db_account.clear()
        db_account.find(account_id)
        uname = db_account.get_account_name()

        cache_value(no_ssn, uname)
    # This no_ssn is not in the database or there is no account :(
    elif (uname == "missing no_ssn" or
          uname == "missing account"):
        return
    # fi

    # These can potentially be empty in the query result (NULL, that is)
    year = ''
    month = ''
    subject = ''
    if row.arstall is not None: year = int(row.arstall)

    if row.manednr is not None: month = int(row.manednr)

    if row.emnekode is not None: subject = row.emnekode
    
    # int()-conversions are necessary, since dco2 hands us numeric data as
    # floating point values
    stream.write(string.join(map(str,
                                 [uname,
                                  subject,
                                  year,
                                  month,
                                  int(row.studienivakode),
                                  int(row.institusjonsnr_reglement),
                                  int(row.faknr_reglement),
                                  int(row.instituttnr_reglement),
                                  int(row.gruppenr_reglement),
                                  row.studieprogramkode]),
                             "','"))
    stream.write("\n")
# end output_row



def output_text(output_file):
    """
    Initialize data structures and start generating the output.
    """

    output_stream = SimilarSizeWriter(output_file, "w")
    output_stream.set_size_change_limit(10)
    db_cerebrum = Factory.get("Database")()
    logger.debug(cereconf.DB_AUTH_DIR)
    
    logger.debug(Database.__file__)
    db = Database.connect(user="ureg2000",
                          service="FSPROD.uio.no",
                          DB_driver='Oracle')
    db_fs = FS(db)
    
    db_person = Factory.get("Person")(db_cerebrum)
    db_account = Factory.get("Account")(db_cerebrum)
    constants = Factory.get("Constants")(db_cerebrum)
    
    names, rows = db_fs.GetPortalInfo()
    count = 0
    for row in rows:
        output_row(row, output_stream, db_person, db_account, constants)
        count += 1
        if count % 10000 == 0:
            logger.debug("Written next 10000 rows")
        # fi
    # od

    output_stream.close()
# end output_text



def usage():
    '''
    Display option summary
    '''

    options = '''
options: 
-o, --output-file: output file (default ./portal.txt)
-v, --verbose:     output some debugging information
-h, --help:        display usage
    '''

    # FIMXE: hmeland, is the log facility the right thing here?
    logger.info(options)
# end usage



def main(argv):
    """
    Start method for this script. 
    """
    global logger

    logging.fileConfig(cereconf.LOGGING_CONFIGFILE)
    logger = logging.getLogger("console")
    logger.setLevel(logging.INFO)
    logger.info( "Generating portal export")
    
    try:
        options, rest = getopt.getopt(argv,
                                      "o:vh", ["output-file=",
                                               "verbose",
                                               "help",])
    except getopt.GetoptError:
        usage()
        sys.exit(1)
    # yrt

    # Default values
    output_file = "portal.txt"
    verbose = False
    
    # Why does this look _so_ ugly?
    for option, value in options:
        if option in ("-o", "--output-file"):
            output_file = value
        elif option in ("-v", "--verbose"):
            # FIXME: make the logger log more? :)
            pass
        elif option in ("-h", "--help"):
            usage()
            sys.exit(2)
        # fi
    # od

    output_text(output_file = output_file)
# fi





if __name__ == "__main__":
    main(sys.argv[1:])
# fi

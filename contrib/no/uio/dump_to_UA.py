#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
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
This file is an UiO-specific extension of the Cerebrum framework.

It generates a dump file for the UA database.

The rules for the dump are thus:

* Every person with an employment (tilsetting) record or with a student
  affiliation is a candidate for ending up in the dump file.
* Every such person can potentially have multiple entries in the dump file.
* An entry consists of 29 fields separated by ';' (semicolumn) 

* Students[1] would have one entry per student affiliation
* Employees[2] would have one entry per active employment[3] (tilsetting)

However, since the UA system does not cope with multiple student records,
none of them end up in the dump file. I.e. only the employee-related records
are output.

[1] def: persons having affiliation STUDENT
[2] def: persons having an employment record (tilsetting)
[3] def: employment records (tilsetting) that have a start date (dato_fra)
         in the past and end date (dato_til) either in the future or
         unknown. Furthermore, such employments (tilsetting) shall not have
         active leaves of absence (permisjon) totalling 100%.
"""


import cerebrum_path
import cereconf

import getopt
import sys
import string
import time
import os
import ftplib

import Cerebrum
from Cerebrum.Utils import Factory
from Cerebrum.extlib.sets import Set





def locate_fnr(person, const):
    """
    Return PERSON's fnr
    """

    fnr = None
    # Force LT to be the first source system to be tried
    systems = [const.system_lt]
    systems.extend([getattr(const, name)
                    for name in cereconf.SYSTEM_LOOKUP_ORDER])
    for system in systems:
        try:
            fnr = person.get_external_id(system, const.externalid_fodselsnr)

            # FIXME: are this test *and* try-catch both necessary?
            if not fnr:
                continue
            # fi
            fnr = str(fnr[0].external_id)
            break
        except Cerebrum.Errors.NotFoundError:
            pass
        # yrt
    # od

    return fnr
# end locate_fnr



def locate_names(person, const):
    """
    Return PERSON's (first, last) names
    """

    first, last = "", ""
    systems = [const.system_lt]
    systems.extend([getattr(const, name)
                    for name in cereconf.SYSTEM_LOOKUP_ORDER])

    for system in systems:
        try:
            first = person.get_name(system, const.name_first)
            break
        except Cerebrum.Errors.NotFoundError:
            pass
        # yrt
    # od

    for system in systems:
        try:
            last = person.get_name(system, const.name_last)
            break
        except Cerebrum.Errors.NotFoundError:
            pass
        # yrt
    # od

    if not first:
        logger.debug("No first name for %s", person.entity_id)
    # fi

    if not last:
        logger.debug("No last name for %s", person.entity_id)
    # fi

    return first, last
# end locate_names



__ou_cache = dict()
def locate_stedkode(ou, ou_id):
    """
    Returns a suitably formatted 6-digit stedkode for OU with OU_ID.
    """

    ou_id = int(ou_id)
    if __ou_cache.has_key(ou_id):
        return __ou_cache[ou_id]
    # fi

    try:
        ou.clear()
        ou.find(ou_id)

        value = "%02d%02d%02d" % (ou.fakultet, ou.institutt, ou.avdeling) 
        __ou_cache[ou_id] = value
        return value
    except Cerebrum.Errors.NotFoundError:
        logger.warn("No such ou_id exists: %s", ou_id)
        return ""
    # yrt
# end locate_stedkode



def process_person(person, ou, const, stream):
    """
    Output information about the individual represented by PERSON.
    """
# end process_person



def prepare_entry(fnr, systemnr, korttype,
                  fornavn, etternavn,
                  arbeidssted,
                  startdato = "", sluttdato = ""):
    """
    Return a suitably formatted entry.
    """

    # 
    # Field layout (in order):
    # 
    # 1.     fnr
    # 2.     systemnr number
    # 3.     korttype
    # 4.     fornavn
    # 5.     etternavn
    # 6-11.  adgangsnivå            -- blank
    # 12.    sist betalt sem.avgift -- blank
    # 13.    betalingsdato 	    -- blank
    # 14.    startdato
    # 15.    sluttdato
    # 16-18. misc                   -- blank
    # 19.    arbeidssted
    # 20-29.                        -- blank

    result = [str(fnr) + systemnr, systemnr, korttype, fornavn, etternavn,
              "", "", "", "", "", "",
              "",
              "",
              startdato, sluttdato,
              "", "", "",
              arbeidssted]
    result.extend([""] * 10)

    # FIXME: The fields should be quoted
    return string.join(result, ";") + "\n"
# end prepare_entry



def locate_common(person, const):
    """
    Returns attributes common for all kinds of entries in the UA dump.

    The return value is a triple -- (no ssn, first name, last name). If no
    suitable value could be found, None is returned in the proper slot. If
    no ssn is None, this person should be skipped.
    """

    fnr, first_name, last_name = (None, None, None)

    fnr = locate_fnr(person, const)
    if fnr is None:
        logger.warn("Person %s lacks NO_SSN (fnr)", person.entity_id)
        return (fnr, first_name, last_name)
    # fi
        
    # Now, let's look for the names
    first_name, last_name = locate_names(person, const)

    return (fnr, first_name, last_name)
# end locate_common



def leave_covered(person, db_row):
    """
    Check whether a given employment (tilsetting) entry has active leaves of
    absence (permisjon) totalling to 100% (or more :))
    """

    total = 0

    now = time.strftime("%Y%m%d")
    for db_row in person.get_permisjon(now, db_row.tilsettings_id):
        if db_row.andel:
            total += int(db_row.andel)
        else:
            logger.debug("%s %s does not have andel",
                         person.entity_id, db_row.tilsettings_id)
        # fi
    # od

    logger.debug1("%s %s has andel == %d",
                  person.entity_id, db_row.tilsettings_id, total)
    return total >= 100
# end leave_covered



def process_employee(person, ou, const, db_row, stream):
    """
    Output an UA entry corresponding to PERSON's employment represented by
    DB_ROW.
    """

    fnr, first_name, last_name = locate_common(person, const)
    if not fnr:
        return
    # fi

    if leave_covered(person, db_row):
        logger.debug("%s has tilsetting %s which has >= 100%% coverage",
                     person.entity_id, db_row.tilsettings_id)
        return
    # fi

    stedkode = locate_stedkode(ou, db_row.ou_id)
    startdato = ""
    if db_row.dato_fra:
        startdato = db_row.dato_fra.strftime("%d.%m.%Y")
    # fi

    sluttdato = ""
    if db_row.dato_til:
        sluttdato = db_row.dato_til.strftime("%d.%m.%Y")
    # fi

    # systemnr == 2 for employees
    stream.write(prepare_entry(fnr = fnr,
                               systemnr = "2",
                               korttype = "Tilsatt UiO",
                               fornavn = first_name,
                               etternavn = last_name,
                               arbeidssted = stedkode,
                               startdato = startdato,
                               sluttdato = sluttdato))
# end process_employee



def process_student(person, ou, const, db_row, stream):
    """
    Output an UA entry corresponding to PERSON's student record represented
    by DB_ROW.
    """

    return

    # NOTREACHED

    fnr, first_name, last_name = locate_common(person, const)
    if not fnr:
        return
    # fi
    
    stedkode = locate_stedkode(ou, db_row.ou_id)

    # systemnr == 1 for students
    stream.write(prepare_entry(fnr = fnr,
                               systemnr = "1",
                               korttype = "STUDENT",
                               fornavn = first_name,
                               etternavn = last_name,
                               arbeidssted = stedkode))
# end process_student



def generate_output(stream, do_employees, do_students):
    """
    Create dump for UA
    """

    # 
    # We will do this in two steps -- first all the employees, then all the
    # the students.
    # 

    db = Factory.get("Database")()
    person = Factory.get("Person")(db)
    ou = Factory.get("OU")(db)
    const = Factory.get("Constants")(db)

    if do_employees:
        logger.debug("Processing all employee records")
        
        for db_row in person.list_tilsetting():
            person_id = db_row.person_id

            try:
                person.clear()
                person.find(person_id)
            except Cerebrum.Errors.NotFoundError:
                logger.exception("Aiee! No person with %s exists, although "
                                 "list_tilsetting() returned it", person_id)
                continue
            # yrt

            process_employee(person, ou, const, db_row, stream)
        # od
    # fi

    if do_students:
        logger.info("Processing all student affiliations")

        for db_row in person.list_affiliations(
                        source_system = const.system_fs,
                        affiliation = int(const.affiliation_student)):
            person_id = db_row.person_id
            
            try:
                person.clear()
                person.find(person_id)
            except Cerebrum.Errors.NotFoundError:
                logger.exception("Aiee! No person with %s exists, although "
                                 "list_affiliations() returned it", person_id)
                continue
            # yrt

            process_student(person, ou, const, db_row, stream)
        # od
    # fi
# end generate_output



def do_sillydiff(dirname, oldfile, newfile, outfile):
    today = time.strftime("%d.%m.%Y")
    try:
        oldfile = open(os.path.join(dirname, oldfile), "r")
        line = oldfile.readline()
        line.rstrip()
    except IOError:
        logger.warn("Warning, old file did not exist, assuming first run ever")
        os.link(os.path.join(dirname, newfile),
                os.path.join(dirname, outfile))
        return
    # yrt

    old_dict = dict()
    while line:
        key = line[0:12]
        value = old_dict.get(key, list()); value.append(line[13:])
        old_dict[key] = value
        
        line = oldfile.readline()        
        line.rstrip()
    # od
    oldfile.close()

    out = open(os.path.join(dirname, outfile), 'w')
    newin = open(os.path.join(dirname, newfile))
    
    newline = newin.readline()        
    newline.rstrip()           
    while newline:
        pnr = newline[0:12]
        dta = newline[13:]
        if pnr in old_dict:
            if dta not in old_dict[pnr]:
                #Some change, want to update with new values.
                out.write(newline)
            else:
                old_dict[pnr].remove(dta)
            # fi
            
            # If nothing else if left, delete the key from the dictionary
            if not old_dict[pnr]:
                del old_dict[pnr]
            # fi
        else:
            out.write(newline)
        # fi
        newline = newin.readline()
        newline.rstrip()
    # od

    for leftpnr in old_dict:
        for entry in old_dict[leftpnr]:
            vals = entry.split(";")
            vals[13] = today
            vals[17] = ""
            out.write("%s;%s" % (leftpnr, ";".join(vals)))
        # od
    # od

    out.close()    
    newin.close()
# end do_sillydiff



def ftpput(host, uname, password, local_dir, file, dir):
    ftp = ftplib.FTP(host, uname, password)
    ftp.cwd(dir)
    ftp.storlines("STOR %s" % file,
                  open(os.path.join(local_dir, file), "r"))
    ftp.quit()
# end ftpput



def usage():
    '''
    Display option summary
    '''

    options = '''
options: 
-o, --output-directory: output directory
-h, --help:             display this message
-d, --distribute:       attempt to deliver the dump file
-e, --employees:        include employees in the output
-s, --students:         include students in the output
    '''

    logger.info(options)
# end usage



def main():
    """
    Start method for this script. 
    """
    global logger

    logger = Factory.get_logger("cronjob")
    logger.info("Generating UA dump")
    
    try:
        options, rest = getopt.getopt(sys.argv[1:],
                                      "o:hdes",
                                      ["output-directory=",
                                       "help",
                                       "distribute",
                                       "employees",
                                       "students",])
    except getopt.GetoptError:
        logger.exception("foo")
        usage()
        sys.exit(1)
    # yrt

    output_directory = None
    distribute = False
    do_employees = False
    do_students = False
    for option, value in options:
        if option in ("-o", "--output-directory"):
            output_directory = value
        elif option in ("-h", "--help"):
            usage()
            sys.exit(2)
        elif option in ("-d", "--distribute"):
            distribute = True
        elif option in ("-e", "--employees"):
            do_employees = True
        elif option in ("-s", "--students"):
            do_students = True
        # fi
    # od

    output_file = open(os.path.join(output_directory, "uadata.new"), "w")
    generate_output(output_file, do_employees, do_students)
    output_file.close()

    diff_file = "uadata.%s" % time.strftime("%Y-%m-%d")
    do_sillydiff(output_directory, "uadata.old", "uadata.new", diff_file)
    os.rename(os.path.join(output_directory, "uadata.new"),
              os.path.join(output_directory, "uadata.old"))

    if distribute:
        ftpput("heimdall.ua.uio.no", "ltimport", "nOureg289337",
               output_directory, diff_file, "ua-lt")
    # fi
# end main





if __name__ == '__main__':
    main()
# fi

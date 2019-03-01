#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

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

# $Id$

import sys
import getopt

import cereconf
from Cerebrum.modules.no.access_FS import make_fs

progname = __file__.split("/")[-1]

__doc__ = """
Usage: %s [options]
   -f, --file FILE   Where to generate the exported output. Default: STDOUT
   -h, --help        Prints this message and quits

   This program generates the datafile needed for migrating the
   accounts of active students into Cerebrum. Each line outputted
   represents one student, formatted as follows:

   <no_ssn>:<uname>:<lastname>:<firstname>

   no_ssn    -- 11-digit Norwegian social security number (fødselsnummer)
   uname     -- Account name = student ID-number
   lastname  -- Last name of the person in question
   firstname -- First name of the person in question

   """ % progname

__version__ = "$Revision$"
# $URL$

options = {"output": sys.stdout}

def usage(message=None):
    """Gives user info on how to use the program and its options.
    
    @param message:
      Extra message to supply to user before rest of help-text is given.
    @type message:
      string
    
    """
    if message is not None:
        print >>sys.stderr, "\n%s" % message
        
    print >>sys.stderr, __doc__


def main(argv=None):
    """Main processing hub for program.
    
    @param argv:
      Substitute for sys.argv if wanted; see main help for options
      that can/should be given.
    @type argv:
      list

    @return:
      value that program should exit with
    @rtype:
      int
      
    """
    if argv is None:
        argv = sys.argv
    try:
        opts, args = getopt.getopt(argv[1:],
                                   "hf:",
                                   ["help", "file="])
    except getopt.GetoptError, error:
        usage(message=error.msg)
        return 1

    output_stream = options["output"]
        
    for opt, val in opts:
        if opt in ('-h', '--help',):
            usage()
            return 0
        if opt in ('-f', '--file',):
            options["output"] = val                        
    
    fs_db = make_fs()
    student_rows = fs_db.student.list_aktiv()

    if options["output"] != sys.stdout:
        output_stream = open(options["output"], "w")
        
    for student_row in student_rows:
        name = "%s %s" % (student_row["fornavn"], student_row["etternavn"])
        no_ssn = "%06d%05d" % (student_row["fodselsdato"], student_row["personnr"])
        uname = "%06d" % student_row["studentnr_tildelt"]
        lastname = student_row["etternavn"]
        firstname = student_row["fornavn"]
        output_stream.write("%s\n" % ":".join((no_ssn, uname, lastname, firstname)))

    if output_stream != sys.stdout:
        output_stream.close()
                        
    return 0


if __name__ == "__main__":
    sys.exit(main())
    

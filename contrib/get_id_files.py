#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2002, 2003, 2006 University of Oslo, Norway
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

import binascii
import string
import sys

import cerebrum_path
from Cerebrum.modules import NotesUtils
from Cerebrum.Utils import Factory

sock = NotesUtils.SocketCom()
logger = Factory.get_logger("cronjob")
users=[]
IDFILEDIR="/cerebrum/uio/dumps/NOTES_IDS/"

if sock.send('LISTNEWIDFILES\n'):
   line=sock.readline()
   logger.info('Getting new ID-files')
else:
   logger.error('Could not get ID-files.')
   sys.exit(1)
   
while line[3]=='-':
   (rest,uname)=string.split(line,'&')
   users.append(uname)
   line=sock.readline()

for user in users:
   if sock.send('GETIDFILE&'+user+'\n'):
      (rest,idfile)=string.split(sock.readline(),'&')
      idfile=binascii.a2b_hex(idfile)
      filename=IDFILEDIR+user+".id"
      file=open(filename, 'w')
      file.write(idfile)
      file.close
      logger.info("Wrote ID-file for %s", user)

sock.send('QUIT\n')
logger.info("All done")
sock.close()


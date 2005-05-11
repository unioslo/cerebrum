#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2002, 2003 University of Oslo, Norway
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

import notesutils

sock = notesutils.SocketCom()
users=[]
IDFILEDIR="/cerebrum/dumps/Notes-IDs/"

sock.send('LISTNEWIDFILES\n')
line=sock.readline()

while line[3]=='-':
   (rest,uname)=string.split(line,'&')
   users.append(uname)
   line=sock.readline()

for user in users:
   sock.send('GETIDFILE&'+user+'\n')
   (rest,idfile)=string.split(sock.readline(),'&')
   idfile=binascii.a2b_hex(idfile)
   filename=IDFILEDIR+user+".id"
   file=open(filename, 'w')
   file.write(idfile)
   file.close

sock.send('QUIT\n')
sock.close()# arch-tag: 9f49f3fa-c21c-11d9-950f-f7f6e76069a4

#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# Copyright 2006 University of Oslo, Norway
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

import sys

import cerebrum_path
import cereconf
import procconf

from Cerebrum.Utils import Factory
from Cerebrum.modules.process_entity.ProcUtils import ProcFactory

def main():
    logger = Factory.get_logger("cronjob")
    parser = ProcFactory.get('BatchRunner')(sys.argv[1:], logger)
    

if __name__ == '__main__':
    main()

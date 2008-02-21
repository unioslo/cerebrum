# -*- coding: iso-8859-1 -*-
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

"""

"""



import cerebrum_path
import cereconf
import time
import xml.sax

from Cerebrum import Database
from Cerebrum import Errors
from Cerebrum.Utils import Factory



class Stillingskode:
    _lookup_table = "[:table schema=cerebrum name=person_stillingskoder]"
    _lookup_code_column = "kode"
    _kode2type_mapping = {}

    def __init__(self,logger):
        self.db = Factory.get('Database')()
        self.logger = logger
        self.load_mappingtable()


    def load_mappingtable(self):
        mapping_file = cereconf.CB_PREFIX + '/var/source/stillingskode_sorted.txt'
        fh = open(mapping_file,'r')
        lines = fh.readlines()
        fh.close()
        for line in lines:
            line = line.strip() # remove whitespace
            if ((not line.startswith('#')) and len(line)>0):
                (kode,tittel,type) = line.split(',')
                kode = int(kode)
                if (not self._kode2type_mapping.has_key(kode)):
                    self._kode2type_mapping[kode] = type
               

    def sko2type(self,sko):

        sko = int(sko)
        if (self._kode2type_mapping.has_key(sko)):
            return self._kode2type_mapping[sko]
        else:
            return 'ØVRIG'
        
        

    def add_sko(self,kode,tittel,type):

        kode = int(kode)
        table = {"code_table" : self._lookup_table }

        upd_qry = """
        UPDATE %(code_table)s
        SET stillingskode=:kode, stillingstittel=:tittel, stillingstype=:type
        WHERE stillingskode=:kode
        """ % (table)

        sel_qry = """
        SELECT stillingstittel,stillingstype FROM %(code_table)s
        WHERE stillingskode=:kode
        """ % (table)

        binds =  { 'kode'  : kode,
                   'type'  : type,
                   'tittel': tittel
                   }
        try:
            res = self.db.query_1(sel_qry,{'kode': kode})
            if (res['stillingstittel'] != tittel or res['stillingstype'] != type):
                self.db.execute(upd_qry,binds)
                self.logger.info("UPDATE SKO: %s. Old=%s:%s, New=%s:%s" % (kode, res['stillingstittel'], res['stillingstype'], tittel, type))
            else:
                self.logger.info("EQUAL: No update on SKO=%s" % kode)
        except Errors.NotFoundError:
            add_qry = """
            INSERT INTO %(code_table)s
              (stillingskode , stillingstittel, stillingstype)
            VALUES
              (:kode, :tittel, :type)
            """ % (table)
 
            #insert new
            self.db.execute(add_qry,binds)
            self.logger.info("NEW SKO: %s->%s:%s" % (kode,tittel,type))


    def commit(self):
        self.db.commit()
# end StillingsKode





class SLP4:

    _fields = 'personnavn,fodt_dato,fodselsnr,kjonn,ansvarssted,fakultet,institutt,stillingskode,stillingsbetegnelse,begynt'

    def __init__(self,slp4_file):
        self.person_info = []
        self.stillingskoder = {}
        
        self.load_slp4_file(slp4_file)


    def load_slp4_file(self,slp4_file):
        # now lets parse the person_info file and collect all relevant information        
	person_handle = open(slp4_file,"r")
        lines = person_handle.readlines()
        person_handle.close()
        
        lineno = 0
        for person in lines:
            lineno += 1
            if (not person.startswith('#')):
                person.rstrip()
                p_info = {}
                items = person.split(",")
                for item in self._fields.split(','):
                    p_info[item] = items.pop(0).strip('"')
                self.person_info.append(p_info)
            
                # build stillingskode liste
                if (p_info['stillingskode'].isdigit()):
                    if (not self.stillingskoder.has_key(p_info['stillingskode'])):
                        self.stillingskoder[p_info['stillingskode']] = p_info['stillingsbetegnelse']
                    
                                  
    def get_stillingskoder(self,kode=None):
        if (kode):
            return self.stillingskoder[kode]
        else:
            return self.stillingskoder

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
UiT implementation of OU
"""
from Cerebrum import Utils
from Cerebrum.Utils import prepare_string
from Cerebrum import Errors
from Cerebrum.Utils import Factory
import cereconf
from Cerebrum.OU import OU
from Cerebrum.modules.no.uit.EntityExpire import EntityExpire
from Cerebrum.modules.no.uit.EntityExpire import EntityExpiredError
logger = Factory.get_logger(cereconf.DEFAULT_LOGGER_TARGET)

class OUMixin(OU):
    """ 
    UiT override of OU. expired_before is added as an extra 
    parameter to the overriden methods in this file. The default
    behaviour is to exclude all entitites that are expired at the
    time of the query."""
    
    #def populate_withouth_sko(self):
    #    logger.warn("ui.uo calling real ou.populate")
    #    super(OUEntityExpireMixin,self).populate()




    def list_all_with_perspective(self, perspective):
        extra = "WHERE eln.entity_id = os.ou_id"
        return self.query("""
        SELECT os.ou_id, eln.name FROM [:table schema=cerebrum name=ou_structure] os, [:table schema=cerebrum name=entity_language_name] eln \
        WHERE os.perspective=:perspective and os.ou_id = eln.entity_id""",
                          {'perspective': int(perspective)})
          


    #
    # Overrides of Stedkode.py functions. Move to Stedkode.py if EntityExpire is ever moved to core.
    #
    
    # def get_stedkoder(self, landkode=0,
    #                   institusjon=cereconf.DEFAULT_INSTITUSJONSNR,
    #                   fakultet=None, institutt=None, avdeling=None, expired_before=None):
    #     """
    #     Overridden method. See L{Stedkode} for functionality.
        
    #     @param expired_before: See L{EntityExpire.is_expired}.
    
    #     """        
    #     sql = """
    #     SELECT sk.ou_id, sk.landkode, sk.institusjon, sk.fakultet, sk.institutt, sk.avdeling
    #     FROM [:table schema=cerebrum name=stedkode] sk
    #     LEFT JOIN [:table schema=cerebrum name=entity_expire] ee
    #       ON sk.ou_id = ee.entity_id
    #     WHERE
    #       sk.landkode = :landkode AND
    #       sk.institusjon = :institusjon """
    #     if fakultet is not None:
    #         sql += "AND sk.fakultet = :fakultet "
    #     if institutt is not None:
    #         sql += "AND sk.institutt = :institutt "
    #     if avdeling is not None:
    #         sql += "AND sk.avdeling = :avdeling "
    #     if expired_before is None:
    #         sql += "AND (ee.expire_date >= [:now] OR \
    #                      ee.expire_date IS NULL)"
    #     elif expired_before is not None:
    #         sql += "AND (ee.expire_date >= :expired_before OR \
    #                      ee.expire_date IS NULL)"
            
    #     return self.query(sql, locals())

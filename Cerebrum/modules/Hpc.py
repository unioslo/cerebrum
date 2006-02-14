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


import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum import Constants

class _CpuArchCode(Constants._CerebrumCode):
    "CPU types for machine"
    _lookup_table = '[:table schema=cerebrum name=cpu_arch_code]'
    pass

class _OperatingSystemCode(Constants._CerebrumCode):
    "Operating system for machine"
    _lookup_table = '[:table schema=cerebrum name=operating_system_code]'
    pass

class _InterConnectCode(Constants._CerebrumCode):
    "Interconnect for HPC machine"
    _lookup_table = '[:table schema=cerebrum name=interconnect_code]'
    pass

class _AllocationAuthorityCode(Constants._CerebrumCode):
    "Entity responsible for allocating credits to projects"
    _lookup_table = '[:table schema=cerebrum name=allocation_authority_code]'
    pass

class _ScienceCode(Constants._CerebrumCode):
    "Science for categorising projects"
    _lookup_table = '[:table schema=cerebrum name=science_code]'
    pass

class Constants(Constants.Constants):

    CpuArch = _CpuArchCode
    OperatingSystem = _OperatingSystemCode
    InterConnect = _InterConnectCode
    AllocationAuthority = _AllocationAuthorityCode
    Science = _ScienceCode


Host_class = Factory.get("Host")
class Machine(Host_class):
    """Hpc specialisation of core class 'Host'."""

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('total_memory', 'node_number', 'node_memory',
        'node_disk', 'cpu_core_number', 'cpu_core_mflops', 'cpu_mhz',
        'credit_production',
        'cpu_arch', 'operating_system', 'interconnect')


    def clear(self):
        super(Machine, self).clear()
        self.clear_class(Machine)
        self.__updated = []

    def delete_machine(self):
        """Demotes Machine to a normal host"""
        if self.entity_id is None:
            raise Errors.NoEntityAssociationError, \
                  "Unable to determine which entity to delete."
        self._db.log_change(self.entity_id, self.const.machine_demote,
                            None)
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=machine_info]
        WHERE host_id=:e_id""", {'e_id': self.entity_id})

    
    def write_db(self):
        """Write Machine instance to database."""
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db

        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=machine_info]
            (host_id, cpu_arch, operating_system, interconnect)
            VALUES (:host_id, :cpu_arch, :operating_system, :interconnect)""",
                         {'host_id': self.entity_id,
                          'cpu_arch': int(self.cpu_arch),
                          'operating_system': int(self.operating_system),
                          'interconnect': int(self.interconnect)})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=machine_info]
            SET cpu_arch=:cpu_arch, operating_system=:operating_system,
                interconnect=:interconnect
            WHERE host_id=:host_id
            VALUES (:host_id, :cpu_arch, :operating_system, :interconnect)""",
                         {'host_id': self.entity_id,
                          'cpu_arch': int(self.cpu_arch),
                          'operating_system': int(self.operating_system),
                          'interconnect': int(self.interconnect)})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, host_id):
        """Connect object to Machine with ``host_id`` in database."""
        self.__super.find(host_id)
        (self.cpu_arch, self.operating_system,
         self.interconnect) = self.query_1("""
         SELECT cpu_arch, operating_system, interconnect
         FROM [:table schema=cerebrum name=machine_info]
         WHERE host_id=:host_id""", locals())
        self.__in_db = True
        self.__updated = []

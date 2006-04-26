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
from Cerebrum import Utils

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
    "Authority responsible for allocating credits to projects"
    _lookup_table = '[:table schema=cerebrum name=allocation_authority_code]'
    pass

class _AllocationStatusCode(Constants._CerebrumCode):
    "Status for an allocation"
    _lookup_table = '[:table schema=cerebrum name=allocation_status_code]'
    pass

class _ScienceCode(Constants._CerebrumCode):
    "Science for categorising projects"
    _lookup_table = '[:table schema=cerebrum name=science_code]'
    pass

class _AllocationCreditPriorityCode(Constants._CerebrumCode):
    "Priority associated with allocated credits."
    _lookup_table ='[:table schema=cerebrum name=allocation_credit_priority]'
    pass
    

class HpcConstants(Constants.Constants):
    CpuArch = _CpuArchCode
    OperatingSystem = _OperatingSystemCode
    InterConnect = _InterConnectCode
    AllocationAuthority = _AllocationAuthorityCode
    AllocationStatusCode = _AllocationStatusCode
    AllocationCreditPriority = _AllocationCreditPriorityCode
    Science = _ScienceCode

    entity_project = Constants._EntityTypeCode(
        'project',
        'see table project_info and friends')

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

    def populate(self, cpu_arch, operating_system, interconnect,
                 total_memory=None, node_number=None, node_memory=None,
                 node_disk=None, cpu_core_number=None, cpu_core_mflops=None,
                 cpu_mhz=None, name=None, description=None, parent=None):
        if parent is not None:
            self.__xerox__(parent)
        else:
            Host_class.populate(self, name, description)
        
        self.__in_db = False
        self.cpu_arch = cpu_arch
        self.operating_system = operating_system
        self.interconnect = interconnect
        self.total_memory = total_memory
        self.node_number = node_number
        self.node_memory = node_memory
        self.node_disk = node_disk
        self.cpu_core_number = cpu_core_number
        self.cpu_core_mflops = cpu_core_mflops
        self.cpu_mhz = cpu_mhz

    def write_db(self):
        """Write Machine instance to database."""
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db

        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=machine_info]
                (host_id, cpu_arch, operating_system, interconnect,
                total_memory, node_number, node_memory, node_disk,
                cpu_core_number, cpu_core_mflops, cpu_mhz)
            VALUES (:host_id, :cpu_arch, :operating_system, :interconnect,
                :total_memory, :node_number, :node_memory, :node_disk,
                :cpu_core_number, :cpu_core_mflops, :cpu_mhz)""",
                         {'host_id': self.entity_id,
                          'cpu_arch': int(self.cpu_arch),
                          'operating_system': int(self.operating_system),
                          'interconnect': int(self.interconnect),
                          'total_memory' : self.total_memory,
                          'node_number' : self.node_number,
                          'node_memory': self.node_memory,
                          'node_disk' : self.node_disk,
                          'cpu_core_number' : self.cpu_core_number,
                          'cpu_core_mflops' : self.cpu_core_mflops,
                          'cpu_mhz' : self.cpu_mhz})
                          
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=machine_info]
            SET cpu_arch=:cpu_arch, operating_system=:operating_system,
                interconnect=:interconnect, total_memory=:total_memory,
                node_number=:node_number, node_memory=:node_memory,
                node_disk=:node_disk, cpu_core_number=:cpu_core_number,
                cpu_core_mflops=:cpu_core_mflops, cpu_mhz=:cpu_mhz
            WHERE host_id=:host_id
            VALUES (:host_id, :cpu_arch, :operating_system, :interconnect,
                :total_memory, :node_number, :node_memory, :node_disk,
                :cpu_core_number, :cpu_core_mflops, :cpu_mhz)""",
                         {'host_id': self.entity_id,
                          'cpu_arch': int(self.cpu_arch),
                          'operating_system': int(self.operating_system),
                          'interconnect': int(self.interconnect),
                          'total_memory' : self.total_memory,
                          'node_number' : self.node_number,
                          'node_memory': self.node_memory,
                          'node_disk' : self.node_disk,
                          'cpu_core_number' : self.cpu_core_number,
                          'cpu_core_mflops' : self.cpu_core_mflops,
                          'cpu_mhz' : self.cpu_mhz})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, host_id):
        """Connect object to Machine with ``host_id`` in database."""
        self.__super.find(host_id)
        (self.cpu_arch, self.operating_system, self.interconnect,
         total_memory, node_number, node_memory, node_disk, cpu_core_number,
         cpu_core_mflops, cpu_mhz) = self.query_1("""
         SELECT cpu_arch, operating_system, interconnect,
             total_memory, node_number, node_memory, node_disk,
             cpu_core_number, cpu_core_mflops, cpu_mhz
         FROM [:table schema=cerebrum name=machine_info]
         WHERE host_id=:host_id""", {'host_id': host_id})
        self.__in_db = True
        self.__updated = []



Entity_class = Utils.Factory.get("Entity")
class Project(Entity_class):
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('owner_id', 'science')

    def clear(self):
        super(Project, self).clear()
        self.clear_class(Project)
        self.__updated = []

    def populate(self, owner_id, science, parent=None):
        """Populate a new project"""
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity_class.populate(self, self.const.entity_project)
        
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        
        self.owner_id = owner_id
        self.science = science

    def write_db(self):
        """Write project instance to database"""
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db

        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=project_info]
            (project_id, owner, science) 
            VALUES (:project_id, :owner, :science)""",
                         {'project_id' : self.entity_id,
                          'owner' : self.owner_id,
                          'science' : int(self.science)})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=project_info]
            SET owner=:owner, science=:science
            WHERE project_id=:project_id
            VALUES (:project_id, :owner, :science)""",
                         {'project_id' : self.entity_id,
                          'owner' : self.owner_id,
                          'science' : int(self.science)})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new


    def find(self, project_id):
        """Connect object to Project with ``project_id`` in database."""
        self.__super.find(project_id)
        (self.owner_id, self.science) = self.query_1("""
         SELECT owner, science
         FROM [:table schema=cerebrum name=project_info]
         WHERE project_id=:project_id""", {'project_id': project_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []


    def delete(self):
        # don't delete projects with allocations!
        if self.__in_db:
            # Remove any members first
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=project_member]
            WHERE project_id=:project_id""", {'project_id': self.entity_id})
            # Remove entry in table `project_info'.
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=group_info]
            WHERE project_id=:project_id""", {'project_id': self.entity_id})
            #self._db.log_change(self.entity_id, self.const.project_destroy, None)
        # Delete from entity tables
        Entity_class.delete(self)

    def list_projects(self):
        """List all projects"""
        return self.query("""
        SELECT project_id, owner, science
        FROM [:table schema=cerebrum name=project_info]""")

    def list_projects_allocations(self):
        """List all projects with allocation names"""
        return self.query("""
        SELECT a.name, a.allocation_authority, pi.project_id,
        pi.owner, pi.science
        FROM [:table schema=cerebrum name=project_info] pi,
        [:table schema=cerebrum name=allocation] a
        WHERE a.project_id=pi.project_id""")

    def add_member(self, member_id):
        """Add ``member`` to project"""
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=project_member]
          (project_id, member_id)
        VALUES (:project_id, :member_id)""",
                     {'project_id': self.entity_id,
                      'member_id': int(member_id)})
        #self._db.log_change(member_id, self.clconst.project_add, self.entity_id)
    def remove_member(self, member_id):
        """Remove ``member`` from project"""
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=project_member]
        WHERE project_id=:project_id AND member_id=:member_id""",
                     {'project_id': self.entity_id,
                      'member_id': int(member_id)})
        #self._db.log_change(member_id, self.clconst.project_remove, self.entity_id)

    def get_members(self):
        """Return a list of members of the project"""

        members = self.query("""SELECT member_id
        FROM [:table schema=cerebrum name=project_member]
        WHERE project_id=:project_id""", {'project_id': self.entity_id})
        return members


    def add_allocation(self, name, authority):
        """Add an allocation to project"""
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=allocation]
          (project_id, allocation_authority, name)
        VALUES (:project_id, :allocation_authority, :name)""",
                     {'project_id': self.entity_id,
                      'allocation_authority': int(authority),
                      'name': name})

    def remove_allocation(self, name):
        """Remove allocation from project"""
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=allocation]
        WHERE project_id=:project_id AND name=:name""",
                     {'project_id': self.entity_id,
                      'name': name})

    def get_allocations(self):
        """Return a list of allocations for the project"""

        allocations = self.query("""SELECT name, allocation_authority
        FROM [:table schema=cerebrum name=allocation]
        WHERE project_id=:project_id""", {'project_id': self.entity_id})
        return allocations

    def find_by_allocation_name(self, name):
        project_id=self.query_1("""
        SELECT project_id
        FROM [:table schema=cerebrum name=allocation]
        WHERE name=:name""", locals())
        self.find(project_id)

    def _add_credit_transaction(self, allocation_name, allocation_period,
                                credits, date=None):
        
        credit_transaction_id=self.nextval("credit_transaction_seq")
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=credit_transaction]
          (credit_transaction_id, project_id, allocation_period,
          date, credits)
        VALUES (:credit_transaction_id, :project_id, :allocation_period,
                :date, :credits)""",
                     {'credit_transaction_id': credit_transaction_id,
                      'project_id': self.entity_id,
                      'allocation_period': allocation_period.entity_id,
                      'date': date,
                      'credits': credits})
        return credit_transaction_id
    
    def allocate_credits(self, allocation_name, allocation_period,
                         credits, description=None):
        """Allocate credits to project and allocation_name"""
        credit_transaction_id=self._add_credit_transaction(allocation_name,
	    allocation_period, credits)
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=accounting_transaction]
          (credit_transaction_id, description)
        VALUES (:credit_transaction_id, :description)""",
                     {'credit_transaction_id': int(credit_transaction_id),
                      'description': description})

    def account_credits(self, allocation_name, allocation_period,
	credits, date, jobstart, jobend, machine, num_nodes, num_cores,
        max_memory, walltime, cputime, suspendtime, num_suspends,
	io_transfered, nice, account):
        """Account credits to project and allocation_name"""
        credit_transaction_id=self._add_credit_transaction(allocation_name,
	    allocation_period, credits, date)
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=accounting_transaction]
          (credit_transaction_id, jobstart, jobend, machine, num_nodes,
          num_cores, max_memory, walltime, cputime, suspendtime,
          num_suspends, io_transfered, nice, account)
        VALUES (:credit_transaction_id, :jobstart, :jobend, :machine,
        :num_nodes, :max_memory, :walltime, :cputime, :suspendtime,
        :num_suspends, :io_transfered, :nice, :account)""",
                     {'credit_transaction_id': int(credit_transaction_id),
                      'jobstart': jobstart,
                      'jobend': jobend,
                      'machine': machine.entity_id,
                      'num_nodes': num_nodes,
                      'num_cores': num_cores,
                      'max_memory': max_memory,
                      'walltime': walltime,
                      'cputime': cputime,
                      'suspendtime': suspendtime,
                      'num_suspends': num_suspends,
                      'io_transfered': io_transfered,
                      'nice': nice,
                      'account': account.entity_id})

    


#Entity_class already defined
class AllocationPeriod(Entity_class):
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('authority', 'name', 'startdate', 'enddate',
                      'description')

    def clear(self):
        super(AllocationPeriod, self).clear()
        self.clear_class(AllocationPeriod)
        self.__updated = []

    def populate(self, authority, name, startdate, enddate, parent=None):
        """Populate a new period"""
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity_class.populate(self, self.const.entity_project)
        
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False

        self.authority=authority
        self.name=name
        self.startdate=startdate
        self.enddate=enddate


    def write_db(self):
        """Write allocation_period instance to database"""
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=allocation_period]
            (allocation_period_id, authority, name, startdate, enddate)
            VALUES (:allocation_period_id, :authority, :name,
              :startdate, :enddate)""",
                         {'allocation_period_id' : self.entity_id,
                          'authority' : int(self.authority),
                          'name' : self.name,
                          'startdate' : self.startdate,
                          'enddate' : self.enddate})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=allocation_period]
            SET authority=:authority, name=:name, startdate=:startdate,
              enddate=:enddate
            WHERE allocation_period_id=:allocation_period_id
            VALUES (:allocation_period_id, :authority, :name,
              :startdate, :enddate)""",
                         {'allocation_period_id' : self.entity_id,
                          'authority' : int(self.authority),
                          'name' : self.name,
                          'startdate' : self.startdate,
                          'enddate' : self.enddate})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, allocation_period_id):
        """Connect object with 'allocation_period' in the database."""
        self.__super.find(allocation_period_id)
        (self.authority, self.name, self.startdate,
         self.enddate) = self.query_1("""
         SELECT authority, name, startdate, enddate
         FROM [:table schema=cerebrum name=allocation_period]
         WHERE allocation_period_id=:period_id""",
                                      {'period_id': allocation_period_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def find_by_name(self, name):
        allocation_period_id=self.query_1("""
        SELECT allocation_period_id
        FROM [:table schema=cerebrum name=allocation_period]
        WHERE name=:name""", locals())
        self.find(allocation_period_id)
        


    def delete(self):
        """Delete an unreferenced allocation period"""
        if self.__in_db:
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=allocation_period]
            WHERE allocation_period_id=:allocation_period_id""",
                         {'allocation_period_id': self.entity_id})
            #self._db.log_change(self.entity_id, self.const.allocation_period_destroy, None)
        # Delete from entity tables
        Entity_class.delete(self)

    def list_allocation_periods(self):
        """List all allocation periods"""
        return self.query("""
        SELECT allocation_period_id, authority, name, startdate, enddate
        FROM [:table schema=cerebrum name=allocation_period]""")



class Allocation(Entity_class):
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('authority', 'name')

    def clear(self):
        super(AllocationPeriod, self).clear()
        self.clear_class(AllocationPeriod)
        self.__updated = []

    def populate(self, authority, name, startdate, enddate, parent=None):
        """Populate a new period"""
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity_class.populate(self, self.const.entity_project)
        
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False

        self.authority=authority
        self.name=name
        self.startdate=startdate
        self.enddate=enddate


    def write_db(self):
        """Write allocation_period instance to database"""
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db

        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=allocation_period]
            (allocation_period_id, authority, name, startdate, enddate)
            VALUES (:allocation_period_id, :authority, :name,
              :startdate, :enddate)""",
                         {'allocation_period_id' : self.entity_id,
                          'authority' : int(self.authority),
                          'name' : self.name,
                          'startdate' : self.startdate,
                          'enddate' : self.enddate})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=allocation_period]
            SET authority=:authority, name=:name, startdate=:startdate,
              enddate=:enddate
            WHERE allocation_period_id=:allocation_period_id
            VALUES (:allocation_period_id, :authority, :name,
              :startdate, :enddate)""",
                         {'allocation_period_id' : self.entity_id,
                          'authority' : int(self.authority),
                          'name' : self.name,
                          'startdate' : self.startdate,
                          'enddate' : self.enddate})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def delete(self):
        """Delete an unreferenced allocation period"""
        if self.__in_db:
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=allocation_period]
            WHERE allocation_period=:allocation_period""",
                         {'allocation_period_id': self.allocation_period_id})
            #self._db.log_change(self.entity_id, self.const.allocation_period_destroy, None)
        # Delete from entity tables
        Entity_class.delete(self)




# arch-tag: 663a698a-9d38-11da-8f54-cae0bdbdc61d

# -*- coding: utf-8 -*-
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
from Cerebrum.modules.CLConstants import _ChangeTypeCode
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
    _lookup_table ='[:table schema=cerebrum name=allocation_credit_priority_code]'
    pass
    

class HpcConstants(Constants.Constants):
    CpuArch = _CpuArchCode
    OperatingSystem = _OperatingSystemCode
    InterConnect = _InterConnectCode
    AllocationAuthority = _AllocationAuthorityCode
    AllocationStatus = _AllocationStatusCode
    AllocationCreditPriority = _AllocationCreditPriorityCode
    Science = _ScienceCode

    entity_project = Constants._EntityTypeCode(
        'project',
        'see table project_info and friends')
    entity_allocation = Constants._EntityTypeCode(
        'allocation',
        'see table allocation_info and friends')
    entity_allocationperiod = Constants._EntityTypeCode(
        'allocationperiod',
        'see table allocation_period_info and friends')

    machine_mod = _ChangeTypeCode('e_machine', 'mod',
                                'modified %(subject)s')
    machine_demote = _ChangeTypeCode('e_machine', 'demote',
                                 'demote %(subject)s')
    machine_promote = _ChangeTypeCode('e_machine', 'promote',
                                 'promote %(subject)s')

    project_create = _ChangeTypeCode('e_project', 'create',
                                 'created %(subject)s')
    project_mod = _ChangeTypeCode('e_project', 'mod',
                                'modified %(subject)s')
    project_destroy = _ChangeTypeCode('e_project', 'destroy',
                                 'destroyed %(subject)s')
   
    allocation_create = _ChangeTypeCode('e_allocation', 'create',
                                  'created %(subject)s')
    allocation_mod = _ChangeTypeCode('e_allocation', 'mod',
                               'modified %(subject)s')
    allocation_destroy = _ChangeTypeCode('e_allocation', 'destroy',
                                'destroyed %(subject)s')
   
    allocation_period_create = _ChangeTypeCode('e_alloc_period', 'create',
                               'created %(subject)s')
    allocation_period_mod = _ChangeTypeCode('e_alloc_period', 'mod',
                               'modified %(subject)s')
    allocation_period_destroy = _ChangeTypeCode('e_alloc_period',
                                'destroy', 'destroyed %(subject)s')


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
            raise Errors.NoEntityAssociationError(
                  "Unable to determine which entity to delete.")
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
            WHERE host_id=:host_id""",
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
    __write_attr__ = ('owner_id', 'science', 'title', 'description')

    def clear(self):
        super(Project, self).clear()
        self.clear_class(Project)
        self.__updated = []

    def populate(self, owner_id, science, title=None, description=None,
                 parent=None):
        """Populate a new project"""
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity_class.populate(self, self.const.entity_project)
        
        try:
            if not self.__in_db:
                raise RuntimeError("populate() called multiple times.")
        except AttributeError:
            self.__in_db = False
        
        self.owner_id = owner_id
        self.science = science
        self.title = title
        self.description = description

    def write_db(self):
        """Write project instance to database"""
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db

        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=project_info]
            (project_id, owner, science, title, description) 
            VALUES (:project_id, :owner, :science, :title, :description)""",
                         {'project_id' : self.entity_id,
                          'owner' : self.owner_id,
                          'title' : self.title,
                          'description' : self.description,
                          'science' : int(self.science)})
            self._db.log_change(self.entity_id, self.const.project_create, None)
        else:
            binds = {'project_id': self.entity_id,
                     'owner': self.owner_id,
                     'title': self.title,
                     'description': self.description,
                     'science': int(self.science)}
            exists_stmt = """
              SELECT EXIST (
                SELECT 1
                FROM [:table schema=cerebrum name=project_info]
                WHERE
                  owner=:owner AND
                  science=:science AND
                  title=:title AND
                  description=:description AND
                  project_id=:project_id
                )
            """
            if not self.query_1(exists_stmt, binds):
                # True positive
                update_stmt = """
                  UPDATE [:table schema=cerebrum name=project_info]
                  SET owner=:owner, science=:science, title=:title,
                      description=:description
                  WHERE project_id=:project_id"""
                self.execute(update_stmt, binds)
                self._db.log_change(self.entity_id,
                                    self.const.project_mod,
                                    None)
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new


    def find(self, project_id):
        """Connect object to Project with ``project_id`` in database."""
        self.__super.find(project_id)
        (self.owner_id, self.science, self.title,
         self.description) = self.query_1("""
         SELECT owner, science, title, description
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
            DELETE FROM [:table schema=cerebrum name=project_info]
            WHERE project_id=:project_id""", {'project_id': self.entity_id})
            self._db.log_change(self.entity_id, self.const.project_destroy, None)
        # Delete from entity tables
        Entity_class.delete(self)

    def list_projects(self):
        """List all projects"""
        return self.query("""
        SELECT project_id, owner, science, title, description
        FROM [:table schema=cerebrum name=project_info]""")

    # Should use LIKE or such
    def list_projects_by_title(self, title):
        """List projects by title"""
        return self.query("""
        SELECT project_id, owner, science, title, description
        FROM [:table schema=cerebrum name=project_info]
        WHERE title=:title""",
                          {'title': title})

    def list_projects_allocation_names(self):
        """List all projects with allocation names"""
        return self.query("""
        SELECT a.project_allocation_name_id, a.name, a.allocation_authority,
        pi.project_id, pi.owner, pi.science, pi.title, pi.description
        FROM [:table schema=cerebrum name=project_info] pi,
        [:table schema=cerebrum name=project_allocation_name] a
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


    def add_allocation_name(self, name, authority):
        """Add an allocation name to project"""
        name_id=self.nextval("project_allocation_name_seq")
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=project_allocation_name]
          (project_allocation_name_id, project_id, allocation_authority, name)
        VALUES (:name_id, :project_id, :allocation_authority, :name)""",
                     {'name_id': name_id,
                      'project_id': self.entity_id,
                      'allocation_authority': int(authority),
                      'name': name})


    def remove_allocation_name(self, name):
        """Remove allocation name from project"""
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=project_allocation_name]
        WHERE name=:name""",
                     {'name': name})


    def get_allocation_names(self):
        """Return a list of allocations for the project"""

        allocations = self.query("""SELECT name, allocation_authority
        FROM [:table schema=cerebrum name=project_allocation_name]
        WHERE project_id=:project_id""", {'project_id': self.entity_id})
        return allocations

    def find_by_allocation_name(self, name):
        project_id=self.query_1("""
        SELECT project_id
        FROM [:table schema=cerebrum name=project_allocation_name]
        WHERE name=:name""", locals())
        self.find(project_id)



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
            Entity_class.populate(self, self.const.entity_allocationperiod)
        
        try:
            if not self.__in_db:
                raise RuntimeError("populate() called multiple times.")
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
            self._db.log_change(self.entity_id, self.const.allocation_create, None)
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=allocation_period]
            SET authority=:authority, name=:name, startdate=:startdate,
              enddate=:enddate
            WHERE allocation_period_id=:allocation_period_id""",
                         {'allocation_period_id' : self.entity_id,
                          'authority' : int(self.authority),
                          'name' : self.name,
                          'startdate' : self.startdate,
                          'enddate' : self.enddate})
            self._db.log_change(self.entity_id, self.const.allocation_mod, None)
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
            self._db.log_change(self.entity_id, self.const.allocation_period_destroy, None)
        # Delete from entity tables
        Entity_class.delete(self)

    def list_allocation_periods(self):
        """List all allocation periods"""
        return self.query("""
        SELECT allocation_period_id, authority, name, startdate, enddate
        FROM [:table schema=cerebrum name=allocation_period]""")



class Allocation(Entity_class):
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('authority', 'name_id', 'period', 'status')

    def clear(self):
        super(Allocation, self).clear()
        self.clear_class(Allocation)
        self.__updated = []

    def populate(self, name, period, status, parent=None):
        """Populate a new allocation"""
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity_class.populate(self, self.const.entity_allocation)
        
        try:
            if not self.__in_db:
                raise RuntimeError("populate() called multiple times.")
        except AttributeError:
            self.__in_db = False

        self.name_id=self._get_allocation_name_id(name)
        self.period=period
        self.status=status


    def write_db(self):
        """Write allocation instance to database"""
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db

        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=allocation_info]
            (allocation_id, name_id, allocation_period, allocation_status)
            VALUES (:allocation_id, :name_id, :allocation_period,
              :allocation_status)""",
                         {'allocation_id' : self.entity_id,
                          'name_id' : self.name_id,
                          'allocation_period' : self.period,
                          'allocation_status' : self.status})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=allocation_info]
            SET name_id=:name_id, allocation_period=:allocation_period,
              allocation_status=:allocation_status
            WHERE allocation_id=:allocation_id""",
                         {'allocation_id' : self.entity_id,
                          'name_id' : self.name_id,
                          'allocation_period' : self.period,
                          'allocation_status' : self.status})

        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def delete(self):
        """Delete an unreferenced allocation"""
        if self.__in_db:
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=allocation_info]
            WHERE allocation_id=:allocation_id""",
                         {'allocation_id': self.entity_id})
            self._db.log_change(self.entity_id, self.const.allocation_destroy, None)
        # Delete from entity tables
        Entity_class.delete(self)

    def list_allocations(self):
        """Lists all allocations"""
        return self.query("""
        SELECT allocation_id, allocation_name, allocation_period,
        allocation_status
        FROM [:table schema=cerebrum name=allocation_info]""")

    def _get_allocation_name_id(self, name):
        """Get project allocation name id from project allocation name"""
        return self.query_1("""
        SELECT project_allocation_name_id
        FROM [:table schema=cerebrum name=project_allocation_name]
        WHERE name=:name""", locals())
        
    def list_allocations_by_name(self, name):
        """Lists all allocations"""
        return self.query("""
        SELECT allocation_id, allocation_period, allocation_status
        FROM [:table schema=cerebrum name=allocation_info]
        WHERE name_id=(SELECT project_allocation_name_id
          FROM [:table schema=cerebrum name=project_allocation_name]
          WHERE name=:name)""", locals())

    def add_machine(self, machine_id):
        """Add ``machine`` to allocation"""
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=allocation_machine]
          (allocation_id, machine)
        VALUES (:allocation_id, :machine_id)""",
                     {'allocation_id': self.entity_id,
                      'machine_id': machine_id})
        #self._db.log_change(machine_id, self.clconst.allocation_add, self.entity_id)

    def get_machines(self):
        """List machines for thios allocation"""
        return self.query("""SELECT machine
        FROM [:table schema=cerebrum name=allocation_machine]
        WHERE allocation_id=:allocation_id""",
                          { 'allocation_id': self.entity_id })
        

    def remove_machine(self, machine_id):
        """Remove ``machine`` from allocation"""
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=allocation_machine]
        WHERE allocation_id=:allocation_id AND machine_id=:machine_id""",
                     {'allocation_id': self.entity_id,
                      'machine_id': machine_id})
        #self._db.log_change(machine_id, self.clconst.allocation_remove, self.entity_id)
        

    def _add_credit_transaction(self, credits, date=None):
        
        credit_transaction_id=self.nextval("credit_transaction_seq")
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=credit_transaction]
          (credit_transaction_id, allocation_id, date, credits)
        VALUES (:credit_transaction_id, :allocation_id, :date, :credits)""",
                     {'credit_transaction_id': credit_transaction_id,
                      'allocation_id': self.entity_id,
                      'date': date,
                      'credits': credits})
        return credit_transaction_id
    
    def allocate_credits(self, credits, date, priority, description=None):
        """Allocate credits to allocation and allocation_name"""
        credit_transaction_id=self._add_credit_transaction(credits, date)
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=allocation_transaction]
          (credit_transaction_id, allocation_credit_priority, description)
        VALUES (:credit_transaction_id, :priority, :description)""",
                     {'credit_transaction_id': int(credit_transaction_id),
                      'priority': priority,
                      'description': description})

    def account_credits(self, credits, date, jobstart, jobend, machine,
                        num_nodes, num_cores, max_memory_mb,
                        walltime, cputime, suspendtime, num_suspends,
                        io_transfered_mb, nice, account):
        """Account credits to allocation and allocation_name"""
        credit_transaction_id=self._add_credit_transaction(credits, date)
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=accounting_transaction]
          (credit_transaction_id, jobstart, jobend, machine,
          num_nodes, num_cores, max_memory_mb, walltime, cputime,
          suspendtime, num_suspends, io_transfered_mb, nice, account)
        VALUES (:credit_transaction_id, :jobstart, :jobend, :machine,
        :num_nodes, :num_cores, :max_memory_mb, :walltime, :cputime,
        :suspendtime, :num_suspends, :io_transfered_mb, :nice, :account)""",
                     {'credit_transaction_id': int(credit_transaction_id),
                      'jobstart': jobstart,
                      'jobend': jobend,
                      'machine': machine,
                      'num_nodes': num_nodes,
                      'num_cores': num_cores,
                      'max_memory_mb': max_memory_mb,
                      'walltime': walltime,
                      'cputime': cputime,
                      'suspendtime': suspendtime,
                      'num_suspends': num_suspends,
                      'io_transfered_mb': io_transfered_mb,
                      'nice': nice,
                      'account': account})

    
        



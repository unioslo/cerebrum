# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

from SpineLib import Registry
registry = Registry.get_registry()

class EntityAuth(object): # Mixin for Entity
    def is_superuser(self):
        """ Check if this object is a superuser """
        return False

    def check_permission(self, operator, operation_type, check_groups=True):
        """Check if operator has permission to do the operation on this object.
        
        ``operator`` is the entity doing the ``operation``

        operator  - Entity
        operation_type - AuthOperation

        If one of the following returns true, he has permission to perform
        the given operation:
            1: Is he a superuser?
            2: He got access to perform the operation on this target?
            3: He is member of a group wich got access to this target?
        """

        # 1 Is he a superuser?
        # -
        if operator.is_superuser():
            return True

        # 2 He got access to perform the operation on this target?
        # -
        # denne kan vi implementere i ren sql...
        # men denne burde være rask nok, siden det ikke blir alt for mange
        # operation_set pr entitet/target

        # finner først alle operation_set's som entiten har lov til å utføre på target
        searcher = registry.AuthRoleSearcher()
        searcher.set_entity(operator)
        searcher.set_target(self)

        # sjekker så om operation_type tilhører en av operation_set'ene vi finner
        for auth_role in searcher.search():
            print auth_role, operation_type, auth_role.get_operation_set()
            searcher = registry.AuthOperationSearcher()
            searcher.set_operation_type(operation_type)
            searcher.set_operation_set(auth_role.get_operation_set())
            if searcher.search():
                return True
        
        if not check_groups:
            return False
            
        # 3 He is member of a group wich got access to this target?
        # -
        # get_groups er ikke implementert. Den skal hente ut alle grupper denne entiteten
        # er direkte eller indirekte medlem av
        # jeg er litt forvirret av intersection/difference.. kanskje vi skal bestemme at
        # grupper entitenen er union-medlem i skal få lov til å brukes til auth?
        for entity in self.get_groups():
            if self.check_permission(entity, operation_type, check_groups=False):
                return True

        return False



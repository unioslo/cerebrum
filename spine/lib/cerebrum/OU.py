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

from Cerebrum.Utils import Factory
import Cerebrum

from SpineLib.Builder import Attribute, Method
from SpineLib.DatabaseClass import DatabaseAttr
from SpineLib.SpineExceptions import DatabaseError
from CerebrumClass import CerebrumClass, CerebrumAttr, CerebrumDbAttr

from SpineLib import Registry

from Commands import Commands
from Entity import Entity
from Types import EntityType, OUPerspectiveType

registry = Registry.get_registry()

__all__ = ['OU']

table = 'ou_info'
class OU(Entity):
    """
    This class represents an organizational unit (OU). OU objects are entities,
    and thus have the same attributes as Entity objects. In addition, they have
    the following attributes (accessible through their accessor methods):
        name - The name of the OU
        acronym - An acronym for the OU
        short_name - A short name for the OU
        display_name - A name for the OU suitable for display
        sort_name - A name on which the OU can be sorted

    OUs can be organized into hierarchical structures representing the
    hierarchy of units in an organization. OUs are useful for describing
    affiliations for persons.

    \\see Entity
    \\see Commands
    \\see PersonAffiliation
    """
    slots = Entity.slots + [
        CerebrumDbAttr('name', table, str, write=True),
        CerebrumDbAttr('acronym', table, str, write=True),
        CerebrumDbAttr('short_name', table, str, write=True), 
        CerebrumDbAttr('display_name', table, str, write=True),
        CerebrumDbAttr('sort_name', table, str, write=True)
    ]

    method_slots = Entity.method_slots + []

    db_attr_aliases = Entity.db_attr_aliases.copy()
    db_attr_aliases[table] = {
        'id': 'ou_id'
    }
    entity_type = EntityType(name='ou')
    cerebrum_class = Factory.get('OU')

registry.register_class(OU)

#def get_structure_mappings(self, perspective):
#    s = registry.OUStructureSearcher()
#    s.set_perspective(perspective)
#    return s.search()
#
#OU.register_method(Method('get_structure_mappings', [registry.OUStructure], args=[('perspective',
#    OUPerspectiveType)]), get_structure_mappings)

def get_parent(self, perspective):
    """
    Fetches the parent of the OU object from the given perspective. The
    perspective concept allows you to have multiple hierarchies of OUs,
    representing the organizational structure from different perspectives.
    
    \\param perspective The perspective from which the parent should be looked up.
    \\return The parent of this OU from the given perspective.
    \\see OUPerspectiveType
    \\see OUStructure
    """
    s = registry.OUStructureSearcher()
    s.set_ou(self)
    s.set_perspective(perspective)
    results = s.search()
    if len(s.search()) > 1:
        raise DatabaseError('More than one parent for %s in perspective %s' % (self, perspective))
    return s.search()[0].get_parent()

OU.register_method(Method('get_parent', OU, args=[('perspective', OUPerspectiveType)],
    exceptions=[DatabaseError]), get_parent)

def get_children(self, perspective):
    """
    Fetches a list of the OUs which are childrens of this OU from the given
    perspective.
    
    \\param perspective The perspective from which the children should be looked up.
    \\return A list of the children of this OU from the given perspective.
    \\see OUPerspectiveType
    \\see OUStructure
    """
    s = registry.OUStructureSearcher()
    s.set_parent(self)
    s.set_perspective(perspective)
    return [i.get_ou() for i in s.search()]

OU.register_method(Method('get_children', [OU], args=[('perspective', OUPerspectiveType)]), get_children)

def get_names(self):
    """
    Fetches all names for the OU.
    \\return A list of the names as strings.
    """
    ou = Factory.get('OU')(self.get_database())
    ou.find(self.get_id())
    return [i[0] for i in ou.get_names()]

OU.register_method(Method('get_names', [str], args=None, write=False), get_names)

def get_acronyms(self):
    """
    Fetches all acronyms for the OU.
    \\return A list of the acronyms as strings.
    """
    ou = Factory.get('OU')(self.get_database())
    ou.find(self.get_id())
    return [i[0] for i in ou.get_acronyms()]

OU.register_method(Method('get_acronyms', [str], args=None, write=False), get_acronyms)

def structure_path(self, perspective):
    """
    Returns a string describing the path to this OU
    from the given perspective.
    \\param perspective The perspective from which to find the structure path.
    \\return A string representing the structure path.
    """
    ou = Factory.get('OU')(self.get_database())
    ou.find(self.get_id())
    return ou.structure_path(perspective)

OU.register_method(Method('structure_path', str, args=[('perspective', OUPerspectiveType)]),
    structure_path)

def _set_parent(self, parent, perspective, forced_create):
    db = self.get_database()
    ou = Factory.get('OU')(db)
    parent_ou = Factory.get('OU')(db)

    # Create a NULL parent for the parent argument if it does not already have
    # a parent in the given perspective
    if forced_create:
        parent_ou.find(parent.get_id())
        try:
            parent_ou.get_parent(perspective.get_id())
        except Cerebrum.Errors.NotFoundError:
            parent_ou.set_parent(perspective.get_id(), None)

    # Set the parent of the OU
    ou.find(self.get_id())
    # TODO: Catch SQL exception and rethrow a more proper exception
    ou.set_parent(perspective.get_id(), parent.get_id())
    ou.write_db()

def set_parent(self, parent, perspective):
    """
    This method sets the parent of this OU from the given perspective.  Not
    that the parent supplied as an argument to this method must have a parent
    itself. If the supplied parent does not have a parent, you may force the
    automated creation of a None parent for the supplied parent by calling
    set_parent_forced_create() instead.

    \\param parent The OU to set as this OUs parent. The supplied OU must
    already have a parent.
    \\param perspective The perspective from which to set the parent.
    """
    _set_parent(self, parent, perspective, False)

def set_parent_forced_create(self, parent, perspective):
    """
    This method sets the parent of this OU from the given perspective. If the
    supplied parent does not already have a parent, it's parent will
    automatically be set to None. 

    \\param parent The OU to set as this OUs parent. The supplied OUs parent is
    set to None if it does not already have a parent.
    \\param perspective The perspective from which to set the parent.
    """
    _set_parent(self, parent, perspective, True)

OU.register_method(Method('set_parent', None, 
    args=[('parent', OU), ('perspective', OUPerspectiveType)], write=True), set_parent)

OU.register_method(Method('set_parent_forced_create', None, 
    args=[('parent', OU), ('perspective', OUPerspectiveType)], write=True), set_parent_forced_create)

def unset_parent(self, perspective):
    """
    Removes the parent for this OU from the given perspective.

    \\param perspective The perspective from which to remove this OUs parent.
    """
    db = self.get_database()
    ou = Factory.get('OU')(db)
    ou.find(self.get_id())
    ou.unset_parent(perspective.get_id())
    ou.write_db()

OU.register_method(Method('unset_parent', None, 
    args=[('perspective', OUPerspectiveType)], write=True), unset_parent)

def create_ou(self, name):
    """
    Creates a new OU (Organizational Unit).

    \\param name The name of the OU to be created.
    \\return The created OU object.
    """
    db = self.get_database()
    ou = Factory.get('OU')(db)
    ou.populate(name)
    ou.write_db()
    spine_ou = OU(ou.entity_id, write_locker=self.get_writelock_holder())
    return spine_ou

Commands.register_method(Method('create_ou', OU, args=[('name', str)], write=True), create_ou)

# arch-tag: ec070b27-28c8-4b51-b1cd-85d14b5e28e4

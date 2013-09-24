# -*- coding: utf-8 -*-
# Copyright 2013 University of Oslo, Norway
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
"""Default Cerebrum settings for Active Directory and the AD synchronisations.

Overrides should go in a local, instance specific file named:

    adconf.py

Each setting should be well commented in this file, to inform developers and
sysadmin about the usage and consequences of the setting.

TODO: Should the check for valid config be here, or in the sync instead?

"""

import cerebrum_path
import cereconf
from Cerebrum.Utils import NotSet

class AttrConfig(object):
    """Configuration settings for an AD attribute.

    This class, and its subclasses, is used to specify what a given attribute
    should contain of information. The configuration is then used by the AD sync
    to feed the given attribute with the values from db that matches these
    criterias.

    """
    def __init__(self, default=NotSet, transform=NotSet, spreads=NotSet):
        """Setting the basic, most used config variables.

        @type default: mixed
        @param default: The default value to set for the attribute if no other
            value is found, based on other criterias, e.g. in the subclasses.

        @type transform: function
        @param transform: A function, e.g. a lambda, that should process the 
            given value before sending it to AD. This could for instance be used
            to strip whitespace, or lowercase strings. For instance:

                lambda x: x[1:].lower()

        @type spreads: str of Cerebrum constants or list thereof
        @param spreads: If set, defines what spreads the user must have for the
            value to be set. Entitites without the spread would get an empty
            (blank) value.

        # TODO: Should attributes behave differently when multiple values are
        # accepted? For instance with the contact types.

        """
        # TODO
        if default is not NotSet:
            self.default = default
        if transform is not NotSet:
            self.transform = transform
        if spreads is not NotSet:
            if not isinstance(spreads, (list, tuple, set)):
                spreads = [spreads]
            self.spreads = spreads

class ContactAttr(AttrConfig):
    """Configuration for an attribute containing contact info.

    This is used for attributes that should contain data that is stored as
    contact info in Cerebrum. 

    """
    def __init__(self, contact_types, source_systems=None, *args, **kwargs):
        """Initiate a contact info variable.

        @type contact_types: str or list thereof
        @param contact_types: One or more of the contact types to use, in
            priority, i.e. the first contact type is used if it exists for an
            entity, otherwise the next one. The contact types are identified by
            their L{code_str}.

        @type source_systems: int or Constant or list thereof
        @param source_systems: One or more of the given source systems to
            retrieve the information from, in prioritised order. If None is set,
            contact info from all source systems is used.

        """
        super(ContactAttr, self).__init__(*args, **kwargs)
        if not isinstance(contact_types, (list, tuple)):
            contact_types = (contact_types,)
        self.contact_types = contact_types
        if source_systems and not isinstance(source_systems, (list, tuple)):
            source_systems = (source_systems,)
        self.source_systems = source_systems

# The SYNCS dict contains settings that are specific to a given sync type. The


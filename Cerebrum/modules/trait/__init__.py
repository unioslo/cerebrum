# -*- coding: utf-8 -*-
#
# Copyright 2022-2026 University of Oslo, Norway
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
Traits are simple key-value stores, where the key is a special CerebrumCode.

Traits are unique tags or attributes that are given to an Entity.  A given
entity can only have *one* trait of a given trait type.

Traits are stored in the ``entity_trait`` table, valid trait types in the
``entity_trait_code`` table.


Trait types
    Each trait type (code) is a distinct ``_EntityTraitCode`` constant.  The
    trait type is limited to a single entity type, and any given trait type
    can only be bound to entities of this type.  Each entity can have zero or
    one traits of a given type.

Trait attributes
    Each trait can store one value of each type:

    - string (strval)
    - number (intval)
    - timestamp (date)
    - target entity_id (target_id)

    Combinations are allowed (i.e. a single trait can store both a string value
    and a numeric value).  The meaning of these values (if any) depend on how
    the trait is used.

    The special ``target_id`` attribute can be used to loosely bind two
    entities together.  Just as with other values, the meaning of this binding
    depends on how the trait is used.


Example use cases
==================
Traits can be used as simple *tags*.  A given trait type can be used to
*exclude* a given user account from forced password rotation, or to mark a
group as *too* important to automatically delete when it is expired.

Traits can also be used to store single-valued *attributes* on an entity. E.g.
an *entitlement* trait can be used to store a Feide ``eduPersonEntitlement``
URN value that should be assigned to all its members.


Add support for traits
=======================
While the trait module is *optional*, a lot of existing Cerebrum features and
scripts depend on the trait functionality.  Most deployments of Cerebrum will
require trait support.

1. Add schema (``design/mod_entity_trait.sql``)
2. Configure cereconf with trait codes and entity mixins.
3. Optionally, add bofhd-commands


Configuration
-------------
``cereconf.CLASS_CLCONSTANTS``
    Must contain the :class:`.constants.CLConstants` class.

    Example:
    ::

        CLASS_CLCONSTANTS = [
          "Cerebrum.modules.trait.constants/CLConstants",
          "Cerebrum.Constants/CLConstants",
        ]

``cereconf.CLASS_CONSTANTS``
    Should contain the :class:`.constants.Constants` class.  This
    is required for most existing trait features in Cerebrum.

    Example:
    ::

        CLASS_CONSTANTS = [
          "Cerebrum.modules.trait.constants/Constants",
          "Cerebrum.Constants/Constants",
        ]

    ``CLASS_CONSTANTS`` should also include constant classes that adds the
    actual trait types that will be used.  The trait module itself does not
    define any trait types.

``cereconf.CLASS_*``
    Entity classes with trait support should have
    :class:`Cerebrum.modules.EntityTrait.EntityTrait`.  This is a requirement
    for most pre-existing use of traits in Cerebrum.

    .. note::
       This is a legacy module, and is planned to be re-factored.

    As trait codes themselves are bound to specific entity types, it's common
    to add trait support directly to ``cereconf.CLASS_ENTITY``, and restrict
    traits to specific entity types by simply not defining any trait types for
    them.

    Example:
    ::

        CLASS_ENTITY = [
          "Cerebrum.modules.EntityTrait/EntityTrait",
          "Cerebrum.Account/Account",
        ]


Bofhd
    Bofhd commands and common authorization rules are implemented in
    :mod:`.bofhd_trait_cmds`.  Remember to subclass and mixin custom
    authorization classes, and add the custom command class to the appropriate
    bofhd commands config.


History
========
Functionality has been (or will be) collected here from various places:

Bofh commands
    Moved from ``Cerebrum.modules.no.uio.bofhd_uio_commands`` after:

      Commit: 863cf9247bcbaea60e48201024abd57f299cbea7


TODO
=====
Refactor/move ``Cerebrum.modules.EntityTrait``
    DBAL and Entity-mixin.  Should be split into a separate module for running
    database queries, and a mixins module, and moved into
    ``Cerebrum.modules.trait``.

Extract trait related codes from ``Cerebrum.modules.bofhd.bofhd_constants``
    Defines ``_AuthRoleOpCode`` constants for delegating access to bofhd trait
    commands.

    Should be moved into `Cerebrum.modules.trait.constants`.
"""

# database schema version (mod_entity_trait)
__version__ = "1.1"

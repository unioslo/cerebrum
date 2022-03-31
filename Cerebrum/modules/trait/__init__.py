# -*- coding: utf-8 -*-
#
# Copyright 2022 University of Oslo, Norway
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

Traits are stored in the entity_trait table, valid trait types in the
entity_trait_code table.

Trait types
    Each trait type (code) is a distinct `_EntityTraitCode` constant.  The
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

    The special `target_id` attribute can be used to loosely bind two entities
    together.  Just as with other values, the meaning of this binding is
    typically different in each trait.


History
-------
Functionality has een (or will be) collected here from various places:

Bofh commands
    Moved from ``Cerebrum.modules.no.uio.bofhd_uio_commands`` after:

      Commit: 863cf9247bcbaea60e48201024abd57f299cbea7


TODO
----
Refactor/move ``Cerebrum.modules.EntityTrait``
    DBAL and Entity-mixin.  Should be split into a separate module for running
    database queries, and a mixins module, and moved into
    ``Cerebrum.modules.trait``.

Refactor/move ``Cerebrum.modules.EntityTraitConstants``
    Defines the ``_EntityTraitCode`` (trait type) and adds ``_ChangeTypeCode``
    constants for each trait change type.

    Should be moved into a ``Cerebrum.modules.trait.constants`` module.

Extract trait related codes from ``Cerebrum.modules.bofhd.bofhd_constants``
    Defines ``_AuthRoleOpCode`` constants for delegating access to bofhd trait
    commands.

    Should be moved into a `Cerebrum.modules.trait.constants` module.

Move module version
    The versioning of the traits module should be moved from
    ``Cerebrum.modules.EntityTrait`` and into this __init__ module (and
    references in makedb/migrate-db updated).
"""

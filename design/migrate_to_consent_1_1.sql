/*
 * Copyright 2023 University of Oslo, Norway
 *
 * This file is part of Cerebrum.
 *
 * Cerebrum is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * Cerebrum is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Cerebrum; if not, write to the Free Software Foundation,
 * Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
 */

/* SQL script for migrating mod_consent from 1.0 to 1.1 */

/* Use tz-aware field */
category:pre;
ALTER TABLE entity_consent
  ALTER COLUMN time_set
    TYPE TIMESTAMP WITH TIME ZONE;

/* Follow name standard elsewhere in cerebrum */
category:pre;
ALTER TABLE entity_consent
    RENAME time_set TO set_at;

/* Remove unused column */
category:pre;
ALTER TABLE entity_consent
  DROP COLUMN expiry;

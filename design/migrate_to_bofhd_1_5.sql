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

/* SQL script for migrating a bofhd_tables 1.4 to 1.5 */

category:pre;
ALTER TABLE bofhd_session_state
  ALTER COLUMN set_time
    TYPE TIMESTAMP WITH TIME ZONE;

/*
 * Add not null constraint to bofhd_session.last_seen
 *
 * We also delete session data that doesn't follow this constraint.  No such
 * rous *should* exist, as all code actually sets this value, but we do it just
 * in case.  Worst case, someone is logged out of bofhd ...
 */
category:pre;
DELETE FROM bofhd_session_state
WHERE session_id in (
   SELECT session_id
   FROM bofhd_session
   WHERE last_seen IS NULL
);

category:pre;
DELETE FROM bofhd_session
WHERE last_seen IS NULL;

category:pre;
ALTER TABLE bofhd_session
  ALTER COLUMN last_seen
    SET NOT NULL;

category:pre;
ALTER TABLE bofhd_session
  ALTER COLUMN last_seen
    TYPE TIMESTAMP WITH TIME ZONE;

category:pre;
ALTER TABLE bofhd_session
  ALTER COLUMN auth_time
    TYPE TIMESTAMP WITH TIME ZONE;

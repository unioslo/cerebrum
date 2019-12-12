/* encoding: utf-8
 *
 * Copyright 2005-2019 University of Oslo, Norway
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
 *
 *
 * tables used by Cerebrum.modules.disk_quota
 */
category:metainfo;
name=disk_quota;

category:metainfo;
version=1.0;

category:drop;
DROP TABLE disk_quota;

/*  disk_quota
 *
 * Stores disk-quota data for accounts.
 *
 * homedir_id
 *   Identifiserer homedir kvoten gjelder for (som implisitt indikerer konto)
 * quota
 *   Kvote i antall MB.  NULL = unlimited
 * override_quota
 * override_expiration
 *   Kvoten overstyres med angitt verdi frem til expiration dato
 * description
 *   Årsak til override
 */
category:main;
CREATE TABLE disk_quota
(
  homedir_id
    NUMERIC(12,0)
    CONSTRAINT disk_quota_pk PRIMARY KEY
    REFERENCES homedir(homedir_id),

  quota
    NUMERIC(6,0),

  override_quota
    NUMERIC(6,0),

  override_expiration
    DATE,

  description
    CHAR VARYING(512),

  CONSTRAINT disk_quota_override_chk
    CHECK (override_quota IS NULL OR
           (override_expiration IS NOT NULL
            AND description IS NOT NULL))
);

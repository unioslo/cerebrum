/*
 * Copyright 2006 University of Oslo, Norway
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

/* SQL script for migrating a bofhd_auth 1.1 to 1.2 */

/* Expand code_str column to varchar(64) */
category:pre;
ALTER TABLE auth_op_code ADD COLUMN code_str_new VARCHAR(64)
    CONSTRAINT auth_op_codestrnew_u UNIQUE;
category:pre;
UPDATE auth_op_code SET code_str_new = code_str;
category:pre;
ALTER TABLE auth_op_code ALTER COLUMN code_str_new SET NOT NULL;
category:pre;
ALTER TABLE auth_op_code DROP COLUMN code_str;
category:pre;
ALTER TABLE auth_op_code RENAME COLUMN code_str_new TO code_str;
category:pre;
ALTER TABLE auth_op_code ADD CONSTRAINT auth_op_codestr_u UNIQUE (code_str);
category:pre;
ALTER TABLE auth_op_code DROP CONSTRAINT auth_op_codestrnew_u;

/* Rename the description column to get the column number order back to what it
 * was before the above operation.  This is most likely completely unnecessary.
 * (We had: [code, code_str, desc]. Now we have: [code, desc, code_str]. After
 * the following we'll have: [code, code_str, desc] again.  */
category:pre;
ALTER TABLE auth_op_code ADD COLUMN desc_new VARCHAR(512);
category:pre;
UPDATE auth_op_code SET desc_new = description;
category:pre;
ALTER TABLE auth_op_code ALTER COLUMN desc_new SET NOT NULL;
category:pre;
ALTER TABLE auth_op_code DROP COLUMN description;
category:pre;
ALTER TABLE auth_op_code RENAME COLUMN desc_new TO description;

/* arch-tag: 273eaab0-abf8-11da-945c-29e8ee2ffa5e
   (do not change this comment) */

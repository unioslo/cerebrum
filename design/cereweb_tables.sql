/*
 * Copyright 2003, 2004 University of Oslo, Norway
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

/* Tables for storing cereweb-specific data in the database.
   These tables are intended for internal cereweb use only.
 */

category:metainfo;
name=cereweb;
category:metainfo;
version=1.0;

category:code;
CREATE SEQUENCE cereweb_seq;

category:main;
CREATE TABLE cereweb_option
(
    option_id   NUMERIC(12,0)
                    NOT NULL
                    CONSTRAINT cereweb_option_pk PRIMARY KEY,
    entity_id   NUMERIC(12,0)
                    NOT NULL
                    CONSTRAINT cereweb_option_entity_id
                        REFERENCES entity_info(entity_id),
    key         CHAR VARYING(50)
                    NOT NULL,
    value       CHAR VARYING(1024)
);

category:main;
CREATE TABLE cereweb_motd
(
    motd_id     NUMERIC(12,0)
                    NOT NULL
                    CONSTRAINT cereweb_motd_pk PRIMARY KEY,
    create_date TIMESTAMP
                    DEFAULT [:now]
                    NOT NULL,
    creator     NUMERIC(12,0)
                    NOT NULL
                    CONSTRAINT cereweb_motd_creator
                        REFERENCES entity_info(entity_id),
    subject     CHAR VARYING(70),
    message     CHAR VARYING(1024)
);

category:drop;
DROP TABLE cereweb_option;

category:drop;
DROP TABLE cereweb_motd;

category:drop;
DROP SEQUENCE cereweb_seq;

/* arch-tag: 2f6b9477-8d68-46d4-8ba2-ac55634d451c
   (do not change this comment) */

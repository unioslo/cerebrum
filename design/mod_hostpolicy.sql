/* encoding: utf-8
 *
 * Copyright 2011-2019 University of Oslo, Norway
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
 * Tables used by Cerebrum.modules.hostpolicy
 */
category:metainfo;
name=hostpolicy;

category:metainfo;
version=1.1;


category:main;
CREATE TABLE hostpolicy_component
(
  entity_type
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT dns_policy_component_type_chk
      CHECK (entity_type = [:get_constant name=entity_hostpolicy_atom] OR
             entity_type = [:get_constant name=entity_hostpolicy_role]),

  component_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT hostpolicy_component_pk PRIMARY KEY,

  description
    CHAR VARYING(512)
    NOT NULL
    DEFAULT '',

  foundation
    CHAR VARYING(512)
    DEFAULT '',

  foundation_date
    DATE
    DEFAULT [:now]
    NOT NULL,

  CONSTRAINT hostpolicy_component_entity_info
    FOREIGN KEY (entity_type, component_id)
    REFERENCES entity_info(entity_type, entity_id)
);


category:code;
CREATE TABLE hostpolicy_relationship_code
(
  code
    NUMERIC(6,0)
    CONSTRAINT hostpolicy_relationship_code_pk PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT hostpolicy_relationship_code_codestr_u UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


category:main;
CREATE TABLE hostpolicy_relationship
(
  source_policy
    NUMERIC(12,0)
    CONSTRAINT hostpolicy_relationship_source
      REFERENCES hostpolicy_component(component_id),

  relationship
    NUMERIC(6,0)
    CONSTRAINT hostpolicy_relationship_relationship
      REFERENCES hostpolicy_relationship_code(code),

  target_policy
    NUMERIC(12,0)
    CONSTRAINT hostpolicy_relationship_target
      REFERENCES hostpolicy_component(component_id),

  CONSTRAINT hostpolicy_relationship_pk
    PRIMARY KEY (source_policy, relationship, target_policy),

  CONSTRAINT hostpolicy_relationship_not_self
    CHECK (source_policy <> target_policy)
);


category:main;
CREATE TABLE hostpolicy_host_policy
(
  dns_owner_id
    NUMERIC(12,0)
    CONSTRAINT hostpolicy_host_policy_dns_owner_id
      REFERENCES dns_owner(dns_owner_id),

  policy_id
    NUMERIC(12,0)
    CONSTRAINT hostpolicy_host_policy_policy_id
      REFERENCES hostpolicy_component(component_id),

  CONSTRAINT hostpolicy_host_policy_pk
    PRIMARY KEY (dns_owner_id, policy_id)
);

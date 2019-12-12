/* encoding: utf-8
 *
 * Copyright 2006-2019 University of Oslo, Norway
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
 * Tables used by Cerebrum.modules.Hpc
 */
category:metainfo;
name=hpc;

category:metainfo;
version=1.0;

/* TODO: split into hpcadmin, hpcquota,
 *  add remaining stuff
 */


category:code;
CREATE TABLE cpu_arch_code
(
  code
    NUMERIC(6,0)
    CONSTRAINT cpu_arch_code_pk PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT cpu_arch_codestr_u UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


category:code;
CREATE TABLE operating_system_code
(
  code
    NUMERIC(6,0)
    CONSTRAINT operating_system_code_pk PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT operating_system_codestr_u UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


category:code;
CREATE TABLE interconnect_code
(
  code
    NUMERIC(6,0)
    CONSTRAINT interconnect_code_pk PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT interconnect_codestr_u UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


/* Mixin to host */
category:main;
CREATE TABLE machine_info
(
  host_id
    NUMERIC(12,0)
    CONSTRAINT machine_info_pk PRIMARY KEY
    CONSTRAINT machine_info_host_id
      REFERENCES host_info(host_id),

  /* Advisory numbers, may not always be precise.
   *
   * May later be moved to separate node table to accomodate
   * asymmetric configurations.
   * Until then, use average or minimum numbers.
   * Note that any of these may be NULL */

  total_memory
    NUMERIC(12,0),

  node_number
    NUMERIC(12,0),

  node_memory
    NUMERIC(12,0),

  node_disk
    NUMERIC(12,0),

  cpu_core_number
    NUMERIC(12,0),

  cpu_core_mflops
    NUMERIC(12,0),

  cpu_mhz
    NUMERIC(12,0),

  credit_production
    NUMERIC(12,0),

  cpu_arch
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT machine_info_cpu_arch
      REFERENCES cpu_arch_code(code),

  operating_system
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT machine_info_operating_system
      REFERENCES operating_system_code(code),

  interconnect
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT machine_info_interconnect
      REFERENCES interconnect_code(code)
);


category:code;
CREATE TABLE allocation_authority_code
(
  code
    NUMERIC(6,0)
    CONSTRAINT allocation_authority_code_pk PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT allocation_authority_codestr_u UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


category:code;
CREATE TABLE allocation_status_code
(
  code
    NUMERIC(6,0)
    CONSTRAINT allocation_status_code_pk PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT allocation_status_codestr_u UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


category:code;
CREATE TABLE allocation_credit_priority_code
(
  code
    NUMERIC(6,0)
    CONSTRAINT allocation_credit_priority_code_pk PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT allocation_credit_priority_codestr_u UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


category:code;
CREATE TABLE science_code
(
  code
    NUMERIC(6,0)
    CONSTRAINT science_code_pk PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT science_codestr_u UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


/* New entity */
category:main;
CREATE TABLE project_info
(
  project_id
    NUMERIC(12,0)
    CONSTRAINT project_info_pk PRIMARY KEY
    CONSTRAINT project_info_project_id
      REFERENCES entity_info(entity_id),

  owner
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT project_info_owner
      REFERENCES person_info(person_id),

  science
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT project_info_science
      REFERENCES science_code(code),

  title
    CHAR VARYING(512),

  description
    CHAR VARYING(512)
);


category:main;
CREATE TABLE project_member
(
  project_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT project_member_project_id
      REFERENCES project_info(project_id),

  member_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT project_member_member_id
      REFERENCES person_info(person_id),

  CONSTRAINT project_member_pk
    PRIMARY KEY (project_id, member_id)
);


category:code;
CREATE SEQUENCE project_allocation_name_seq;


/*  project_allocation_name
 *
 * project_allocation_name(name) is "kvotenummer" in the spesification
 */
category:main;
CREATE TABLE project_allocation_name
(
  project_allocation_name_id
    NUMERIC(12,0)
    CONSTRAINT project_allocation_name_id PRIMARY KEY,

  name
    CHAR VARYING(16)
    CONSTRAINT project_allocation_name_name_u UNIQUE,

  project_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT allocation_project_id
      REFERENCES project_info(project_id),

  allocation_authority
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT allocation_allocation_authority
      REFERENCES allocation_authority_code(code)
);


/*
 * This should really be category:code, but the data needed may make
 * that impossible????
 */
category:main;
CREATE TABLE allocation_period
(
  allocation_period_id
    NUMERIC(12,0)
    CONSTRAINT allocation_period_id PRIMARY KEY,

  authority
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT allocation_period_authority
      REFERENCES allocation_authority_code(code),

  name
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT allocation_period_name_u UNIQUE,

  startdate
    DATE
    NOT NULL,

  enddate
    DATE
    NOT NULL
);


category:main;
CREATE TABLE allocation_info
(
  allocation_id
    NUMERIC(12,0)
    CONSTRAINT allocation_info_pk PRIMARY KEY
    CONSTRAINT allocation_info_project_id
      REFERENCES entity_info(entity_id),

  name_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT allocation_info_name_id
      REFERENCES project_allocation_name(project_allocation_name_id),

  allocation_period
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT allocation_info_allocation_period
      REFERENCES allocation_period(allocation_period_id),

  allocation_status
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT allocation_info_allocation_status
      REFERENCES allocation_status_code(code)
);

category:main;
CREATE TABLE allocation_machine
(
  allocation_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT allocation_machine_allocation
      REFERENCES allocation_info(allocation_id),

  machine
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT accounting_machine_machine
      REFERENCES machine_info(host_id)
);


category:code;
CREATE SEQUENCE credit_transaction_seq;


/*
 * Should this really refer to directly to allocation "kvotenummer",
 * instead of project??
 */
category:main;
CREATE TABLE credit_transaction
(
  credit_transaction_id
    NUMERIC(12,0)
    CONSTRAINT credit_transaction_pk PRIMARY KEY,

  allocation_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT credit_transaction_allocation_id
      REFERENCES allocation_info(allocation_id),

  credits
    NUMERIC(24,0)
    NOT NULL,

  date
    TIMESTAMP
    DEFAULT [:now]
    NOT NULL
);


category:main;
CREATE TABLE accounting_transaction
(
  credit_transaction_id
    NUMERIC(12,0)
    CONSTRAINT accounting_transaction_pk PRIMARY KEY
    CONSTRAINT accounting_transaction_credit_transaction_id
      REFERENCES credit_transaction(credit_transaction_id),

  jobsubmit
    TIMESTAMP,

  jobstart
    TIMESTAMP,

  jobend
    TIMESTAMP,

  machine
    NUMERIC(12,0)
    CONSTRAINT accounting_transaction_machine
      REFERENCES machine_info(host_id),

  jobid
    CHAR VARYING(64),

  jobname
    CHAR VARYING(64),

  queuename
    CHAR VARYING(16),
    /* Should refer to code? */

  num_nodes
    NUMERIC(12,0),

  num_cores
    NUMERIC(12,0),

  num_nodes_req
    NUMERIC(12,0),

  num_cores_req
    NUMERIC(12,0),

  memory_req_mb
    NUMERIC(12,0),

  max_memory_mb
    NUMERIC(12,0),

  walltime_req
    NUMERIC(12,0),

  walltime
    NUMERIC(12,0),

  cputime_req
    NUMERIC(24,0),

  cputime
    NUMERIC(24,0),

  waittime
    NUMERIC(12,0),

  suspendtime
    NUMERIC(12,0),

  num_suspends
    NUMERIC(12,0),

  io_transfered_mb
    NUMERIC(24,0),

  nice
    NUMERIC(12,0),

  exitstatus
    NUMERIC(12,0),

  account
    NUMERIC(12,0)
    CONSTRAINT accounting_transaction_account
      REFERENCES account_info(account_id)

  /* Do we really need this? Version 2? */
  /*
  group
    NUMERIC(12,0)
    CONSTRAINT accounting_transaction_group
      REFERENCES group_info(group_id),
  */
);


category:main;
CREATE TABLE allocation_transaction
(
  credit_transaction_id
    NUMERIC(12,0)
    CONSTRAINT allocation_transaction_pk PRIMARY KEY
      CONSTRAINT allocation_transaction_credit_transaction_id
      REFERENCES credit_transaction(credit_transaction_id),

  allocation_credit_priority
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT allocation_transaction_allocation_credit_priority
      REFERENCES allocation_credit_priority_code(code),

  description
    CHAR VARYING(512)
);


category:drop;
DROP TABLE accounting_transaction;

category:drop;
DROP TABLE allocation_transaction;

category:drop;
DROP TABLE credit_transaction;

category:drop;
DROP SEQUENCE credit_transaction_seq;

category:drop;
DROP TABLE allocation_machine;

category:drop;
DROP TABLE allocation_info;

category:drop;
DROP TABLE project_allocation_name;

category:drop;
DROP SEQUENCE project_allocation_name_seq;

category:drop;
DROP TABLE project_member;

category:drop;
DROP TABLE project_info;

category:drop;
DROP TABLE allocation_period;

category:drop;
DROP TABLE allocation_authority_code;

category:drop;
DROP TABLE allocation_status_code;

category:drop;
DROP TABLE allocation_credit_priority_code;

category:drop;
DROP TABLE science_code;

category:drop;
DROP TABLE machine_info;

category:drop;
DROP TABLE cpu_arch_code;

category:drop;
DROP TABLE operating_system_code;

category:drop;
DROP TABLE interconnect_code;

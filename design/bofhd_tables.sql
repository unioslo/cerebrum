/* Tables for storing state in the bofhd server.  The tables are
  intended for internal bofhd use only.
*/

/* bofhd_session

  session_id : unique PK
  account_id : associated authenticated session.  If it was
      FK(account), extra code would be needed in delete_account
  auth_time : time-stamp for last authentication

  TBD:  do we also want a "last-seen" entry?
*/

category:main;
CREATE TABLE bofhd_session
(
  session_id   CHAR VARYING(32)
               CONSTRAINT bofhd_session_pk PRIMARY KEY
               NOT NULL,
  account_id   NUMERIC(12,0)
               NOT NULL,
  auth_time    DATE
               NOT NULL
);

/* bofhd_session_state

  session_id : FK to  bofhd_session
  state_type : identifies the type of state, i.e set_passwd
  entity_id  : affected entity_id
  state_data : data
  set_time   : time-stamp

  TBD:  do we want entity_id?
*/

category:main;
CREATE TABLE bofhd_session_state
(
  session_id   CHAR VARYING(32)
               CONSTRAINT bofhd_session_state_fk 
                 REFERENCES bofhd_session(session_id)
               NOT NULL,
  state_type   CHAR VARYING(32)
               NOT NULL,
  entity_id    NUMERIC(12,0)
               NULL,
  state_data   CHAR VARYING(80)
               NULL,
  set_time     DATE
               NOT NULL
);

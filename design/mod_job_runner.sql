category:main;
CREATE TABLE job_ran
(
  id           CHAR VARYING(32)
               CONSTRAINT job_ran_pk
               PRIMARY KEY,
  timestamp    TIMESTAMP
               NOT NULL
);

category:main;
CREATE TABLE job_ran
(
  id           CHAR VARYING(32)
               CONSTRAINT job_ran_pk
               PRIMARY KEY,
  timestamp    TIMESTAMP
               NOT NULL
);

category:drop;
DROP TABLE job_ran;

/* arch-tag: aa468296-bbb1-427f-aac9-cdeedeabf59a
   (do not change this comment) */

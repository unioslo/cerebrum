/* tables used by Cerebrum.modules.no.uio.DiskQuota

  Stores disk-quota data for accounts. */
category:metainfo;
name=disk_quota;
category:metainfo;
version=1.0;
category:drop;
DROP TABLE disk_quota;

/*  disk_quota

   homedir_id
       Identifiserer homedir kvoten gjelder for (som implisitt
       indikerer konto)
   quota
       Kvote i antall MB.  NULL = unlimited
   override_quota
   override_expiration
       Kvoten overstyres med angitt verdi frem til expiration dato
   description
       Årsak til override
*/

category:main;
CREATE TABLE disk_quota (
  homedir_id            NUMERIC(12,0)
                        CONSTRAINT disk_quota_pk PRIMARY KEY
                        REFERENCES homedir(homedir_id),
  quota                 NUMERIC(6,0),
  override_quota        NUMERIC(6,0),
  override_expiration   DATE,
  description           CHAR VARYING(512),
  CONSTRAINT disk_quota_override_chk
    CHECK (override_quota IS NULL OR
           (override_expiration IS NOT NULL 
            AND description IS NOT NULL))
);

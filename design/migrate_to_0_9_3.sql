/* SQL script for migrating a 0.9.2 database to 0.9.3
*/
category:pre;
ALTER TABLE auth_op_target ADD COLUMN attr CHAR VARYING(50);

category:post;
ALTER TABLE auth_op_target DROP COLUMN has_attr;
category:post;
DROP TABLE auth_op_target_attrs;

/* arch-tag: f4411d8a-a413-4bcc-b26e-2caaff887540
   (do not change this comment) */

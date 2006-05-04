
from Cerebrum.modules import PosixUser

class UidRangeException(Exception):
    """Exception raissed for Uids out of legal range"""
    pass


# This probably behaves badly if all uids in range are used.
class PosixUserNoturMixin(PosixUser.PosixUser):
    #Gah! BDB uses 50001-53000 inclusive.
    #But others may believe 50000-52999 inclusive.
    #Be safe.
    minuid = 50001
    maxuid = 52999
    #Autogenerate uids outside those currently used by BDB, Check!
    minfreeuid = 51500
    maxfreeuid = 52999
    
    def get_free_uid(self):
        uid=self.__super.get_free_uid()
        if uid<self.minfreeuid or uid>self.maxfreeuid:
            # We're resetting the sequence ourselves. Ugly!
            # Postgres-spesific!
            self.execute("""ALTER SEQUENCE posix_uid_seq
            MINVALUE :min MAXVALUE :max
            RESTART :min INCREMENT 1""",
                         {'min': self.minfreeuid,
                          'max': self.maxfreeuid})
            uid=self.__super.get_free_uid()
            if uid<=self.minfreeuid or uid>=self.maxfreeuid:
                raise UidRangeException(
                    "Uid out of range: Please reset posix_uid_seq to %d" %
                    minfreeuid)
        return uid

    def illegal_uid(self, uid):
        # All uids outside NOTUR range is disallowed, also when set manually.
        if uid<self.minuid or uid>self.maxuid:
            return "Uid (%d) of of NOTUR range." % uid
        # self.__super.illegal_uid(uid)

    def write_db(self):
        tmp=self.illegal_uid(self.posix_uid)
        if tmp:
            raise self._db.IntegrityError, "Illegal Posix UID: %s" % tmp
        self.__super.write_db()

# arch-tag: 174b9c44-dac9-11da-91a8-0e10df6ad6e9

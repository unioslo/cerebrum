
from Cerebrum.modules import PosixUser

class UidRangeException(Exception):
    """Exception raissed for Uids out of legal range"""
    pass


# This probably behaves badly if all uids in range are used.
class PosixUserNoturMixin(PosixUser.PosixUser):
    minfreeuid = 50000
    maxfreeuid = 53000
    def get_free_uid(self):
        uid=self.__super.get_free_uid()
        if (uid<=self.minfreeuid or uid>=self.maxfreeuid):
            # We're resetting the sequence ourselves. Ugly!
            # Postgres-spesific!
            self.execute("""ALTER SEQUENCE posix_uid_seq
            MINVALUE :min MAXVALUE :max
            RESTART :min INCREMENT 1""",
                         {'min': self.minfreeuid,
                          'max': self.maxfreeuid})
            uid=self.__super.get_free_uid()
            if (uid<=self.minfreeuid or uid>=self.maxfreeuid):
                raise UidRangeException(
                    "Uid out of range: Please reset posix_uid_seq to %d" %
                    minfreeuid)
        return uid

# arch-tag: 174b9c44-dac9-11da-91a8-0e10df6ad6e9

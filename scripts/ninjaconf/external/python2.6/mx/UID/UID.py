""" mx.UID -- A UID datatype.

    Relies on mx.DateTime.

    Copyright (c) 1998-2000, Marc-Andre Lemburg; mailto:mal@lemburg.com
    Copyright (c) 2000-2008, eGenix.com Software GmbH; mailto:info@egenix.com
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

"""
import string, mimetypes
try:
    import hashlib
except ImportError:
    import md5 as hashlib
from mx import DateTime

#
# Import the C extension module
#
from mxUID import *
from mxUID import __version__

### Helpers

def mangle(uid, key,

           md5=hashlib.md5,otp=otp):

    """ Mangle the UID string uid using the given key string.

        The output has the same length as the input UID string and
        should make it hard to forge valid UIDs without knowledge of
        the key string.

        Note that the output string is not a valid UID string in
        itself, i.e. it most likely won't verify().

    """
    # Idea: Even if somebody finds the akey which allows decoding
    # the timestamp, it should not be possible to use it to extract
    # the key or the bkey from it.
    akey = md5(key).digest()
    bkey = md5(uid[:16] + key).digest()
    # Add a little noise to please the eye (except to the counter part)
    # and apply the encoding pad
    ckey = 'ffff' + uid[:4] * 7
    return otp(otp(uid, ckey), akey + bkey * 2)

def demangle(muid, key,

             md5=hashlib.md5,otp=otp):

    """ Demangle a mangle()d UID string muid using the given key
        string.

    """
    akey = md5(key).digest()
    # First decode the counter and the noisy timestamp part
    tuid = otp(muid[:16], akey)
    # Next denoise the timestamp part to build the bkey
    ckey = 'ffff' + tuid[:4] * 7
    bkey = md5(otp(tuid, ckey) + key).digest()
    # Decode and denoise the UID
    return otp(otp(muid, akey + bkey * 2), ckey)

# Override the function provided by mxUID with one using DateTime
# instances:
timestamp_ticks = timestamp
def timestamp(uid,

              DateTimeFromTicks=DateTime.DateTimeFromTicks,
              timestamp=timestamp_ticks):

    """ Returns the timestamp encoded in the UID string uid
        as DateTime instance.
    """
    return DateTimeFromTicks(timestamp(uid))

###

#
# Experimental Python wrapper around UID strings.
#

class ID:

    """ ID class for creating unique IDs.

        The generated IDs are unique to the host, process and time
        with high probabilty. In addition their validity can be
        verified (using a CRC type algorithm).

        The algorithm uses a 40-bit timestamp in the ID which can be
        extracted using the .timestamp() method. Accuracy is one second.

    """
    # ID value
    uid = None 

    def __init__(self,target=None,code='',timestamp=None):

        """ Construct a new uid for the object target.

            target defaults to the singleton None.

            code is an optional addition to the uid that can later be
            used to verify the validity of the uid together with the
            UID's CRC value.

            timestamp may be given as DateTime instance. It defaults
            to the current local time.

        """
        if timestamp:
            self.uid = UID(target,code,timestamp)
        else:
            self.uid = UID(target,code)

    def timestamp(self,

                  DateTimeFromTicks=DateTime.DateTimeFromTicks,
                  timestamp=timestamp):

        """ Returns the timestamp encoded in the ID
            as DateTime instance.
        """
        return DateTimeFromTicks(timestamp(self.uid))

    def set_uid(self,uid,code='',

               verify=verify):

        # Check validity
        if not verify(uid,code):
            raise Error,'invalid UID'

        self.uid = uid

    def __str__(self):

        return self.uid

    def __cmp__(self,other,

                cmp=cmp):

        return cmp(self.uid,other.uid)

    def __hash__(self,

                 hash=hash):

        return hash(self.uid)

# Helper class
class _EmptyClass:
    pass

### Other constructors

def IDFromUID(s,code=''):

    """ Create an ID object from the given string UID.

        This can raise an Error in case the string does not map to a
        valid UID. code is used in the verification process if given.

    """
    id = _EmptyClass()
    id.__class__ = ID
    id.set_uid(s,code)
    return id

if __name__ == '__main__':
    uid = UID()
    print uid,' timestamp =',timestamp(uid)
    print verify(uid) * 'OK' or 'NOT OK'

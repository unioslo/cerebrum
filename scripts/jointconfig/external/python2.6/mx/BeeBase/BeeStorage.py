# -*- coding: latin-1 -*-

""" BeeStorage - Flatfile data storage facility.

    Definitions:
    
      block: minimal amount of storage allocated in the file
      record: Header + content + padding

    Copyright (c) 1998-2000, Marc-Andre Lemburg; mailto:mal@lemburg.com
    Copyright (c) 2000-2008, eGenix.com Software GmbH; mailto:info@egenix.com
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

"""
import cPickle,cStringIO,struct,exceptions,types,sys,marshal,string,re
import FileLock,Cache
from mx import Tools
freeze=Tools.freeze
from mx.Log import *

# Blocksize used to improve alignment of records (NOTE: Don't change this
# parameter, or the implementation will corrupt any existing storage file
# using a different block size !!!
BLOCKSIZE = 32

# Default minimal record size (must be multiple of BLOCKSIZE)
MINRECORDSIZE = BLOCKSIZE

# File header size to allocate. This should be large enough to
# hold data for future enhancements.
FILEHEADERSIZE = 1024

# Start of data according to the storage layout
STARTOFDATA = FILEHEADERSIZE + BLOCKSIZE

# Cache management (only used if caches are enabled)
MAXCACHESIZE = 1000
CACHELIMIT = 1000

# Codes
ID      = '\333'
VALID   = '\370'
OLD     = '\373'

# Special markers; these are written to the first block after the
# fileheader (position FILEHEADERSIZE) and must have equal size
COLD_MARKER =   '*cold***'
HOT_MARKER =    '*hot****'

# States
HOT = 1
COLD = 0

# Output debugging info
_debug = 0

### Errors

class Error(exceptions.StandardError):

    """ Baseclass for Errors related to this module.
    """
    pass

class RunRecoveryError(Error):

    """ Error raised in case the storage file is damaged and recovery
        could be possible.
    """
    pass

### Classes

def dummy_callback(old_position,new_position,raw_data):

    """ This callback is used by the .collect() method to
        inform an object using the storage facility of a change
        in record layout.

        raw_data contains the raw data contents of the record.
        Use storage.decode() to decode it.
    """
    return
        
class BeeStorage:

    """ Baseclass for flatfile data storage facilities.

        This class implements a simple database which can store and
        restore objects. The database is designed to be easily
        reconstructable in case something goes terribly wrong.

        File layout:

        · [Fileheader] (length FILEHEADERSIZE)
        · [Marker block] (length BLOCKSIZE)
        · STARTOFDATA: ...[datablock] (length mulitple of BLOCKSIZE)...

        Datablocks layout:
        
        · [ID] (1 byte)
        · [length of whole block] (4 bytes, little endian)
        · [CODE] (1 bytes)
        · [raw data]
        
        XXX Todo:

        * Implement write cache.
        * Add more recovery tools
    
    """
    version = '1.2'                     # Version number; increase whenever
                                        # the internal layout changes

    filename = None                     # Filename of the file used
    file = None                         # Open file
    EOF = 0                             # EOF address
    filelock = None                     # BeeStorageLock instance in case
                                        # locking is enabled
    min_recordsize = MINRECORDSIZE      # Minimal record size
    caching = 0                         # Is caching enabled ?
    readonly = 0                        # Operate in read-only mode ?
    state = None                        # State in which the file is in
    is_new = 0                          # Was the file created by the
                                        # constructor, or just reopened ?
    
    # Caches
    header_cache = None
    record_cache = None

    def __init__(self,filename,lock=0,cache=0,min_recordsize=MINRECORDSIZE,
                 readonly=0,recover=0):

        """ Create an instance using filename as data file.
        
            If lock is true, a filelock will be enabled until the file
            is closed. cache controls whether to enable a cache or not
            (should only be used where OS level caches are not
            available).

            min_recordsize can be set to have all records be padded to
            at least this size (might reduce overhead due to
            reallocation of records that have become too small for
            updates).

            readonly can be set to true to have existing files opened
            in read-only mode. Writes will then cause an IOError,
            opening a non-existing file in read-only mode will too.

            Opening the storage file in recover mode will disable some
            of the checks normally done. This flag should only be used
            if a previous normal opening failed with a hint to run
            recovery.

        """#'

        self.readonly = readonly

        if _debug:
            log.call(SYSTEM_DEBUG)

        # Adjust min_recordsize
        if min_recordsize < MINRECORDSIZE:
            min_recordsize = MINRECORDSIZE
        if min_recordsize % BLOCKSIZE != 0:
            min_recordsize = (min_recordsize / BLOCKSIZE + 1) * BLOCKSIZE
        self.min_recordsize = min_recordsize
        
        # Lock the file
        if lock:
            self.filelock = filelock = FileLock.FileLock(filename)
            # This may raise a FileLock.Error
            if recover:
                try:
                    filelock.lock()
                except FileLock.Error:
                    filelock.remove_lock()
                    filelock.lock()
            else:
                filelock.lock()
            
        # Open it:
        #  first try for an existing file, then revert to creating a new one
        if readonly:
            mode = 'rb'
        else:
            mode = 'r+b'
        self.filename = filename
        try:
            # Existing file
            self.file = file = open(filename,mode)
            file.seek(0,2)
            self.EOF = EOF = file.tell()

        except IOError,why:
            if readonly:
                raise IOError,why
            # New file: write header and state marker
            if _debug:
                log(SYSTEM_INFO,'Creating a new storage file %s' % filename)
            self.file = file = open(filename,'w+b')
            self.write_fileheader(file)
            self.mark(COLD)
            EOF = file.tell()
            if EOF % BLOCKSIZE != 0:
                # pad to block boundary
                file.write(' '*(BLOCKSIZE - EOF % BLOCKSIZE))
                EOF = file.tell()
            self.EOF = EOF
            self.is_new = 1

        else:
            self.is_new = 0
            
        # Create caches
        if cache:
            self.caching = 1
            self.header_cache = header_cache = Cache.Cache(MAXCACHESIZE)
            self.record_cache = record_cache = Cache.Cache(MAXCACHESIZE,
                                                           CACHELIMIT)
            self.caches = [header_cache,record_cache]

        # Sanity check
        if EOF % BLOCKSIZE != 0 and not recover:
            raise RunRecoveryError,\
                  'storage file is damaged; run recovery ! (EOF=%i)' % EOF

        # Check mark
        file.seek(FILEHEADERSIZE)
        marker = file.read(len(COLD_MARKER))
        if marker != COLD_MARKER and \
           not (readonly and marker == HOT_MARKER) and \
           not recover:
            raise RunRecoveryError,\
                  'storage file is damaged; run recovery ! (marker=%s)' % \
                  repr(marker)

        # Set state to COLD
        self.state = COLD

        # Header check
        self.check_fileheader(file)

    def mark(self,state=HOT,

             HOT=HOT,HOT_MARKER=HOT_MARKER,COLD_MARKER=COLD_MARKER,
             FILEHEADERSIZE=FILEHEADERSIZE):

        """ Change the state of the storage file.

            The state indicates whether the file has changed in
            a way that needs proper shutdown (HOT). An unchanged
            or stable file should be marked COLD.

            This is an internal interface, use .start/end_transaction()
            for externally setting the state.

        """
        if self.state == state:
            return
        if self.readonly:
            raise Error,'storage is read-only'
        if _debug:
            log(SYSTEM_DEBUG,
                'Marking the file "%s": %s',
                self.filename,((state==HOT)*'HOT' or 'COLD'))
        self.file.seek(FILEHEADERSIZE)
        if state == HOT:
            self.file.write(HOT_MARKER)
        else:
            self.file.write(COLD_MARKER)
        self.state = state

    def recover(self,callback=dummy_callback):

        """ Run recovery.

            callback is a call back function that will be called for
            every valid record and has the same signature as the one
            used for .collect().

            To open a storage file in recovery mode, pass the keyword
            'recover=1' to the constructor.
            
        """
        self.collect(callback,recover=1)

    def start_transaction(self,

                          HOT=HOT):

        """ Start a sequence of storage manipulation commands.

            Note that every write/free command automatically starts
            a transaction sequence.
        """
        self.mark(HOT)

    def end_transaction(self,

                        COLD=COLD):

        """ End a sequence of storage manipulation commands.
        """
        self.mark(COLD)

    def write_fileheader(self,file):

        """ Write a new header to the open file.

            Changes the file's position: moves the file's position to
            the start of the data area.
            
        """
        # The fileheader (also see header_check below):
        fileheader = ('%s version %s\n'
                      'blocksize %i\n' % (self.__class__.__name__,
                                          self.version,
                                          BLOCKSIZE))
        # Pad to FILEHEADERSIZE bytes length
        fileheader = fileheader + \
                     ' '*(FILEHEADERSIZE - len(fileheader) - 1) + '\n'

        # Make sure we start on a block boundary
        if FILEHEADERSIZE % BLOCKSIZE != 0:
            fileheader = fileheader + '\0' * \
                         ((FILEHEADERSIZE / BLOCKSIZE + 1) * BLOCKSIZE \
                          - FILEHEADERSIZE)
        file.seek(0)
        file.write(fileheader)

    header_check = re.compile(('(\w+) version ([\w.]+)\n'
                               'blocksize (\d+)\n'))
    
    def check_fileheader(self,file):

        """ Checks the file header and verifies that all parameters are
            the same.

            Changes the file's position.
        """
        file.seek(0)
        fileheader = file.read(FILEHEADERSIZE)
        if len(fileheader) != FILEHEADERSIZE:
            raise Error,'header is damaged: "%s"' % fileheader
        m = self.header_check.match(fileheader)
        if m is None:
            raise Error,'wrong header format: "%s"' % fileheader
        name,version,blocksize = m.groups()
        if name != self.__class__.__name__:
            raise Error,'wrong storage class: %s (expected %s)' % \
                  (name,self.__class__.__name__)
        if version > self.version:
            raise Error,'wrong version: %s (expected %s)' % \
                  (version,self.version)
        if string.atoi(blocksize) != BLOCKSIZE:
            raise Error,'blocksize mismatch: %s (expected %i)'  % \
                  (blocksize,BLOCKSIZE)

    def encode(self,object,

               StringType=types.StringType,type=type):

        """ Encode an object giving a string.

            Since the records are usually larger than the data size,
            it is important to store the string length or at least
            mark the end of data in some way.

            This method must be overloaded in order to implement
            an encoding schemes.
        """
        raise Error,'.encode() needs to be overridden'

    def decode(self,data):

        """ Decode a string giving an object.

            The data string may well be larger than the string
            returned by the .encode method. This method will have to
            determine the true length on its own.

            This method must be overloaded in order to implement
            an encoding scheme.
        """
        raise Error,'.decode() needs to be overridden'

    def clear_cache(self):

        """ Clears the caches used (flushing any data not yet
            written).
        """
        if self.caching:
            #self.flush()
            method_mapply(self.caches,'clear',())

    def close(self,

              COLD=COLD,method_mapply=method_mapply):

        """ Flush buffers and close the associated file.
        """
        if self.caching:
            self.flush()
            method_mapply(self.caches,'clear',())
        if self.file:
            # Mark COLD
            if not self.readonly and self.state != COLD:
                self.mark(COLD)
            del self.file
        if self.filelock:
            self.filelock.unlock()
            del self.filelock

    def __del__(self):

        if _debug:
            log(SYSTEM_DEBUG,'del %s',self)
        if self.file:
            self.close()

    def flush(self):

        """ Flush all buffers.
        """
        return

    def __repr__(self):

        return '<%s instance for "%s" at 0x%x>' % (self.__class__.__name__,
                                                   self.filename,
                                                   id(self))

    def read_header(self,position,

                    unpack=struct.unpack,BLOCKSIZE=BLOCKSIZE,
                    ID=ID,headertypes=(OLD,VALID)):

        """ Read the header located at position and return
            a tuple (record size, statebyte, data area size).
            
            statebyte is one of the state constants. record size
            is the total number of bytes reserved for the record,
            data area size the number of bytes in its data area.

            self.file is positioned to point to the records data area.

            May raise errors if the position is invalid.

        """
        if self.caching:
            header = self.header_cache.get(position,None)
            if header is not None:
                self.file.seek(position+6)
                return header

        # Sanity check
        if position % BLOCKSIZE != 0 or \
           position > self.EOF:
            raise Error,'invalid position: %i' % position

        # Read and check header
        file = self.file
        file.seek(position)
        header = file.read(6)
        if not header:
            raise EOFError,'position %i is beyond EOF' % position
        if header[0] != ID or header[5] not in headertypes:
            raise Error,'invalid header at %i: %s' % \
                        (position,repr(header))
        recordsize = unpack('<l',header[1:5])[0]

        header = (recordsize, header[5], recordsize - 6)
        if self.caching:
            self.header_cache.put(position,header)
        return header

    def write_header(self,position,recordsize,rtype=VALID,

                     pack=struct.pack,
                     join=string.join,ID=ID,HOT=HOT):

        """ Write a plain header to position.

            The header will mark the record as being of size recordsize
            and having rtype. No data part is written; the file pointer is
            positioned to the start of the data part.

            The header cache is updated, yet marking the file as HOT
            is *not* done. Sanity checks are not performed either.

            This method is intended for internal use only.

        """
        file = self.file
        file.seek(position)
        file.write(join((ID,pack('<l',recordsize),rtype),''))
        
        if self.caching:
            self.header_cache.put(position,(recordsize,rtype,recordsize-6))

    def write_record(self,data,position,minsize=0,rtype=VALID,

                     BLOCKSIZE=BLOCKSIZE,pack=struct.pack,
                     join=string.join,ID=ID,HOT=HOT):

        """ Write a record of given rtype (defaults to VALID)
            containing data to position.

            data is not encoded; caches are not used.  position may be
            EOF in which case the data is appended to the storage file
            (with proper padding). minsize can be set to a value
            greater than len(data) to have the allocation mechanism
            reserve more space for data in the record.
            
        """
        file = self.file
        EOF = self.EOF
        datalen = len(data)
        if minsize and datalen < minsize:
            datalen = minsize

        # Mark HOT
        if self.state != HOT:
            self.mark(HOT)

        # Record is to be updated
        if position < EOF:
            recordsize,rtype,datasize = self.read_header(position)
            if datasize < datalen:
                # Drop old record
                if rtype == VALID:
                    if _debug:
                        log(SYSTEM_INFO,
                            'Could not update %i record in place: '
                            'old size = %i, datalen = %i, data = %s',
                            position,datasize,datalen,data)
                    self.free(position)
                # revert to appending...
                position = EOF
            else:
                # Write new data
                file.write(data)
                if _debug:
                    log(SYSTEM_INFO,'Data written to position %i: %s',
                        position,data)
                return position

        # Record is to be appended
        recordsize = datalen + 6
        if recordsize < self.min_recordsize:
            recordsize = self.min_recordsize
        if recordsize % BLOCKSIZE != 0:
            recordsize = (recordsize / BLOCKSIZE + 1) * BLOCKSIZE

        # Write the header + data + padding
        file.seek(position)
        file.write(join((ID,pack('<l',recordsize),rtype,        # Header
                         data,                                  # Data
                         '\0' * (recordsize - 6 - datalen)      # Padding
                         ),''))
        if self.caching:
            self.header_cache.put(position,(recordsize,rtype,recordsize-6))

        # Update EOF
        self.EOF = file.tell()
        if _debug:
            log(SYSTEM_DEBUG,'New EOF = %i',self.EOF)
            log(SYSTEM_DEBUG,'Data written to position %i: %s',
                position,data)

        return position

    def read_record(self,position,rtype=VALID):

        """ Read the raw data from record position having the given
            rtype (defaults to VALID).

            An error is raised in case the record does not have the
            correct rtype or is not found.  The data is not decoded;
            caches are not used.
            
        """
        file = self.file
        recordsize,rt,datasize = read_header(position)
        if rtype != rt:
            raise Error,'record has wrong type'
        
        # Read the record
        return file.read(datasize)

    def free(self,position,

             OLD=OLD,HOT=HOT):

        """ Deletes an already written record by marking it OLD.

            The next garbage collection will make the change permanent
            and free the occupied space.

        """
        if self.state != HOT:
            self.mark(HOT)
        file = self.file
        file.seek(position + 5)
        file.write(OLD)

        if self.caching:
            method_mapply(self.caches,'delete',(position,))

    # Aliases
    delete = free
    __delitem__ = free

    def write(self,obj,position=None):

        """ Write the encoded object to the file and
            return the file address where the data was written.

            If position is given or None, the object is assumed to be
            replacing an old data record. The implementation tries to
            use the old record for writing the new data. In case it
            doesn't fit the old record is marked OLD and another
            record is used.  The return value will be different from
            the passed position in the latter case.

            Note: Records that are marked OLD will be collected by the
            next run of the garbage collection.
            
        """
        data = self.encode(obj)

        if position is None:
            position = self.EOF
        position = self.write_record(data,position)

        if self.caching:
            self.record_cache.put(position,data)

        return position

    # Aliases
    append = write
    add = write

    def __setitem__(self,position,obj):

        self.write(obj,position)

    def read(self,position,

             NotCached=Cache.NotCached):

        """ Load an object from the file at the given position.
        """
        if self.caching:
            data = self.record_cache.get(position,NotCached)
            if data is not NotCached:
                return self.decode(data)

        file = self.file
        recordsize,rtype,datasize = self.read_header(position)
        data = file.read(datasize)

        if self.caching:
            self.record_cache.put(position,data)

        return self.decode(data)

    # Alias
    __getitem__ = read
        
    def find_records(self,start=STARTOFDATA,stop=sys.maxint):

        """ Scans the data file for valid, old and invalid records and
            returns a list of positions to these records.

            start and end can be given to narrow down the search
            space.
            
        """
        EOF = self.EOF
        if start < STARTOFDATA:
            start = STARTOFDATA
        if stop > EOF:
            stop = EOF
        position = start
        valid = []
        invalid = []
        old = []
        read_header = self.read_header
        old_append = old.append
        valid_append = valid.append
        invalid_append = invalid.append
        # Adjust position to next block boundary
        if position % BLOCKSIZE != 0:
            position = (position / BLOCKSIZE + 1) * BLOCKSIZE

        while position < stop:
            try:
                recordsize,rtype,datasize = read_header(position)
            except Error:
                # No record found at that position: try next block
                position = position + BLOCKSIZE
                invalid_append((position,BLOCKSIZE))
                continue
            if rtype == VALID:
                valid_append((position,recordsize))
            elif rtype == OLD:
                old_append((position,recordsize))
            position = position + recordsize

        return valid,old,invalid

    def statistics(self):

        """ Scans the data file for valid, old and invalid records and
            returns a tuple valid, old, invalid indicating the number
            of bytes for each class of records/blocks.
        """
        position = STARTOFDATA
        EOF = self.EOF
        valid = 0
        invalid = 0
        old = 0
        read_header = self.read_header
        while position < EOF:
            try:
                recordsize,rtype,datasize = read_header(position)
            except Error:
                # No record found at that position: try next block
                position = position + BLOCKSIZE
                invalid = invalid + BLOCKSIZE
                continue
            if rtype == VALID:
                valid = valid + recordsize
            elif rtype == OLD:
                old = old + recordsize
            position = position + recordsize

        return valid,old,invalid

    def collect(self,callback=dummy_callback,recover=0):

        """ Collect garbage that accumulated since the last .collect()
            run.

            Garbage is collected by moving all VALID records to the
            beginning of the file and then truncating it to the new
            (reduced) size.

            Collecting will be done without using the cache. It also
            starts a new transaction (if not already marked HOT).

            For every move operation the callback is called with arguments
            (old_position,new_position,raw_data). raw_data is the raw
            data stored in the record that is being moved; use .decode[_key]
            to decode it.

            If recover is true, the callback is called for all valid
            records, not just the ones that are actually being moved.

        """
        file = self.file
        if recover:
            # Don't trust self.EOF in recover mode
            file.seek(0,2)
            EOF = file.tell()
            if EOF % BLOCKSIZE != 0:
                # Pad file with \0 bytes
                padsize = BLOCKSIZE - EOF % BLOCKSIZE
                file.write('\0' * padsize)
                EOF = EOF + padsize
        else:
            EOF = self.EOF
        read_header = self.read_header
        source = dest = STARTOFDATA

        # Temporarily disable caching
        caching = self.caching
        if caching:
            self.clear_cache()
            self.caching = 0

        # Mark HOT
        if self.state != HOT:
            self.mark(HOT)

        # First align all VALID records to the "left"
        while source < EOF:
            try:
                recordsize,rtype,datasize = read_header(source)
            except Error:
                # Unallocated space: skip
                source = source + BLOCKSIZE
                if not recover:
                    log(SYSTEM_WARNING,
                        'Skipping unallocated/misaligned block at %i',source)
                continue

            if rtype == VALID:
                if source != dest:
                    # Move record (informing caller via callback)
                    file.seek(source)
                    record = file.read(recordsize)
                    file.seek(dest)
                    file.write(record)
                    callback(source,dest,record[6:])
                elif recover:
                    # Inform caller of all valid records found
                    file.seek(source)
                    record = file.read(recordsize)
                    callback(source,dest,record[6:])
                dest = dest + recordsize

            elif rtype == OLD:
                # Skip record
                pass
            
            # Process next record
            source = source + recordsize

        # Everything behind dest is now considered free space
        try:
            file.truncate(dest)
        except AttributeError:
            # Truncate is not supported: clear out the remaining
            # space to make it invalid and continue processing as if
            # the file were truncated.
            file.seek(dest)
            while dest < EOF:
                file.write('\0'*BLOCKSIZE)
                dest = dest + BLOCKSIZE
        EOF = dest
        if EOF % BLOCKSIZE != 0:
            if recover:
                # In recover mode we simply pad the file to align
                # the file's end to BLOCKSIZE
                file.seek(EOF)
                padsize = BLOCKSIZE - EOF % BLOCKSIZE
                file.write('\0' * padsize)
                EOF = EOF + padsize
            else:
                raise Error,'EOF malaligned after collect()'
        self.EOF = EOF
            
        # Reenable caching
        if caching:
            self.caching = 1

    def backup(self,archive=None,buffersize=8192):

        """ Issues a backup request using archiveext as filename
            extension.

            The archive file is a simple copy of the current storage
            file. If no name is given self.filename + '.backup' is
            used.

            buffersize gives the size of the buffer used for copying
            the file.

        """
        if not archive:
            archive = self.filename + '.backup'
        archfile = open(archive,'wb')

        # Mark HOT
        if self.state != HOT:
            self.mark(HOT)

        # Copy the file
        file = self.file
        file.seek(0)
        while 1:
            buffer = file.read(buffersize)
            if not buffer:
                break
            archfile.write(buffer)
        archfile.close()

###

class PickleMixin:

    """ Pickle encoding.

        Uses binary pickles.
    """
    def encode(self,object,

               dumps=cPickle.dumps):

        """ Encode an object giving a string.

            This method can be overloaded in order to implement
            other encoding schemes.
        """
        return dumps(object,1)

    def decode(self,object,

               loads=cPickle.loads):

        """ Decode a string giving an object.

            This method can be overloaded in order to implement
            other encoding schemes.
        """
        return loads(object)

class BeePickleStorage(PickleMixin,BeeStorage):

    """ Flatfile data storage facility for pickleable objects.
    """
    
freeze(BeePickleStorage)

###

class MarshalMixin:

    """ Marshal encoding.
    """

    def encode(self,object,

               dumps=marshal.dumps):

        """ Encode an object giving a string.

            This method can be overloaded in order to implement
            other encoding schemes.
        """
        return dumps(object)

    def decode(self,object,

               loads=marshal.loads):

        """ Decode a string giving an object.

            This method can be overloaded in order to implement
            other encoding schemes.
        """
        return loads(object)

class BeeMarshalStorage(MarshalMixin,BeeStorage):

    """ Flatfile data storage facility for marshallable objects.
    """

freeze(BeeMarshalStorage)

###

class BeeKeyValueStorage(BeeStorage):

    """ Flatfile storage for key,value pairs.

        keys and values must be pickleable object.

        The main difference between this class and the base class
        is that keys are readable separately from the values, e.g.
        values can be multi-MB big and are only read if this is really
        requested.

        NOTE: The .en/decode methods are NOT used. Uses binary
        pickles.

    """
    key_cache = None

    def __init__(self,*args,**kws):

        apply(BeeStorage.__init__,(self,)+args,kws)
        if self.caching:
            self.key_cache = key_cache = Cache.Cache(MAXCACHESIZE,CACHELIMIT)
            self.caches.append(key_cache)

    def write(self,key,value,position=None,

              dumps=cPickle.dumps):

        """ Write key and value to position. Returns the position under
            which the record was stored.

            If position is None, the implementation chooses a new
            one.
        """
        # Pack key and value into two separate pickles
        data = dumps(key,1) + dumps(value,1)

        # Write the record
        if position is None:
            position = self.EOF
        position = self.write_record(data,position)

        if self.caching:
            self.record_cache.put(position,data)
            self.key_cache.put(position,key)

        return position

    # Aliases
    append = write
    add = write

    def decode_key(self,raw_data,

                   loads=cPickle.loads):

        """ Decode the key part of a raw data record field.
        """
        return loads(raw_data)

    def read_key(self,position,

                 load=cPickle.load,NotCached=Cache.NotCached):

        """ Load the key part of an object from the file at the given
            position.
        """
        if self.caching:
            key = self.key_cache.get(position,NotCached)
            if key is not NotCached:
                return key

        # Position file reader and only read the key part
        self.read_header(position)
        key = load(self.file)

        if self.caching:
            self.key_cache.put(position,key)

        return key
        
    def read(self,position,

             load=cPickle.load,StringIO=cStringIO.StringIO,
             NotCached=Cache.NotCached):

        """ Load an object from the file at the given position and
            return it as tuple (key,value).
        """
        if self.caching:
            record = self.record_cache.get(position,NotCached)
            if record is not NotCached:
                file = StringIO(record)
                key = load(file)
                data = load(file)
                return key,data

        # Read the header and position the file over the data area
        recordsize,rtype,datasize = self.read_header(position)

        if self.caching:
            record = file.read(datasize)
            file = StringIO(record)
            key = load(file)
            data = load(file)
            self.record_cache.put(position,record)
            self.key_cache.put(position,key)
        else:
            file = self.file
            key = load(file)
            data = load(file)

        return key,data

    # Alias
    __getitem__ = read
        
    def read_value(self,position):

        """ Load the value part of an object from the file at the given
            position.
        """
        return self.read(position)[1]
        
freeze(BeeKeyValueStorage)

### tests

if __name__ == '__main__':

    f = BeePickleStorage('test-BeePickleStorage.dat',cache=1,lock=1)
    l = [1,'blabla','Hi there',2.3434,4+7j] + range(1000)
    k = map(f.write,l)
    m = map(f.read,k)
    if l != m:
        print 'BeePickleStorage:\n'
        print 'Results differ:'
        print 'orig:',l
        print 'rest:',m
    else:
        print 'BeePickleStorage works.'
    valid,old,invalid = f.find_records()
    print ' %i valid records, %i old, %i invalid' % (len(valid),len(old),len(invalid))
    print ' r cache hits:',f.record_cache.hits,' misses:',f.record_cache.misses
    print ' h cache hits:',f.header_cache.hits,' misses:',f.header_cache.misses
    
    print ' rewrite...'
    l = [1,'blabla','Hi there',2.3434,4+7j] + ['x'*100] * 1000
    k = map(lambda value,oldpos: f.write(value,oldpos),l,k)
    m = map(f.read,k)
    if l != m:
        print ' Results differ:'
        print '  orig:',l
        print '  rest:',m
    valid,old,invalid = f.find_records()
    print ' %i valid records, %i old, %i invalid' % (len(valid),len(old),len(invalid))
    print ' r cache hits:',f.record_cache.hits,' misses:',f.record_cache.misses
    print ' h cache hits:',f.header_cache.hits,' misses:',f.header_cache.misses

    print ' collect...'
    def callback(old,new,data,k=k):
        index = k.index(old)
        k[index] = new
    f.collect(callback)
    m = map(f.read,k)
    if l != m:
        print ' Results differ:'
        print '  orig:',l
        print '  rest:',m
    valid,old,invalid = f.find_records()
    print ' %i valid records, %i old, %i invalid' % (len(valid),len(old),len(invalid))
    print ' r cache hits:',f.record_cache.hits,' misses:',f.record_cache.misses
    print ' h cache hits:',f.header_cache.hits,' misses:',f.header_cache.misses

    print

    g = BeeKeyValueStorage('test-BeeKeyValueStorage.dat',cache=1)
    d = {}
    for i in range(256):
        d[str(i)] = 'As char: %s, as number: %i, octal: %s' %\
                    (repr(chr(i)),i,oct(i))
    l = []
    for k,v in d.items():
        l.append(g.write(k,v))
    for addr in l:
        k,v = g.read(addr)
        if d[k] != v:
            print 'BeeKeyValueStorage:\n'
            print 'Mismatch for "%s": "%s"' % (k,v)
    print 'BeeKeyValueStorage works.'
    valid,old,invalid = g.find_records()
    print ' %i valid records, %i old, %i invalid' % (len(valid),len(old),len(invalid))
    print ' r cache hits:',g.record_cache.hits,' misses:',g.record_cache.misses
    print ' h cache hits:',g.header_cache.hits,' misses:',g.header_cache.misses
    print

    del f,g
    

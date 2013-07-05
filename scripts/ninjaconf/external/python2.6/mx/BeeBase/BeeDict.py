""" BeeDict - On-disk dictionary like databases


"""
import exceptions, os
import BeeIndex,BeeStorage
from mx import Tools
freeze = Tools.freeze
from mx.Log import *

#import TraceCalls; TraceCalls.install()
#log.setup(ignore_level=SYSTEM_LOG_EVERYTHING)

### Constants

# Special keys
FirstKey = BeeIndex.FirstKey
LastKey = BeeIndex.LastKey

# Maximal cache size default value ( == size of transaction log; kept in memory !)
MAXCACHESIZE = 1000

### Errors

class Error(exceptions.StandardError):
    pass

class IndexError(Error):
    
    """ This error is raised for index related errors.
        
    """
    pass

class RecreateIndexError(IndexError):
    
    """ This error is raised in case the index for a dictionary was
        not found and/or needs to be recreated by running recovery.
    """
    pass

class RecoverError(Error):
    
    """ This error is raised in case the storage for a dictionary was
        found to be in an inconsistent state.
    """
    pass

### Base classes

# State constants
READ = 0
MODIFIED = 1
DELETED = 2
READKEYONLY = 3 # XXX Currently not used.

class BeeBaseDict:

    """ Base class that collects some method that all dicts can usually
        share without modification.

        The base class implements a transaction based caching
        mechanism.  The cache stores data in the form
        key:(state,value) where state is:

        * READ for read but not yet modified
        * MODIFIED for added/modified
        * DELETED for deleted
        * READKEYONLY for key read, value still on disk

        The .commit method has to implement the needed disk mechanism
        to write the cache data to disk storage.
        
    """
    name = 'NoName'                             # Name of the dict
    index = None                                # Index object
    storage = None                              # Storage object
    closed = 0                                  # Are we closed ?
    cache = None                                # Cache dict
    readonly = 0                                # Are we read-only ?
    autocommit = 0                              # Autocommit ? (this will
                                                # perform a commit whenever
                                                # the cache gets to full)

    # Max. cache size in number of items to store in the in-memory
    # transaction cache
    maxcachesize = MAXCACHESIZE

    # Special keys that can be used for .cursor()
    FirstKey = FirstKey
    LastKey = LastKey

    def __init__(self, name, keysize=8, min_recordsize=0, readonly=0,
                 recover=0, autocommit=0, validate=0,
                 index=BeeIndex.BeeIntegerIndex, maxcachesize=None):

        """ Create an instance using name as basename for the
            data and index files.

            Two files will be created: <name>.dat and <name>.idx.

            keysize gives the maximal size of the key strings used as
            index keys. This is only useful for string based keys.

            min_recordsize is passed to the BeeStorage as indicator of
            the minimum size for data records.

            readonly can be set to true to open the files in read-only
            mode, preventing any disk modifications.

            To open the dictionary in recovery mode, pass a keyword
            recover=1. Then run .recover() and reopen using the normal
            settings.

            If autocommit is true the cache control will do an
            automatic .commit() whenever the transaction log
            overflows.
            
            If validate is true, the dictionary will run a validation
            check after having successfully opened storage and index.
            RecreateIndexError or RecoverError exceptions could be
            raised in case inconsistencies are found.

            index gives the constructor to use for the .index. The
            constructors BeeIntegerIndex and BeeStringIndex from the
            BeeIndex module are supported.

            maxcachesize defines the maximum size of the in-memory
            transaction cache. It defaults to MAXCACHESIZE if not
            given.
            
        """
        # Init instance vars
        self.name = name
        self.cache = {}
        if maxcachesize is not None:
            self.maxcachesize = maxcachesize
        else:
            self.maxcachesize = self.maxcachesize

        # Open storage
        self.storage = BeeStorage.BeeKeyValueStorage(
                                name + '.dat',
                                lock= not readonly,
                                cache=0,
                                min_recordsize=min_recordsize,
                                readonly=readonly,
                                recover=recover)
        
        # Determine the filemode
        if readonly:
            # Readonly mode
            filemode = 1
        else:
            if self.storage.is_new or recover:
                # Create a new file (overwriting a possibly existing one)
                filemode = 2
            else:
                # Open a file, create is non-existent
                filemode = 3
                
        # Open the index
        try:

            # Special argument treatment for the indexes; we check
            # depending on the used constructor function
            if (index is BeeIndex.BeeStringIndex or
                index is BeeIndex.BeeFixedLengthStringIndex):
                # Calculate the right sectorsize
                if keysize <= 30:
                    sectorsize = 256
                elif keysize <= 73:
                    sectorsize = 512
                elif keysize <= 158:
                    sectorsize = 1024
                else:
                    raise IndexError, 'keysize %i is too large' % keysize
                self.index = index(name + '.idx',
                                   keysize,
                                   dupkeys=0,
                                   filemode=filemode,
                                   sectorsize=sectorsize)
                
            elif index is BeeIndex.BeeIntegerIndex:
                # keysize is sizeof(long)
                self.index = index(name + '.idx',
                                   dupkeys=1,
                                   filemode=filemode,
                                   sectorsize=256)

            elif index is BeeIndex.BeeFloatIndex:
                # keysize is sizeof(double)
                self.index = index(name + '.idx',
                                   dupkeys=1,
                                   filemode=filemode,
                                   sectorsize=256)

            else:
                raise IndexError, 'unknown index type: %s' % repr(index)

        except IOError, why:
            # Make sure the storage lock is freed
            self.close()
            raise RecreateIndexError,\
                  'Index for %s "%s" could not be opened' % \
                  (index.__name__, name)
        self.readonly = readonly
        self.autocommit = autocommit
        
        if validate:
            self.validate_index()
            self.validate_storage()

    def _calc_sectorsize(self, keysize):

        """ Calculate the sectorsize given the keysize.
        
        """
        if keysize <= 30:
            return 256
        elif keysize <= 73:
            return 512
        elif keysize <= 158:
            return 1024
        else:
            raise IndexError, 'keysize %i is too large' % keysize

    def remove_files(self):

        """ Deletes the storage and index files used for the instance.

            Closes the on-disk dictionary before proceeding with the
            removal.
        
            USE WITH CARE !

        """
        self.close()
        os.remove(self.name + '.dat')
        os.remove(self.name + '.idx')

    def __len__(self):

        """ This only gives correct results if no modifications
            are pending.
        """
        # Check for uncommitted changes
        if self.cache and self.changed():
            raise Error, 'uncommitted data exists; can\'t calculate length'
        return len(self.index)

    def close(self):

        """ Flush buffers and close.

            This issues a .rollback(), so the current transaction is
            rolled back. It also frees the lock on the used index.
            
        """
        if not self.closed:
            self.rollback()
            for obj in (self.index, self.storage):
                if obj is not None:
                    # .rollback will have flushed the buffers
                    obj.close()
            self.closed = 1

    def __del__(self,

                AttributeError=AttributeError):

        """ Make sure the object is closed and locks are freed.
        
        """
        #print '__del__ %s' % repr(self)
        if not self.closed:
            try:
                self.close()
            except AttributeError:
                # Could occur during interpreter cleanup
                pass

    def flush(self):

        """ Flush buffers to disk.
        """
        if self.closed:
            # Nothing much to do
            return
        if self.storage is not None:
            self.storage.flush()
        if self.index is not None:
            self.index.flush()

    def __repr__(self):

        return '<%s instance for "%s" at 0x%x>' % (self.__class__.__name__,
                                                   self.name,
                                                   id(self))

    def commit(self):

        """ Commit all changes and start a new transaction.

            This method does not implement any write operation, but
            takes care of managing the cache and flushing the storage
            and index buffers.

            You must override this method to have commit have any
            writing effect. The base method must be called after the
            cache has been processed.
            
        """
        # Clear cache
        if self.cache is not None:
            self.cache.clear()
                
        # Flush storage and index
        self.flush()

    def rollback(self):

        """ Take back all changes and start a new transaction.

            Overriding is normally not needed. This method only takes
            care of managing the cache and flushing the storage and
            index buffers.
            
        """
        # Clear cache
        if self.cache is not None:
            self.cache.clear()

        # Flush storage and index
        self.flush()

    def changed(self,

                modified=(MODIFIED,DELETED)):

        """ Return true in case the current transaction includes changes
            to the database, false otherwise.
        """
        if self.cache:
            for key,(state,value) in self.cache.items():
                if state in modified:
                    return 1
        return 0

    def free_cache(self,

                   len=len,unmodified=(READ,READKEYONLY)):

        """ Remove all unmodified entries from the cache.

            If self.autocommit and the cache cleanup did not reduce
            the size below the .maxcachesize limit, a .commit() will be
            executed automatically.

            Otherwise the processing continues. If the cache size hits
            2 * .maxcachesize, a forced .rollback() is done and an
            error raised.
            
        """
        cache = self.cache
        for key,(state,value) in cache.items():
            if state in unmodified:
                del cache[key]
        size = len(cache)
        if size > self.maxcachesize:
            if self.autocommit:
                self.commit()
                return
            log(SYSTEM_ERROR,
                'Cache overflow: %i modified items in cache',size)
            if size > 2 * self.maxcachesize:
                # Force .rollback() and raise an error
                log(SYSTEM_ERROR,
                    'Cache overflow: forced a .rollback()')
                self.rollback()
                raise Error,'cache overflow; last transaction rolled back'

    def read(self,key,checkonly=0):

        """ Read and return the value corresponding to key.

            If checkonly is true, only the availability of a value
            has to be checked.

            Override this method with an implementation that accesses
            the disk.
            
        """
        raise KeyError,'key not found'

    def __setitem__(self,key,value,

                    MODIFIED=MODIFIED):

        """ Save the item in the dictionary.

            Note that it is written to the cache first. Use .commit()
            to make sure it is written to disk.

        """
        self.cache[key] = (MODIFIED, value)
        
    def __getitem__(self,key,

                    validstates=(READ,MODIFIED),len=len,KeyError=KeyError,
                    DELETED=DELETED,READ=READ):

        """ Get an item from the dictionary.

            This first tries to read the item from cache and reverts
            to the disk storage if it is not found.
        """
        try:
            cache = self.cache
            state,value = cache[key]
            if state in validstates:
                return value
        except KeyError:
            pass
        else:
            if state == DELETED:
                raise KeyError,'key deleted'

        # Read from disk
        value = self.read(key)

        # Cache the item
        if len(cache) > self.maxcachesize:
            self.free_cache()
        cache[key] = (READ, value)

        return value

    def __delitem__(self, key,

                    DELETED=DELETED):

        """ Delete an item.

            The item is only marked for deletion. The next .commit()
            will make the action permanent.
        """
        cache = self.cache
        if not cache.has_key(key):
            self.read(key, 1)
        cache[key] = (DELETED, None)

    def has_key(self,key,

                len=len,KeyError=KeyError,DELETED=DELETED,READ=READ):

        """ Check if the dictionary has an item indexed by key.

            Successfully found items are put in the cache for fast
            subsequent access.
        """
        try:
            cache = self.cache
            state,value = cache[key]
            if state == DELETED:
                return 0
            return 1
        except KeyError:
            pass

        # Read from disk
        try:
            value = self.read(key)
        except KeyError:
            return 0

        # Cache the item
        if len(cache) > self.maxcachesize:
            self.free_cache()
        cache[key] = (READ, value)

        return 1

    def get(self,key,default=None,

            len=len,KeyError=KeyError,DELETED=DELETED,READ=READ):

        """ Get item indexed by key from the dictionary or default if
            no such item exists.

            This first tries to read the item from cache and reverts
            to the disk storage if it is not found.

        """
        try:
            cache = self.cache
            state,value = cache[key]
            if state == DELETED:
                return default
            return value
        except KeyError:
            pass

        # Read from disk
        try:
            value = self.read(key)
        except KeyError:
            return default

        # Cache the item
        if len(cache) > self.maxcachesize:
            self.free_cache()
        cache[key] = (READ, value)

        return value

    def cursor(self, key=FirstKey, default=None):

        """ Return a cursor instance for this kind of dictionary.

            If key is given, the cursor is positioned on that key in
            the dictionary. Otherwise, the first entry in the
            dictionary is used which guarantees that all entries are
            scanned.

            In case the key is not found, default is returned instead.
            Note that cursors operate with the data on disk meaning
            that any uncommitted changes will not be seen by the
            cursor.

            Has to be overridden to return a suitable cursor object.
        """
        # Check for uncommitted changes
        if self.cache and self.changed():
            raise Error,'uncommitted data exists'
        # Get the index cursor and create a dict cursor from it
        cursor = self.index.cursor(key,None)
        if cursor is None:
            return default
        return BeeBaseDictCursor(self,cursor)

    def garbage(self):

        """ Determine the amount of garbage in bytes that has accumulated
            in the storage file.

            This amount would be freed if .collect() were run.
        """
        valid,old,invalid = self.storage.statistics()
        return old + invalid

    def collect(self):

        """ Run the storage garbage collector.

            Storage collection can only be done for writeable
            dictionaries and then only if the current transaction does
            not contain any pending changes.

            This can take a while depending on the size of the
            dictionary.

        """
        if self.readonly:
            raise Error,'dict is read-only'
        # Check for uncommitted changes
        if self.cache and self.changed():
            raise Error,'uncommitted data exists'
        self.flush()
        log(SYSTEM_INFO,'Collecting %s',self)
        # Run collector
        self.storage.collect(self.collect_callback)
        # End the storage transaction
        self.storage.end_transaction()

    def collect_callback(self,old_position,new_position,raw_data):

        """ Internal callback used to update the index when
            the storage garbage collector moves a record.

            This method must be overridden to account for the
            different indexing schemes.

        """
        raise Error,'.collect_callback() not implemented'

    def recover(self):

        """ Recover all valid records and recreate the index.
        """
        log(SYSTEM_INFO,'Recovering %s',self)
        # Clear the index
        self.index.clear()
        # Run recovery and recreate the index through the callback
        self.storage.recover(self.recover_callback)
        # End the storage transaction
        self.storage.end_transaction()
        
    def recover_callback(self,old_position,new_position,raw_data):

        """ Internal callback used to update the index when
            the storage recovery collector finds a record.

            old_position is only given as additional information,
            new_position contains the position of the found record.

            This method must be overridden to account for the
            different indexing schemes.

        """
        raise Error,'.recover_callback() not implemented'

    def validate_index(self):

        """ Checks the consistency of the index and raises an
            RecreateIndexError in case the index is found to be
            inconsistent.

            Validation takes places for the data on disk. The in
            memory data is not checked.

        """
        log(SYSTEM_INFO,'Validating index for %s',self)
        if not self.index.validate():
            raise RecreateIndexError,'index is inconsistent'

    def validate_storage(self):

        """ Checks the consistency of the storage and raises an
            RecoverError in case it is found to be
            inconsistent.
            
            Validation takes places for the data on disk. The in
            memory data is not checked.

            XXX This currently does nothing since storages don't
            support validation yet.

        """
        log(SYSTEM_INFO,'Validating storage for %s',self)
        return

    def backup(self,archive=None):

        """ Issues a backup request to the storage using archive
            which defaults to the storage filename + '.backup'.

            This causes an implicit .rollback() to be done.

        """
        self.rollback()
        self.storage.backup(archive)

    def restore(self,archive):

        """ Restores the storage from an archive file.

            XXX Currently does NOT work.
        
        """
        raise SystemError,'.restore() not implemented !'

    ### Iterator interface

    def __iter__(self, method='items'):

        """ Iterator interface.

            Creates an iterator which iterates over the items of the
            complete dictionary.

            Note that this only works if there are no uncommitted
            changes.

        """
        cursor = self.cursor(FirstKey)
        if cursor is None:
            return EmptyIterator()
        if method == 'items':
            return BeeBaseIterator(cursor)
        elif method == 'keys':
            return BeeBaseIterator(cursor, cursor.read_key)
        elif method == 'values':
            return BeeBaseIterator(cursor, cursor.read_value)
        else:
            raise ValueError, 'unknown iterator method: %s' % method

    def iteritems(self):

        """ Returns an iterator to iterate over the items of the dictionary.
        """
        return self.__iter__()

    def iterkeys(self):

        """ Returns an iterator to iterate over the keys of the dictionary.
        """
        return self.__iter__('keys')

    def itervalues(self):

        """ Returns an iterator to iterate over the values of the dictionary.
        """
        return self.__iter__('values')

### BeeBase iterators

# To make iterators work in Python 2.1 and below
try:
    StopIteration
except NameError:
    class StopIteration(exceptions.IndexError):
        pass

class EmptyIterator:

    """ Empty iterator.
    """
    def next(self):
        raise StopIteration
    def __getitem__(self, index):
        raise StopIteration

class BeeBaseIterator:

    """ Iterator for BeeBaseDict subclasses.
    """
    def __init__(self, cursor, read_method=None):

        """ Iterate over cursor and return the values which the read_method
            function returns when called without arguments.

            If read_method is None, cursor.read_item is used.

        """
        self.cursor = cursor
        if read_method is None:
            self.read_method = cursor.read_item
        else:
            self.read_method = read_method
        self.stop = 0

    def next(self):
        if self.stop:
            raise StopIteration
        x = self.read_method()
        self.stop = not self.cursor.next()
        return x

    def __getitem__(self, index):
        return self.next()

### Cursor base class

class BeeBaseDictCursor:

    """ Cursor for BeeBaseDict subclasses.

        The read/read_key/write methods assume that the dictionary
        uses a BeeKeyValueStorage instances as storage facility.

        Note that modifying the targetted dictionary while using a
        cursor can cause the cursor to skip new entries or fail due to
        deleted items. Especially deleting the key to which the cursor
        currently points can cause errors to be raised.  In all other
        cases, the cursor will be repositioned.
        
    """
    cursor = None
    
    def __init__(self,dict,cursor):

        self.dict = dict
        self.cursor = cursor
        self.key = cursor.key
        self.value = cursor.value
        # Alias
        self.read_value = self.read

    def position(self, key, value=None):

        """ Position the index cursor to index[key]. If value is given,
            index[key] == value is assured.

            key may also be FirstKey or LastKey (in which case value
            has to be None).
        """
        # Create and position the cursor
        self.cursor = cursor = self.dict.index.cursor(key)
        if value and cursor.value != value:
            # assure that the cursor points to key,value
            while cursor.next():
                if cursor.value == value:
                    break
                if cursor.key != key:
                    raise KeyError,'key not found'
            else:
                raise KeyError,'key not found'
        self.key = key
        self.value = value

    def next(self):

        """ Moves to the next entry in the dictionary.

            Returns true on success, false if the end-of-data has been
            reached.
        """
        cursor = self.cursor
        if not cursor.valid:
            self.position(self.key,self.value)
            cursor = self.cursor
        rc = cursor.next()
        self.key = cursor.key
        self.value = cursor.value
        return rc

    def prev(self):

        """ Moves to the previous entry in the dictionary.

            Returns true on success, false if the end-of-data has been
            reached.
        """
        cursor = self.cursor
        if not cursor.valid:
            self.position(self.key,self.value)
            cursor = self.cursor
        rc = cursor.prev()
        self.key = cursor.key
        self.value = cursor.value
        return rc

    def read(self):

        """ Reads the value object from the dict to which the cursor
            currently points.

            This method assumes a BeeKeyValueStorage instance in
            self.storage and an index that holds copies of the key
            objects. Override if this is not the case.
            
        """
        return self.dict[self.key]

    def read_key(self):

        """ Reads the key object from the dict to which the cursor
            currently points.

            This method is intended for dictionaries that store hash
            values in the index. Normally, accessing the instance
            variable .key would give the current key object.

            This method assumes a BeeKeyValueStorage instance in
            self.storage. Override if this is not the case.
        """
        return self.dict.storage.read_key(self.value)

    def read_item(self):

        """ Reads the (key, value) item object from the dict to which
            the cursor currently points.

            This method is intended for dictionaries that store hash
            values in the index.

            This method assumes a BeeKeyValueStorage instance in
            self.storage. Override if this is not the case.
        """
        keyobj = self.dict.storage.read_key(self.value)
        return keyobj, self.dict[keyobj]

    def write(self,object):

        """ Writes the value object to the dict under the key to which
            the cursor currently points.

            The new data is not written to disk until the dictionaries
            current transaction is committed.

            This method assumes a BeeKeyValueStorage instance in
            self.storage and an index that holds copies of the key
            objects. Override if this is not the case.

        """
        self.dict[self.key] = object

### Actual implementations

class BeeDict(BeeBaseDict):

    """ On-disk dictionary that uses a "hash to address" index.

        Both Keys and values must be pickleable. Keys also have to be
        hashable. Both can have arbitrary size (keys shouldn't be too
        long though).

        Hash collisions are treated by sequential reads of all records
        with the same hash value and testing for equality of keys. This
        can be expensive !
    
    """
    # Count the number of hash collisions in writes
    collisions = 0

    def __init__(self,name,min_recordsize=0,readonly=0,recover=0,
                 autocommit=0,validate=0, maxcachesize=None,

                 basemethod=BeeBaseDict.__init__):

        """ Create an instance using name as basename for the
            data and index files.

            Two files will be created: <name>.dat and <name>.idx.

            min_recordsize is passed to the BeeStorage as indicator of
            the minimum size for data records. readonly can be set to
            true to open the files in read-only mode, preventing any
            disk modifications.

            To open the dictionary in recovery mode, pass a keyword
            recover=1. Then run .recover() and reopen using the normal
            settings.

            If autocommit is true the cache control will do an
            automatic .commit() whenever the transaction log
            overflows.
            
            If validate is true, the dictionary will run a validation
            check after having successfully opened storage and index.
            RecreateIndexError or RecoverError exceptions could be
            raised in case inconsistencies are found.
            
            maxcachesize defines the maximum size of the in-memory
            transaction cache. It defaults to MAXCACHESIZE if not
            given.
            
        """
        basemethod(self, name, min_recordsize=min_recordsize,
                   readonly=readonly, recover=recover,
                   autocommit=autocommit, validate=validate,
                   index=BeeIndex.BeeIntegerIndex,
                   maxcachesize=maxcachesize)

    def find_address(self,cursor,hashvalue,key):

        """ Find the address of a key by scanning the hash value
            set pointed to by the cursor.

            Returns the address of the found key or None.
        
        """
        while cursor.next():
            if cursor.key != hashvalue:
                # Left set of identical keys in index: not found
                return None
            if key == self.storage.read_key(cursor.value):
                # Found
                return cursor.value
        # EOF reached index: not found
        return None

    def index_cursor(self, key=FirstKey, default=None):

        """ Return an index cursor pointing to key.

            If key is not given, it defaults to FirstKey.  In case the
            key is not found, default is returned.

            XXX Should use this method in more places...

        """
        if key is FirstKey or key is LastKey:
            return self.index.cursor(key, default)
        hashvalue = hash(key)
        cursor = self.index.cursor(hashvalue,None)
        if cursor is None:
            return default
        # Check that we have really found the key
        address = cursor.value
        if key != self.storage.read_key(address):
            # Ah, a collision
            address = self.find_address(cursor,hashvalue,key)
            if address is None:
                return default
        return cursor

    def commit(self,

               basemethod=BeeBaseDict.commit,MODIFIED=MODIFIED,DELETED=DELETED):

        """ Commit all changes and start a new transaction.
        """
        if __debug__:
            log(SYSTEM_DEBUG,'Committing all changes for "%s"...',self.name)

        # Write all changed entries in the cache to disk
        index = self.index
        index_cursor = index.cursor
        index_update = index.update
        index_delete = index.delete
        storage = self.storage
        storage_read_key = storage.read_key
        storage_write = storage.write
        storage_delete = storage.delete
        readonly = self.readonly
        NotFound = None

        for key,(state,value) in self.cache.items():

            if state == MODIFIED:
                if __debug__:
                    log.object(SYSTEM_DEBUG,' writing key "%s":' % repr(key), value)
                if readonly:
                    raise Error,'dict is read-only'
                hashvalue = hash(key)
                cursor = index_cursor(hashvalue, NotFound)
                if cursor is not NotFound:
                    # Update an existing entry (or maybe add a new one if there
                    # was a hash collision)
                    address = cursor.value
                    if key != storage_read_key(address):
                        self.collisions = self.collisions + 1
                        address = self.find_address(cursor, hashvalue, key)
                        # address may be None (== NotFound)... meaning
                        # that we have to add a new record
                    new_address = storage_write(key, value, address)
                    if new_address == address:
                        continue
                    # Update index
                    if address is not NotFound:
                        index_update(hashvalue, new_address, address)
                    else:
                        index[hashvalue] = new_address
                else:
                    # Add a new entry
                    address = storage_write(key, value)
                    # Update index
                    index[hashvalue] = address

            elif state == DELETED:
                if __debug__:
                    log(SYSTEM_DEBUG,' deleting key "%s"',key)
                if readonly:
                    raise Error,'dict is read-only'
                hashvalue = hash(key)
                cursor = index_cursor(hashvalue)
                # Check that we have really found the key
                address = cursor.value
                if key != storage_read_key(address):
                    # Ah, a collision
                    address = self.find_address(cursor, hashvalue, key)
                    if address is NotFound:
                        raise KeyError,'key not found'
                storage_delete(address)
                # Update index
                index_delete(hashvalue, address)

        # End the storage transaction
        storage.end_transaction()

        # Call basemethod
        basemethod(self)

    def read(self,key,checkonly=0):

        # Load from disk
        hashvalue = hash(key)
        cursor = self.index.cursor(hashvalue)
            
        # Check that we have really found the key
        address = cursor.value
        if key != self.storage.read_key(address):
            # Ah, a collision
            address = self.find_address(cursor,hashvalue,key)
            if address is None:
                raise KeyError,'key not found'
        if checkonly:
            return
        else:
            return self.storage.read(address)[1]

    def keys(self,

             DELETED=DELETED):

        """ Return a list of keys.

            The method does not load any data into the cache, but does
            take notice of uncommitted changes.

        """
        l = []
        read_key = self.storage.read_key
        # First the cache entries that are not yet committed
        for key,(state,value) in self.cache.items():
            if state != DELETED:
                l.append(key)
        # Next the remaining entries read from disk
        key_added = self.cache.has_key
        for address in self.index.values():
            key = read_key(address)
            if not key_added(key):
                l.append(key)
        return l

    def values(self,

               DELETED=DELETED):

        """ Return a list of values.

            The method does not load any data into the cache, but does
            take notice of uncommitted changes.

        """
        l = []
        read = self.storage.read
        # First the cache entries that are not yet committed
        for key,(state,value) in self.cache.items():
            if state != DELETED:
                l.append(value)
        # Next the remaining entries read from disk
        key_added = self.cache.has_key
        for address in self.index.values():
            key,value = read(address)
            if not key_added(key):
                l.append(value)
        return l

    def items(self,

              DELETED=DELETED):

        """ Return a list of items.

            The method does not load any data into the cache, but does
            take notice of uncommitted changes.

        """
        l = []
        read = self.storage.read
        # First the cache entries that are not yet committed
        for key,(state,value) in self.cache.items():
            if state != DELETED:
                l.append((key,value))
        # Next the remaining entries read from disk
        key_added = self.cache.has_key
        for address in self.index.values():
            key,value = read(address)
            if not key_added(key):
                l.append((key,value))
        return l

    def cursor(self, key=FirstKey, default=None):

        """ Return a cursor instance for this kind of dictionary.

            If key is given, the cursor is positioned on that key in
            the dictionary. Otherwise, the first entry in the
            dictionary is used which guarantees that all entries are
            scanned.

            Note that cursors operate with the data on disk. The
            method will raise an error in case there are uncommitted
            changes pending.

            In case the key is not found, default is returned instead.
        """
        # Check for uncommitted changes
        if self.cache and self.changed():
            raise Error,'uncommitted data exists'
        # Get the index cursor and create a dict cursor from it
        cursor = self.index_cursor(key,None)
        if cursor is None:
            return default
        return BeeDictCursor(self,cursor)

    def collect_callback(self, old_position, new_position, raw_data):

        """ Internal callback used to update the index when
            the storage garbage collector moves a record.
        """
        key = hash(self.storage.decode_key(raw_data))
        try:
            self.index.update(key,new_position,old_position)
        except KeyError:
            # Ok, then we'll add the key as new entry
            log(SYSTEM_WARNING,
                'Collect callback detected a missing key in '
                'index: %i; restoring it',old_position)
            self.index[key] = new_position
        
    def recover_callback(self, old_position, new_position, raw_data):

        """ Internal callback used to update the index when
            the storage recovery collector finds a record.

            old_position is only given as additional information.
            new_position contains the position of the found record.
            
        """
        self.index[hash(self.storage.decode_key(raw_data))] = new_position
        
###

class BeeDictCursor(BeeBaseDictCursor):

    """ Cursor for BeeDict instances.

        Since the keys are not kept directly in the index, .read_key()
        must be used to obtain the real key objects instead of
        querying the instance variable .key.

    """
    def read(self):

        """ Reads the value object from the dict to which the cursor
            currently points.
        """
        keyobj = self.dict.storage.read_key(self.value)
        return self.dict[keyobj]

    def read_key(self):

        """ Reads the key object from the dict to which the cursor
            currently points.
        """
        return self.dict.storage.read_key(self.value)

    def read_item(self):

        """ Reads the (key, value) item object from the dict to which
            the cursor currently points.
        """
        keyobj = self.dict.storage.read_key(self.value)
        return keyobj, self.dict[keyobj]

    def write(self,object):

        """ Writes the value object to the dict under the key to which
            the cursor currently points.

            The new data is not written to disk until the dictionary's
            current transaction is committed.
        """
        keyobj = self.dict.storage.read_key(self.value)
        self.dict[keyobj] = object

freeze(BeeDictCursor)

###

class BeeStringDict(BeeBaseDict):

    """ A dictionary that is indexed by limited size strings.

        The key strings may *not* contain embedded \0 characters.

        Though the keys must be strings of limited size, the values
        can be any pickleable object.

    """
    def __init__(self,name,keysize=10,min_recordsize=0,readonly=0,recover=0,
                 autocommit=0,validate=0, maxcachesize=None,

                 basemethod=BeeBaseDict.__init__):

        """ Create an instance using name as dictionary name.

            Two files will be created: <name>.dat and <name>.idx.

            keysize gives the maximal size of the strings used as
            index keys.

            min_recordsize gives a hint to the expected typical size
            of (key,value) pickles: all records will have at least
            this size.

            To open the dictionary in recovery mode, pass a keyword
            recover=1. Then run .recover() and reopen using the normal
            settings.
            
            If autocommit is true the cache control will do an
            automatic .commit() whenever the transaction log
            overflows.

            If validate is true, the dictionary will run a validation
            check after having successfully opened storage and index.
            RecreateIndexError or RecoverError exceptions could be
            raised in case inconsistencies are found.
            
            maxcachesize defines the maximum size of the in-memory
            transaction cache. It defaults to MAXCACHESIZE if not
            given.
            
            XXX Save keysize in storage file header.
            
        """
        basemethod(self, name, keysize=keysize, min_recordsize=min_recordsize,
                   readonly=readonly, recover=recover,
                   autocommit=autocommit, validate=validate,
                   index=BeeIndex.BeeStringIndex,
                   maxcachesize=maxcachesize)

    def commit(self,

               basemethod=BeeBaseDict.commit,DELETED=DELETED,MODIFIED=MODIFIED):

        """ Commit all changes and start a new transaction.
        """
        if __debug__:
            log(SYSTEM_DEBUG,'Committing all changes for "%s"...',self.name)

        # Write all changed entries in the cache to disk
        index = self.index
        index_get = index.get
        storage = self.storage
        storage_write = storage.write
        storage_delete = storage.delete
        readonly = self.readonly
        NotFound = None

        for key,(state,value) in self.cache.items():

            if state == MODIFIED:
                if __debug__:
                    log.object(SYSTEM_DEBUG,' writing key "%s":' % repr(key), value)
                address = index_get(key,NotFound)
                if address is not NotFound:
                    # Update storage
                    new_addr = storage_write(key,value,address)
                    if new_addr == address:
                        continue
                    # Update index
                    index[key] = new_addr
                else:
                    # Add to storage
                    address = storage_write(key,value)
                    # Add to the index
                    index[key] = address

            elif state == DELETED:
                if __debug__:
                    log(SYSTEM_DEBUG,' deleting key "%s"',key)
                if readonly:
                    raise Error,'dict is read-only'
                address = index_get(key,NotFound)
                if address is not NotFound:
                    # Delete record
                    storage_delete(address)
                    # Update Index
                    del index[key]
                else:
                    raise KeyError,'key not found'

        # End the storage transaction
        storage.end_transaction()

        # Call basemethod
        basemethod(self)

    def read(self,key,checkonly=0):

        address = self.index[key]
        if checkonly:
            return
        else:
            return self.storage.read(address)[1]

    def keys(self):

        """ Return a list of keys.

            The method will raise an error if there are uncommitted
            changes pending. Output is sorted ascending according to
            keys.
            
        """
        if self.cache and self.changed():
            raise Error,'uncommitted data exists'
        return self.index.keys()

    def values(self):

        """ Return a list of values.

            The method will raise an error if there are uncommitted
            changes pending. Output is sorted ascending according to
            keys.
            
        """
        if self.cache and self.changed():
            raise Error,'uncommitted data exists'
        l = []
        read = self.storage.read
        for address in self.index.values():
            l.append(read(address)[1])
        return l

    def items(self):

        """ Return a list of items.

            The method will raise an error if there are uncommitted
            changes pending. Output is sorted ascending according to
            keys.
            
        """
        if self.cache and self.changed():
            raise Error,'uncommitted data exists'
        l = []
        read = self.storage.read
        for address in self.index.values():
            l.append(read(address))
        return l

    def cursor(self, key=FirstKey, default=None):

        """ Return a cursor instance for this kind of dictionary.

            If key is given, the cursor is positioned on that key in
            the dictionary. Otherwise, the first entry in the
            dictionary is used which guarantees that all entries are
            scanned.

            Note that cursors operate with the data on disk meaning
            that any uncommitted changes will not be seen by the
            cursor.

            In case the key is not found, default is returned instead.
        """
        # Check for uncommitted changes
        if self.cache and self.changed():
            raise Error,'uncommitted data exists'
        # Get the index cursor and create a dict cursor from it
        cursor = self.index.cursor(key,None)
        if cursor is None:
            return default
        return BeeStringDictCursor(self,cursor)

    def collect_callback(self,old_position,new_position,raw_data):

        """ Internal callback used to update the index when
            the storage garbage collector moves a record.
        """
        key = self.storage.decode_key(raw_data)
        try:
            self.index.update(key,new_position,old_position)
        except KeyError:
            # Ok, then we'll add the key as new entry
            log(SYSTEM_WARNING,
                'Collect callback detected a missing key in '
                'index: %i; restoring it',old_position)
            self.index[key] = new_position
        
    def recover_callback(self,old_position,new_position,raw_data):

        """ Internal callback used to update the index when
            the storage recovery collector finds a record.

            old_position is only given as additional information.
            new_position contains the position of the found record.

            XXX What if the recovery collector find two records
                with the same key ?
            
        """
        self.index[self.storage.decode_key(raw_data)] = new_position
        
freeze(BeeStringDict)

###

class BeeFixedLengthStringDict(BeeStringDict):

    """ A dictionary that is indexed by fixed length strings.

        The key strings may contain embedded \0 characters.

        Though the keys must be strings of limited size, the values
        can be any pickleable object.

    """
    def __init__(self,name,keysize=10,min_recordsize=0,readonly=0,recover=0,
                 autocommit=0,validate=0, maxcachesize=None,

                 basemethod=BeeBaseDict.__init__):

        """ Create an instance using name as dictionary name.

            Two files will be created: <name>.dat and <name>.idx.

            keysize gives the maximal size of the strings used as
            index keys.

            min_recordsize gives a hint to the expected typical size
            of (key,value) pickles: all records will have at least
            this size.

            To open the dictionary in recovery mode, pass a keyword
            recover=1. Then run .recover() and reopen using the normal
            settings.
            
            If autocommit is true the cache control will do an
            automatic .commit() whenever the transaction log
            overflows.

            If validate is true, the dictionary will run a validation
            check after having successfully opened storage and index.
            RecreateIndexError or RecoverError exceptions could be
            raised in case inconsistencies are found.
            
            maxcachesize defines the maximum size of the in-memory
            transaction cache. It defaults to MAXCACHESIZE if not
            given.
            
            XXX Save keysize in storage file header.
            
        """
        basemethod(self, name, keysize=keysize, min_recordsize=min_recordsize,
                   readonly=readonly, recover=recover,
                   autocommit=autocommit, validate=validate,
                   index=BeeIndex.BeeFixedLengthStringIndex,
                   maxcachesize=maxcachesize)

freeze(BeeFixedLengthStringDict)

###

class BeeStringDictCursor(BeeBaseDictCursor):

    """ Cursor for BeeStringDict and BeeFixedLengthStringDict instances.
    """
    def read_key(self):

        """ Reads the key object from the dict to which the cursor
            currently points.
        """
        return self.key

    def read_item(self):

        """ Reads the (key, value) item object from the dict to which
            the cursor currently points.
        """
        return self.key, self.dict[self.key]

freeze(BeeStringDictCursor)

###

def AutoRecover(Class,*args,**kws):

    """ Wrapper that runs recovery whenever needed.

        This can still fail, but at least many "normal" failures can
        be handled this way automatically.
        
    """
    try:
        d = apply(Class,args,kws)
        return d
    except BeeStorage.RunRecoveryError:
        pass
    except RecreateIndexError:
        pass
    except RecoverError:
        pass
    # Open in recovery mode
    log(SYSTEM_ERROR,
        'Database "%s" is corrupt; trying recovery...',args[0])
    new_kws = kws.copy()
    new_kws['readonly'] = 0
    new_kws['validate'] = 0
    #new_kws['lock'] = 1
    new_kws['recover'] = 1
    d = apply(Class,args,new_kws)
    # Run recover & close
    d.recover()
    del d
    # Reopen in original mode
    d = apply(Class,args,kws)
    log(SYSTEM_WARNING,
        'Successfully recovered the database "%s"',args[0])
    return d

###

if __name__ == '__main__':

    import sys

    print 'Testing BeeStringDict...'
    
    s = BeeStringDict('test-BeeStringDict')
    s['Marc'] = 'Sveta'
    s['Thorsten'] = 'Petra'
    s['Christian'] = 'Leesa'
    s.commit()

    print 'Testing BeeDict...'

    d = BeeDict('test-BeeDict')
    d['Marc'] = 'Sveta'
    d['Thorsten'] = 'Petra'
    d['Christian'] = 'Leesa'
    d.commit()

    d['Marc'] = 'Sveta' * 100
    d.commit()
    
    del d,s

    print 'Testing iteration...'
    d = BeeDict('test-BeeDict')
    d['Marc'] = 'Sveta'
    d['Thorsten'] = 'Petra'
    d['Christian'] = 'Leesa'
    d.commit()
    i = 0
    for k,v in d.iteritems():
        print '%s: %s' % (k,v)
        i = i + 1
    assert i == 3

    if sys.version[:3] >= '2.2':
        i = 0
        for k,v in d:
            print '%s: %s' % (k,v)
            i = i + 1
        assert i == 3
 
    del d
    
    print 'Works.'


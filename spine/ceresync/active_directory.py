"""active_directory - a lightweight wrapper around COM support
 for Microsoft's Active Directory

Active Directory is Microsoft's answer to LDAP, the industry-standard
 directory service holding information about users, computers and
 other resources in a tree structure, arranged by departments or
 geographical location, and optimized for searching.

There are several ways of attaching to Active Directory. This
 module uses the Dispatchable LDAP:// objects and wraps them
 lightly in helpful Python classes which do a bit of the
 otherwise tedious plumbing. The module is quite naive, and
 has only really been developed to aid searching, but since
 you can always access the original COM object, there's nothing
 to stop you using it for any AD operations.

+ The active directory object (AD_object) will determine its
   properties and allow you to access them as instance properties.

   eg
     import active_directory
     goldent = active_directory.find_user ("goldent")
     print ad.displayName

+ Any object returned by the AD object's operations is themselves
   wrapped as AD objects so you get the same benefits.

  eg
    import active_directory
    users = active_directory.root ().child ("cn=users")
    for user in users.search ("displayName='Tim*'"):
      print user.displayName

+ To search the AD, there are two module-level general
   search functions, two module-level functions to
   find a user and computer specifically and the search
   method on each AD_object. Usage is illustrated below:

   import active_directory as ad

   for user in ad.search (
     "objectClass='User'",
     "displayName='Tim Golden' OR sAMAccountName='goldent'"
   ):
     #
     # This search returns an AD_object
     #
     print user

   query = \"""
     SELECT Name, displayName 
     FROM 'LDAP://cn=users,DC=gb,DC=vo,DC=local'
     WHERE displayName = 'John*'
   \"""
   for user in ad.search_ex (query):
     #
     # This search returns an ADO_object, which
     #  is faster but doesn't give the convenience
     #  of the AD methods etc.
     #
     print user

   print ad.find_user ("goldent")

   print ad.find_computer ("vogbp200")

   users = ad.root ().child ("cn=users")
   for u in users.search ("displayName='Tim*'"):
     print u

+ Typical usage will be:

import active_directory

for computer in active_directory.search ("objectClass='computer'"):
  print computer.displayName

(c) Tim Golden <tim.golden@iname.com> October 2004

Many thanks, obviously to Mark Hammond for creating
 the pywin32 extensions.

20th Oct 2004 0.3  Added "Page Size" param to query to allow result
                    sets of > 1000.
                   Refactored search mechanisms to module-level and
                    switched to SQL queries.
19th Oct 2004 0.2  Added support for attribute assignment
                     (see AD_object.__setattr__)
                   Added module-level functions:
                     root - returns a default AD instance
                     search - calls root's search
                     find_user - returns first match for a user/fullname
                     find_computer - returns first match for a computer
                   Now runs under 2.2 (removed reference to basestring)
15th Oct 2004 0.1  Initial release by Tim Golden
"""
from __future__ import generators

__VERSION__ = "0.2"

from win32com.client import Dispatch, GetObject
from win32com.client.gencache import EnsureDispatch

def _set (obj, attribute, value):
  """Helper function to add an attribute directly into the instance
   dictionary, bypassing possible __getattr__ calls
  """
  obj.__dict__[attribute] = value

def _and (*args):
  """Helper function to return its parameters and-ed
   together and bracketed, ready for a SQL statement.

  eg,

    _and ("x=1", "y=2") => "(x=1 AND y=2)"
  """
  return " AND ".join (args)

def _or (*args):
  """Helper function to return its parameters or-ed
   together and bracketed, ready for a SQL statement.

  eg,

    _or ("x=1", _and ("a=2", "b=3")) => "(x=1 OR (a=2 AND b=3))"
  """
  return " OR ".join (args)

def _add_path (root_path, relative_path):
  """Add another level to an LDAP path.
  eg,

    _add_path ('LDAP://DC=gb,DC=vo,DC=local', "cn=Users")
      => "LDAP://cn=users,DC=gb,DC=vo,DC=local"
  """
  protocol = "LDAP://"
  if relative_path.startswith (protocol):
    return relative_path

  if root_path.startswith (protocol):
    start_path = root_path[len (protocol):]
  else:
    start_path = root_path

  return protocol + relative_path + "," + start_path

#
# Global cached ADO Connection object
#
_connection = None
def connection ():
  global _connection
  if _connection is None:
    _connection = EnsureDispatch ("ADODB.Connection")
    _connection.Provider = "ADsDSOObject"
    _connection.Open ("Active Directory Provider")
  return _connection

class ADO_record (object):
  """Simple wrapper around an ADO result set"""

  def __init__ (self, record):
    self.record = record
    self.fields = {}
    for i in range (record.Fields.Count):
      field = record.Fields.Item (i)
      self.fields[field.Name] = field

  def __getattr__ (self, name):
    """Allow access to field names by name rather than by Item (...)"""
    try:
      return self.fields[name]
    except KeyError:
      raise AttributeError

  def __str__ (self):
    """Return a readable presentation of the entire record"""
    s = []
    s.append (repr (self))
    s.append ("{")
    for name, item in self.fields.items ():
      s.append ("  %s = %s" % (name, item))
    s.append ("}")
    return "\n".join (s)

def query (query_string, **command_properties):
  """Auxiliary function to serve as a quick-and-dirty
   wrapper round an ADO query
  """
  command = EnsureDispatch ("ADODB.Command")
  command.ActiveConnection = connection ()
  #
  # Add any client-specified ADO command properties.
  # NB underscores in the keyword are replaced by spaces.
  #
  # Examples:
  #   "Cache_results" = False => Don't cache large result sets
  #   "Page_size" = 500 => Return batches of this size
  #   "Time Limit" = 30 => How many seconds should the search continue
  #
  for k, v in command_properties.items ():
    command.Properties (k.replace ("_", " ")).Value = v
  command.CommandText = query_string

  recordset, result = command.Execute ()
  while not recordset.EOF:
    yield ADO_record (recordset)
    recordset.MoveNext ()

class AD_object (object):
  """Wrap an active-directory object for easier access
   to its properties and children. May be instantiated
   either directly from a COM object or from an ADs Path.

   eg,

     import active_directory
     users = AD_object (path="LDAP://cn=Users,DC=gb,DC=vo,DC=local")     
  """

  def __init__ (self, obj=None, path=""):
    #
    # Be careful here with attribute assignment;
    #  __setattr__ & __getattr__ will fall over
    #  each other if you aren't.
    #
    if path:
      _set (self, "com_object", GetObject (path))
    else:
      _set (self, "com_object", obj)
    schema = GetObject (self.com_object.Schema)
    _set (self, "properties", schema.MandatoryProperties + schema.OptionalProperties)
    _set (self, "is_container", schema.Container)

  def __getattr__ (self, name):
    #
    # Allow access to object's properties as though normal
    #  Python instance properties. Some properties are accessed
    #  directly through the object, others by calling its Get
    #  method. Not clear why.
    #
    try:
      return getattr (self.com_object, name)
    except AttributeError:
      try:
        return self.com_object.Get (name)
      except:
        raise AttributeError

  def __setattr__ (self, name, value):
    #
    # Allow attribute access to the underlying object's
    #  fields.
    #
    if name in self.properties:
      self.com_object.Put (name, value)
      self.com_object.SetInfo ()
    else:
      _set (self, name, value)

  def as_string (self):
    return self.path ()

  def __str__ (self):
    return self.as_string ()

  def __repr__ (self):
    return "<%s: %s>" % (self.__class__.__name__, self.as_string ())

  def __iter__ (self):
    self._iter = iter (self.com_object)
    return self

  def next (self):
    return AD_object (self._iter.next ())

  def set (self, **kwds):
    """Set a number of values at one time. Should be
     a little more efficient than assigning properties
     one after another.

    eg,

      import active_directory
      user = active_directory.find_user ("goldent")
      user.set (displayName = "Tim Golden", description="SQL Developer")
    """
    for k, v in kwds.items ():
      self.com_object.Put (k, v)
    self.com_object.SetInfo ()

  def path (self):
    return self.com_object.ADsPath

  def parent (self):
    """Find this object's parent"""
    return AD_object (path=self.com_object.Parent)

  def child (self, relative_path):
    """Return the relative child of this object. The relative_path
     is inserted into this object's AD path to make a coherent AD
     path for a child object.

    eg,

      import active_directory
      root = active_directory.root ()
      users = root.child ("cn=Users")
      
    """
    return AD_object (path=_add_path (self.path (), relative_path))

  def search (self, *args):
    sql_string = []
    sql_string.append ("SELECT *")
    sql_string.append ("FROM '%s'" % self.path ())
    where_clause = _and (*args)
    if where_clause:
      sql_string.append ("WHERE %s" % where_clause)

    for result in query ("\n".join (sql_string), Page_size=50):
      yield AD_object (path=result.ADsPath.Value)

def AD (server=None):
  default_naming_context = _root (server).Get ("defaultNamingContext")
  return AD_object (GetObject ("LDAP://%s" % default_naming_context))

def _root (server=None):
  if server:
    return GetObject ("LDAP://%s/rootDSE" % server)
  else:
    return GetObject ("LDAP://rootDSE")

def find_user (name):
  for user in search ("sAMAccountName='%s' OR displayName='%s'" % (name, name)):
    return user
  
def find_computer (name):
  for computer in search ("objectCategory='Computer'", "Name='%s'" % name):
    return computer

#
# root returns a cached object referring to the
#  root of the logged-on active directory tree.
#
_ad = None
def root ():
  global _ad
  if _ad is None:
    _ad = AD ()
  return _ad

def search (*args, **kwargs):
  return root ().search (*args, **kwargs)

def search_ex (query_string=""):
  """Search the Active Directory by specifying a complete
   query string. NB The results will *not* be AD_objects
   but rather ADO_objects which are queried for their fields.

   eg,

     import active_directory
     for user in active_directory.search_ex (\"""
       SELECT displayName
       FROM 'LDAP://DC=gb,DC=vo,DC=local'
       WHERE objectCategory = 'Person'
     \"""):
       print user.displayName
  """
  for result in query (query_string, Page_size=50):
    yield result

# arch-tag: c0328e03-83ed-4a7a-a77d-2888a1f8004f

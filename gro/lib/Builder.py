#!/usr/bin/env python

# TODO: Create proper exceptions

from pickle import Pickler, Unpickler
import os
#import cereconf

GRO_IDL_FILE_NAME = "ap_generated.idl"
GRO_PYTHON_FILE_NAME = "ap_generated.py"
IDL_ERROR_LOG = "error.log"
GRO_ALLOWED_DATA_TYPES = ["string", "long", "boolean", "float"]

class Builder:
    exists = 0
    def __init__( self ):
        if not self.exists:
            self.objects = {}
            self.exists = 1
            pass
        else:
            # Ignorer init kall
            pass
        
        # Les alt fra config-område
        # Kjør filer som er definert der
        #self._build()
        

    def register( self, class_name, attr_name, attr_type, api_class,
                  api_attr, auth=None, val=None, override=0 ):
        """ Registers an attribute

        class_name is the name of the class this attribute is a member of
        attr_name is the name of the attribute as it will be in the API
        attr_type is the data type of attr_name
        api_class is the name of the Class where this attribute can be found in the
        Cerebrum datbase API
        api_attr is the name of the attribute in the Cerebrum database API
        auth is the authentication function to use for this attribute. None for no
        access control (default)
        val is the validation function to use for this attribute. None for no
        validation (default)
        override decides whether to replace an existing definition of this attribute.
        defaults to 0

        If the attribute does not exist, it will be added to the class defined by
        classname. If classname does not exist as a class, it will be created.

        If override=0 and the class_name/attr_name combination exists, and exception
        will be raised.
        """
        
        if attr_type not in GRO_ALLOWED_DATA_TYPES:
            raise Exception( "Data type %s for %s.%s not allowed" %
                             (attr_type, class_name, attr_name) )
        if (not override) and  self.objects.has_key( ( class_name, attr_name ) ):
            raise Exception( "%s.%s already exists. " % (class_name, attr_name) +
                             "Set method documentation for Builder.register." )
        else:
            if auth is None:
                auth = []
            else:
                auth = [self._get_full_identifier(auth)]

            if val is None:
                val = []
            else:
                val = [self._get_full_identifier(val)]
                
            attr = [(attr_type, api_class, api_attr), auth, val]
            if not self.objects.has_key( class_name ):
                attrs = {attr_name:attr}
                classvals = []
            else:
                attrs, classvals = self.objects[class_name]
                attrs[attr_name] = attr
            
            self.objects[class_name] = attrs, classvals 

    
    def _get_full_identifier( self, func ):
        return func

    def reg_attr_val( self, class_name, attr_name, val, replace=0 ):
        """ Registers a validation function for an attribute """

        if not self.objects.has_key( class_name ):
            raise Exception( "class %s not registered" % class_name )
        attrs, classvals = self.objects[class_name]
        if not attrs.has_key( attr_name ):
            raise Exception( "attribute %s in class %s not registered" %
                              (attr_name, class_name) )

        if replace:
            attrs[attr_name][2] = [self._get_full_identifier(val)]
        else:
            attrs[attr_name][2] += [self._get_full_identifier(val)]
            
        self.objects[class_name] = attrs, classvals 

    def reg_class_val( self, class_name, val, replace=0 ):
        """ Registers a validation function for a class """

        if not self.objects.has_key( class_name ):
            raise Exception( "class %s not registered" % class_name )
        attrs, classvals = self.objects[class_name]
        if replace:
            classvals
        else:
            classvals.append( self._get_full_identifier(val) )
            
        self.objects[class_name] = attrs, classvals 

        
    def reg_attr_auth( self, class_name, attr_name, auth, replace=0 ):
        """ Registers an authorization function for an attribute """
        
        if not self.objects.has_key( class_name ):
            raise Exception( "class %s not registered" % class_name )
        attrs, classvals = self.objects[class_name]
        if not attrs.has_key( attr_name ):
            raise Exception( "attribute %s in class %s not registered" %
                             (attr_name, class_name) )
        if replace:
            attrs[attr_name][1] = [self._get_full_identifier(auth)]
        else:
            attrs[attr_name][1] += [self._get_full_identifier(auth)]
            
        self.objects[class_name] = attrs, classvals 


    def _check_for_changes( self, new_objects, old_objects, check_reverse=1 ):
        newPyReason = 0
        for key, value in new_objects.items():
            # Check presence of class 
            if not old_objects.has_key( key ):
                return (1,1)            
            oattrs, oclassval = old_objects[key]
            attrs, classval = new_objects[key]
            
            # Check class validation functions
            for valfunc in classval:
                if not oclassval.__contains__( valfunc ):
                    newPyReason = 1

            for attr, attrinfo in attrs.items():
                # Check presence of attribute in class
                if not oattrs.has_key( attr ):
                    return (1,1)
                ( atype, apiname, apiattr )= attrinfo[0]
                ( oatype, oapiname, oapiattr) = oattrs[attr][0]

                # Check type of attribute
                if atype is not oatype:
                    return (1,1)

                # Check class and attribute for cerebrum api reference
                if apiname is not oapiname or apiattr is not oapiattr:
                    newPyReason = 1

                # Check attribute authorization functions
                for authfunc in attrinfo[1]:
                    if not oattrs[attr][1].__contains__( authfunc ):
                        newPyReason = 1

                # Check attribute validation functions
                for avalfunc in attrinfo[2]:
                    if not oattrs[attr][2].__contains__( avalfunc ):
                        newPyReason = 1

        # If we still look good to go, check the data structures the opposite way
        if check_reverse:
            (newpy, newidl) = self._check_for_changes( old_objects, new_objects, 0 )
            return (newPyReason or newpy, newidl)
        else:
            return (newPyReason,0)

    def _build( self ):
        """ Build the shit """
        if os.path.isfile( 'objektfil' ):
            old_objects = Unpickler( open( 'objektfil' ) ).load()
        else:
            Pickler( open( 'objektfil', 'w' ) ).dump( self.objects )
                  

        # Check to see if new files must be built
        (newpy, newidl) = self._check_for_changes( self.objects, old_objects )
        if newpy:
            print "Need to build new python files"
        if newidl:
            print "Need to build new idl files"

        if newidl :
            self._build_idl()

        if newpy:
            self._build_python()
            
        # Save the file with new class information
        Pickler( open( 'objektfil', 'w' ) ).dump( self.objects )

    # TODO: Make an idl exception for lacking privileges
    # TODO: Create facilities for populating objects    
    def _build_python( self ):
        py = open( GRO_PYTHON_FILE_NAME, "w" )
        py.write( "#AUTOGENERATED FILE. CHANGES WILL BE OVERWRITTEN\n" )
        py.write( "from Cerebrum.gro import Gro\n" )
        py.write( "from Cerebrum.gro.Cerebrum.AP import *\n" )

        for key, value in self.objects.items():
            (attrs, classval) = value
            py.write( "class %s(Cerebrum.AP__POA.%s):\n" % (key,key) )
            for attr, attrinfo in attrs.items():
                ( atype, apiname, apiattr )= attrinfo[0]
                
                # Create set_... function
                py.write( "\tdef set_%s( self, new_%s ):\n" % (attr, attr) )
                # Check authorization
                for afunc in attrinfo[1]:
                    py.write( "\t\tif not %s( self.__db, Gro.get_user()," % afunc +
                              "'change', self.id):\n" )                              
                    py.write( "\t\t\traise Exception( '...' )\n" )

                # Check validation
                for vfunc in attrinfo[2]:
                    py.write( "\t\tif not %s( self.__db, Gro.get_user(), " % vfunc +
                              "'change', self.id, new_%s):\n" % attr )
                    py.write( "\t\t\traise Exception( '...' )\n" )

                py.write( "\t\tself.%s = new_%s\n\n" % (attr, attr) )

                # Create get_... function
                py.write( "\tdef get_%s( self ):\n" % attr )
                # Check authorization
                for afunc in attrinfo[1]:
                    py.write( "\t\tif not %s( self.__db, Gro.get_user()," % afunc +
                              "'read', self.id):\n" )
                              
                    py.write( "\t\t\traise Exception( '...' )\n" )

                py.write( "\t\treturn self.%s\n\n" % attr )

            py.write( "\tdef store( self ):\n" )
            for valfunc in classval:
                py.write( "\t\tif not %s( self.__db, Gro.get_user()," % valfunc +
                          "'read', self):\n" )
                py.write( "\t\t\traise Exception( '...' )\n" )
            py.write( "\t\t #NEED ZOME CODEZ HEREZ! !1|1\n\n" )
                
            # TODO: Store data in the database
            
    def _build_idl( self ):
        idl = open( GRO_IDL_FILE_NAME, "w" )
        idl.write( "//AUTOGENERATED FILE. CHANGES WILL BE OVERWRITTEN\n" )
        idl.write( "module Cerebrum{\n" )
        idl.write( "\tmodule AP{\n" )

        for key, value in self.objects.items():
            idl.write( "\t\tinterface %s{\n" % key )
            
            for attr, attrinfo in value[0].items():
                ( atype, apiname, apiattr )= attrinfo[0]
                idl.write( "\t\t\t%s get_%s();\n" % (atype, attr) )
                idl.write( "\t\t\tvoid set_%s(in %s new_%s);\n" % (attr,atype,attr) )

            idl.write( "\t\t};\n" )

        idl.write( "\t};\n };\n" )
        idl.close()
        
        # Compile idl files
        for i in range( 1):#len(cereconf.GRO_IDL_COMPILER) ):
            #(in,out,err) = os.popen3( cereconf.GRO_IDL_COMPILER[i]+" "+GRO_IDL_FILE_NAME )
            (ins,outs,errs) = os.popen3( "omniidl -bpython -Wbpackage=Cerebrum.gro.ap "+
                                         GRO_IDL_FILE_NAME )
            items = errs.readlines()
            if len( items ) != 0:
                errf = open ( IDL_ERROR_LOG, "w" )
                errf.writelines( items )
                errf.close()
            signal,status = os.wait()
            if status is not 0:
                raise Exception( "Could not compile idl file. See %s for detail" %
                                 IDL_ERROR_LOG )

#Gro.Builder.register( string klassenavn, string attrnavn,
#                      string type,
#                      string db-location, function auth  )


#db-location er f.eks Entity.Entity._id


# Under kjøring:
"""
Entity ole = Entity.search( 'id=1234' )
ole.setName( 'Dole' )

--> På server:
setName():
  (APHandler?) foo( 'Entity'. 'name', 1234, brukernavn_som_kjører_dette, 'write' )
--> I foo:
  matcher 'Entity' + 'name' og finner auth-funksjon
  auth( db, brukernavn_som_kjører_dette, 'write', 1234 )
  hvis auth ok:
    bruk api_name til å skrive riktig sted

"""


#Lage en modul:

"""
#Legge til attributten fisk i Person

#i en ny fil
def auth_fisk( db_obj, uname, read_write, id): # Navn uten betydning
    if( uname = db_obj.search( 'SELECT uname from Person WHERE id=%s',id )):
        return 1
    else:
        return 0

register( 'Person', 'fisk', 'string', 'Person.fisk', auth_fisk )
    
"""
def fiskauth( db_obj, uname, mode, id ):
    print "fiskauth was called"
    return 1

def fiskauth2( db_obj, uname, mode, id ):
    print "fiskauth2 was called"
    return 1

def fiskval1( db_obj, uname, mode, id ):
    print "fiskval1 was called"
    return 1

def fiskval2( db_obj, uname, mode, id ):
    print "fiskval2 was called"
    return 1

def fooauth( db_obj, uname, mode, id ):
    print "fooauth was called"
    return 1

def fooauth2( db_obj, uname, mode, id ):
    print "fooauth2 was called"
    return 1

def personval():
    print "bar"
    return 1

if __name__ == '__main__':
  a = Builder()
  a.register( "Person", "fisk", "string", "Person", "gjedde" )
  a.register( "Person", "frsdddssk", "string", "Person", "gjedde" )
  
  # print a.objects.values()
  a.reg_attr_auth( "Person", "fisk", "fiskauth" )
  a.reg_attr_auth( "Person", "fisk", "fiskauth2", 0 )
  a.reg_attr_val( "Person", "fisk", "fiskval2"  )
  a.reg_attr_val( "Person", "fisk", "fiskval2" )
  a.register( "Hus", "vegg", "long", "Hus", "fooo", auth="fooauth" )
  a.reg_attr_val( "Hus", "vegg", "fooauth2", 1 )
  a.reg_class_val( "Person", "personval" )
  a._build()
  # print a.objects.values()
  
  

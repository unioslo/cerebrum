# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

import omniORB

from Cerebrum_core import Errors
from Transaction import Transaction
from classes.Builder import CorbaBuilder, Method, Attribute
from classes.Account import Account # FIXME: midlertidig. bruker denne til å lage søkeklasse. GroRegistry noen?

def create_ap_method(method_name, data_type, method_arguments=[]):
    args_table = dict(method_arguments)
    def method(self, *corba_args, **corba_vargs):
        if len(corba_args) + len(corba_vargs) > len(method_arguments):
            raise TypeError('too many arguments')

        # TODO: hooks til transaksjon/låsing/auth må fikses her

        args = []
        for value, arg in zip(corba_args, method_arguments):
            args.append(APHandler.convert_from_corba(value, arg[1])) # FIXME: er arg[1] riktig?

        vargs = {}
        for name, value in corba_vargs.items():
            vargs[name] = APHandler.convert_from_corba(value, args_table[name])

        value = getattr(self.gro_object, method_name)(*args, **vargs)

        return APHandler.convert_to_corba(value, data_type, self.ap_handler)
    return method

class APClass:
    """ Creator of Access point proxy object.

    An APClass object contains the APHandler and an object from the GRO API. 
    It acts as a proxy for the object.
    This is to give us a sort of automatic session handling that will solve two problems:
    1 - The client does not have to deal with a session id
    2 - GRO can perform locking on objects requested by a client,
        using the APHandler to identify it.
    """

    def __init__(self, gro_object, ap_handler):
        self.gro_object = gro_object
        self.ap_handler = ap_handler

    def create_ap_class(cls, gro_class, idl_class):
        name = gro_class.__name__
        ap_class_name = 'AP' + name
        
        exec 'class %s(cls, idl_class):\n\tpass\nap_class = %s' % (
             ap_class_name, ap_class_name)

        for attribute in gro_class.slots:
            get_name = 'get_' + attribute.name
            get = create_ap_method(get_name, attribute.data_type)
            setattr(ap_class, get_name, get)

            if attribute.writable:
                set_name = 'set_' + attribute.name
                set = create_ap_method(set_name, 'void', [(attribute.name, attribute.data_type)])
                setattr(ap_class, set_name, set)

        # TODO: legge til support for gro_class.method_slots

        for method in gro_class.method_slots:
            ap_method = create_ap_method(method.name, method.data_type, method.args)
            setattr(ap_class, method.name, ap_method)

        ap_class.gro_class = gro_class

        return ap_class

    create_ap_class = classmethod(create_ap_class)

def create_ap_handler_get_method(data_type):
    def get(self, *args, **vargs):
        obj = APHandler.gro_classes[data_type](*args, **vargs)
        return APHandler.convert_to_corba(obj, data_type, self)
    return get

class APHandler(CorbaBuilder, Transaction):
    """Access point handler.

    Each client has his own access point, wich will be used to identify the client
    so we can lock down objects to the client and check if the client has access to
    make the changes he tries to do. The client has to provide GRO a username
    and password before he gets the APHandler. This information will be stored in
    this object.
    """

    classes = {} # Access Point classes
    gro_classes = {} # GRO API classes to be used
    slots = []
    method_slots = [Method('begin','void'), Method('rollback', 'void'), Method('commit', 'void')]

    def convert_to_corba(cls, value, data_type, ap_handler):
        if data_type == 'Entity': # we need to "cast" to the correct class
            data_type = value.__class__.__name__
        # TODO: skummel bruk av navnekonvesjon, burde legge til flags i Attribute i stedet
        if data_type.endswith('Seq'):
            return [cls.convert_to_corba(i, data_type[:-3], ap_handler) for i in value]
        elif data_type in cls.classes:
            ap_object = cls.classes[data_type](value, ap_handler)
            return ap_handler.com.get_corba_representation(ap_object)
        elif data_type == 'void':
            return value
        elif value is None:
            # TODO. her må vi bestemme oss for noe. lage en egen exception for dette kanskje,
            # siden det verdier faktisk kan være None
            print 'warning. trying to return None'
            raise TypeError('cant convert None')
        else:
            return value

    convert_to_corba = classmethod(convert_to_corba)

    def convert_from_corba(cls, value, data_type):
        if data_type.endswith('Seq'):
            return [cls.convert_from_corba(i, data_type[:-3]) for i in value]
        elif data_type in cls.classes:
            return value.gro_object
        else:
            return value

    convert_from_corba = classmethod(convert_from_corba)

    def __init__(self, com, username, password):
        self.client = self.login(username, password)
        self.username = username
        self.com = com

    def login(self, username, password):
        """Login the user with the username and password.
        """
        # We will always throw the same exception in here.
        # this is important

        exception = Errors.LoginError('Wrong username or password')

        # Check username
        for char in ['*','?']:
            if char in username or char in password:
                raise exception

        search = Account.create_search_class()() # FIXME: midlertidig. hente ut fra GroRegistry
        search.set_name(username)
        unames = search.search()
        if len(unames) != 1:
            raise exception
        account = unames[0]

        # Check password
        if not account.authenticate(password):
            raise exception

        # Check quarantines
        if account.is_quarantined():
            raise exception

        # Log successfull login..
        
        return account
    
    def get_username(self):
        """Returns the username of the client.
        """
        return self.username

    def register_gro_class(cls, gro_class):
        gro_class.build_methods()
        name = gro_class.__name__

        method_name = 'get_%s' % name.lower()
        method_impl = create_ap_handler_get_method(name)
        method = Method(method_name, name, [(i.name, i.data_type) for i in gro_class.primary])

        cls.method_slots.append(method)
        cls.gro_classes[name] = gro_class
        setattr(cls, method_name, method_impl)

    register_gro_class = classmethod(register_gro_class)

    def create_idl(cls):
        txt = 'typedef sequence<string> stringSeq;\n'
        txt += 'typedef sequence<long> longSeq;\n'
        txt += 'typedef sequence<float> floatSeq;\n'
        txt += 'typedef sequence<boolean> booleanSeq;\n'

        defined = []
        for gro_class in cls.gro_classes.values():
            txt += gro_class.create_idl_header(defined)
            
        for gro_class in cls.gro_classes.values():
            txt += gro_class.create_idl_interface()

        tmp = cls.create_idl_interface()
        txt += tmp
        
        return 'module %s {\n\t%s\n};' % ('generated', txt)

    create_idl = classmethod(create_idl)

    def build_classes(cls):
        idl_string = cls.create_idl()
        omniORB.importIDLString(idl_string)
        import generated__POA
        for name, gro_class in cls.gro_classes.items():
            idl_class = getattr(generated__POA, name)
            ap_class = APClass.create_ap_class(gro_class, idl_class)
            cls.classes[name] = ap_class

    build_classes = classmethod(build_classes)

    def create_ap_handler_impl(cls):
        import generated__POA
        class APHandlerImpl(cls, generated__POA.APHandler):
            pass
        return APHandlerImpl

    create_ap_handler_impl = classmethod(create_ap_handler_impl)

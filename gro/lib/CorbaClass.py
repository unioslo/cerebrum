import Communication

from classes.Builder import Method
from classes.Dumpable import Struct
from classes.Auth import AuthOperationType

# FIXME: weakref her?
class_cache = {}
object_cache = {}

corba_types = [int, str, bool, None]
corba_structs = {}

def convert_to_corba(obj, transaction, data_type):
    if obj is None and data_type is not None:
        raise TypeError("Can't convert None, should be %s" % data_type)
    elif data_type in corba_types:
        return obj
    elif isinstance(data_type, Struct):
        data_type = data_type.data_type
        struct = corba_structs[data_type]

        vargs = {}
        vargs['reference'] = convert_to_corba(obj['reference'], transaction, data_type)

        for attr in data_type.slots + [i for i in data_type.method_slots if not i.write]:
            if attr.name in obj:
                value = convert_to_corba(obj[attr.name], transaction, attr.data_type)
            else:
                if attr.data_type == int:
                    value = 0
                elif attr.data_type == str:
                    value = ''
                elif attr.data_type == bool:
                    value = False
                elif type(attr.data_type) == list:
                    value = []
                elif attr.data_type in class_cache:
                    value = None
                else:
                    raise TypeError("Can't convert attribute %s in %s to nil" % (attr, data_type))
            vargs[attr.name] = value

        return struct(**vargs)

    elif type(data_type) == list:
        return [convert_to_corba(i, transaction, data_type[0]) for i in obj]

    elif data_type in class_cache:
        # corba casting
        if obj.__class__ in data_type.builder_children:
            data_type = obj.__class__

        corba_class = class_cache[data_type]
        key = (corba_class, transaction, obj)
        if key in object_cache:
            return object_cache[key]

        com = Communication.get_communication()
        corba_object = com.servant_to_reference(corba_class(obj, transaction))
        object_cache[key] = corba_object
        return corba_object
    else:
        raise TypeError('unknown data_type', data_type)

def convert_from_corba(obj, data_type):
    if data_type in corba_types:
        return obj
    elif type(data_type) == list:
        return [convert_from_corba(i, data_type[0]) for i in obj]
    elif data_type in class_cache:
        corba_class = class_cache[data_type]
        com = Communication.get_communication()
        return com.reference_to_servant(obj).gro_object

def create_corba_method(method):
    args_table = {}
    for name, data_type in method.args:
        args_table[name] = data_type
        
    def corba_method(self, *corba_args, **corba_vargs):
        if len(corba_args) + len(corba_vargs) > len(args_table):
            raise TypeError('too many arguments')

        # Auth

        class_name = self.gro_class.__name__
        operator = self.transaction.get_client()
        operation_name = '%s.%s' % (class_name, method.name)
        try:
            operation_type = AuthOperationType(name=operation_name)
        except Exception, e:
            # FIXME: kaste en exception
            # print 'no operation_type defined for %s' % operation_name
            operation_type = None

        # FIXME: bruk isinstance eller issubclass
        if hasattr(self.gro_object, 'check_permission'):
            if self.gro_object.check_permission(operator, operation_type):
                print operation_name, 'access granted'
            else:
                # FIXME: kaste en exception
                # print operation_name, 'access denied' 
                pass
        else:
            # FIXME: kaste en exception
            pass

        # Transaction
        if self.transaction is not None:
            if method.write:
                self.gro_object.lock_for_writing(self.transaction)
            else:
                self.gro_object.lock_for_reading(self.transaction)
            self.transaction.add_ref(self.gro_object)

        elif not method.write:
            if self.gro_object.get_writelock_holder() is not None:
                self.gro_object = self.gro_class(*self.gro_object.get_primary_key(), **{'nocache':True})

        else:
            raise Exception('Trying to access write-method outside a transaction: %s' % method)


        # convert corba arguments to real arguments
        args = []
        for value, (name, data_type) in zip(corba_args, method.args):
            args.append(convert_from_corba(value, data_type))

        vargs = {}
        for name, value in corba_vargs:
            data_type = args_table[name]
            vargs[name] = convert_from_corba(value, data_type)

        # run the real method
        value = getattr(self.gro_object, method.name)(*args, **vargs)
        if method.write:
            self.gro_object.save()

        return convert_to_corba(value, self.transaction, method.data_type)

    return corba_method

class CorbaClass:
    def __init__(self, gro_object, transaction):
        self.gro_object = gro_object
        self.transaction = transaction

def register_gro_class(gro_class, idl_class, idl_struct):
    name = gro_class.__name__
    corba_class_name = 'Spine' + name

    corba_structs[gro_class] = idl_struct

    exec 'class %s(CorbaClass, idl_class):\n\tpass\ncorba_class = %s' % (
        corba_class_name, corba_class_name)

    corba_class.gro_class = gro_class

    for attr in gro_class.slots:
        get_name = 'get_' + attr.name
        get = Method(get_name, attr.data_type)

        setattr(corba_class, get_name, create_corba_method(get))

        if attr.write:
            set_name = 'set_' + attr.name
            set = Method(set_name, None, [(attr.name, attr.data_type)], write=True)

            setattr(corba_class, set_name, create_corba_method(set))

    for method in gro_class.method_slots:
        setattr(corba_class, method.name, create_corba_method(method))

    class_cache[gro_class] = corba_class

# arch-tag: 0503a6a6-0d9f-4a47-9299-1763270ff257

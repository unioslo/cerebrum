import Communication

from classes.Builder import Method

# FIXME: weakref her?
class_cache = {}
object_cache = {}

corba_types = [int, str, bool, None]

def convert_to_corba(obj, transaction, data_type, sequence):
    def convert(obj, data_type):
        # ugly hack to make casting work with Entity
        if data_type.__name__ == 'Entity':
            data_type = obj.__class__

        if obj is None and data_type is not None:
            raise TypeError('cant convert None')
        elif data_type in corba_types:
            return obj
        elif data_type in class_cache:
            corba_class = class_cache[data_type]
            key = (corba_class, transaction, obj)
            if key in object_cache:
                corba_object = object_cache[key]
            else:
                corba_object = corba_class(obj, transaction)

            com = Communication.get_communication()
            return com.servant_to_reference(corba_object)
        else:
            raise TypeError('unknown data_type', data_type)

    if sequence:
        return [convert(i, data_type) for i in obj]
    else:
        return convert(obj, data_type)

def convert_from_corba(corba_obj, data_type, sequence):
    def convert(obj):
        if data_type in corba_types:
            return obj
        elif data_type in class_cache:
            corba_class = class_cache[data_type]
            com = Communication.get_communication()
            return com.reference_to_servant(obj).gro_object

    if sequence:
        return [convert(i) for i in obj]
    else:
        return convert(corba_obj)

from classes import Registry
registry = Registry.get_registry()

def create_corba_method(method):
    args_table = {}
    for name, data_type, sequence in method.args:
        args_table[name] = data_type, sequence
        
    def corba_method(self, *corba_args, **corba_vargs):
        if len(corba_args) + len(corba_vargs) > len(args_table):
            raise TypeError('too many arguments')

        # Auth

        """
        # FIXME: avhengighet til registry er teit her.
        # må lage en metode som gjør jobbe i GroBuilder.
        class_name = self.gro_object.__class__.__name__
        operation_type = registry.AuthOperationType('%s.%s' % (class_name, method.name))
        operator = self.transaction.get_client()
        try:
            if self.gro_object.check_permission(operator, operation_type):
                print 'access granted'
            else:
                print 'access denied'
        except Exception, e:
            print 'warning check_permission(', operator , ', ', operation_type, ') failed:', e
            print 'access denied'
        """

        # Transaction
        if method.write:
            self.gro_object.lock_for_writing(self.transaction)
        else:
            self.gro_object.lock_for_reading(self.transaction)

        self.transaction.add_ref(self.gro_object)

        # convert corba arguments to real arguments
        args = []
        for value, (name, data_type, sequence) in zip(corba_args, method.args):
            args.append(convert_from_corba(value, data_type, sequence))

        vargs = {}
        for name, value in corba_vargs:
            data_type, sequence = args_table[name]
            vargs[name] = convert_from_corba(value, data_type, sequence)

        # run the real method
        value = getattr(self.gro_object, method.name)(*args, **vargs)
        if method.write:
            self.gro_object.save()

        return convert_to_corba(value, self.transaction, method.data_type, method.sequence)

    return corba_method

class CorbaClass:
    def __init__(self, gro_object, transaction):
        self.gro_object = gro_object
        self.transaction = transaction

def register_gro_class(gro_class, idl_class):
    name = gro_class.__name__
    corba_class_name = 'AP' + name

    exec 'class %s(CorbaClass, idl_class):\n\tpass\ncorba_class = %s' % (
        corba_class_name, corba_class_name)

    for attr in gro_class.slots:
        get_name = 'get_' + attr.name
        get = Method(get_name, attr.data_type, attr.sequence)

        setattr(corba_class, get_name, create_corba_method(get))

        if attr.write:
            set_name = 'set_' + attr.name
            set = Method(set_name, None, False, [(attr.name, attr.data_type, attr.sequence)])

            setattr(corba_class, set_name, create_corba_method(set))

    for method in gro_class.method_slots:
        setattr(corba_class, method.name, create_corba_method(method))

    class_cache[gro_class] = corba_class

# arch-tag: 0503a6a6-0d9f-4a47-9299-1763270ff257

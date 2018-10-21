import cerebrum_path
import cereconf
from Cerebrum.Utils import dyn_import
from Cerebrum.extlib.doc_exception import DocstringException
from Cerebrum.extlib.doc_exception import ProgrammingError

#
# Create sito OU factory class
#
class sitoFactory(object):
    @classmethod
    def get(cls,comp):
        components = {'sito_ou' : 'CLASS_SITO_OU'}
        try:
            conf_var = components[comp]
        except KeyError:
            raise ValueError, "Unknown component %r" % comp
        import_spec = getattr(cereconf, conf_var)
        if not isinstance(import_spec, (tuple, list)):
            raise ValueError, \
                  "Invalid import spec for component %s: %r" % (comp,
                                                                import_spec)
        bases = []
        for c in import_spec:
            (mod_name, class_name) = c.split("/", 1)
            mod = dyn_import(mod_name)
            cls = getattr(mod, class_name)
            # The cereconf.CLASS_* tuples control which classes
            # are used to construct a Factory product class.
            # Order inside such a tuple is significant for the
            # product class's method resolution order.
            #
            # A likely misconfiguration is to list a class A as
            # class_tuple[N], and a subclass of A as
            # class_tuple[N+x], as that would mean the subclass
            # won't override any of A's methods.
            #
            # The following code should ensure that this form of
            # misconfiguration won't be used.
            for override in bases:
                if issubclass(cls, override):
                    raise RuntimeError, \
                          ("Class %r should appear earlier in"
                           " abcconf.%s, as it's a subclass of"
                           " class %r." % (cls, conf_var, override))
            bases.append(cls)
        if len(bases) == 1:
            comp_class = bases[0]
        else:
            # Dynamically construct a new class that inherits from
            # all the specified classes.  The name of the created
            # class is the same as the component name with a
            # prefix of "_dynamic_"; the prefix is there to reduce
            # the probability of `auto_super` name collision
            # problems.
            comp_class = type('_dynamic_' + str(comp), tuple(bases), {})
        #print "comp_class:%s" % (comp_class)
        return comp_class

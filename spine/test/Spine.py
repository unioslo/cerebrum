import sys

sys.path = ["/home/havarden/install/lib/python2.2/site-packages"] + sys.path
sys.path.append('/home/havarden/install/etc/cerebrum')

import sys
import os
import omniORB
import CosNaming
import ConfigParser
import urllib
from omniORB import CORBA, sslTP

config = ConfigParser.ConfigParser()
config.read(('test.conf.template', 'test.conf'))

sslTP.certificate_authority_file(config.get('ssl', 'ca_file'))
sslTP.key_file(config.get('ssl', 'key_file'))
sslTP.key_file_password(config.get('ssl', 'password'))

idl_path = config.get('idl', 'path')
idl_spine = os.path.join(idl_path, config.get('idl', 'spine'))
idl_errors = os.path.join(idl_path, config.get('idl', 'errors'))

def connect(args=[]):
    """ 
    Method for connecting to a CORBA name service
    and fetch the Gro object. The method prefers
    SSL connections.
    """
    orb = CORBA.ORB_init(args + ['-ORBendPoint', 'giop:ssl::'], CORBA.ORB_ID)
    # Get the name service and narrow the root context
    obj = orb.resolve_initial_references("NameService")
    rootContext = obj._narrow(CosNaming.NamingContext)

    if rootContext is None:
        raise Exception("Could not narrow the root naming context")

    # Fetch spine using the name service
#    name = [CosNaming.NameComponent(config.get('corba', 'context'),
#                                    config.get('corba', 'service')),
#            CosNaming.NameComponent(config.get('corba', 'object'), "")]
#
#    obj = rootContext.resolve(name)
#    spine = obj._narrow(Cerebrum_core.Gro)
#    if spine is None or obj is None:
#        raise Exception("Could not narrow the Spine object")
    ior = urllib.urlopen(config.get('corba', 'url')).read()
    obj = orb.string_to_object(ior)
    spine = obj._narrow(Cerebrum_core.Spine)

    return spine

if config.getboolean('spine', 'cache'):
    # add tmp path to sys.path if it doesnt exists
    cache_dir = config.get('spine', 'cache_dir')
    if cache_dir not in sys.path:
        sys.path.append(cache_dir)

    try:
        import Cerebrum_core
    except:
        os.system('omniidl -bpython -C %s %s %s' % (cache_dir, idl_spine, idl_errors))
        import Cerebrum_core

    try:
        import generated
    except:
        spine = connect()
        source = spine.get_idl()
        generated = os.path.join(cache_dir, 'generated.idl')
        fd = open(generated, 'w')
        fd.write(source)
        fd.close()
        os.system('omniidl -bpython -C %s -I%s %s' % (cache_dir, idl_path, generated))
        import generated
else:
    omniORB.importIDL(idl_spine)
    omniORB.importIDL(idl_errors)
    import Cerebrum_core

    idl = connect().get_idl()
    omniORB.importIDLString(idl, ['-I' + idl_path])
    import generated

# arch-tag: abe7c858-0c12-4741-b8ca-3d5301f3816a

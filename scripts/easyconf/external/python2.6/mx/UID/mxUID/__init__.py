from mxUID import *
from mxUID import __version__

### Python part of module initialization

# Set IDs
def _init():
    global _hostid
    import os,string,time
    try:
        # Try to use the IP address as host id
        import socket
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except socket.error:
            raise ImportError, 'no network connection'
        ip = map(int, string.split(ip, '.'))
        _hostid = reduce(lambda x,y: (x+y) % 65536, ip)
    except ImportError:
        try:
            # Use the data from the root stat as host id
            _hostid = reduce(lambda x,y: (x+y) % 65536, os.stat(os.sep))
        except os.error:
            # Fallback to a constant
            _hostid = 0x2003
    # -559038737 == 0xdeadbeef
    setids(_hostid, os.getpid(), -559038737 & long(time.time() / 1000))

_init()

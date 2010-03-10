from ceresync import config
import ConfigParser
from ceresync import errors
import unittest
import os
import errno
import signal
import atexit
import types
import sys
import stat
import time

from httplib import HTTPConnection
from M2Crypto import SSL
from ceresync.SignatureHandler import SignatureHandler

from ceresync import cerews_services

from ZSI import FaultException

log = config.logger


try:
    from ceresync.dom import DomletteReader as ReaderClass
except ImportError, e:
    log.warn("Could not import DomletteReader.  Install 4Suite for extra performance.")
    from xml.dom import expatbuilder
    class ReaderClass(object):
        fromString = staticmethod(expatbuilder.parseString)
        fromStream = staticmethod(expatbuilder.parse)

class AlreadyRunning(Exception):
    """Thrown when the client is already running and the pid file exists"""
    def __init__(self, pidfile, pidfile_mtime):
        self.pidfile = pidfile
        Exception.__init__(self, "Already running for %s secs with pid file %s" % (int(time.time() - pidfile_mtime), pidfile))

class AlreadyRunningWarning(AlreadyRunning):
    """Thrown when the client is already running and the pid file exists,
    but has been running for less than an hour."""
    pass


def create_pidfile(pid_file):
    # I don't like setting sighandlers in such a hidden location, but I
    # didn't know of any better place to put it. The sighandler is required
    # because atexit doesn't work when the program is killed by a signal.
    oldhandler = signal.getsignal(signal.SIGTERM)
    def termhandler(signum, frame):
        print >>sys.stderr, "Killed by signal %d" % signum
        remove_pidfile(pid_file)
        if type(oldhandler) == types.FunctionType:
            oldhandler()
        elif oldhandler != signal.SIG_IGN:
            # Is this correct? sys.exit(1) here caused random segfaults,
            # but this might skip som cleanup stuff.
            os._exit(1)
    signal.signal(signal.SIGTERM, termhandler)
    
    pid_dir = os.path.dirname(pid_file)
    if not os.path.isdir(pid_dir):
        try:
            os.makedirs(pid_dir, 0755)
        except:
            pass # fdopen below will give a better error message
    
    try:
        pidfile = os.fdopen(os.open(pid_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL), 'w')
        # Make sure the pid file is removed when exiting.
        atexit.register(remove_pidfile, pid_file)
    except OSError, e:
        if e.errno == errno.EEXIST:
            try:
                mtime = os.stat(e.filename)[stat.ST_MTIME]
            except OSError, e:
                if e.errno == errno.ENOENT:
                    # Pidfile has been removed since we tried to create it.
                    # Warn and ignore.
                    raise AlreadyRunningWarning(e.filename, None)
                else:
                    raise
            if time.time() - mtime < 3600:
                # e.filename is less than an hour old. Just warn.
                raise AlreadyRunningWarning(e.filename, mtime)
            raise AlreadyRunning(e.filename, mtime)
        else:
            raise
    
    pidfile.write(str(os.getpid()) + "\n")
    pidfile.close()
    log.debug("Created pid file " + pid_file)
    return pid_file

def remove_pidfile(pid_file):
    if not os.path.exists(pid_file):
        return # File doesn't exist, nothing to do
    try:
        os.remove(pid_file)
    except OSError, e:
        # "No such file or directory" is OK, other errors are not
        if e.errno != errno.ENOENT:
            raise
    log.debug("Removed pid file " + pid_file)

class Entity(object):
    entity_type= ""
    attributes= []
    lists= {}
    def __init__(self, obj, encode_to=None):
        # Set attributes from the response, set '' for missing.
        for key in self.attributes:
            value = obj._attrs.get(key, '')
            if encode_to and type(value) == unicode:
                value = value.encode(encode_to)
            self.__setattr__(key, value)

        # Set lists, if any
        for objkey, entkey in self.lists.items():
            self.__setattr__(entkey, getattr(obj, objkey, []))
        config.apply_override(self, self.entity_type)
        config.apply_default(self, self.entity_type)
        if 'quarantines' in self.lists.values():
            config.apply_quarantine(self, self.entity_type)
    def __str__(self):
        return "%s(%s)" % (
            self.__class__.__name__,
            ", ".join(["%s=%s"%(k,repr(v)) for k,v in self.__dict__.items()])
        )
    def __repr__(self):
        return self.__str__()

class Account(Entity):
    entity_type= "account"
    attributes= [
        "name","passwd","homedir","home","disk_path","disk_host",
        "gecos","full_name","shell","shell_name","posix_uid",
        "posix_gid","primary_group","owner_id","owner_group_name",
        "primary_affiliation","primary_ou_id",
    ]
    lists= { "_quarantine": "quarantines", }

class Group(Entity):
    entity_type= "group"
    attributes= [
        "name","posix_gid",
    ]
    lists= { "_quarantine": "quarantines", "_member": "members", }
    
class Ou(Entity):
    entity_type= "ou"
    attributes= [
        "id","name","acronym","short_name","display_name","sort_name",
        "parent_id","email","url","phone","post_address","stedkode",
        "parent_stedkode",
    ]
    lists= { "_quarantine": "quarantines", }

class Alias(Entity):
    entity_type= "alias"
    attributes= [
        "local_part","domain","primary_address_local_part",
        "primary_address_domain","address_id","primary_address_id",
        "server_name","account_id","account_name",
    ]

class Homedir(Entity):
    entity_type= "homedir"
    attributes= [
        "homedir_id","disk_path","home","homedir","account_name",
        "posix_uid","posix_gid",
    ]

class Person(Entity):
    entity_type= "person"
    attributes= [
        "id", "export_id", "type", "birth_date", "nin", "first_name", 
        "last_name", "full_name", "display_name", "work_title", 
        "primary_account", "primary_account_name",
        "primary_account_password", "email", "address_text", "city",
        "postal_number", "phone", "url", "primary_affiliation",
        "primary_ou_id", "keycardid0", "keycardid1",
    ]
    lists= { 
        "_quarantine": "quarantines", 
        "_affiliation": "affiliations",
        "_trait": "traits", 
    }

class Affiliation(Entity):
    entity_type= "affiliation"
    attributes= [
        "affiliation", "ou_id", "status",
    ]

class CeresyncHTTPSConnection(HTTPConnection):
    def __init__(self, host, port=443, strict=None):
        HTTPConnection.__init__(self, host, port, strict)
        self.ctx= None
        self.sock= None
        self.ca_path= config.get("cerews", "ca_path", allow_none=True)
        self.ca_file= config.get("cerews", "ca_file", allow_none=True)
        if self.ca_path is None and self.ca_file is None:
            log.error("Missing path to CA certificates. Add ca_path or ca_file under [cerews]")
            exit(1)
        self.host = host
        self.port = port
        if ':' in self.host:
            tab = self.host.split(':')
            self.host = tab[0]
            self.port = int(tab[1])
    def connect(self):
        "Connect to a host on a given (SSL) port."
        self._init_ssl()
        sock = SSL.Connection(self.ctx)
        sock.connect((self.host, self.port))
        #server_cert = sock.get_peer_cert()
        self.sock= sock
    def _init_ssl(self):
        ctx = SSL.Context('sslv23')
        ctx.load_verify_info(cafile=self.ca_file, capath=self.ca_path)
        ## typical options for a client
        ctx.set_options(SSL.op_no_sslv2)
        ctx.set_verify((SSL.verify_fail_if_no_peer_cert|SSL.verify_peer), 9)
        self.ctx= ctx

class Sync(object):
    def __init__(self, locking=True):
        # Create a pid file, and store the file name for use in the destructor
        # Make sure self.pid_file exists, in case create_pidfile() fails.
        self.pid_file = None 

        if locking:
            self.pid_file = create_pidfile(
                    config.get("sync","pid_file","/var/run/cerebrum/ceresync.pid"))

        try:
            self.username= config.get("cerews","login")
            self.password= config.get("cerews","password")
            self.url= config.get("cerews","url")
        except ConfigParser.Error, e:
            log.error("Missing url, login or password: %s",e)
            sys.exit(1)


        self.zsi_options= {
                "readerclass": ReaderClass,
                #"tracefile": file("/var/log/cerebrum/cerewstrace.log","w"),
                "transport": CeresyncHTTPSConnection,
                #"auth": (AUTH.none,),
                #"host": "localhost",
                #"ns": ...,
                #"nsdict": {},
                #"port": 443,
                #"soapaction": "http://www.zolera.com",
                #"ssl", 0,
                #"url": ...,
        }

    def __del__(self):
        if self.pid_file:
            remove_pidfile(self.pid_file)
    
    def _get_ceresync_port(self, useDigest=False):
        locator= cerews_services.cerewsLocator()
        port= locator.getcerewsPortType(url=self.url, **self.zsi_options)
        port.binding.sig_handler= SignatureHandler(self.username, 
                                                   self.password,
                                                   useDigest)
        return port

    def get_changelogid(self):
        request=cerews_services.getChangelogidRequest()
        port= self._get_ceresync_port()
        try:
            return port.get_changelogid(request)
        except FaultException, e:
            log.error("get_changelogid: %s", e.fault.detail[0].string)
            sys.exit(1)

    def get_accounts(self, accountspread=None, auth_type=None, incr_from=None,
                     encode_to=None, account_xml_in=None, account_xml_out=None,
                     include_affiliations=False, **kwargs):
        """
        encode_to is a valid string encoding that the unicode attributes we get
        from ZSI will be encoded to.  If it's None the attributes remain
        unicode.  If it's utf-8 or latin-1, then the attribute will be a str
        encoded to the given encoding.
        """
        try:
            accountspread = accountspread or config.get("sync","account_spread")
        except ConfigParser.Error, e:
            log.error("Missing account_spread: %s",e)
            sys.exit(1)
        try:
            auth_type = auth_type or config.get("sync","auth_type")
        except ConfigParser.Error, e:
            log.error("Missing auth_type: %s", e)
            sys.exit(1)
        request = cerews_services.getAccountsRequest()
        request._accountspread = accountspread
        request._auth_type = auth_type
        request._incremental_from = incr_from
        request._include_affiliations = include_affiliations
        port = self._get_ceresync_port()
        response = self._perform_request(request, port.get_accounts,
                                         load_file=account_xml_in,
                                         save_file=account_xml_out)
        return [Account(obj, encode_to=encode_to) for obj in response._account]

    def get_groups(self, accountspread=None, groupspread=None, incr_from=None,
                   encode_to=None, group_xml_in=None, group_xml_out=None,
                   **kwargs):
        try: 
            accountspread= accountspread or config.get("sync","account_spread")
        except ConfigParser.Error, e:
            log.error("Missing account_spread: %s",e)
            sys.exit(1)
        try:
            groupspread= groupspread or config.get("sync","group_spread")
        except ConfigParser.Error, e:
            log.error("Missing group_spread: %s",e)
            sys.exit(1)
        request= cerews_services.getGroupsRequest()
        request._accountspread= accountspread
        request._groupspread= groupspread
        request._incremental_from= incr_from
        port= self._get_ceresync_port()
        response = self._perform_request(request, port.get_groups,
                                         load_file=group_xml_in,
                                         save_file=group_xml_out)
        return [Group(obj, encode_to=encode_to) for obj in response._group]

    def get_ous(self, incr_from=None, encode_to=None,
                ou_xml_in=None, ou_xml_out=None, **kwargs):
        request= cerews_services.getOUsRequest()
        request._incremental_from= incr_from
        port= self._get_ceresync_port()
        response = self._perform_request(request, port.get_ous,
                                         load_file=ou_xml_in,
                                         save_file=ou_xml_out)
        return [Ou(obj, encode_to=encode_to) for obj in response._ou]

    def get_persons(self, personspread=None, incr_from=None, encode_to=None,
                    person_xml_in=None, person_xml_out=None, **kwargs):
        personspread= personspread or \
            config.get("sync", "person_spread", allow_none=True)
        request= cerews_services.getPersonsRequest()
        request._personspread= personspread
        request._incremental_from= incr_from
        port= self._get_ceresync_port()
        response = self._perform_request(request, port.get_persons,
                                         load_file=person_xml_in,
                                         save_file=person_xml_out)
        return [Person(obj, encode_to=encode_to) for obj in response._person]

    def get_aliases(self, emailserver=None, incr_from=None, encode_to=None,
                    alias_xml_in=None, alias_xml_out=None, **kwargs):
        request= cerews_services.getAliasesRequest()
        request._incremental_from = incr_from
        if emailserver is not None:
            request._emailserver = emailserver
        port= self._get_ceresync_port()
        response = self._perform_request(request, port.get_aliases,
                                         load_file=alias_xml_in,
                                         save_file=alias_xml_out)
        return [Alias(obj, encode_to=encode_to) for obj in response._alias]
       
    def get_homedirs(self, status, hostname, encode_to=None,
                     homedir_xml_in=None, homedir_xml_out=None, **kwargs):
        request= cerews_services.getHomedirsRequest()
        request._status= status
        request._hostname= hostname
        port= self._get_ceresync_port()
        response = self._perform_request(request, port.get_homedirs,
                                         load_file=homedir_xml_in,
                                         save_file=homedir_xml_out)
        return [Homedir(obj, encode_to=encode_to) for obj in response._homedir]

    def _perform_request(self, request, method, load_file=None, save_file=None):
        """
        load_file is the name of a file containing the xml that should be
        injected into the ZSI framework.  This will cause ZSI to believe that
        it received the given xml from the server.

        save_file is the name a file that should be filled with the xml
        received from the server
        """
        try:
            port = method.im_self

            if load_file:
                port.binding.data = open(load_file).read()
                port.binding.IsSOAP = lambda: True

                name = request.__class__.__name__.replace("Request_Holder", "Response")
                response = getattr(cerews_services, name)
                return port.binding.Receive(
                    response.typecode)

            response= method(request)

            if save_file:
                open(save_file, 'w').write(port.binding.data)

            return response
        except FaultException, e:
            log.error("%s: %s", method.__name__, e.fault.detail[0].string)
            sys.exit(1)

    def set_homedir_status(self, homedir_id, status):
        request= cerews_services.setHomedirStatusRequest()
        request._homedir_id= homedir_id
        request._status= status
        port= self._get_ceresync_port()
        try:
            response= port.set_homedir_status(request)
        except FaultException, e:
            log.error("set_homedir_status: %s", e.fault.detail[0].string)
            sys.exit(1)


# In windows, the only way to get stdout, stdin and return value from a process
# is with using subprocess. Subprocess is not available under Python 2.3, so to
# also be able to support Python 2.3 (on Unix at least), we make a wrapper
# class using either subprocess or popen.Popen3
try:
    import subprocess
except ImportError:
    try:
        from popen2 import Popen3
    except ImportError:
        log.error("Neither subprocess nor a usable popen2 module was found.")
        sys.exit(1)
    class Process(object):
        def __init__(self, cmd):
            self.p= Popen3(cmd, capturestderr=True)
        def write(self, message):
            self.p.tochild.write(message)
            self.p.tochild.close()
        def read(self):
            return self.p.fromchild.read()
        def wait(self):
            return self.p.wait()
        def error(self):
            return self.p.childerr.read()
else:
    class Process(object):
        def __init__(self, cmd):
            PIPE= subprocess.PIPE
            self.p= subprocess.Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        def write(self, message):
            self.p.stdin.write(message)
            self.p.stdin.close()
        def read(self):
            return self.p.stdout.read()
        def wait(self):
            return self.p.wait()
        def error(self):
            return self.p.stderr.read()

class Pgp:
    def __init__(self, pgp_prog=None, enc_opts='', dec_opts='', keyid=None):
        try: 
            pgp_prog= pgp_prog or config.get('pgp', 'prog')
            enc_opts= enc_opts or config.get('pgp', 'encrypt_opts')
            dec_opts= dec_opts or config.get('pgp', 'decrypt_opts')
            keyid= keyid or config.get('pgp', 'keyid')
        except ConfigParser.Error, e:
            log.error("Missing PGP configuration: %s",e)
            sys.exit(1)

        self.pgp_enc_cmd= [ pgp_prog,
            '--recipient', keyid,
            '--default-key', keyid,
        ] + enc_opts.split()
        self.pgp_dec_cmd= [pgp_prog] + dec_opts.split()
    def decrypt(self, cryptstring):
        if not cryptstring:
            return None
        p= Process(self.pgp_dec_cmd)
        try:
            p.write(cryptstring)
        except IOError, e:
            log.error(p.error())
            sys.exit(1)
        message= p.read()
        if p.wait() != 0:
            log.error(p.error())
            sys.exit(1)
        return message
    def encrypt(self, message):
        if not message:
            return None
        p= Process(self.pgp_enc_cmd)
        try:
            p.write(message)
        except IOError, e:
            log.error(p.error())
            sys.exit(1)
        cryptstring= p.read()
        if p.wait() != 0:
            log.error(p.error())
            sys.exit(1)
        return cryptstring

class PgpTestCase(unittest.TestCase):
    def setUp(self):
        self.p= Pgp()
        self.message= 'FooX123.-=/'

    def testEncrypt(self):
        e= self.p.encrypt(self.message).strip()
        assert e.startswith('-----BEGIN PGP MESSAGE-----') and \
            e.endswith('-----END PGP MESSAGE-----')

    def testEncryptDecrypt(self):
        cryptstring= self.p.encrypt(self.message)
        assert self.message == self.p.decrypt(cryptstring), \
                'encryption and decryption yield wrong result'

if __name__ == '__main__':
    unittest.main()

from threading import Lock
import xmlrpclib
import re

# these methods are available directly under the _server connection
# argument.
XMLRPC_METHODS = """login logout get_commands get_format_suggestion
                    help run_command get_default_param 
                    call_prompt_func""".split()
# Of these methods, these do NOT take the session ID as their first
# argument
WITHOUT_SESSION = "login get_format_suggestion".split()

class ServerConnection:
    _url = "http://localhost:8000/"
    _encoding = "iso-8859-1"
    _server = None
    _serverLock = Lock()
    _acquire = _serverLock.acquire
    _release = _serverLock.release
    
    def __init__(self, user, password):
        self._checkConnection()
        self._registerRPCCommands()
        self._login(user, password)
        self._registerRunCommands()

    def _checkConnection(cls):    
        cls._acquire()
        try:
            if cls._server is None:
                cls._server = xmlrpclib.Server(cls._url, encoding=cls._encoding)
        finally:
            cls._release()

    _checkConnection = classmethod(_checkConnection)
    
    def _login(self, user, password):
        self._session = self.login(user, password)
    
    def _helpMethod(self, methodname):
        """"Generates the __doc__ body for the methodname"""
        try:
            helpnames = methodname.split("_")
            help = self.help(*helpnames)
            help = help.strip() 
            help = help.split(":")[-1]
            help = help.strip() # again!
            doc = [help, ""]
        except:
            doc = []
        try:
            parameters = self._commands[methodname][1]
        except IndexError:
            parameters = [] # none!
        else:
            doc.append("Parameters:")
            doc.append("")
        count = 0
        for parameter in parameters:
            if type(parameter) in (str, unicode):
                doc.append(parameter)
                continue

            count += 1
            name = parameter.get('help_ref')
            if not name:
                name = "param%s" % count
            typename = parameter.get('type', '')
            if typename:
                typename = " [%s]" % typename
            desc = re.sub(r"^Enter ", "", parameter.get('prompt', ''))
            doc.append(name + typename)
            if desc:
                doc.append("    " + desc)
        doc = '\n'.join(doc)              
        # hmm..
        if type(doc) == unicode:
            doc = doc.encode("iso8859-1", "replace")
        return doc    
        
        
    def _runMethod(self, methodname, *args):
        if methodname not in WITHOUT_SESSION:
            # Add the session ID as the first argument 
            args = (self._session,) + args
        self._acquire()
        try:
            method = getattr(self._server, methodname)
            return method(*args)
        finally:
            self._release()
         
    def _registerRPCCommands(self):
        """Registers known commands as methods on self. 
           Note that available commands vary with the rights of
           the current user, that's why these methods are set on
           self instead of cls."""
            # Those methods the server accepts natively
            # (ie. not behind run_command) - we'll wrap it to
            # get locking, and make sure we store the method.
        for command in XMLRPC_METHODS:
            
            # This lambda could have been used instead of the 
            # class below!
            ##func = (lambda methodname: 
            ##    lambda *args: self._runMethod(methodname, *args))(command)
            ##func.__doc__ = command + "\n"

            # Prepare the fake function
            class functionWrapper(staticmethod):
                def __init__(self, serverconn, methodname):
                    # Stores the ServerConnection for back-calling
                    self.serverconn = serverconn
                    self.methodname = methodname
                def __call__(self, *args):
                    return self.serverconn._runMethod(self.methodname, *args)
                __name__ = command        
            func = functionWrapper(self, command)        
            setattr(self, command, func)

    def _registerRunCommands(self):
        """Register Cerebrum commands, which uses
        run_command to takes care of locking, all we need to
        to is to be a function."""
        # NOTE: run_command and get_commands are in XMLRPC_METHODS and
        # must be registered first. (see _registerRPCCommands)
        self._commands = self.get_commands()
        for command in self._commands:
            if command in XMLRPC_METHODS:
                # Overloading those methods could be dangerous
                continue

            # Prepare the fake function
            class functionWrapper(staticmethod):
                def __init__(self, serverconn, methodname):
                    # Stores the ServerConnection for back-calling
                    self.serverconn = serverconn
                    self.methodname = methodname
                def __call__(self, *args):
                    return self.serverconn.run_command(self.methodname, *args)
                def doc(self):
                    return self.serverconn._helpMethod(self.methodname)
                __doc__ = property(doc)    
                __name__ = command
            func = functionWrapper(self, command)        
            setattr(self, command, func)


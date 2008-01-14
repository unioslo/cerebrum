from ceresync import config
import SpineClient
from popen2 import Popen3
import unittest

class Sync:
    def __init__(self, incr=False, id=-1, auth_type=None):
        self.incr=incr
        self.auth_type= auth_type or config.conf.get('sync','auth_type')
        connection = SpineClient.SpineClient(config=config.conf).connect()
        self.session = connection.login(config.conf.get('spine', 'login'),
                                        config.conf.get('spine', 'password'))
        self.tr = self.session.new_transaction()
        self.cmd = self.tr.get_commands()
        self.view = self.tr.get_view()
        account_spread=config.conf.get('sync', 'account_spread')
        group_spread=config.conf.get('sync', 'group_spread')
        
        self.view.set_account_spread(self.tr.get_spread(account_spread))
        self.view.set_group_spread(self.tr.get_spread(group_spread))
        self.view.set_authentication_method(self.tr.get_authentication_type(self.auth_type))
        self.view.set_changelog(id)

    def __del__(self):
        for i in self.session.get_transactions():
            try: i.rollback()
            except: pass
        try: self.session.logout()
        except: pass

    def set_authtype(self, auth_type):
        self.auth_type = auth_type
        self.view.set_authentication_method(self.tr.get_authentication_type(auth_type))

    def _do_get(self, objtype, incr):
        if incr is None:
            incr=self.incr
        if incr:
            m = "get_%ss_cl" % objtype
        else:
            m = "get_%ss" % objtype
        res=[]
        for obj in getattr(self.view, m)():
            obj.type=objtype
            config.apply_override(obj, objtype)
            config.apply_default(obj, obj.type)
            #config.apply_quarantine(obj, obj.type)
            res.append(obj)
        return res
    
    def get_accounts(self, incr=None):
        return self._do_get("account", incr)
        
    def get_groups(self, incr=None):
        return self._do_get("group", incr)

    def get_persons(self, incr=None):
        return self._do_get("person", incr)        

    def get_ous(self, incr=None):
        return self._do_get("ou", incr)
    
    def close(self):
        self.tr.commit()
        self.session.logout()

class Pgp:
    def __init__(self, pgp_prog=None, enc_opts='', dec_opts='', keyid=None):
        # Handle NoOptionError?
        pgp_prog= pgp_prog or config.conf.get('pgp', 'prog')
        enc_opts= enc_opts or config.conf.get('pgp', 'encrypt_opts')
        dec_opts= dec_opts or config.conf.get('pgp', 'decrypt_opts')
        keyid= keyid or config.conf.get('pgp', 'keyid')

        self.pgp_enc_cmd= [ pgp_prog,
            '--recipient', keyid,
            '--default-key', keyid,
        ] + enc_opts.split()
        self.pgp_dec_cmd= [pgp_prog] + dec_opts.split()
    
    def decrypt(self, cryptstring):
        message= cryptstring
        if cryptstring:
            child= Popen3(self.pgp_dec_cmd)
            child.tochild.write(cryptstring)
            child.tochild.close()
            message= child.fromchild.read()
            exit_code= child.wait()
            if exit_code:
                raise IOError, "%r exited with %i" % (self.pgp_dec_cmd,exit_code)
        return message

    def encrypt(self, message):
        child= Popen3(self.pgp_enc_cmd)
        child.tochild.write(message)
        child.tochild.close()
        cryptstring= child.fromchild.read()
        exit_code= child.wait()
        if exit_code:
            raise IOError, "%r exited with %i" % (self.pgp_enc_cmd,exit_code)
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

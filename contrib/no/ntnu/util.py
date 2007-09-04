import config
from popen2 import Popen3
import unittest

def stedkode_string_to_tuple(stedkode):
    """
    Converts a stedkode string to a tuple representing
    (landkode, institusjon, fakultet, institutt, avdeling).
    """
    assert len(stedkode) == 9
    landkode = 0
    institusjon = int(stedkode[:3])
    fakultet = int(stedkode[3:5])
    institutt = int(stedkode[5:7])
    avdeling = int(stedkode[7:])
    return (landkode, institusjon, fakultet, institutt, avdeling)

def find_ou_by_stedkode(stedkode, transaction):
    """
    Searches for the OU with the given stedkode string in Spine, and returns
    the found OU.
    """
    landkode, institusjon, fakultet, institutt, avdeling = stedkode_string_to_tuple(stedkode)
    ou_searcher = transaction.get_ou_searcher()
    ou_searcher.set_landkode(landkode)
    ou_searcher.set_institusjon(institusjon)
    ou_searcher.set_fakultet(fakultet)
    ou_searcher.set_institutt(institutt)
    ou_searcher.set_avdeling(avdeling)
    return ou_searcher.search()

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


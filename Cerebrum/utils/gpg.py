import cereconf

import gpgme
from io import BytesIO


def _unicode2str(obj, encoding='utf-8'):
    """Encode unicode object to a str with the given encoding."""
    if isinstance(obj, unicode):
        return obj.encode(encoding)
    return obj


def get_gpgme_context(ascii_armor=True, gnupghome=None):
    home = gnupghome or cereconf.GNUPGHOME
    ctx = gpgme.Context()
    ctx.set_engine_info(gpgme.PROTOCOL_OpenPGP, None, home)
    if ascii_armor:
        ctx.armor = True
        ctx.textmode = True  # do we need this?
    return ctx


def gpgme_encrypt(message, recipient_key_id=None, context=None):
    """
    Encrypts a message using GnuPG (pygpgme).

    Keyword arguments:
    :param message: the message that is to be encrypted
    :type message: str or unicode
    :param recipient_key_id: the private key id
    :type recipient_key_id: str or unicode
    :param ascii_armor: use ascii armor
    :type ascii_armor: bool

    :returns: the encrypted message (ciphertext).
              If ascii_armor is defined True, ASCII armor will be returned,
              otherwise a regular byte string will be returned
    :rtype: str

    May throw a gpgme.GpgmeError. Should be handled by the caller.

    The private key id is used by pygpgme to determine which public key
    to use for encryption.
    'gpg2 -k --fingerprint' can be used to list all available public keys
    in the current GnuPG database, along with their fingerprints.
    Possible values:
    uid: (f.i. "Cerebrum Test <cerebrum@uio.no>")
    key-id: (f.i. "FEAC69E4")
    fingerprint (recommended): (f.i.'78D9E8FEB39594D4EAB7A9B85B17D23FFEAC69E4')
    """
    context = context or get_gpgme_context()
    recipient_key = context.get_key(recipient_key_id)
    plaintext = BytesIO(_unicode2str(message))
    ciphertext = BytesIO()
    context.encrypt([recipient_key], 0, plaintext, ciphertext)
    return ciphertext.getvalue()


def gpgme_decrypt(ciphertext, context=None):
    """
    Decrypts a ciphertext using GnuPG (pygpgme).

    Keyword arguments:
    :param ciphertext: the ciphertext that is to be decrypted
    :type ciphertext: str

    :returns: the decrypted ciphertext (message)
    :rtype: str

    May throw a gpgme.GpgmeError. Should be handled by the caller.

    Just like GnuPG, pygpgme extracts the private key corresponding to the
    ciphertext (encrypted message) automatically from the local
    GnuPG keydatabase situated in $GNUPGHOME of the active (Cerebrum) user.
    """
    context = context or get_gpgme_context()
    ciphertext = BytesIO(ciphertext)
    plaintext = BytesIO()
    context.decrypt(ciphertext, plaintext)
    return plaintext.getvalue()

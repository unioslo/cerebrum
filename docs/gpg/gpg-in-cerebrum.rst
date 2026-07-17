=================
GPG in Cerebrum
=================

Cerberum has multiple GPG related modules for encrypting and decrypting
messages.  All of them will use the system GnuPG library with a common, custom
GnuPG homedir.

The modules that use this functionality is:

- ``Cerebrum.modules.gpg``
- ``Cerebrum.utils.gpg``

See the setup document for more info on how to set up GPG on a given host.

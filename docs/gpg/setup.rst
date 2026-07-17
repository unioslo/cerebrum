Setting up GPG for use with Cerebrum
====================================

This is a short howto for setting up GPG for use with the
``Cerebrum.modules.gpg`` and ``Cerebrum.utils.gpg`` modules.


Setting up a GnuPG homedir
==========================

First, create a home directory for GnuPG keyrings, trust-db, etc...:
::

    mkdir -m 0700 /path/to/gnupg_home


Then import public keys for use with the module:
::

    gpg2 --homedir /path/to/gnupg_home --import /path/to/pubkey


Now, to be able to use this key for encryption, it needs to be validated.
This can either be achieved by signing it with our own, private key, or by
setting *ultimate* trust for the key:
::

    # list keys and their ids
    gpg2 --homedir /path/to/gnupg_home --list-keys

    # edit the key, and follow the wizard to set trust level 5 (ultimate)
    gpg2 --homedir /path/to/gnupg_home --edit-key <key-id> trust

    ...
    Your decision? 5
    Do you really want to set this key to ultimate trust? (y/N) y
    gpg>


For test environment, you may want to generate your own key pair, so that you
are able to decrypt the GPG data as well:
::

    # generate a key
    gpg2 --homedir /path/to/gnupg_home --full-generate-key

    # After completing the wizard, you can list your keys with
    gpg2 --homedir /path/to/gnupg_home --list-keys



Configuring Cerebrum
====================
Set ``cereconf.GNUPGHOME``:
::

    GNUPGHOME = "/path/to/gnupg_home"


Configure which keys to use for different *tags*. This is done in the
``${CEREBRUM_CONFIG_ROOT}/gpg_data.(json|yml)`` file:
::

    {
        "tag_to_recipient_map": [
            {
                "tag": "foo",
                "recipients": [
                    "60A6...",
                    "531E..."
                ]
            },
            {
                "tag": "bar",
                "recipients": [
                    "60A6..."
                ]
            }
        ]
    }


Cerebrum GPG tags
=================

``password``
    This tag is stored by the ``Cerebrum.modules.gpg.password`` module. It
    stores a GPG-encrypted plaintext password for each recipient. The recipient
    is typically a public key belonging to the Active Directory hosts that are
    involved in syncing passwords.

``password-base64``
    Like ``password``, but the password is base64 encoded


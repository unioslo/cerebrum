======================
Bofh - administration
======================

Introduction
=============

This chapter covers the administrative parts of setting up a bofh
server, like editing configuration files.

For information about using bofh, see `Bofh user guide
<../user/bofh.html>`_

For information about developing bofh extensions and description of
the network protocol, see `Bofh developer guide <../devel/bofh.html>`_


Configuring bofhd
==================

When starting bofhd, a configuration file must be spesified.  This
configuration file defines what modules this bofh server should
contain.  If the configuration file is empty, the server will start,
but very few comands will be available.

The configuration file contains a number of lines on the format
``module_name/class_name``, and thus points to python classes in
various files.  Blank lines, and lines starting with ``#`` are
ignored.  The files are loaded in consecutive order.  When
name-clashes occours, the command from the file loaded last will be
used.

This is an example of a configuration file::

  # Load most of the commands used at UoO
  Cerebrum.modules.no.uio.bofhd_uio_cmds/BofhdExtension
  # The printer-quota commands are in a separate module
  Cerebrum.modules.no.uio.printer_quota.bofhd_pq_cmds/BofhdExtension


Starting bofhd
===============

Bofhd can be started like: ``bofhd.py --config-file filename``.  It
will default to encrypted mode, using the certificates in
``cereconf.DB_AUTH_DIR/`` named ``server.cert``, ``ca.pem`` and the
``dh1024.pem`` file (for information on generating these files, see
below).

By default, bofhd will use a logger named ``bofhd`` (see also TODO:
logger-enduser-doc).  For testing, one might want to use
``--logger-name=console`` as the first command-line argument.

By using the ``--port number`` argument, one may run multiple bofh
servers at different ports with different configurations.

.. TODO: it would be nice if we could automatically include the bofhd
   usage string here


Distributing the jbofh client
==============================

The jbofh is distributed as a jar file.  A jar file is a normal zip
file with some special files, and standard zip utilities can be used
to modify its contents.  There are typicaly two changes one may want
to do to the default jar file:

1. Update/add the ``cacert.pem`` in its root-folder.  This cacert
should match the one used by the server.

2. Update ``jbofh.properties``.  Atleast ``bofhd_url`` should be set
to point to the default bofh server.  Also, if you use a comercial CA,
whose root-certificate is in javas default keystore, you may wish to
set ``InternalTrustManager.enable=false``

For more information about jbofh, see (TODO)


Encrypted bofhd
================

You should run bofhd in its encrypted mode to avoid sending plaintext
passwords and other sensitive data unprotected over the network.
Since you have to distribute the jar file anyway, you may want to
avoid the hazzle of buying a comercial certificate for use with your
bofh server.  You can build your own certificate by following the
instructions below.::

  ### Generate my own CA Authority.
  ###
  luggage$ cd /tmp/
  luggage$ mkdir cert-test 
  luggage$ cd cert-test
  luggage$ mkdir demoCA
  luggage$ mkdir demoCA/certs
  luggage$ mkdir demoCA/crl
  luggage$ mkdir demoCA/newcerts
  luggage$ mkdir demoCA/private
  luggage$ echo "01" > demoCA/serial
  luggage$ touch demoCA/index.txt
  luggage$ openssl req -new -x509 -keyout demoCA/private/cakey.pem -out demoCA/cacert.pem -days 1825 -config /etc/ssl/openssl.cnf
  Generating a 1024 bit RSA private key
  .++++++
  .++++++
  writing new private key to 'demoCA/private/cakey.pem'
  Enter PEM pass phrase:
  Verifying - Enter PEM pass phrase:
  -----
  You are about to be asked to enter information that will be incorporated
  into your certificate request.
  What you are about to enter is what is called a Distinguished Name or a DN.
  There are quite a few fields but you can leave some blank
  For some fields there will be a default value,
  If you enter '.', the field will be left blank.
  -----
  Country Name (2 letter code) [AU]:NO
  State or Province Name (full name) [Some-State]:Oslo
  Locality Name (eg, city) []:
  Organization Name (eg, company) [Internet Widgits Pty Ltd]:Tveita Hybel-IT
  Organizational Unit Name (eg, section) []:
  Common Name (eg, YOUR name) []:Harald Meland
  Email Address []:harald.meland@usit.uio.no

  ### Generate a certificate request for my server.  The servers FQDN
  ### must be given as the sertificate's "Common Name".
  ###
  luggage$ openssl req -new -keyout key.pem -out req.pem -days 1825 -config /etc/ssl/openssl.cnf -nodes
  Generating a 1024 bit RSA private key
  ...............++++++
  ...................++++++
  writing new private key to 'key.pem'
  -----
  You are about to be asked to enter information that will be incorporated
  into your certificate request.
  What you are about to enter is what is called a Distinguished Name or a DN.
  There are quite a few fields but you can leave some blank
  For some fields there will be a default value,
  If you enter '.', the field will be left blank.
  -----
  Country Name (2 letter code) [AU]:NO
  State or Province Name (full name) [Some-State]:Oslo
  Locality Name (eg, city) []:
  Organization Name (eg, company) [Internet Widgits Pty Ltd]:Tveita Hybel-IT
  Organizational Unit Name (eg, section) []:Mobile Gadgets 'n' Stuff
  Common Name (eg, YOUR name) []:luggage.dnsalias.org
  Email Address []:                     

  Please enter the following 'extra' attributes
  to be sent with your certificate request
  A challenge password []:
  An optional company name []:
  luggage$ cat req.pem key.pem > full-req.pem

  ### Use my own CA Authority to issue the new certificate.
  ###
  luggage$ openssl ca -policy policy_match -out out.pem -config /etc/ssl/openssl.cnf -days 1825 -infiles full-req.pem 
  Using configuration from /etc/ssl/openssl.cnf
  Enter pass phrase for ./demoCA/private/cakey.pem:
  Check that the request matches the signature
  Signature ok
  Certificate Details:
          Serial Number: 1 (0x1)
          Validity
              Not Before: Dec 11 23:45:40 2003 GMT
              Not After : Dec  9 23:45:40 2008 GMT
          Subject:
              countryName               = NO
              stateOrProvinceName       = Oslo
              organizationName          = Tveita Hybel-IT
              organizationalUnitName    = Mobile Gadgets 'n' Stuff
              commonName                = luggage.dnsalias.org
          X509v3 extensions:
              X509v3 Basic Constraints: 
                  CA:FALSE
              Netscape Comment: 
                  OpenSSL Generated Certificate
              X509v3 Subject Key Identifier: 
                  9D:73:E4:2D:DE:A9:B4:29:1F:E6:84:12:2C:52:C0:F3:7E:CE:74:BB
              X509v3 Authority Key Identifier: 
                  keyid:04:7A:77:E6:C5:58:87:01:59:06:80:18:64:3E:41:69:9B:5F:58:36
                  DirName:/C=NO/ST=Oslo/O=Tveita Hybel-IT/CN=Harald Meland/emailAddress=harald.meland@usit.uio.no
                  serial:00

  Certificate is to be certified until Dec  9 23:45:40 2008 GMT (1825 days)
  Sign the certificate? [y/n]:y


  1 out of 1 certificate requests certified, commit? [y/n]y
  Write out database with 1 new entries
  Data Base Updated
  luggage$ cat out.pem key.pem > server.cert

  ### Generate a Diffie-Hellman symmetric cipher key, for use in
  ### bofhd.py.
  ###
  luggage$ openssl gendh -out dh1024.pem 1024
  Generating DH parameters, 1024 bit long safe prime, generator 2
  This is going to take a long time
  ...........................................+...................+...............+......+.....................+...........................................................................+..................+................+...............................................................+............................................+............+....................+.+.......................................................................................................................................................+.............+.......+.......................................................................................................+................+..............+.........................+.............................................+.......................................................................................+....+...................................................+........................+...................................+....................+.............+....................+...+............+..............+.........+.................................................................+.................................+........+.......................................+..........+......+.....................................+.............................................+....................................................................................+.+.................................................................+...............................+................+.....................................+...............+...................................+.................................................+.........+............................................................+...........................................+..........................................+................+.....................+...............+..+...............................................................................................+...............................+.....................................................................................................................................................................................+..+.....+...............................................................+...................................................................................+...............................................+.................................................+.........+...............+..........+.......................................+..........+........................+.........+.....................+................................+.....................................................................................................................+....+.................................+....+...............................................+............................................................+....................................+.................................+....................................+.......+......+.....+...+...............................................................................................................................................+........................+....++*++*++*

  ### Copy the various generated files into place, so that bofhd.py will
  ### find them.
  ###
  luggage$ cp dh1024.pem /home/hmeland/project/cerebrum/etc/
  luggage$ cp server.cert /home/hmeland/project/cerebrum/etc/
  luggage$ cp demoCA/cacert.pem /home/hmeland/project/cerebrum/etc/ca.pem

  ### Include my own CA in JBofh, and make sure the default URL matches
  ### the server name as given in the server certificate.
  ###
  ### Given an existing JBofh.jar, this is easy to do in Emacs; open the
  ### .jar file, and modify the files 'cacert.pem' and
  ### 'jbofh.properties' as needed.


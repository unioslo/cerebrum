==============================================
Installing the ADserver.
==============================================

Install following components on an Domain Controller:

* ActivePython 2.4.3 Build 12 (ActiveState Software Inc.)
 
  Download page <http://www.activestate.com/store/download.aspx?prdGUID=b08b04e0-6872-4d9d-a722-7a0c2dea2758>
* Win32OpenSSL-v0.9.8b
   
  Download page <http://www.slproweb.com/products/Win32OpenSSL.html>
* pyOpenSSL-0.6.win32-py2.4.exe
   
  Download page <http://webcleaner.sourceforge.net/install.html>

Download from sourceforge: 

* ADconstants.py
* ADserver.py
* ADobject.py
  
Download page http://cerebrum.cvs.sourceforge.net/cerebrum/cerebrum/adserver/>

place them on a suitable place(c:\cerebrum\python)

Edit the Constants in the file ADconstants.py to work with your Cerebrum 
installation. 

* Get a certificate for your installation, and place this in the path 
  specified by KEYFILE and CERTFILE.
* Edit the LISTEN_HOST to the local domain controller.
* Edit LISTEN_PORT to the portnumber specified on the cerebrum server. 
* Edit ACCESSLIST to the ip-address of the cerebrum server.
* Edit AUTH to a valid user in Active Directory. The server is not running in 
  the context of this user. The server use the password specified in the 
  basic HTML autentication header sent from the cerebrum server to allow access.
* Configure the logger. 

==============================================
Running the ADserver.
==============================================

Start the server by running ADserver.py. The script takes the following options.

options::

	--debug		Start the server in debug mode.

	--service	Run the server as a service. The rest of the options
			on the commandline is handed over and interpreted by the
			pythonservice module.

Some exsamples:
================

* Run in debug mode:
  ADserver.py --debug
  The server is writing output from the script to console. 

* Install the server as a service:
  ADserver.py --service --startup auth install

* Start the service:
  ADserver.py --service start

* Stop the service:
  Not working from commandline, you have to kill pythonservice.exe process in the TaskManager.

* Remove the service:
  The service must be stopped, then run
  ADserver.py --service remove 


On the cerebrum side:
=======================
A simple script to test contact with the server. The variables must be edited 
to match the installation::

	#!/usr/bin/env python
	
	import xmlrpclib
	uname = 'cerebrum' 
	passwd = 'H3mm3lig!'
	ADserver = 'dctest.uio.no'
	port = 8000
	
	server = xmlrpclib.Server('https://%s:%s@%s:%i' % (uname, passwd, ADserver, port))

	print server.location()


The output should be the FQDN of the domain. 
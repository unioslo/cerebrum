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
  
Download page <http://cerebrum.cvs.sourceforge.net/cerebrum/cerebrum/adserver/>

place them on a suitable place(c:\cerebrum\python)


Settings in ADconstants.py 
========================================

Edit the Constants in the file ADconstants.py to work with your Cerebrum 
installation. 

* Get a certificate for your installation, and place this in the path 
  specified by KEYFILE and CERTFILE.
* Edit the LISTEN_HOST to the local domain controller.
* Edit LISTEN_PORT to the portnumber specified on the cerebrum server. 
* Edit ACCESSLIST to the ip-address of the cerebrum server.
* Edit AUTH to a valid user in Active Directory. The default user is Cerebrum. 
  The server is not running in the context of this user, but the server use the password 
  specified in the basic HTML autentication header sent from the cerebrum server 
  to allow access.
* Configure the logger. 
* Configure the MixIn class. This class defines what modules the server will have available 
  through the interface to cerebrum. Here you can write your own classes and make them avaiable. 
  First import the class, then modify the base classes of the MixIn class defined in 
  ADconstants.py.  
  


Recomended settings on the Domain Controller:
=============================================

* Create a user called cerebrum in AD, place the user in the Builtin OU or the OU specified in the 
  AD_DO_NOT_TOUCH variable in cerebrum. This user must be the same user specified in the 
  AUTH constant on AD-server. The password on the user must match the password used in the 
  HTML autentication header sent from Cerebrum. 
 
* Domain Functional level must be above 2000mixed mode to allow groups as groupmembers.

* The Group Policy Setting in Default Domain Policy: 
  Computer Configuration -> Windows Settings Security Settings -> Account Policy -> 
  Password Policy -> Password must meet complexity requirements should be disabled, or changing of 
  password might fail.

* The Group Policy Setting in Default Domain Policy: User Configuration -> Windows Settings -> 
  Administrative Template -> System -> Ctrl+Alt+Del Options -> 
  Remove Change Password should be disabled  

* Create an OU matching the AD_DO_NOT_TOUCH value in cerebrum, 
  default value is 'Cerebrum_dont_touch'.

* Create an OU matching the AD_LOST_AND_FOUND value in cerebrum, 
  default value is 'lost-n-found'. This is the place where deleted objects is placed if 
  syncronication is run without the delete option.


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
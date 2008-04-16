==============================================
Installing the ADserver.
==============================================

This documentation is written for and tested with revision 9935 of the 
code.

ADserver was tested on Windows Vista x86 and 2008 server x64. The code was very 
slow on 2008 server x64, unknown why, this platform is presently not advised.  

A problem with x64, there is currently no x64 support for pywin32:-(
Therefore all binaries must use 32bit versions.  


Install the following components on a domain member machine:

ActivePython-2.5.1.1-win32-x86.msi from 
http://downloads.activestate.com/ActivePython/windows/2.5/
(A newer version will most probably work)

pyOpenSSL-0.7a2-py2.5.exe from 
http://sourceforge.net/project/showfiles.php?group_id=78018


Win32OpenSSL_Light-0_9_8g from 
http://www.slproweb.com/products/Win32OpenSSL.html


Download the components of the ADserver from sourceforge: 
The wanted components must be configured in the MixIn class in 
ADConstants.py 

* ADconstants.py
* ADserver.py
* ADobject.py
* ADexchange.py
* ADaccountDir.py  

Download page:
http://cerebrum.svn.sourceforge.net/viewvc/cerebrum/trunk/cerebrum/servers/ad/

place them in a suitable place(c:\cerebrum\python)


Settings in ADconstants.py 
========================================

Edit the Constants in the file ADconstants.py, below is a description of 
each setting.

* Get a certificate for your installation, and place this in the path 
  specified by KEYFILE and CERTFILE. The certificate can be generated with
  win32OpenSSL.

* LISTEN_HOST can be set to IP of local machine, or left blank. 
  Default it is blank.

* Edit LISTEN_PORT to the portnumber specified on the cerebrum server. 
  Default is 8000.

* Edit ACCESSLIST to the ip-address of the cerebrum server. This is a list 
  and can contain more than one address.
  
* Edit DOMAIN to the domain you want to autenticate against. This might be a 
  windows AD domain or the local machine. The windows domain is resolved 
  by default.

* Edit AUTH to a valid user in the domain specified by the DOMAIN constant. 
  The default user is cerebrum. The password specified in the basic HTML 
  autentication header sent in the XML-RPC request is used to autenticate the 
  specified user.

* Configure the logger(see documentation of the python logger module) 

* Configure the MixIn class. This class defines what modules the server will 
  use. Here you can write your own classes and make them available for 
  Cerebrum to access the methods.

  


Recomended settings on the Domain Controller:
=============================================

* Create a user in AD, place the user in the Builtin OU or the 
  OU specified in the AD_DO_NOT_TOUCH variable in cerebrum. Give this user 
  the necessary rights to perform actions in Active Directory. Run the 
  service in the context of this user. Remember to change password on the 
  service if password is changed on the user AD. For security reasons
  This user should not be the user specified in the AUTH variable in the 
  constants file. For test purposes it is advised that the user is a member og 
  Domain Admins.    
 
* Domain Functional level must be above 2000mixed mode to allow groups as 
  groupmembers.

* The Group Policy Setting in Default Domain Policy: 
  Computer Configuration -> Windows Settings Security Settings -> 
  Account Policy -> Password Policy -> Password must meet complexity 
  requirements should be disabled, else changing of password might fail.
  Password complexity requirements should be handled by Cerebrum.

* The Group Policy Setting in Default Domain Policy: 
  User Configuration -> Windows Settings -> 
  Administrative Template -> System -> Ctrl+Alt+Del Options -> 
  Remove Change Password should be disabled.   

* Create an OU matching the AD_DO_NOT_TOUCH value in cerebrum, 
  default value is 'Cerebrum_dont_touch'.

* Create an OU matching the AD_LOST_AND_FOUND value in cerebrum, 
  default value is 'lost-n-found'. This is the place where deleted objects is 
  placed if syncronization is run without the delete option.

* Remember to configure the firewall and accept communication through port 
  8000, or the port specified by the PORT variable.

* The Machine must be member of the domain. The changes is done 
  in the Active Directory domain through the Windows COM interface. The 
  machine do not need to be a domain controller for the server work.



==============================================
Running the ADserver.
==============================================

Start the server by running ADserver.py. The script have the following options.

options::

	--debug		Start the server in debug mode. Running the server 
                        from CMD, displays all debug information. 
                         

	--service	Run the server as a service. The rest of the options
			on the commandline is handed over and interpreted by the
			pythonservice module. The service is logging to the 
                        eventlog, so this is a good source for information. 
			Debug information from the service can also be caught 
			by running win32traceutil.py
                         


Some exsamples:
================

* Run in debug mode:
  ADserver.py --debug
  The server is writing output from the script to console. 

* Install the server as a service:
  ADserver.py --service --startup auth install
 
  Remember to configure the service to Log On as a user with the autorization 
  to make changes i Active Directory. The server run in the context of this 
  user. Running as Local System Account will only work on a domain controller.

* Start the service:
  ADserver.py --service start

* Stop the service:
  ADserver.py --service stop

* Remove the service:
  The service must be stopped, then run
  ADserver.py --service remove 



On the cerebrum side:
=======================
A simple script to test contact with the server. The variables must be edited 
to match the installation::

	#!/usr/bin/env python
	
	import xmlrpclib
	uname = 'user1' 
	passwd = 'H3mm3lig!'
	ADserver = 'dctest.uio.no'
	port = 8000
	
	server = xmlrpclib.Server('https://%s:%s@%s:%i' % (uname, passwd, ADserver, port))

	print server.location()


The output should be the FQDN of the domain. 
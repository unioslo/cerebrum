==============================================
Installing the Cerebrum ADserver.
==============================================

This documentation is written for and tested with revision 12264 of the 
code.

ADserver was tested on Windows Server 2008 x64, Windows Server 2008 R2 x64 and Windows Server 2003 x86.

A problem with x64 and python means there is currently no x64 support for Python for Windows Extensions (PyWin32), therefore all binaries must use 32bit versions.  

Install the following components on a domain member machine:

ActivePython-2.5.4.4-win32-x86.msi from 
http://downloads.activestate.com/ActivePython/windows/2.5/
(A newer version 2.5 will most probably work)

pywin32-214.win32-py2.5.exe from
http://sourceforge.net/project/showfiles.php?group_id=78018&package_id=79063&release_id=616849

pyOpenSSL-0.8.winxp32-py2.5.exe from 
http://sourceforge.net/project/showfiles.php?group_id=31249&package_id=90289

Win32 OpenSSL v0.9.8k Light
http://www.slproweb.com/products/Win32OpenSSL.html

If OpenSSL is complaining about missing DLL, try to install 
Visual C++ 2008 Redistributables from 
http://www.slproweb.com/products/Win32OpenSSL.html

Download the components of the ADserver from the git repo:
The wanted components must be configured in the MixIn class in 
ADConstants.py 

* ADconstants.py
* ADserver.py
* ADobject.py
* ADexchange.py
* ADaccountDir.py  

Download page:
https://utv.uio.no/stash/projects/CRB/repos/cerebrum/browse

place them in a suitable place (c:\cerebrum\python)


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
  
* Edit DOMAIN to the domain you want to autenticate against. This
  might be a windows AD domain or the DN of the local macine. The
  windows domain is resolved by default.

* Edit AUTH to a valid user in the domain specified by the DOMAIN
  constant.  The default user is cerebrum. The password specified in
  the basic HTML autentication header sent in the XML-RPC request is
  used to autenticate the specified user. NB: avoid using chars not in
  7 bit ASCII in the password for the account.

* Configure the logger (see documentation of the python logger module) 

* Configure the MixIn class. This class defines what modules the server will 
  use. Here you can write your own classes and make them available for 
  Cerebrum to access the methods.

  


Recomended settings on the Domain Controller:
=============================================

* Create an user in AD, place the user in an OU Cerebrum is configured not to touch.
  Give this user the necessary rights to perform actions in Active Directory. Run the 
  service in the context of this user. Remember to change password on the 
  service if password is changed on the user AD. For security reasons
  This user should not be the user specified in the AUTH variable in the 
  constants file. For test purposes it is advised that the user is a member of 
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

* Create OUs matching the AD_OU values in cerebrum for deleted objects, 
  groups, user and so on. 

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
  ADserver.py --service --startup auto install
 
  Remember to configure the service to Log On as a user with the autorization 
  to make changes i Active Directory after install. The server run in the context 
  of this user. Running as Local System Account will only work on a domain controller.

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

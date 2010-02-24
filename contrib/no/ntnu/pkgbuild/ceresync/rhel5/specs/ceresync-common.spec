%define _unpackaged_files_terminate_build 0
%define python_ver %(%{__python} -c "import sys; print sys.version[:3]")%{nil}
%define fakeroot %(if [ "`id -u`" -eq 0 ]; then echo -n ; else echo -n "fakeroot"; fi)
%define pythonssl %(if [ -n "`grep SUSE /etc/issue`" ]; then echo -n "python-openssl" ; else echo -n "pyOpenSSL"; fi )
Name: ceresync-common
Summary: Files needed for all ceresync clients
Version: VERSION
Release: RELEASE
Source0: cerebrum-ntnu-%{version}-%{release}.tar.gz
Patch0: setup.py.path.patch
License: GPL
Group: Applications/System
BuildRequires: python-setuptools
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root
BuildArch: noarch
Requires: %{pythonssl}
Requires: python-zsi, m2crypto


%description
Files common to all ceresync clients.

%package -n ceresync-ldap
Group: Applications/System
Summary: The LDAP ceresync client
Requires: ceresync-common
BuildArch: noarch

%description -n ceresync-ldap
The LDAP ceresync client

%package -n ceresync-kerberos
Group: Applications/System
Summary: The Kerberos ceresync client
Requires: ceresync-common
BuildArch: noarch

%description -n ceresync-kerberos
The Kerberos ceresync client

%package -n ceresync-radius
Group: Applications/System
Summary: The Radius ceresync client
Requires: ceresync-common
BuildArch: noarch

%description -n ceresync-radius
The Radius ceresync client

%package -n ceresync-homedir
Group: Applications/System
Summary: The homedir ceresync client
Requires: ceresync-common
BuildArch: noarch

%description -n ceresync-homedir
The homedir ceresync client

%package -n ceresync-aliases
Group: Applications/System
Summary: The aliases ceresync client.
Requires: ceresync-common
BuildArch: noarch

%description -n ceresync-aliases
The aliases ceresync client

%prep
[ ${RPM_BUILD_ROOT} != "/" ] && rm -rf ${RPM_BUILD_ROOT}
%setup -q -n cerebrum-ntnu-%{version}-%{release}
%patch0
sed "s|RPM_BUILD_ROOT|${RPM_BUILD_ROOT}|g" -i setup.py
aclocal
autoconf


%build
./configure --prefix=${RPM_BUILD_ROOT}/usr \
            --sysconfdir=${RPM_BUILD_ROOT}/etc \
            --localstatedir=${RPM_BUILD_ROOT}/var \
            --with-webroot=${RPM_BUILD_ROOT}/usr/lib/cereweb \
            --disable-bofh

%install
%{fakeroot} make -C spine/ceresync install
%{fakeroot} make -C spine/client install
sed "s|${RPM_BUILD_ROOT}||g" -i ${RPM_BUILD_ROOT}/usr/lib/python%{python_ver}/site-packages/ceresync/config.py

%clean
[ ${RPM_BUILD_ROOT} != "/" ] && rm -rf ${RPM_BUILD_ROOT}

%files
%defattr(-,root,root)
/usr/lib/python%{python_ver}/site-packages/SignatureHandler.py
/usr/lib/python%{python_ver}/site-packages/ceresync/backend/file.py*
/usr/lib/python%{python_ver}/site-packages/ceresync/backend/__init__.py*
/usr/lib/python%{python_ver}/site-packages/ceresync/cerelog.py*
/usr/lib/python%{python_ver}/site-packages/ceresync/config.py*
/usr/lib/python%{python_ver}/site-packages/ceresync/doc_exception.py*
/usr/lib/python%{python_ver}/site-packages/ceresync/errors.py*
/usr/lib/python%{python_ver}/site-packages/ceresync/__init__.py*
/usr/lib/python%{python_ver}/site-packages/ceresync/syncws.py*
/usr/lib/python%{python_ver}/site-packages/Cerebrum/__init__.py
/usr/lib/python%{python_ver}/site-packages/Cerebrum/lib/__init__.py
/usr/lib/python%{python_ver}/site-packages/Cerebrum/lib/cerews/__init__.py
/usr/lib/python%{python_ver}/site-packages/Cerebrum/lib/cerews/cerews_services.py
/usr/lib/python%{python_ver}/site-packages/Cerebrum/lib/cerews/cerews_services_types.py
/usr/lib/python%{python_ver}/site-packages/Cerebrum/lib/cerews/dom.py
/usr/sbin/syncfile.py*
/usr/sbin/syncnothing.py*

%files -n ceresync-kerberos
%defattr(-,root,root)
/usr/sbin/synckerberos.py*
/usr/lib/python%{python_ver}/site-packages/ceresync/backend/kerberos/

%files -n ceresync-ldap
%defattr(-,root,root)
/usr/sbin/syncldap.py*
/usr/lib/python%{python_ver}/site-packages/ceresync/backend/ldapbackend.py*

%files -n ceresync-radius
%defattr(-,root,root)
/usr/sbin/syncradius.py*

%files -n ceresync-homedir
%defattr(-,root,root)
/usr/sbin/synchomedir.py*

%files -n ceresync-aliases
%defattr(-,root,root)
/usr/sbin/syncaliases.py*

%changelog
* Mon Feb 08 2010 Leiv Arild Andenes <laa (at) ntnu (dot) no>
- Ceresync 2.x does not use Spine, hence omniorb is not needed

* Wed Jan 20 2010 Christian H. Toldnes <chritol (at) ntnu (dot) no>
- updated to fit new version

* Mon Feb 09 2009 Christian H. Toldnes <chritol (at) ntnu (dot) no>
- Initial spec

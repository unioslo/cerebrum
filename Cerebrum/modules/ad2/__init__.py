# -*- coding: utf-8 -*-
#
# Copyright 2011-2024 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
"""
Active Directory (AD) integration.

These modules implements the Cerebrum/AD sync.  This sync communicates with AD
using Powershell shell commands over WinRM, a Windows specific SOAP service.

Glossary
========

WS-Management
    Open standard for remote management with SOAP APIs.

WinRM
    Windows Remote Management - the Windows WS-Management API.  This API
    enables us to run shell commands on Windows hosts, including Powershell
    commands.

Powershell
    Microsoft shell and scripting language, with optional first and third party
    modules and access to .Net functionality.

    This sync utilizes the ActiveDirectory module to interact with AD.


Overview
========
The AD sync is split into multiple modules:

:mod:`.winrm`
    The *winrm* module implements most of the WinRM-communication and
    functionality for running powershell commands.

    The WinRM client implements *SOAP actions* such as "create shell", "run
    command in shell", "receive data from shell", etc...

    The Powershell class wraps SOAP actions into a simple "run powershell
    command and return output" method.

:mod:`.ADUtils`
    *ADUtils implements an helper class that implements AD "actions", like:

    - Connecting to a domain controller
    - Listing AD objects (e.g. get all accounts, groups, ...)
    - Managing AD objects (create, get, update, delete)
    - Running arbitrary scripts

:mod:`.CerebrumData`
    *CerebrumData* contains utilities for generating AD object models from
    Cerebrum data.

:mod:`.ADSync`
    Implements the sync itself. Typical behaviour

    1. Fetch and cache all relevant Cerebrum data

    2. Fetch and cache all relevant AD data

    3. Calculate all diffs.  For an objects that exists in both AD and
       Cerebrum, diff is calculated by the :mod:`.CerebrumData` object

    4. Run all required commands for bringing each object up to date.

:mod:`.ConfigUtils`
    Models for specifying *what* to sync to AD.  Typically used in
    ``adconf.SYNCS[<preset>['attributes']``.  Very tightly integrated with
    :mod:`.CerebrumData` and :mod:`.ADSync`.

:mod:`.Entity`
    *Entity* is an entity mixin for storing ad specific attributes in Cerebrum.
    Attribtues can be stored e.g. as traits, or in a specific `ad_attribute`
    table.  See also :mod:`.bofhd_ad_cmds` for managing attributes.

    TODO: These modules are poorly named, and don't really belong here.
    Should probably be moved to ``Cerebrum.modules.ad_attrs.*`` or similar.


TODO
====
Unify configuration and script invocation:

1. Group configuration (connection, ad domain, business logic), implement
   config to validate certain groups.

2. Split subclassed objects.  The Powershell class *isn't* a WinRM client --
   it uses a WinRM client to send commands and receive output.  This would make
   configuring these objects easier (e.g. the Powershell object is initiated by
   passing a configured WinRM-client, the AD-client is configured by passing a
   powershell-object).

3. Unify the cli-arguments further.


Maybe use some 3rd party packages rather than implementing these clients
ourselves?

- WinRM client package: pywinrm - <https://github.com/diyan/pywinrm>
- Powershell shell utils: I'm certain there's a shlex-like package for Python.
  Can't find it, but another candidate may be mslex
  <https://github.com/smoofra/mslex>?

We may want to re-build the integration using LDAP rather than
WinRM/Powershell: <https://github.com/zorn96/ms_active_directory/>
"""

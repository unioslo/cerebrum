@echo off
set CERECONF_DIR=C:\etc\cerebrum
set PYTHON_HOME=C:\Python25
set PYTHONPATH=C:\Cerebrum\lib\python2.5\site-packages
set Path=%PYTHON_HOME%;%PYTHON_HOME%\Scripts

C:\Cerebrum\sbin\syncadsi.py -i
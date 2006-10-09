To run the examples, the PYTHONPATH environment variable must include the path
to SpineClient.py (cerebrum/spine/client if spine is not installed, and
lib/python2.4/site-packages/ if spine is installed).  In addition, the
SpineCore.idl file must be in the same directory as the SpineClient.py file.
This should be done by the install script, but if you haven't installed spine,
go to cerebrum/spine/client/ and run (ln -s ../lib/server/idl/SpineCore.idl .).

Example: export PYTHONPATH=$HOME/cerebrum/spine/client:$PYTHONPATH

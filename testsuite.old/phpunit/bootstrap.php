<?php
/**
 * Bootstrapping phpunit, gets php ready for the unittests.
 *
 * This file could be used for doing certain changes before testing anything.  
 * You could also use the phpunit.xml file for various settings, e.g. for saying 
 * that this is the bootstrap file.
 */

# Create the session directory, if it doesn't exist already:
if (!file_exists(ini_get('session.save_path'))) {
    @mkdir(ini_get('session.save_path'));
}

# Path to the root of the cerebrum-tree
define('TEST_PREFIX_CEREBRUM', realpath(dirname(__FILE__) . '/../..'));

?>

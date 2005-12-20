#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# tail -f /site/opt/apache-ssl/logs/error_log /local2/home/runefro/usit/cerebrum/mydocs/web/www.log

import logging

import cerebrum_path
from Cerebrum.modules.no.Indigo.Cweb import Cfg
from Cerebrum.modules.no.Indigo.Cweb import Controller

def make_logger(): # TBD: use cgi.py's logger?
    logger = logging.getLogger('myapp')
    hdlr = logging.FileHandler(Cfg.log_file)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr) 
    logger.setLevel(logging.DEBUG)
    return logger

if __name__ == '__main__':
    c = Controller.Controller(make_logger())
    c.process_request()

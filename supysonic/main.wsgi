# coding: utf-8

import os.path, sys
from supysonic import config, db

if not config.check():
	sys.exit(1)

if not os.path.exists(config.get('base', 'cache_dir')):
	os.makedirs(config.get('base', 'cache_dir'))

db.init_db()

from supysonic.web import app as application


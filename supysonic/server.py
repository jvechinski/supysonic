# coding: utf-8

import config
import os.path, sys

def start_standalone_server(host=None, port=None, debug=True):
    if not config.check():
        sys.exit(1)

    if not os.path.exists(config.get('base', 'cache_dir')):
        os.makedirs(config.get('base', 'cache_dir'))

    import db
    from web import app

    db.init_db()
    app.run(host=host, port=port, debug=debug)
   
if __name__ == '__main__':
    start_standalone_server(host='0.0.0.0', debug=True)

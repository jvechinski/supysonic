try:
    from setuptools import setup
    have_setuptools = True
except ImportError:
    from distutils.core import setup
    have_setuptools = False

import os
import re

module_dir = os.path.dirname(os.path.abspath(__file__))

version_file = file(os.path.join(module_dir, 
    'supysonic', '__version__.py'))
version = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", 
    version_file.read(),
    re.MULTILINE).group(1)      
    
setup_info = {
    'name': 'supysonic',
    'version': version,
    'author': 'spl0k',
    'author_email': 'spl0k@github.com',
    'packages': [
        'supysonic',
        'supysonic.api',
        'supysonic.managers',        
    ],
    'package_data': {'supysonic': ['templates/*', 'main.wsgi']},
    'description': 'A Python implementation of the Subsonic server API.',
    'url': 'https://github.com/spl0k/supysonic',
    'install_requires': [
        'flask >= 0.7',
        'SQLAlchemy',
        'Pillow', # using this instead of the original PIL
        'simplejson',
        'requests >= 0.12.1',        
        'mutagen'
    ],
    'extras_require': {
        'mysql': ['MySQL-python'],
    },
    'entry_points': {
        'console_scripts':
            ['supysonic = supysonic.cli:command_line'],
    }      
}

if not have_setuptools:
    # Remove unsupported setup_info items if we are stuck with the
    # old and busted distutils.
    del setup_info['install_requires'] 
    del setup_info['extras_require']
    del setup_info['entry_points']

setup(**setup_info)                                        

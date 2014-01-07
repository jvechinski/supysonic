# coding: utf-8

import os, sys, tempfile, ConfigParser

default_config_values = {
    'cache_dir': os.path.join(tempfile.gettempdir(), 'supysonic'),
    # @todo Will this syntax work on Windows???
    'database_uri': 'sqlite:///'+ os.path.expanduser('~/.supysonic.db'),
}   

config_sections_when_no_config_file = ['base'] 

config = ConfigParser.RawConfigParser(default_config_values)

def check():
    try:
        ret = config.read([ '/etc/supysonic', os.path.expanduser('~/.supysonic') ])
    except (ConfigParser.MissingSectionHeaderError, ConfigParser.ParsingError), e:
        print >>sys.stderr, "Error while parsing the configuration file(s):\n%s" % str(e)
        return False

    if not ret:
        for section in config_sections_when_no_config_file:
            config.add_section(section)
        
        print("WARNING: No configuration file found, using default values for all configuration parameters")
        return True

    #if not config.has_option('base', 'database_uri'):
    #    print("WARNING: No database URI set, using default {}".format(
    #        default_config_values['database_uri']))     

    return True

def get(section, name):
    try:
        return config.get(section, name)
    except:
        return None


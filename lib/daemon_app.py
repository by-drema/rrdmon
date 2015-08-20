__author__ = 'drema'

import os
import sys
import time
import configparser

from lib.external.timer import Timer
from lib.monitorRMQ import MonitorRMQ

class App():
    def __init__(self, config, check=False):
        self.config = config
        self.check = check
        self.stdin_path = '/dev/null'
        self.stdout_path = self.config['daemon']['logfile']
        self.stderr_path = self.config['daemon']['logfile']
        self.monitors_dir = self.config['daemon']['monitors_dir']
        if not os.path.exists(self.monitors_dir):
            os.mkdir(self.monitors_dir)
        # self.pidfile_path = os.path.join(self.config['daemon']['root_dir'], self.config['daemon']['pidfile'])
        self.pidfile_path = self.config['daemon']['pidfile']
        self.pidfile_timeout = 10
        self.allowed_types = ['rmq', 'disk', 'cpu']
        self.workers_pool = []


    def get_monitors(self, cfg):
        monitors_list = []
        for section in cfg.sections():
            try:
                if cfg.has_option(section, 'type') and cfg.getboolean(section, 'enabled'):
                    monitors_list.append(section)
                else:
                    continue
            except configparser.NoOptionError as exc:
                print("ATTENTION! %(exc_message)s\n"
                      "Please, add this option into needed section and restart monitor.\n"
                      "Continuing without this monitor.." % {'exc_message':exc.message}
                    )
        return monitors_list


    def run(self):
        type_mon_accord = dict(rmq=MonitorRMQ)
        monitors_list = self.get_monitors(self.config)
        monitors_pool = []

        for section in monitors_list:
            type = self.config[section]['type']
            if type.lower() not in self.allowed_types:
                print("You've specified unallowed type of monitor in section \"%s\": \"%s\". I'm skipping this section." % (section, type))
                continue
            else:
                monik = type_mon_accord[type](self.config, section, chk_flag=self.check)
                monitors_pool.append((section, monik))
        self.workers_pool = []
        for (section, monik) in monitors_pool:
            self.workers_pool.append(Timer(self.config.getint(section, 'step'), monik.monitoring, '', t_name=section))
        if self.workers_pool:
            for worker in self.workers_pool:
                worker.start()
                print("handling workers_pool: monitor \"%(name)s\" started." % (dict(name=worker.name)) )
        else:
            print("There are no any active monitors were found. Exiting...")
            sys.exit(0)


    def terminate_me(self, sig_num, frame):
        try:
            for worker in self.workers_pool:
                while worker.is_alive():
                    print("handling workers_pool: monitor \"%(name)s\" is alive, stopping..." % (dict(name=worker.name)) )
                    worker.stop()
                    worker.join(3)
                print("handling workers_pool: monitor \"%(name)s\" was stopped." % (dict(name=worker.name)) )
        except Exception as err:
            print("Exception on terminating was caught: %s" % err.args[0])
            sys.exit(-1)
        else:
            print("All threads were stopped successfully." )

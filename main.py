import os
import sys
import configparser
import optparse
import signal

from lib.external.runner import DaemonRunner
from lib.daemon_app import App
from webS import Web

import bottle


def help():
    print("\nUsage ::")
    print("\tpython main.py {start|stop|restart} [OPTIONS]")
    print("\nAvailable OPTIONS ::")
    print("\t--web : logical flag to run webserver ('False' by default)")
    print("\t--mon : logical flag to run monitoring ('False' by default)")
    print("\t--chk : logical flag to run monitoring with check for aberrations; using in couple with --mon ('False' by default)")
    print(" --cfg <path> : specify custom config; default is ./etc/my.config from root application's dir\n")


p = optparse.OptionParser()
p.add_option("--chk", action="store_true", dest="chk_flag")
p.add_option("--web", action="store_true", dest="web_flag")
p.add_option("--mon", action="store_true", dest="mon_flag")
p.add_option("--config", action="store", type="string", dest="CONFIG_FILE")

p.set_defaults(chk_flag=False,
               web_flag=False,
               mon_flag=False,
               CONFIG_FILE=os.path.join(os.path.dirname(os.path.abspath(__file__)), './etc/my.config'),
              )

opts, args = p.parse_args()

print(args, sys.argv)

defaults = dict(root_proj_dir=os.path.dirname(os.path.abspath(__file__)))
config = configparser.ConfigParser(defaults, interpolation = configparser.ExtendedInterpolation())
config.read(opts.CONFIG_FILE)
### добавить анализ ключа запуска --web и в зависимости от этого создавать объекты разных классов - App или Web
if opts.web_flag:
    app = Web(config)
    bottle.route('/')(app.home)
    bottle.route('/stats')(app.stats)
    bottle.route('<path:path>')(app.server_static)
elif opts.mon_flag:
    app = App(config, opts.chk_flag)
else:
    print("Mode flag was missed!")
    help()
    sys.exit(-1)

allowed_actions = ['start', 'stop', 'restart']
if args[0] not in allowed_actions:
    print("Invalid action was entered!")
    help()
    sys.exit(-1)

daemon_runner = DaemonRunner(app)
daemon_runner.daemon_context.working_directory = config['daemon']['root_dir']

if getattr(app, 'terminate_me', False):
    daemon_runner.daemon_context.signal_map = { signal.SIGTERM : app.terminate_me }
else:
    pass
# daemon_runner.daemon_context.signal_map = { signal.SIGTERM : app.terminate_me}
daemon_runner.do_action()

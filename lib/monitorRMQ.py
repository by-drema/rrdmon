from .monitor import Monitor
from .wraprrd import RRDer
import os
import requests
import random


class MonitorRMQ(Monitor):
    _requestStr = "http://%s:%s%s"
    _login = ""
    _passwd = ""

    def __init__(self, config, cfg_section, chk_flag):
        Monitor.__init__(self, config, chk_flag)
        self.my_cfg = config[cfg_section]
        self._root_dir = os.path.join(config['daemon']['monitors_dir'], cfg_section)
        if not os.path.exists(self._root_dir):
            os.mkdir(self._root_dir)
        self._rrd_dir = self._root_dir + '/rrd'
        if not os.path.exists(self._rrd_dir):
            os.mkdir(self._rrd_dir)
        self._png_dir = self._root_dir + '/png'
        if not os.path.exists(self._png_dir):
            os.mkdir(self._png_dir)
        ### надо в конфиге определить default_port=80
        self._requestStr = self._requestStr % (self.my_cfg['host'], self.my_cfg['port'], self.my_cfg['uri'])
        self._login = self.my_cfg['login']
        self._passwd = self.my_cfg['password']
        self._step = self.my_cfg['step']
        self._season = int(self.my_cfg['season_in_steps'])
        self.rrd_worker = RRDer(config, self._rrd_dir, self._png_dir)

    def getVals(self, sys_time):
        for x in self.StringList:
            [queueName, msgCount] = x
            values = {}
            values['sysTime'], values['objName'], values['msgCount'] = sys_time, repr(queueName), msgCount
            self.DataList.append(values)
        return

    def getData(self):
        json_data = None
        self.StringList = []
        banned_symbol_in_qname = '/'
        try:
            resp = requests.get(self._requestStr, auth=(self._login, self._passwd))
            if resp.status_code == 200:
                json_data = resp.json()
            else:
                print("Invalid response was received! RetCode: %d, Content: \n %s" % (resp.status_code, resp.text))
        except Exception as err:
            print("HTTP exception has been occured! ErrMsg: %s" % str(err.args))
        if json_data is not None:
            for x in json_data:
                try:
                    if banned_symbol_in_qname in x['name']:
                        continue
                    else:
                        self.StringList.append((x['name'], x['messages']))
                except KeyError as exc:
                    print("BE AWARE! Invalid data has been received from \"%s\"! Err: %s" % (self.my_cfg['host'], str(exc.args)) )
                    for k,v in x.items():
                        print("\t%-15s := %s" % (k,v))
                    self.StringList.append((x['name'], '-1'))
                    continue
        else:
            print("No data were received from site! JSON object wasn't initialized!")
        return

    def getCreateTemplate(self, sys_time):
        common_templ = ['--start', '', '--step', '', 'DS:msg:GAUGE:%d:0:U', 'RRA:AVERAGE:0.5:1:%d',
                        'RRA:MHWPREDICT:%d:0.1:0.0035:%d', 'RRA:FAILURES:%d:5:7:4']
        common_templ[1] = str(sys_time)
        common_templ[3], int_step = self._step, int(self._step)
        common_templ[4] = common_templ[4] % (2 * int_step)
        common_templ[5] = common_templ[5] % (2419200 / int_step)
        common_templ[6] = common_templ[6] % (2419200 / int_step, self._season)
        common_templ[7] = common_templ[7] % (2419200 / int_step)
        return common_templ


    def updateRRD(self, sys_time):
        day_season_rrd = self.getCreateTemplate(sys_time)
        for x in self.DataList:
            rrd_db_name = os.path.join(self._rrd_dir, x['objName'][1:-1] + '.rrd')
            if x['msgCount'] == 0:
                valueStr = str(sys_time) + ':' + str(x['msgCount'] + random.random())
            else:
                valueStr = str(sys_time) + ':' + str(x['msgCount'])
            self.rrd_worker.rrd_update(rrd_db_name, day_season_rrd, valueStr)
        return

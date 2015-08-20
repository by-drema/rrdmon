__author__ = 'drema'


import os, sys
import signal
import rrdtool
from lib.wraprrd import RRDer

from datetime import datetime, timedelta
import time

from bottle import Bottle, run, route, static_file, view, template, post, request
import bottle


class Web():
    def __init__(self, config):
        self.config = config
        self.stdin_path = '/dev/null'
        self.stdout_path = self.config['webserv']['logfile']
        self.stderr_path = self.config['webserv']['logfile']
        self.pidfile_path = self.config['webserv']['pidfile']
        self.pidfile_timeout = 10
        self.host = '0.0.0.0'
        self.port = self.config['webserv']['port']
        self.static_path = self.config['webserv']['static_dir']
        self.templ_path = self.config['webserv']['templ_dir']
        bottle.TEMPLATE_PATH.append(self.templ_path)
        self.allowed_types = ['rmq', 'disk', 'cpu']

    def home(self):
        monitors_info_dict=self.get_monitors_dict()
        return bottle.template('home.html', monitors_info=monitors_info_dict)

    def stats(self):
        start_date = request.query.date_from
        end_date = request.query.date_to
        graph_type = request.query.graph
        monitor = request.query.monitor
        qname = request.query.queue

        monitor_dir = os.path.join(self.config['daemon']['monitors_dir'], monitor + '/rrd')

        ### validated_data = tuple(start_tim_in_utc, delta_in_secs)  -- наверное, есть смысл переделать в словарь это добро
        ### gen_image завязан еще в common_check() в классе монитора, поэтому выпилить enddate оттуда пока сложновато
        validated_data = self.validate_dates(start_date, end_date)

        if None in validated_data or not monitor or not qname:
            return bottle.template('404.html', start_date=start_date, end_date=end_date, monitor=monitor, qname=qname)

        # проверка, не пытаются ли запросить js-график для сета данных БОЛЬШЕ 7 дней
        if validated_data[1] > 604800 and graph_type == 'js-graph':
            return '''
            <script>
                alert(\'Time interval is too long for using js-graph! You can use it MAX for 7 days.\')
                location.replace("/");
            </script>
            '''

        if graph_type == "rrd-graph":
            RRDer.gen_image(None, os.path.join(self.static_path, 'pictures'),
                            monitor_dir, qname, validated_data[0]+validated_data[1], validated_data[0])
            return bottle.template("rrdgraph.html")

        elif graph_type == 'js-graph':
             fails_for_queue = self.get_csv_files_for_queue(monitor, qname, validated_data[0], validated_data[1])
             return bottle.template("jsgraph.html", queue=qname, fails_list=fails_for_queue)
        else:
            return "OUT OF CONTROL!"


    def get_rrd_data(self, fname, cf, ts_begin, ts_delta):
        ts_end = ts_begin + ts_delta
        rrdfetch_result = rrdtool.fetch(fname, cf, "--start", str(ts_begin), "--end", str(ts_end))
        '''
        rrdfetch output:
        [
          (select_from, select_to, select_step),
          (name_of_DS),
          [
            (value1, ),
            (value2, ),
            (None, ),
            (value3, ),
            etc..
          ]
        ]
        '''
        select_from, select_to, select_step = rrdfetch_result[0]
        data_set = rrdfetch_result[2]
        time_range = range(select_from, select_to, select_step)
        result = [(tstamp, data_point[0]) if data_point[0] is not None else (tstamp, '') for (tstamp, data_point) in
                  zip(time_range, data_set)]
        return result


    def get_csv_files_for_queue(self, monitor, qname, ts_start, ts_delta):
        csv_path = os.path.join(self.static_path, 'csv')
        rrd_path = os.path.join(self.config['daemon']['monitors_dir'], monitor + '/rrd')
        start_date, end_date = str(ts_start), str(ts_start + ts_delta)
        CFs = ['AVERAGE', 'MHWPREDICT', 'DEVPREDICT', 'FAILURES']

        t_start = time.time()
        results = {}

        rrdfetch_result = rrdtool.fetch(os.path.join(rrd_path, qname + '.rrd'), CFs[0], "--start", start_date, "--end",
                                        end_date)
        rrd_info = rrdtool.info(os.path.join(rrd_path, qname + '.rrd'))

        select_from, select_to, select_step = rrdfetch_result[0]
        SEASON_LEN = rrd_info['step'] * int(rrd_info['rra[2].rows'])
        yesterday_ts_start = ts_start - SEASON_LEN

        time_range_utc = range(select_from, select_to, select_step)

        for cf in CFs:
            results[cf] = self.get_rrd_data(os.path.join(rrd_path, qname + '.rrd'), cf, ts_start, ts_delta)

        results['YESTERDAY'] = self.get_rrd_data(os.path.join(rrd_path, qname + '.rrd'), 'AVERAGE', yesterday_ts_start, ts_delta)

        time_range_str = [time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(ts)) for ts in time_range_utc]

        csv_fname = os.path.join(csv_path, qname + '.csv')

        fail_ranges = list(map(lambda x: str(x[0]) if x[1] else '', results['FAILURES']))
        aka = ' '.join(fail_ranges)
        aka = aka.strip()
        aka = aka.split('  ')
        # вот тут вместо цикла можно ещё подумать что-нибудь
        while (aka.count('')):
            aka.remove('')
        aka = [x.strip().split() for x in aka]
        aka = [[int(x[0]) * 1000, int(x[-1]) * 1000] for x in aka]
        # хак для отрисовки зоны фейла в dygraph (когда фейл представляет собой одну точку)
        fail_ranges_result = list(map(lambda x: x if x[0] != x[1] else [x[0], x[1] + 1000 * select_step], aka))

        with (open(csv_fname, 'w')) as csv_f:
            print('Date', 'Deviation', 'Upper Bound', 'Lower Bound', 'Forecast', 'Value', 'Yesterday', sep=',', file=csv_f)
            for ts, dev, mhw, avg, yes in zip(time_range_str, results['DEVPREDICT'], results['MHWPREDICT'],
                                         results['AVERAGE'], results['YESTERDAY']):
                pos_dev_predict, neg_dev_predict = None, None
                if dev[1] and mhw[1]:
                    pos_dev_predict = 2 * dev[1] + mhw[1]
                    neg_dev_predict = -2 * dev[1] + mhw[1]
                else:
                    pos_dev_predict, neg_dev_predict = '', ''
                print(ts, (-1) * dev[1], pos_dev_predict, neg_dev_predict, mhw[1], avg[1], yes[1], sep=',', file=csv_f)

        t_end = time.time()
        print("Обработка данных очереди (%s) заняла: %s секунд" % (qname, (t_end - t_start)), file=sys.stderr)
        return fail_ranges_result



    def validate_dates(self, start_date, end_date):
        date_format = "%d-%m-%Y %H:%M:%S"

        if not start_date or not end_date:
            return (None, None)
        else:
            dtime_start = datetime.strptime(start_date, date_format)
            dtime_start_utc = dtime_start.timestamp()
            dtime_end = datetime.strptime(end_date, date_format)
            dtime_end_utc = dtime_end.timestamp()
            delta = (dtime_end - dtime_start).total_seconds()
            if delta < 0:
                return (None, None)
            else:
                return int(dtime_start_utc), int(delta)

    def get_monitors_dict(self):
        result_dict = {}
        monitors_list = os.listdir(self.config['daemon']['monitors_dir'])
        for mon_name in monitors_list:
            result_dict[mon_name] = sorted( [ obj.replace('.rrd', '') for obj in
                                              os.listdir(os.path.join(self.config['daemon']['monitors_dir'], mon_name + '/rrd')) ])
        return result_dict

    def server_static(self, path):
        return static_file(path, root=self.config['webserv']['work_dir'])

    def run(self):
        bottle.run(host=self.host, port=self.port, debug=True)



    # def terminate_me(self, sig_num, frame):
    #     my_pid = open(self.pidfile_path, 'r')
    #     ret_code = os.kill(int(my_pid.read().strip()), signal.SIGINT)
    #     if not ret_code:
    #         print("Bottle was stopped successfully")
    #     else:
    #         print("Some problems with stopping Bottle: retcode = %d" % my_pid)
    #     my_pid.close()

import threading
import os

class Timer(threading.Thread):
    def __init__(self, interval, func, param, t_name=None):
        threading.Thread.__init__(self, name=t_name)
        self._finished = threading.Event()
        self.func = func
        self.param = param
        self.set_timer(interval)


    def set_timer(self, interval):
        self.interval = interval


    def stop(self):
        self._finished.set()


    def run(self):
        while 1:
            if self._finished.isSet():
                return
            self.func(*self.param)
            self._finished.wait(self.interval)


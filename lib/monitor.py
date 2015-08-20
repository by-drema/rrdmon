import time

class Monitor:
    _step = ''
    _season = ''
    _check_flag = False
    COMMON_CFG = None

    def __init__(self, config, chk_flag):
        self.COMMON_CFG = config
        self._check_flag = chk_flag

    #переопределить в подклассе
    def updateRRD(self, sys_time):
        pass

    #переопределить в подклассе
    def getVals(self, sys_time):
        pass

    #переопределить в подклассе
    def getData(self):
        pass

    def monitoring(self):
        systemTime = int(time.time())

        self.DataList = []
        self.StringList = []

        self.getData()
        self.getVals(systemTime)
        self.updateRRD(systemTime)

        if self._check_flag:
            self.rrd_worker.common_check(systemTime)
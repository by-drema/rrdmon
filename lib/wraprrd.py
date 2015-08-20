import os, sys
import time

import rrdtool
import pickle
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart


class RRDer():

    COMMASPACE = ', '
    rrdpath = ''
    pngpath = ''
    active_aberrations_file = 'active_fails.pkl'

    mailsender = ''
    mailreceip = ''
    mailserver = ''
    senderpass = ''

    def __init__(self, config, rrdpath, pngpath):
        self.mailsender = config['Email']['mailsender']
        self.mailreceip = config['Email']['mailreceip'].split()
        self.mailserver = config['Email']['mailserver']
        self.senderpass = config['Email']['senderpass']

        self.rrdpath = rrdpath
        self.pngpath = pngpath
        self.active_aberrations_file = os.path.join(self.pngpath, '../' + self.active_aberrations_file)

    def send_alert_attached(self, subject, flist):
        """ Will send e-mail, attaching png
        files in the flist.
        """
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = self.mailsender
        msg['To'] = self.COMMASPACE.join(self.mailreceip)
        for filename in flist:
            png_file = os.path.join(self.pngpath, filename.replace('.rrd','.png'))
            print (png_file)
            with open(png_file, 'rb') as fp:
                img = MIMEImage(fp.read())
            msg.attach(img)
        mserver = smtplib.SMTP(self.mailserver)
        mserver.starttls()
        mserver.login(self.mailsender, self.senderpass)
        mserver.sendmail(self.mailsender, self.mailreceip, msg.as_string())
        mserver.quit()


    def check_aberration(self, fname):
        """ This will check for begin and end of aberration
            in file. Will return:
            0 if aberration not found. 
            1 if aberration begins
            2 if aberration ends
        """
        ab_status = 0
        rrdfilename = os.path.join(self.rrdpath, fname)
        info = rrdtool.info(rrdfilename)
    
        if not os.path.exists(self.active_aberrations_file):
            abr_list = {}
        else:
            with open(self.active_aberrations_file, 'rb') as fails:
                abr_list = pickle.load(fails)
    
        fails_history = list(info['rra[6].cdp_prep[0].history'])
        fails_threshold = int(info['rra[6].failure_threshold'])
        curr_state = fails_history.count('1')
    
        objName = fname.split('.')[0]
        if objName not in abr_list:
            abr_list[objName] = 'empty'
    
        if curr_state >= fails_threshold:
            if abr_list[objName] in ('end', 'empty'):
                ab_status = 1
                abr_list[objName] = 'start'
        else:
            if abr_list[objName] == 'start':
                ab_status = 2
                abr_list[objName] = 'end'
            elif abr_list[objName] == 'end':
                abr_list[objName] = 'empty'
    
        with open(self.active_aberrations_file, 'wb') as fails:
            pickle.dump(abr_list, fails)
    
        return ab_status



    def gen_image(self, dest_path, rrd_path, fname, enddate, begdate=0):
        """
        Generates png file from rrd database:
        rrdpath - the path where rrd is located
        pngpath - the path png file should be created in
        fname - rrd file name, png file will have the same name .png extension
        width - chart area width
        height - chart area height
        begdate - unixtime
        enddate - unixtime
        """
        # File names
# if fname given from monitoring:
        if fname.endswith('.rrd'):
            pngfname = os.path.join(dest_path, fname.replace('.rrd', '.png'))
            rrdfname = os.path.join(rrd_path, fname)
# else we take this argument from Tornado and this - objectName
        else:
            pngfname = os.path.join(dest_path, 'file.png')
            rrdfname = os.path.join(rrd_path, fname+'.rrd')
        # Get iformation from rrd file
        info = rrdtool.info(rrdfname)
        rrdtype = info['ds[msg].type']
        rrdstep = info['step']
        rrdseason = rrdstep * int(info['rra[2].rows'])

# if begdate given from monitoring:
        if not begdate:
            begdate = enddate - 2 * rrdseason

        ldaybeg = str(begdate - rrdseason)
        ldayend = str(enddate - rrdseason)
# "yesterday"-shift : сдвиг по значениям на один сезон (в нашем случае сезон=24h, поэтому и "yesterday"-shift)
        shift = str(rrdseason)

        width = '700'
        height = '250'

        endd_str = time.strftime("%d/%m/%Y %H:%M:%S",(time.localtime(int(enddate)))).replace(':','\:')
        begd_str = time.strftime("%d/%m/%Y %H:%M:%S",(time.localtime(int(begdate)))).replace(':','\:')
        title = 'Chart for: '+fname.split('.')[0]

        multip = str(round((int(enddate) - int(begdate))/int(rrdstep)))
        print("png = %s queue = %s enddate = %d  begdate = %d  ldaybeg = %s  ldayend = %s season = %d " % (dest_path, fname, enddate, begdate, ldaybeg, ldayend, rrdseason), file=sys.stderr )

        # Make png image
        rrdtool.graph(pngfname,
        '--width', width,'--height', height,
        '--start',str(begdate),'--end',str(enddate),'--title='+title,
        '--lower-limit','0',
        '--slope-mode',
        '-m', '3',
        'COMMENT:From\:'+begd_str+'  To\:'+endd_str+'\\c',
        'DEF:value='+rrdfname+':msg:AVERAGE',
        'DEF:pred='+rrdfname+':msg:MHWPREDICT',
        'DEF:dev='+rrdfname+':msg:DEVPREDICT',
        'DEF:fail='+rrdfname+':msg:FAILURES',
        'DEF:yvalue='+rrdfname+':msg:AVERAGE:start='+ldaybeg+':end='+ldayend,
        'SHIFT:yvalue:'+shift,
        'CDEF:upper=pred,dev,2,*,+',
        'CDEF:lower=pred,dev,2,*,-',
        'CDEF:ndev=dev,-1,*',
        'CDEF:tot=value,'+multip+',*',
        'CDEF:ytot=yvalue,'+multip+',*',
        'TICK:fail#FDD017:1.0:"Failures"\\n',
        'AREA:yvalue#C0C0C0:"Yesterday\:"',
        'GPRINT:ytot:AVERAGE:"Total\:%8.0lf"',
        'GPRINT:yvalue:MAX:"Max\:%8.0lf"',
        'GPRINT:yvalue:AVERAGE:"Average\:%8.0lf" \\n',
        'LINE3:value#0000ff:"Value    \:"',
        'GPRINT:tot:AVERAGE:"Total\:%8.0lf"',
        'GPRINT:value:MAX:"Max\:%8.0lf"',
        'GPRINT:value:AVERAGE:"Average\:%8.0lf" \\n',
        'LINE1:upper#ff0000:"Upper Bound "',
        'LINE1:pred#ff00FF:"Forecast "',
        'LINE1:ndev#000000:"Deviation "',
        'LINE1:lower#00FF00:"Lower Bound "')


    def common_check(self, enddate):
        # List of new aberrations
        begin_ab = []
        # List of gone aberrations
        end_ab = []
        # List files and generate charts
        for fname in os.listdir(self.rrdpath):
            self.gen_image(self.pngpath, self.rrdpath, fname, enddate )
        # Now check files for being in aberrations
        for fname in os.listdir(self.rrdpath):
            ab_status = self.check_aberration(fname)
            if ab_status == 1:
                begin_ab.append(fname)
            if ab_status == 2:
                end_ab.append(fname)
        if len(begin_ab) > 0:
            self.send_alert_attached('New aberrations were detected',begin_ab)
        if len(end_ab) > 0:
            self.send_alert_attached('Abberations have gone',end_ab)

 
    def rrd_update(self, db_name, create_template, valueStr):
        try:
            if not os.path.exists(db_name):
                rrdtool.create(db_name, *create_template)
            else:
                rrdtool.update(db_name, valueStr)
        except rrdtool.OperationalError as err:
            print("We have some troubles with creating/updating \"%s\" database !\nError: %s" % (db_name, err.args[0]), file=sys.stderr)


if __name__ == '__main__':
    print("Bingo!")
    k = RRDer()

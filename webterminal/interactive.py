import socket
import sys
from paramiko.py3compat import u
from django.utils.encoding import smart_unicode
import os

try:
    import termios
    import tty
    has_termios = True
except ImportError:
    has_termios = False
    raise Exception('This project does\'t support windows system!')
try:
    import simplejson as json
except ImportError:
    import json
import sys
import time
import codecs
import io
import re
import errno
import subprocess
from django.contrib.auth.models import User 
from django.utils import timezone
from webterminal.models import SshLog
from webterminal.settings import MEDIA_ROOT

def mkdir_p(path):
    """
    Pythonic version of "mkdir -p".  Example equivalents::

        >>> mkdir_p('/tmp/test/testing') # Does the same thing as...
        >>> from subprocess import call
        >>> call('mkdir -p /tmp/test/testing')

    .. note:: This doesn't actually call any external commands.
    """
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            pass
        else:
            raise # The original exception
        
def interactive_shell(chan,channel,log_name=None):
    if has_termios:
        posix_shell(chan,channel,log_name=log_name)
    else:
        sys.exit(1)
       
class CustomeFloatEncoder(json.JSONEncoder):
    def encode(self, obj):
        if isinstance(obj, float):
            return format(obj, '.6f')
        return json.JSONEncoder.encode(self, obj)

def posix_shell(chan,channel,log_name=None):
    from webterminal.asgi import channel_layer
    stdout = list()
    begin_time = time.time()
    last_write_time = {'last_activity_time':begin_time}    
    try:
        chan.settimeout(0.0)
        while True:
            try:               
                x = u(chan.recv(1024))
                if len(x) == 0:
                    channel_layer.send(channel, {'text': json.dumps(['disconnect',smart_unicode('\r\n*** EOF\r\n')]) })
                    break
                now = time.time()
                delay = now - last_write_time['last_activity_time']
                last_write_time['last_activity_time'] = now                
                if x == "exit\r\n" or x == "logout\r\n" or x == 'logout':
                    pass
                else:
                    stdout.append([delay,codecs.getincrementaldecoder('UTF-8')('replace').decode(x)]) 
                channel_layer.send(channel, {'text': json.dumps(['stdout',smart_unicode(x)]) })
            except socket.timeout:
                pass
            except Exception,e:
                channel_layer.send(channel, {'text': json.dumps(['stdout','A bug find,You can report it to me' + smart_unicode(e)]) })

    finally:
        attrs = {
            "version": 1,
            "width": 90,#int(subprocess.check_output(['tput', 'cols'])),
            "height": 40,#int(subprocess.check_output(['tput', 'lines'])),
            "duration": round(time.time()- begin_time,6),
            "command": os.environ.get('SHELL',None),
            'title':None,
            "env": {
                "TERM": os.environ.get('TERM'),
                "SHELL": os.environ.get('SHELL','sh')
                },
            'stdout':list(map(lambda frame: [round(frame[0], 6), frame[1]], stdout))
            }
        mkdir_p('/'.join(os.path.join(MEDIA_ROOT,log_name).rsplit('/')[0:-1]))
        with open(os.path.join(MEDIA_ROOT,log_name), "a") as f:
            f.write(json.dumps(attrs, ensure_ascii=False,cls=CustomeFloatEncoder,indent=2))
        
        audit_log=SshLog.objects.get(channel=channel,log=log_name.rsplit('/')[-1].rsplit('.json')[0])
        audit_log.is_finished = True
        audit_log.end_time = timezone.now()
        audit_log.save()
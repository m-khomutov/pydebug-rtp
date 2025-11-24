import random
import string
import struct


class Session:
    """RTSP Session parameters"""
    def __init__(self, content_base, filename, address):
        self._session_id=''
        self._transport=[]
        self.content_base=content_base
        self.sdp=''
        self._play_range=''
        self.rtpmap={}
        with open(filename, 'rb') as f:
            sdp_size=struct.unpack(">I", f.read(4))[0]
            sdp=f.read(sdp_size).decode('utf-8').split('\r\n')
            for line in sdp:
                if line.startswith('o='):
                    fields=line.split(' ')
                    fields[-1]=address
                    line=' '.join(fields)
                elif line.startswith('a=control'):
                    fields=line.split(':')
                    line=fields[0]+':'+content_base+'/'+fields[-1].split('/')[-1]
                elif line.startswith('a=rtpmap'):
                    fields=line.split(':')[1].split(' ')[1].split('/')
                    self.rtpmap[fields[0]]=fields[1].strip()
                self.sdp+=line.strip()+'\r\n'

    def valid_session(self, headers):
        """Verifies session identity"""
        session_id = [k for k in headers if 'Session: ' in k][0][9:]
        return session_id == self._session_id

    def add_stream(self, headers):
        """Adds a controlled stream"""
        self._transport.append([k for k in headers if 'Transport: ' in k][0])
        return self._transport[-1]

    def identification(self, params=''):
        """Returns session identification"""
        if not self._session_id:
            source = string.ascii_letters + string.digits
            self._session_id = ''.join(map(lambda x: random.choice(source), range(16)))
        return ''.join(['Session: ', self._session_id, params, '\r\n'])

    def play_range(self, headers):
        """Returns media duration in Clock or NPT format"""
        self._play_range=[x for x in headers if 'Range: ' in x]
        self._play_range = self._play_range[0] if self._play_range else ''
        return self._play_range

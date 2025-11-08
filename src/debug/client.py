import socket
import errno
import os
import urllib.parse
from base64 import b64encode
from base64 import b64decode
from datetime import datetime, timezone
from hashlib import md5
from time import sleep
import threading
from .rtp import *

def thread_function(client):
    client.receive_stream()

class RtspDialog:
    def __init__(self, url, query):
        self._user_agent='pyRtspTest\r\n'
        self.url=url
        if len(query):
            self.query='?'+query
        else:
            self.query=''
        self.authorization=''
        self.session=''
        self._range='npt=0.000-\r\n'

    def options(self, cseq=1):
        return "OPTIONS "+self.url+self.query+" RTSP/1.0\r\nCSeq: "+str(cseq)+"\r\nUser-Agent: "+self._user_agent+self.authorization+"\r\n"

    def describe(self, cseq):
        return "DESCRIBE "+self.url+self.query+" RTSP/1.0\r\nAccept: application/sdp\r\nCSeq: "+str(cseq)+"\r\nUser-Agent: "+self._user_agent+self.authorization+"\r\n"

    def setup(self, cseq, content_base, control):
        if control.startswith('rtsp://'):
            return "SETUP "+control+' RTSP/1.0\r\nTransport: RTP/AVP/TCP;unicast;interleaved=0-1\r\nCSeq: '+str(cseq)+"\r\nUser-Agent: "+self._user_agent+self.authorization+'\r\n'
        if content_base:
            return "SETUP "+content_base+control+' RTSP/1.0\r\nTransport: RTP/AVP/TCP;unicast;interleaved=0-1\r\nCSeq: '+str(cseq)+"\r\nUser-Agent: "+self._user_agent+self.authorization+'\r\n'
        return "SETUP "+self.url+self.query+"/"+control+' RTSP/1.0\r\nTransport: RTP/AVP/TCP;unicast;interleaved=0-1\r\nCSeq: '+str(cseq)+"\r\nUser-Agent: "+self._user_agent+self.authorization+'\r\n'

    def play(self, cseq, content_base, a_range, scale):
        if not content_base:
            ret="PLAY "+self.url+self.query+" RTSP/1.0\r\n"
        else:
            ret="PLAY "+content_base+" RTSP/1.0\r\n"
        if a_range:
            ret+="Range: "+a_range+"\r\n"
        else:
            ret+="Range: "+self._range
        if scale:
            ret+="Scale: "+str(scale)+"\r\n"
        return ret+"CSeq: "+str(cseq)+"\r\nUser-Agent: "+self._user_agent+self.session+self.authorization+"\r\n"

    def pause(self, cseq, content_base, a_range):
        if not content_base:
            ret="PAUSE "+self.url+self.query+" RTSP/1.0\r\n"
        else:
            ret="PAUSE "+content_base+" RTSP/1.0\r\n"
        if len(a_range):
            ret += "Range: " + a_range + "\r\n"
        return ret + "CSeq: " + str(cseq) + "\r\nUser-Agent: " + self._user_agent + self.session + self.authorization + "\r\n"

    def teardown(self, cseq, content_base):
        if not content_base:
            return "TEARDOWN "+self.url+self.query+" RTSP/1.0\r\nCSeq: "+str(cseq)+"\r\nUser-Agent: "+self._user_agent+self.session+self.authorization+"\r\n"
        return "TEARDOWN "+content_base+" RTSP/1.0\r\nCSeq: "+str(cseq)+"\r\nUser-Agent: "+self._user_agent+self.session+self.authorization+"\r\n"


class RtspReply:
    def __init__(self, reply):
        self.reply=reply
        self.headers=self.reply.splitlines()
        self.result=int(self.headers[0].split(' ')[1])
        self.cseq=None
        self.session=''
        self.authentication=''
        self.content_length=0
        self.content_base=''
        self.range=''
        for hdr in self.headers:
            if hdr.startswith('CSeq: '):
                self.cseq=int(hdr.split(' ')[1])
            elif hdr.startswith('Content-Length: '):
                self.content_length=int(hdr.split(': ')[1])
            elif hdr.startswith('Session: '):
                self.session=hdr.split(': ')[1]
                if ';' in self.session:
                    self.session, self.timeout = self.session.split(";")
            elif hdr.startswith('WWW-Authenticate: '):
                self.authentication=hdr.split(': ')[1]
            elif hdr.startswith('Content-Base: '):
                self.content_base=hdr.split(': ')[1]
            elif hdr.startswith('Range: '):
                self.range=hdr.split(': ')[1]

    def __str__(self):
        return self.reply


class SDP:
    def __init__(self, headers):
        self.rtpmap=''
        self.fmtp=''
        self.control=''
        self.range=''
        self.full_range=''
        vs=False
        for hdr in headers:
            if hdr.startswith('m=video'):
                vs=True
            elif hdr.startswith('m=audio'):
                vs=False
            elif hdr.startswith('a=range:'):
                self.range=hdr.split(':')[1].split(';')
                self.full_range=self.range[0].split('-')[0]+'-'+self.range[-1].split('-')[1]
            elif vs:
                if hdr.startswith('a=rtpmap:'):
                    self.rtpmap=hdr.split(':')[1]
                elif hdr.startswith('a=fmtp:'):
                    self.fmtp=hdr.split(':')[1]
                elif hdr.startswith('a=control:'):
                    self.control=hdr.split('control:')[1]

class Golomb:
    def __init__(self, data):
        self._bits=''
        self.bits_idx=0
        for b in data:
            self._bits+=bin(b)[2:]

    def next(self):
        res=0
        idx=self.bits_idx
        while self._bits[idx] != '1':
            idx += 1
        if idx != self.bits_idx:
            res=int(self._bits[idx:idx+idx], 2)-1
            self.bits_idx=idx
        else:
            self.bits_idx+=1
        return res


class SliceType(IntEnum):
    P=0,
    B=1,
    I=2,
    SP=3,
    SI=4


class SliceHeader:
    def __init__(self, data):
        golomb=Golomb(data)
        self._first_mb_in_slice=golomb.next()
        slice_type=golomb.next()
        if slice_type==SliceType.P or slice_type==SliceType.P+5:
            self._slice_type='P'
        elif slice_type==SliceType.B or slice_type==SliceType.B+5:
            self._slice_type='B'
        elif slice_type==SliceType.I or slice_type==SliceType.I+5:
            self._slice_type='I'
        if slice_type==SliceType.SP or slice_type==SliceType.SP+5:
            self._slice_type='SP'
        elif slice_type==SliceType.SI or slice_type==SliceType.SI+5:
            self._slice_type='SI'

    def __str__(self):
        return f'mb:{self._first_mb_in_slice} {self._slice_type}'


class DumpType(IntEnum):
    H264=0,
    RTP=1


class Client:
    def __init__(self, dumps):
        self.dumps=dumps
        self._sock=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setblocking(True)
        self.cseq=1
        self._lock=threading.Lock()
        self._url=None
        self.running=True
        self._command_queue=[]
        self._verbose=False
        self.nalunit=b''
        self.sdp=None
        self.exception=None
        self._run_thread=None
        self._dialog=None
        self._content_base=''
        self._basic_auth=None
        self._digest_auth_parameters=None
        for dump in self.dumps:
            if dump:
                try:
                    os.remove(dump)
                except:
                    pass

    def __del__(self):
        try:
            if self._dialog and len(self._dialog.session):
                self._dialog.authorization = self._prepare_authorization('TEARDOWN')
                reply = self._send_command(self._dialog.teardown(self.cseq, self._content_base))
                print(f'{datetime.now()} {reply}')
        except ConnectionResetError:
            pass
        self._sock.close()

    def connect(self, url):
        self._url = urllib.parse.urlparse(url)
        if self._url.scheme != 'rtsp':
            raise AttributeError('only rtsp scheme is supported')
        if not self._url.port:
            netloc = self._url.netloc + ':554'
            u = self._url
            self._url = urllib.parse.ParseResult(scheme=u.scheme, netloc=netloc, path=u.path, params=u.params, query=u.query, fragment=u.fragment)
        self._dialog=RtspDialog(self._url.scheme+'://'+self._url.hostname+':'+str(self._url.port)+self._url.path, self._url.query)
        self._sock.connect((self._url.hostname, self._url.port))
        self._sock.setblocking(False)
        reply=self._send_command(self._dialog.options(self.cseq))
        self.cseq = reply.cseq+1

        reply=self._send_command(self._dialog.describe(self.cseq))
        self.cseq = reply.cseq+1
        if reply.result == 401:
            reply = self._send_command(self._dialog.describe(self.cseq))
            self.cseq = reply.cseq+1

        self.sdp=SDP(reply.headers)
        if len(reply.content_base) > 0:
            self._dialog.url=reply.content_base
            self._content_base=reply.content_base

        self._dialog.authorization = self._prepare_authorization('SETUP')
        reply = self._send_command(self._dialog.setup(reply.cseq + 1, reply.content_base, self.sdp.control))
        self.cseq = reply.cseq+1

        self._dialog.session='Session: '+reply.session+'\r\n'
        if self.sdp and len(self.sdp.full_range):
            self._dialog.range=self.sdp.full_range+'\r\n'

        self._dialog.authorization = self._prepare_authorization('PLAY')
        reply = self._send_command(self._dialog.play(reply.cseq + 1, self._content_base, self.sdp.full_range if self.sdp else None, 1))
        self.cseq = reply.cseq+1

    def run(self):
        self._run_thread = threading.Thread(target=thread_function, args=(self,))
        self._run_thread.start()

    def is_running(self):
        with self._lock:
            return self.running

    def stop(self):
        with self._lock:
            self.running=False
        if self._run_thread:
            self._run_thread.join()

    def play(self, http_params):
        with self._lock:
            self._command_queue.append({'play': http_params})

    def pause(self):
        with self._lock:
            self._command_queue.append({'pause': ''})

    def get_parameter(self, http_params):
        with self._lock:
            self._command_queue.append({'get_parameter': http_params})

    def receive_stream(self):
        while self.is_running():
            self._check_command_queue()
            data=b''
            try:
                interleaved_hdr=self._receive_some(4)
                if len(interleaved_hdr) != 4:
                    continue
                interleaved=RtpInterleaved(interleaved_hdr)
                if self._verbose:
                    print(interleaved)
                data=self._receive_some(interleaved.size)
                if len(data) != interleaved.size:
                    continue
                self._store_rtp_packet(b''.join([interleaved_hdr, data]))
                rtp_hdr=RtpHeader(data)
                if self._verbose:
                    print(rtp_hdr)
                data_end = len(data) if rtp_hdr.P == 0 else len(data) - int(data[-1])
                if data_end <= rtp_hdr.size:
                    continue
                nalu=RtpNalunit(data[rtp_hdr.size:data_end])
                if nalu.header.Type == NalunitType.FU_A:
                    if nalu.fu_header.S == 1:
                        self.nalunit=((nalu.header.F < 7) | (nalu.header.NRI << 5) | (nalu.fu_header.Type)).to_bytes(1, byteorder='big')
                    self.nalunit += data[rtp_hdr.size+2:data_end]
                    if nalu.fu_header.E == 1:
                        nalu=RtpNalunit(self.nalunit)
                        print(f'{nalu} {SliceHeader(self.nalunit[1:3])} sz:{nalu.size}')
                        self._store_frame(self.nalunit)
                else:
                    if nalu.header.Type == NalunitType.NON_IDR:
                        print(f'{nalu} {SliceHeader(data[rtp_hdr.size + 1:rtp_hdr.size + 3])} sz:{nalu.size}')
                    else:
                        print(f'{nalu} sz: {nalu.size}')
                    self._store_frame(data[rtp_hdr.size:data_end])

            except InvalidRtpInterleaved as err:
                self.exception = err
                if data == b'RTSP':
                    try:
                        self.get_reply(data, '')
                    except RuntimeError as rte:
                        self.exception = rte
                with self._lock:
                    self.running = False
                break

    def _receive_some(self, length):
        data=bytearray()
        while len(data) < length:
            if not self.is_running():
                return b''
            try:
                data += self._sock.recv(length - len(data))
            except socket.error as e:
                if e.args[0] == errno.EAGAIN or e.args[0] == errno.EWOULDBLOCK:
                    self._check_command_queue()
                    sleep(0.001)
                    continue
        return data

    def _check_command_queue(self):
        command=dict()
        with self._lock:
            if len(self._command_queue) > 0:
                command=self._command_queue.pop(0)
                self._verbose=False
        self._apply_command(command)

    def _apply_command(self, command):
        if command:
            key, params = list(command.keys())[0], list(command.values())[0]
            if key == 'play':
                a_range=None
                a_scale=1
                for param in params.split('&'):
                    p=param.split('=')
                    if len(p)==2:
                        if p[0]=='pos':
                            utc_dt = datetime.fromtimestamp(int(p[1])).astimezone().astimezone(timezone.utc)
                            a_range="clock="+utc_dt.strftime('%Y%m%dT%H%M%S')+'Z-'
                        elif p[0]=='scale':
                            a_scale=int(p[1])
                self._dialog.authorization=self._prepare_authorization('PLAY')
                self._send_command(self._dialog.play(self.cseq+1, self._content_base, a_range, a_scale))
                self.cseq+=1
            elif key == 'pause':
                self._dialog.authorization = self._prepare_authorization('PAUSE')
                reply = self._send_command(self._dialog.pause(self.cseq, self._content_base, params))
                self.cseq = reply.cseq + 1
            with self._lock:
                self._verbose=False

    def _send_command(self, command):
        print(f'{datetime.now()} {command}')
        self._sock.sendall(str.encode(command))
        data=b''
        return self.get_reply(data, command)

    def get_reply(self, data, command):
        idx_start=-1
        while self.is_running():
            data+=self._receive_some(1)
            if len(data) > 10:
                if idx_start == -1:
                    idx_start = data.find(b'RTSP/1.0')
                idx_end=data.find(b'\x0d\x0a\x0d\x0a')
                if idx_start != -1 and idx_end != -1:
                    break
        if idx_start==-1:
            return b''
        reply=RtspReply(data[idx_start:idx_end+4].decode('utf8'))
        if reply.content_length != 0:
            sdp=data[idx_end+4:]
            while len(sdp) < reply.content_length:
                sdp+=self._sock.recv(reply.content_length-len(sdp))
            reply=RtspReply(data[idx_start:idx_end+4].decode('utf8')+sdp.decode('utf8'))
        print(f'{datetime.now()} {reply}')
        if reply.result == 401:
            self._dialog.authorization=self._set_authorization(reply, command)
            if len(self._dialog.authorization) == 0:
                raise RuntimeError(reply.headers[0])
        elif reply.result == 500:
            print(b64decode(str(reply).split('\x0d\x0a\x0d\x0a')[1]))
        elif reply.result < 200 or reply.result >= 300:
            raise RuntimeError(reply.headers[0])
        return reply

    def _set_authorization(self, reply, command):
        method = command.split(' ')[0]
        if reply.authentication.startswith("Basic"):
            self._basic_auth='Authorization: Basic ' + b64encode((self._url.username+":"+self._url.password).encode()).decode("ascii")+'\r\n'
            return self._basic_auth
        self._digest_auth_parameters=self._parse_digest_header(reply.authentication.split('Digest ')[1])
        return self._prepare_digest_authorization(method)

    def _prepare_digest_authorization(self, method):
        if not self._digest_auth_parameters:
            return ''
        uri=self._url.scheme+'://'+self._url.hostname+':'+str(self._url.port)+self._url.path+self._url.query
        ha1_content=self._url.username+':'+self._digest_auth_parameters["realm"]+':'+self._url.password
        ha1_value=md5(ha1_content.encode('utf-8')).hexdigest()
        ha2_content=method+':'+uri
        ha2_value=md5(ha2_content.encode('utf-8')).hexdigest()
        response_content=ha1_value+':'+self._digest_auth_parameters["nonce"]+':'+ha2_value
        response_value=md5(response_content.encode('utf-8')).hexdigest()
        return ('Authorization: Digest username="'+self._url.username+
                '", realm="'+self._digest_auth_parameters["realm"]+
                '", nonce="'+self._digest_auth_parameters["nonce"]+
                '", uri="'+uri+
                '", response="'+response_value+'"\r\n')

    def _parse_digest_header(self, header):
        rc=dict()
        for field in header.split(','):
            pair=field.split('=')
            rc[pair[0].strip(' ')]=pair[1].strip('"')
        return rc

    def _prepare_authorization(self, method):
        if self._basic_auth:
            return self._basic_auth
        return self._prepare_digest_authorization(method)

    def _store_frame(self, nal_unit):
        if self.dumps[DumpType.H264]:
            with open(self.dumps[DumpType.H264], 'ab') as f:
                f.write(b'\x00\x00\x00\x01')
                f.write(nal_unit)

    def _store_rtp_packet(self, packet):
        if self.dumps[DumpType.RTP]:
            with open(self.dumps[DumpType.RTP], 'ab') as f:
                f.write(packet)

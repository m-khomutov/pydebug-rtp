import os
from datetime import datetime
from typing import List
from .session import Session
from .dump import Dump

class Connection:
    @staticmethod
    def _datetime():
        return ''.join(['Date: ', datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S"), ' GMT\r\n'])

    @staticmethod
    def _header(headers, header):
        return [k for k in headers if header + ': ' in k]

    def __init__(self, address, root):
        self._seq_num=1
        self._session=None
        self._dump=None
        self._playing=False
        self._address=address
        self._root=root
        self._dumpfile=''
        print(f'RTSP connect from {self._address}')

    def _sequence_number(self, headers=None):
        if headers:
            self._seq_num=int(Connection._header(headers, 'CSeq')[0].split(': ')[1])
        else:
            self._seq_num+=1
        return ''.join(['CSeq: ', str(self._seq_num), '\r\n'])

    def on_read_event(self, key):
        data = key.fileobj.recv(2048)  # Should be ready to read
        if data:
            key.data.inb += data
            if key.data.inb.find(bytes([0x0d, 0x0a, 0x0d, 0x0a])):
                self._on_rtsp_directive(key.data)
                key.data.inb = b''
                return
        raise EOFError()

    def on_write_event(self, key):
        """Manager write socket event"""
        if key.data.outb:
            sent=key.fileobj.send(key.data.outb)  # Should be ready to write
            key.data.outb = key.data.outb[sent:]
        if self._session and self._playing:
            try:
                key.data.outb = self._dump.get_next_packet()
            except EOFError:
                self._dump.reopen()
                key.data.outb = self._dump.get_next_packet()
            except:  # noqa # pylint: disable=bare-except
                self._playing = False

    def _on_rtsp_directive(self, data):
        """Manages RTSP directive"""
        headers = []
        try:
            directive = data.inb.decode('utf-8')
            print(directive)
            headers = directive.split('\r\n')
            if headers[0][:8] == 'OPTIONS ':
                self._on_options(headers, data)
            elif headers[0][:9] == "DESCRIBE ":
                self._on_describe(headers, data)
            elif headers[0][:14] == "GET_PARAMETER ":
                self._on_get_parameter(headers, data)
            elif headers[0][:6] == "SETUP ":
                self._on_setup(headers, data)
            elif headers[0][:5] == "PLAY ":
                self._on_play(headers, data)
            elif headers[0][:9] == "TEARDOWN ":
                self._on_teardown(headers, data)
        except:  # noqa # pylint: disable=bare-except
            data.outb = ''.join(['RTSP/1.0 400 Bad Request\r\n', self._sequence_number(headers), '\r\n']).encode()
        print(data.outb.decode('utf-8'))

    def _on_options(self, headers, data):
        """Manager OPTIONS RTSP directive"""
        data.outb = ''.join(['RTSP/1.0 200 OK\r\n',
                             self._sequence_number(headers),
                             'Public: OPTIONS, DESCRIBE, SETUP, TEARDOWN, PLAY, PAUSE\r\n\r\n']).encode()

    def _on_describe(self, headers, data):
        """Manager DESCRIBE RTSP directive"""
        content_base = headers[0].split()[1]
        filename = os.path.join(self._root, content_base.split('/')[-1])+'.rtp'
        if not os.path.isfile(filename):
            data.outb = str.encode('RTSP/1.0 404 Not Found\r\n\r\n')
            return
        accept = [k for k in headers if 'Accept: ' in k]
        if accept and accept[0][8:] != 'application/sdp':
            data.outb = ''.join(['RTSP/1.0 405 Method Not Allowed\r\n',
                                 self._sequence_number(headers),
                                 '\r\n']).encode()
            return
        self._session = Session(content_base, filename, self._address[0])
        self._dump=Dump(filename, self._session.rtpmap)
        data.outb = ''.join(['RTSP/1.0 200 OK\r\n',
                             self._sequence_number(headers),
                             self._datetime(),
                             'Content-Base: ', content_base + '\r\n',
                             'Content-Type: application/sdp\r\n',
                             'Content-Length: ', str(len(self._session.sdp)), '\r\n\r\n',
                             self._session.sdp]).encode()

    def _on_get_parameter(self, headers, data):
        """Manages GET_PARAMETER RTSP directive"""
        rc: List[str] = ['RTSP/1.0 200 OK\r\n',
                         self._sequence_number(headers),
                         self._session.identification(),
                         self._datetime(),
                         '\r\n\r\n']
        data.outb = ''.join(rc).encode()
        print(data.outb)

    def _on_setup(self, headers, data):
        """Manager SETUP RTSP directive"""
        if [k for k in headers if 'Session: ' in k] and \
                not self._session.valid_session(headers):
            self._on_session_error(data, headers)
        else:
            transport = self._session.add_stream(headers)
            data.outb = ''.join(['RTSP/1.0 200 OK\r\n',
                                 self._sequence_number(headers),
                                 self._datetime(),
                                 self._session.identification(';timeout=60'),
                                 transport,
                                 '\r\n\r\n']).encode()

    def _on_play(self, headers, data):
        """Manager PLAY RTSP directive"""
        data.outb = ''.join(['RTSP/1.0 200 OK\r\n',
                             self._sequence_number(headers),
                             self._session.play_range(headers),
                             self._datetime(),
                             self._session.identification(),
                             '\r\n']).encode()
        self._playing = True

    def _on_teardown(self, headers, data):
        """Manager TEARDOWN RTSP directive"""
        data.outb = ''.join(['RTSP/1.0 200 OK\r\n',
                             self._sequence_number(headers),
                             self._datetime(),
                             self._session.identification(),
                             '\r\n']).encode()
        self._playing = False

    def _on_session_error(self, data, headers):
        data.outb = ''.join(['RTSP/1.0 454 Session Not Found\r\n',
                             self._sequence_number(headers),
                             '\r\n']).encode()

    def _teardown(self, data):
        data.outb = ''.join(['TEARDOWN '+self._session.content_base+' RTSP/1.0\r\n',
                             self._sequence_number(),
                             self._datetime(),
                             self._session.identification(),
                             '\r\n']).encode()

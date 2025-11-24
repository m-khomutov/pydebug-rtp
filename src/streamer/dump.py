import io
import struct
import time
from .rtp import RtpInterleaved, RtpHeader

class Dump:
    def __init__(self, filename, rtpmap):
        self._filename=filename
        self._timestamp={}
        self._rtpmap=[90000,44100]
        self._frame_length = [0, 0]
        for key,frequency in rtpmap.items():
            if key.upper()=='H264':
                self._rtpmap[0]=float(frequency)
            else:
                self._rtpmap[1]=float(frequency)
        self._open_dump()

    def __del__(self):
        self._dump.close()

    def reopen(self):
        self._dump.close()
        self._open_dump()

    def get_next_packet(self):
        buf=self._read_bytes(16)
        interleaved=RtpInterleaved(buf[0:4])
        chan = 0 if interleaved.channel == 0 else 1
        rtp_header=RtpHeader(buf[4:])
        buf=buf+self._read_bytes(interleaved.size-12)
        self._frame_length[chan] += interleaved.size-12
        if chan == 0 and buf[16] & 0x1f == 28: # FU-A 2 байта: FU indicator и FU header
           self._frame_length[chan] -= 2
        # buf=b'\x24\x02'+buf[2:]+self._read_bytes(interleaved.size - 12)
        if not interleaved.channel in self._timestamp:
            self._timestamp[interleaved.channel]=rtp_header.timestamp
        ts_diff=rtp_header.timestamp-self._timestamp[interleaved.channel]
        if ts_diff:
            if chan == 0:
                if buf[16] & 0x1f == 28: # в FU-A учесть NALU-header
                   self._frame_length[chan] += 1
                time.sleep(ts_diff / self._rtpmap[0])
            print(f'{"audio" if interleaved.channel else "video"} ts_diff: {ts_diff} length: {self._frame_length[chan]}')
            self._frame_length[chan] = 0
        self._timestamp[interleaved.channel]=rtp_header.timestamp
        return buf

    def _open_dump(self):
        self._dump=open(self._filename, 'rb')
        sdp_size = struct.unpack(">I", self._dump.read(4))[0]
        self._dump.seek(sdp_size, io.SEEK_CUR)
        self._timestamp={}

    def _read_bytes(self, count):
        ret=self._dump.read(count)
        if len(ret)==count:
            return ret
        raise EOFError()

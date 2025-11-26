import io
import struct
import time
from .rtp import RtpInterleaved, RtpHeader

class NaluHeader:
    def __init__(self, byte):
        self.F=byte>>7
        self.NRI=(byte>>5) & 3
        self.type=byte & 0x1f

    def __repr__(self):
        return f'F:{self.F} NRI:{self.NRI} type:{self.type}'


class Dump:
    def __init__(self, filename, rtpmap):
        self._filename=filename
        self._timestamp={}
        self._timestamp_ext={}
        self._rtpmap=[90000,44100]
        self._frame_length = []
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
        rtp_header=RtpHeader(buf[4:])
        self._update_timestamp(interleaved.channel, rtp_header.timestamp)
        buf=(buf[0:4]+
             self._marshall_rtp_header(rtp_header, self._timestamp_ext[interleaved.channel])+
             self._read_bytes(interleaved.size-12))
        self._update_frame_length(interleaved, buf[16] & 0x1f)
        if interleaved.channel == 1:
            print(f'rtcp request: {str(interleaved)}')
        if ts_diff := rtp_header.timestamp - self._timestamp[interleaved.channel]:
            if interleaved.channel == 0:
                if buf[16] & 0x1f == 28: # в FU-A учесть NALU-header
                   self._frame_length[interleaved.channel] += 1
                time.sleep(ts_diff / self._rtpmap[0])
            print(f'{str(NaluHeader(buf[16]))} {"audio" if interleaved.channel else "video"} ts_diff: {ts_diff} length: {self._frame_length[interleaved.channel]}')
            self._frame_length[interleaved.channel] = 0
        self._timestamp[interleaved.channel]=rtp_header.timestamp
        return buf

    def _open_dump(self):
        self._dump=open(self._filename, 'rb')
        sdp_size = struct.unpack(">I", self._dump.read(4))[0]
        self._dump.seek(sdp_size, io.SEEK_CUR)

    def _read_bytes(self, count):
        ret=self._dump.read(count)
        if len(ret)==count:
            return ret
        raise EOFError()

    def _update_timestamp(self,channel, timestamp):
        if not channel in self._timestamp:
            self._timestamp[channel] = timestamp
            self._timestamp_ext[channel] = 0
        if timestamp < self._timestamp[channel]:
            self._timestamp_ext[channel] += self._timestamp[channel] - timestamp
            self._timestamp[channel] = timestamp

    def _marshall_rtp_header(self, header, timestamp_ext):
        ts=header.timestamp
        header.timestamp+=timestamp_ext
        ret=(bytes(header))
        header.timestamp=ts
        return ret

    def _update_frame_length(self, interleaved, nalu_type):
        if len(self._frame_length) <= interleaved.channel:
            while len(self._frame_length) < interleaved.channel+1:
                self._frame_length.append(0)
        self._frame_length[interleaved.channel] += interleaved.size-12
        if interleaved.channel == 0 and nalu_type == 28: # FU-A 2 байта: FU indicator и FU header
           self._frame_length[interleaved.channel] -= 2

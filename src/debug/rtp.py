from enum import IntEnum


class InvalidRtpInterleaved(Exception):
    pass


class RtpInterleaved:
    def __init__(self, data):
        #for c in range(len(data)):
        #    print('{:x}'.format(data[c]), end=' ')
        self.preamble=int(data[0])
        if self.preamble != 0x24:
            raise InvalidRtpInterleaved('invalid preamble: '+str(self.preamble))
        self.channel=int(data[1])
        self.size=int.from_bytes(data[2:], "big")

    def __str__(self):
        return 'channel='+str(self.channel)+' size='+str(self.size)


class RtpHeader:
    def __init__(self, data):
        off=0
        b=data[off]
        self.version=(b>>6) & 2
        self.P=(b>>5) & 1
        self.X=(b>>4) & 1
        self.CC=(b & 4)
        off+=1
        b=data[off]
        self.M=(b>>7) & 1
        self.PT=(b & 0x7f)
        off+=1
        self.sn = int.from_bytes(data[off:off+2], "big")
        off+=2
        self.timestamp = int.from_bytes(data[off:off+4], "big")
        off+=4
        self.ssrc = int.from_bytes(data[off:off+4], "big")
        off+=4
        self.csrc=[]
        for c in range(self.CC):
            self.csrc.append(int.from_bytes(data[off:off + 4], "big"))
            off+=4
        if self.X == 1:
            self.ext_id = int.from_bytes(data[off:off + 2], "big")
            off+=2
            self.ext_length = int.from_bytes(data[off:off + 2], "big")
            off+=2+self.ext_length*4
        self.size=off

    def __str__(self):
        ret = 'ver:'+str(self.version)+' P:'+str(self.P)+' X:'+str(self.X)+' CC:'+str(self.CC)+' M:'+str(self.M)+' PT:'+str(self.PT)+' sn:'+str(self.sn)+\
              ' ts:'+str(self.timestamp)+' ssrc:'+str(self.ssrc)+' csrc:'+str(self.csrc)
        if self.X == 1:
            ret += ' ext{id:'+str(self.ext_id)+' len:'+str(self.ext_length)+'}'
        return ret


class NalunitType(IntEnum):
    RESERVED = 0,
    NON_IDR = 1,
    IDR = 5,
    SPS = 7,
    PPS = 8,
    STAP_A = 24,
    STAP_B = 25,
    MTAP16 = 26,
    MTAP24 = 27,
    FU_A = 28,
    FU_B = 29


class RtpNalunitHeader:
    def __init__(self, data):
        c=data[0]
        self.F = c>>7
        self.NRI=(c>>5) & 3
        self.Type=(c & 0x1f)

    def __str__(self):
        return 'F:'+str(self.F)+' nri:'+str(self.NRI)+' type:'+hex(self.Type)


class RtpFUHeader:
    def __init__(self, data):
        c=data[1]
        self.S=(c >>7)
        self.E = (c >> 6) & 1
        self.Type = (c & 0x1f)


class RtpNalunit:
    def __init__(self, data):
        self.data=''
        self.size=len(data)
        self.header=RtpNalunitHeader(data)
        if self.header.Type == NalunitType.FU_A:
            self.fu_header=RtpFUHeader(data)
        elif self.header.Type == NalunitType.SPS or self.header.Type == NalunitType.PPS:
            self.data=' ['
            for c in data:
                self.data+=hex(c)+' '
            self.data = self.data[:-1]+']'

    def __str__(self):
        return str(self.header) + self.data

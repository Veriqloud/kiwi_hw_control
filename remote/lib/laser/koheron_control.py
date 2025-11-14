from serial import Serial

def format_value(val, fmt):
    if fmt == 'f':
        return float(val)
    elif fmt == 'u':
        return int(val)
    elif fmt in ['x','s']:
        return val


def format_values(val, fmt):
    vals = val.split(" ")
    vals = [v for v in vals if v != '']
    if len(vals) == 0:
        return None
    if len(vals) == 1 or len(fmt) == 1:
        return format_value(vals[0], fmt[0])
    tup = ()
    for i, v in enumerate(vals):
        if i < len(fmt):
            tup += (format_value(v, fmt[i]),)
        else:
            tup += (v,)
    return tup


cmds = {
    'ilaser':   ('rw',  'f', ["CTL200", "CTL300E", "CTL20"]),
    'lason':    ('rw',  'u', ["CTL200", "CTL300E", "CTL20"]),
    'ilmon':    ('rw',  'f', ["CTL300E", "CTL20"]),
    'vlaser':   ('r',   'f', ["CTL200", "CTL300E", "CTL20"]),
    'ldelay':   ('rw',  'u', ["CTL200", "CTL300E", "CTL20"]),
    'ilmax':    ('rw',  'f', ["CTL200", "CTL300E", "CTL20"]),
    'lckon':    ('rw',  'u', ["CTL200", "CTL300E", "CTL20"]),
    'vslaser':  ('rw',  'f', ["CTL300E"]),
    'vslmon':   ('r',   'f', ["CTL300E"]),
    'vldrop':   ('rw',  'f', ["CTL300E"]),
    'vldauto':  ('rw',  'u', ["CTL300E"]),
    'bsel':     ('r',   'u', ["CTL300E"]),
    'lmodgain': ('rw',  'f', ["CTL200"]),
    'tecon':    ('rw',  'u', ["CTL200", "CTL300E", "CTL20", "TEC200"]),
    'tprot':    ('rw',  'u', ["CTL200", "CTL300E", "CTL20"]),
    'rtset':    ('rw',  'f', ["CTL200", "CTL300E", "CTL20", "TEC200"]),
    'rtact':    ('r',   'f', ["CTL200", "CTL300E", "CTL20", "TEC200"]),
    'rttol':    ('r',   'f', ["TEC200"]),
    'itec':     ('r',   'f', ["CTL200", "CTL300E", "CTL20", "TEC200"]),
    'vtec':     ('r',   'f', ["CTL200", "CTL300E", "CTL20", "TEC200"]),
    'vtmon':    ('r',   'f', ["TEC200"]),
    'rtec':     ('r',   'f', ["TEC200"]),
    'pgain':    ('rw',  'f', ["CTL200", "CTL300E"]),
    'dgain':    ('rw',  'f', ["CTL200", "CTL300E"]),
    'igain':    ('rw',  'f', ["CTL200", "CTL300E"]),
    'kprop':    ('rw',  'f', ["CTL20", "TEC200"]),
    'tint':     ('rw',  'f', ["CTL20", "TEC200"]),
    'tder':     ('rw',  'f', ["CTL20", "TEC200"]),
    'vstec':    ('rw',  'f', ["CTL300E"]),
    'tilim':    ('rw',  'f', ["CTL300E", "CTL20"]),
    'rtmin':    ('rw',  'f', ["CTL200", "CTL300E", "CTL20", "TEC200"]),
    'rtmax':    ('rw',  'f', ["CTL200", "CTL300E", "CTL20", "TEC200"]),
    'vtmin':    ('rw',  'f', ["CTL200", "CTL300E", "CTL20", "TEC200"]),
    'vtmax':    ('rw',  'f', ["CTL200", "CTL300E", "CTL20", "TEC200"]),
    'tjunc':    ('r',   'f', ["CTL300E", "CTL20", "TEC200"]),
    'tmodgain': ('rw',  'f', ["CTL200", "TEC200"]),
    'iphd':     ('r',   'f', ["CTL200", "CTL300E", "CTL20"]),
    'ain':      ('r',   'f', ["CTL300E", "TEC200"]),
    'ain1':     ('r',   'f', ["CTL200"]),
    'ain2':     ('r',   'f', ["CTL200"]),
    'vbus':     ('r',   'f', ["CTL300E", "TEC200"]),
    'ibus':     ('r',   'f', ["CTL300E", "TEC200"]),
    'almode':   ('rw',  'f', ["TEC200"]),
    'intmode':  ('rw',  'f', ["TEC200"]),
}

class Controller(object):
    def __init__(self, port='COM1'):
        self.ser = Serial(port, 115200, timeout=1)
        self.cmds = {
            'tboard': ('r','f'),
            'err': ('r','x'),
            'errclr': ('w', 'x'),
            'version': ('r','s'),
            'model': ('r','s'),
            'serial': ('r','s'),
            'userdata write': ('w','s'),
            'userdata': ('r','s'),
            'brate': ('rw', 'u'),
            'save': ('w','')
        }
        model = self.get('model')
        short_model = model.split("-")[0]
        for cmd in cmds:
            if short_model in cmds[cmd][2]:
                self.cmds[cmd] = cmds[cmd][0:2]


    def command(self, cmd):
        self.ser.write(cmd.encode() + b"\r\n")
        line = self.ser.readline().decode(errors='ignore')
        if cmd not in line:
            raise ValueError(f'Command "{cmd}" not returned in prompt. Received "{line}" instead.')
        return self.ser.readline().decode(errors='ignore').rstrip()




    def get(self, cmd, fmt=None):
        if fmt is None:
            x = self.cmds.get(cmd, None)
            if x is None:
                print(f"Command {cmd} does not exist")
                return None
            if 'r' not in x[0]:
                print(f"Command {cmd} is not readable")
                return None
            fmt = x[1]
        val = self.command(cmd)
        return format_values(val, fmt)

    def set(self, cmd, args="", fmt=None):
        if fmt is None:
            x = self.cmds.get(cmd, None)
            if x is None:
                print(f"Command {cmd} does not exist")
                return None
            if 'w' not in x[0]:
                print(f"Command {cmd} is not writable")
                return None
            fmt = x[1]
            if fmt == "":
                return self.command(cmd)
        fmt_ = " ".join(["%"+s for s in [*fmt]])
        val = self.command(f"{cmd} {fmt_}" % args)
        return format_values(val, fmt)

if __name__ == '__main__':

    port="/dev/ttyUSB0"
    ctl = Controller(port=port)

    print(f"MODEL    : {ctl.get('model')}")
    print(f"SERIAL   : {ctl.get('serial')}")
    print(f"VERSION  : {ctl.get('version')}")
    print(f"TBOARD   : {ctl.get('tboard')}")
    print(f"USER DATA: {ctl.get('userdata')}")
    print(f"ERR      : {ctl.get('err')}")

#    ctl.set("ilmax", 50.0)
    print(f"ILMAX    : {ctl.get('ilmax')}")

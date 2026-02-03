from enum import Enum
from lib.visuals import mylogger

# some enums for status files to avoid typos
# hwi stands for hardware init
# hws stands for hardware system, responsible for calibration


class Filenames(Enum):
    HWI= "/tmp/hwi.status"
    HWS= "/tmp/hws.status"

class HwiValues(Enum):
    DONE= "done"
    INITING= "initing"
    INACTIVE= "hwi not running"

class HwsValues(Enum):
    WAITING= "waiting for init done"
    GATES= "searching gates"
    SHIFT= "searching shift"
    DELAYS= "searching delays"
    DONE= "done"


# edit the status file for hwi; 
class HwiStatus():
    def __init__(self):
        self.filename = Filenames.HWI.value
        self.logger = mylogger()

    def done(self):
        with open(self.filename, 'w') as f:
            f.write(HwiValues.DONE.value)

    def initing(self):
        with open(self.filename, 'w') as f:
            f.write(HwiValues.INITING.value)
    
    def inactive(self):
        with open(self.filename, 'w') as f:
            f.write(HwiValues.INACTIVE.value)

    def get(self):
        with open(self.filename, 'r') as f:
            line = f.readline()
            try:
                return HwiValues(line)
            except:
                self.logger.error(f"wrong entry {line} in file {self.filename}")

                



def main():
    status = HwiStatus()
    status.done()
    print(status.get())
    


if __name__=="__main__":
    main()








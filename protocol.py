# http://developer.empatica.com/windows-streaming-server-commands.html

# General Message Structure
#
# Messages are ASCII strings terminated with a newline (in Windows '\r\n')
# character and encoded with UTF-8. Some commands have parameters,
# which are separated by spaces.
#
# Client requests are in the following format
#
# <COMMAND> <ARGUMENT_LIST>
# Example:
# device_subscribe gsr ON
#
# Messages from server containing responses to commands are in the following
# format:
#
# <COMMAND> <ARGUMENT_LIST>
# Example:
# R device_subscribe acc OK
#
# Errors:
# R device_connect_btle ERR could not connect device over BTLE
#
# Status
# R device_connect OK
#
# Messages from server containing data from device are in the following format
#
# <STREAM_TYPE> <TIMESTAMP> <DATA>
# Example:
# G 123345627891.123 3.129

from __future__ import annotations

from enum import Enum
from typing import Dict, NamedTuple, Optional


class NoSuchCommandError(Exception):
    pass


class MissingArgumentError(Exception):
    pass


class CmdID(Enum):
    DEV_DISCOVER = 0
    DEV_CONNECT_BTLE = 1
    DEV_DISCONNECT_BTLE = 2
    DEV_LIST = 3
    DEV_CONNECT = 4
    DEV_DISCONNECT = 5
    DEV_SUBSCRIBE = 6
    DEV_PAUSE = 7


_cmd_fmt: Dict[CmdID, str] = {
    CmdID.DEV_DISCOVER       : 'device_discover_list\r\n',
    CmdID.DEV_CONNECT_BTLE   : 'device_connect_btle {dev} {timeout}\r\n',
    CmdID.DEV_DISCONNECT_BTLE: 'device_disconnect_btle {dev}\r\n',
    CmdID.DEV_LIST           : 'device_list\r\n',
    CmdID.DEV_CONNECT        : 'device_connect {dev}\r\n',
    CmdID.DEV_DISCONNECT     : 'device_disconnect\r\n',
    CmdID.DEV_SUBSCRIBE      : 'device_subscribe {stream} {on}\r\n',
    CmdID.DEV_PAUSE          : 'pause {on}\r\n'
}


class DataStream(Enum):
    ACC = 0,
    GSR = 1,
    BVP = 2,
    TEMP = 3,
    IBI = 4,
    HR = 5,
    BAT = 6,
    TAG = 7


class CmdStatus(Enum):
    SUCCESS = 0,
    ERROR = 1


class StatusResponse(NamedTuple):
    command: CmdID
    status: CmdStatus
    msg: Optional[str]



def gen_command_string(cmd_id: CmdID, **kwargs) -> str:
    # preprocess args: booleans need to be turned into on/off:
    for k, v in kwargs.items():
        if type(v) == bool:
            kwargs[k] = 'ON' if v else 'OFF'

    cmd_str = _cmd_fmt.get(cmd_id, None)
    if cmd_str is not None:
        try:
            return cmd_str.format(**kwargs)
        except KeyError as e:
            raise MissingArgumentError(*e.args) from e
    else:
        raise NoSuchCommandError(cmd_id)

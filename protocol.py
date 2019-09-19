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
from typing import Dict, NamedTuple, Optional, Tuple, Type, Union, Set, List


class NoSuchCommandError(Exception):
    pass


class MissingArgumentError(Exception):
    pass


class ServerCommandGenerator:
    def __init__(self, cmd_id: CmdID, cmd, args: Dict[str, Type]):
        self._cmd_id = cmd_id
        self._cmd = cmd
        self._args = args

    def gen_cmd_string(self, **kwargs) -> str:
        assert len(kwargs) == len(self._args)
        for kwarg, val in kwargs.items():
            if kwarg not in self._args:
                raise RuntimeError(f'Unexpected argument \'{kwarg}\' for '
                                   f'command {self._cmd}.')
            if type(val) != self._args[kwarg]:
                raise RuntimeError(f'Wrong type for argument \'{kwarg}\' for '
                                   f'command {self._cmd}. '
                                   f'Expected {self._args[kwarg]}, but '
                                   f'got {type(val)}.')

            # turn booleans into on/off
            if type(val) == bool:
                kwargs[kwarg] = 'ON' if val else 'OFF'

        # generate the actual string
        return f'{self._cmd} ' + \
               ' '.join([f'{kwargs[k]}' for k, _ in self._args.items()]) + \
               '\r\n'


class CmdID(Enum):
    DEV_DISCOVER = 0
    DEV_CONNECT_BTLE = 1
    DEV_DISCONNECT_BTLE = 2
    DEV_LIST = 3
    DEV_CONNECT = 4
    DEV_DISCONNECT = 5
    DEV_SUBSCRIBE = 6
    DEV_PAUSE = 7


# set up mappings for the commands
_id_to_cmd = {}
_str_to_cmd = {}
_cmd_set: List[Tuple[CmdID, str, Dict[str, Type]]] = [
    (CmdID.DEV_DISCOVER, 'device_discover_list', {}),
    (CmdID.DEV_CONNECT_BTLE, 'device_connect_btle',
     {'dev': str, 'timeout': int}),
    (CmdID.DEV_DISCONNECT_BTLE, 'device_disconnect_btle', {'dev': str}),
    (CmdID.DEV_LIST, 'device_list', {}),
    (CmdID.DEV_CONNECT, 'device_connect', {'dev': str, 'timeout': int}),
    (CmdID.DEV_DISCONNECT, 'device_disconnect', {}),
    (CmdID.DEV_SUBSCRIBE, 'device_subscribe', {'stream': str, 'on': bool}),
    (CmdID.DEV_PAUSE, 'pause', {'on': bool})
]

for cmd_id, cmd, args in _cmd_set:
    cmd_gen = ServerCommandGenerator(cmd_id, cmd, args)
    _id_to_cmd[cmd_id] = cmd_gen
    _str_to_cmd[cmd] = cmd_gen


class DataStream(Enum):
    ACC = 0
    GSR = 1
    BVP = 2
    TEMP = 3
    IBI = 4
    HR = 5
    BAT = 6
    TAG = 7


class ServerMessageType(Enum):
    STATUS_RESP = 0
    STREAM_DATA = 1


class CmdStatus(Enum):
    SUCCESS = 0
    ERROR = 1


class StatusResponse(NamedTuple):
    command: CmdID
    status: CmdStatus
    msg: Optional[str]


class StreamingDataSample(NamedTuple):
    stream: DataStream
    timestamp: float
    data: Tuple


def gen_command_string(cmd_id: CmdID, **kwargs) -> str:
    return _id_to_cmd[cmd_id].gen_cmd_string(**kwargs)

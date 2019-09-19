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
from typing import Dict, List, NamedTuple, Tuple, Type, Union


class NoSuchCommandError(Exception):
    pass


class MissingArgumentError(Exception):
    pass


class CommandDefinition:
    def __init__(self, cmd_id: CmdID,
                 cmd: str,
                 args: Dict[str, Type],
                 is_query: bool = False):
        self._cmd_id = cmd_id
        self._cmd = cmd
        self._args = args
        self._is_query = is_query

    @property
    def is_query(self):
        return self._is_query

    @property
    def cmd_id(self) -> CmdID:
        return self._cmd_id

    @property
    def cmd_str(self) -> str:
        return self._cmd

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

_cmd_defs = [
    CommandDefinition(CmdID.DEV_DISCOVER,
                      'device_discover_list', {},
                      is_query=True),
    CommandDefinition(CmdID.DEV_CONNECT_BTLE,
                      'device_connect_btle', {'dev': str, 'timeout': int},
                      is_query=False),
    CommandDefinition(CmdID.DEV_DISCONNECT_BTLE,
                      'device_disconnect_btle', {'dev': str},
                      is_query=False),
    CommandDefinition(CmdID.DEV_LIST,
                      'device_list', {},
                      is_query=True),
    CommandDefinition(CmdID.DEV_CONNECT,
                      'device_connect', {'dev': str},
                      is_query=False),
    CommandDefinition(CmdID.DEV_DISCONNECT,
                      'device_disconnect', {},
                      is_query=False),
    CommandDefinition(CmdID.DEV_SUBSCRIBE,
                      'device_subscribe', {'stream': str, 'on': bool},
                      is_query=False),
    CommandDefinition(CmdID.DEV_PAUSE,
                      'pause', {'on': bool},
                      is_query=False)
]

for cmd_def in _cmd_defs:
    _id_to_cmd[cmd_def.cmd_id] = cmd_def
    _str_to_cmd[cmd_def.cmd_str] = cmd_def


class DataStream(Enum):
    ACC = 0
    BVP = 1
    GSR = 2
    TEMP = 3
    IBI = 4
    HR = 5
    BAT = 6
    TAG = 7


_str_to_stream_id = {
    'E4_Acc'    : DataStream.ACC,
    'E4_Bvp'    : DataStream.BVP,
    'E4_Gsr'    : DataStream.GSR,
    'E4_Temp'   : DataStream.TEMP,
    'E4_Ibi'    : DataStream.IBI,
    'E4_Hr'     : DataStream.HR,
    'E4_Battery': DataStream.BAT,
    'E4_Tag'    : DataStream.TAG
}


class ServerMessageType(Enum):
    STATUS_RESP = 0
    STREAM_DATA = 1
    QUERY_REPLY = 3


class CmdStatus(Enum):
    SUCCESS = 0
    ERROR = 1


class StatusResponse(NamedTuple):
    command: CmdID
    status: CmdStatus


class StreamingDataSample(NamedTuple):
    stream: DataStream
    timestamp: float
    data: Tuple[float]


class QueryReply(NamedTuple):
    command: CmdID
    data: str


def gen_command_string(cmd_id: CmdID, **kwargs) -> str:
    return _id_to_cmd[cmd_id].gen_cmd_string(**kwargs)


def parse_incoming_message(message: str) \
        -> Tuple[ServerMessageType, Union[StatusResponse,
                                          StreamingDataSample,
                                          QueryReply]]:
    # split message on whitespace
    msg_t, _, message = message.partition(' ')

    # first element of message is type of message
    if msg_t == 'R':
        # response, either a query reply or status
        cmd_str, _, message = message.partition(' ')
        cmd = _str_to_cmd[cmd_str]

        if cmd.is_query:
            # response is a response to query, so it doesn't include OK/ERR
            data = message
            return ServerMessageType.QUERY_REPLY, \
                   QueryReply(cmd.cmd_id, data)
        else:
            # response is a status response
            # special handling for subscription responses as those include
            # the stream before the status message...
            if cmd.cmd_id == CmdID.DEV_SUBSCRIBE:
                # pop the stream from the string
                _, _, message = message.partition(' ')
            elif cmd.cmd_id == CmdID.DEV_PAUSE:
                # also special handling for Pause since it echoes back ON or
                # OFF instead of OK/ERR ... Who designed this PoS API??
                return ServerMessageType.STATUS_RESP, \
                       StatusResponse(cmd.cmd_id, CmdStatus.SUCCESS)

            status_str, _, message = message.partition(' ')
            status = CmdStatus.SUCCESS \
                if status_str == 'OK' else CmdStatus.ERROR

            return ServerMessageType.STATUS_RESP, \
                   StatusResponse(cmd.cmd_id, status)

    elif msg_t.startswith('E4_'):
        # subscription data
        sub_id = _str_to_stream_id[msg_t]
        payload = message.split(' ')
        timestamp = float(payload[0])
        data = tuple(float(d) for d in payload[1:])

        return ServerMessageType.STREAM_DATA, \
               StreamingDataSample(sub_id, timestamp, data)

    else:
        # TODO?
        raise RuntimeError()

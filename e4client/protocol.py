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
from typing import Dict, NamedTuple, Optional, Tuple, Type, Union


class CmdID(Enum):
    DEV_DISCOVER = 0
    DEV_CONNECT_BTLE = 1
    DEV_DISCONNECT_BTLE = 2
    DEV_LIST = 3
    DEV_CONNECT = 4
    DEV_DISCONNECT = 5
    DEV_SUBSCRIBE = 6
    DEV_PAUSE = 7


class DataStreamID(Enum):
    ACC = 0
    BVP = 1
    GSR = 2
    TEMP = 3
    IBI = 4
    HR = 5
    BAT = 6
    TAG = 7


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


class DataStream(NamedTuple):
    stream_id: DataStreamID
    cmd_abbrv: str  # abbreviation used in commands (acc, bat, and so on)
    resp_prefix: str  # prefix used by the server to identify streams


# actually define commands:
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

# set up mappings for the commands
_id_to_cmd = {}
_str_to_cmd = {}
for cmd_def in _cmd_defs:
    _id_to_cmd[cmd_def.cmd_id] = cmd_def
    _str_to_cmd[cmd_def.cmd_str] = cmd_def

# define streams:
_stream_defs = [
    DataStream(DataStreamID.ACC, 'acc', 'E4_Acc'),
    DataStream(DataStreamID.BVP, 'bvp', 'E4_Bvp'),
    DataStream(DataStreamID.GSR, 'gsr', 'E4_Acc'),
    DataStream(DataStreamID.TEMP, 'tmp', 'E4_Temp'),
    # Interbeat interval and heartrate share the same command abbreviation,
    # i.e., can't subscribe to one without the other
    DataStream(DataStreamID.IBI, 'ibi', 'E4_Ibi'),
    DataStream(DataStreamID.HR, 'ibi', 'E4_Hr'),
    # --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- ---
    DataStream(DataStreamID.BAT, 'bat', 'E4_Battery'),
    DataStream(DataStreamID.TAG, 'tag', 'E4_Tag')
]

# easy lookup mappings for streams
_prefix_to_stream = {}
_id_to_stream = {}
_abbrv_to_stream = {}
for stream in _stream_defs:
    _prefix_to_stream[stream.resp_prefix] = stream
    _id_to_stream[stream.stream_id] = stream
    _abbrv_to_stream[stream.cmd_abbrv] = stream


# definitions for the replies:
class ServerMessageType(Enum):
    STATUS_RESP = 0
    QUERY_REPLY = 1
    STREAM_DATA = 2


class CmdStatus(Enum):
    SUCCESS = 0
    ERROR = 1


class StreamingDataSample(NamedTuple):
    stream: DataStreamID
    timestamp: float
    data: Tuple[float]


class ServerReply(NamedTuple):
    command: CmdID
    status: CmdStatus
    data: Optional[str]


def gen_command_string(cmd_id: CmdID, **kwargs) -> str:
    return _id_to_cmd[cmd_id].gen_cmd_string(**kwargs)


def parse_incoming_message(message: str) \
        -> Tuple[ServerMessageType, Union[ServerReply, StreamingDataSample]]:
    # split message on whitespace
    msg_t, _, message = message.partition(' ')

    # first element of message is type of message
    if msg_t == 'R':
        # response, either a query reply or status
        cmd_str, _, message = message.partition(' ')
        cmd = _str_to_cmd[cmd_str]

        if cmd.is_query:
            # response is a response to query, so it doesn't include OK/ERR
            return ServerMessageType.QUERY_REPLY, \
                   ServerReply(command=cmd.cmd_id,
                               status=CmdStatus.SUCCESS,
                               data=message)
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
                       ServerReply(command=cmd.cmd_id,
                                   status=CmdStatus.SUCCESS,
                                   data=None)

            status_str, _, message = message.partition(' ')
            status = CmdStatus.SUCCESS \
                if status_str == 'OK' else CmdStatus.ERROR

            return ServerMessageType.STATUS_RESP, \
                   ServerReply(command=cmd.cmd_id,
                               status=status,
                               data=None)

    elif msg_t.startswith('E4_'):
        # subscription data
        sub_id = _prefix_to_stream[msg_t].stream_id
        payload = message.split(' ')
        timestamp = float(payload[0])
        data = tuple(float(d) for d in payload[1:])

        return ServerMessageType.STREAM_DATA, \
               StreamingDataSample(sub_id, timestamp, data)

    else:
        # TODO?
        raise RuntimeError()

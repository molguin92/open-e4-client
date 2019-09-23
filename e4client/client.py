from __future__ import annotations

import logging
import queue
import socket
import sys
import threading
import time
from contextlib import AbstractContextManager
from typing import Tuple, Union

from e4client.protocol import E4DataStreamID, E4Device, _CmdID, _CmdStatus, \
    _ServerMessageType, _ServerReply, _gen_command_string, _parse_device_list, \
    _parse_incoming_message

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)


class DeviceNotFoundError(Exception):
    pass


class ServerRequestError(Exception):
    pass


class E4StreamingClient(AbstractContextManager):
    _delim = b'\n'

    def __init__(self, server_ip: str,
                 server_port: int,
                 max_conn_attempts: int = 20):
        super().__init__()

        self._logger = logging.getLogger(self.__class__.__name__)

        # set up buffers for responses and subscriptions
        self._resp_q = queue.Queue(maxsize=1)
        self.sub_qs = {
            stream_id: queue.Queue() for stream_id in E4DataStreamID
        }

        self._logger.info(f'Connecting to {server_ip}:{server_port}...')

        # immediately try to connect
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        attempts = 0
        while True:
            try:
                self._logger.info(f'Connection attempt {attempts + 1}.')
                self._socket.connect((server_ip, server_port))
                self._logger.info('Connection success.')
                break
            except OSError:
                self._logger.info('Connection failed.')
                if attempts < max_conn_attempts:
                    self._logger.info('Reattempting connection...')
                    attempts += 1
                    time.sleep(0.01)
                    continue
                else:
                    self._logger.error('Too many connection attempts!')
                    self._socket.close()
                    raise

        self._connected = True

        self._recv_thread = threading.Thread(target=self._recv_loop,
                                             daemon=True)
        self._recv_thread.start()

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _recv_loop(self):
        self._logger.debug('Starting receiving thread...')

        data = b''
        while True:
            try:
                # small block size since messages are short
                data += self._socket.recv(64)

                # split up responses and process them
                while True:
                    raw_msg, lim, rest = \
                        data.partition(E4StreamingClient._delim)
                    if len(lim) == len(rest) == 0:
                        # no remaining complete messages, read again from socket
                        break

                    data = rest  # save the remaining data for further
                    # processing

                    # parse the first extracted response
                    message = raw_msg.decode('utf-8')
                    self._logger.debug(f'Raw incoming message: {message}')

                    msg_type, parsed_msg = _parse_incoming_message(message)
                    self._logger.debug(f'Parsed message: {parsed_msg}')

                    if msg_type == _ServerMessageType.STREAM_DATA:
                        self.sub_qs[parsed_msg.stream].put(
                            (parsed_msg.timestamp, *parsed_msg.data))
                    else:
                        while True:
                            try:
                                self._resp_q.get_nowait()
                            except queue.Empty:
                                self._resp_q.put_nowait(parsed_msg)
                                break

            except socket.error as e:
                self._logger.debug(e)
                self._logger.debug('Shutting down receiving thread...')
                return

    def _send(self, cmd: str):
        self._logger.debug(f'Sending \'{cmd.encode("utf-8")}\' to server.')
        self._socket.sendall(cmd.encode('utf-8'))

    def _send_command(self, cmd_id: _CmdID, **kwargs) \
            -> _ServerReply:
        self._send(_gen_command_string(cmd_id, **kwargs))
        resp = self._resp_q.get(block=True)

        assert resp.command == cmd_id
        return resp

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    # public convenience methods follow:

    def list_connected_devices(self) -> Tuple[E4Device]:
        resp = self._send_command(_CmdID.DEV_LIST)
        return _parse_device_list(resp.data)

    def connect_to_device(self,
                          device: Union[E4Device, str]) -> E4DeviceConnection:

        device = device.uid if isinstance(device, E4Device) else device
        resp = self._send_command(_CmdID.DEV_CONNECT, dev=device)

        if resp.status == _CmdStatus.SUCCESS:
            return E4DeviceConnection(client=self, dev_uid=device)
        else:
            raise DeviceNotFoundError(device)

    def disconnect_from_device(self) -> None:
        resp = self._send_command(_CmdID.DEV_DISCONNECT)
        if resp.status != _CmdStatus.SUCCESS:
            raise ServerRequestError(resp.data)

    def subscribe_to_stream(self, stream: E4DataStreamID) -> None:
        resp = self._send_command(_CmdID.DEV_SUBSCRIBE,
                                  stream=stream, on=True)

        if resp.status != _CmdStatus.SUCCESS:
            raise ServerRequestError(resp.data)

    def unsubscribe_from_stream(self, stream: E4DataStreamID) -> None:
        resp = self._send_command(_CmdID.DEV_SUBSCRIBE,
                                  stream=stream, on=False)

        if resp.status != _CmdStatus.SUCCESS:
            raise ServerRequestError(resp.data)

    def close(self):
        if self._connected:
            self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()
            self._recv_thread.join()
            self._connected = False


class E4DeviceConnection(AbstractContextManager):
    def __init__(self,
                 client: E4StreamingClient,
                 dev_uid: str):
        self._client = client
        self._dev = dev_uid
        self._subscriptions = set()

        self._logger = logging.getLogger(self.__class__.__name__)

    def __exit__(self, exc_type, exc_value, traceback):
        self.disconnect()

    @property
    def uid(self) -> str:
        return self._dev

    def subscribe_to_stream(self, stream: E4DataStreamID) -> queue.Queue:
        self._logger.debug(f'Subscribing to {stream}.')
        self._client.subscribe_to_stream(stream)
        self._subscriptions.add(stream)
        return self._client.sub_qs[stream]

    def unsubscribe_from_stream(self, stream: E4DataStreamID) -> None:
        self._logger.debug(f'Unsubscribing from {stream}.')
        self._client.unsubscribe_from_stream(stream)
        self._subscriptions.remove(stream)

    def disconnect(self):
        self._logger.debug(f'Disconnecting device {self._dev}.')
        for sub in self._subscriptions:
            self._client.unsubscribe_from_stream(sub)

        self._client.disconnect_from_device()

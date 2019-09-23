from __future__ import annotations

import logging
import queue
import socket
import sys
import threading
import time
from contextlib import AbstractContextManager
from typing import Tuple, Union

from e4client.protocol import DataStreamID, E4Device, _CmdID, _CmdStatus, \
    _ServerMessageType, _ServerReply, _gen_command_string, _parse_device_list, \
    _parse_incoming_message

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)


class DeviceNotFoundError(Exception):
    pass


class ServerRequestError(Exception):
    pass


class E4StreamingClient(threading.Thread):
    _delim = b'\n'

    def __init__(self, server_ip: str,
                 server_port: int,
                 max_conn_attempts: int = 20):
        super().__init__()

        self.logger = logging.getLogger(self.__class__.__name__)

        # set up buffers for responses and subscriptions
        self.resp_q = queue.Queue(maxsize=1)
        self.sub_qs = {
            stream_id: queue.Queue() for stream_id in DataStreamID
        }

        self.logger.info(f'Connecting to {server_ip}:{server_port}...')

        # immediately try to connect
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        attempts = 0
        while True:
            try:
                self.logger.info(f'Connection attempt {attempts + 1}.')
                self.socket.connect((server_ip, server_port))
                self.logger.info('Connection success.')
                break
            except OSError:
                self.logger.info('Connection failed.')
                if attempts < max_conn_attempts:
                    self.logger.info('Reattempting connection...')
                    attempts += 1
                    time.sleep(0.01)
                    continue
                else:
                    self.logger.error('Too many connection attempts!')
                    self.socket.close()
                    raise

        self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self.recv_thread.start()

    def _recv_loop(self):
        self.logger.debug('Starting receiving thread...')

        data = b''
        while True:
            # small block size since messages are short
            data += self.socket.recv(64)

            # split up responses and process them
            while True:
                raw_msg, lim, rest = data.partition(E4StreamingClient._delim)
                if len(lim) == len(rest) == 0:
                    # no remaining complete messages, read again from socket
                    break

                data = rest  # save the remaining data for further processing

                # parse the first extracted response
                message = raw_msg.decode('utf-8')
                self.logger.debug(f'Raw incoming message: {message}')

                msg_type, parsed_msg = _parse_incoming_message(message)
                self.logger.debug(f'Parsed message: {parsed_msg}')

                if msg_type == _ServerMessageType.STREAM_DATA:
                    self.sub_qs[parsed_msg.stream].put(parsed_msg.data)
                else:
                    while True:
                        try:
                            self.resp_q.get_nowait()
                        except queue.Empty:
                            self.resp_q.put_nowait(parsed_msg)
                            break

    def _send(self, cmd: str):
        self.logger.debug(f'Sending \'{cmd.encode("utf-8")}\' to server.')
        self.socket.sendall(cmd.encode('utf-8'))

    def _send_command(self, cmd_id: _CmdID, **kwargs) \
            -> _ServerReply:
        self._send(_gen_command_string(cmd_id, **kwargs))
        resp = self.resp_q.get(block=True)

        assert resp.command == cmd_id
        return resp

    # public convenience methods follow:

    def list_connected_devices(self) -> Tuple[E4Device]:
        resp = self._send_command(_CmdID.DEV_LIST)
        return _parse_device_list(resp.data)

    def connect_to_device(self,
                          device: Union[E4Device, str]) -> DeviceConnection:

        device = device.uid if isinstance(device, E4Device) else device
        resp = self._send_command(_CmdID.DEV_CONNECT, dev=device)

        if resp.status == _CmdStatus.SUCCESS:
            return DeviceConnection(client=self, dev_uid=device)
        else:
            raise DeviceNotFoundError(device)

    def disconnect_from_device(self) -> None:
        resp = self._send_command(_CmdID.DEV_DISCONNECT)
        if resp.status != _CmdStatus.SUCCESS:
            raise ServerRequestError(resp.data)

    def subscribe_to_stream(self, stream: DataStreamID) -> None:
        resp = self._send_command(_CmdID.DEV_SUBSCRIBE,
                                  stream=stream, on=True)

        if resp.status != _CmdStatus.SUCCESS:
            raise ServerRequestError(resp.data)

    def unsubscribe_from_stream(self, stream: DataStreamID) -> None:
        resp = self._send_command(_CmdID.DEV_SUBSCRIBE,
                                  stream=stream, on=False)

        if resp.status != _CmdStatus.SUCCESS:
            raise ServerRequestError(resp.data)


class DeviceConnection(AbstractContextManager):
    def __init__(self,
                 client: E4StreamingClient,
                 dev_uid: str):
        self._client = client
        self._dev = dev_uid

    def __exit__(self, exc_type, exc_value, traceback):
        self.client.disconnect_from_device()

    @property
    def client(self):
        return self._client

    @property
    def uid(self):
        return self._dev

    def subscribe_to_stream(self):
        pass

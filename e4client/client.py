import logging
import queue
import socket
import sys
import threading
import time

from e4client.protocol import CmdID, ServerMessageType, ServerReply, \
    gen_command_string, \
    parse_incoming_message

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)


class BaseE4Client(threading.Thread):
    __delim = b'\n'

    def __init__(self, server_ip: str,
                 server_port: int,
                 max_conn_attempts: int = 20):
        super().__init__()

        self.logger = logging.getLogger(self.__class__.__name__)

        # set up buffers for responses and subscriptions
        self.resp_q = queue.Queue(maxsize=1)
        self.sub_q = queue.Queue()

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

        self.recv_thread = threading.Thread(target=self.__recv, daemon=True)
        self.recv_thread.start()

    def __recv(self):
        self.logger.debug('Starting receiving thread...')

        data = b''
        while True:
            # small block size since messages are short
            data += self.socket.recv(64)

            # split up responses and process them
            while True:
                raw_msg, lim, rest = data.partition(BaseE4Client.__delim)
                if len(lim) == len(rest) == 0:
                    # no remaining complete messages, read again from socket
                    break

                data = rest  # save the remaining data for further processing

                # parse the first extracted response
                message = raw_msg.decode('utf-8')
                self.logger.debug(f'Raw incoming message: {message}')

                msg_type, parsed_msg = parse_incoming_message(message)
                self.logger.debug(f'Parsed message: {parsed_msg}')

                if msg_type == ServerMessageType.STREAM_DATA:
                    self.sub_q.put(parsed_msg)
                else:
                    while True:
                        try:
                            self.resp_q.get_nowait()
                        except queue.Empty:
                            self.resp_q.put_nowait(parsed_msg)
                            break

    def __send(self, cmd: str):
        self.logger.debug(f'Sending \'{cmd.encode("utf-8")}\' to server.')
        self.socket.sendall(cmd.encode('utf-8'))

    def send_command(self, cmd_id: CmdID, **kwargs) \
            -> ServerReply:
        self.__send(gen_command_string(cmd_id, **kwargs))
        resp = self.resp_q.get(block=True)

        assert resp.command == cmd_id
        return resp

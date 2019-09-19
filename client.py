import logging
import queue
import socket
import sys
import threading
import time

from protocol import CmdID, gen_command_string

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)


class E4StreamingClient(threading.Thread):
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

    def __parse_incoming(self, msg):
        pass

    def __recv(self):
        self.logger.debug('Starting receiving thread...')

        data = b''
        while True:
            data += self.socket.recv(1024)

            # check if we received a full response
            raw_msg, lim, rest = data.partition(E4StreamingClient.__delim)
            if len(lim) == len(rest) == 0:
                data = raw_msg
                continue

            # save the incomplete rest of the incoming data (TCP streams can
            # be split haphazardly...)
            data = rest

            # parse the response
            message = raw_msg.decode('utf-8')
            self.logger.debug(message)

            response = self.__parse_incoming(message)

    def __send(self, cmd: str):
        self.socket.sendall(cmd.encode('utf-8'))

    def send_command(self, cmd_id: CmdID, **kwargs):
        self.__send(gen_command_string(cmd_id, **kwargs))

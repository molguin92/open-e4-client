import logging
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
            data += self.socket.recv(1024)

            # check if we received a full response
            response, lim, rest = data.partition(E4StreamingClient.__delim)
            if len(lim) == len(rest) == 0:
                data = response
            else:
                data = rest
                result = response.decode('utf-8')
                self.logger.debug(result)

    def __send(self, cmd: str):
        self.socket.sendall(cmd.encode('utf-8'))

    def list_devices(self):
        self.__send(gen_command_string(CmdID.DEV_LIST))

    def connect_device(self, device_id: str):
        pass

    def disconnect_current_device(self):
        pass

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


if __name__ == '__main__':
    client = E4StreamingClient('192.168.56.101', 5000)
    while True:
        client.list_devices()
        time.sleep(5)

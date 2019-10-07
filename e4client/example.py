import time

from e4client import *


def print_sub(stream_id, timestamp, *sample) -> None:
    print(stream_id, timestamp, *sample)


if __name__ == '__main__':
    with E4StreamingClient('192.168.56.101', 28000) as client:
        devs = client.list_connected_devices()
        with client.connect_to_device(devs[0]) as conn:
            conn.subscribe_to_stream(E4DataStreamID.ACC, print_sub)
            conn.subscribe_to_stream(E4DataStreamID.TEMP, print_sub)

            time.sleep(30.0)

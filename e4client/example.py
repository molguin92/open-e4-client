import queue
import threading
import time

from e4client import *


def print_sub(sub_q: queue.Queue) -> None:
    while True:
        print(sub_q.get(block=True))


if __name__ == '__main__':
    with E4StreamingClient('192.168.56.101', 28000) as client:
        devs = client.list_connected_devices()
        with client.connect_to_device(devs[0]) as conn:
            acc_q = conn.subscribe_to_stream(E4DataStreamID.ACC)
            tmp_q = conn.subscribe_to_stream(E4DataStreamID.TEMP)

            acc_t = threading.Thread(target=print_sub, args=(acc_q,),
                                     daemon=True)
            tmp_t = threading.Thread(target=print_sub, args=(tmp_q,),
                                     daemon=True)

            acc_t.start()
            tmp_t.start()

            time.sleep(30.0)

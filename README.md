# open-e4-client

Pure Python 3.7+ client for the [Empatica E4](https://www.empatica.com/research/e4/) realtime [streaming server.](http://developer.empatica.com/windows-streaming-server.html) 

## Installation
### Dependencies: 

None, runs on pure Python 3.7+.

### Setting up through Pip:

```
\\ coming up
```

## Basic Usage

This library provides a simple class `E4StreamingClient` to interact with the Empatica E4 streaming server. This class is intended to be used as a context manager for easy cleanup of the underlying socket objects:

```python
from e4client import E4StreamingClient

with E4StreamingClient('0.0.0.0', 28000) as client:
    dev_list = client.list_connected_devices()
# dev_list = (E4Device(uid='FFFFFF', name='Empatica_E4', allowed=True), ...)
```

Connecting to a specific E4 for streaming also creates a context manager which cleans up subscriptions and disconnects from the device on context exit:

```python
from e4client import E4StreamingClient, E4DataStreamID

with E4StreamingClient('0.0.0.0', 28000) as client:
    dev_list = client.list_connected_devices()

    with client.connect_to_device(dev_list[0]) as conn:
        # connected to the first device here
        tag_q = conn.subscribe_to_stream(E4DataStreamID.TAG)
        
        # block and wait for a tag press:
        print(tag_q.get(block=True))

    # device disconnected here, no need to disconnect or unsubscribe,
    # all is handled by the context manager. 
```

The example above connects to the server, then connects to the first available E4, subscribes to the TAG stream and waits for a single press before disconnecting smoothly.
This example also exposes the handling of subscriptions: each subscription has an associated thread-safe queue for easy extraction of data. 
Samples are parsed asynchronously by the receiving thread and deposited in the corresponding queue as tuples in the following format:
```python
(timestamp, datum_0, datum_1, ..., datum_n)
```

The following simple example shows the complete basic usage of the API to connect to the server, subscribe to a couple of streams and print them asynchronously for 30 seconds before silently and smoothly shutting down:

```python
import queue
import threading
import time

from e4client import *


def print_sub(sub_q: queue.Queue) -> None:
    while True:
        print(sub_q.get(block=True))


if __name__ == '__main__':
    with E4StreamingClient('0.0.0.0', 28000) as client:
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

```



## License:

This software is licensed under an Apache v2 License.
For details, see file [LICENSE](./LICENSE).


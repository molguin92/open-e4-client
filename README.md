[![PyPI version](https://badge.fury.io/py/open-e4-client.svg)](https://badge.fury.io/py/open-e4-client)

# open-e4-client

Pure Python 3.7+ client for the [Empatica E4](https://www.empatica.com/research/e4/) realtime [streaming server](http://developer.empatica.com/windows-streaming-server.html).

## Installation
### Dependencies: 

None, runs on pure Python 3.7+.

### Setting up through Pip:

The library can easily be installed from PyPi by running:

```bash
pip install open-e4-client
```

Alternatively, it can be installed from the github repo itself:
```bash
pip install git+https://github.com/molguin92/open-e4-client.git
```

## Basic Usage

Make sure the Empatica E4 realtime streaming server is launched with administrator priviledges (relative to [this issue](https://github.com/Munroe-Meyer-Institute-VR-Laboratory/pyEmpatica/issues/1))

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
import threading

with E4StreamingClient('0.0.0.0', 28000) as client:
    dev_list = client.list_connected_devices()

    with client.connect_to_device(dev_list[0]) as conn:
        # connected to the first device here
        
        event = threading.Event()
    
        def _callback(stream: E4DataStreamID, timestamp: float, *data):
            print(stream, timestamp, *data)
            event.set()


        conn.subscribe_to_stream(E4DataStreamID.TAG, _callback)
        
        # block and wait for a tag press:
        event.wait()

    # device disconnected here, no need to disconnect or unsubscribe,
    # all is handled by the context manager. 
```

The example above connects to the server, then connects to the first available E4, subscribes to the TAG stream and waits for a single press before disconnecting smoothly.
This example also exposes the handling of subscriptions: each subscription is  associated with a callback which the library executes on a separate thread, once per sample. The callbacks passed to `subscribe_to_stream()` will receive arguments in the form:
```python
(stream_id, timestamp, datum_1, datum_2, ..., datum_n)
```

The following simple example shows the complete basic usage of the API to connect to the server, subscribe to a couple of streams and print them asynchronously for 30 seconds before silently and smoothly shutting down:

```python
import time

from e4client import *


def print_sub(stream_id, timestamp, *sample) -> None:
    print(stream_id.name, timestamp, *sample)


if __name__ == '__main__':
    with E4StreamingClient('192.168.56.101', 28000) as client:
        devs = client.list_connected_devices()
        with client.connect_to_device(devs[0]) as conn:
            conn.subscribe_to_stream(E4DataStreamID.ACC, print_sub)
            conn.subscribe_to_stream(E4DataStreamID.TEMP, print_sub)

            time.sleep(30.0)
```

## License:

This software is licensed under an Apache v2 License.
For details, see file [LICENSE](./LICENSE).


import time
from typing import Tuple

import matplotlib.pyplot as plt
import numpy as np
import scipy
import scipy.stats

from e4client import *

plt.style.use('bmh')


# TODO: update to use callbacks!!


# Nominal sampling rates for the E4:
#
#    Blood volume pulse,@64Hz
#    Inter beat interval: time, IBI(time) pair
#    Electrodermal activity @4 Hz
#    XYZ raw acceleration @32Hz
#    Skin temperature @4Hz*
#


def benchmark_sensor(conn: E4DeviceConnection,
                     stream: E4DataStreamID,
                     nom_freq: int,
                     bench_time_s: float,
                     repetitions: int) -> Tuple[float, np.ndarray]:
    print(f'..............Benchmarking {stream}..............')
    print(f'Duration of each benchmark: ~{bench_time_s} seconds.')
    freq_samples = []
    sample_intervals = []

    for i in range(repetitions):
        print(f'\rRunning repetition {i + 1}/{repetitions}.', end='',
              flush=True)
        res_q = conn.subscribe_to_stream(stream)
        # wait for the first packet before starting
        t_prev, *rest = res_q.get(block=True)

        t_i = time.time()
        time.sleep(bench_time_s)
        conn.unsubscribe_from_stream(stream)
        delta_t = time.time() - t_i

        # count the received packets
        total_cnt = 0
        while not res_q.empty():
            t_stamp, *rest = res_q.get()
            sample_intervals.append(t_stamp - t_prev)
            t_prev = t_stamp
            total_cnt += 1

        freq_samples.append(total_cnt / delta_t)

    freq_samples = np.array(freq_samples)
    _, freq_minmax, freq_mean, freq_var, _, _ = scipy.stats.describe(
        freq_samples)

    sample_intervals = np.array(sample_intervals)
    _, inter_minmax, inter_mean, inter_var, _, _ = scipy.stats.describe(
        sample_intervals)

    print(f'''
Nominal sampling frequency: {nom_freq} Hz
Results over {repetitions} benchmarks:
Mean: {freq_mean} Hz
Min: {freq_minmax[0]} Hz
Max: {freq_minmax[1]} Hz
Variance: {freq_var} Hz

Expected interval between reported timestamps: {1.0 / nom_freq} s.
Actual reported intervals:
Mean: {inter_mean} s
Min: {inter_minmax[0]} s
Max: {inter_minmax[1]} s
Variance: {inter_var} s
    ''')

    return nom_freq, freq_samples


if __name__ == '__main__':
    bench_cnt = 20
    bench_time = 10
    # connect to client:
    with E4StreamingClient('192.168.56.101', 28000) as client:
        device = client.list_connected_devices()[0]
        print(f'Connecting to {device}...')
        results = {}
        with client.connect_to_device(device) as conn:
            for stream in E4DataStreamID:
                if stream in [E4DataStreamID.TEMP, E4DataStreamID.GSR]:
                    results[stream] = benchmark_sensor(conn, stream, 4,
                                                       bench_time, bench_cnt)
                elif stream == E4DataStreamID.BVP:
                    results[stream] = benchmark_sensor(conn, stream, 64,
                                                       bench_time, bench_cnt)
                elif stream == E4DataStreamID.ACC:
                    results[stream] = benchmark_sensor(conn, stream, 32,
                                                       bench_time, bench_cnt)

    exp_vals = []
    samples = []
    for stream, stats in results.items():
        f_exp, data = stats
        exp_vals.append(f_exp)
        samples.append(data)

    fig, ax = plt.subplots()

    labels = []
    for exp, stream in zip(exp_vals, results.keys()):
        ax.axhline(y=exp)
        labels.append(f'{stream.name}\nNom. Freq. {exp} Hz')

    y_ticks = ax.get_yticks()
    ax.set_yticks(np.append(y_ticks, np.array(exp_vals)))

    ax.boxplot(samples, vert=True, labels=labels)
    ax.legend()

    ax.set_ylabel('Measured sampling frequency [Hz]')

    plt.show()

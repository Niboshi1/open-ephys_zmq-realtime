import numpy as np
import time
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider

from open_ephys_process_zmq import OpenEphysProcess
from repeatedTimer import RepeatedTimer


class SimplePlotter(OpenEphysProcess):
    def __init__(self, sampling_rate):
        """
        :param sampling_rate: the sampling rate of the process
        :return: None
        Here all the configuration detail that is available during
        initialization. However, no matplotlib object should be defined in
        here because they can't be pickled and sent it
        through the process borders. The constructor gets called in the
        """

        super(SimplePlotter, self).__init__()
        self.y = np.empty(0, dtype=np.float32)  # the buffer for the data
        self.x = np.empty(0, dtype=np.float64)  # the buffer for the timestamps
        self.ttl_timestamps = []

        self.chan_in = 32
        self.plotting_interval = 1000.  # in ms
        self.frame_count = 0
        self.frame_max = 0
        self.sampling_rate = sampling_rate
        self.buffer_max = int(self.plotting_interval/1000*self.sampling_rate)
        self.app_name = "Simple Plotter"
        self.continuous_elapsed = 0

        # matplotlib members, initialized to None
        self.ax = None
        self.hl = None
        self.figure = None
        self.num_samples = 0
        self.pipe = None
        self.code = 0

    def startup(self):
        # build the plot
        ylim0 = 200
        self.print_log("starting plot", 'INFO_BLUE')
        self.figure, self.ax = plt.subplots()
        plt.subplots_adjust(left=0.1, bottom=0.2)
        self.ax.set_facecolor('#001230')
        axcolor = 'lightgoldenrodyellow'
        axylim = plt.axes([0.1, 0.05, 0.65, 0.03], facecolor=axcolor)
        sylim = Slider(axylim, 'Ylim', 1, 600, valinit=ylim0)

        # noinspection PyUnusedLocal
        def update(val):
            yl = sylim.val
            self.ax.set_ylim(-yl, yl)
            plt.draw()

        sylim.on_changed(update)

        self.hl, = self.ax.plot([], [])
        self.hl.set_color('#d92eab')
        self.hl.set_linewidth(0.5)
        self.lver = self.ax.axvline(color='white')
        self.ax.set_autoscaley_on(True)
        self.ax.margins(y=0.1)
        self.ax.set_xlim(0., 1)
        self.ax.set_ylim(-ylim0, ylim0)
        # initialize timer
        timer = RepeatedTimer(interval=50/1000, callback=self.callback)
        timer.start()
        plt.show(block=True)

    @staticmethod
    def param_config():
        chan_labels = list(range(32))
        return ("int_set", "chan_in", chan_labels),

    def continuous(self, n_arr, timestamp):
        self.update_plot(n_arr, timestamp)

    def on_event(self, event):
        self.ttl_timestamps.append(event.timestamp)
        time.sleep(1)

    def update_plot(self, n_arr, timestamp, plot_chan=0):
        # setting up frame dependent parameters
        events = []

        # increment the buffer
        self.y = np.append(self.y, n_arr[:, plot_chan])

        # increment the timestamp buffer
        buffer_size_ms = n_arr.shape[0] * 1000. / self.sampling_rate
        self.x = np.append(self.x, np.linspace(timestamp, timestamp + buffer_size_ms, n_arr.shape[0], dtype=np.float64))

        # update the plot once the buffer is full
        if len(self.y) > self.buffer_max:
            # print update time
            self.print_log("time: " + str(time.time()-self.continuous_elapsed), 'INFO_BLUE')
            self.continuous_elapsed = time.time()

            # update the plot
            y = self.y[:self.buffer_max]
            x_real = self.x[:self.buffer_max]

            # search for ttl events in the buffer
            ttl_timestamps = []
            for ts in self.ttl_timestamps:
                if ts > x_real[0] and ts < x_real[-1]:
                    # find the closest index of the timestamp in x_real
                    idx = np.where(x_real > ts)[0][0]
                    ttl_timestamps.append(idx)
                    # delete the timestamp from the list
                    self.ttl_timestamps.remove(ts)

            x = np.arange(len(y), dtype=np.float32) * 1000. / self.sampling_rate
            self.hl.set_ydata(y)
            self.hl.set_xdata(x)

            # add vertical lines for the ttl events
            # clear the previous vertical lines
            if len(ttl_timestamps) == 0:
                self.lver.set_xdata(-1)
            else:
                for idx in ttl_timestamps:
                    self.lver.set_xdata(x[idx])
            self.ax.set_xlim(0., self.plotting_interval)
            self.ax.relim()
            self.ax.autoscale_view(True, True, False)
            self.figure.canvas.draw()
            self.figure.canvas.flush_events()

            self.y = self.y[self.buffer_max:]
            self.x = self.x[self.buffer_max:]

        # if np.random.random() < 0.5:
        #     events.append({'type': 3, 'sampleNum': 0, 'eventId': self.code})
        #     self.code += 1
        return events
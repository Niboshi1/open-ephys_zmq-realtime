import numpy as np
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
        self.chan_in = 32
        self.plotting_interval = 1000.  # in ms
        self.frame_count = 0
        self.frame_max = 0
        self.sampling_rate = sampling_rate
        self.app_name = "Simple Plotter"

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

    def update_plot(self, n_arr, plot_chan=0):
        self.buffer_max = int(self.plotting_interval/1000*self.sampling_rate)
        # setting up frame dependent parameters
        self.num_samples = int(n_arr.shape[0])
        events = []

        # increment the buffer
        self.y = np.append(self.y, n_arr[:, plot_chan])

        # update the plot once the buffer is full
        if len(self.y) > self.buffer_max:
            # update the plot
            y = self.y[:self.buffer_max]
            x = np.arange(len(y), dtype=np.float32) * 1000. / self.sampling_rate
            self.hl.set_ydata(y)
            self.hl.set_xdata(x)
            #print ("shape(x): ", x.shape, " shape(y): ", y.shape, " min:", np.min(y), " max:", np.max(y) )
            self.ax.set_xlim(0., self.plotting_interval)
            self.ax.relim()
            self.ax.autoscale_view(True, True, False)
            self.figure.canvas.draw()
            self.figure.canvas.flush_events()

            self.y = self.y[self.buffer_max:]

        # if np.random.random() < 0.5:
        #     events.append({'type': 3, 'sampleNum': 0, 'eventId': self.code})
        #     self.code += 1
        return events

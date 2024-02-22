import matplotlib.pyplot as plt
import zmq
import sys
import numpy as np
import json
import uuid
import time


class OpenEphysEvent(object):

    event_types = {
        0: 'TIMESTAMP', 
        1: 'BUFFER_SIZE', 
        2: 'PARAMETER_CHANGE',
        3: 'TTL', 
        4: 'SPIKE', 
        5: 'MESSAGE', 
        6: 'BINARY_MSG'
        }

    def __init__(self, _d, _data=None, _timestamp=None):

        self.type = None
        self.stream = ''
        self.sample_num = 0
        self.source_node = 0
        self.event_state = 0
        self.event_line = 0
        self.event_word = 0
        self.numBytes = 0
        self.data = b''

        self.__dict__.update(_d)
        self.timestamp = None
        # noinspection PyTypeChecker
        self.type = OpenEphysEvent.event_types[self.type]
        if _data:
            self.data = _data
            self.numBytes = len(_data)

            dfb = np.frombuffer(self.data, dtype=np.uint8)
            self.event_line = dfb[0]

            dfb = np.frombuffer(self.data, dtype=np.uint8, offset=1)
            self.event_state = dfb[0]

            dfb = np.frombuffer(self.data, dtype=np.uint64, offset=2)
            self.event_word = dfb[0]
        if _timestamp:
            self.timestamp = _timestamp
        if self.type == 'TIMESTAMP':
            t = np.frombuffer(self.data, dtype=np.int64)
            self.timestamp = t[0]

    def set_data(self, _data):
        self.data = _data
        self.numBytes = len(_data)

    def __str__(self):
        ds = self.__dict__.copy()
        del ds['data']
        return str(ds)


class OpenEphysSpikeEvent(object):

    def __init__(self, _d, _data=None):
        self.stream = ''
        self.source_node = 0
        self.electrode = 0
        self.sample_num = 0
        self.num_channels = 0
        self.num_samples = 0
        self.sorted_id = 0
        self.threshold = []

        self.__dict__.update(_d)
        self.data = _data

    def __str__(self):
        ds = self.__dict__.copy()
        del ds['data']
        return str(ds)


class OpenEphysProcess(object):
    def __init__(self, ):
        # keep this slot for multiprocessing related initialization if needed
        self.n_arr_buffer = []
        self.chan_in = 0

        self.context = zmq.Context()
        self.data_socket = None
        self.event_socket = None
        self.poller = zmq.Poller()
        self.message_num = -1
        self.socket_waits_reply = False
        self.event_no = 0
        self.app_name = 'OpenEphys Process'
        self.uuid = str(uuid.uuid4())
        self.last_heartbeat_time = 0
        self.last_reply_time = time.time()
        self.isTesting = True

    def startup(self):
        pass

    def get_time(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    
    def print_log(self, msg, level='INFO_GREEN'):
        info_color = {
            'INFO_BLUE': '\033[94m',
            'INFO_GREEN': '\033[92m',
            'WARN': '\033[93m',
            'ERR': '\033[91m',
            'END': '\033[0m'
        }
        level_color = info_color[level]
        if level == 'INFO_GREEN' or level == 'INFO_BLUE':
            level = 'INFO'
        print(level_color + f"{self.get_time()} [{level}] {msg}" + info_color['END'])

    @staticmethod
    def param_config():
        # TODO we'll have to pass the parameter requests via a second socket
        # this is meant to support a mechanism to set parameters of the
        # application from the Open Ephys GUI.
        # not sure if it will be needed actually, it may disappear
        return ()

    def continuous(self, n_arr, timestamp):
        pass

    def on_event(self, event):
        self.print_log(event, 'INFO_BLUE')

    # noinspection PyMethodMayBeStatic
    def on_spike_event(self, spike):
        print(spike)

    def send_heartbeat(self):
        d = {'application': self.app_name,
             'uuid': self.uuid,
             'type': 'heartbeat'}
        j_msg = json.dumps(d)
        # send heartbeat with time
        self.print_log("sending heartbeat", 'INFO_GREEN')
        self.event_socket.send(j_msg.encode('utf-8'))
        self.last_heartbeat_time = time.time()
        self.socket_waits_reply = True

    def send_event(self, event_list=None, event_type=3, sample_num=0,
                   event_id=2, event_channel=1):
        if not self.socket_waits_reply:
            self.event_no += 1
            if event_list:
                for e in event_list:
                    self.send_event(event_type=e['event_type'],
                                    sample_num=e['sample_num'],
                                    event_id=e['event_id'],
                                    event_channel=e['event_channel'])
            else:
                de = {'type': event_type, 'sample_num': sample_num,
                      'event_id': event_id % 2 + 1,
                      'event_channel': event_channel}

                d = {'application': self.app_name,
                     'uuid': self.uuid,
                     'type': 'event',
                     'event': de}

                j_msg = json.dumps(d)
                print("sending event", j_msg)
                if self.socket_waits_reply:
                    self.print_log("can't send event", 'ERR')
                else:
                    self.event_socket.send(j_msg.encode('utf-8'), 0)
            self.socket_waits_reply = True
            self.last_reply_time = time.time()
        else:
            self.print_log("can't send event, still waiting for previous reply", 'ERR')

    def callback(self):
        events = []

        if not self.data_socket:
            self.print_log("Init socket", 'INFO_BLUE')
            self.data_socket = self.context.socket(zmq.SUB)
            self.data_socket.connect("tcp://localhost:5556")

            self.event_socket = self.context.socket(zmq.REQ)
            self.event_socket.connect("tcp://localhost:5557")

            # self.data_socket.connect("ipc://data.ipc")
            self.data_socket.setsockopt(zmq.SUBSCRIBE, b'')
            self.poller.register(self.data_socket, zmq.POLLIN)
            self.poller.register(self.event_socket, zmq.POLLIN)

        # send every two seconds a "heartbeat"
        # so that Open Ephys knows we're alive

        if self.isTesting:
            # randomly send a TTL event
            if np.random.random() < 0.005:
                self.send_event(event_type=3, sample_num=0,
                                event_id=self.event_no, event_channel=1)

        while True:
            if (time.time() - self.last_heartbeat_time) > 2.:
                if self.socket_waits_reply:
                    self.print_log("heartbeat haven't got reply, retrying...", 'ERR')
                    self.last_heartbeat_time += 1.
                    if (time.time() - self.last_reply_time) > 10.:
                        # reconnecting the socket as per
                        # the "lazy pirate" pattern (see the ZeroMQ guide)
                        self.print_log("connection lost, trying to reconnect", 'ERR')

                        self.poller.unregister(self.event_socket)
                        self.event_socket.close()
                        self.event_socket = self.context.socket(zmq.REQ)
                        self.event_socket.connect("tcp://localhost:5557")
                        self.poller.register(self.event_socket)
                        self.socket_waits_reply = False
                        self.last_reply_time = time.time()
                else:
                    self.send_heartbeat()

            socks = dict(self.poller.poll(1))
            if not socks:
                # print("poll exits")
                break
            if self.data_socket in socks:
                try:
                    message = self.data_socket.recv_multipart(zmq.NOBLOCK)
                except zmq.ZMQError as err:
                    self.print_log(f"got error: {err}", 'ERR')
                    break
                if message:
                    if len(message) < 2:
                        self.print_log(f"no frames for message: {message[0]}", 'ERR')
                    try:
                        header = json.loads(message[1].decode('utf-8'))
                    except ValueError as e:
                        self.print_log(f"ValueError: {e}", 'ERR')
                        self.print_log(f"{message[1]}", 'ERR')
                    if self.message_num != -1 and header['message_num'] != self.message_num + 1:
                        self.print_log(f"missing a message at number {self.message_num}", 'ERR')

                    self.message_num = header['message_num']
                    if header['type'] == 'data':
                        c = header['content']
                        num_samples = c['num_samples']
                        channel_num = c['channel_num']
                        sample_rate = c['sample_rate']
                        sample_num = c['sample_num']
                        timestamp = header['timestamp']

                        # get the data
                        try:
                            n_arr = np.frombuffer(message[2],
                                                    dtype=np.float32)
                            n_arr = np.reshape(n_arr, num_samples)
                            self.n_arr_buffer.append(n_arr)

                        except IndexError as e:
                            self.print_log(f"{e}", 'ERR')
                            self.print_log(f"{header}", 'ERR')
                            self.print_log(f"{message[1]}", 'ERR')

                            if len(message) > 2:
                                self.print_log(f"{len(message[2])}", 'ERR')
                            else:
                                self.print_log("only one frame???", 'ERR')

                        # update the plot when the last channel is received
                        if channel_num == int(self.chan_in-1):
                            n_arr = np.array(self.n_arr_buffer).T
                            if num_samples > 0:
                                self.continuous(n_arr, timestamp)
                            
                            # reset the buffer
                            self.n_arr_buffer = []

                    elif header['type'] == 'event':

                        if header['data_size'] > 0:
                            event = OpenEphysEvent(header['content'],
                                                   message[2],
                                                   header['timestamp'])
                        else:
                            event = OpenEphysEvent(header['content'])

                        self.on_event(event)

                    elif header['type'] == 'spike':
                        spike = OpenEphysSpikeEvent(header['spike'],
                                                    message[2])
                        self.on_spike_event(spike)

                    elif header['type'] == 'param':
                        c = header['content']
                        self.__dict__.update(c)
                        self.print_log(f"{c}", 'INFO_GREEN')
                    else:
                        raise ValueError("message type unknown")
                else:
                    self.print_log("got no data", 'ERR')

                    break
            elif self.event_socket in socks and self.socket_waits_reply:
                message = self.event_socket.recv()
                #self.print_log("event reply received", 'INFO_GREEN')
                self.print_log(f"OpenEphys GUI: {message}", 'INFO_GREEN')
                if self.socket_waits_reply:
                    self.socket_waits_reply = False

                else:
                    self.print_log("???? getting a reply before a send?", 'ERR')
        # print "finishing callback"
        if events:
            pass  # TODO implement the event passing

        return True

    @staticmethod
    def terminate():
        plt.close()
        sys.exit(0)

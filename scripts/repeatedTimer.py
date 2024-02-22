from threading import Timer

class RepeatedTimer(Timer):
    def __init__(self, interval, callback):
        self.interval = interval
        self.callback = callback

    def start(self):
        timer = Timer(self.interval, self._run)
        timer.start()

    def stop(self):
        self.timer.cancel()

    def _run(self):
        self.callback()
        self.start()

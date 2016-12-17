import logging
import sys
import thread
import threading

from location_server import LocationServer


class GrpcSource:
    def __init__(self, port):
        self._x = -1
        self._y = -1
        self._width = -1
        self._height = -1
        self._middle_inc = -1
        self._x_lock = threading.Lock()
        self._y_lock = threading.Lock()
        self._x_ready = threading.Event()
        self._y_ready = threading.Event()
        self._location_server = LocationServer('[::]:' + str(port), self)

    def start_grpc_source(self):
        try:
            thread.start_new_thread(LocationServer.start_location_server, (self._location_server,))
            logging.info("Started gRPC location server")
        except BaseException as e:
            logging.error("Unable to start gRPC location server [{0}]".format(e))
            sys.exit(1)

    def set_location(self, location):
        with self._x_lock:
            self._x = location[0]
            self._width = location[2]
            self._middle_inc = location[4]
            self._x_ready.set()

        with self._x_lock:
            self._y = location[1]
            self._height = location[3]
            self._middle_inc = location[4]
            self._y_ready.set()

    # Blocking
    def get_x(self):
        self._x_ready.wait()
        with self._x_lock:
            self._x_ready.clear()
            return self._x, self._width, self._middle_inc

    # Blocking
    def get_y(self):
        self._y_ready.wait()
        with self._y_lock:
            self._y_ready.clear()
            return self._y, self._height, self._middle_inc

    # Non-blocking
    def get_pos(self, name):
        return self._x if name == "x" else self._y

    # Non-blocking
    def get_size(self, name):
        return self._width if name == "x" else self._height

import logging
import sys
import time

import camera
import common_cli_args  as cli
import cv2
import image_server as img_server
import imutils
import opencv_utils as utils
from common_cli_args import setup_cli_args
from common_utils import is_raspi
from contour_finder import ContourFinder
from location_server import LocationServer

# I tried to include this in the constructor and make it depedent on self.__leds, but it does not work
if is_raspi():
    from blinkt import set_pixel, show

logger = logging.getLogger(__name__)


class GenericObjectTracker(object):
    def __init__(self,
                 bgr_color,
                 width,
                 middle_percent,
                 minimum_pixels,
                 hsv_range,
                 grpc_port,
                 display,
                 flip_x,
                 flip_y,
                 usb_camera,
                 leds,
                 camera_name,
                 http_host,
                 http_delay_secs,
                 http_file):
        self.__width = width
        self.__middle_percent = middle_percent
        self.__orig_width = width
        self.__orig_middle_percent = middle_percent
        self.__display = display
        self.__flip_x = flip_x
        self.__flip_y = flip_y
        self.__leds = leds

        self.__stopped = False
        self.__http_launched = False
        self.__cnt = 0
        self.__last_write_millis = 0
        self._prev_x, self._prev_y = -1, -1
        self.__contour_finder = ContourFinder(bgr_color, hsv_range, minimum_pixels)
        self.__location_server = LocationServer(grpc_port)
        self.__cam = camera.Camera(use_picamera=not usb_camera)
        self.__http_server = img_server.ImageServer(camera_name, http_host, http_delay_secs, http_file)

    @property
    def width(self):
        return self.__width

    @width.setter
    def width(self, width):
        if 200 <= width <= 4000:
            self.__width = width
            self._prev_x, self._prev_y = -1, -1

    @property
    def percent(self):
        return self.__middle_percent

    @percent.setter
    def percent(self, percent):
        if 2 <= percent <= 98:
            self.__middle_percent = percent
            self._prev_x, self._prev_y = -1, -1

    @property
    def stopped(self):
        return self.__stopped

    @property
    def contour_finder(self):
        return self.__contour_finder

    @property
    def location_server(self):
        return self.__location_server

    @property
    def cam(self):
        return self.__cam

    @property
    def http_server(self):
        return self.__http_server

    @property
    def cnt(self):
        return self.__cnt

    @cnt.setter
    def cnt(self, val):
        self.__cnt = val

    def stop(self):
        self.__stopped = True
        self.__location_server.stop()
        self.__http_server.stop()

    def set_leds(self, left_color, right_color):
        if not is_raspi():
            return
        if self.__leds:
            for i in range(0, 4):
                set_pixel(i, left_color[2], left_color[1], left_color[0], brightness=0.05)
        if self.__leds:
            for i in range(4, 8):
                set_pixel(i, right_color[2], right_color[1], right_color[0], brightness=0.05)
            show()

    def clear_leds(self):
        self.set_leds([0, 0, 0], [0, 0, 0])

    def process_image(self, image, img_width, img_height):
        raise Exception("Implemented by subclass")

    # Do not run this in a background thread. cv2.waitKey has to run in main thread
    def start(self):
        try:
            self.location_server.start()
        except BaseException as e:
            logger.error("Unable to start location server [{0}]".format(e), exc_info=True)
            sys.exit(1)

        self.location_server.write_location(-1, -1, 0, 0, 0)

        while self.cam.is_open() and not self.stopped:
            try:
                image = self.cam.read()
                image = imutils.resize(image, width=self.width)
                image = self.flip(image)

                img_height, img_width = image.shape[:2]

                # Called once the dimensions of the images are known
                self.http_server.serve_images(img_width, img_height)

                self.process_image(image, img_width, img_height)
                self.http_server.image = image
                self.display_image(image)

                self.cnt += 1

            except KeyboardInterrupt as e:
                raise e
            except BaseException as e:
                logger.error("Unexpected error in main loop [{0}]".format(e), exc_info=True)
                time.sleep(1)

        self.clear_leds()
        self.cam.close()

    def display_image(self, image):
        if self.__display:
            cv2.imshow("Image", image)

            key = cv2.waitKey(1) & 0xFF

            if key == 255:
                pass
            elif key == ord("w"):
                self.width -= 10
            elif key == ord("W"):
                self.width += 10
            elif key == ord("-") or key == ord("_") or key == 0:
                self.percent -= 1
            elif key == ord("+") or key == ord("=") or key == 1:
                self.percent += 1
            elif key == ord("r"):
                self.width = self.__orig_width
                self.percent = self.__orig_middle_percent
            elif key == ord("s"):
                utils.write_image(image, log_info=True)
            elif key == ord("q"):
                self.stop()

    @property
    def markup_image(self):
        return self.__display or self.http_server.enabled

    def flip(self, image):
        img = image
        if self.__flip_x:
            img = cv2.flip(img, 0)
        if self.__flip_y:
            img = cv2.flip(img, 1)
        return img

    @staticmethod
    def cli_args():
        return setup_cli_args(cli.bgr,
                              cli.usb,
                              cli.width,
                              cli.middle_percent,
                              cli.minimum_pixels,
                              cli.hsv_range,
                              cli.grpc_port,
                              cli.leds,
                              cli.flip_x,
                              cli.flip_y,
                              cli.camera_name_optional,
                              cli.http_host,
                              cli.http_delay_secs,
                              cli.http_file,
                              cli.display,
                              cli.verbose)

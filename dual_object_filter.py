#!/usr/bin/env python2

import logging

import cv2
import opencv_defaults as defs
from cli_args import LOG_LEVEL
from constants import MINIMUM_PIXELS, GRPC_PORT, HSV_RANGE, LEDS, CAMERA_NAME, HTTP_HOST, USB_CAMERA, WIDTH, DISPLAY, \
    BGR_COLOR, MIDDLE_PERCENT, FLIP_X, FLIP_Y
from generic_filter import GenericFilter
from object_tracker import ObjectTracker
from opencv_utils import BLUE, GREEN, RED, YELLOW
from opencv_utils import get_moment
from utils import setup_logging

logger = logging.getLogger(__name__)


class DualObjectFilter(GenericFilter):
    def __init__(self, tracker, *args, **kwargs):
        super(DualObjectFilter, self).__init__(tracker, *args, **kwargs)

    def process_image(self, image):
        img_height, img_width = image.shape[:2]
        mid_x, mid_y = img_width / 2, img_height / 2
        avg_x, avg_y = -1, -1

        text = "#{0} ({1}, {2})".format(self.tracker.cnt, img_width, img_height)
        text += " {0}%".format(self.tracker.middle_percent)

        # Find the 2 largest contours
        contours = self.contour_finder.get_max_contours(image, count=2)

        # Check for > 2 in case one of the targets is divided.
        # The calculation will be off, but something will be better than nothing
        if contours is not None and len(contours) >= 2:
            countour1, area1, img_x1, img_y1 = get_moment(contours[0])
            countour2, area2, img_x2, img_y2 = get_moment(contours[1])

            # Calculate the average location between the two midpoints
            avg_x = (abs(img_x1 - img_x2) / 2) + min(img_x1, img_x2)
            avg_y = (abs(img_y1 - img_y2) / 2) + min(img_y1, img_y2)

            if self.tracker.markup_image:
                x1, y1, w1, h1 = cv2.boundingRect(countour1)
                if self.draw_box:
                    cv2.rectangle(image, (x1, y1), (x1 + w1, y1 + h1), BLUE, 2)
                if self.draw_contour:
                    cv2.drawContours(image, [countour1], -1, GREEN, 2)
                cv2.circle(image, (img_x1, img_y1), 4, RED, -1)

                x2, y2, w2, h2 = cv2.boundingRect(countour2)
                cv2.rectangle(image, (x2, y2), (x2 + w2, y2 + h2), BLUE, 2)
                cv2.drawContours(image, [countour2], -1, GREEN, 2)
                cv2.circle(image, (img_x2, img_y2), 4, RED, -1)

                # Draw midpoint
                cv2.circle(image, (avg_x, avg_y), 4, YELLOW, -1)
                text += " Avg: ({0}, {1})".format(avg_x, avg_y)

        # The middle margin calculation is based on % of width for horizontal and vertical boundary
        middle_pct = (float(self.tracker.middle_percent) / 100.00) / 2
        middle_inc = int(mid_x * middle_pct)
        x_in_middle = mid_x - middle_inc <= avg_x <= mid_x + middle_inc
        y_in_middle = mid_y - middle_inc <= avg_y <= mid_y + middle_inc
        x_color = GREEN if x_in_middle else RED if avg_x == -1 else BLUE
        y_color = GREEN if y_in_middle else RED if avg_y == -1 else BLUE

        # Set Blinkt leds
        if self.leds:
            self.set_leds(x_color, y_color)

        # Write location if it is different from previous value written
        if avg_x != self.prev_x or avg_y != self.prev_y:
            self.location_server.write_location(avg_x, avg_y, img_width, img_height, middle_inc)
            self.prev_x, self.prev_y = avg_x, avg_y

        if self.tracker.markup_image:
            # Draw the alignment lines
            if self.vertical_lines:
                cv2.line(image, (mid_x - middle_inc, 0), (mid_x - middle_inc, img_height), x_color, 1)
                cv2.line(image, (mid_x + middle_inc, 0), (mid_x + middle_inc, img_height), x_color, 1)
            if self.horizontal_lines:
                cv2.line(image, (0, mid_y - middle_inc), (img_width, mid_y - middle_inc), y_color, 1)
                cv2.line(image, (0, mid_y + middle_inc), (img_width, mid_y + middle_inc), y_color, 1)
            if self.display_text:
                cv2.putText(image, text, defs.TEXT_LOC, defs.TEXT_FONT, defs.TEXT_SIZE, RED, 1)


if __name__ == "__main__":
    # Parse CLI args
    args = ObjectTracker.cli_args()

    # Setup logging
    setup_logging(level=args[LOG_LEVEL])

    tracker = ObjectTracker(width=args[WIDTH],
                            middle_percent=args[MIDDLE_PERCENT],
                            display=args[DISPLAY],
                            flip_x=args[FLIP_X],
                            flip_y=args[FLIP_Y],
                            usb_camera=args[USB_CAMERA],
                            camera_name=args[CAMERA_NAME],
                            http_host=args[HTTP_HOST],
                            http_delay_secs=args["http_delay_secs"],
                            http_file=args["http_file"],
                            http_verbose=args["http_verbose"])

    filter = DualObjectFilter(tracker,
                              bgr_color=args[BGR_COLOR],
                              hsv_range=args[HSV_RANGE],
                              minimum_pixels=args[MINIMUM_PIXELS],
                              grpc_port=args[GRPC_PORT],
                              leds=args[LEDS],
                              display_text=True,
                              draw_contour=True,
                              draw_box=True,
                              vertical_lines=True,
                              horizontal_lines=True)
    try:
        tracker.start(filter)
    except KeyboardInterrupt:
        pass
    finally:
        tracker.stop()

    logger.info("Exiting...")
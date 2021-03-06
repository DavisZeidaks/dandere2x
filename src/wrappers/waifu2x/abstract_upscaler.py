"""
    This file is part of the Dandere2x project.
    Dandere2x is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    Dandere2x is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.
    You should have received a copy of the GNU General Public License
    along with Dandere2x.  If not, see <https://www.gnu.org/licenses/>.
""""""
========= Copyright aka_katto 2018, All rights reserved. ============
Original Author: aka_katto 
Purpose: 
 
====================================================================="""
import os
import time
from abc import ABC, abstractmethod
from threading import Thread

from context import Context
from dandere2xlib.utils.dandere2x_utils import get_lexicon_value, wait_on_file_controller, file_exists
from wrappers.frame.frame import Frame


class AbstractUpscaler(Thread, ABC):

    """
    Notes: When instantiating an AbstractUpscaler type, super().__init__(context) goes last since
    self._construct_upscale_command() is an implemented method and needs the instantiated variables in the inheriting
    class.
    """
    def __init__(self, context: Context):
        super().__init__()

        # load context
        self.context = context
        self.controller = self.context.controller
        self.residual_images_dir = context.residual_images_dir
        self.residual_upscaled_dir = context.residual_upscaled_dir
        self.noise_level = context.noise_level
        self.scale_factor = context.scale_factor
        self.workspace = context.workspace
        self.frame_count = context.frame_count

        self.upscale_command = self._construct_upscale_command()

    # todo - not verifying if program even exists.
    def verify_upscaling_works(self) -> None:
        """
        Verify the upscaler works by upscaling a very small frame, and throws a descriptive error if it doesn't.
        """
        test_file = self.context.workspace + "test_frame.jpg"
        test_file_upscaled = self.context.workspace + "test_frame_upscaled.jpg"

        test_frame = Frame()
        test_frame.create_new(2, 2)
        test_frame.save_image(test_file)

        self.upscale_file(test_file, test_file_upscaled)

        if not file_exists(test_file_upscaled):
            print("Your computer could not upscale a test image, which is required for dandere2x to work.")
            print("This may be a hardware issue or a software issue - verify your computer is capable of upscaling "
                  "images using the selected upscaler.")

            raise Exception("Your computer could not upscale the test file.")

        os.remove(test_file)
        os.remove(test_file_upscaled)

    def run(self) -> None:
        """
        Every upscaler essentially works like this (more or less):
        1) Continue to do the same thing until we've upscaled every frame possible.
        2) The dandere2x session was yanked.
        3) Delete upscaled files so the upscaler doesnt have to upscale them twice.

        As a result, I've abstracted this into the abstract class, so every upscaler to behave in this way
        to keep the variation of upscalers consistent across variations.
        """

        remove_thread = RemoveUpscaledFiles(context=self.context)
        remove_thread.start()

        while not self.check_if_done() and self.controller.is_alive():
            self.repeated_call()

    def join(self, timeout=None) -> None:
        while self.controller.is_alive() and not self.check_if_done():
            time.sleep(0.05)

    def check_if_done(self) -> bool:
        if self.controller.get_current_frame() >= self.frame_count - 1:
            return True

        return False

    @abstractmethod
    def _construct_upscale_command(self) -> list:
        """
        Every waifu2x-upscaler has to have a command that needs to be called in order to upscale a file(s).

        For example, waifu2x-ncnn-vulkans is:
                "C:\..\waifu2x-ncnn-vulkan -i file.png -o output.png"
        This needs to be put into an array to be callable via subprocess.call
        """
        pass

    @abstractmethod
    def upscale_file(self, input_image: str, output_image: str) -> None:
        """
        Upscale a single file using the implemented upscaling program.
        """
        pass

    @abstractmethod
    def repeated_call(self) -> None:
        """
        Every upscaler varient will continue to repeat the same call (in whatever way it was implemented)
        until Dandere2x has finished.
        """
        pass


class RemoveUpscaledFiles(Thread):
    def __init__(self, context):
        Thread.__init__(self, name="Remove Upscale Files Thread")
        super().__init__()

        self.context = context

        # make a list of names that will eventually (past or future) be upscaled
        self.list_of_names = []
        for x in range(self.context.start_frame, self.context.frame_count):
            self.list_of_names.append("output_" + get_lexicon_value(6, x) + ".jpg")

    # todo, fix this a bit. This isn't scalable / maintainable
    def run(self) -> None:
        for x in range(len(self.list_of_names)):
            name = self.list_of_names[x]
            residual_file = self.context.residual_images_dir + name.replace(".png", ".jpg")
            residual_upscaled_file = self.context.residual_upscaled_dir + name.replace(".jpg", ".png")

            wait_on_file_controller(residual_upscaled_file, self.context.controller)
            if not self.context.controller.is_alive():
                return

            if os.path.exists(residual_file):
                os.remove(residual_file)
            else:
                pass

    def join(self, timeout=None):
        Thread.join(self, timeout)

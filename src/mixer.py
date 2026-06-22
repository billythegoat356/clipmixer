from os import listdir
from random import shuffle
from typing import Generator
import cupy as cp

from ovni.base import demux_and_decode, encode, mux
from ovni.ops import pipe_nv12_to_rgb, scale_translate, overlay, pipe_rgb_to_nv12
from ovni.utils import get_video_duration, get_video_frame_count, get_video_framerate, get_video_dimensions, resample_frames





BITRATE = '8M'
PRESET = 'P1'

CLIPS_FOLDER = "clips"


OvniGenerator = Generator[cp.ndarray, None, None]



class ClipMixer:

    def __init__(
            self,
            transition_duration: float,
            output_duration: float | None,
            framerate: int,
            width: int,
            height: int,
            out_path: str
    ):
        """
        Initialize a ClipMixer instance

        Parameters:
            transition_duration: float - the duration of each transition, in seconds
            output_duration: float | None - the (minimum) duration of the output
            framerate: int
            width: int
            height: int
            out_path: str
        """
        self.transition_duration = transition_duration
        self.output_duration = output_duration
        self.framerate = framerate
        self.width = width
        self.height = height
        self.out_path = out_path


    def run(self):
        """
        Runs the pipeline and generates the video at the output path
        """
            
        frames = self.frames_generator()

        frames = pipe_rgb_to_nv12(frames)
        stream = encode(frames, self.width, self.height, self.framerate, BITRATE, PRESET)
        mux(stream, self.out_path)

        
    def get_clips(self) -> list[str]:
        """
        Gets the list of clips to use, randomly chosen, in order to exceed output duration
        
        Returns:
            list[str]
        """
        all_clips = listdir(CLIPS_FOLDER)
        shuffle(all_clips)

        final_clips = []
        duration = 0

        for clip in all_clips:
            clip_duration = get_video_duration(CLIPS_FOLDER + '/' + clip)

            duration += clip_duration
            final_clips.append(clip)

            if (
                self.output_duration is not None and
                duration - ((len(final_clips) - 1) * self.transition_duration) >= self.output_duration
            ):
                break

        return final_clips



    def adjust_dims(self, bg_frames: OvniGenerator, bg_width: int, bg_height: int) -> OvniGenerator:
        """
        Adjusts the dimensions of the bg frames to match with the requested ones

        Parameters:
            bg_frame: OvniGenerator
            bg_width: int
            bg_height: int

        Returns:
            OvniGenerator
        """

        if self.width == bg_width and self.height == bg_height:
            yield from bg_frames
            return

        bg_ar = bg_width / bg_height
        target_ar = self.width / self.height

        if bg_ar > target_ar:
            # Width is too big, we limit at height
            scale = self.height / bg_height
        
        elif bg_ar < target_ar:
            # Height is too big, we limit at width
            scale = self.width / bg_width

        else:
            # We can limit at any
            scale = self.width / bg_width

        # Calculate translations after scale is applied
        tx = (self.width - bg_width*scale) / 2
        ty = (self.height - bg_height*scale) / 2

        for frame in bg_frames:

            # First its scaled then translated
            frame = scale_translate(
                frame,
                scale=scale,
                tx=tx,
                ty=ty,
                dst_width=self.width,
                dst_height=self.height
            )

            yield frame
    



    def frames_generator(self) -> OvniGenerator:
        """
        The actual generator yielding frames
        
        Returns:
            OvniGenerator
        """

        clips = self.get_clips()

        # Lists storing clips frame count and generators
        clips_frame_count: list[int] = []
        clips_generators: list[OvniGenerator] = []

        for clip in clips:
            clip_path = CLIPS_FOLDER + '/' + clip

            clip_frame_count = get_video_frame_count(clip_path)
            clip_framerate = get_video_framerate(clip_path)

            resampled_frame_count = int(self.framerate / clip_framerate * clip_frame_count) # ovni never adds last one when resampling!
            clips_frame_count.append(resampled_frame_count)


            clip_gen = demux_and_decode(clip_path)
            clip_gen = resample_frames(clip_gen, clip_framerate, self.framerate)

            width, height = get_video_dimensions(clip_path)
            clip_gen = pipe_nv12_to_rgb(clip_gen, width, height)
            clip_gen = self.adjust_dims(clip_gen, width, height)

            clips_generators.append(clip_gen)


        for i in range(len(clips)):

            # Skip end transition for last one
            if i == len(clips) - 1:
                yield from clips_generators[i]
                break

            frame_i = 0

            for frame1 in clips_generators[i]:

                left_seconds = (clips_frame_count[i] - (frame_i + 1)) / self.framerate

                # If not the first one, remove the transition duration, that happened previously
                if i != 0:
                    left_seconds -= self.transition_duration

                # If in the transition period, mix frames
                if left_seconds <= self.transition_duration:
                    opacity = 1 - (left_seconds / self.transition_duration)

                    frame2 = next(clips_generators[i+1])

                    overlay(frame1, frame2, 0, 0, opacity)
                
                yield frame1

                frame_i += 1



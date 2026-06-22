from time import time
from src import ClipMixer


t = time()

ClipMixer(
    transition_duration=0.5,
    output_duration=None,
    framerate=24,
    width=1920,
    height=1080,
    out_path="out.mp4"
).run()

print(f"Done in {round(time() - t, 2)}s.")
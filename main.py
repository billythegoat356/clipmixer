from time import time
from src import ClipMixer


t = time()

ClipMixer(
    transition_duration=0.5,
    output_duration=60,
    framerate=60,
    width=1080,
    height=1920,
    out_path="out.mp4"
).run()

print(f"Done in {round(time() - t, 2)}s.")
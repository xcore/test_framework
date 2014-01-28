import time
import random
import sys

if len(sys.argv) > 1:
    random.seed(int(sys.argv[1]))
else:
    random.seed(1)

bug = -1
if len(sys.argv) > 2:
    bug = int(sys.argv[2])

output = [
    (random.random() * 3, "Started"),
    (random.random() * 3, "Next"),
    (random.random() * 3, "Count0"),
    (random.random() * 3, "Count1"),
]

for (i, (delay, string)) in enumerate(output):
    if bug != i:
        time.sleep(delay)
        print string


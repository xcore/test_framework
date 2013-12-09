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
    (random.random() * 10, "PTP Role: Master"),
    (random.random() * 10, "MAAP reserved Talker stream #0 address: 91:E0:F0:0:97:8B"),
    (random.random() * 10, "CONNECTING Talker stream #0 (22970042A10000) -> Listener 0:22:97:FF:FE:0:42:A2"),
    (random.random() * 10, "Talker stream #0 ready"),
    (random.random() * 10, "Talker stream #0 on"),
    (random.random() * 1,  "CONNECTING Listener sink #0 chan map:"),
    (random.random() * 1,  "  0 -> 0"),
    (random.random() * 1,  "  1 -> 1"),
    (random.random() * 1,  "  2 -> 2"),
    (random.random() * 1,  "  3 -> 3"),
    (random.random() * 1,  "Media output 0 locked: 75 samples shorter"),
    (random.random() * 1,  "Media output 1 locked: 73 samples shorter"),
    (random.random() * 1,  "Media output 2 locked: 74 samples shorter"),
    (random.random() * 1,  "Media output 3 locked: 75 samples shorter"),
]

for (i, (delay, string)) in enumerate(output):
    if bug != i:
        time.sleep(delay)
        print string


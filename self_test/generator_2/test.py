import random
import xmos.test.generator as generator

random.seed(1)

if __name__ == "__main__":

    import json
    with open('test.json') as f:
        x = json.load(f, object_hook=generator.json_hooks)

    for i in x:
        print i


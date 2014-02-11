import random
import os
import sys

def get_parent(full_path):
  (parent, file) = os.path.split(full_path)
  return parent

# Configure the path so that the test framework will be found
rootDir = get_parent(get_parent(get_parent(get_parent(os.path.realpath(__file__)))))
sys.path.append(os.path.join(rootDir,'test_framework'))

import xmos.test.generator as generator

random.seed(1)

if __name__ == "__main__":

  import json
  with open('test.json') as f:
    x = json.load(f, object_hook=generator.json_hooks)

  for i in x:
    command = i.get_command()
    if command is None:
      continue
    print i.command


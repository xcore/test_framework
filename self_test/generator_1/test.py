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
  seq = generator.Sequence([
          generator.Command("+", { 'repeat' : 2 }),
          generator.Choice([
            generator.Command("A", { 'weight' : 10 }),
            generator.Command("B", { 'weight' : 1 })
          ], { 'repeat' : 10 }),
          generator.Command("*")], { 'order_rand' : True, 'repeat' : 10 })

  for i in seq:
      print i.command


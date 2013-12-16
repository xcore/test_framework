#!/usr/bin/python

import os
import subprocess
import re

test_dirs = [d for d in os.listdir('.') if os.path.isdir(d)]
test_dirs.sort()

top_dir = os.getcwd()

for d in test_dirs:
  print "---- Running {test_dir} ----".format(test_dir=d)

  # This was done using subprocess.call, but that fails to work with the
  # tests using the Twisted framework
  os.chdir(os.path.join(top_dir, d))
  os.system("python test.py > test.output 2>&1")

  err = subprocess.call(["diff","test.output","expected.output"])

  if err == 0:
      print "PASSED"
  else:
      print "ERROR: Mismatch between actual and expected outputs"


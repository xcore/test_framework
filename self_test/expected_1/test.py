import sys
import os

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks

def get_parent(full_path):
  (parent, file) = os.path.split(full_path)
  return parent

# Configure the path so that the test framework will be found
rootDir = get_parent(get_parent(get_parent(get_parent(os.path.realpath(__file__)))))
sys.path.append(os.path.join(rootDir,'test_framework'))

import xmos.test.process as process
import xmos.test.master as master
import xmos.test.base as base
import xmos.test.xmos_logging as xmos_logging
from xmos.test.xmos_logging import log_debug
from xmos.test.base import AllOf, OneOf, NoneOf, Sequence, Expected

endpoints = []

@inlineCallbacks
def runTest(args):
  """ The test program - needs to yield on each expect and be decorated
    with @inlineCallbacks
  """

  startup = AllOf([Expected(e, "Started", 10) for e in endpoints])
  log_debug(startup)
  yield master.expect(startup)

  next_steps = AllOf([AllOf([Expected('ep0', "Next", 10)]), AllOf([Expected('ep1', "Next", 10)])])
  log_debug(next_steps)
  yield master.expect(next_steps)

  seq = AllOf([Sequence([Expected(e, "Count0", 10), Expected(e, "Count1", 10)]) for e in endpoints])
  log_debug(seq)
  yield master.expect(seq)

  base.testComplete(reactor)
      

if __name__ == "__main__":
  parser = base.getParser()
  parser.add_argument(dest="seed", nargs="?", type=int, default=1)
  parser.add_argument(dest="ep0_bug", nargs="?", type=int, default=-1)
  parser.add_argument(dest="ep1_bug", nargs="?", type=int, default=-1)
  args = parser.parse_args()

  xmos_logging.configure_logging(level_file='DEBUG', filename=args.logfile)

  # Create the master to pass to each process
  master = master.Master()

  # Endpoint 0
  endpoints.append('ep0')
  ep0 = process.XrunProcess('ep0', master, verbose=True, output_file="ep0_console.log")

  # Call python with unbuffered mode to enable us to see each line as it happens
  reactor.spawnProcess(ep0, 'python',
      ['python', '-u', 'process_0.py', str(args.seed), str(args.ep0_bug)],
      env=os.environ)

  # Endpoint 1
  endpoints.append('ep1')
  ep1 = process.XrunProcess('ep1', master, verbose=True, output_file="ep1_console.log")
  reactor.spawnProcess(ep1, 'python',
      ['python', '-u', 'process_1.py', str(args.seed + 1), str(args.ep1_bug)],
      env=os.environ)

  base.testStart(runTest, args)
  

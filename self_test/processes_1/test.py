import sys
import os

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks

import xmos.test.process as process
import xmos.test.master as master
import xmos.test.base as base
from xmos.test.base import AllOf, OneOf, NoneOf, Sequence, Expected

endpoints = []

@inlineCallbacks
def runTest(args):
  """ The test program - needs to yield on each expect and be decorated
    with @inlineCallbacks
  """

  startup = AllOf([Expected(e, "PTP Role: Master", 30) for e in endpoints])

  ptpslave = OneOf([
      Sequence([Expected(e, "PTP Role: Slave", 5),
            Expected(e, "PTP sync locked", 1)])
      for e in endpoints
    ])

  talker_connections = [
      Sequence([Expected(e, "MAAP reserved Talker stream #0 address: 91:E0:F0:0", 30),
            Expected(e, "CONNECTING Talker stream #0", 10),
            Expected(e, "Talker stream #0 ready", 10),
            Expected(e, "Talker stream #0 on", 10)])
      for e in endpoints
    ]

  listener_connections = [
      Sequence([Expected(e, "CONNECTING Listener sink #0", 30),
            AllOf([Expected(e, "%d -> %d" % (n, n), 10) for n in range(4)]),
            AllOf([Expected(e, "Media output %d locked" % n, 10) for n in range(4)]),
            NoneOf([Expected(e, "lost lock", 10)])])
      for e in endpoints
    ]

  yield master.expect(startup)
  for name,process in base.getActiveProcesses().iteritems():
    process.registerErrorPattern("PTP Role: Master")
  yield master.expect(AllOf([ptpslave] + talker_connections + listener_connections))

  base.testComplete(reactor)
      

if __name__ == "__main__":
  parser = base.getParser()
  parser.add_argument(dest="seed", nargs="?", type=int, default=1)
  parser.add_argument(dest="ep0_bug", nargs="?", type=int, default=-1)
  parser.add_argument(dest="ep1_bug", nargs="?", type=int, default=-1)
  args = parser.parse_args()

  # Create the master to pass to each process
  master = master.Master()

  # Endpoint 0
  endpoints.append('ep0')
  ep0 = process.XrunProcess('ep0', master, verbose=True, output_file="ep0_console.log")

  # Call python with unbuffered mode to enable us to see each line as it happens
  reactor.spawnProcess(ep0, 'python',
      ['python', '-u', 'back_to_back_master.py', str(args.seed), str(args.ep0_bug)],
      env=os.environ)

  # Endpoint 1
  endpoints.append('ep1')
  ep1 = process.XrunProcess('ep1', master, verbose=True, output_file="ep1_console.log")
  reactor.spawnProcess(ep1, 'python',
      ['python', '-u', 'back_to_back_slave.py', str(args.seed + 1), str(args.ep1_bug)],
      env=os.environ)

  base.testStart(runTest, args)
  

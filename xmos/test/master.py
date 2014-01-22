from xmos.test.process import *
from xmos.test.base import *

class Master():
  def __init__(self):
    self.timeout = None
    self.deferred = None
    self.expected = None

  def checkReceived(self, process, string):
    """ Check one process and string against the expected values,
      remove it if found.
    """
    assert self.expected
    (completed, started, timedout) = self.expected.completes(process, string)

    if completed or started:
      if process in activeProcesses and test_config.prune_on_match:
        activeProcesses[process].pruneExpectHistory(string)
      log_debug("Events remaining: %s" % self.expected)

    if completed:
      self.expected = None
    return (completed, started, timedout)

  def checkAgainstHistory(self):
    """ Check through the existing process data history to
      see whether the expected has already been seen.
    """
    for process in self.expected.getProcesses():
      for data in activeProcesses[process].getExpectHistory():
        self.checkReceived(process, data)
        if not self.expected:
          return

  def clearExpectHistory(self, process):
    activeProcesses[process].clearExpectHistory()

  def expect(self, expected):
    # If there is nothing to expect then just continue
    if not expected:
      return []

    self.expected = expected
    self.checkAgainstHistory()

    # If the expected has already been met (self.expected == None)
    # then simply return and the test will continue
    if not self.expected:
      return self.expected

    self.expected.registerTimeouts(self)

    # Create a deferred to return while we wait
    self.deferred = Deferred()
    return self.deferred

  def sendLine(self, process, command):
    activeProcesses[process].sendLine(command)

  def receive(self, process, string):
    if self.expected:
      (completed, started, timedout) = self.checkReceived(process, string)
      if started and not completed:
        self.checkAgainstHistory()

    if not self.expected:
      self.callDeferred()

  def timedOut(self, done):
    """ We've seen one timeout, clear all other pending ones and continue
    """
    assert self.expected

    if done:
      self.expected.cancelTimeouts()
      self.callDeferred()
    else:
      # Check for valid timeouts having completed all transactions
      self.checkReceived('invalid', 'invalid')
      if not self.expected:
        self.callDeferred()

  def callDeferred(self):
    """ Call the deferred and ensure it is removed so that it
      can't be called again
    """
    remaining = self.expected
    self.expected = []

    if self.deferred:
      d = self.deferred
      self.deferred = None
      d.callback(remaining)

  def killAllActive(self):
    global activeProcesses
    for (n, p) in activeProcesses.iteritems():
      try:
        p.kill()
      except:
        # process already ended
        pass

  def interruptAllActive(self):
    global activeProcesses
    for (n, p) in activeProcesses.iteritems():
      try:
        p.interrupt()
      except:
        # process already ended
        pass

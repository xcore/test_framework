from xmos.test.process import *
from xmos.test.base import *

class Master():
  def __init__(self):
    self.timeout = None
    self.deferred = None
    self.expected = []
    self.nextExpected = []

  def printState(self, message):
    # Add a blank line before
    log_debug("")

    log_debug(message)
    for (i,e) in enumerate(self.expected):
      log_debug("%d: Indexes %s" % (i,
            ", ".join(["%s:%s" % (p, activeProcesses[p].getHistoryIndex(i)) for p in e.getProcesses()])))
      log_debug("%s" % e)

    # Add a blank line after
    log_debug("")

  def checkReceived(self, process, string):
    """ Check one process and string against the expected values,
      remove it if found.
    """
    assert self.expected
    result = ExpectedResult(completed=True)
    nextExpected = []
    consumed = False
    for (i,e) in enumerate(self.expected):
      if consumed:
        result.completed = False
        nextExpected += [e]

      else:
        eventResult = e.completes(process, string)
        result.started |= eventResult.started
        result.timedout |= eventResult.timedout

        if eventResult.consume:
          # Only allow one process to match this string
          activeProcesses[process].consume(string)
          consumed = True

        if (eventResult.completed or eventResult.started) and process in activeProcesses:
          activeProcesses[process].moveHistoryIndex(i, string)

        if eventResult.completed:
          # Need to keep something so that the indexes are not changed
          nextExpected += [AllOf([])]
        else:
          result.completed = False
          nextExpected += [e]

    if result.completed:
      self.expected = []
    else:
      self.expected = nextExpected

    if result.completed or result.started:
      self.printState("Events remaining:")

    return result

  def checkAgainstHistory(self):
    """ Check through the existing process data history to
      see whether the expected has already been seen.
    """
    changed = True
    while changed:
      changed = False
      for (i,e) in enumerate(self.expected):
        for process in e.getProcesses():
          for data in activeProcesses[process].getExpectHistory(i):
            log_debug("checkAgainstHistory: %s: %s" % (process, data.strip()))
            result = self.checkReceived(process, data)
            changed |= result.started and not result.completed
            if not self.expected:
              return

  def clearExpectHistory(self, process):
    activeProcesses[process].clearExpectHistory()

  def addExpected(self, expected):
    if expected:
      self.nextExpected += [expected]

  def startNext(self):
    self.expected = self.nextExpected
    self.nextExpected = []

  def expect(self, expected=None):
    if expected:
      self.expected = [expected]

    # If there is nothing to expect then just continue
    if not self.expected:
      return []

    self.printState("Master expect:")

    self.checkAgainstHistory()

    # If the expected has already been met (self.expected == None)
    # then simply return and the test will continue
    if not self.expected:
      return self.expected

    for e in self.expected:
      e.registerTimeouts(self)

    # Create a deferred to return while we wait
    self.deferred = Deferred()
    return self.deferred

  def sendLine(self, process, command):
    activeProcesses[process].sendLine(command)

  def receive(self, process, string):
    if self.expected:
      result = self.checkReceived(process, string)
      if result.started and not result.completed:
        self.checkAgainstHistory()

    if not self.expected:
      self.callDeferred()

  def timedOut(self, done):
    """ We've seen one timeout, clear all other pending ones and continue
    """
    assert self.expected

    if done:
      for e in self.expected:
        e.cancelTimeouts()
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

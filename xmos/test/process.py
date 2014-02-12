from twisted.internet import protocol
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, Deferred
import re
import os
import datetime
from xmos.test.base import *
from xmos.test.xmos_logging import *

""" Global list of all known entities
"""
entities = {}

def getEntities():
  return entities

def chomp(s):
  """ Remove any trailing newline characters
  """
  return s.rstrip('\n')


class Process(protocol.ProcessProtocol):
  full_line = ''

  def __init__(self, name, master, errorFn=testError,
               criticalErrors=None, **kwargs):
    if criticalErrors == None:
      criticalErrors = defaultToCriticalFailure
    self.name = name
    self.master = master

    # History of all lines received from this process - can be cleared by master
    self.output_history = []

    # Map of expected index to current index into the history
    self.history_indexes = {}

    self.error_patterns = set()
    self.output_file = None
    self.errorFn = errorFn
    self.criticalErrors = criticalErrors

    if 'output_file' in kwargs:
      self.output_file = open(kwargs['output_file'], 'w')

    # Ensure there are no two processes created with the same name
    assert self.name not in activeProcesses

    activeProcesses[self.name] = self

  def log(self, message, level='debug'):
    """ Log to the process log and to the full log.
    """
    now = datetime.datetime.now()
    if level is not None:
      eval('log_%s' % level)("%s: %s: %s" % (now.time(), self.name, message.strip()))
    if self.output_file:
      self.output_file.write("%s: %s\n" % (now.time(), message.strip()))
      self.output_file.flush()
      os.fsync(self.output_file.fileno())

  def connectionMade(self):
    self.log("connection made\n")

  def inConnectionLost(self):
    log_debug("%s: stdin is closed!" % self.name)

  def outConnectionLost(self):
    log_debug("%s: The child closed their stdout" % self.name)

  def errConnectionLost(self):
    log_debug("%s: The child closed their stderr" % self.name)

  def processExited(self, reason):
    if reason.value.exitCode:
      log_debug("%s: process exited, status %d" % (self.name, reason.value.exitCode))
    else:
      log_debug("%s: process exited, no exit code" % (self.name))

  def processEnded(self, reason):
    if reason.value.exitCode:
      log_debug("%s: process ended, status %d" % (self.name, reason.value.exitCode))
    else:
      log_debug("%s: process ended, no exit code" % (self.name))

  def outReceived(self, data):
    self.errReceived(data)

  def errReceived(self, data):

    newlines_and_oldlines = self.full_line + data

    lines = newlines_and_oldlines.splitlines(True)

    for i, line in enumerate(lines):
      if line.endswith('\n'):
        self.log(line)
        self.output_history.append(line)

        # Need to check error pattern before calling master as the master may change
        # the active error patterns
        self.checkErrorPatterns(line)

        self.master.receive(self.name, line)

        # If the last line in the list ends with a newline, we do not need to carry over
        # any output to the next comparison
        if (i == len(lines)-1):
          self.full_line = ''

      elif i == len(lines)-1:
        self.full_line += lines[-1]

  def getHistoryIndex(self, expect_index):
    return self.history_indexes.get(expect_index, 0)

  def setHistoryIndex(self, expect_index, history_index):
    self.history_indexes[expect_index] = history_index

  def getExpectHistory(self, expect_index):
    """ Build up a copy so that there are no iteration issues
       when the history is pruned by a process checking the
      history.
    """
    history_index = self.getHistoryIndex(expect_index)
    return [h for h in self.output_history[history_index:]]

  def moveHistoryIndex(self, expect_index, data):
    """ Return index of entry after matching entry
    """
    history_index = self.getHistoryIndex(expect_index)
    history = self.output_history[history_index:]
    if data in history:
      self.setHistoryIndex(expect_index, history_index + history.index(data) + 1)
    else:
      self.setHistoryIndex(expect_index, len(self.output_history))

  def clearExpectHistory(self):
    """ Clear the entire history of values seen
    """
    self.log("CLEAR HISTORY", level=None)
    self.output_history[:] = []
    self.history_indexes = {}

  def sendLine(self, command):
    """ Send a given command to a process
    """
    self.log("send: '%s'" % command, level='info')
    self.transport.write(command + '\r\n')

  def checkErrorPatterns(self, data):
    for (pattern, errorFn, critical) in self.error_patterns:
      if matchesPattern(pattern, data):
        errorFn("found %s: %s" % (self.name, data), critical=critical)

  def registerErrorPattern(self, pattern, errorFn=None, critical=None):
    if errorFn is None:
      errorFn = self.errorFn
    if critical is None:
      critical = self.criticalErrors
    log_debug("%s: registering error pattern '%s'" % (self.name, pattern))
    self.error_patterns.add((pattern, errorFn, critical))
    self.printErrorPatterns()

  def unregisterErrorPattern(self, pattern):
    """ Remove error patterns which match the specified pattern
    """
    log_debug("%s: unregistering error pattern '%s'" % (self.name, pattern))
    self.error_patterns = set([ (p,e,c) for (p,e,c) in self.error_patterns if p != pattern ])
    self.printErrorPatterns()

  def printErrorPatterns(self):
    prefix = "\n  %s: " % self.name
    log_debug("%s: error patterns now:%s%s" % (self.name, prefix,
         prefix.join([ p for (p,e,c) in self.error_patterns ])))

  def kill(self):
    self.transport.signalProcess('KILL')

  def interrupt(self):
    self.transport.signalProcess('INT')


class XrunProcess(Process):
  def __init__(self, name, master, **kwargs):
    Process.__init__(self, name, master, **kwargs)
    self.registerErrorPattern("xrun: Problem", critical=True)
    self.registerErrorPattern("xrun: Executable file", critical=True) # does not exist
    self.registerErrorPattern("xrun: ID is incorrect", critical=True)
    self.registerErrorPattern("xrun: No available devices", critical=True)
    self.registerErrorPattern("xrun: The selected adapter is not connected", critical=True)


class ControllerProcess(Process):
  def __init__(self, name, master, **kwargs):
    Process.__init__(self, name, master, **kwargs)

  def outReceived(self, data):
    m = re.search("Found \d+ entities", data)
    if m:
      entities.clear()
      lines = data.split()
      for line in lines:
        if line.startswith("0x"):
          try:
            entities[int(line, 16)] = 1
          except Exception, e:
            pass
    Process.outReceived(self, data)


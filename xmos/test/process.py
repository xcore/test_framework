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

  def __init__(self, name, master, errorFn = testError,
               criticalErrors = None, **kwargs):
    if criticalErrors == None:
      criticalErrors = defaultToCriticalFailure
    self.name = name
    self.master = master
    self.output_history = []
    self.error_patterns = set()
    self.output_file = None
    self.errorFn = errorFn
    self.criticalErrors = criticalErrors

    if 'output_file' in kwargs:
      self.output_file = open(kwargs['output_file'], 'w')

    # Ensure there are no two processes created with the same name
    assert self.name not in activeProcesses

    activeProcesses[self.name] = self

  def log(self, message):
    """ Log to the process log and to the full log.
    """
    now = datetime.datetime.now()
    log_debug("%s: %s: %s" % (now.time(), self.name, message))
    if self.output_file:
      self.output_file.write("%s: %s" % (now.time(), message))
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

  def getExpectHistory(self):
    """ Build up a copy so that there are no iteration issues
       when the history is pruned by a process checking the
      history.
    """
    return [h for h in self.output_history]

  def pruneExpectHistory(self, data):
    """ Prune up to and including the data value passed
    """
    while self.output_history and self.output_history[0] != data:
      self.output_history.pop(0)

    if self.output_history:
      self.output_history.pop(0)

  def clearExpectHistory(self):
    """ Clear the entire history of values seen
    """
    self.output_history[:] = []

  def sendLine(self, command):
    """ Send a given command to a process
    """
    self.log("Send: '%s'" % command)
    log_info("Send: '%s'" % command)
    self.transport.write(command + '\r\n')

  def checkErrorPatterns(self, data):
    for (pattern, errorFn) in self.error_patterns:
      if matchesPattern(pattern, data):
        errorFn("found %s: %s" % (self.name, data), self.criticalErrors)

  def registerErrorPattern(self, pattern, errorFn=None):
    if not errorFn:
      errorFn = self.errorFn
    self.error_patterns.add((pattern, errorFn))

  def kill(self):
    self.transport.signalProcess('KILL')

  def interrupt(self):
    self.transport.signalProcess('INT')


class XrunProcess(Process):
  def __init__(self, name, master, **kwargs):
    Process.__init__(self, name, master, **kwargs)
    self.registerErrorPattern("xrun: Problem")
    self.registerErrorPattern("xrun: Executable file") # does not exist
    self.registerErrorPattern("xrun: ID is incorrect")
    self.registerErrorPattern("xrun: No available devices")


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


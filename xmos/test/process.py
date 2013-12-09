from twisted.internet import protocol
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, Deferred
import re
import os
import datetime
from xmos.test.base import *

""" Global list of all known entities
"""
entities = {}

def chomp(s):
  """ Remove any trailing newline characters
  """
  return s.rstrip('\n')


class Process(protocol.ProcessProtocol):
  full_line = ''

  def __init__(self, name, master, **kwargs):
    self.name = name
    self.master = master
    self.output_history = []
    self.error_patterns = set()
    self.verbose = False
    self.output_file = None

    if 'verbose' in kwargs:
      self.verbose = kwargs['verbose']

    if 'output_file' in kwargs:
      self.output_file = open(kwargs['output_file'], 'w')

    # Ensure there are no two processes created with the same name
    assert self.name not in activeProcesses

    activeProcesses[self.name] = self

  def log(self, message):
    """ Log either to a file or to the console. When logging to the console
      then add the process name as a prefix
    """
    now = datetime.datetime.now()
    if self.output_file:
      self.output_file.write("%s: %s" % (now.time(), message))
      self.output_file.flush()
      os.fsync(self.output_file.fileno())
    else:
      sys.stdout.write("%s: %s: %s" % (now.time(), self.name, message))
      sys.stdout.flush()

  def connectionMade(self):
    self.log("connection made\n")

  def inConnectionLost(self):
#    print "%s: stdin is closed!" % self.name
    pass

  def outConnectionLost(self):
#    print "%s: The child closed their stdout" % self.name
    pass

  def errConnectionLost(self):
#    print "%s: The child closed their stderr" % self.name
    pass
    
  def processExited(self, reason):
#    print "%s: process exited, status %d" % (self.name, reason.value.exitCode)
    pass

  def processEnded(self, reason):
#    print "%s: process ended, status %d" % (self.name, reason.value.exitCode)
    pass

  def outReceived(self, data):
    self.errReceived(data)

  def errReceived(self, data):

    newlines_and_oldlines = self.full_line + data

    lines = newlines_and_oldlines.splitlines(True)

    for i, line in enumerate(lines):
      if line.endswith('\n'):

        if self.verbose or self.output_file:
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
    if self.verbose:
      self.log("Send: '%s'" % command)

    print "Send: '%s'" % command
    self.transport.write(command + '\r\n')

  def checkErrorPatterns(self, data):
    for pattern in self.error_patterns:
      if matchesPattern(pattern, data):
        testError("found %s: %s" % (self.name, data), True)

  def registerErrorPattern(self, pattern):
    self.error_patterns.add(pattern)


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


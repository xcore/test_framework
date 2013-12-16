from twisted.internet import reactor
import argparse
import functools
import os
import re
import sys
import signal
import string

""" Global list of all active processes
"""
activeProcesses = {}

def getActiveProcesses():
  return activeProcesses

def file_abspath(filename):
  """ Given a search path, find whether a file exists
  """
  paths = string.split(os.environ['PATH'], os.pathsep)
  for path in paths:
    if os.path.exists(os.path.join(path, filename)):
      return os.path.abspath(os.path.join(path, filename))

  return None

def exe_name(filename):
  if sys.platform.startswith("win"):
    return filename + ".exe"
  else:
    return filename

def testShutdown():
  """ Shutdown all child processes by closing stdin/out/err
    and then killing the process tree to ensure child processes
    are killed.
  """
  for name,process in getActiveProcesses().iteritems():
    if (process.transport):
      process.transport.loseConnection()

  if sys.platform.startswith("win"):
    import psutil
    parent = psutil.Process(os.getpid())
    for child in parent.get_children(recursive=True):
      child.kill()
    parent.kill()

  else:
    """ Ensure that all sub-processes are killed on exit
    """
    print "Exiting - killing all child processes"
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    os.kill(-os.getpgid(os.getpid()), signal.SIGINT)

def matchesPattern(pattern, string):
  m = re.search(pattern, string)
  if m:
    return True
  else:
    return False

def matches(expect_process, pattern, process, string):
  if process != expect_process:
    return False

  return matchesPattern(pattern, string)

def testError(reason="", critical=False):
  test_state.error_count += 1
  print "Error: %s " % reason
  if critical and test_state.reactor_running:
    test_state.reactor_running = False
    reactor.stop()
class reprwrapper(object):
  """ A wrapper class so that functions can control their __repr__ output
  """
  def __init__(self, reprfun, func):
    self._reprfun = reprfun
    self._func = func
    functools.update_wrapper(self, func)
  def __call__(self, *args, **kw):
    return self._func(*args, **kw)
  def __repr__(self):
    return self._reprfun(self._func)

def withrepr(reprfun):
    def _wrap(func):
        return reprwrapper(reprfun, func)
    return _wrap

@withrepr(lambda x: "%s" % x.__name__)
def testTimeout(process, pattern, timeout):
  """ Timeout functions return whether or not they should complete the current expected.
    Errors should return true.
  """
  testError("timeout after waiting %.1f for %s: '%s'" % (timeout, process, pattern), True)
  return True

@withrepr(lambda x: "%s" % x.__name__)
def testTimeoutPassed(process, pattern, timeout):
  """ Timeout functions return whether or not they should complete the current expected.
    Expected timeouts can be ignored.
  """
  print "Success: %s: %s not seen in %.1f seconds" % (process, pattern, timeout)
  return False

@withrepr(lambda x: "%s" % x.__name__)
def testTimeoutIgnore(process, pattern, timeout):
  """ Timeout functions return whether or not they should complete the current expected.
    Expected timeouts can be ignored.
  """
  print "Ignoring: %s: %s not seen in %.1f seconds" % (process, pattern, timeout)
  return False

def testStart(testFunction, args):
  test_config.verbose = args.verbose
  test_state.stopped = False

  # Register a callback to ensure that all processes are killed before exiting
  reactor.addSystemEventTrigger('before', 'shutdown', testShutdown)

  # Register test program to run on startup
  reactor.callWhenRunning(testFunction, args)
  test_state.reactor_running = True
  reactor.run()

def testComplete(reactor):
  if test_state.error_count > 0:
    print "Test failed with %d errors" % test_state.error_count
  else:
    print "Test passed"
  if test_state.reactor_running:
    test_state.reactor_running = False
    reactor.stop()


class TestConfig(object):
  """ Test Configuration:
  """

  """ prune_on_match: when set (default) then matches in the expect history
            cause the history to be pruned up until that point
            so that it can't be matched again. Sometimes when the
            order doesn't matter then the pruning needs to be
            disabled
  """
  prune_on_match = True

  """ verbose: when set will cause increased debug messages to be printed
  """
  verbose = False

class TestState(object):
  """ Keep track of test state as it runs. Currently this is:
      - number of errors seen
  """
  error_count = 0

  """ Keep track of whether the reactor is running to prevent it being stopped
    more than once.
  """
  reactor_running = False


class Waitable(object):

  def getProcesses(self):
    raise NotImplementedError("Should have implemented this")

  def registerTimeouts(self, master):
    raise NotImplementedError("Should have implemented this")

  def completes(self, process, string):
    raise NotImplementedError("Should have implemented this")

  def cancelTimeouts(self):
    raise NotImplementedError("Should have implemented this")


class SetBasedWaitable(Waitable):
  def __init__(self, name, l):
    self.name = name
    self.s = set(l)

  def getProcesses(self):
    processes = set()
    for event in self.s:
      processes |= event.getProcesses()
    return processes

  def registerTimeouts(self, master):
    assert self.s

    for event in self.s:
      event.registerTimeouts(master)

  def cancelTimeouts(self):
    for event in self.s:
      event.cancelTimeouts()

  def __repr__(self):
    return "%s(%s)" % (self.name, ", ".join(str(item) for item in self.s))


class Expected(Waitable):

  def __init__(self, process, pattern, timeout_time=0, func=testTimeout):
    self.process = process
    self.pattern = pattern
    self.timeout = None
    self.timeout_time = timeout_time
    self.func = func
    self.timedout = False

  def getProcesses(self):
    return set([self.process])

  def registerTimeouts(self, master):
    if self.timeout_time > 0:
      if test_config.verbose:
        print "Register timeout %s: %s %.1f" % (self.process, self.pattern, self.timeout_time)
      self.timeout = reactor.callLater(self.timeout_time, self.timedOut)
      self.master = master

  def cancelTimeouts(self):
    if self.timeout:
      if test_config.verbose:
        print "Cancel timeout %s: %s" % (self.process, self.pattern)
      self.timeout.cancel()
      self.timeout = None

  def completes(self, process, string):
    """ Returns whether an event was completed, started or timedout
    """
    if self.timedout:
      return (False, False, True)

    if matches(self.process, self.pattern, process, string):
      self.cancelTimeouts()
      print "Success: seen match for %s: %s" % (self.process, self.pattern)
      return (True, True, False)

    return (False, False, False)

  def timedOut(self):
    assert self.timeout

    # Call the function registered for timeouts
    done = self.func(self.process, self.pattern, self.timeout_time)

    # Remove the timeout so that we don't try to cancel it when it has fired
    self.timeout = None
    self.timedout = True

    self.master.timedOut(done)

  def __repr__(self):
    return "%s: '%s' %d(%s) %s" % (
        self.process, self.pattern, self.timeout_time, self.timedout, self.func.__repr__()
      )


class AllOf(SetBasedWaitable):
  def __init__(self, l):
    """ Takes a list of events that all have to be completed
    """
    super(AllOf, self).__init__('AllOf', l)

  def completes(self, process, string):
    """ Finds if there is one of the entries which completes the match
      and then removes that entry from the list if it is found.
      Considered complete if the list is now empty.

      Returns whether an event was completed, started or timedout.
    """
    started = False
    timedout = False
    for event in self.s:
      (event_completed, event_started, event_timedout) = event.completes(process, string)
      started |= event_started
      timedout |= event_timedout

      if event_completed or event_timedout:
        self.s.remove(event)

      if event_completed or event_started or event_timedout:
        break

    completed = not self.s
    return (completed, started, timedout)


class OneOf(SetBasedWaitable):
  def __init__(self, l):
    """ Takes a list of events of which only one has to be completed
    """
    super(OneOf, self).__init__('OneOf', l)

  def completes(self, process, string):
    """ Finds if there is one of the entries which completes or starts
      the match. If one starts the match then remove all other entries
      as they are no longer relevant. If it completes then remove all
      entries.
      Considered complete if the list is now empty.

      Returns whether an event was completed, started or timedout.
    """
    started = False
    timedout = False
    to_remove = set()
    for event in self.s:
      (event_completed, event_started, event_timedout) = event.completes(process, string)
      started |= event_started
      timedout |= event_timedout

      if event_completed or event_timedout:
        to_remove |= self.s
        break

      if event_started:
        to_remove |= self.s - set([event])
        break

    # Update the contents of the set and cancel timeouts from all events being removed.
    self.s -= to_remove
    for event in to_remove:
      event.cancelTimeouts()

    completed = not self.s
    return (completed, started, timedout)


class NoneOf(SetBasedWaitable):
  def __init__(self, l):
    """ Takes a list of events which should not be seen. Their timeout
      functions need to be changed to not be errors.
    """
    super(NoneOf, self).__init__('NoneOf', l)
    for event in self.s:
      event.func = testTimeoutPassed

  def completes(self, process, string):
    """ Finds if there is one of the entries which completes or starts
      the match. If so, then an error has occured and the event can
      be considered complete.
    """
    to_remove = set()
    for event in self.s:
      (event_completed, event_started, event_timedout) = event.completes(process, string)

      if event_completed or event_started:
        testError("Seen NoneOf event %s:\n   Pattern: %s\n   Actual: %s" % (event.process, event.pattern, string))
        self.cancelTimeouts()
        self.s.clear()
        break

      if event_timedout:
        to_remove |= set([event])

    # Update the contents of the set and cancel timeouts from all events being removed.
    self.s -= to_remove
    for event in to_remove:
      event.cancelTimeouts()

    completed = not self.s
    return (completed, completed, False)


class Sequence(object):
  def __init__(self, l):
    """ Takes a list of events which must complete in order
    """
    self.l = l
    self.master = None

  def getProcesses(self):
    processes = set()
    for event in self.l:
      processes |= event.getProcesses()
    return processes

  def registerTimeouts(self, master):
    self.master = master

    assert self.l
    self.l[0].registerTimeouts(master)

  def cancelTimeouts(self):
    if self.l:
      self.l[0].cancelTimeouts()

  def completes(self, process, string):
    """ Finds if the first entry starts or completes. If it completes then
      it is removed.
      Considered complete if the list is now empty.
    """
    assert self.l

    (event_completed, started, event_timedout) = self.l[0].completes(process, string)

    if event_completed:
      self.l[0].cancelTimeouts()

    if event_completed or event_timedout:
      self.l.pop(0)

      if self.l and self.master:
        # Enable time out of the next event in the sequence
        self.l[0].registerTimeouts(self.master)

    completed = not self.l

    # If the last event completed then return whether that was due to a timeout.
    # Otherwise the sequence hasn't timedout yet.
    timedout = event_timedout if completed else False
    return (completed, started, timedout)

  def __repr__(self):
    return "Sequence(%s)" % " -> ".join(str(item) for item in self.l)


test_state = TestState()
test_config = TestConfig()

def getParser():
  parser = argparse.ArgumentParser(description='Automated test')
  parser.add_argument('--verbose', dest='verbose',
      action='store_true', help='enable verbose mode')
  return parser

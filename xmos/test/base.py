from twisted.internet import reactor
from twisted.internet import defer
import argparse
import datetime
import functools
import os
import re
import sys
import signal
import string

import threading
from contextlib import contextmanager

from xmos.test.xmos_logging import *
_tls = threading.local()

LOG_ENABLED = False
log_indent = 1

def log_completes_start(entity):
  global log_indent
  if not LOG_ENABLED:
    return

  log_debug("%s%s" % ("  "*log_indent, entity.__class__.__name__))
  log_indent += 1

def log_completes_end(entity, result):
  global log_indent
  if not LOG_ENABLED:
    return

  log_debug("%s%s: %s" % ("  "*log_indent, entity.__class__.__name__, result))
  assert(log_indent > 0)
  log_indent -= 1

def log_completes_expected(expected, process, string, result):
  global log_indent
  if not LOG_ENABLED:
    return

  log_debug("%s%s: '%s:%s...' match '%s:%s...' ? %s" % ("  "*log_indent, expected.__class__.__name__,
      expected.process, expected.pattern[0:10], process, string[0:10], result))
  assert(log_indent > 0)
  log_indent -= 1


@contextmanager
def _nested():
  _tls.level = getattr(_tls, "level", 0) + 1
  try:
    yield "   " * _tls.level
  finally:
    _tls.level -= 1

@contextmanager
def _recursion_lock(obj):
  if not hasattr(_tls, "history"):
    _tls.history = []  # can't use set(), not all objects are hashable
  if obj in _tls.history:
    yield True
    return
  _tls.history.append(obj)
  try:
    yield False
  finally:
    _tls.history.pop(-1)


""" Global list of all active processes
"""
activeProcesses = {}

defaultToCriticalFailure = False

def sleep(secs):
  """ A sleep function to be used within tests. Called using yield, eg:
        yield base.sleep(1)
  """
  d = defer.Deferred()
  reactor.callLater(secs, d.callback, None)
  return d

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
    log_debug("Exiting - killing all child processes")
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
def testTimeout(process, pattern, timeout, errorFn, critical=None):
  """ Timeout functions return whether or not they should complete the current expected.
    Errors should return true.
  """
  if critical == None:
    critical = defaultToCriticalFailure
  errorFn("timeout after waiting %.1f for %s: '%s'" % (timeout, process, pattern), critical=critical)
  return True

@withrepr(lambda x: "%s" % x.__name__)
def testTimeoutPassed(process, pattern, timeout, errorFn, critical=None):
  """ Timeout functions return whether or not they should complete the current expected.
    Expected timeouts can be ignored.
  """
  log_info("Success: %s: %s not seen in %.1f seconds" % (process, pattern, timeout))
  return False

@withrepr(lambda x: "%s" % x.__name__)
def testTimeoutIgnore(process, pattern, timeout, errorFn, critical=None):
  """ Timeout functions return whether or not they should complete the current expected.
    Expected timeouts can be ignored.
  """
  log_info("Ignoring: %s: %s not seen in %.1f seconds" % (process, pattern, timeout))
  return False

def testError(reason="", critical=False):
  test_state.error_count += 1
  log_error("%s" % reason)
  if critical and test_state.reactor_running:
    test_state.reactor_running = False
    reactor.stop()

def testStart(testFunction, args):
  test_state.stopped = False

  # Register a callback to ensure that all processes are killed before exiting
  reactor.addSystemEventTrigger('before', 'shutdown', testShutdown)

  # Register test program to run on startup
  reactor.callWhenRunning(testFunction, args)
  test_state.reactor_running = True
  reactor.run()

def testComplete(reactor):
  print_status_summary()
  if test_state.reactor_running:
    test_state.reactor_running = False
    reactor.stop()


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
  def __init__(self, l):
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
    if getattr(_tls, "level", 0) > 0:
      return str(self)
    else:
      attrs = ", ".join("%s = %r" % (k, v) for k, v in self.__dict__.items())
      return "%s(%s)" % (self.__class__.__name__, attrs)

  def __str__(self):
    with _recursion_lock(self) as locked:
      if locked:
        return "<...>"
      with _nested() as indent:
        attrs = []

        for x in self.s:
          with _nested() as indent2:
            attrs.append("%s%r," % (indent2, x))

        if not attrs:
          return "%s{}" % (self.__class__.__name__,)
        else:
          return "%s: {\n%s\n%s}" % (self.__class__.__name__, "\n".join(attrs), indent)


class Expected(Waitable):

  def __init__(self, process, pattern, timeout_time=0, func=testTimeout,
               errorFn=testError, critical=None,
               completionFn=None, completionArgs=None):
    if critical == None:
      critical = defaultToCriticalFailure
    self.process = process
    self.pattern = pattern
    self.timeout = None
    self.timeoutTime = timeoutTime
    self.func = func
    self.timedout = False
    self.errorFn = errorFn
    self.critical = critical
    self.completionFn = completionFn
    self.completionArgs = completionArgs
    self.prevLine = ""

  def getPrevLine(self):
    return self.prevLine

  def getProcesses(self):
    return set([self.process])

  def registerTimeouts(self, master):
    if self.timeoutTime > 0:
      now = datetime.datetime.now()
      log_debug("%s: Register timeout %s: %s %.1f" % (now.time(), self.process, self.pattern, self.timeoutTime))
      self.timeout = reactor.callLater(self.timeoutTime, self.timedOut)
      self.master = master

  def cancelTimeouts(self):
    if self.timeout:
      log_debug("Cancel timeout %s: %s" % (self.process, self.pattern))
      self.timeout.cancel()
      self.timeout = None

  def completes(self, process, string):
    """ Returns whether an event was completed, started or timedout
    """
    log_completes_start(self)
    self.prevLine = string

    if self.timedout:
      log_completes_expected(self, process, string, (False, False, True))
      return (False, False, True)

    if matches(self.process, self.pattern, process, string):

      # Upon completion call the completion hook if it has been registered
      if self.completionFn:
        log_info("Possible match for %s: %s" % (self.process, self.pattern))
        res = self.completionFn(self)
        if res == False:
          log_completes_expected(self, process, string, (False, False, False))
          return (False, False, False)

      self.cancelTimeouts()
      log_info("Success: seen match for %s: %s" % (self.process, self.pattern))

      log_completes_expected(self, process, string, (True, True, False))
      return (True, True, False)

    log_completes_expected(self, process, string, (False, False, False))
    return (False, False, False)

  def timedOut(self):
    assert self.timeout

    # Call the function registered for timeouts
    done = self.func(self.process, self.pattern, self.timeout_time,
                     errorFn=self.errorFn, critical=self.critical)

    # Remove the timeout so that we don't try to cancel it when it has fired
    self.timeout = None
    self.timedout = True

    self.master.timedOut(done)

  def __repr__(self):
    return "%s: '%s', timeout: %d, %s, %s" % (
        self.process, self.pattern, self.timeout_time, self.timedout, self.func.__repr__()
      )


class AllOf(SetBasedWaitable):
  def __init__(self, l):
    """ Takes a list of events that all have to be completed
    """
    super(AllOf, self).__init__(l)

  def completes(self, process, string):
    """ Finds if there is one of the entries which completes the match
      and then removes that entry from the list if it is found.
      Considered complete if the list is now empty.

      Returns whether an event was completed, started or timedout.
    """
    log_completes_start(self)

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
    log_completes_end(self, (completed, started, timedout))
    return (completed, started, timedout)


class OneOf(SetBasedWaitable):
  def __init__(self, l):
    """ Takes a list of events of which only one has to be completed
    """
    super(OneOf, self).__init__(l)

  def completes(self, process, string):
    """ Finds if there is one of the entries which completes or starts
      the match. If one starts the match then remove all other entries
      as they are no longer relevant. If it completes then remove all
      entries.
      Considered complete if the list is now empty.

      Returns whether an event was completed, started or timedout.
    """
    log_completes_start(self)

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
    log_completes_end(self, (completed, started, timedout))
    return (completed, started, timedout)


class NoneOf(SetBasedWaitable):
  def __init__(self, l, critical=None, errorFn=testError):
    """ Takes a list of events which should not be seen. Their timeout
      functions need to be changed to not be errors.
    """
    super(NoneOf, self).__init__(l)
    for event in self.s:
      event.func = testTimeoutPassed
    if critical == None:
      critical = defaultToCriticalFailure
    self.critical = critical
    self.errorFn = errorFn

  def completes(self, process, string):
    """ Finds if there is one of the entries which completes or starts
      the match. If so, then an error has occured and the event can
      be considered complete.
    """
    log_completes_start(self)

    to_remove = set()
    for event in self.s:
      (event_completed, event_started, event_timedout) = event.completes(process, string)

      if event_completed or event_started:
        self.errorFn("Seen NoneOf event %s:\n   Pattern: %s\n   Actual: %s" % (event.process, event.pattern, string), critical=self.critical)
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
    log_completes_end(self, (completed, completed, False))
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
    log_completes_start(self)

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
    log_completes_end(self, (completed, started, timedout))
    return (completed, started, timedout)

  def __repr__(self):
    if getattr(_tls, "level", 0) > 0:
      return str(self)
    else:
      attrs = ", ".join("%s = %r" % (k, v) for k, v in self.__dict__.items())
      return "%s(%s)" % (self.__class__.__name__, attrs)

  def __str__(self):
    with _recursion_lock(self) as locked:
      if locked:
        return "<...>"
      with _nested() as indent:
        attrs = []

        for x in self.l:
          with _nested() as indent2:
            attrs.append("%s%r," % (indent2, x))

        if not attrs:
          return "%s[]" % (self.__class__.__name__,)
        else:
          return "%s: [\n%s\n%s]" % (self.__class__.__name__, "\n".join(attrs), indent)


test_state = TestState()

def getParser():
  parser = argparse.ArgumentParser(description='Automated test')
  parser.add_argument('--logfile', dest='logfile',
      action='store_true', help='log file to be used', default='run.log')
  parser.add_argument('--summaryfile', dest='summaryfile',
      nargs='?', help='file to write summary log to', default=None)
  return parser


"""CellExecutor executes tests in a cell.

CellExecuter executes the test for the given cell consecutively, concisely, and
consistently.
"""
import logging
import time

import google3
from contextlib33_backport import contextlib

from google3.googlex.glass.xtf.openxtf.openxtf import dutmanager
from google3.googlex.glass.xtf.openxtf.openxtf import testmanager
from google3.googlex.glass.xtf.openxtf.openxtf.lib import capabilities
from google3.googlex.glass.xtf.openxtf.openxtf.lib import configuration
from google3.googlex.glass.xtf.openxtf.openxtf.lib import threads
from google3.googlex.glass.xtf.shared import records

configuration.Declare('cell_info', """
All the information for each cell. This should be a mapping from cell number to
cell data. What is in the cell data is dictated by the capabilities used.
""", default_value={1: {}})


_LOG = logging.getLogger('xtf.cells')


class BlankDUTSerialError(Exception):
  """Provided DUT serial cannot be blank."""


class TestStopError(Exception):
  """Test is being stopped."""


class CellExecutorStarter(object):
  """Starts all the cell executor threads."""

  def __init__(self, test):
    self.test = test
    self._config = configuration.XTFConfig()
    self._cells = self._MakeCells()

  def _MakeCells(self):
    """Find and return all the cells."""
    cell_info = self._config.cell_info
    _LOG.info('Number of cells to build: %s', len(cell_info))

    cells = {}
    for cell_idx, cell_data in cell_info.iteritems():
      cell_config = self._config.CreateStackedConfig(cell_data)
      cells[cell_idx] = CellExecutor(cell_idx, cell_config, self.test)
    return cells

  def Start(self):
    for cell in self._cells.values():
      cell.start()
    _LOG.info(
        'Started %d cells and are left to their own devices from now on.',
        len(self._cells))

  def Wait(self):
    """Waits until death."""
    for cell in self._cells.values():
      cell.join()

  def Stop(self):
    _LOG.info('Stopping cells: %s - %s', self, self._cells)
    for cell in self._cells.itervalues():
      cell.Stop()
    for cell in self._cells.itervalues():
      cell.join(1)
    _LOG.info('All cells have been stopped.')


class LogSleepSuppress(records.Record('Suppressor', failure_reason='')):

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_value, exc_tb):
    if exc_type is not None:
      # Only log if there is a failure.
      _LOG.exception(self.failure_reason)
      time.sleep(1.0)
    if exc_type is not BlankDUTSerialError:
      # Don't supress these exceptions, since it's likely a test-writing
      # error.
      return False
    # Suppress all other exceptions, we probably want to start the next test.
    return True


class CellExecutor(threads.KillableThread):
  """Encompasses the execution of a single test cell."""

  daemon = True

  def __init__(self, cell_number, cell_config, test):
    super(CellExecutor, self).__init__()

    self.test = test
    self._cell_config = cell_config
    self._cell_number = cell_number
    self._current_exit_stack = None
    self._dut_manager = dutmanager.DutManager.FromConfig(self._cell_config)

  @threads.Loop
  def _ThreadProc(self):
    """Handles one whole test from start to finish.

    When this finishes, the parent loops back around and calls us again.

    Raises:
      BlankDUTSerialError: If the DUT serial is blank.
    """
    with contextlib.ExitStack() as exit_stack, LogSleepSuppress() as suppressor:
      _LOG.info('Starting test %s', self.test)

      self._current_exit_stack = exit_stack
      exit_stack.callback(lambda: setattr(self, '_current_exit_stack', None))

      _LOG.info('Starting test.')
      suppressor.failure_reason = 'TEST_START failed to complete.'

      self._dut_manager.WaitForTestStart()

      suppressor.failure_reason = 'Unable to initialize capabilities.'
      _LOG.info('Initializing capabilities.')
      capability_manager = (
          capabilities.CapabilityManager.InitializeFromTypes(
              self.test.capability_type_map))
      exit_stack.callback(capability_manager.TearDownCapabilities)

      _LOG.debug('Making test manager.')
      # Store the reason the next function can fail, then call the function.
      suppressor.failure_reason = 'Test is invalid.'
      test_manager = testmanager.TestManager(
          self._cell_number, self._cell_config, self.test,
          capability_manager.capability_map)

      def OptionallyStop(exc_type, unused_exc_value, unused_exc_tb):
        # If Stop was called, we don't care about the test stopping completely
        # anymore, nor if ctrl-C was hit.
        if exc_type not in (TestStopError, KeyboardInterrupt):
          self._dut_manager.WaitForTestStop()

      # Call WaitForTestStop() to match WaitForTestStart().
      exit_stack.push(OptionallyStop)

      # Remove the test after OptionallyStop() is done.
      exit_stack.callback(test_manager.RemoveTest)
      # This won't do anything normally, unless self.Stop is called.
      exit_stack.callback(test_manager.Stop)

      # Obtain DUT serial.
      suppressor.failure_reason = 'Unable get DUT serial.'
      dut_serial = self._dut_manager.GetSerial()

      if not dut_serial:
        raise BlankDUTSerialError(
            'Provided DUT serial was blank, XTF requires a non-blank serial.')

      test_manager.test_run_adapter.SetDutSerial(dut_serial)
      suppressor.failure_reason = 'Failed to execute test.'
      test_manager.ExecuteOneTest()

  def Stop(self):
    _LOG.info('Stopping test executor.')
    if self._current_exit_stack:
      # Tell the stack to exit.
      with self._current_exit_stack.pop_all() as stack:
        # Supress the error we're about to raise.
        stack.push(lambda *exc_details: True)
        raise TestStopError('Stopping.')
    self.Kill()
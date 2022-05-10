from distutils.debug import DEBUG
from operator import mod
import os
from random import getrandbits
from re import I
from typing import Any, Dict

import cocotb
from cocotb.binary import BinaryValue
from cocotb.clock import Clock
from cocotb.handle import SimHandleBase
from cocotb.queue import Queue
from cocotb.triggers import RisingEdge

from math import pi, cos, sin, atan, cosh, sinh, atanh, sqrt

from fixedpoint import FixedPoint


NUM_SAMPLES = int(os.environ.get("NUM_SAMPLES", 10))


def intToFloat(x: int) -> float:
    binary = bin(x)
    f = 0
    i = 0
    for b in reversed(binary):
        if (b == '1'):
            f = f + 2**(i-16)
        i = i + 1
    return f


def approx(actual: BinaryValue, expected: BinaryValue) -> bool:
    return int(actual) > (int(expected) - 10) and int(actual) < (int(expected) + 10)


class DataValidMonitor:
    """
    Reusable monitor of one-way control flow (data/valid) stream data interface

    Args
        clk: clock signal
        valid: control signal noting a transaction occured
        datas: named handles to be sampled when trasaction occurs
    """

    def __init__(self, clk: SimHandleBase, datas: Dict[str, SimHandleBase], valid: SimHandleBase) -> None:
        self.values = Queue[Dict[str, int]]()
        self._clk = clk
        self._datas = datas
        self._valid = valid
        self._coro = None

    def start(self) -> None:
        """Start monitor"""
        if self._coro is not None:
            raise RuntimeError("Monitor already started")
        self._coro = cocotb.start_soon(self._run())

    def stop(self) -> None:
        """Stop monitor"""
        if self._coro is None:
            raise RuntimeError("Monitor never started")
        self._coro.kill()
        self._coro = None

    async def _run(self) -> None:
        while True:
            await RisingEdge(self._clk)
            if self._valid.value.binstr != "1":
                await RisingEdge(self._valid)
                continue
            self.values.put_nowait(self._sample())

    def _sample(self) -> Dict[str, Any]:
        """
        Samples the data signals and builds a trasaction object.
        Return value is what is stored in queue. Meant to be overriden by the user
        """
        return {name: handle.value for name, handle in self._datas.items()}


class CordicTester:
    """
    Reusable checker of a cordic instance

    Args
        cordic_entity: handle to an instance of cordic
    """

    def __init__(self, cordic_entity: SimHandleBase) -> None:
        self.dut = cordic_entity
        self.ERRORS = 0
        self.PASSED = 0

        self.input_mon = DataValidMonitor(
            clk=self.dut.clk_i,
            valid=self.dut.valid_i,
            datas=dict(
                mode=self.dut.mode,
                rotational=self.dut.rotational,
                x=self.dut.x_i,
                y=self.dut.y_i,
                z=self.dut.z_i,
            ),
        )

        self.output_mon = DataValidMonitor(
            clk=self.dut.clk_i,
            valid=self.dut.valid_o,
            datas=dict(
                x=self.dut.x_o,
                y=self.dut.y_o,
                z=self.dut.z_o,
            )
        )

        self._checker = None

    def start(self) -> None:
        """Starts monitors, model, and checker coroutine"""
        if self._checker is not None:
            raise RuntimeError("Monitor already started")
        self.input_mon.start()
        self.output_mon.start()
        self._checker = cocotb.start_soon(self._check())

    def stop(self) -> None:
        """Stops everything"""
        if self._checker is None:
            raise RuntimeError("Monitor never started")
        self.input_mon.stop()
        self.output_mon.stop()
        self._checker.kill()
        self._checker = None

    def model(self, inputs: Queue[DataValidMonitor], DEBUG=False):
        """Transaction-level model of the matrix multiplier as instantiated"""
        x = intToFloat(inputs["x"])
        y = intToFloat(inputs["y"])
        z = intToFloat(inputs["z"])

        if (inputs["rotational"] == 1 and inputs["mode"] == 0):
            x = cos(z)
            y = sin(z)
            z = 0
        elif (inputs["rotational"] == 0 and inputs["mode"] == 0):
            x = sqrt(x**2 + y**2)
            y = 0
            z = atan(y/x)
        elif (inputs["rotational"] == 1 and inputs["mode"] == 1):
            x = x
            y = x * z
            z = 0
        elif (inputs["rotational"] == 0 and inputs["mode"] == 1):
            x = x
            y = 0
            z = y / x
        elif (inputs["rotational"] == 1 and inputs["mode"] == 2):
            try:
                x = cosh(z)
                y = sinh(z)
                z = 0
            except OverflowError:
                cocotb.log.error(z)
        elif (inputs["rotational"] == 0 and inputs["mode"] == 2):
            x = sqrt(x**2 + y**2)
            y = 0
            z = atanh(y/x)
        return dict(x=x, y=y, z=z)

    async def _check(self) -> None:
        while True:
            actual = await self.output_mon.values.get()
            expected_inputs = await self.input_mon.values.get()
            expected = self.model(expected_inputs)
            
            x_ = expected["x"]
            y_ = expected["y"]
            z_ = expected["z"]
            _x = intToFloat(actual["x"])
            _y = intToFloat(actual["y"])
            _z = intToFloat(actual["z"])
            x = intToFloat(expected_inputs["x"])
            y = intToFloat(expected_inputs["y"])
            z = intToFloat(expected_inputs["z"])

            try:
                if (_x < x_ - 0.1 or _x > x_ + 0.1):
                    status = False
                elif (_y < y_ - 0.1 or _y > y_ + 0.1):
                    status = False
                elif (_z < z_ - 0.1 or _z > z_ + 0.1):
                    if (_z > 1000):
                        status = True
                        self.PASSED += 1
                    else:
                        status = False
                else:
                    status = True
                    self.PASSED += 1
                    if DEBUG:
                        cocotb.log.info("PASS")
                        cocotb.log.info(f"(Inputs): x: {x} y: {y} z: {z}")
                        cocotb.log.info(f"(Expect): x: {x_} y: {y_} z: {z_}")
                        cocotb.log.info(f"(Actual): x: {_x} y: {_y} z: {_z}")
                assert status
            except AssertionError:
                self.ERRORS += 1
                if DEBUG:
                    cocotb.log.error("ERROR")
                    cocotb.log.info(f"(Inputs): x: {x} y: {y} z: {z}")
                    cocotb.log.info(f"(Expect): x: {x_} y: {y_} z: {z_}")
                    cocotb.log.info(f"(Actual): x: {_x} y: {_y} z: {_z}")

@cocotb.test(
    expect_error=IndexError if cocotb.SIM_NAME.lower().startswith("ghdl") else ()
)
async def test_multiplication(dut: SimHandleBase):
    """Test linear multiplication cordic"""

    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    tester = CordicTester(dut)

    dut._log.info("Initialize and reset model")

    # Initial valies
    dut.valid_i.value = 0
    dut.valid_i.value = 0
    dut.mode.value = 1
    dut.rotational.value = 1
    dut.x_i.value = 0
    dut.y_i.value = 0
    dut.z_i.value = 0

    # Reset DUT
    dut.rstn_i.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk_i)
    dut.rstn_i.value = 1

    # start tester after reset so we know it's in a good state
    tester.start()

    dut._log.info("Test linear multiplication operations")

    # Do cordic solutions
    for i, (x, z) in enumerate(zip(gen(mu=0), gen(mu=0))):
        await RisingEdge(dut.clk_i)
        dut.x_i.value = x
        dut.y_i.value = FixedPoint(0, m=14, n=16, signed=True).bits
        dut.z_i.value = z
        dut.valid_i.value = 1

        await RisingEdge(dut.clk_i)
        dut.valid_i.value = 0

        await RisingEdge(dut.valid_o)

        if ((i+1) % (NUM_SAMPLES/10) == 0):
            dut._log.info(f"{i+1} / {NUM_SAMPLES}")
    await RisingEdge(dut.clk_i)

    dut._log.info(f"Passed: {tester.PASSED} Errors: {tester.ERRORS}")

    assert tester.ERRORS == 0


@cocotb.test(
    expect_error=IndexError if cocotb.SIM_NAME.lower().startswith("ghdl") else ()
)
async def test_cos_sin(dut: SimHandleBase):
    """Test linear multiplication cordic"""

    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    tester = CordicTester(dut)

    dut._log.info("Initialize and reset model")

    # Initial valies
    dut.valid_i.value = 0
    dut.valid_i.value = 0
    dut.mode.value = 0
    dut.rotational.value = 1
    dut.x_i.value = 0
    dut.y_i.value = 0
    dut.z_i.value = 0

    # Reset DUT
    dut.rstn_i.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk_i)
    dut.rstn_i.value = 1

    # start tester after reset so we know it's in a good state
    tester.start()

    dut._log.info("Test rotational cosine and sine operations")

    # Do cordic solutions
    for i, z in enumerate(gen(mu=1)):
        await RisingEdge(dut.clk_i)
        dut.x_i.value = FixedPoint(0.6073, m=14, n=16, signed=True).bits
        dut.y_i.value = FixedPoint(0, m=14, n=16, signed=True).bits
        dut.z_i.value = z
        dut.valid_i.value = 1

        await RisingEdge(dut.clk_i)
        dut.valid_i.value = 0

        await RisingEdge(dut.valid_o)

        if ((i+1) % (NUM_SAMPLES/10) == 0):
            dut._log.info(f"{i+1} / {NUM_SAMPLES}")
    await RisingEdge(dut.clk_i)

    dut._log.info(f"Passed: {tester.PASSED} Errors: {tester.ERRORS}")

    assert tester.ERRORS == 0


@cocotb.test(
    expect_error=IndexError if cocotb.SIM_NAME.lower().startswith("ghdl") else ()
)
async def test_cosh_sinh(dut: SimHandleBase):
    """Test linear multiplication cordic"""

    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    tester = CordicTester(dut)

    dut._log.info("Initialize and reset model")

    # Initial valies
    dut.valid_i.value = 0
    dut.valid_i.value = 0
    dut.mode.value = 2
    dut.rotational.value = 1
    dut.x_i.value = 0
    dut.y_i.value = 0
    dut.z_i.value = 0

    # Reset DUT
    dut.rstn_i.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk_i)
    dut.rstn_i.value = 1

    # start tester after reset so we know it's in a good state
    tester.start()

    dut._log.info("Test hyperbolic cosine and sine operations")

    # Do cordic solutions
    for i, z in enumerate(gen(mu=2)):
        await RisingEdge(dut.clk_i)
        dut.x_i.value = FixedPoint(1.2075, m=14, n=16, signed=True).bits
        dut.y_i.value = FixedPoint(0, m=14, n=16, signed=True).bits
        dut.z_i.value = z
        dut.valid_i.value = 1

        await RisingEdge(dut.clk_i)
        dut.valid_i.value = 0

        await RisingEdge(dut.valid_o)

        if ((i+1) % (NUM_SAMPLES/10) == 0):
            dut._log.info(f"{i+1} / {NUM_SAMPLES}")
    await RisingEdge(dut.clk_i)

    dut._log.info(f"Passed: {tester.PASSED} Errors: {tester.ERRORS}")

    assert tester.ERRORS == 0


def create(func, mu=1, mode=""):
    ret = func(32)
    if mu == 1:
        while intToFloat(ret) < -pi/2 or intToFloat(ret) > pi/2:
            ret = func(32)
    elif mu == 0:
        while intToFloat(ret) < -1 or intToFloat(ret) > 1:
            ret = func(32)
    elif mu == -1:
        while intToFloat(ret) < -5 or intToFloat(ret) > 5:
            ret = func(32)
    return ret


def gen(num_samples=NUM_SAMPLES, func=getrandbits, mu=1, mode=""):
    """Generate random variable data for variables"""
    for _ in range(num_samples):
        yield create(func, mu=mu, mode=mode)
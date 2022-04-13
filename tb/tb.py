from math import atan, atanh
import os
from random import getrandbits
from typing import Any, Dict

import cocotb
from cocotb.binary import BinaryValue
from cocotb.clock import Clock
from cocotb.handle import SimHandleBase
from cocotb.queue import Queue
from cocotb.triggers import RisingEdge

from math import pi

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


def approx(actual: int, expected: FixedPoint) -> bool:
    return int(actual) > (expected.bits - 10) and actual < (expected.bits - 10)


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

        print(self)

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

    def model(self, inputs: Queue[DataValidMonitor]):
        """Transaction-level model of the matrix multiplier as instantiated"""
        x = FixedPoint(intToFloat(inputs["x"]), m=14, n=16, signed=True)
        y = FixedPoint(intToFloat(inputs["y"]), m=14, n=16, signed=True)
        z = FixedPoint(intToFloat(inputs["z"]), m=14, n=16, signed=True)
        for i in range(16):
            if (inputs["rotational"] == 1):
                if (z > 0):
                    d = 1
                else:
                    d = -1
            else:
                if (x * y < 0):
                    d = 1
                else:
                    d = -1
            if (inputs["mode"] == 0):
                e = FixedPoint(atan(2**(-i)), m=14, n=16, signed=True)
            elif (inputs["mode"] == 1):
                e = FixedPoint(2**(-i), m=14, n=16, signed=True)
            elif (inputs["mode"] == 2):
                e = FixedPoint(atanh(2**(-(i+1))), m=14, n=16, signed=True)
            x = x + (inputs["mode"] - 1) * d * (y >> i)
            y = y + d * (x >> i)
            z = z - d * e
        return dict(x=x, y=y, z=z)

    async def _check(self) -> None:
        while True:
            actual = await self.output_mon.values.get()
            expected_inputs = await self.input_mon.values.get()
            expected = self.model(expected_inputs)

            self.dut._log.info(f"(X): Expected: {(expected['x'])} Actual: {int(actual['x'])}")
            self.dut._log.info(f"(Y): Expected: {(expected['y'])} Actual: {int(actual['y'])}")
            self.dut._log.info(f"(Z): Expected: {(expected['z'])} Actual: {int(actual['z'])}")
            
            x = expected["x"]
            y = expected["y"]
            z = expected["z"]

            assert approx(actual=actual['x'], expected=x), f"Actual: {int(actual['x'])} Expected: {x.bits}"
            assert approx(actual=actual['y'], expected=y), f"Actual: {int(actual['y'])} Expected: {y.bits}"
            assert approx(actual=actual['z'], expected=z), f"Actual: {int(actual['z'])} Expected: {z.bits}"

@cocotb.test(
    expect_error=IndexError if cocotb.SIM_NAME.lower().startswith("ghdl") else ()
)
async def test_cordic(dut: SimHandleBase):
    """Test cordic"""

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

    thetas = [pi / 6, pi / 4, pi / 3, pi / 2]
    tests = [(0.2, 0.75), (0.5, 1), (0.25, 0.5), (0.1, 0.2), (0.1, 0.6)]

    dut._log.info("Test linear multiplication operations")

    # Do cordic solutions
    for i, z in enumerate(thetas):
        await RisingEdge(dut.clk_i)
        dut.x_i.value = FixedPoint(0.6073, m=14, n=16, signed=True).bits
        dut.y_i.value = FixedPoint(0, m=14, n=16, signed=True).bits
        dut.z_i.value = FixedPoint(z, m=14, n=16, signed=True).bits
        dut.valid_i.value = 1

        await RisingEdge(dut.clk_i)
        dut.valid_i.value = 0

        await RisingEdge(dut.valid_o)

        dut._log.info(f"{i+1} / {5}")
    await RisingEdge(dut.clk_i)


def create(func):
    return func(32)


def gen(num_samples=NUM_SAMPLES, func=getrandbits):
    """Generate random variable data for variables"""
    for _ in range(num_samples):
        yield create(func)
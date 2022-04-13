from enum import Flag
import math
import os
from random import getrandbits
from typing import Any, Dict, List
from venv import create

import cocotb
from cocotb.binary import BinaryValue
from cocotb.clock import Clock
from cocotb.handle import SimHandleBase
from cocotb.queue import Queue
from cocotb.triggers import RisingEdge

from math import pi

from fixedpoint import FixedPoint
from numpy import sign


NUM_SAMPLES = int(os.environ.get("NUM_SAMPLES", 10))


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

    def model(self, z: float) -> Dict[FixedPoint, FixedPoint]:
        """Transaction-level model of the matrix multiplier as instantiated"""
        return dict(x=FixedPoint(math.cos(z), m=16, n=16, signed=True), y=FixedPoint(math.sin(z), m=16, n=16, signed=True))

    async def _check(self) -> None:
        while True:
            actual = await self.output_mon.values.get()
            expected_inputs = await self.input_mon.values.get()
            expected = self.model(
                z=expected_inputs["z"]
            )

            assert actual["x"] == expected["x"].bits
            assert actual["y"] == expected["y"].bits


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

    dut._log.info("Test cordic operations")

    thetas = [pi / 6, pi / 4, pi / 3, pi / 2]

    # Do cordic solutions
    for i, z in enumerate(thetas):
        await RisingEdge(dut.clk_i)
        dut.x_i.value = FixedPoint(0.6073, m=16, n=16, signed=True).bits
        dut.y_i.value = 0
        dut.z_i.value = FixedPoint(z, m=16, n=16, signed=True).bits
        dut.valid_i.value = 1

        await RisingEdge(dut.clk_i)
        dut.valid_i.value = 0

        await RisingEdge(dut.valid_o)

        dut._log.info(f"{i+1} / {4}")
    await RisingEdge(dut.clk_i)


def create(func):
    return func(32)


def gen(num_samples=NUM_SAMPLES, func=getrandbits):
    """Generate random variable data for variables"""
    for _ in range(num_samples):
        yield create(func)
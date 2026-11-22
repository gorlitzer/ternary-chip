# SPDX-License-Identifier: Apache-2.0
# Tests for tt_um_gorlitzer_ternary_mac: dot products against a plain Python reference.

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, Timer

NZ, NEG, VALID, CLEAR, HI = 1, 2, 4, 8, 16
WEIGHT_BITS = {0: 0, 1: NZ, -1: NZ | NEG}


def to16(v):
    """Wrap to the chip's 16-bit signed accumulator."""
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


async def reset(dut):
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 1)


async def feed(dut, x, w, extra=0):
    dut.ui_in.value = x & 0xFF
    dut.uio_in.value = WEIGHT_BITS[w] | VALID | extra
    await ClockCycles(dut.clk, 1)
    dut.uio_in.value = 0


async def read_acc(dut):
    dut.uio_in.value = 0
    await Timer(1, unit="us")
    lo = int(dut.uo_out.value)
    dut.uio_in.value = HI
    await Timer(1, unit="us")
    hi = int(dut.uo_out.value)
    dut.uio_in.value = 0
    return to16((hi << 8) | lo)


async def clear(dut):
    dut.uio_in.value = CLEAR
    await ClockCycles(dut.clk, 1)
    dut.uio_in.value = 0


@cocotb.test()
async def test_starts_at_zero(dut):
    await reset(dut)
    assert await read_acc(dut) == 0


@cocotb.test()
async def test_single_terms(dut):
    await reset(dut)
    for x in (0, 1, 5, 127, -1, -128, 77):
        for w in (1, -1, 0):
            await clear(dut)
            await feed(dut, x, w)
            assert await read_acc(dut) == w * x, (x, w)


@cocotb.test()
async def test_weight_code_10_is_zero(dut):
    await reset(dut)
    dut.ui_in.value = 100
    dut.uio_in.value = NEG | VALID      # neg without nz still means w = 0
    await ClockCycles(dut.clk, 1)
    assert await read_acc(dut) == 0


@cocotb.test()
async def test_random_dot_products(dut):
    await reset(dut)
    rng = random.Random(42)
    for _ in range(40):
        n = rng.randint(1, 64)
        xs = [rng.randint(-128, 127) for _ in range(n)]
        ws = [rng.choice((-1, 0, 1)) for _ in range(n)]
        await clear(dut)
        for x, w in zip(xs, ws):
            await feed(dut, x, w)
        assert await read_acc(dut) == to16(sum(x * w for x, w in zip(xs, ws)))


@cocotb.test()
async def test_valid_low_holds(dut):
    await reset(dut)
    await feed(dut, 50, 1)
    dut.ui_in.value = 99
    dut.uio_in.value = NZ                # weight set but VALID low: nothing added
    await ClockCycles(dut.clk, 5)
    assert await read_acc(dut) == 50


@cocotb.test()
async def test_wraps_at_16_bits(dut):
    await reset(dut)
    for _ in range(300):                 # 300 * 127 = 38100 > 32767
        await feed(dut, 127, 1)
    assert await read_acc(dut) == to16(300 * 127)


@cocotb.test()
async def test_reset_clears(dut):
    await reset(dut)
    await feed(dut, 42, 1)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 1)
    dut.rst_n.value = 1
    assert await read_acc(dut) == 0

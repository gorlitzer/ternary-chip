# SPDX-License-Identifier: Apache-2.0
# Tests for the four-neuron ternary layer, against a plain Python reference.

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, Timer

HOLD, MAC, LOAD, CLEAR = 0 << 6, 1 << 6, 2 << 6, 3 << 6
CODE = {0: 0b00, 1: 0b01, -1: 0b11}


def to16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def pack(ws):
    """Four ternary weights -> the LOAD byte (neuron k in bits 2k+1:2k)."""
    return sum(CODE[w] << (2 * k) for k, w in enumerate(ws))


async def reset(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="us").start())
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 1)


async def command(dut, cmd, data=0):
    dut.ui_in.value = data & 0xFF
    dut.uio_in.value = cmd
    await ClockCycles(dut.clk, 1)
    dut.uio_in.value = HOLD


async def read(dut, k):
    out = []
    for hi in (0, 1):
        dut.uio_in.value = HOLD | (k << 1) | hi
        await Timer(1, unit="us")
        out.append(int(dut.uo_out.value))
    dut.uio_in.value = HOLD
    return to16((out[1] << 8) | out[0])


async def read_all(dut):
    return [await read(dut, k) for k in range(4)]


@cocotb.test()
async def test_starts_at_zero(dut):
    await reset(dut)
    assert await read_all(dut) == [0, 0, 0, 0]


async def load_matrix(dut, W):
    """W[i] = the four weights of row i."""
    await command(dut, CLEAR)
    for ws in W:
        await command(dut, LOAD, pack(ws))


def layer(W, xs):
    """Reference: y_k = sum_i W[i % 8][k] * x[i], wrapped to 16 bits."""
    return [to16(sum(W[i % 8][k] * x for i, x in enumerate(xs))) for k in range(4)]


@cocotb.test()
async def test_a_small_layer(dut):
    await reset(dut)
    W = [[1, -1, 0, 1], [1, 1, -1, 0], [0, 0, 1, -1], [-1, 1, 1, 1], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    xs = [5, -3, 100, 7, 1, 2, 3, 4]
    await load_matrix(dut, W)
    for x in xs:
        await command(dut, MAC, x)
    assert await read_all(dut) == layer(W, xs)


@cocotb.test()
async def test_random_layers(dut):
    await reset(dut)
    rng = random.Random(7)
    for _ in range(30):
        W = [[rng.choice((-1, 0, 1)) for _ in range(4)] for _ in range(8)]
        xs = [rng.randint(-128, 127) for _ in range(rng.choice((8, 8, 16, 3, 40)))]
        await load_matrix(dut, W)
        for x in xs:
            await command(dut, MAC, x)
        assert await read_all(dut) == layer(W, xs), (W, len(xs))


@cocotb.test()
async def test_same_weights_reused_after_clear(dut):
    await reset(dut)
    W = [[1, -1, 1, -1]] * 4 + [[0, 1, 0, 1]] * 4
    await load_matrix(dut, W)
    xs = [9, 8, 7, 6, 5, 4, 3, 2]
    for _ in range(2):                      # CLEAR keeps the weights: same answer twice
        await command(dut, CLEAR)
        for x in xs:
            await command(dut, MAC, x)
        assert await read_all(dut) == layer(W, xs)


@cocotb.test()
async def test_code_10_is_zero(dut):
    await reset(dut)
    await load_matrix(dut, [[0, 0, 0, 0]] * 8)
    await command(dut, CLEAR)
    await command(dut, LOAD, 0b10_10_10_10)   # neg without nz: weight 0
    await command(dut, MAC, 77)
    assert await read_all(dut) == [0, 0, 0, 0]


@cocotb.test()
async def test_hold_adds_nothing(dut):
    await reset(dut)
    await load_matrix(dut, [[1, -1, 1, -1]] * 8)
    await command(dut, MAC, 9)
    dut.ui_in.value = 50
    dut.uio_in.value = HOLD
    await ClockCycles(dut.clk, 5)
    assert await read_all(dut) == [9, -9, 9, -9]


@cocotb.test()
async def test_wraps_at_16_bits(dut):
    await reset(dut)
    await load_matrix(dut, [[1, -1, 0, 1]] * 8)
    for _ in range(300):
        await command(dut, MAC, 127)
    assert await read_all(dut) == [to16(300 * 127), to16(-300 * 127), 0, to16(300 * 127)]


@cocotb.test()
async def test_reset_clears_everything(dut):
    await reset(dut)
    await load_matrix(dut, [[1, 1, 1, 1]] * 8)
    await command(dut, MAC, 42)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 1)
    dut.rst_n.value = 1
    await command(dut, MAC, 42)               # weights were reset to 0
    assert await read_all(dut) == [0, 0, 0, 0]

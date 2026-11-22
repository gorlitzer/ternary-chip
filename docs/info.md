<!---
This file is used to generate your project datasheet.
-->

## How it works

AI chips spend most of their logic multiplying numbers by weights. In BitNet-style models every weight is
-1, 0 or +1, so a multiply becomes: pass the number, negate it, or ignore it. This chip is a tiny AI layer
built that way: **4 neurons working in parallel, no multiplier anywhere.**

- A **weight memory** on chip holds 8 rows; each row has one ternary weight for each of the 4 neurons.
  Weights stay next to the maths, as in a real AI accelerator.
- Every **MAC** clock, one 8-bit signed number `x` arrives on `ui` and all four neurons add
  `W[row][k] * x` to their 16-bit sums at the same time (four operations per clock). The row advances by
  itself, so 8 MAC clocks compute a full 8-input, 4-output layer: `y_k = sum_i W[i][k] * x[i]`.
  After row 7 it wraps to row 0.

Inside each neuron, `(x AND nz) XOR neg` plus `neg` adds `x`, subtracts `x`, or adds nothing (two's complement).

## Commands (`uio[7:6]`)

| `uio[7:6]` | Command | What happens |
|---|---|---|
| `00` | HOLD | nothing changes; read the outputs |
| `01` | MAC | all four neurons add their weight for this row times `ui`; next row |
| `10` | LOAD | `ui` is written into the next weight row: neuron k uses bits `2k+1:2k` = `{neg, nz}` (`01` = +1, `11` = -1, `00` or `10` = 0) |
| `11` | CLEAR | all four sums to 0 and both row pointers back to row 0 (weights are kept) |

Output: `uo` shows a byte of one neuron's sum: neuron `uio[2:1]`, low byte if `uio[0]` = 0, high byte if 1.

## How to test

1. Reset (`rst_n` low): sums, pointers and weights go to 0.
2. CLEAR, then LOAD 8 times: the 8 weight rows.
3. MAC 8 times with your 8 input numbers.
4. Read each neuron: set `uio[2:1]` to the neuron, read `uo` with `uio[0]` = 0 then 1.

Example: row 0 = weights (+1, -1, 0, +1) i.e. LOAD `0b01_00_11_01`, then MAC with x = 5:
the neurons read 5, -5, 0, 5.

## External hardware

None needed beyond the Tiny Tapeout demo board; a microcontroller can load weights and stream inputs.

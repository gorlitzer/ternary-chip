<!---
This file is used to generate your project datasheet.
-->

## How it works

AI chips spend most of their logic on multiplying numbers by weights. In BitNet-style models every weight is
-1, 0 or +1, so a multiply becomes: pass the number, negate it, or ignore it. This design does exactly that,
with no multiplier.

Every clock with `valid` high, it adds `w * x` to a 16-bit signed accumulator:

- `x` is an 8-bit signed number on `ui[7:0]`.
- `w` is set by `uio[0]` (`w_nz`, weight not zero) and `uio[1]` (`w_neg`, weight negative):
  `00` = 0, `01` = +1, `11` = -1 (`10` also counts as 0).
- Feed numbers one after another and the accumulator holds their dot product, of any length
  (it wraps at 16 bits).

Inside, the lane computes `(x AND nz) XOR neg` plus `neg`, which is the two's-complement way to add `x`,
subtract `x`, or add nothing. The same unit was first built and tested in a browser game (Bitforge) and on an FPGA.

## How to test

1. Reset (`rst_n` low), or pulse `uio[3]` (`clear`) high for one clock.
2. For each term: put `x` on `ui`, set `uio[1:0]` to the weight, set `uio[2]` (`valid`) high for one clock.
3. Read the result: `uo` shows the low byte; set `uio[4]` (`hi`) to see the high byte.

Example: x = 5, w = +1, then x = 3, w = -1 gives 5 - 3 = 2.

## External hardware

None needed: switches and LEDs on the Tiny Tapeout demo board are enough. A microcontroller can stream
longer dot products.

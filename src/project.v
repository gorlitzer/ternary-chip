/*
 * Copyright (c) 2026 gorlitzer
 * SPDX-License-Identifier: Apache-2.0
 *
 * Four ternary neurons in parallel: a tiny multiplier-free AI layer (8 inputs x 4 outputs).
 *
 * The chip holds a small weight memory: 8 rows, each row = one ternary weight (-1, 0, +1) for each of the
 * 4 neurons. Weights stay on chip, next to the maths, as in a real AI accelerator. Every MAC clock, one
 * 8-bit signed number x arrives on ui_in and ALL FOUR neurons add (their weight for this row) * x at once:
 * four operations per clock, no multiplier. The row advances by itself, so 8 MAC clocks compute a full
 * 8-input layer: y_k = sum_i W[i][k] * x[i]. After row 7 it wraps to row 0.
 *
 * Commands on uio_in[7:6]:
 *   00  HOLD   just read outputs
 *   01  MAC    every neuron adds W[row][k] * x (x = ui_in), then row = row + 1
 *   10  LOAD   write ui_in into the next weight row (neuron k: bits 2k+1:2k = {neg, nz})
 *   11  CLEAR  all four sums to 0, both row pointers back to 0 (weights are kept)
 * Output: uo_out = byte uio_in[0] (0 low, 1 high) of neuron uio_in[2:1]'s sum.
 *
 * Benchmark mode, for measuring energy on the real chip with the input pins quiet:
 *   uio_in[3] RUN  every clock, all four neurons MAC with x and weights from an on-chip 16-bit random
 *                  generator (LFSR), so nothing has to be fed through the pins. Commands are ignored.
 *   uio_in[4] DRY  with RUN: the generator runs but the sums do not change, so (RUN) - (RUN+DRY) is the
 *                  energy of the MACs alone.
 * CLEAR (with RUN low) also restarts the generator, so every run is repeatable and checkable.
 */

`default_nettype none

module tt_um_gorlitzer_ternary_mac (
    input  wire [7:0] ui_in,    // x (MAC) or the four weights (LOAD)
    output wire [7:0] uo_out,   // selected byte of the selected neuron's sum
    input  wire [7:0] uio_in,   // [7:6] command, [4] dry, [3] run, [2:1] neuron, [0] high byte
    output wire [7:0] uio_out,  // unused: all uio pins are inputs
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);
  localparam HOLD = 2'b00, MAC = 2'b01, LOAD = 2'b10, CLEAR = 2'b11;
  wire [1:0] cmd = uio_in[7:6];
  wire run = uio_in[3], dry = uio_in[4];
  wire restart = !rst_n || (!run && cmd == CLEAR);

  reg  [7:0] wmem [0:7];             // 8 rows x 4 neurons x {neg, nz}
  reg  [2:0] wptr, rptr;              // next row to LOAD, next row to use in MAC
  reg  signed [15:0] sum [0:3];
  wire signed [15:0] term [0:3];
  reg  [15:0] lfsr;                   // Galois LFSR x^16+x^14+x^13+x^11+1: 65535 states
  always @(posedge clk) begin
    if (restart)  lfsr <= 16'hACE1;
    else if (run) lfsr <= {1'b0, lfsr[15:1]} ^ (lfsr[0] ? 16'hB400 : 16'h0000);
  end
  wire [7:0] x   = run ? lfsr[7:0]  : ui_in;
  wire [7:0] row = run ? lfsr[15:8] : wmem[rptr];

  genvar k;
  generate
    for (k = 0; k < 4; k = k + 1) begin : neuron
      // one ternary lane per neuron: pass, negate or zero x, with no multiplier
      tdot #(.N(1), .W(8), .ACC(16)) lane (.x(x), .w(row[2*k+1:2*k]), .y(term[k]));
      always @(posedge clk) begin
        if (restart)                     sum[k] <= 16'sd0;
        else if (run ? !dry : cmd == MAC) sum[k] <= sum[k] + term[k];
      end
    end
  endgenerate

  integer r;
  always @(posedge clk) begin
    if (!rst_n) begin
      wptr <= 3'd0; rptr <= 3'd0;
      for (r = 0; r < 8; r = r + 1) wmem[r] <= 8'd0;
    end else if (!run) begin
      case (cmd)
        LOAD:  begin wmem[wptr] <= ui_in; wptr <= wptr + 3'd1; end
        MAC:   rptr <= rptr + 3'd1;
        CLEAR: begin wptr <= 3'd0; rptr <= 3'd0; end
        default: ;
      endcase
    end
  end

  wire [15:0] picked = sum[uio_in[2:1]];
  assign uo_out  = uio_in[0] ? picked[15:8] : picked[7:0];
  assign uio_out = 8'b0;
  assign uio_oe  = 8'b0;

  wire _unused = &{ena, uio_in[5], 1'b0};
endmodule

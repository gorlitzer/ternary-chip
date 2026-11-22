/*
 * Copyright (c) 2026 gorlitzer
 * SPDX-License-Identifier: Apache-2.0
 *
 * Ternary multiply-accumulate: the core operation of a BitNet-style AI chip, with no multiplier.
 * Every clock with VALID high it adds  w * x  to a 16-bit signed accumulator, where x is an 8-bit
 * signed number on ui_in and w is a ternary weight in {-1, 0, +1} on uio_in[1:0].
 * Feed numbers one after another and the accumulator holds their dot product, of any length.
 */

`default_nettype none

module tt_um_gorlitzer_ternary_mac (
    input  wire [7:0] ui_in,    // x: 8-bit signed activation
    output wire [7:0] uo_out,   // accumulator, low or high byte (see uio_in[4])
    input  wire [7:0] uio_in,   // [0] nz, [1] neg, [2] valid, [3] clear, [4] high byte
    output wire [7:0] uio_out,  // unused: all uio pins are inputs
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);
  // weight w: nz=0 -> 0, nz=1 & neg=0 -> +1, nz=1 & neg=1 -> -1
  wire nz    = uio_in[0];
  wire neg   = uio_in[1];
  wire valid = uio_in[2];
  wire clear = uio_in[3];
  wire hi    = uio_in[4];

  // one ternary lane: pass, negate or zero x (no multiplier), sign-extended to 16 bits
  wire signed [15:0] term;
  tdot #(.N(1), .W(8), .ACC(16)) lane (.x(ui_in), .w({neg, nz}), .y(term));

  reg signed [15:0] acc;
  always @(posedge clk) begin
    if (!rst_n || clear) acc <= 16'sd0;
    else if (valid)      acc <= acc + term;
  end

  assign uo_out  = hi ? acc[15:8] : acc[7:0];
  assign uio_out = 8'b0;
  assign uio_oe  = 8'b0;

  wire _unused = &{ena, uio_in[7:5], 1'b0};
endmodule

// Copied from gorlitzer/bitforge hw/rtl/tdot.v (tested there against signed multiply at 6 sizes).
// tdot: ternary dot product, the core operation of a BitNet-style AI chip.
//
//   y = sum over i of  w[i] * x[i],   w[i] in {-1, 0, +1},   x[i] a signed W-bit number
//
// No multiplier anywhere. Each lane only has to pass, negate or zero its input,
// exactly like the "Ternary weight" level in Bitforge:
//
//   lane term t[i] = (x[i] AND nz[i]) XOR neg[i]     (one AND + one XOR per bit)
//   y              = sum of t[i]  +  (number of lanes with neg = 1)
//
// The second line is two's complement: -x = NOT x + 1. Instead of adding the
// "+1" inside every lane, all of them are added once at the end. (When nz = 0
// and neg = 1 the lane contributes NOT 0 + 1 = 0, so that code is also zero.)
//
// Weight encoding, 2 bits per lane:  w[2i] = nz (non-zero),  w[2i+1] = neg.
//    +1 = 2'b01    -1 = 2'b11    0 = 2'b00 (2'b10 also reads as 0)

`timescale 1ns/1ps
module tdot #(
  parameter integer N   = 4,   // lanes
  parameter integer W   = 8,   // activation width, signed
  parameter integer ACC = 16   // result width; needs W + ceil(log2(N)) + 1 bits to never overflow
) (
  input  wire [N*W-1:0]          x,  // lane i = x[i*W +: W]
  input  wire [N*2-1:0]          w,  // lane i = w[i*2 +: 2] = {neg, nz}
  output reg  signed [ACC-1:0]   y
);
  integer i;
  reg [W-1:0]          t;
  reg signed [ACC-1:0] sum;

  always @* begin
    sum = 0;
    for (i = 0; i < N; i = i + 1) begin
      t   = (x[i*W +: W] & {W{w[i*2]}}) ^ {W{w[i*2+1]}};
      sum = sum + {{(ACC-W){t[W-1]}}, t};        // sign-extend the lane term
      sum = sum + {{(ACC-1){1'b0}}, w[i*2+1]};   // the "+1" of each negation
    end
    y = sum;
  end
endmodule

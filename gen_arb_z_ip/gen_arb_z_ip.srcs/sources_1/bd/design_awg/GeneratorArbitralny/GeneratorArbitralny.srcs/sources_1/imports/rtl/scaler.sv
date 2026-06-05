`timescale 1ns/1ps

// Pipelined scaler.
// Fix for Vivado timing failure:
// old critical path was wave_bram -> scaler multiply/add/saturate -> sigma_delta.
// This version splits scaling into registered stages.
module scaler #(
    parameter integer SAMPLE_BITS = 16
)(
    input  wire                         clk,
    input  wire                         rst,
    input  wire                         enable,

    input  wire signed [SAMPLE_BITS-1:0] sample_in,
    input  wire signed [15:0]            amplitude_q15,
    input  wire signed [SAMPLE_BITS-1:0] offset,
    output reg  signed [SAMPLE_BITS-1:0] sample_out
);

    localparam signed [SAMPLE_BITS:0] MAX_SAMPLE = 17'sd32767;
    localparam signed [SAMPLE_BITS:0] MIN_SAMPLE = -17'sd32768;

    // Stage 0: register BRAM/config inputs.
    reg signed [SAMPLE_BITS-1:0] sample_in_r;
    reg signed [15:0]            amplitude_q15_r;
    reg signed [SAMPLE_BITS-1:0] offset_r0;

    // Stage 1: registered multiplier result.
    reg signed [SAMPLE_BITS+15:0] mult_r;
    reg signed [SAMPLE_BITS-1:0]  offset_r1;

    // Stage 2: scale, add offset and saturate.
    wire signed [SAMPLE_BITS:0] scaled_ext;
    wire signed [SAMPLE_BITS:0] offset_ext;
    wire signed [SAMPLE_BITS:0] sum_ext;

    assign scaled_ext = mult_r[SAMPLE_BITS+14:15];
    assign offset_ext = {offset_r1[SAMPLE_BITS-1], offset_r1};
    assign sum_ext    = scaled_ext + offset_ext;

    always @(posedge clk) begin
        if (rst) begin
            sample_in_r     <= {SAMPLE_BITS{1'b0}};
            amplitude_q15_r <= 16'sd0;
            offset_r0       <= {SAMPLE_BITS{1'b0}};
            mult_r          <= {(SAMPLE_BITS+16){1'b0}};
            offset_r1       <= {SAMPLE_BITS{1'b0}};
            sample_out      <= {SAMPLE_BITS{1'b0}};
        end else if (enable) begin
            sample_in_r     <= sample_in;
            amplitude_q15_r <= amplitude_q15;
            offset_r0       <= offset;

            mult_r          <= sample_in_r * amplitude_q15_r;
            offset_r1       <= offset_r0;

            if (sum_ext > MAX_SAMPLE)
                sample_out <= 16'sd32767;
            else if (sum_ext < MIN_SAMPLE)
                sample_out <= -16'sd32768;
            else
                sample_out <= sum_ext[SAMPLE_BITS-1:0];
        end
    end

endmodule

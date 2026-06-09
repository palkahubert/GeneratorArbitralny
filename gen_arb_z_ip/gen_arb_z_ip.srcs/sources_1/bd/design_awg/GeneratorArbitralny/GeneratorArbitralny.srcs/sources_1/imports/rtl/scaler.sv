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

    input  wire [SAMPLE_BITS-1:0]       sample_in,
    input  wire [15:0]                  amplitude_q16,
    input  wire [SAMPLE_BITS-1:0]       offset,
    output reg  [SAMPLE_BITS-1:0]       sample_out
);

    localparam [SAMPLE_BITS-1:0] MAX_SAMPLE = {SAMPLE_BITS{1'b1}};

    // Stage 0: register BRAM/config inputs.
    reg [SAMPLE_BITS-1:0] sample_in_r;
    reg [15:0]            amplitude_q16_r;
    reg [SAMPLE_BITS-1:0] offset_r0;

    // Stage 1: registered multiplier result.
    reg [SAMPLE_BITS+15:0] mult_r;
    reg [SAMPLE_BITS-1:0]  sample_in_r1;
    reg [SAMPLE_BITS-1:0]  offset_r1;
    reg                    unity_gain_r1;

    // Stage 2: scale, add offset and saturate.
    wire [SAMPLE_BITS:0] scaled_ext;
    wire [SAMPLE_BITS:0] offset_ext;
    wire [SAMPLE_BITS:0] sum_ext;

    assign scaled_ext = unity_gain_r1
                      ? {1'b0, sample_in_r1}
                      : {1'b0, mult_r[SAMPLE_BITS+15:16]};
    assign offset_ext = {1'b0, offset_r1};
    assign sum_ext    = scaled_ext + offset_ext;

    always @(posedge clk) begin
        if (rst) begin
            sample_in_r     <= {SAMPLE_BITS{1'b0}};
            amplitude_q16_r <= 16'd0;
            offset_r0       <= {SAMPLE_BITS{1'b0}};
            mult_r          <= {(SAMPLE_BITS+16){1'b0}};
            sample_in_r1    <= {SAMPLE_BITS{1'b0}};
            offset_r1       <= {SAMPLE_BITS{1'b0}};
            unity_gain_r1   <= 1'b0;
            sample_out      <= {SAMPLE_BITS{1'b0}};
        end else if (enable) begin
            sample_in_r     <= sample_in;
            amplitude_q16_r <= amplitude_q16;
            offset_r0       <= offset;

            mult_r          <= sample_in_r * amplitude_q16_r;
            sample_in_r1    <= sample_in_r;
            offset_r1       <= offset_r0;
            unity_gain_r1   <= (amplitude_q16_r == 16'hFFFF);

            if (sum_ext > {1'b0, MAX_SAMPLE})
                sample_out <= MAX_SAMPLE;
            else
                sample_out <= sum_ext[SAMPLE_BITS-1:0];
        end
    end

endmodule

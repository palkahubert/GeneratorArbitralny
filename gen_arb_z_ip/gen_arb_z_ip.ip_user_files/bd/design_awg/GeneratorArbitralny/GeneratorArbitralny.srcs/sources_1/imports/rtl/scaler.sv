`timescale 1ns/1ps
module scaler #(
    parameter integer SAMPLE_BITS = 16
)(
    input  wire signed [SAMPLE_BITS-1:0] sample_in,
    input  wire signed [15:0]            amplitude_q15,
    input  wire signed [SAMPLE_BITS-1:0] offset,
    output reg  signed [SAMPLE_BITS-1:0] sample_out
);

    wire signed [SAMPLE_BITS+15:0] mult_full;
    wire signed [SAMPLE_BITS:0]    scaled_ext;
    wire signed [SAMPLE_BITS:0]    offset_ext;
    wire signed [SAMPLE_BITS:0]    sum_ext;

    assign mult_full  = sample_in * amplitude_q15;
    assign scaled_ext = mult_full[SAMPLE_BITS+14:15];
    assign offset_ext = {offset[SAMPLE_BITS-1], offset};
    assign sum_ext    = scaled_ext + offset_ext;

    always @(*) begin
        if (sum_ext > 17'sd32767)
            sample_out = 16'sd32767;
        else if (sum_ext < -17'sd32768)
            sample_out = -16'sd32768;
        else
            sample_out = sum_ext[SAMPLE_BITS-1:0];
    end

endmodule

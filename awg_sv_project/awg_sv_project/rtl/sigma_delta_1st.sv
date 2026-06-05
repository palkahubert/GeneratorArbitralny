`timescale 1ns/1ps
module sigma_delta_1st #(
    parameter integer SAMPLE_BITS = 16,
    parameter integer ACC_BITS    = 20
)(
    input  wire                         clk,
    input  wire                         rst,
    input  wire                         enable,
    input  wire signed [SAMPLE_BITS-1:0] sample_in,
    output reg                          sd_out
);

    reg signed [ACC_BITS-1:0] acc;

    wire signed [ACC_BITS-1:0] x_ext;
    wire signed [ACC_BITS-1:0] feedback;

    assign x_ext = {{(ACC_BITS-SAMPLE_BITS){sample_in[SAMPLE_BITS-1]}}, sample_in};

    assign feedback = sd_out
                    ? {{(ACC_BITS-SAMPLE_BITS){1'b0}}, 16'sd32767}
                    : {{(ACC_BITS-SAMPLE_BITS){1'b1}}, -16'sd32768};

    always @(posedge clk) begin
        if (rst) begin
            acc    <= {ACC_BITS{1'b0}};
            sd_out <= 1'b0;
        end else if (enable) begin
            acc    <= acc + x_ext - feedback;
            sd_out <= ~acc[ACC_BITS-1];
        end
    end

endmodule

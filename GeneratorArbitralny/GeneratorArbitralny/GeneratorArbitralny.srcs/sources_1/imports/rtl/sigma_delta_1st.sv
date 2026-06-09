`timescale 1ns/1ps
module sigma_delta_1st #(
    parameter integer SAMPLE_BITS = 16,
    parameter integer ACC_BITS    = 20
)(
    input  wire                         clk,
    input  wire                         rst,
    input  wire                         enable,
    input  wire [SAMPLE_BITS-1:0]       sample_in,
    output reg                          sd_out
);

    localparam integer SHIFT_BITS = ACC_BITS - SAMPLE_BITS;
    localparam [SAMPLE_BITS-1:0] MAX_SAMPLE = {SAMPLE_BITS{1'b1}};

    reg [ACC_BITS-1:0] acc;
    wire [ACC_BITS-1:0] sample_ext;
    wire [ACC_BITS:0]   acc_sum;

    assign sample_ext = {sample_in, {SHIFT_BITS{1'b0}}};
    assign acc_sum    = {1'b0, acc} + {1'b0, sample_ext};

    always @(posedge clk) begin
        if (rst) begin
            acc    <= {ACC_BITS{1'b0}};
            sd_out <= 1'b0;
        end else if (enable) begin
            if (sample_in == {SAMPLE_BITS{1'b0}}) begin
                acc    <= {ACC_BITS{1'b0}};
                sd_out <= 1'b0;
            end else if (sample_in == MAX_SAMPLE) begin
                acc    <= {ACC_BITS{1'b0}};
                sd_out <= 1'b1;
            end else begin
                acc    <= acc_sum[ACC_BITS-1:0];
                sd_out <= acc_sum[ACC_BITS];
            end
        end else begin
            acc    <= {ACC_BITS{1'b0}};
            sd_out <= 1'b0;
        end
    end

endmodule

`timescale 1ns/1ps
module dds_addr #(
    parameter integer PHASE_BITS = 32,
    parameter integer ADDR_BITS  = 10
)(
    input  wire                         clk,
    input  wire                         rst,
    input  wire                         enable,
    input  wire [PHASE_BITS-1:0]         phase_step,
    output reg  [PHASE_BITS-1:0]         phase_acc,
    output wire [ADDR_BITS-1:0]          lut_addr
);

    always @(posedge clk) begin
        if (rst) begin
            phase_acc <= {PHASE_BITS{1'b0}};
        end else if (enable) begin
            phase_acc <= phase_acc + phase_step;
        end
    end

    assign lut_addr = phase_acc[PHASE_BITS-1 : PHASE_BITS-ADDR_BITS];

endmodule

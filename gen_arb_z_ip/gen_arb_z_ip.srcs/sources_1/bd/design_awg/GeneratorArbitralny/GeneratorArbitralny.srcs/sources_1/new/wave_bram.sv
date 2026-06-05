`timescale 1ns/1ps

module wave_bram #(
    parameter integer ADDR_BITS   = 12,
    parameter integer SAMPLE_BITS = 16,
    parameter INIT_FILE   = "waveform.mem"
)(
    input  wire                         clk,

    input  wire                         wr_en,
    input  wire [ADDR_BITS-1:0]          wr_addr,
    input  wire signed [SAMPLE_BITS-1:0] wr_data,

    input  wire [ADDR_BITS-1:0]          rd_addr,
    output reg  signed [SAMPLE_BITS-1:0] rd_data
);

    localparam integer DEPTH = (1 << ADDR_BITS);

    (* ram_style = "block" *)
    reg signed [SAMPLE_BITS-1:0] mem [0:DEPTH-1];

    initial begin
        if (INIT_FILE != "")
            $readmemh(INIT_FILE, mem);
    end

    always @(posedge clk) begin
        if (wr_en)
            mem[wr_addr] <= wr_data;

        rd_data <= mem[rd_addr];
    end

endmodule
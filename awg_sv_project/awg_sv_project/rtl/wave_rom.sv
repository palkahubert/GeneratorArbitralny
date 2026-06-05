`timescale 1ns/1ps
module wave_rom #(
    parameter integer ADDR_BITS   = 10,
    parameter integer SAMPLE_BITS = 16,
    parameter string  INIT_FILE   = "waveform.mem"
)(
    input  wire                         clk,
    input  wire [ADDR_BITS-1:0]          addr,
    output reg  signed [SAMPLE_BITS-1:0] sample
);

    localparam integer DEPTH = (1 << ADDR_BITS);
    reg signed [SAMPLE_BITS-1:0] mem [0:DEPTH-1];

    initial begin
        $readmemh(INIT_FILE, mem);
    end

    always @(posedge clk) begin
        sample <= mem[addr];
    end

endmodule

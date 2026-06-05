`timescale 1ns/1ps

module wave_bram #(
    parameter integer ADDR_BITS   = 12,
    parameter integer SAMPLE_BITS = 16,
    parameter INIT_FILE = "waveform.mem"
)(
    input  wire                          clk,

    input  wire                          wr_en,
    input  wire [ADDR_BITS-1:0]           wr_addr,
    input  wire signed [SAMPLE_BITS-1:0]  wr_data,

    input  wire [ADDR_BITS-1:0]           rd_addr,
    output reg  signed [SAMPLE_BITS-1:0]  rd_data
);

    localparam integer DEPTH = (1 << ADDR_BITS);

    (* ram_style = "block" *)
    reg signed [SAMPLE_BITS-1:0] mem [0:DEPTH-1];

    integer i;

    initial begin
        // Najpierw zerujemy cala pamiec, zeby symulacja nie czytala X
        for (i = 0; i < DEPTH; i = i + 1) begin
            mem[i] = {SAMPLE_BITS{1'b0}};
        end

        // Potem opcjonalnie nadpisujemy probkami z pliku
        if (INIT_FILE != "") begin
            $readmemh(INIT_FILE, mem);
        end
    end

    always @(posedge clk) begin
        if (wr_en)
            mem[wr_addr] <= wr_data;

        rd_data <= mem[rd_addr];
    end

endmodule
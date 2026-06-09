`timescale 1ns/1ps

module sigma_delta_1st #(
    parameter integer SAMPLE_BITS = 16
)(
    input  wire                         clk,
    input  wire                         rst,
    input  wire                         enable,

    /*
     * sample_in jest signed:
     * -32768 ... +32767
     */
    input  wire signed [SAMPLE_BITS-1:0] sample_in,

    /*
     * sd_out jest 1-bitowym PDM:
     * 0 albo 1
     */
    output reg                          sd_out
);

    /*
     * Zamiana signed audio/sample na unsigned duty target:
     *
     * sample_in = -32768 -> target = 0
     * sample_in =      0 -> target = 32768
     * sample_in = +32767 -> target = 65535
     *
     * Dziêki temu zero sygna³u odpowiada wype³nieniu 50%.
     */
    wire [SAMPLE_BITS:0] sample_unsigned;

    assign sample_unsigned =
        {1'b0, sample_in[SAMPLE_BITS-1:0]} + (1 << (SAMPLE_BITS-1));

    /*
     * Akumulator sigma-delta.
     * Ma jeden bit wiêcej ni¿ sample_unsigned.
     */
    reg [SAMPLE_BITS:0] acc;

    always @(posedge clk) begin
        if (rst) begin
            acc    <= {SAMPLE_BITS+1{1'b0}};
            sd_out <= 1'b0;
        end else if (enable) begin
            /*
             * Klasyczny 1-bitowy modulator sigma-delta:
             * carry z dodawania jest wyjœciem.
             */
            {sd_out, acc[SAMPLE_BITS-1:0]} <=
                acc[SAMPLE_BITS-1:0] + sample_unsigned[SAMPLE_BITS-1:0];

            acc[SAMPLE_BITS] <= 1'b0;
        end else begin
            acc    <= {SAMPLE_BITS+1{1'b0}};
            sd_out <= 1'b0;
        end
    end

endmodule
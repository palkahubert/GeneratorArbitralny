`timescale 1ns / 1ps

module awg_core #(
    parameter integer ADDR_BITS   = 12,
    parameter integer SAMPLE_BITS = 16,
    parameter INIT_FILE = "waveform.mem"
)(
    input  wire                          clk,
    input  wire                          rst,
    input  wire                          enable,

    input  wire [31:0]                   cfg_phase_step,
    input  wire [15:0]                   cfg_amplitude_q15,
    input  wire signed [15:0]            cfg_offset,

    input  wire                          wave_wr_en,
    input  wire [ADDR_BITS-1:0]           wave_wr_addr,
    input  wire signed [SAMPLE_BITS-1:0]  wave_wr_data,

    output wire                          sd_out,

    /*
     * Wyjscie dla zewnetrznej drabinki R-2R.
     *
     * dac_out[7] = MSB, najwieksza waga drabinki
     * dac_out[0] = LSB, najmniejsza waga drabinki
     */
    output reg  [7:0]                    dac_out,

    /*
     * Debug
     */
    output reg  [31:0]                   dbg_phase_acc,
    output wire [ADDR_BITS-1:0]           dbg_lut_addr,
    output wire signed [SAMPLE_BITS-1:0]  dbg_raw_sample,
    output wire signed [SAMPLE_BITS-1:0]  dbg_scaled_sample
);

    /*
     * DDS phase accumulator.
     *
     * Adres LUT/BRAM jest brany z najstarszych ADDR_BITS bitow
     * 32-bitowego akumulatora fazy.
     */
    always @(posedge clk) begin
        if (rst) begin
            dbg_phase_acc <= 32'd0;
        end else if (enable) begin
            dbg_phase_acc <= dbg_phase_acc + cfg_phase_step;
        end else begin
            dbg_phase_acc <= 32'd0;
        end
    end

    assign dbg_lut_addr = dbg_phase_acc[31 -: ADDR_BITS];

    /*
     * BRAM z probkami.
     *
     * MicroBlaze moze wpisywac probki przez wave_wr_en/wave_wr_addr/wave_wr_data.
     * DDS czyta probki przez dbg_lut_addr.
     */
    wave_bram #(
        .ADDR_BITS   (ADDR_BITS),
        .SAMPLE_BITS (SAMPLE_BITS),
        .INIT_FILE   (INIT_FILE)
    ) u_wave_bram (
        .clk     (clk),

        .wr_en   (wave_wr_en),
        .wr_addr (wave_wr_addr),
        .wr_data (wave_wr_data),

        .rd_addr (dbg_lut_addr),
        .rd_data (dbg_raw_sample)
    );

    /*
     * Skalowanie amplitudy i dodanie offsetu.
     *
     * dbg_raw_sample     : signed, probka z BRAM
     * dbg_scaled_sample  : signed, probka po amplitudzie/offsetcie
     */
    scaler #(
        .SAMPLE_BITS (SAMPLE_BITS)
    ) u_scaler (
        .clk           (clk),
        .rst           (rst),
        .enable        (enable),

        .sample_in     (dbg_raw_sample),
        .amplitude_q15 (cfg_amplitude_q15),
        .offset        (cfg_offset),

        .sample_out    (dbg_scaled_sample)
    );

    /*
     * Stare wyjscie 1-bit sigma-delta.
     * Nie podlaczac tego do drabinki R-2R.
     */
    sigma_delta_1st #(
        .SAMPLE_BITS (SAMPLE_BITS)
    ) u_sigma_delta (
        .clk       (clk),
        .rst       (rst),
        .enable    (enable),
        .sample_in (dbg_scaled_sample),
        .sd_out    (sd_out)
    );

    /*
     * Konwersja signed -> unsigned dla R-2R.
     *
     * dbg_scaled_sample jest signed:
     *
     *   -32768 ... 0 ... +32767
     *
     * Drabinka R-2R potrzebuje unsigned:
     *
     *   0 ... 32768 ... 65535
     *
     * Dlatego dodajemy 0x8000.
     *
     * Przyklad:
     *
     *   -32768 -> 0x0000 -> dac_out = 0x00
     *        0 -> 0x8000 -> dac_out = 0x80
     *   +32767 -> 0xFFFF -> dac_out = 0xFF
     */
    reg [15:0] sample_unsigned_reg;

    always @(posedge clk) begin
        if (rst) begin
            sample_unsigned_reg <= 16'h8000;
            dac_out             <= 8'h80;
        end else if (enable) begin
            sample_unsigned_reg <= $signed(dbg_scaled_sample) + 16'sh8000;
            dac_out             <= sample_unsigned_reg[15:8];
        end else begin
            sample_unsigned_reg <= 16'h8000;
            dac_out             <= 8'h80;
        end
    end

endmodule
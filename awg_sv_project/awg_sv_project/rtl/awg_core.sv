`timescale 1ns/1ps
module awg_core #(
    parameter integer PHASE_BITS  = 32,
    parameter integer ADDR_BITS   = 12,
    parameter integer SAMPLE_BITS = 16,
    parameter string  INIT_FILE   = "waveform.mem"
)(
    input  wire                          clk,
    input  wire                          rst,

    // Rejestry konfiguracyjne, docelowo z AXI-Lite:
    input  wire                          enable,
    input  wire [PHASE_BITS-1:0]         cfg_phase_step,
    input  wire signed [15:0]            cfg_amplitude_q15,
    input  wire signed [SAMPLE_BITS-1:0] cfg_offset,
    
    input  wire                          wave_wr_en,
    input  wire [ADDR_BITS-1:0]          wave_wr_addr,
    input  wire signed [SAMPLE_BITS-1:0] wave_wr_data,


    output wire                          sd_out,

    // Debug do symulacji:
    output wire [ADDR_BITS-1:0]          dbg_lut_addr,
    output wire signed [SAMPLE_BITS-1:0] dbg_raw_sample,
    output wire signed [SAMPLE_BITS-1:0] dbg_scaled_sample,
    output wire [PHASE_BITS-1:0]         dbg_phase_acc
);

    dds_addr #(
        .PHASE_BITS(PHASE_BITS),
        .ADDR_BITS(ADDR_BITS)
    ) u_dds_addr (
        .clk(clk),
        .rst(rst),
        .enable(enable),
        .phase_step(cfg_phase_step),
        .phase_acc(dbg_phase_acc),
        .lut_addr(dbg_lut_addr)
    );

//    wave_rom #(
//        .ADDR_BITS(ADDR_BITS),
//        .SAMPLE_BITS(SAMPLE_BITS),
//        .INIT_FILE(INIT_FILE)
//    ) u_wave_rom (
//        .clk(clk),
//        .addr(dbg_lut_addr),
//        .sample(dbg_raw_sample)
//    );

    wave_bram #(
    .ADDR_BITS(ADDR_BITS),
    .SAMPLE_BITS(SAMPLE_BITS),
    .INIT_FILE(INIT_FILE)
    ) u_wave_bram (
    .clk(clk),

    .wr_en(wave_wr_en),
    .wr_addr(wave_wr_addr),
    .wr_data(wave_wr_data),

    .rd_addr(dbg_lut_addr),
    .rd_data(dbg_raw_sample)
    );

    scaler #(
        .SAMPLE_BITS(SAMPLE_BITS)
    ) u_scaler (
        .sample_in(dbg_raw_sample),
        .amplitude_q15(cfg_amplitude_q15),
        .offset(cfg_offset),
        .sample_out(dbg_scaled_sample)
    );

    sigma_delta_1st #(
        .SAMPLE_BITS(SAMPLE_BITS),
        .ACC_BITS(20)
    ) u_sigma_delta (
        .clk(clk),
        .rst(rst),
        .enable(enable),
        .sample_in(dbg_scaled_sample),
        .sd_out(sd_out)
    );

endmodule

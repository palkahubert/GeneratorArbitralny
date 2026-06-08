//Copyright 1986-2018 Xilinx, Inc. All Rights Reserved.
//--------------------------------------------------------------------------------
//Tool Version: Vivado v.2018.3 (win64) Build 2405991 Thu Dec  6 23:38:27 MST 2018
//Date        : Mon Jun  8 16:04:55 2026
//Host        : DESKTOP-OEUP6RI running 64-bit major release  (build 9200)
//Command     : generate_target design_awg_wrapper.bd
//Design      : design_awg_wrapper
//Purpose     : IP block netlist
//--------------------------------------------------------------------------------
`timescale 1 ps / 1 ps

module design_awg_wrapper
   (clk_125MHz,
    reset_rtl_0,
    reset_rtl_0_0,
    sd_out_0,
    uart_rtl_0_rxd,
    uart_rtl_0_txd);
  input clk_125MHz;
  input reset_rtl_0;
  input reset_rtl_0_0;
  output sd_out_0;
  input uart_rtl_0_rxd;
  output uart_rtl_0_txd;

  wire clk_125MHz;
  wire reset_rtl_0;
  wire reset_rtl_0_0;
  wire sd_out_0;
  wire uart_rtl_0_rxd;
  wire uart_rtl_0_txd;

  design_awg design_awg_i
       (.clk_125MHz(clk_125MHz),
        .reset_rtl_0(reset_rtl_0),
        .reset_rtl_0_0(reset_rtl_0_0),
        .sd_out_0(sd_out_0),
        .uart_rtl_0_rxd(uart_rtl_0_rxd),
        .uart_rtl_0_txd(uart_rtl_0_txd));
endmodule

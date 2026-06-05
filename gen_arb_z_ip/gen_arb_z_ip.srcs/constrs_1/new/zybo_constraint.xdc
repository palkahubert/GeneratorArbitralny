## ============================================================
## Zybo Z7 - AWG MicroBlaze constraints
## Wrapper ports:
## clk_125MHz
## reset_rtl_0
## reset_rtl_0_0
## sd_out_0
## uart_rtl_0_rxd
## uart_rtl_0_txd
## ============================================================

## 125 MHz system clock
set_property -dict { PACKAGE_PIN K17 IOSTANDARD LVCMOS33 } [get_ports { clk_125MHz }]

## Do not use "-add" here. In the original project Vivado reported two
## equivalent clocks on the same clocking network: clk_125MHz and sys_clk_pin.
## That was not the main setup violation, but it caused confusing
## multiple-clock timing checks.
create_clock -name clk_125MHz -period 8.000 -waveform {0.000 4.000} [get_ports { clk_125MHz }]
set_input_jitter [get_clocks clk_125MHz] 0.080

## Reset inputs
## BTN0 and BTN1
set_property -dict { PACKAGE_PIN K18 IOSTANDARD LVCMOS33 } [get_ports { reset_rtl_0 }]
set_property -dict { PACKAGE_PIN P16 IOSTANDARD LVCMOS33 } [get_ports { reset_rtl_0_0 }]

## These are asynchronous human pushbuttons, so do not time them as normal data.
set_false_path -from [get_ports { reset_rtl_0 reset_rtl_0_0 }]

## Sigma-delta output
## Pmod JA1
set_property -dict { PACKAGE_PIN N15 IOSTANDARD LVCMOS33 } [get_ports { sd_out_0 }]

## sd_out_0 goes to a simple external 1-bit output / RC filter path, not to
## another synchronous device with a defined capture clock. Ignore external
## output timing for this port.
set_false_path -to [get_ports { sd_out_0 }]

## UARTLite
## Pmod JA2 / JA3
## FPGA TX -> USB-UART RX
## FPGA RX <- USB-UART TX
set_property -dict { PACKAGE_PIN L14 IOSTANDARD LVCMOS33 } [get_ports { uart_rtl_0_txd }]
set_property -dict { PACKAGE_PIN K16 IOSTANDARD LVCMOS33 } [get_ports { uart_rtl_0_rxd }]

## UART RX is asynchronous to the FPGA clock, and UART TX is not captured by a
## synchronous FPGA clock at the other end in this design.
set_false_path -from [get_ports { uart_rtl_0_rxd }]
set_false_path -to   [get_ports { uart_rtl_0_txd }]

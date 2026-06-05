# AWG FPGA - symulacja systemowa w SystemVerilog

Tor:
waveform.mem -> DDS/NCO adresujacy LUT -> skalowanie -> sigma-delta -> sd_out

## Vivado 2018.3

Dodaj:
- rtl/*.sv jako Design Sources
- tb/tb_awg_core.sv jako Simulation Source
- tb/waveform.mem jako Simulation Source albo skopiuj do katalogu symulacji

Dla plikow .sv ustaw File Type = SystemVerilog.
Simulation top: tb_awg_core.

Na razie nie ma pelnego AXI-Lite. Sygnaly cfg_* modeluja rejestry,
ktore pozniej beda wystawione przez AXI-Lite slave sterowany z MicroBlaze.

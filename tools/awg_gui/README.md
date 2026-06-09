# AWG Signal Forge

Static JavaScript GUI for generating 4096-point unsigned 16-bit waveforms and sending them to the MicroBlaze AWG over UART.

## Open

Use Chrome or Edge:

```powershell
cd C:\repos\GeneratorArbitralny\tools\awg_gui
python -m http.server 8765 --bind 127.0.0.1
```

Then open:

```text
http://127.0.0.1:8765/
```

Web Serial does not talk to `mdm_1`. It needs a normal serial COM device, so use `axi_uartlite_0` on the Pmod UART pins with a USB-UART adapter. Keep `mdm_1` for SDK debug prints.

If you do not have a USB-UART adapter, use **Export XSDB** or **Copy XSDB Config**. That path uses the existing programming/debug cable and writes AWG registers through Xilinx XSDB.

## UART Path

Current hardware:

- `mdm_1`: JTAG/debug UART through Xilinx tools
- `axi_uartlite_0`: physical UARTLite routed to Pmod JA
- `sd_out_0`: signal output

The GUI uses the browser Web Serial API, so it targets `axi_uartlite_0`, not `mdm_1`.

## No Adapter Path

For config-only changes:

1. Change frequency, `Gain Q0.16`, or `Offset raw` in the GUI.
2. Click **Copy XSDB Config**.
3. In Xilinx SDK, open the XSCT/XSDB console.
4. Paste the copied commands and press Enter.

For a new waveform:

1. Design the waveform in the GUI.
2. Click **Export XSDB**.
3. In Xilinx SDK XSCT/XSDB console, run:

```tcl
source C:/repos/GeneratorArbitralny/tools/awg_gui/awg_update.tcl
```

If the browser downloads the file elsewhere, use that downloaded path instead.

The generated script writes:

```text
0x44A00000 control
0x44A00004 phase_step
0x44A00008 offset/gain
0x44A0000C waveform write register
```

## Packet Format

All integers are little-endian.

```text
magic      4 bytes  ASCII "AWG1"
command    1 byte
length     2 bytes  payload byte count
payload    N bytes
checksum   2 bytes  uint16 sum(command + length bytes + payload bytes)
```

Commands:

```text
0x01 LOAD
payload: uint16 sample_count, then sample_count x uint16 samples

0x02 CONFIG
payload: uint32 phase_step, uint16 gain_q16, uint16 offset, uint8 enable

0x03 ENABLE
payload: uint8 enable

0x04 RESET
payload: empty

0x05 PING
payload: empty
```

For the current 100 MHz AWG clock:

```text
phase_step = round(output_frequency_hz * 2^32 / 100000000)
```

## Firmware

`microblaze_uart_receiver.c` is a reference replacement for the SDK `awg_gen/main.c`.

It:

- boots with the same default 1 kHz sine
- prints debug status through `xil_printf`
- listens for GUI packets on `XPAR_AXI_UARTLITE_0_BASEADDR`
- writes incoming samples to `REG_WAVE_WRITE`
- applies `phase_step`, gain, offset, and enable commands

At 9600 baud, a full 4096-sample waveform packet takes roughly 9 seconds to transmit. Use a higher UARTLite baud rate in Vivado if you want fast live updates.

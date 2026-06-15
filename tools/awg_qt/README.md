# AWG Signal Forge Qt

PyQt6 desktop version of `tools/awg_gui`. It generates the same 4096-point unsigned 16-bit waveform table and can update the FPGA through either XSDB/JTAG or the `AWG1` UART packet protocol.

## Requirements

- Python 3.13.13
- PyQt6
- pyserial

Install into your chosen environment:

```powershell
python -m pip install -r C:\repos\GeneratorArbitralny\tools\awg_qt\requirements.txt
```

## Run

```powershell
python C:\repos\GeneratorArbitralny\tools\awg_qt\awg_qt.py
```

By default the app uses **XSDB/JTAG single cable** mode. This talks through the same Xilinx cable/path used by Vivado or SDK and writes the AWG registers directly.

If `xsdb` is not in `PATH`, set **XSDB tool** to a full Xilinx tool path, for example:

```text
C:\Xilinx\SDK\2018.3\bin\xsdb.bat
```

or:

```text
C:\Xilinx\SDK\2018.3\bin\xsct.bat
```

Click **Check** to verify XSDB can connect and read the AWG control register. Click **Apply Config** to update frequency/gain/offset without changing samples. Click **Send Waveform** to write all 4096 samples and apply config. Less common actions such as reset, enable, and exports are under **More**.

The UART mode still exists for a separate USB-UART adapter connected to the MicroBlaze `axi_uartlite_0` pins. In the current Vivado design, that UART is routed to Pmod JA2/JA3, not the Zybo onboard USB-UART COM port.

## UART Packet Format

The packet format is unchanged from the JavaScript GUI:

```text
magic      4 bytes  ASCII "AWG1"
command    1 byte
length     2 bytes  payload byte count
payload    N bytes
checksum   2 bytes  uint16 sum(command + length bytes + payload bytes)
```

Commands:

```text
0x01 LOAD    uint16 sample_count, then sample_count x uint16 samples
0x02 CONFIG  uint32 phase_step, uint16 gain_q16, uint16 offset, uint8 enable
0x03 ENABLE  uint8 enable
0x04 RESET   empty
0x05 PING    empty
```

Use **Refresh** to enumerate COM ports, select the FPGA UART adapter, connect, then send the waveform or config.

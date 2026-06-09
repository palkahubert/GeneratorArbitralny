# AWG config update over Xilinx XSCT/XSDB.
# Edit these values, then run run_xsdb_set_config.bat.

set AWG_BASE      0x44A00000
set REG_CONTROL   [expr {$AWG_BASE + 0x00}]
set REG_PHASE     [expr {$AWG_BASE + 0x04}]
set REG_GAIN_OFF  [expr {$AWG_BASE + 0x08}]

# 100 MHz clock phase-step examples:
# 1 kHz  = 0x0000A7C6
# 2 kHz  = 0x00014F8B
# 5 kHz  = 0x000346DC
# 10 kHz = 0x00068DB9
set PHASE_STEP 0x0000A7C6

# Gain is Q0.16. 0xFFFF is unity/full-scale.
set GAIN_Q16 0xFFFF

# Offset is unsigned 16-bit and goes into the upper 16 bits of REG_GAIN_OFF.
set OFFSET 0x0000

set GAIN_OFFSET [expr {($OFFSET << 16) | $GAIN_Q16}]

connect -url tcp:127.0.0.1:3121
targets -set -nocase -filter {name =~ "microblaze*#0"} -index 1
configparams force-mem-access 1

mwr $REG_PHASE $PHASE_STEP
mwr $REG_GAIN_OFF $GAIN_OFFSET
mwr $REG_CONTROL 0x00000001

configparams force-mem-access 0
puts "AWG config written"

#include "xparameters.h"
#include "xil_io.h"
#include "xil_printf.h"
#include <stdint.h>

#define AWG_BASEADDR XPAR_AWG_AXI_0_S00_AXI_BASEADDR

#define REG_CONTROL     0x00u
#define REG_PHASE_STEP  0x04u
#define REG_GAIN_OFFSET 0x08u

#define CTRL_ENABLE     0x00000001u
#define CTRL_RESET      0x00000002u

#define PHASE_STEP_1KHZ 0x0000A7C6u
#define GAIN_UNITY_Q16  0xFFFFu

static void awg_reset(void)
{
    Xil_Out32(AWG_BASEADDR + REG_CONTROL, CTRL_RESET);
    Xil_Out32(AWG_BASEADDR + REG_CONTROL, 0x00000000u);
}

static void awg_config(uint32_t phase_step, uint16_t gain_q16, uint16_t offset)
{
    uint32_t gain_offset = ((uint32_t)offset << 16) | (uint32_t)gain_q16;

    Xil_Out32(AWG_BASEADDR + REG_PHASE_STEP, phase_step);
    Xil_Out32(AWG_BASEADDR + REG_GAIN_OFFSET, gain_offset);
}

static void awg_enable(void)
{
    Xil_Out32(AWG_BASEADDR + REG_CONTROL, CTRL_ENABLE);
}

static void start_default_waveform(void)
{
    awg_reset();
    awg_config(PHASE_STEP_1KHZ, GAIN_UNITY_Q16, 0u);
    awg_enable();
}

int main(void)
{
    start_default_waveform();

    xil_printf("\r\nAWG initialized with the default 1 kHz waveform.\r\n");
    xil_printf("Runtime control uses direct AXI register writes through XSDB/JTAG.\r\n");

    while (1) {
        /* XSDB/JTAG writes AWG registers independently of the CPU loop. */
    }

    return 0;
}

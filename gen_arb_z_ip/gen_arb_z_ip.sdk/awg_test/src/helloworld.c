#include "xparameters.h"
#include "xil_io.h"
#include <stdint.h>

#define AWG_BASEADDR XPAR_AWG_AXI_0_S00_AXI_BASEADDR

#define REG_CONTROL     0x00
#define REG_PHASE_STEP  0x04
#define REG_AMP_OFFSET  0x08
#define REG_WAVE_WRITE  0x0C

#define CTRL_ENABLE     0x00000001
#define CTRL_RESET      0x00000002

static uint32_t calc_phase_step(double fout, double fclk)
{
    return (uint32_t)((fout / fclk) * 4294967296.0);
}

static void awg_write_sample(uint16_t addr, int16_t sample)
{
    uint32_t word;
    word = ((uint32_t)(addr & 0x0FFF) << 16) | ((uint16_t)sample);
    Xil_Out32(AWG_BASEADDR + REG_WAVE_WRITE, word);
}

int main()
{
    uint32_t phase_step;
    uint32_t amp_offset;

    // Reset rdzenia AWG
    Xil_Out32(AWG_BASEADDR + REG_CONTROL, CTRL_RESET);
    Xil_Out32(AWG_BASEADDR + REG_CONTROL, 0x00000000);

    // Zaladowanie 4096 probek przebiegu trojkatnego do BRAM
    for (uint16_t i = 0; i < 4096; i++)
    {
        int32_t sample;

        if (i < 2048)
        {
            sample = -32768 + ((int32_t)i * 65535) / 2047;
        }
        else
        {
            sample = 32767 - ((int32_t)(i - 2048) * 65535) / 2047;
        }

        awg_write_sample(i, (int16_t)sample);
    }

    // f_clk AWG = 100 MHz, f_out = 1 kHz
    phase_step = calc_phase_step(1000.0, 100000000.0);

    // amplitude Q1.15 = 0x6000 ~= 0.75, offset = 0
    amp_offset = ((uint32_t)0x0000 << 16) | 0x6000;

    Xil_Out32(AWG_BASEADDR + REG_PHASE_STEP, phase_step);
    Xil_Out32(AWG_BASEADDR + REG_AMP_OFFSET, amp_offset);

    // Start generatora
    Xil_Out32(AWG_BASEADDR + REG_CONTROL, CTRL_ENABLE);

    while (1)
    {
        // Generator dziala sprzetowo w FPGA
    }

    return 0;
}

#include "xparameters.h"
#include "xil_io.h"
#include "xil_printf.h"
#include <stdint.h>

#define AWG_BASEADDR XPAR_AWG_AXI_0_S00_AXI_BASEADDR

#define REG_CONTROL     0x00
#define REG_PHASE_STEP  0x04
#define REG_AMP_OFFSET  0x08
#define REG_WAVE_WRITE  0x0C

#define CTRL_ENABLE     0x00000001
#define CTRL_RESET      0x00000002

#define AWG_DEPTH       4096

static void awg_write_sample(uint16_t addr, int16_t sample)
{
    uint32_t word;

    /*
     * REG_WAVE_WRITE:
     * bits [27:16] = address, 12 bit
     * bits [15:0]  = signed sample
     */
    word = ((uint32_t)(addr & 0x0FFF) << 16) | ((uint16_t)sample);

    Xil_Out32(AWG_BASEADDR + REG_WAVE_WRITE, word);
}

int main(void)
{
    static const int16_t wave16[16] = {
        -25000, -20000, -12000,  -4000,
          4000,  12000,  20000,  25000,
         25000,  20000,  12000,   4000,
         -4000, -12000, -20000, -25000
    };

    int addr;

    xil_printf("AWG SIM START\r\n");

    /*
     * Reset rdzenia AWG.
     * Bit 1 slv_reg0 = core reset.
     */
    Xil_Out32(AWG_BASEADDR + REG_CONTROL, CTRL_RESET);

    /*
     * Zwolnienie resetu rdzenia AWG, enable jeszcze = 0.
     */
    Xil_Out32(AWG_BASEADDR + REG_CONTROL, 0x00000000);

    /*
     * Wypelnienie CALEJ pamieci probek.
     *
     * To jest wazne w symulacji:
     * jezeli DDS odczyta niezapisany adres BRAM, dostanie X,
     * a potem X przejdzie przez scaler i sigma-delta na sd_out.
     */
    for (addr = 0; addr < AWG_DEPTH; addr++) {
        awg_write_sample((uint16_t)addr, wave16[addr & 0xF]);
    }

    /*
     * Dla ADDR_BITS = 12 adres LUT jest brany z gornych 12 bitow
     * 32-bitowego akumulatora fazy.
     *
     * 0x00100000 = 2^(32 - 12), czyli adres LUT rosnie o 1 na takt:
     * 0, 1, 2, 3, ...
     */
    Xil_Out32(AWG_BASEADDR + REG_PHASE_STEP, 0x00100000);

    /*
     * slv_reg2:
     * bits [15:0]  = amplitude_q15
     * bits [31:16] = offset
     *
     * 0x6000 to ok. 0.75 w Q1.15.
     * Offset = 0.
     */
    Xil_Out32(AWG_BASEADDR + REG_AMP_OFFSET, 0x00006000);

    /*
     * Start generatora.
     * Bit 0 slv_reg0 = enable.
     */
    Xil_Out32(AWG_BASEADDR + REG_CONTROL, CTRL_ENABLE);

    xil_printf("AWG ENABLED\r\n");

    while (1) {
        /*
         * Program zostaje tutaj, AWG dziala sprzetowo.
         */
    }

    return 0;
}

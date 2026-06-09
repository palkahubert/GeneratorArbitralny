#include "xparameters.h"
#include "xil_io.h"
#include "xil_printf.h"
#include <stdint.h>
#include <math.h>

#define AWG_BASEADDR XPAR_AWG_AXI_0_S00_AXI_BASEADDR

#define REG_CONTROL     0x00
#define REG_PHASE_STEP  0x04
#define REG_AMP_OFFSET  0x08
#define REG_WAVE_WRITE  0x0C

#define CTRL_ENABLE     0x00000001
#define CTRL_RESET      0x00000002

#define AWG_DEPTH       4096
#define PI              3.14159265358979323846

/*

 */
#define AWG_CLK_HZ      100000000.0
#define OUT_FREQ_HZ     1000.0

/*
 * phase_step = f_out * 2^32 / f_clk
 *
 * Dla:
 * f_out = 1 kHz
 * f_clk = 100 MHz
 *
 *
 */
#define PHASE_STEP_1KHZ 0x0000A7C6

/*
 * Amplituda prbek wpisywanych do BRAM.
 * Zakres int16_t to oko³o -32768 ... +32767.
 * Dajemy 25000, eby nie jechapo samych granicach zakresu.
 */
#define SAMPLE_AMPLITUDE 16000.0

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
    int addr;
    double angle;
    double s;
    int16_t sample;

    xil_printf("AWG 4096 SAMPLE SINE START\r\n");

    /*
     * Reset rdzenia AWG.
     * slv_reg0 bit 1 = core reset
     */
    Xil_Out32(AWG_BASEADDR + REG_CONTROL, CTRL_RESET);

    /*
     * Zwolnienie resetu.
     * enable jeszcze = 0.
     */
    Xil_Out32(AWG_BASEADDR + REG_CONTROL, 0x00000000);

    /*
     * Wypelnienie calej pamieci BRAM jednym pelnym okresem sinusa.
     *
     * BRAM[0]    = okolice 0
     * BRAM[1024] = dodatnie maksimum
     * BRAM[2048] = okolice 0
     * BRAM[3072] = ujemne maksimum
     * BRAM[4095] = powrot w okolice 0
     */
    for (addr = 0; addr < AWG_DEPTH; addr++) {
        angle = 2.0 * PI * (double)addr / (double)AWG_DEPTH;
        s = sin(angle);

        sample = (int16_t)(SAMPLE_AMPLITUDE * s);

        awg_write_sample((uint16_t)addr, sample);
    }

    xil_printf("BRAM LOADED WITH 4096 SAMPLES\r\n");

    /*
     * Ustawienie kroku fazy DDS.
     *
     * Dla jednego penego okresu sinusa w BRAM i zegara 100 MHz:
     *
     * phase_step = 0x0000A7C6 daje okoo 1 kHz.
     */
    Xil_Out32(AWG_BASEADDR + REG_PHASE_STEP, PHASE_STEP_1KHZ);

    /*
     * slv_reg2:
     * bits [15:0]  = amplitude_q15
     * bits [31:16] = offset
     *
     * 0x6000 = okolo 0.75 w Q1.15
     * offset = 0
     *
     * Czyli:
     * amplitude_q15 = 0x6000
     * offset        = 0x0000
     */
    Xil_Out32(AWG_BASEADDR + REG_AMP_OFFSET, 0x00003000);

    /*
     * Start generatora.
     * slv_reg0 bit 0 = enable
     */
    Xil_Out32(AWG_BASEADDR + REG_CONTROL, CTRL_ENABLE);

    xil_printf("AWG ENABLED\r\n");

    while (1) {
        /*
         * Program zostaje tutaj.
         * AWG dziaa dalej sprztowo.
         */
    }

    return 0;
}

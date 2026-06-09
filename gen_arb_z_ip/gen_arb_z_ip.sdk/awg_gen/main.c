#include "xparameters.h"
#include "xil_io.h"
#include "xil_printf.h"
#include "xuartlite_l.h"
#include <stdint.h>

#define AWG_BASEADDR XPAR_AWG_AXI_0_S00_AXI_BASEADDR
#define PC_UART_BASEADDR XPAR_AXI_UARTLITE_0_BASEADDR

#define REG_CONTROL     0x00
#define REG_PHASE_STEP  0x04
#define REG_GAIN_OFFSET 0x08
#define REG_WAVE_WRITE  0x0C

#define CTRL_ENABLE     0x00000001u
#define CTRL_RESET      0x00000002u

#define AWG_DEPTH       4096u
#define PHASE_STEP_1KHZ 0x0000A7C6u
#define GAIN_UNITY_Q16  0xFFFFu

#define CMD_LOAD        0x01u
#define CMD_CONFIG      0x02u
#define CMD_ENABLE      0x03u
#define CMD_RESET       0x04u
#define CMD_PING        0x05u

enum parser_state {
    RX_MAGIC_A,
    RX_MAGIC_W,
    RX_MAGIC_G,
    RX_MAGIC_1,
    RX_CMD,
    RX_LEN0,
    RX_LEN1,
    RX_PAYLOAD,
    RX_SUM0,
    RX_SUM1
};

static enum parser_state rx_state = RX_MAGIC_A;
static uint8_t rx_cmd = 0u;
static uint16_t rx_len = 0u;
static uint16_t rx_index = 0u;
static uint16_t rx_sum = 0u;
static uint16_t rx_expected_sum = 0u;

static uint16_t load_count = 0u;
static uint16_t load_addr = 0u;
static uint16_t sample_word = 0u;
static uint8_t cfg_payload[9];

static void awg_write_sample(uint16_t addr, uint16_t sample)
{
    uint32_t word = ((uint32_t)(addr & 0x0FFFu) << 16) | (uint32_t)sample;
    Xil_Out32(AWG_BASEADDR + REG_WAVE_WRITE, word);
}

static void awg_reset(void)
{
    Xil_Out32(AWG_BASEADDR + REG_CONTROL, CTRL_RESET);
    Xil_Out32(AWG_BASEADDR + REG_CONTROL, 0x00000000u);
}

static void awg_enable(uint8_t enable)
{
    Xil_Out32(AWG_BASEADDR + REG_CONTROL, enable ? CTRL_ENABLE : 0x00000000u);
}

static void awg_config(uint32_t phase_step, uint16_t gain_q16, uint16_t offset)
{
    uint32_t gain_offset = ((uint32_t)offset << 16) | (uint32_t)gain_q16;
    Xil_Out32(AWG_BASEADDR + REG_PHASE_STEP, phase_step);
    Xil_Out32(AWG_BASEADDR + REG_GAIN_OFFSET, gain_offset);
}

static void uart_putc(char c)
{
    XUartLite_SendByte(PC_UART_BASEADDR, (uint8_t)c);
}

static void uart_puts(const char *text)
{
    while (*text != '\0') {
        uart_putc(*text);
        text++;
    }
}

static int uart_getc_nonblocking(uint8_t *data)
{
    if (XUartLite_IsReceiveEmpty(PC_UART_BASEADDR)) {
        return 0;
    }

    *data = XUartLite_ReadReg(PC_UART_BASEADDR, XUL_RX_FIFO_OFFSET) & 0xFFu;
    return 1;
}

static uint16_t read_u16_le(const uint8_t *data)
{
    return (uint16_t)data[0] | ((uint16_t)data[1] << 8);
}

static uint32_t read_u32_le(const uint8_t *data)
{
    return (uint32_t)data[0] |
           ((uint32_t)data[1] << 8) |
           ((uint32_t)data[2] << 16) |
           ((uint32_t)data[3] << 24);
}

static void parser_reset(void)
{
    rx_state = RX_MAGIC_A;
    rx_cmd = 0u;
    rx_len = 0u;
    rx_index = 0u;
    rx_sum = 0u;
    rx_expected_sum = 0u;
    load_count = 0u;
    load_addr = 0u;
    sample_word = 0u;
}

static void process_payload_byte(uint8_t byte)
{
    if (rx_cmd == CMD_LOAD) {
        if (rx_index == 0u) {
            load_count = byte;
        } else if (rx_index == 1u) {
            load_count |= ((uint16_t)byte << 8);
            if (load_count > AWG_DEPTH) {
                load_count = AWG_DEPTH;
            }
        } else {
            if (((rx_index - 2u) & 1u) == 0u) {
                sample_word = byte;
            } else {
                sample_word |= ((uint16_t)byte << 8);
                if (load_addr < load_count) {
                    awg_write_sample(load_addr, sample_word);
                    load_addr++;
                }
            }
        }
    } else if (rx_cmd == CMD_CONFIG && rx_index < sizeof(cfg_payload)) {
        cfg_payload[rx_index] = byte;
    } else if (rx_cmd == CMD_ENABLE && rx_index == 0u) {
        cfg_payload[0] = byte;
    }
}

static void process_packet_done(uint8_t checksum_ok)
{
    if (!checksum_ok) {
        uart_puts("N checksum\r\n");
        xil_printf("UART packet checksum error\r\n");
        return;
    }

    if (rx_cmd == CMD_LOAD) {
        uart_puts("A load\r\n");
        xil_printf("Loaded waveform samples: %d\r\n", load_addr);
    } else if (rx_cmd == CMD_CONFIG && rx_len == 9u) {
        uint32_t phase_step = read_u32_le(&cfg_payload[0]);
        uint16_t gain_q16 = read_u16_le(&cfg_payload[4]);
        uint16_t offset = read_u16_le(&cfg_payload[6]);
        uint8_t enable = cfg_payload[8];

        awg_config(phase_step, gain_q16, offset);
        awg_enable(enable);

        uart_puts("A config\r\n");
        xil_printf("Config phase=0x%08x gain=%d offset=%d enable=%d\r\n",
                   (unsigned int)phase_step, gain_q16, offset, enable);
    } else if (rx_cmd == CMD_ENABLE && rx_len == 1u) {
        awg_enable(cfg_payload[0] != 0u);
        uart_puts("A enable\r\n");
        xil_printf("Enable=%d\r\n", cfg_payload[0] != 0u);
    } else if (rx_cmd == CMD_RESET && rx_len == 0u) {
        awg_reset();
        uart_puts("A reset\r\n");
        xil_printf("AWG reset\r\n");
    } else if (rx_cmd == CMD_PING && rx_len == 0u) {
        uart_puts("A pong\r\n");
        xil_printf("Ping\r\n");
    } else {
        uart_puts("N command\r\n");
        xil_printf("Unknown UART command\r\n");
    }
}

static void parser_accept(uint8_t byte)
{
    switch (rx_state) {
    case RX_MAGIC_A:
        rx_state = (byte == 'A') ? RX_MAGIC_W : RX_MAGIC_A;
        break;
    case RX_MAGIC_W:
        rx_state = (byte == 'W') ? RX_MAGIC_G : RX_MAGIC_A;
        break;
    case RX_MAGIC_G:
        rx_state = (byte == 'G') ? RX_MAGIC_1 : RX_MAGIC_A;
        break;
    case RX_MAGIC_1:
        rx_state = (byte == '1') ? RX_CMD : RX_MAGIC_A;
        break;
    case RX_CMD:
        rx_cmd = byte;
        rx_sum = byte;
        rx_index = 0u;
        rx_state = RX_LEN0;
        break;
    case RX_LEN0:
        rx_len = byte;
        rx_sum = (rx_sum + byte) & 0xFFFFu;
        rx_state = RX_LEN1;
        break;
    case RX_LEN1:
        rx_len |= ((uint16_t)byte << 8);
        rx_sum = (rx_sum + byte) & 0xFFFFu;
        rx_state = (rx_len == 0u) ? RX_SUM0 : RX_PAYLOAD;
        break;
    case RX_PAYLOAD:
        process_payload_byte(byte);
        rx_sum = (rx_sum + byte) & 0xFFFFu;
        rx_index++;
        if (rx_index >= rx_len) {
            rx_state = RX_SUM0;
        }
        break;
    case RX_SUM0:
        rx_expected_sum = byte;
        rx_state = RX_SUM1;
        break;
    case RX_SUM1:
        rx_expected_sum |= ((uint16_t)byte << 8);
        process_packet_done(rx_sum == rx_expected_sum);
        parser_reset();
        break;
    default:
        parser_reset();
        break;
    }
}

static void uart_service(void)
{
    uint8_t byte;
    while (uart_getc_nonblocking(&byte)) {
        parser_accept(byte);
    }
}

static void start_default_waveform(void)
{
    awg_reset();
    awg_config(PHASE_STEP_1KHZ, GAIN_UNITY_Q16, 0u);
    awg_enable(1u);
}

int main(void)
{
    start_default_waveform();

    xil_printf("\r\nAWG live UART receiver ready, using waveform.mem at boot\r\n");
    xil_printf("Debug console: mdm_1, GUI data UART: axi_uartlite_0\r\n");
    uart_puts("A ready\r\n");

    while (1) {
        uart_service();
    }

    return 0;
}

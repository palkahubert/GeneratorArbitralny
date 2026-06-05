`timescale 1ns/1ps

module tb_design_awg;

    reg clk_125MHz;
    reg reset_rtl_0;
    reg reset_rtl_0_0;
    reg uart_rtl_0_rxd;

    wire sd_out_0;
    wire uart_rtl_0_txd;

    initial begin
        clk_125MHz = 1'b0;
    end

    // 125 MHz => okres 8 ns
    always #4 clk_125MHz = ~clk_125MHz;

    design_awg_wrapper dut (
        .clk_125MHz      (clk_125MHz),
        .reset_rtl_0     (reset_rtl_0),
        .reset_rtl_0_0   (reset_rtl_0_0),
        .sd_out_0        (sd_out_0),
        .uart_rtl_0_rxd  (uart_rtl_0_rxd),
        .uart_rtl_0_txd  (uart_rtl_0_txd)
    );

    initial begin
        // UART RX w stanie idle
        uart_rtl_0_rxd = 1'b1;

        // UWAGA: w design_awg.v polaryzacje resetow sa rozne:
        //   reset_rtl_0   = ACTIVE_LOW,  wiec 0 oznacza reset aktywny
        //   reset_rtl_0_0 = ACTIVE_HIGH, wiec 1 oznacza reset aktywny
        reset_rtl_0   = 1'b0;
        reset_rtl_0_0 = 1'b1;

        // W symulacji Clocking Wizard potrafi nie wystawic locked tak,
        // jak oczekuje Processor System Reset. Wymuszamy locked = 1,
        // aby MicroBlaze i magistrala AXI mogly wyjsc z resetu.
        // Gdyby Vivado zglosil blad sciezki, znajdz w hierarchii sygnal
        // locked/dcm_locked od clk_wiz_1 i dopasuj ponizsza sciezke.
        force dut.design_awg_i.clk_wiz_1_locked = 1'b1;

        // 2 us resetu na starcie
        #2000;

        // Puszczenie resetow:
        //   ACTIVE_LOW  reset_rtl_0   musi isc na 1
        //   ACTIVE_HIGH reset_rtl_0_0 musi isc na 0
        reset_rtl_0   = 1'b1;
        reset_rtl_0_0 = 1'b0;

        // MicroBlaze potrzebuje czasu na start, wykonanie programu
        // i zapis rejestrow AWG przez AXI. 5 ms to bezpieczny czas testu.
        #5000000;

        $finish;
    end

endmodule
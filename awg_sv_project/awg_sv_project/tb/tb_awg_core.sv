`timescale 1ns/1ps
module tb_awg_core;

    localparam integer PHASE_BITS  = 32;
    localparam integer ADDR_BITS   = 10;
    localparam integer SAMPLE_BITS = 16;

    localparam real CLK_FREQ_HZ = 1000000.0;
    localparam real F_OUT_HZ    = 1000.0;
    localparam integer CLK_PERIOD_NS = 1000;

    reg clk = 1'b0;
    reg rst = 1'b1;
    reg enable = 1'b0;

    reg [PHASE_BITS-1:0] cfg_phase_step;
    reg signed [15:0] cfg_amplitude_q15;
    reg signed [SAMPLE_BITS-1:0] cfg_offset;

    wire sd_out;
    wire [ADDR_BITS-1:0] dbg_lut_addr;
    wire signed [SAMPLE_BITS-1:0] dbg_raw_sample;
    wire signed [SAMPLE_BITS-1:0] dbg_scaled_sample;
    wire [PHASE_BITS-1:0] dbg_phase_acc;

    integer fd;
    integer i;

    function [31:0] calc_phase_step;
        input real f_out;
        input real f_clk;
        real tmp;
        begin
            tmp = (f_out / f_clk) * 4294967296.0;
            calc_phase_step = $rtoi(tmp);
        end
    endfunction

    awg_core #(
        .PHASE_BITS(PHASE_BITS),
        .ADDR_BITS(ADDR_BITS),
        .SAMPLE_BITS(SAMPLE_BITS),
        .INIT_FILE("waveform.mem")
    ) dut (
        .clk(clk),
        .rst(rst),
        .enable(enable),
        .cfg_phase_step(cfg_phase_step),
        .cfg_amplitude_q15(cfg_amplitude_q15),
        .cfg_offset(cfg_offset),
        .sd_out(sd_out),
        .dbg_lut_addr(dbg_lut_addr),
        .dbg_raw_sample(dbg_raw_sample),
        .dbg_scaled_sample(dbg_scaled_sample),
        .dbg_phase_acc(dbg_phase_acc)
    );

    always #(CLK_PERIOD_NS/2) clk = ~clk;

    initial begin
        fd = $fopen("awg_output.csv", "w");
        $fwrite(fd, "n,addr,raw_sample,scaled_sample,sd_out\n");

        cfg_phase_step    = calc_phase_step(F_OUT_HZ, CLK_FREQ_HZ);
        cfg_amplitude_q15 = 16'sh6000;
        cfg_offset        = 16'sd0;

        repeat (10) @(posedge clk);
        rst <= 1'b0;
        enable <= 1'b1;

        for (i = 0; i < 5000; i = i + 1) begin
            @(posedge clk);
            $fwrite(fd, "%0d,%0d,%0d,%0d,%0d\n",
                    i, dbg_lut_addr, dbg_raw_sample, dbg_scaled_sample, sd_out);
        end

        cfg_amplitude_q15 <= 16'sh3000;

        for (i = 5000; i < 8000; i = i + 1) begin
            @(posedge clk);
            $fwrite(fd, "%0d,%0d,%0d,%0d,%0d\n",
                    i, dbg_lut_addr, dbg_raw_sample, dbg_scaled_sample, sd_out);
        end

        $fclose(fd);
        $display("Koniec symulacji. Wyniki zapisane w awg_output.csv");
        $finish;
    end

endmodule

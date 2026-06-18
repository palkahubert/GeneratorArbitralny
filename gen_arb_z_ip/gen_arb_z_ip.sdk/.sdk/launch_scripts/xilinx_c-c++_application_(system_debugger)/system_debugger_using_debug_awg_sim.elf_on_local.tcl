connect -url tcp:127.0.0.1:3121
targets -set -nocase -filter {name =~"APU*" && jtag_cable_name =~ "Digilent Zybo Z7 210351A6C862A"} -index 0
loadhw -hw C:/Users/palka/Documents/SDUP/sdup_projekt/sdup_projekt/gen_arb_z_ip/gen_arb_z_ip.sdk/design_awg_wrapper_hw_platform_0/system.hdf -mem-ranges [list {0x40000000 0xbfffffff}]
configparams force-mem-access 1
configparams mdm-detect-bscan-mask 2
targets -set -nocase -filter {name =~ "microblaze*#0" && bscan=="USER2"  && jtag_cable_name =~ "Digilent Zybo Z7 210351A6C862A"} -index 1
rst -processor
targets -set -nocase -filter {name =~ "microblaze*#0" && bscan=="USER2"  && jtag_cable_name =~ "Digilent Zybo Z7 210351A6C862A"} -index 1
dow C:/Users/palka/Documents/SDUP/sdup_projekt/sdup_projekt/gen_arb_z_ip/gen_arb_z_ip.sdk/awg_sim/Debug/awg_sim.elf
configparams force-mem-access 0
targets -set -nocase -filter {name =~ "microblaze*#0" && bscan=="USER2"  && jtag_cable_name =~ "Digilent Zybo Z7 210351A6C862A"} -index 1
con

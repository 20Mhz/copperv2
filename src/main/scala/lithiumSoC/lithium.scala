package lithium

import chisel3._
import wishbone._

class LithiumSoC extends Module with RequireSyncReset {
  val cpu_config = new copperv2.Copperv2Config()
  val wb_i = IO(new WishboneSource(cpu_config.addr_width,cpu_config.data_width))
  val wb_d = IO(new WishboneSource(cpu_config.addr_width,cpu_config.data_width))
  val cpu = Module(new copperv2.Copperv2Core(cpu_config))
  val wb_bridge = Module(new WishboneBridge(cpu_config.addr_width,cpu_config.data_width,cpu_config.resp_width))
  cpu.bus <> wb_bridge.cpu_bus
  wb_i <> wb_bridge.wb_i_bus
  wb_d <> wb_bridge.wb_d_bus
}

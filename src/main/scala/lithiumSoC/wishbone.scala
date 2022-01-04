package lithium

import chisel3._
import dataclass.data

class WishboneSource(addr_width: Int, data_width: Int) extends Bundle {
  val sel_width = data_width / 8
  val adr = Output(UInt(addr_width.W))
  val datwr = Output(UInt(data_width.W))
  val datrd = Input(UInt(data_width.W))
  val we = Output(Bool())
  val cyc = Output(Bool())
  val stb = Output(Bool())
  val ack = Input(Bool())
  val sel = Output(UInt(sel_width.W))
}

class WishboneAdapter(addr_width: Int, data_width: Int, resp_width: Int = 0) extends Module with RequireSyncReset {
  val bus = IO(new Bundle {
    val w = Flipped(new copperv2.WriteChannel(addr_width=addr_width,data_width=addr_width,resp_width=resp_width))
    val r = Flipped(new copperv2.ReadChannel(addr_width=addr_width,data_width=addr_width))
  })
  val wb = IO(new WishboneSource(addr_width=addr_width,data_width=data_width))
  bus.w.req.ready := RegInit(1.B)
  bus.w.resp.valid := 0.B
  bus.w.resp.bits := 0.B
  bus.r.addr.ready := RegInit(1.B)
  bus.r.data.valid := 0.B
  bus.r.data.bits := 0.B
  wb.datwr := 0.B
  wb.adr := 0.B
  wb.sel := 0.B
  wb.we := 0.B
  wb.cyc := 0.B
  wb.stb := 0.B
}

class WishboneBridge(addr_width: Int, data_width: Int, resp_width: Int) extends Module with RequireSyncReset {
  val cpu_bus = IO(new copperv2.CoppervBusSink(addr_width,data_width,resp_width))
  val wb_d_bus = IO(new WishboneSource(addr_width,data_width))
  val wb_i_bus = IO(new WishboneSource(addr_width,data_width))
  val d_adapter = Module(new WishboneAdapter(addr_width,data_width,resp_width))
  val i_adapter = Module(new WishboneAdapter(addr_width,data_width))
  cpu_bus.dr <> d_adapter.bus.r
  cpu_bus.ir <> i_adapter.bus.r
  cpu_bus.dw <> d_adapter.bus.w
  0.U.asTypeOf(i_adapter.bus.w) <> i_adapter.bus.w
  wb_d_bus <> d_adapter.wb
  wb_i_bus <> i_adapter.wb
}


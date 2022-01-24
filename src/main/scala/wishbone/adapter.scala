package wishbone

import chisel3._
import dataclass.data

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
  val wb_datwr = Reg(UInt())
  val wb_adr = Reg(UInt())
  val wb_sel = Reg(UInt())
  val wb_we = RegInit(0.B)
  val wb_cyc = RegInit(0.B)
  val wb_stb = RegInit(0.B)
  wb.datwr := wb_datwr
  wb.adr := wb_adr
  wb.sel := wb_sel
  wb.we := wb_we
  wb.cyc := wb_cyc
  wb.stb := wb_stb
  when(bus.r.req.fire){
    wb_adr := bus.r.req.bits
    wb_we := 0.B
    wb_cyc := 1.B
    wb_stb := 1.B
  }.elsewhen(bus.w.req.fire){
    wb_adr := bus.w.req.bits.addr
    wb_datwr := bus.w.req.bits.data
    wb_sel := bus.w.req.bits.strobe
    wb_we := 1.B
    wb_cyc := 1.B
    wb_stb := 1.B
  }
  when(wb.ack){
    wb_cyc := 0.B
    wb_stb := 0.B
    when(wb.we){
      bus.w.resp.enq(1.B)
    }.otherwise {
      bus.r.resp.enq(wb.datrd)
    }
  }
  val bus_w_resp_fire = RegNext(bus.w.resp.fire)
  when(bus_w_resp_fire) {
    bus.w.resp.noenq()
  }
  val bus_r_resp_fire = RegNext(bus.r.resp.fire)
  when(bus_r_resp_fire) {
    bus.r.resp.noenq()
  }
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


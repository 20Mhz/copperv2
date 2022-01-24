package copperv2

import chisel3._
import chisel3.util.{Decoupled,MuxLookup,Cat}
import chisel3.stage.{ChiselStage, ChiselGeneratorAnnotation}
import chisel3.internal.requireIsChiselType
import chisel3.experimental.dataview._
import chisel3.util.DecoupledIO

class Copperv2Config {
  val pc_init: Int = 0
  val addr_width: Int = 32
  val data_width: Int = 32
  val resp_width: Int = 1
}

class ReadChannel(addr_width: Int, data_width: Int) extends Bundle {
  def req = addr
  def resp = data
  // Output
  val addr = Decoupled(UInt(addr_width.W))
  // Input
  val data = Flipped(Decoupled(UInt(data_width.W)))
}

class WriteChannel(addr_width: Int, data_width: Int, resp_width: Int) extends Bundle {
  // Output
  val req = Decoupled(new Bundle {
    val strobe_width = data_width / 8
    val data = UInt(data_width.W)
    val addr = UInt(addr_width.W)
    val strobe = UInt(strobe_width.W)
  })
  // Input
  val resp = Flipped(Decoupled(UInt(resp_width.W)))
}

class VerilogCoppervBusSource(val addr_width: Int, val data_width: Int, val resp_width: Int) extends Bundle {
  val ir_data_valid = Input(Bool())
  val ir_addr_ready = Input(Bool())
  val ir_data = Input(UInt(data_width.W))
  val dr_data_valid = Input(Bool())
  val dr_addr_ready = Input(Bool())
  val dw_data_addr_ready = Input(Bool())
  val dw_resp_valid = Input(Bool())
  val dr_data = Input(UInt(data_width.W))
  val dw_resp = Input(UInt(resp_width.W))
  val ir_data_ready = Output(Bool())
  val ir_addr_valid = Output(Bool())
  val ir_addr = Output(UInt(addr_width.W))
  val dr_data_ready = Output(Bool())
  val dr_addr_valid = Output(Bool())
  val dw_data_addr_valid = Output(Bool())
  val dw_resp_ready = Output(Bool())
  val dr_addr = Output(UInt(addr_width.W))
  val dw_data = Output(UInt(data_width.W))
  val dw_addr = Output(UInt(addr_width.W))
  val dw_strobe = Output(UInt((data_width / 8).W))
}

class CoppervBusSource(val addr_width: Int, val data_width: Int, val resp_width: Int) extends Bundle {
  val ir = new ReadChannel(addr_width=addr_width,data_width=addr_width)
  val dr = new ReadChannel(addr_width=addr_width,data_width=addr_width)
  val dw = new WriteChannel(addr_width=addr_width,data_width=addr_width,resp_width=resp_width)
  def read_instruction(addr: UInt, addr_valid: Bool): (UInt,Bool) = {
    val inst = Reg(UInt())
    val inst_valid = RegInit(0.B)
    ir.addr.bits := 0.U
    ir.addr.valid := addr_valid
    ir.data.ready := 1.B
    when (ir.addr.ready) {
        ir.addr.bits := addr
    }
    when (ir.data.fire) {
        inst := ir.data.bits
        inst_valid := 1.B
    } .otherwise {
        inst_valid := 0.B
    }
    return (inst,inst_valid)
  }
  def write_data(write_addr: UInt, write_data: UInt, write_strobe: UInt,write_data_valid: Bool): Bool = {
    val dw_addr = RegInit(0.U)
    val dw_data = RegInit(0.U)
    val dw_strobe = RegInit(0.U)
    val dw_req_valid = RegInit(0.B)
    when (write_data_valid) {
        dw_addr := Cat(write_addr(31,2),0.U(2.W))
        dw_data := write_data
        dw_strobe := write_strobe
        dw_req_valid := 1.B
    } .otherwise {
        dw_req_valid := 0.B
    }
    dw.req.bits.addr := dw_addr
    dw.req.bits.data := dw_data
    dw.req.bits.strobe := dw_strobe
    dw.req.valid := dw_req_valid
    val write_valid = RegInit(0.B)
    when (dw.resp.fire) {
        write_valid := MuxLookup(dw.resp.bits,false.B,Array(
            0.U -> false.B,
            1.U -> true.B
          ))
    } .otherwise {
        write_valid := 0.B
    }
    val dw_resp_ready = RegInit(1.B)
    dw.resp.ready := dw_resp_ready
    return write_valid
  }
  def read_data(read_addr: UInt,addr_valid: Bool): (UInt,Bool) = {
    val dr_addr = RegInit(0.U)
    val dr_addr_valid = RegInit(0.U)
    when (addr_valid) {
      dr_addr := read_addr(31,2) << 2.U
      dr_addr_valid := 1.B
    } .otherwise {
      dr_addr_valid := 0.B
    }
    dr.addr.bits := dr_addr
    dr.addr.valid := dr_addr_valid
    val read_data = RegInit(0.U)
    val read_valid = RegInit(0.B)
    when (dr.data.fire) {
      read_data := dr.data.bits
      read_valid := 1.B
    } .otherwise {
      read_valid := 0.B
    }
    val dr_data_ready = RegInit(1.B)
    dr.data.ready := dr_data_ready
    return (read_data,read_valid)
  }
}

class CoppervBusSink(addr_width: Int, data_width: Int, resp_width: Int) extends Bundle {
  val ir = Flipped(new ReadChannel(addr_width=addr_width,data_width=addr_width))
  val dr = Flipped(new ReadChannel(addr_width=addr_width,data_width=addr_width))
  val dw = Flipped(new WriteChannel(addr_width=addr_width,data_width=addr_width,resp_width=resp_width))
}

object CoppervBusSource {
  implicit val busView = PartialDataView[VerilogCoppervBusSource, CoppervBusSource](
    vcb => new CoppervBusSource(vcb.addr_width,vcb.data_width,vcb.resp_width),
    _.ir_addr_ready -> _.ir.addr.ready,
    _.ir_addr_valid -> _.ir.addr.valid,
    _.ir_addr       -> _.ir.addr.bits,
    _.ir_data_ready -> _.ir.data.ready,
    _.ir_data_valid -> _.ir.data.valid,
    _.ir_data       -> _.ir.data.bits,
    _.dr_addr_ready -> _.dr.addr.ready,
    _.dr_addr_valid -> _.dr.addr.valid,
    _.dr_addr       -> _.dr.addr.bits,
    _.dr_data_ready -> _.dr.data.ready,
    _.dr_data_valid -> _.dr.data.valid,
    _.dr_data       -> _.dr.data.bits,
    _.dw_data_addr_ready -> _.dw.req.ready,
    _.dw_data_addr_valid -> _.dw.req.valid,
    _.dw_data            -> _.dw.req.bits.data,
    _.dw_addr            -> _.dw.req.bits.addr,
    _.dw_strobe          -> _.dw.req.bits.strobe,
    _.dw_resp_ready      -> _.dw.resp.ready,
    _.dw_resp_valid      -> _.dw.resp.valid,
    _.dw_resp            -> _.dw.resp.bits
  )
}

class Copperv2(config: Copperv2Config = new Copperv2Config()) extends RawModule {
  val clk = IO(Input(Clock()))
  val rst = IO(Input(Bool()))
  val io = IO(new VerilogCoppervBusSource(config.addr_width,config.data_width,config.resp_width)).suggestName("bus")
  val bus = io.viewAs[CoppervBusSource]
  withClockAndReset(clk,!rst) {
    val control = Module(new ControlUnit)
    val idec = Module(new idecoder)
    val regfile = Module(new RegFile)
    val alu = Module(new Alu)
    val inst_fetch = Wire(Bool())
    val pc = RegInit(config.pc_init.U)
    val pc_en = control.io.pc_next_sel =/= PcNextSel.STALL
    val pc_next = MuxLookup(control.io.pc_next_sel.asUInt,pc,Array(
      PcNextSel.STALL.asUInt -> pc,
      PcNextSel.INCR.asUInt -> (pc + 4.U),
      PcNextSel.ADD_IMM.asUInt -> (pc + idec.io.imm),
      PcNextSel.ADD_RS1_IMM.asUInt -> (regfile.io.rs1_dout + idec.io.imm),
    ))
    when (pc_en) {
      pc := pc_next
    }
    val (inst_type,inst_type_valid) = InstType.safe(idec.io.inst_type)
    control.io.inst_type := inst_type
    control.io.alu_comp := alu.io.comp
    val (funct,funct_valid) = Funct.safe(idec.io.funct)
    control.io.funct := funct
    inst_fetch := control.io.inst_fetch
    regfile.io.rd_en := control.io.rd_en
    regfile.io.rs1_en := control.io.rs1_en
    regfile.io.rs2_en := control.io.rs2_en
    regfile.io.rd := idec.io.rd
    regfile.io.rs1 := idec.io.rs1
    regfile.io.rs2 := idec.io.rs2
    val write_addr = alu.io.dout
    val write_offset = write_addr(1,0)
    val write_strobe = WireDefault(0.U(4.W))
    val write_data = WireDefault(0.U)
    when (idec.io.funct === 9.U) {
      write_strobe := "b0001".U << write_offset
      write_data   := regfile.io.rs2_dout(7,0) << (write_offset << 3.U)
    } .elsewhen(idec.io.funct === 10.U) {
      write_strobe := "b0011".U << write_offset
      write_data   := regfile.io.rs2_dout(15,0) << (write_offset << 3.U)
    } .elsewhen(idec.io.funct === 11.U) {
      write_strobe := "b1111".U
      write_data   := regfile.io.rs2_dout
    }
    val read_addr = alu.io.dout
    val dw_req_fire = control.io.store_data && bus.dw.req.ready
    val dr_req_fire = control.io.load_data && bus.dr.addr.ready
    val (inst,inst_valid) = bus.read_instruction(pc,inst_fetch)
    val write_valid = bus.write_data(write_addr,write_data,write_strobe,dw_req_fire)
    val (read_data,read_valid) = bus.read_data(read_addr,dr_req_fire)
    idec.io.inst := inst
    control.io.inst_valid := inst_valid
    control.io.data_valid := write_valid || read_valid
    val read_offset = Reg(UInt(2.W))
    when (control.io.load_data) {
      read_offset := read_addr(1,0)
    }
    val read_data_t = (read_data >> (read_offset << 3))
    val ext_read_data = MuxLookup(idec.io.funct,0.S(32.W),Array(
      Funct.MEM_BYTE.asUInt -> read_data_t(7,0).asSInt,
      Funct.MEM_HWORD.asUInt -> read_data_t(15,0).asSInt,
      Funct.MEM_WORD.asUInt -> read_data_t.asSInt,
      Funct.MEM_BYTEU.asUInt -> read_data_t(7,0).zext,
      Funct.MEM_HWORDU.asUInt -> read_data_t(15,0).zext,
    )).asUInt
    regfile.io.rd_din := MuxLookup(control.io.rd_din_sel.asUInt,idec.io.imm,Array(
      RdDinSel.NONE.asUInt -> 0.U,
      RdDinSel.IMM.asUInt -> idec.io.imm,
      RdDinSel.ALU.asUInt -> alu.io.dout,
      RdDinSel.MEM.asUInt -> ext_read_data
    ))
    alu.io.op := control.io.alu_op
    alu.io.load := control.io.alu_load
    alu.io.din1 := MuxLookup(control.io.alu_din1_sel.asUInt,regfile.io.rs1_dout,Array(
      AluDin1Sel.RS1.asUInt -> regfile.io.rs1_dout,
      AluDin1Sel.PC.asUInt -> pc,
    ))
    alu.io.din2 := MuxLookup(control.io.alu_din2_sel.asUInt,regfile.io.rs2_dout,Array(
      AluDin2Sel.IMM.asUInt -> idec.io.imm,
      AluDin2Sel.RS2.asUInt -> regfile.io.rs2_dout,
      AluDin2Sel.CONST_4.asUInt -> 4.U,
    )) 
  }
}

class Copperv2Core(config: Copperv2Config = new Copperv2Config()) extends Module {
  val bus = IO(new CoppervBusSource(config.addr_width,config.data_width,config.resp_width))
  val cpu = Module(new Copperv2(config))
  cpu.clk := clock
  cpu.rst := ~reset.asBool
  cpu.bus <> bus
}

object Copperv2Driver extends App {
  val verilog_args = Array("--target-dir", "work/rtl") ++ args
  (new ChiselStage).emitVerilog(new copperv2.Copperv2, verilog_args ++ Array("-o","copperv2.v"))
//  (new ChiselStage).execute(Array("--emit-modules", "verilog"),Seq(ChiselGeneratorAnnotation(() => new copperv2.copperv2)))
  (new ChiselStage).emitVerilog(new wishbone.WishboneAdapter(32,32,1), verilog_args ++ Array("-o","wb_adapter.v"))
  (new ChiselStage).emitVerilog(new lithium.LithiumSoC, verilog_args ++ Array("-o","lithium_top.v"))
}

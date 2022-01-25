
import chisel3.stage.{ChiselStage, ChiselGeneratorAnnotation}

object Copperv2Driver extends App {
  val verilog_args = Array("--target-dir", "work/rtl") ++ args
  (new ChiselStage).emitVerilog(new copperv2.Copperv2, verilog_args ++ Array("-o","copperv2.v"))
//  (new ChiselStage).execute(Array("--emit-modules", "verilog"),Seq(ChiselGeneratorAnnotation(() => new copperv2.copperv2)))
  (new ChiselStage).emitVerilog(new wishbone.WishboneAdapter(32,32,1), verilog_args ++ Array("-o","wb_adapter.v"))
//  (new ChiselStage).emitVerilog(new copperv2.CoppervSoC, verilog_args ++ Array("-o","copperv_soc_top.v"))
  (new ChiselStage).emitVerilog(new wishbone.CrossBar(2), verilog_args ++ Array("-o","crossbar.v"))
}

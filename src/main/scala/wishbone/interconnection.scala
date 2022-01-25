package wishbone

import chisel3._
import chisel3.util.HasBlackBoxResource

class CrossBar(val source_number: Int) extends RawModule {
  val io = IO(new Bundle {
    val i_mcyc = Input(UInt(source_number.W))
  })
  val xbar = Module(new wxbar(source_number))
  xbar.io.i_mcyc := io.i_mcyc
}

class wxbar(val NM: Int) extends BlackBox(Map("NM" -> NM)) with HasBlackBoxResource {
  val io = IO(new Bundle {
    //    val out = Output(UInt(64.W))

    val i_clk = Input(Clock())
    val i_reset = Input(Reset())
    val i_mcyc = Input(UInt(NM.W))
//		input	wire	[NM-1:0]	, i_mstb, i_mwe,
//		input	wire	[NM*AW-1:0]	i_maddr,
//		input	wire	[NM*DW-1:0]	i_mdata,
//		input	wire	[NM*DW/8-1:0]	i_msel,
//		//
//		// .... and their return data
//		output	wire	[NM-1:0]	o_mstall,
//		output	wire	[NM-1:0]	o_mack,
//		output	reg	[NM*DW-1:0]	o_mdata,
//		output	reg	[NM-1:0]	o_merr,
//		//
//		//
//		// Here are the output ports, used to control each of the
//		// various slave ports that we are connected to
//		output	reg	[NS-1:0]	o_scyc, o_sstb, o_swe,
//		output	reg	[NS*AW-1:0]	o_saddr,
//		output	reg	[NS*DW-1:0]	o_sdata,
//		output	reg	[NS*DW/8-1:0]	o_ssel,
//		//
//		// ... and their return data back to us.
//		input	wire	[NS-1:0]	i_sstall, i_sack,
//		input	wire	[NS*DW-1:0]	i_sdata,
//		input	wire	[NS-1:0]	i_serr

  })
  addResource("external/wb2axip/rtl/wbxbar.v")
}

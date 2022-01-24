from cocotb_utils import SimpleBfm
from cocotb.triggers import RisingEdge, ReadOnly, NextTimeStep, ClockCycles

class WishboneBfm(SimpleBfm):
    Signals = SimpleBfm.make_signals("WishboneBfm",[
        "adr", "datwr", "datrd",
        "we", "cyc", "stb", "ack",
    ],optional=["sel"])
    has_sel = property(lambda self: self.bus.sel is not None)
    def __init__(self, clock, entity = None, signals = None, reset=None, reset_n=None, period=10, period_unit="ns",prefix=None):
        super().__init__(clock, signals=signals, entity=entity, reset=reset, reset_n=reset_n, period=period, period_unit=period_unit, prefix=prefix)
    def source_init(self):
        self.bus.cyc.setimmediatevalue(0)
        self.bus.stb.setimmediatevalue(0)
        self.bus.we.setimmediatevalue(0)
        self.bus.adr.setimmediatevalue(0)
        self.bus.datwr.setimmediatevalue(0)
        if self.has_sel:
            self.bus.sel.setimmediatevalue(0)
    def sink_init(self):
        self.bus.ack.setimmediatevalue(0)
        self.bus.datrd.setimmediatevalue(0)
    def source_read(self,addr):
        return self.source_read_write(addr=addr,wr_enable=False)
    def source_write(self,data,addr,sel=None):
        return self.source_read_write(data=data,addr=addr,sel=sel,wr_enable=True)
    async def source_read_write(self,data=None,addr=None,sel=None,wr_enable=False):
        await RisingEdge(self.clock)
        self.bus.cyc.value = 1
        self.bus.stb.value = 1
        self.bus.we.value = wr_enable
        self.bus.adr.value = addr
        if wr_enable:
            self.bus.datwr.value = data
            if self.has_sel:
                if sel is None:
                    sel = int("1"*self.bus.sel.value.n_bits,2)
                self.bus.sel.value = sel
        while True:
            await RisingEdge(self.clock)
            await ReadOnly()
            if self.bus.ack.value.binstr == "1":
                break
        await RisingEdge(self.clock)
        self.bus.cyc.value = 0
        self.bus.stb.value = 0
    async def source_receive(self):
        """ Receive WB source transaction: ack and datrd"""
        while True:
            await RisingEdge(self.clock)
            await ReadOnly()
            if self.in_reset:
                self.log.debug(f"WB sink receive in_reset true, continue...")
                continue
            if self.bus.ack.value.binstr == "1":
                received = dict(ack=True)
                if self.bus.we.value.binstr == "0":
                    received['data'] = self.bus.datrd.value.integer
                yield received
    async def sink_receive(self):
        """ Receive WB sink transaction: addr, datwr and sel """
        while True:
            await RisingEdge(self.clock)
            await ReadOnly()
            if self.in_reset:
                self.log.debug(f"WB sink receive in_reset true, continue...")
                continue
            if self.bus.cyc.value.binstr == "1" and self.bus.stb.value.binstr == "1":
                received = dict(addr=int(self.bus.adr.value))
                if self.bus.we.value.binstr == "1":
                    received['data'] = int(self.bus.datwr.value)
                    if self.has_sel:
                        received['sel'] = int(self.bus.sel.value)
                self.log.debug(f"WB sink received {received}")
                yield received
    async def sink_reply(self,data=None):
        await RisingEdge(self.clock)
        self.bus.ack.value = 1
        if self.bus.we.value.binstr == "0":
            self.bus.datrd.value = data
        await self.wait_for_signal(self.bus.stb,0)
        self.bus.ack.value = 0


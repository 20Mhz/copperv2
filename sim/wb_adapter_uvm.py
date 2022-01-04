import logging
from typing import Awaitable
import cocotb
from cocotb.decorators import RunningTask
from cocotb.triggers import First, Join, PythonTrigger
import pyuvm as uvm
import random

from cocotb_utils import anext

class WbSeqItem(uvm.uvm_sequence_item):
    def __init__(self, name):
        super().__init__(name)
        self.addr_width = 32
        self.data_width = 32
        self.granularity = 8
        self.sel_width = self.data_width // self.granularity

class WbReadSeqItem(WbSeqItem):
    def __init__(self, name):
        super().__init__(name)
        self.addr = None
    def __str__(self):
        res = f'{self.get_name()} : '
        res += f'addr: 0x{self.addr:0{self.addr_width//4}X} '
        return res
    def randomize(self):
        self.addr = random.randint(0, (2**self.addr_width)-1)

class WbWriteSeqItem(WbSeqItem):
    def __init__(self, name):
        super().__init__(name)
        self.addr = None
        self.data = None
        self.sel = None
    def __str__(self):
        res = f'{self.get_name()} : '
        res += f'data: 0x{self.data:0{self.data_width//4}X} '
        res += f'addr: 0x{self.addr:0{self.addr_width//4}X} '
        res += f'sel: 0b{self.strobe:0{self.sel_width}b}'
        return res
    def randomize(self):
        self.addr = random.randint(0, (2**self.addr_width)-1)
        self.data = random.randint(0, (2**self.data_width)-1)
        self.sel = random.randint(0, (2**self.sel_width)-1)

class BusSeqItem(uvm.uvm_sequence_item):
    def __init__(self, name):
        super().__init__(name)
        self.addr_width = 32
        self.data_width = 32
        self.strobe_width = self.data_width // 8

class BusReadSeqItem(BusSeqItem):
    def __init__(self, name):
        super().__init__(name)
        self.addr = None
    def __str__(self):
        res = f'{self.get_name()} : '
        res += f'addr: 0x{self.addr:0{self.addr_width//4}X} '
        return res
    def randomize(self):
        self.addr = random.randint(0, (2**self.addr_width)-1)

class BusWriteSeqItem(BusSeqItem):
    def __init__(self, name):
        super().__init__(name)
        self.addr = None
        self.data = None
        self.strobe = None
    def __str__(self):
        res = f'{self.get_name()} : '
        res += f'data: 0x{self.data:0{self.data_width//4}X} '
        res += f'addr: 0x{self.addr:0{self.addr_width//4}X} '
        res += f'strobe: 0b{self.strobe:0{self.strobe_width}b}'
        return res
    def randomize(self):
        self.addr = random.randint(0, (2**self.addr_width)-1)
        self.data = random.randint(0, (2**self.data_width)-1)
        self.strobe = random.randint(0, (2**self.strobe_width)-1)

class BusSeq(uvm.uvm_sequence):
    async def body(self):
        for _ in range(10):
            bus_read_tr = BusReadSeqItem("bus_read_tr")
            await self.start_item(bus_read_tr)
            bus_read_tr.randomize()
            await self.finish_item(bus_read_tr)
            bus_write_tr = BusWriteSeqItem("bus_write_tr")
            await self.start_item(bus_write_tr)
            bus_write_tr.randomize()
            await self.finish_item(bus_write_tr)

class WbAdapterScoreboard(uvm.uvm_component):
    def build_phase(self):
        self.bus_req_fifo = uvm.uvm_tlm_analysis_fifo("bus_req_fifo", self)
        self.bus_resp_fifo = uvm.uvm_tlm_analysis_fifo("bus_resp_fifo", self)
        self.wb_resp_fifo = uvm.uvm_tlm_analysis_fifo("wb_resp_fifo", self)
        self.bus_req_port = uvm.uvm_get_port("bus_req_port", self)
        self.bus_resp_port = uvm.uvm_get_port("bus_resp_port", self)
        self.wb_resp_port = uvm.uvm_get_port("wb_resp_port", self)
        self.bus_req_export = self.bus_req_fifo.analysis_export
        self.bus_resp_export = self.bus_resp_fifo.analysis_export
        self.wb_resp_export = self.wb_resp_fifo.analysis_export
    def connect_phase(self):
        self.bus_req_port.connect(self.bus_req_fifo.get_export)
        self.bus_resp_port.connect(self.bus_resp_fifo.get_export)
        self.wb_resp_port.connect(self.wb_resp_fifo.get_export)
    def check_phase(self):
        while self.bus_req_port.can_get():
            _, bus_req = self.bus_req_port.try_get()
            bus_resp_success, bus_resp = self.bus_resp_port.try_get()
            _, wb_resp = self.wb_resp_port.try_get()
            if not bus_resp_success:
                self.logger.critical(f"Bus request {bus_req} had no response")
                assert False
            else:
                ref = wb_resp
                if ref == bus_resp:
                    self.logger.info(f"PASSED: {ref} = {bus_resp}")
                else:
                    self.logger.error(f"FAILED: {ref} != {bus_resp}")
                    assert False

class WbMonitor(uvm.uvm_component):
    def __init__(self, name, parent):
        super().__init__(name, parent)
    def build_phase(self):
        self.req_ap = uvm.uvm_analysis_port("req_ap", self)
        self.resp_ap = uvm.uvm_analysis_port("resp_ap", self)
    def connect_phase(self):
        self.bfm = self.cdb_get("BFM")
    async def run_phase(self):
        while True:
            datum = await anext(self.bfm.sink_receive())
            self.logger.debug(f"Receiving request: {datum}")
            self.req_ap.write(datum)
            datum = await anext(self.bfm.source_receive())
            self.logger.debug(f"Receiving response: {datum}")
            self.resp_ap.write(datum)

class WbResponseDriver(uvm.uvm_driver):
    def connect_phase(self):
        self.bfm = self.cdb_get("BFM")
    async def run_phase(self):
        while True:
            seq_item = await self.seq_item_port.get_next_item()
            if isinstance(seq_item,WbReadSeqItem):
                await self.bfm.source_read(addr=seq_item.addr)
            if isinstance(seq_item,WbWriteSeqItem):
                await self.bfm.source_write(addr=seq_item.addr,data=seq_item.data,sel=seq_item.sel)
            self.logger.debug(f"Sent WB request: {seq_item}")
            self.seq_item_port.item_done()

class WbSinkAgent(uvm.uvm_agent):
    def build_phase(self):
        self.req_ap = uvm.uvm_analysis_port("req_ap", self)
        self.resp_ap = uvm.uvm_analysis_port("resp_ap", self)
        self.mon = WbMonitor("mon", self)
        if self.active:
            self.driver = WbResponseDriver("driver", self)
            self.seqr = uvm.uvm_sequencer("seqr", self)
            self.cdb_set("SEQR",self.seqr,"")
    def connect_phase(self):
        self.req_ap.connect(self.mon.req_ap)
        self.resp_ap.connect(self.mon.resp_ap)
        if self.active:
            self.driver.seq_item_port.connect(self.seqr.seq_item_export)

# Sink and Source:
## Request = read -> addr, write -> req
## Response = read -> data, write -> resp

class BusRequestDriver(uvm.uvm_driver):
    def connect_phase(self):
        self.bfm = self.cdb_get("BFM")
    async def run_phase(self):
        while True:
            seq_item = await self.seq_item_port.get_next_item()
            if isinstance(seq_item,BusReadSeqItem):
                await self.bfm.send_read_request(addr=seq_item.addr)
            if isinstance(seq_item,BusWriteSeqItem):
                await self.bfm.send_write_request(addr=seq_item.addr,data=seq_item.data,strobe=seq_item.strobe)
            self.logger.debug(f"Sent bus request: {seq_item}")
            self.seq_item_port.item_done()

class BusMonitor(uvm.uvm_component):
    def __init__(self, name, parent, method):
        super().__init__(name, parent)
        self.method = method
    def build_phase(self):
        self.ap = uvm.uvm_analysis_port("ap", self)
    def connect_phase(self):
        self.bfm = self.cdb_get("BFM")
        self.get_read = getattr(self.bfm,'get_read_'+self.method)
        self.get_write = getattr(self.bfm,'get_write_'+self.method)
    async def run_phase(self):
        while True:
            datum = await First(anext(self.get_read()),anext(self.get_write()))
            self.logger.debug(f"Receiving bus {self.method}: {datum}")
            self.ap.write(datum)

class BusSourceAgent(uvm.uvm_agent):
    def __init__(self, name, parent):
        super().__init__(name, parent)
    def build_phase(self):
        self.req_ap = uvm.uvm_analysis_port("req_ap", self)
        self.resp_ap = uvm.uvm_analysis_port("resp_ap", self)
        self.req_mon = BusMonitor("req_mon", self, 'request')
        self.resp_mon = BusMonitor("resp_mon", self, 'response')
        if self.active:
            self.req_driver = BusRequestDriver("req_driver", self)
            self.seqr = uvm.uvm_sequencer("seqr", self)
            self.cdb_set("SEQR",self.seqr,"")
    def connect_phase(self):
        self.req_mon.ap.connect(self.req_ap)
        self.resp_mon.ap.connect(self.resp_ap)
        if self.active:
            self.req_driver.seq_item_port.connect(self.seqr.seq_item_export)

class Debugger(uvm.uvm_export_base):
    def write(self,data):
        print('DEBUGGER:',data)

class WbAdapterEnv(uvm.uvm_env):
    def build_phase(self):
        self.bus_agent = BusSourceAgent("bus_agent", self)
        self.wb_agent = WbSinkAgent("wb_agent", self)
        self.scoreboard = WbAdapterScoreboard("scoreboard", self)
    def connect_phase(self):
        self.bus_agent.req_ap.connect(self.scoreboard.bus_req_export)
        self.bus_agent.resp_ap.connect(self.scoreboard.bus_resp_export)
        self.wb_agent.resp_ap.connect(self.scoreboard.wb_resp_export)

class WbAdapterTest(uvm.uvm_test):
    def build_phase(self):
        #uvm.ConfigDB().is_tracing = True
        self.env = WbAdapterEnv.create("env", self)
    async def run_phase(self):
        self.raise_objection()
        seqr = uvm.ConfigDB().get(self, "env.bus_agent", "SEQR")
        seq = BusSeq("seq")
        await seq.start(seqr)
        self.drop_objection()
    def end_of_elaboration_phase(self):
        self.set_logging_level_hier(logging.DEBUG)
        self.set_logging_level_hier(uvm.FIFO_DEBUG)
        self.logger.debug("UVM hierarchy:")
        self.print_hierarchy(self.logger,self)
    @staticmethod        
    def print_hierarchy(logger: logging.Logger,component: uvm.uvm_component):
        child: uvm.uvm_component
        for child in component.children:
            if isinstance(child,uvm.uvm_export_base):
                continue
            logger.debug(f'{child.get_full_name()}')
            WbAdapterTest.print_hierarchy(logger,child)


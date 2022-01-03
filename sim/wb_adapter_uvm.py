import logging
from typing import Awaitable
import cocotb
from cocotb.decorators import RunningTask
from cocotb.triggers import First, PythonTrigger
import pyuvm as uvm
import random

from pyuvm.s13_uvm_component import uvm_component

from cocotb_utils import anext

class BusReadSeqItem(uvm.uvm_sequence_item):
    def __init__(self, name):
        super().__init__(name)
        self.addr = None
        self.addr_width = 32
    def __str__(self):
        res = f'{self.get_name()} : '
        res += f'addr: 0x{self.addr:0{self.addr_width//4}X} '
        return res
    def randomize(self):
        self.addr = random.randint(0, (2**self.addr_width)-1)

class BusWriteSeqItem(uvm.uvm_sequence_item):
    def __init__(self, name):
        super().__init__(name)
        self.addr = None
        self.data = None
        self.strobe = None
        self.addr_width = 32
        self.data_width = 32
        self.strobe_width = self.data_width // 8
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

class BusReadSeq(uvm.uvm_sequence):
    async def body(self):
        for _ in range(10):
            bus_read_tr = BusReadSeqItem("bus_read_tr")
            await self.start_item(bus_read_tr)
            bus_read_tr.randomize()
            await self.finish_item(bus_read_tr)

class BusWriteSeq(uvm.uvm_sequence):
    async def body(self):
        for _ in range(10):
            bus_write_tr = BusWriteSeqItem("bus_write_tr")
            await self.start_item(bus_write_tr)
            bus_write_tr.randomize()
            await self.finish_item(bus_write_tr)

class Scoreboard(uvm.uvm_component):
    def build_phase(self):
        self.bus_fifo = uvm.uvm_tlm_analysis_fifo("bus_fifo", self)
        self.wb_fifo = uvm.uvm_tlm_analysis_fifo("wb_fifo", self)
        self.bus_port = uvm.uvm_get_port("bus_port", self)
        self.wb_port = uvm.uvm_get_port("wb_port", self)
        self.bus_export = self.bus_fifo.analysis_export
        self.wb_export = self.wb_fifo.analysis_export
    def connect_phase(self):
        self.bus_port.connect(self.bus_fifo.get_export)
        self.wb_port.connect(self.wb_fifo.get_export)
    def check_phase(self):
        while self.bus_port.can_get():
            _, actual_result = self.wb_port.try_get()
            ref_success, ref = self.bus_port.try_get()
            if not ref_success:
                self.logger.critical(f"result {actual_result} had no bus transaction")
            else:
                if ref == actual_result:
                    self.logger.info(f"PASSED: {ref} = {actual_result}")
                else:
                    self.logger.error(f"FAILED: {ref} != {actual_result}")
                    assert False

class WbMonitor(uvm.uvm_component):
    def __init__(self, name, parent):
        super().__init__(name, parent)
    def build_phase(self):
        self.ap = uvm.uvm_analysis_port("ap", self)
    def connect_phase(self):
        self.bfm = self.cdb_get("WB_BFM")
    async def run_phase(self):
        while True:
            datum = await anext(self.bfm.sink_receive())
            self.logger.debug(f"Receiving transaction: {datum}")
            self.ap.write(datum)

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
                await self.bfm.send_request(addr=seq_item.addr)
            if isinstance(seq_item,BusWriteSeqItem):
                await self.bfm.send_request(addr=seq_item.addr,data=seq_item.data,strobe=seq_item.strobe)
            self.logger.debug(f"Sent bus request: {seq_item}")
            self.seq_item_port.item_done()

class BusRequestMonitor(uvm.uvm_component):
    def build_phase(self):
        self.ap = uvm.uvm_analysis_port("ap", self)
    def connect_phase(self):
        self.bfm = self.cdb_get("BFM")
    async def run_phase(self):
        while True:
            datum = await anext(self.bfm.get_request())
            self.logger.debug(f"Receiving bus request: {datum}")
            self.ap.write(datum)

class BusResponseMonitor(uvm.uvm_component):
    def build_phase(self):
        self.ap = uvm.uvm_analysis_port("ap", self)
    def connect_phase(self):
        self.bfm = self.cdb_get("BFM")
    async def run_phase(self):
        while True:
            datum = await anext(self.bfm.get_response())
            self.logger.debug(f"Receiving bus response: {datum}")
            self.ap.write(datum)

class BusSourceAgent(uvm.uvm_agent):
    def build_phase(self):
        self.req_ap = uvm.uvm_analysis_port("req_ap", self)
        self.resp_ap = uvm.uvm_analysis_port("resp_ap", self)
        self.req_mon = BusRequestMonitor("req_mon", self)
        self.resp_mon = BusRequestMonitor("resp_mon", self)
        if self.active:
            self.req_driver = BusRequestDriver("req_driver", self)
            self.seqr = uvm.uvm_sequencer("seqr", self)
            self.cdb_set("SEQR",self.seqr,"")
    def connect_phase(self):
        self.req_ap.connect(self.req_ap)
        self.resp_ap.connect(self.resp_ap)
        if self.active:
            self.req_driver.seq_item_port.connect(self.seqr.seq_item_export)

class WbAdapterEnv(uvm.uvm_env):
    def build_phase(self):
        self.wb_mon = WbMonitor("wb_mon", self)
        self.bus_read_agent = BusSourceAgent("bus_read_agent", self)
        self.bus_write_agent = BusSourceAgent("bus_write_agent", self)
        self.scoreboard = Scoreboard("scoreboard", self)
    def connect_phase(self):
        self.bus_read_agent.req_ap.connect(self.scoreboard.bus_export)
        self.wb_mon.ap.connect(self.scoreboard.wb_export)

class WbAdapterTest(uvm.uvm_test):
    def build_phase(self):
        uvm.ConfigDB().is_tracing = True
        self.env = WbAdapterEnv.create("env", self)
    async def run_phase(self):
        self.raise_objection()
        read_seqr = uvm.ConfigDB().get(self, "env.bus_read_agent", "SEQR")
        write_seqr = uvm.ConfigDB().get(self, "env.bus_write_agent", "SEQR")
        read_seq = BusReadSeq("read_seq")
        write_seq = BusWriteSeq("write_seq")
        await read_seq.start(read_seqr)
        await write_seq.start(write_seqr)
        self.drop_objection()
        assert False
    def end_of_elaboration_phase(self):
        self.set_logging_level_hier(logging.DEBUG)
        self.logger.debug("UVM hierarchy:")
        self.print_hierarchy(self.logger,self)
    @staticmethod        
    def print_hierarchy(logger: logging.Logger,component: uvm_component):
        child: uvm_component
        for child in component.children:
            if isinstance(child,uvm.uvm_export_base):
                continue
            logger.debug(f'{child.get_full_name()}')
            WbAdapterTest.print_hierarchy(logger,child)


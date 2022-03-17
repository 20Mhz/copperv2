import dataclasses

import cocotb
from cocotb.triggers import RisingEdge, ReadOnly, Combine
from cocotb_bus.monitors import Monitor
from cocotb.log import SimLog

from cocotb_utils import Bfm, SimpleBfm, anext
from riscv_constants import abi_reg_map, reg_abi_map

@dataclasses.dataclass
class RegFileWriteTransaction:
    reg: int = None
    data: int = None
    @property
    def reg_name(self):
        if self.reg is None:
            return None
        return reg_abi_map[self.reg] 
    @classmethod
    def from_string(cls, string):
        tokens = string.split()
        reg, value = tokens
        return cls(abi_reg_map[reg],int(value,0))
    def __str__(self):
        data = f'0x{self.data:X}' if self.data is not None else None
        return f'RegFileWriteTransaction(reg={self.reg_name}, data={data})'

@dataclasses.dataclass
class RegFileReadTransaction:
    reg1: int = None
    data1: int = None
    reg2: int = None
    data2: int = None
    @classmethod
    def from_string(cls, string):
        tokens = string.split()
        if len(tokens) == 2:
            reg, value = tokens
            return cls(abi_reg_map[reg],int(value,0))
        elif len(tokens) == 4:
            reg1, value1, reg2, value2 = tokens
            return cls(abi_reg_map[reg1],int(value1,0)
                    ,abi_reg_map[reg2],int(value2,0))
        else:
            ValueError("Invalid transaction")
    @property
    def reg1_name(self):
        if self.reg1 is None:
            return None
        return reg_abi_map[self.reg1]
    @property
    def reg2_name(self):
        if self.reg2 is None:
            return None
        return reg_abi_map[self.reg2]
    def __str__(self):
        data1 = f'0x{self.data1:X}' if self.data1 is not None else None
        data2 = f'0x{self.data2:X}' if self.data2 is not None else None
        return f'RegFileReadTransaction(reg1={self.reg1_name}, data1={data1}, reg2={self.reg2_name}, data1={data2})'

class RegFileBfm(SimpleBfm):
    Signals = SimpleBfm.make_signals("RegFileBfmSignals",[
        "rd_en",
        "rd_addr",
        "rd_data",
        "rs1_en",
        "rs1_addr",
        "rs1_data",
        "rs2_en",
        "rs2_addr",
        "rs2_data",
    ])
    def __init__(self, clock, entity=None,signals=None, reset=None, reset_n=None, period=10, period_unit="ns"):
        super().__init__(clock, entity=entity, signals=signals, reset=reset, reset_n=reset_n, period=period, period_unit=period_unit)
    async def recv_rd(self):
        while(True):
            await RisingEdge(self.clock)
            await ReadOnly()
            if self.bus.rd_en.value:
                yield dict(
                    addr = int(self.bus.rd_addr.value),
                    data = int(self.bus.rd_data.value)
                )
    async def recv_rs(self):
        while(True):
            buf = {}
            await RisingEdge(self.clock)
            await ReadOnly()
            en1 = self.bus.rs1_en.value
            en2 = self.bus.rs2_en.value
            if (not en1) and (not en2):
                continue
            await RisingEdge(self.clock)
            await ReadOnly()
            if en1:
                buf['addr'] = int(self.bus.rs1_addr.value)
                buf['data'] = int(self.bus.rs1_data.value)
            if en2:
                buf['addr2'] = int(self.bus.rs2_addr.value)
                buf['data2'] = int(self.bus.rs2_data.value)
            yield buf

class RegFileWriteMonitor(Monitor):
    def __init__(self,name,bfm,callback=None,event=None):
        self.name = name
        self.log = SimLog(f"cocotb.{self.name}")
        self.bfm = bfm
        super().__init__(callback=callback,event=event)
    async def _monitor_recv(self):
        while True:
            received = await anext(self.bfm.recv_rd())
            transaction = RegFileWriteTransaction(
                reg = received['addr'],
                data = received['data'],
            )
            self.log.debug("Regfile write: %s", transaction)
            self._recv(transaction)

class RegFileReadMonitor(Monitor):
    def __init__(self,name,bfm,callback=None,event=None):
        self.name = name
        self.log = SimLog(f"cocotb.{self.name}")
        self.bfm = bfm
        super().__init__(callback=callback,event=event)
    async def _monitor_recv(self):
        while True:
            transaction = None
            received = await anext(self.bfm.recv_rs())
            if len(received) == 4:
                transaction = RegFileReadTransaction(
                    reg1 = int(received['addr']),
                    data1 = int(received['data']),
                    reg2 = int(received['addr2']),
                    data2 = int(received['data2']),
                )
            elif 'addr' in received:
                transaction = RegFileReadTransaction(
                    reg1 = int(received['addr']),
                    data1 = int(received['data']),
                )
            elif 'addr2' in received:
                transaction = RegFileReadTransaction(
                    reg1 = int(received['addr2']),
                    data1 = int(received['data2']),
                )
            self.log.debug('Regfile read: %s',transaction)
            self._recv(transaction)

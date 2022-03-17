import dataclasses
import typing

import cocotb
from cocotb.triggers import RisingEdge, ReadOnly, NextTimeStep, Combine
from cocotb_bus.monitors import Monitor
from cocotb_bus.drivers import Driver
from cocotb.log import SimLog

from cocotb_utils import Bfm, SimpleBfm, anext

@dataclasses.dataclass
class BusReadTransaction:
    bus_name: str
    data: int = None
    addr: int = None
    @classmethod
    def from_string(cls, string):
        addr, data = string.split()
        return cls(
            bus_name=None,
            data=int(data,0),
            addr=int(addr,0))
    @classmethod
    def from_reqresp(cls, bus_name, request, response = None):
        new = cls(bus_name=bus_name,addr=request['addr'])
        if response is not None:
            new.data = response['data']
        return new
    def to_reqresp(self):
        return dict(request = self.addr, response = dict(data=self.data))
    @classmethod
    def default_transaction(cls,bus_name):
        return cls(bus_name=bus_name,addr=0,data=0)
    def __eq__(self, other) -> bool:
        return self.addr == other.addr and self.data == other.data
    def __str__(self):
        data = f'0x{self.data:X}' if self.data is not None else None
        addr = f'0x{self.addr:X}' if self.addr is not None else None
        return f'{self.__class__.__name__}(bus_name={self.bus_name}, addr={addr}, data={data})'


@dataclasses.dataclass
class BusWriteTransaction:
    bus_name: str
    data: int = None
    addr: int = None
    strobe: int = None
    response: int = None
    @classmethod
    def from_string(cls, string):
        addr, data, strobe, response = string.split()
        return cls(
            bus_name=None,
            data=int(data,0),
            addr=int(addr,0),
            strobe=int(strobe,0),
            response=int(response,0))
    @classmethod
    def from_reqresp(cls, bus_name, request, response = None):
        new = cls(
            bus_name = bus_name,
            data = request['data'],
            addr = request['addr'],
            strobe = request['strobe'])
        if response is not None:
            new.response = response['resp']
        return new
    def to_reqresp(self):
        return dict(
                request = dict(data=self.data,addr=self.addr,strobe=self.strobe),
                response = dict(resp=self.response)
            )
    @classmethod
    def default_transaction(cls,bus_name):
        return cls(bus_name=bus_name,addr=0,data=0,strobe=0,response=0)
    def __eq__(self, other) -> bool:
        return self.addr == other.addr and self.data == other.data \
            and self.strobe == other.strobe and self.response == other.response
    def __str__(self):
        data = f'0x{self.data:X}' if self.data is not None else None
        addr = f'0x{self.addr:X}' if self.addr is not None else None
        strobe = f'0x{self.strobe:X}' if self.strobe is not None else None
        response = f'0x{self.response:X}' if self.response is not None else None
        return f'{self.__class__.__name__}(bus_name={self.bus_name}, addr={addr}, data={data}, strobe={strobe}, response={response})'

class ReadyValidBfm(SimpleBfm):
    Signals = SimpleBfm.make_signals("ReadyValidBfmSignals",["ready","valid"])
    def __init__(self, clock, signals, payload, reset=None, reset_n=None, period=10, period_unit="ns",init_valid=False,relaxed_mode=False):
        self.payload = payload
        self.relaxed_mode = relaxed_mode
        super().__init__(signals=signals, period=period, period_unit=period_unit, reset=reset, reset_n=reset_n, clock=clock)
        if init_valid:
            self.bus.valid.setimmediatevalue(0)
    def sink_init(self):
        self.bus.ready.setimmediatevalue(0)
    def source_init(self):
        self.bus.valid.setimmediatevalue(0)
    def to_int(self,value):
        if self.relaxed_mode:
            return int(value.binstr.replace('x','0'),2)
        else:
            return int(value)
    async def recv_payload(self):
        while(True):
            await RisingEdge(self.clock)
            await ReadOnly()
            if self.in_reset:
                self.log.debug(f"recv_payload in_reset true, continue... {self.bus.ready._name}")
                continue
            if self.bus.ready.value and self.bus.valid.value:
                actual_payload = {k:self.to_int(p.value) for k,p in self.payload.items()}
                self.log.debug(f"Receiving payload {self.bus.ready._name} {actual_payload}")
                yield actual_payload
    async def send_payload(self,**kwargs):
        self.log.debug(f"Send payload {self.bus.ready._name} {kwargs}")
        await self.wait_for_signal(self.bus.ready,1)
        self.bus.valid.value = 1
        for name,payload_signal in self.payload.items():
            payload_signal.value = int(kwargs[name])
        await RisingEdge(self.clock)
        await NextTimeStep()
        self.bus.valid.value = 0
    async def drive_ready(self,value):
        self.log.debug(f"Drive ready {self.bus.ready._name} {value}")
        await RisingEdge(self.clock)
        self.bus.ready.value = value
    async def drive_valid(self,value):
        self.log.debug(f"Drive valid {self.bus.valid._name} {value}")
        await RisingEdge(self.clock)
        self.bus.valid.value = value

class CoppervBusSourceBfm(SimpleBfm):
    Signals = SimpleBfm.make_signals("CoppervBusSourceBfm",[
        "r_addr_ready", "r_addr_valid", "r_addr_bits",
        "r_data_ready", "r_data_valid", "r_data_bits",
        "w_req_ready",  "w_req_valid",  "w_req_bits_data", "w_req_bits_addr", "w_req_bits_strobe",
        "w_resp_ready", "w_resp_valid", "w_resp_bits",
    ])
    def __init__(self, clock, entity = None, signals = None, reset=None, reset_n=None, period=10, period_unit="ns", prefix=None, relaxed_mode=False):
        super().__init__(clock, signals=signals, entity=entity, reset=reset, reset_n=reset_n, period=period, period_unit=period_unit, prefix=prefix)
        addr_payload = dict(addr=self.bus.r_addr_bits)
        data_payload = dict(data=self.bus.r_data_bits)
        req_payload=dict(data=self.bus.w_req_bits_data,addr=self.bus.w_req_bits_addr,strobe=self.bus.w_req_bits_strobe)
        resp_payload = dict(resp=self.bus.w_resp_bits)
        addr_signals = ReadyValidBfm.Signals(ready=self.bus.r_addr_ready,valid=self.bus.r_addr_valid)
        data_signals = ReadyValidBfm.Signals(ready=self.bus.r_data_ready,valid=self.bus.r_data_valid)
        req_signals = ReadyValidBfm.Signals(ready=self.bus.w_req_ready,valid=self.bus.w_req_valid)
        resp_signals = ReadyValidBfm.Signals(ready=self.bus.w_resp_ready,valid=self.bus.w_resp_valid)
        self.addr = ReadyValidBfm(clock,addr_signals,addr_payload,reset_n=reset_n,reset=reset,relaxed_mode=relaxed_mode)
        self.data = ReadyValidBfm(clock,data_signals,data_payload,reset_n=reset_n,reset=reset,relaxed_mode=relaxed_mode)
        self.req = ReadyValidBfm(clock,req_signals,req_payload,reset_n=reset_n,reset=reset,relaxed_mode=relaxed_mode)
        self.resp = ReadyValidBfm(clock,resp_signals,resp_payload,reset_n=reset_n,reset=reset,relaxed_mode=relaxed_mode)
    def init(self):
        self.addr.source_init()
        self.req.source_init()
        self.data.sink_init()
        self.resp.sink_init()
    async def drive_ready(self,value):
        t1 = cocotb.start_soon(self.data.drive_ready(value))
        t2 = cocotb.start_soon(self.resp.drive_ready(value))
        return Combine(t1,t2)
    def get_read_request(self):
        return self.addr.recv_payload()
    def get_read_response(self):
        return self.data.recv_payload()
    async def send_read_request(self,addr):
        await self.addr.send_payload(addr=addr)
    def get_write_request(self):
        return self.req.recv_payload()
    def get_write_response(self):
        return self.resp.recv_payload()
    async def send_write_request(self,data,addr,strobe):
        await self.req.send_payload(data=data,addr=addr,strobe=strobe)
    async def check(self):
        while(True):
            await RisingEdge(self.clock)
            await ReadOnly()
            if self.in_reset:
                continue
            assert not (self.addr.bus.valid.value and self.req.bus.valid.value), "Cannot read and write at the same time"

class CoppervBusBfm(SimpleBfm):
    Signals = SimpleBfm.make_signals("CoppervBusBfm",[
        "ir_addr_valid", "ir_addr_ready", "ir_addr",
        "ir_data_valid", "ir_data_ready", "ir_data",
        "dr_addr_valid", "dr_addr_ready", "dr_addr",
        "dr_data_valid", "dr_data_ready", "dr_data",
        "dw_data_addr_ready", "dw_data_addr_valid", 
        "dw_data", "dw_addr", "dw_strobe",
        "dw_resp_ready", "dw_resp_valid", "dw_resp",
    ])
    def __init__(self, clock, entity = None, signals = None, reset=None, reset_n=None, period=10, period_unit="ns", prefix=None,relaxed_mode=False):
        super().__init__(clock, signals=signals, entity=entity, reset=reset, reset_n=reset_n, period=period, period_unit=period_unit, prefix=prefix)
        channels = dict(
            ir_addr=(dict(addr=self.bus.ir_addr),False),
            ir_data=(dict(data=self.bus.ir_data),True),
            dr_addr=(dict(addr=self.bus.dr_addr),False),
            dr_data=(dict(data=self.bus.dr_data),True),
            dw_data_addr=(dict(
                data=self.bus.dw_data,
                addr=self.bus.dw_addr,
                strobe=self.bus.dw_strobe,
            ),False),
            dw_resp=(dict(resp=self.bus.dw_resp),True),
        )
        for ch_name,temp in channels.items():
            payload,init_valid=temp
            signals = ReadyValidBfm.Signals(
                ready = getattr(self.bus,f"{ch_name}_ready"),
                valid = getattr(self.bus,f"{ch_name}_valid"),
            )
            bfm = ReadyValidBfm(clock,signals,payload,reset_n=reset_n,init_valid=init_valid,relaxed_mode=relaxed_mode)
            setattr(self,f"{ch_name}_bfm",bfm)
    async def ir_send_response(self,**kwargs):
        await self.ir_data_bfm.send_payload(**kwargs)
    async def ir_drive_ready(self,value):
        await self.ir_addr_bfm.drive_ready(value)
    def ir_get_request(self):
        return self.ir_addr_bfm.recv_payload()
    def ir_get_response(self):
        return self.ir_data_bfm.recv_payload()
    async def dr_send_response(self,**kwargs):
        await self.dr_data_bfm.send_payload(**kwargs)
    async def dr_drive_ready(self,value):
        await self.dr_addr_bfm.drive_ready(value)
    def dr_get_request(self):
        return self.dr_addr_bfm.recv_payload()
    def dr_get_response(self):
        return self.dr_data_bfm.recv_payload()
    async def dw_send_response(self,**kwargs):
        await self.dw_resp_bfm.send_payload(**kwargs)
    async def dw_drive_ready(self,value):
        await self.dw_data_addr_bfm.drive_ready(value)
    def dw_get_request(self):
        return self.dw_data_addr_bfm.recv_payload()
    def dw_get_response(self):
        return self.dw_resp_bfm.recv_payload()

class BusMonitor(Monitor):
    def __init__(self,name,transaction_type,bfm_recv_req,bfm_recv_resp=None,callback=None,event=None,bus_name=None):
        self.bus_name = bus_name
        if self.bus_name is None:
            self.bus_name = name
        self.name = name
        self.log = SimLog(f"cocotb.{self.name}")
        self.bfm_recv_req = bfm_recv_req
        self.bfm_recv_resp = bfm_recv_resp
        self.transaction_type = transaction_type
        super().__init__(callback=callback,event=event)
    async def _monitor_recv(self):
        req_transaction = None
        resp_transaction = None
        while True:
            req_transaction = await anext(self.bfm_recv_req())
            if self.bfm_recv_resp is not None:
                resp_transaction = await anext(self.bfm_recv_resp())
            transaction = self.transaction_type.from_reqresp(
                bus_name = self.bus_name,
                request = req_transaction,
                response = resp_transaction
            )
            _type = "request" if self.bfm_recv_resp is None else "full"
            self.log.debug(f"Receiving {_type} transaction: %s",transaction)
            self._recv(transaction)

class BusSourceDriver(Driver):
    def __init__(self,name,transaction_type,bfm_send_resp,bfm_drive_ready):
        self.name = name
        self.log = SimLog(f"cocotb.{self.name}")
        self.bfm_send_resp = bfm_send_resp
        self.bfm_drive_ready = bfm_drive_ready
        self.transaction_type = transaction_type
        super().__init__()
        ## reset
        self.append('assert_ready')
    async def _driver_send(self, transaction, sync: bool = True):
        if isinstance(transaction, self.transaction_type):
            transaction = self.transaction_type.to_reqresp(transaction)
            self.log.debug("%s responding read transaction: %s", self.name, transaction)
            await self.bfm_send_resp(**transaction['response'])
        elif transaction == "assert_ready":
            await self.bfm_drive_ready(True)
        elif transaction == "deassert_ready":
            await self.bfm_drive_ready(False)

import logging
import os
from pathlib import Path
from textwrap import dedent
from cocotb.log import SimLog

import pytest
from cocotb_test.simulator import run

from cocotb_utils import Bfm

import cocotb
from cocotb.triggers import Join, RisingEdge
from bus import ReadyValidBfm
from cocotb_utils import anext
from wishbone import WishboneBfm

root_dir = Path(__file__).resolve().parent.parent
work_dir = root_dir/'work/sim/test_testbench'
work_dir.mkdir(exist_ok=True,parents=True)

@pytest.fixture
def ready_valid_rtl():
    rtl = work_dir/"ready_valid.v"
    rtl.write_text(dedent("""
    `timescale 1ns/1ps
    module top(
        output clock,
        output reset,
        output ready,
        output valid,
        output [7:0] data
    );
    initial #1000;
    endmodule
    """))
    print("Generated",rtl)
    return rtl

@pytest.fixture
def wishbone_rtl():
    rtl = work_dir/"wishbone.v"
    rtl.write_text(dedent("""
    `timescale 1ns/1ps
    module top(
        output clock,
        output reset,
        output [7:0] adr,
        output [7:0] datwr,
        output [7:0] datrd,
        output we,
        output cyc,
        output stb,
        output ack,
        output sel
    );
    initial #1000;
    endmodule
    """))
    print("Generated",rtl)
    return rtl

@pytest.fixture
def fake_signals():
    return Bfm.make_signals("FakeSignals",["a","b"],optional=["c"])

@cocotb.test(timeout_time=10,timeout_unit="us")
async def run_ready_valid_bfm_test(dut):
    """ ready/valid BFM test """
    SimLog("bfm").setLevel(logging.DEBUG)
    reference = 123
    signals = ReadyValidBfm.Signals(ready = dut.ready, valid = dut.valid)
    payload = dict(data = dut.data)
    bfm = ReadyValidBfm(dut.clock,signals,payload,reset=dut.reset)
    bfm.start_clock()
    await bfm.reset()
    await bfm.drive_ready(1)
    send_task = cocotb.start_soon(bfm.send_payload(data=reference))
    received = await anext(bfm.recv_payload())
    assert received['data'] == reference
    await Join(send_task)
    await RisingEdge(dut.clock)

def test_ready_valid(ready_valid_rtl):
    run(
        verilog_sources=[ready_valid_rtl],
        toplevel="top",
        module="test_testbench",
        waves = True,
        sim_build=work_dir/'test_ready_valid',
        testcase = "run_ready_valid_bfm_test",
    )

def test_signals_dataclass_required(fake_signals):
    foo = fake_signals(a=1,b=2)
    assert foo.a == 1
    assert foo.b == 2
    assert foo.c is None
    assert 'a' in foo
    assert 'b' in foo
    assert not 'c' in foo

def test_signals_dataclass_optional(fake_signals):
    foo = fake_signals(a=1,b=2,c=3)
    assert foo.a == 1
    assert foo.b == 2
    assert foo.c == 3

def test_signals_dataclass_unexpected(fake_signals):
    with pytest.raises(TypeError):
        foo = fake_signals(a=1,b=2,d=4)

def test_signals_dataclass_missing(fake_signals):
    with pytest.raises(TypeError):
        foo = fake_signals(a=1)

@cocotb.test(timeout_time=10,timeout_unit="us")
async def run_wishbone_bfm_read_test(dut):
    """ Wishbone BFM read test """
    SimLog("bfm").setLevel(logging.DEBUG)
    data = 123
    addr = 101
    bfm = WishboneBfm(dut.clock,entity=dut,reset=dut.reset)
    bfm.start_clock()
    bfm.sink_init()
    bfm.source_init()
    await bfm.reset()
    send_task = cocotb.start_soon(bfm.source_read(addr))
    received = await anext(bfm.sink_receive())
    assert received['addr'] == addr
    reply_task = cocotb.start_soon(bfm.sink_reply(data))
    reply = await anext(bfm.source_receive())
    assert reply['data'] == data
    assert reply['ack'] == True
    await Join(send_task)
    await Join(reply_task)
    await RisingEdge(dut.clock)

@cocotb.test(timeout_time=10,timeout_unit="us")
async def run_wishbone_bfm_write_test(dut):
    """ Wishbone BFM write test """
    SimLog("bfm").setLevel(logging.DEBUG)
    data = 123
    addr = 101
    sel = 1
    bfm = WishboneBfm(dut.clock,entity=dut,reset=dut.reset)
    bfm.start_clock()
    bfm.sink_init()
    bfm.source_init()
    await bfm.reset()
    send_task = cocotb.start_soon(bfm.source_write(data,addr,sel))
    received = await anext(bfm.sink_receive())
    assert received['data'] == data
    assert received['addr'] == addr
    assert received['sel'] == sel
    reply_task = cocotb.start_soon(bfm.sink_reply(data))
    reply = await anext(bfm.source_receive())
    assert reply['ack'] == True
    await Join(send_task)
    await Join(reply_task)
    await RisingEdge(dut.clock)

def test_wishbone_read(wishbone_rtl):
    run(
        verilog_sources=[wishbone_rtl],
        toplevel="top",
        module="test_testbench",
        waves = True,
        sim_build=work_dir/'test_wishbone_read',
        testcase = "run_wishbone_bfm_read_test",
    )

def test_wishbone_write(wishbone_rtl):
    run(
        verilog_sources=[wishbone_rtl],
        toplevel="top",
        module="test_testbench",
        waves = True,
        sim_build=work_dir/'test_wishbone_write',
        testcase = "run_wishbone_bfm_write_test",
    )

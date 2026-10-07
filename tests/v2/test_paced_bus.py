"""paced_bus codegen mode: guest bus accesses use the region-paced runtime
accessors and the block constant charges only fetches and internal cycles,
so compiled code advances the master clock like the interpreter tier."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "recompiler")]
from v2.emit_function import _pace_bus_lines, _paced_block_master


def test_guest_accesses_become_paced_and_are_counted():
    lines = [
        "uint8 _v1 = cpu_read8(cpu, cpu->DB, (uint16)(0x4212));",
        "cpu_write16(cpu, 0x00, cpu->S, cpu->A);",
        "{ uint16 _rpcl = (uint16)cpu_read8(cpu, 0x00, cpu->S); uint16 _rpch = (uint16)cpu_read8(cpu, 0x00, cpu->S); }",
        "uint16 _host_rpcl = cpu_read8(cpu, 0x00, (uint16)(_entry_s + 1u));",
    ]
    out, data_bytes = _pace_bus_lines(lines)
    assert out[0] == "uint8 _v1 = cpu_read8_paced(cpu, cpu->DB, (uint16)(0x4212));"
    assert out[1] == "cpu_write16_paced(cpu, 0x00, cpu->S, cpu->A);"
    assert out[2].count("cpu_read8_paced(") == 2
    assert out[3] == lines[3]          # host bookkeeping, not a guest access
    assert data_bytes == 1 + 2 + 2


def test_already_paced_lines_are_left_alone():
    out, data_bytes = _pace_bus_lines(["x = cpu_read16_paced(cpu, 0, 1);"])
    assert out == ["x = cpu_read16_paced(cpu, 0, 1);"] and data_bytes == 2


def test_block_master_charges_fetches_at_code_speed_and_internal_at_6():
    # LDA abs (4 cycles, 3 bytes, 1 data byte at m=1) + INX (2 cycles, 1 byte)
    # cycles 6, fetched 4 bytes, 1 data byte -> internal 1
    assert _paced_block_master(6, 4, 1, "8") == "4 * 8 + 6"
    assert _paced_block_master(6, 4, 1, None, 6) == "30"
    # never charges negative internal time
    assert _paced_block_master(3, 2, 4, None, 8) == "16"

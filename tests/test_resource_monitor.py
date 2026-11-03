from types import SimpleNamespace

import dearpygui.dearpygui as dpg
import pytest

from ui.scan import _format_memory_usage, _publish_resource_usage


def test_resource_monitor_displays_cpu_and_ram_percentages():
    dpg.create_context()
    try:
        with dpg.window(tag="resource_test_window"):
            dpg.add_progress_bar(tag="system_cpu_usage")
            dpg.add_progress_bar(tag="system_ram_usage")
            dpg.add_text("", tag="system_cpu_usage_text")
            dpg.add_text("", tag="system_ram_usage_text")

        memory = SimpleNamespace(
            used=8 * 1024 ** 3,
            total=16 * 1024 ** 3,
            percent=50.0,
        )
        _publish_resource_usage(37.0, memory)

        assert dpg.get_value("system_cpu_usage") == pytest.approx(0.37)
        assert dpg.get_value("system_ram_usage") == pytest.approx(0.5)
        assert dpg.get_value("system_cpu_usage_text") == "37%"
        assert dpg.get_value("system_ram_usage_text") == "8.0 / 16.0 GB (50%)"
        assert _format_memory_usage(memory) == "8.0 / 16.0 GB (50%)"
    finally:
        dpg.destroy_context()


def test_resource_monitor_clamps_progress_bar_values():
    dpg.create_context()
    try:
        with dpg.window(tag="resource_test_window"):
            dpg.add_progress_bar(tag="system_cpu_usage")
            dpg.add_progress_bar(tag="system_ram_usage")
            dpg.add_text("", tag="system_cpu_usage_text")
            dpg.add_text("", tag="system_ram_usage_text")

        memory = SimpleNamespace(
            used=0,
            total=1,
            percent=120.0,
        )
        _publish_resource_usage(-5.0, memory)

        assert dpg.get_value("system_cpu_usage") == 0.0
        assert dpg.get_value("system_ram_usage") == 1.0
    finally:
        dpg.destroy_context()

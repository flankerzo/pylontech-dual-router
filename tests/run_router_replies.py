"""Compile the actual router with minimal ESPHome IO stubs using MSVC on Windows.

Run with Python from any directory. Build artifacts stay in .esphome/router-tests.
This verifies router logic, not ESP32 UART timing or an ESPHome firmware build.
"""
from pathlib import Path
import os
import subprocess

root = Path(__file__).resolve().parents[1]
build = root / ".esphome" / "router-tests"
build.mkdir(parents=True, exist_ok=True)
stubs = {
    "core/component.h": """
#pragma once
#include <cstdint>
namespace esphome {
extern uint32_t test_now;
inline uint32_t millis() { return test_now; }
namespace setup_priority { constexpr float LATE = -100; }
class Component { public: virtual void setup() {} virtual void loop() {}
virtual void dump_config() {} virtual float get_setup_priority() const { return 0; } };
}
""",
    "core/log.h": """
#pragma once
#define ESP_LOGW(...) ((void)0)
#define ESP_LOGD(...) ((void)0)
#define ESP_LOGCONFIG(...) ((void)0)
""",
    "components/uart/uart.h": """
#pragma once
#include <string>
#include <vector>
namespace esphome { namespace uart {
class UARTDevice { public:
std::string rx; std::vector<std::string> tx;
int available() { return static_cast<int>(rx.size()); }
bool read_byte(uint8_t *b) { if (rx.empty()) return false;
*b = rx.front(); rx.erase(0, 1); return true; }
void write_str(const char *s) { tx.emplace_back(s); }
}; } }
""",
}
for namespace, classname, datatype, initial in [
    ("sensor", "Sensor", "float", "0"),
    ("binary_sensor", "BinarySensor", "bool", "false"),
    ("text_sensor", "TextSensor", "std::string", '""'),
    ("number", "Number", "float", "0"),
    ("switch", "Switch", "bool", "false"),
]:
    cpp_namespace = "switch_" if namespace == "switch" else namespace
    stubs[f"components/{namespace}/{namespace}.h"] = f"""
#pragma once
#include <string>
#include <vector>
namespace esphome {{ namespace {cpp_namespace} {{
class {classname} {{ public:
{datatype} state = {initial}; std::vector<{datatype}> values;
void publish_state({datatype} value) {{ state = value; values.push_back(value); }}
}}; }} }}
"""
for name, content in stubs.items():
    target = build / "esphome" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)

vsroot = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Microsoft Visual Studio"
setups = sorted(vsroot.glob("*/Community/VC/Auxiliary/Build/vcvars64.bat"))
if not setups:
    raise SystemExit("MSVC Community vcvars64.bat not found")
component = root / "components" / "pylontech_dual_proxy"
command = (f'call "{setups[-1]}" >nul && cl /nologo /EHsc /std:c++17 '
           f'/DUSE_BINARY_SENSOR /I"{build}" /I"{component}" '
           f'"{root / "tests" / "router_replies.cpp"}" '
           f'"{component / "pylontech_dual_proxy.cpp"}" /Fe:router_replies.exe '
           '&& router_replies.exe')
subprocess.run(command, shell=True, cwd=build, check=True)

#include "pylontech_dual_proxy.h"
#include <cassert>
#include <iostream>

uint32_t esphome::test_now = 100;
using esphome::pylontech_dual_proxy::PylontechDualProxy;

class TestProxy : public PylontechDualProxy {
 public:
  using PylontechDualProxy::calculate_checksum_;
  using PylontechDualProxy::pending_requests_;
  using PylontechDualProxy::shared_snapshot_;
};

std::string frame(const std::string &rtn) {
  const std::string payload = "200246" + rtn + "0000";
  return "~" + payload + TestProxy::calculate_checksum_(payload) + "\r";
}

int main() {
  TestProxy battery, inv1, inv2;
  battery.set_battery_port(true);
  battery.setup(); inv1.setup(); inv2.setup();
  esphome::text_sensor::TextSensor decoded;
  battery.set_last_battery_snapshot_sensor(&decoded);
  const std::string request1 = "~201246630000FDA8\r";
  const std::string request2 = "~200246610000FDAB\r";

  // Both ports use the same battery address in normal operation. An error
  // must go to the requesting UART, release the queue, and never update data.
  for (const auto &rtn : {"01", "02", "03", "04", "05", "06", "90", "91"}) {
    battery.tx.clear(); inv1.tx.clear(); inv2.tx.clear(); decoded.values.clear();
    inv1.rx = request1; inv1.loop();
    inv2.rx = request2; inv2.loop();
    assert(battery.tx.size() == 1 && battery.tx[0] == request1);
    battery.rx = frame(rtn); battery.loop();
    assert(inv1.tx.size() == 1 && inv1.tx[0] == frame(rtn));
    assert(inv2.tx.empty());
    assert(decoded.values.empty());
    assert(battery.tx.size() == 2 && battery.tx[1] == request2);
    assert(TestProxy::pending_requests_.size() == 1);
    battery.rx = frame("00"); battery.loop();
    assert(inv2.tx.size() == 1 && inv2.tx[0] == frame("00"));
    assert(TestProxy::pending_requests_.empty());
  }

  // With no transaction, neither success nor error replies are broadcasts.
  inv1.tx.clear(); inv2.tx.clear();
  battery.rx = frame("00") + frame("02"); battery.loop();
  assert(inv1.tx.empty() && inv2.tx.empty());

  // Preserve the existing event path and leave the outstanding request intact.
  inv2.rx = request2; inv2.loop();
  battery.rx = frame("62"); battery.loop();
  assert(inv1.tx.size() == 1 && inv2.tx.size() == 1);
  assert(TestProxy::pending_requests_.size() == 1);
  battery.rx = frame("02"); battery.loop();
  assert(inv1.tx.size() == 1 && inv2.tx.size() == 2);
  assert(TestProxy::pending_requests_.empty());

  // Malformed frames cannot complete a transaction.
  inv1.rx = request1; inv1.loop();
  battery.rx = "~200246020000FFFF\r"; battery.loop();
  assert(TestProxy::pending_requests_.size() == 1);
  esphome::test_now += 1501; battery.loop();
  assert(TestProxy::pending_requests_.empty());
  std::cout << "PASS: error ownership, queue release, success replies, orphan replies, events, invalid frames and timeout\n";
}

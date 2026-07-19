#pragma once

// Classic Bluetooth SPP exposes the same binary serial protocol as USB.
void bluetooth_begin();
void bluetooth_handle();
bool bluetooth_available();

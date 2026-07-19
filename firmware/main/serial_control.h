#pragma once

#include <Arduino.h>

void serial_control_begin();
void serial_control_handle();
void serial_control_handle_stream(Stream& stream);

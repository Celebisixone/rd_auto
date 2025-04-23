import serial, time

ser = serial.Serial(
    'COM6',           # your pump’s COM port
    baudrate=4800,
    bytesize=serial.SEVENBITS,
    parity=serial.PARITY_ODD,
    stopbits=serial.STOPBITS_ONE,
    timeout=1
)

# assume ser is your open 7E1,4800 serial.Serial instance

# 1) Enable Remote mode
ser.write(b'\x02P01R\x0D')     # <STX>P01R<CR>
print("Remote on:", ser.read(ser.in_waiting or 1))

# 2) Zero revolutions-to-go
ser.write(b'\x02P01Z\x0D')     # <STX>P01Z<CR>
print("Zero revs:", ser.read(ser.in_waiting or 1))

# 3) Set speed (60 RPM CW)
ser.write(b'\x02P01S+60.0\x0D')
print("Speed set:", ser.read(ser.in_waiting or 1))

# 4) START the pump
ser.write(b'\x02P01G0\x0D')
resp = ser.read(ser.in_waiting or 1)
print("Go response:", resp)

# If resp is 0x06, it’s running. If it’s still 0x15, STOP is still latched!

# 5) After your test interval, STOP it
time.sleep(30)
ser.write(b'\x02P01H\x0D')
print("Halt:", ser.read(ser.in_waiting or 1))

ser.close()



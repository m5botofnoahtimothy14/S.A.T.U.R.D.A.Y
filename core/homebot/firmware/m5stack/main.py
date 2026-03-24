"""
AEGIS HomeBot for M5Stack CORE2
MicroPython v1.0
================================
Voice controlled robot via serial
"""
import machine
import time
import sys

# M5Stack CORE2 I2C motor driver (KAISE or similar)
# Using GPIO pins for motor control
MOTOR_A_PWM = 32
MOTOR_A_DIR1 = 33
MOTOR_A_DIR2 = 25
MOTOR_B_PWM = 26
MOTOR_B_DIR1 = 27
MOTOR_B_DIR2 = 14

# Initialize
def init():
    global pwm_a, pwm_b
    
    # Motor A
    machine.Pin(MOTOR_A_DIR1, machine.Pin.OUT)
    machine.Pin(MOTOR_A_DIR2, machine.Pin.OUT)
    pwm_a = machine.PWM(machine.Pin(MOTOR_A_PWM), freq=1000)
    pwm_a.duty(0)
    
    # Motor B
    machine.Pin(MOTOR_B_DIR1, machine.Pin.OUT)
    machine.Pin(MOTOR_B_DIR2, machine.Pin.OUT)
    pwm_b = machine.PWM(machine.Pin(MOTOR_B_PWM), freq=1000)
    pwm_b.duty(0)
    
    stop()
    print("AEGIS_HOMEBOT_READY")
    print("M5Stack CORE2 MicroPython v1.0")

def stop():
    pwm_a.duty(0)
    pwm_b.duty(0)
    machine.Pin(MOTOR_A_DIR1).value(0)
    machine.Pin(MOTOR_A_DIR2).value(0)
    machine.Pin(MOTOR_B_DIR1).value(0)
    machine.Pin(MOTOR_B_DIR2).value(0)

def forward(speed=800):
    pwm_a.duty(speed)
    pwm_b.duty(speed)
    machine.Pin(MOTOR_A_DIR1).value(1)
    machine.Pin(MOTOR_A_DIR2).value(0)
    machine.Pin(MOTOR_B_DIR1).value(1)
    machine.Pin(MOTOR_B_DIR2).value(0)

def backward(speed=800):
    pwm_a.duty(speed)
    pwm_b.duty(speed)
    machine.Pin(MOTOR_A_DIR1).value(0)
    machine.Pin(MOTOR_A_DIR2).value(1)
    machine.Pin(MOTOR_B_DIR1).value(0)
    machine.Pin(MOTOR_B_DIR2).value(1)

def left(speed=800):
    pwm_a.duty(speed)
    pwm_b.duty(speed)
    machine.Pin(MOTOR_A_DIR1).value(0)
    machine.Pin(MOTOR_A_DIR2).value(1)
    machine.Pin(MOTOR_B_DIR1).value(1)
    machine.Pin(MOTOR_B_DIR2).value(0)

def right(speed=800):
    pwm_a.duty(speed)
    pwm_b.duty(speed)
    machine.Pin(MOTOR_A_DIR1).value(1)
    machine.Pin(MOTOR_A_DIR2).value(0)
    machine.Pin(MOTOR_B_DIR1).value(0)
    machine.Pin(MOTOR_B_DIR2).value(1)

def rotate_left(speed=500):
    pwm_a.duty(speed)
    pwm_b.duty(speed)
    machine.Pin(MOTOR_A_DIR1).value(0)
    machine.Pin(MOTOR_A_DIR2).value(1)
    machine.Pin(MOTOR_B_DIR1).value(1)
    machine.Pin(MOTOR_B_DIR2).value(0)

def rotate_right(speed=500):
    pwm_a.duty(speed)
    pwm_b.duty(speed)
    machine.Pin(MOTOR_A_DIR1).value(1)
    machine.Pin(MOTOR_A_DIR2).value(0)
    machine.Pin(MOTOR_B_DIR1).value(0)
    machine.Pin(MOTOR_B_DIR2).value(1)

def process(cmd):
    cmd = cmd.strip().upper()
    
    if cmd == "PING":
        return "PONG"
    elif cmd == "STATUS":
        return "STATUS:OK|HOMEBOT_ONLINE|M5STACK_CORE2"
    elif cmd == "INFO":
        return "AEGIS_HOMEBOT_V1.0|M5STACK_CORE2|2_MOTORS"
    elif cmd == "HELP":
        return "FWD|REV|LFT|RGT|RTL|RTR|STP|PING|STATUS"
    elif cmd == "FWD":
        forward()
        return "MOVING:FWD"
    elif cmd == "REV":
        backward()
        return "MOVING:REV"
    elif cmd == "LFT":
        left()
        return "MOVING:LFT"
    elif cmd == "RGT":
        right()
        return "MOVING:RGT"
    elif cmd == "RTL":
        rotate_left()
        return "ROTATING:LEFT"
    elif cmd == "RTR":
        rotate_right()
        return "ROTATING:RIGHT"
    elif cmd == "STP":
        stop()
        return "STOPPED"
    else:
        return "UNKNOWN:" + cmd

# Main loop
init()
uart = machine.UART(2, 115200, tx=17, rx=16)
uart.init(115200)

buffer = ""

while True:
    if uart.any():
        data = uart.read()
        if data:
            for b in data:
                c = chr(b) if 32 <= b < 127 else ''
                if c == '\n' or c == '\r':
                    if buffer.strip():
                        resp = process(buffer)
                        print(resp)
                        uart.write(resp + "\r\n")
                        buffer = ""
                else:
                    buffer += c
    
    # Check serial from USB
    if sys.stdin.any():
        data = sys.stdin.read(1)
        if data == '\n' or data == '\r':
            if buffer.strip():
                resp = process(buffer)
                print(resp)
                buffer = ""
        else:
            buffer += data
    
    time.sleep_ms(10)

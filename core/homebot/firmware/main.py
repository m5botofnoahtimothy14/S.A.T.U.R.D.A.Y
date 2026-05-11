
import machine
import time
import ujson

MOTOR_A_IN1 = 2
MOTOR_A_IN2 = 4
MOTOR_A_ENA = 5
MOTOR_B_IN1 = 18
MOTOR_B_IN2 = 19
MOTOR_B_ENB = 21

LED = 22

def init_pins():
             
    machine.Pin(MOTOR_A_IN1, machine.Pin.OUT)
    machine.Pin(MOTOR_A_IN2, machine.Pin.OUT)
    machine.Pin(MOTOR_A_ENA, machine.Pin.OUT)
    
    machine.Pin(MOTOR_B_IN1, machine.Pin.OUT)
    machine.Pin(MOTOR_B_IN2, machine.Pin.OUT)
    machine.Pin(MOTOR_B_ENB, machine.Pin.OUT)
    
    machine.Pin(LED, machine.Pin.OUT)
    
    global pwm_a, pwm_b
    pwm_a = machine.PWM(machine.Pin(MOTOR_A_ENA))
    pwm_b = machine.PWM(machine.Pin(MOTOR_B_ENB))
    pwm_a.freq(1000)
    pwm_b.freq(1000)
    pwm_a.duty(0)
    pwm_b.duty(0)
    
    stop()

def stop():
    pwm_a.duty(0)
    pwm_b.duty(0)
    machine.Pin(MOTOR_A_IN1).value(0)
    machine.Pin(MOTOR_A_IN2).value(0)
    machine.Pin(MOTOR_B_IN1).value(0)
    machine.Pin(MOTOR_B_IN2).value(0)

def forward(speed=600):
    pwm_a.duty(speed)
    pwm_b.duty(speed)
    machine.Pin(MOTOR_A_IN1).value(1)
    machine.Pin(MOTOR_A_IN2).value(0)
    machine.Pin(MOTOR_B_IN1).value(1)
    machine.Pin(MOTOR_B_IN2).value(0)

def backward(speed=600):
    pwm_a.duty(speed)
    pwm_b.duty(speed)
    machine.Pin(MOTOR_A_IN1).value(0)
    machine.Pin(MOTOR_A_IN2).value(1)
    machine.Pin(MOTOR_B_IN1).value(0)
    machine.Pin(MOTOR_B_IN2).value(1)

def left(speed=600):
    pwm_a.duty(speed)
    pwm_b.duty(speed)
    machine.Pin(MOTOR_A_IN1).value(0)
    machine.Pin(MOTOR_A_IN2).value(1)
    machine.Pin(MOTOR_B_IN1).value(1)
    machine.Pin(MOTOR_B_IN2).value(0)

def right(speed=600):
    pwm_a.duty(speed)
    pwm_b.duty(speed)
    machine.Pin(MOTOR_A_IN1).value(1)
    machine.Pin(MOTOR_A_IN2).value(0)
    machine.Pin(MOTOR_B_IN1).value(0)
    machine.Pin(MOTOR_B_IN2).value(1)

def rotate_left(speed=400):
    pwm_a.duty(speed)
    pwm_b.duty(speed)
    machine.Pin(MOTOR_A_IN1).value(0)
    machine.Pin(MOTOR_A_IN2).value(1)
    machine.Pin(MOTOR_B_IN1).value(1)
    machine.Pin(MOTOR_B_IN2).value(0)

def rotate_right(speed=400):
    pwm_a.duty(speed)
    pwm_b.duty(speed)
    machine.Pin(MOTOR_A_IN1).value(1)
    machine.Pin(MOTOR_A_IN2).value(0)
    machine.Pin(MOTOR_B_IN1).value(0)
    machine.Pin(MOTOR_B_IN2).value(1)

def blink_led():
    p = machine.Pin(LED)
    p.value(1)
    time.sleep_ms(100)
    p.value(0)

def process_command(cmd):
    cmd = cmd.strip().upper()
    
    if cmd == "PING":
        return "PONG"
    elif cmd == "STATUS":
        return "STATUS:OK|HOMEBOT_ONLINE"
    elif cmd == "INFO":
        return "SATURDAY_HOMEBOT_V1.0|ESP32|MOTORS:2"
    elif cmd == "HELP":
        return "FWD|REV|LFT|RGT|RTL|RTR|STP|PING|STATUS|INFO"
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

def main():
    init_pins()
    
    uart = machine.UART(0, 115200)
    uart.init(115200, bits=8, parity=None, stop=1)
    
    print("SATURDAY_HOMEBOT_READY")
    print("ESP32 MicroPython v1.0")
    
    buffer = ""
    
    while True:
        if uart.any():
            char = uart.read(1)
            if char:
                c = char.decode('utf-8', 'ignore')
                
                if c == '\n' or c == '\r':
                    if buffer.strip():
                        blink_led()
                        response = process_command(buffer)
                        print(response)
                        uart.write(response + "\r\n")
                        buffer = ""
                else:
                    buffer += c
        
        time.sleep(1)

if __name__ == "__main__":
    main()

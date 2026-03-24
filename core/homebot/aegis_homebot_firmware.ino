/*
 * AEGIS HomeBot Firmware v1.0
 * Compatible with AEGIS Voice Control System
 * 
 * Hardware: Arduino/ESP32 with motor driver
 * Connection: Serial at 115200 baud
 * 
 * Commands:
 *   FWD - Move forward
 *   REV - Move backward  
 *   LFT - Move left
 *   RGT - Move right
 *   RTL - Rotate left
 *   RTR - Rotate right
 *   STP - Stop
 *   PING - Check connection
 *   STATUS - Get status
 *   INFO - Device info
 */

#include <Arduino.h>

// Motor pins (customize for your setup)
#define MOTOR_A_IN1 2
#define MOTOR_A_IN2 3
#define MOTOR_A_ENA 4
#define MOTOR_B_IN1 5
#define MOTOR_B_IN2 6
#define MOTOR_B_ENB 7

// LED indicator
#define LED_PIN 13

String command = "";
bool commandComplete = false;

void setup() {
    Serial.begin(115200);
    
    // Initialize motor pins
    pinMode(MOTOR_A_IN1, OUTPUT);
    pinMode(MOTOR_A_IN2, OUTPUT);
    pinMode(MOTOR_A_ENA, OUTPUT);
    pinMode(MOTOR_B_IN1, OUTPUT);
    pinMode(MOTOR_B_IN2, OUTPUT);
    pinMode(MOTOR_B_ENB, OUTPUT);
    pinMode(LED_PIN, OUTPUT);
    
    // Ensure motors are stopped
    stopMotors();
    digitalWrite(LED_PIN, LOW);
    
    // Send ready signal
    Serial.println("AEGIS_HOMEBOT_READY");
    Serial.println("Type HELP for commands");
}

void loop() {
    // Read serial commands
    while (Serial.available()) {
        char inChar = (char)Serial.read();
        
        if (inChar == '\\n' || inChar == '\\r') {
            if (command.length() > 0) {
                commandComplete = true;
            }
        } else {
            command += inChar;
        }
    }
    
    // Process command
    if (commandComplete) {
        processCommand(command);
        command = "";
        commandComplete = false;
    }
}

void processCommand(String cmd) {
    cmd.trim();
    cmd.toUpperCase();
    
    if (cmd == "PING") {
        Serial.println("PONG");
    }
    else if (cmd == "STATUS") {
        Serial.println("STATUS:OK");
        Serial.println("HOMEBOT_ONLINE");
    }
    else if (cmd == "INFO") {
        Serial.println("AEGIS_HOMEBOT_V1.0");
        Serial.println("MOTORS:2");
        Serial.println("SENSORS:0");
    }
    else if (cmd == "HELP") {
        Serial.println("AEGIS HomeBot Commands:");
        Serial.println("  FWD  - Forward");
        Serial.println("  REV  - Backward");
        Serial.println("  LFT  - Left");
        Serial.println("  RGT  - Right");
        Serial.println("  RTL  - Rotate Left");
        Serial.println("  RTR  - Rotate Right");
        Serial.println("  STP  - Stop");
        Serial.println("  PING - Check");
        Serial.println("  STATUS - Status");
        Serial.println("  INFO - Info");
    }
    else if (cmd == "FWD") {
        moveForward();
        Serial.println("MOVING:FWD");
    }
    else if (cmd == "REV") {
        moveBackward();
        Serial.println("MOVING:REV");
    }
    else if (cmd == "LFT") {
        moveLeft();
        Serial.println("MOVING:LFT");
    }
    else if (cmd == "RGT") {
        moveRight();
        Serial.println("MOVING:RGT");
    }
    else if (cmd == "RTL") {
        rotateLeft();
        Serial.println("ROTATING:LEFT");
    }
    else if (cmd == "RTR") {
        rotateRight();
        Serial.println("ROTATING:RIGHT");
    }
    else if (cmd == "STP") {
        stopMotors();
        Serial.println("STOPPED");
    }
    else {
        Serial.println("UNKNOWN_COMMAND:" + cmd);
    }
    
    // Blink LED on command
    digitalWrite(LED_PIN, HIGH);
    delay(100);
    digitalWrite(LED_PIN, LOW);
}

void moveForward() {
    digitalWrite(MOTOR_A_IN1, HIGH);
    digitalWrite(MOTOR_A_IN2, LOW);
    analogWrite(MOTOR_A_ENA, 200);
    digitalWrite(MOTOR_B_IN1, HIGH);
    digitalWrite(MOTOR_B_IN2, LOW);
    analogWrite(MOTOR_B_ENB, 200);
}

void moveBackward() {
    digitalWrite(MOTOR_A_IN1, LOW);
    digitalWrite(MOTOR_A_IN2, HIGH);
    analogWrite(MOTOR_A_ENA, 200);
    digitalWrite(MOTOR_B_IN1, LOW);
    digitalWrite(MOTOR_B_IN2, HIGH);
    analogWrite(MOTOR_B_ENB, 200);
}

void moveLeft() {
    digitalWrite(MOTOR_A_IN1, LOW);
    digitalWrite(MOTOR_A_IN2, HIGH);
    analogWrite(MOTOR_A_ENA, 200);
    digitalWrite(MOTOR_B_IN1, HIGH);
    digitalWrite(MOTOR_B_IN2, LOW);
    analogWrite(MOTOR_B_ENB, 200);
}

void moveRight() {
    digitalWrite(MOTOR_A_IN1, HIGH);
    digitalWrite(MOTOR_A_IN2, LOW);
    analogWrite(MOTOR_A_ENA, 200);
    digitalWrite(MOTOR_B_IN1, LOW);
    digitalWrite(MOTOR_B_IN2, HIGH);
    analogWrite(MOTOR_B_ENB, 200);
}

void rotateLeft() {
    digitalWrite(MOTOR_A_IN1, LOW);
    digitalWrite(MOTOR_A_IN2, HIGH);
    analogWrite(MOTOR_A_ENA, 150);
    digitalWrite(MOTOR_B_IN1, HIGH);
    digitalWrite(MOTOR_B_IN2, LOW);
    analogWrite(MOTOR_B_ENB, 150);
}

void rotateRight() {
    digitalWrite(MOTOR_A_IN1, HIGH);
    digitalWrite(MOTOR_A_IN2, LOW);
    analogWrite(MOTOR_A_ENA, 150);
    digitalWrite(MOTOR_B_IN1, LOW);
    digitalWrite(MOTOR_B_IN2, HIGH);
    analogWrite(MOTOR_B_ENB, 150);
}

void stopMotors() {
    digitalWrite(MOTOR_A_IN1, LOW);
    digitalWrite(MOTOR_A_IN2, LOW);
    digitalWrite(MOTOR_B_IN1, LOW);
    digitalWrite(MOTOR_B_IN2, LOW);
    analogWrite(MOTOR_A_ENA, 0);
    analogWrite(MOTOR_B_ENB, 0);
}

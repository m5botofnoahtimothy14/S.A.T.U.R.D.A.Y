
#include <Arduino.h>

#define MOTOR_A_IN1 2
#define MOTOR_A_IN2 3
#define MOTOR_A_ENA 4
#define MOTOR_B_IN1 5
#define MOTOR_B_IN2 6
#define MOTOR_B_ENB 7

#define LED_PIN 13

String command = "";
bool commandComplete = false;

void setup() {
    Serial.begin(115200);
    
    pinMode(MOTOR_A_IN1, OUTPUT);
    pinMode(MOTOR_A_IN2, OUTPUT);
    pinMode(MOTOR_A_ENA, OUTPUT);
    pinMode(MOTOR_B_IN1, OUTPUT);
    pinMode(MOTOR_B_IN2, OUTPUT);
    pinMode(MOTOR_B_ENB, OUTPUT);
    pinMode(LED_PIN, OUTPUT);
    
    stopMotors();
    digitalWrite(LED_PIN, LOW);
    
    Serial.println("AEGIS_HOMEBOT_READY");
    Serial.println("Type HELP for commands");
}

void loop() {
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

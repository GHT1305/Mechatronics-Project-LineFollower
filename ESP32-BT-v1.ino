#include "BluetoothSerial.h"

// Motor driver (TB6612)
const int PIN_IN1 = 22;   // AIN1
const int PIN_IN2 = 18;   // AIN2
const int PIN_PWM = 23;   // PWMA (PWM output)

// Encoder
const int ENC_A   = 35;   // C1/A
const int ENC_B   = 34;   // C2/B
const int ENCODER_PPR = 660; // pulses per revolution

// LED, button
const int LED = 2;

// Bluetooth SPP mode
BluetoothSerial SerialBT;

// --- Logging & control ---
const unsigned long LOG_INTERVAL_MS = 10;
unsigned long lastLogTime = 0;
volatile long encoderPos = 0;
volatile int  lastA     = LOW;
long lastEncoderCount = 0;
int  currentPWM = 0;
unsigned long lastBlink = 0;
bool isRunning = false; // Motor trạng thái chạy
long encoderPosStart = 0; // Mốc khi bấm START
float distanceTraveled = 0;

bool ledState = false;

uint8_t D_wheel = 65;

// ISR đọc encoder
void IRAM_ATTR handleEncoder() {
  int a = digitalRead(ENC_A);
  int b = digitalRead(ENC_B);
  if (a != lastA) {
    encoderPos += (a == b) ? +1 : -1;
    lastA = a;
  }
}

// Stop motor
void stopMotor() {
  digitalWrite(PIN_IN1, LOW);
  digitalWrite(PIN_IN2, LOW);
  analogWrite(PIN_PWM, 0);
  currentPWM = 0;
}

// Set speed, direction by PWM, PWM ∈ [-255..+255]
void setMotorPWM(int pwm) {
  pwm = constrain(pwm, -255, 255);
  currentPWM = pwm;
  if (pwm > 0) {
    digitalWrite(PIN_IN1, HIGH);
    digitalWrite(PIN_IN2, LOW);
    analogWrite(PIN_PWM, pwm);
  }
  else if (pwm < 0) {
    pwm = -pwm;
    digitalWrite(PIN_IN1, LOW);
    digitalWrite(PIN_IN2, HIGH);
    analogWrite(PIN_PWM, pwm);
  }
  else {
    stopMotor();
  }
}

void setup() {
  Serial.begin(115200);
  SerialBT.begin("ESP32test");
  pinMode(LED, OUTPUT);

  // Motor-driver pins
  pinMode(PIN_IN1, OUTPUT);
  pinMode(PIN_IN2, OUTPUT);
  pinMode(PIN_PWM, OUTPUT);
  stopMotor();

  // Encoder pins + interrupt
  pinMode(ENC_A, INPUT_PULLUP);
  pinMode(ENC_B, INPUT_PULLUP);
  lastA = digitalRead(ENC_A);
  attachInterrupt(digitalPinToInterrupt(ENC_A), handleEncoder, CHANGE);
}

void loop() {
  unsigned long now = millis();

  // If BT is connected -> Blink LED
  if (SerialBT.hasClient() && (now - lastBlink >= 200)) {
    ledState = !ledState;
    digitalWrite(LED, ledState ? HIGH : LOW);
    lastBlink = now;
  }

  // 1) Nhận lệnh PWM qua SerialBT (−255…+255)
  if (SerialBT.available()) {
    String line = SerialBT.readStringUntil('\n');
    line.trim();
    if (line.length() > 1 && line.charAt(0) == 'L') { // chỉ nhận khi bắt đầu bằng 'L'
      int pwmValue = line.substring(1).toInt();  // lấy chuỗi phía sau ký tự 'L'
      setMotorPWM(pwmValue);
    }

    if (line.equalsIgnoreCase("START")) {
      setMotorPWM(100);
      isRunning = true;
      encoderPosStart = encoderPos; // Đặt mốc
      distanceTraveled = 0; // Reset quãng đường
    }
    else if (line.equalsIgnoreCase("STOP")) {
      setMotorPWM(0);
      isRunning = false;
      // Không reset encoderPosStart, giữ distanceTraveled cho tới lần START tiếp theo
    }
  }

  // 2) Ghi log mỗi LOG_INTERVAL_MS
  unsigned long dt = now - lastLogTime;
  if (now - lastLogTime >= 10) {
    // Lấy số xung trong khoảng thời gian dt
    long deltaCounts = encoderPos - lastEncoderCount;
    lastEncoderCount = encoderPos;

    // Tính RPM: (số vòng quay trong dt) × (60000 ms / phút) / dt
    // số vòng = deltaCounts / ENCODER_PPR
    float rpm = (deltaCounts / (float)ENCODER_PPR) * (60000.0f / dt);
    float vel = (rpm / 60) * (D_wheel * 3.14);

    if (isRunning) {
      long encoderDelta = encoderPos - encoderPosStart;
      // 1 vòng = ENCODER_PPR xung, chuyển ra mét với đường kính D_wheel
      // Khoảng cách = số vòng * chu vi bánh xe
      distanceTraveled = (encoderDelta / (float)ENCODER_PPR) * (D_wheel * 3.14); // mm
    }
    
    char buf[32];
    sprintf(buf, "%.2f,%.2f,%.2f", vel, vel, distanceTraveled);
    SerialBT.println(buf);

    lastLogTime = now;
  }
  
  // // Truyền dữ liệu từ serial USB tới Bluetooth
  // if (Serial.available()) {
  //   SerialBT.write(Serial.read());
  // }
  // // Truyền dữ liệu từ Bluetooth tới serial USB
  // if (SerialBT.available()) {
  //   Serial.write(SerialBT.read());
  // }
}

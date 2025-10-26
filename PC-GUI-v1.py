import serial, threading, time
import customtkinter as ctk

SERIAL_PORT = "COM13"
BAUDRATE = 115200

class ESP32Monitor(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("ESP32 Motor Monitor")
        self.geometry("600x400")
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        # Serial
        self.ser = None
        self.last_rx_time = time.time()
        self.running = True
        self.mode = "Auto"
        self.connected = False

        # --- System Frame ---
        sys_frame = ctk.CTkFrame(self, fg_color="#ecf0f1", corner_radius=10)
        sys_frame.place(relx=0.01, rely=0.01, relwidth=0.98, relheight=0.23)
        
        # System title
        system_title = ctk.CTkLabel(sys_frame, text="SYSTEM", font=("Arial", 16, "bold"))
        system_title.place(x=10, y=5)
        
        self.status_label = ctk.CTkLabel(sys_frame, text="Status: Disconnected", text_color="red", font=("Arial", 18))
        self.status_label.place(x=10, y=30)
        self.mode_toggle = ctk.CTkSegmentedButton(sys_frame, values=["Auto", "Manual"], command=self.toggle_mode)
        self.mode_toggle.set("Auto")
        self.mode_toggle.place(x=220, y=30)
        self.left_speed_label = ctk.CTkLabel(sys_frame, text="Left motor: 0.00 mm/s", font=("Arial", 14))
        self.left_speed_label.place(x=10, y=65)
        self.right_speed_label = ctk.CTkLabel(sys_frame, text="Right motor: 0.00 mm/s", font=("Arial", 14))
        self.right_speed_label.place(x=250, y=65)

        # --- Auto Mode Frame ---
        self.auto_frame = ctk.CTkFrame(self, fg_color="#daf7a6", corner_radius=10)
        self.auto_frame.place(relx=0.01, rely=0.25, relwidth=0.98, relheight=0.28)
        
        # Auto Mode title
        auto_title = ctk.CTkLabel(self.auto_frame, text="AUTO MODE", font=("Arial", 16, "bold"))
        auto_title.place(x=10, y=5)
        
        # Combined Start/Stop button
        self.start_stop_btn = ctk.CTkButton(self.auto_frame, text="Start", command=self.toggle_start_stop, 
                                          width=100, fg_color="#4CAF50", hover_color="#45a049")
        self.start_stop_btn.place(x=10, y=35)
        self.is_running = False
        self.distance = ctk.CTkLabel(self.auto_frame, text="Distance: 0.00 mm", font=("Arial", 14))
        self.distance.place(x=180, y=40)
        self.auto_time = ctk.CTkLabel(self.auto_frame, text="Time: 00:00.00", font=("Arial", 14))
        self.auto_time.place(x=350, y=40)
        self.timer_running = False
        self.timer_start = 0
        self.timer_elapsed = 0

        # --- Manual Mode Frame ---
        self.manual_frame = ctk.CTkFrame(self, fg_color="#aed6f1", corner_radius=10)
        self.manual_frame.place(relx=0.01, rely=0.54, relwidth=0.98, relheight=0.25)
        
        # Manual Mode title
        manual_title = ctk.CTkLabel(self.manual_frame, text="MANUAL MODE", font=("Arial", 16, "bold"))
        manual_title.place(x=10, y=5)
        
        ctk.CTkLabel(self.manual_frame, text="Left speed (PWM):", font=("Arial", 13)).place(x=10, y=35)
        self.left_entry = ctk.CTkEntry(self.manual_frame, width=60)
        self.left_entry.place(x=130, y=35)
        self.left_send = ctk.CTkButton(self.manual_frame, text="Send", command=self.send_left, width=50)
        self.left_send.place(x=200, y=35)

        ctk.CTkLabel(self.manual_frame, text="Right speed (PWM):", font=("Arial", 13)).place(x=270, y=35)
        self.right_entry = ctk.CTkEntry(self.manual_frame, width=60)
        self.right_entry.place(x=390, y=35)
        self.right_send = ctk.CTkButton(self.manual_frame, text="Send", command=self.send_right, width=50)
        self.right_send.place(x=460, y=35)

        # Disable manual at start
        self.set_mode_state()

        # Thread đọc dữ liệu serial không làm kẹt GUI
        threading.Thread(target=self.serial_thread, daemon=True).start()
        self.after(100, self.update_connect_status)
        self.after(50, self.update_timer)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def serial_open(self):
        try:
            # Giảm timeout từ 0.1s xuống 0.01s (10ms)
            self.ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=0.01)
            self.connected = True
            self.status_label.configure(text="ESP32: Connected", text_color="green")
        except:
            self.connected = False
            self.status_label.configure(text="ESP32: Disconnected", text_color="red")
            self.ser = None

    def serial_thread(self):
        while self.running:
            if not self.ser or not self.ser.is_open:
                self.serial_open()
                time.sleep(1)
                continue
            try:
                line = self.ser.readline()
                if line:
                    self.last_rx_time = time.time()
                    msg = line.decode().strip()
                    # ESP gửi "200.5,300.35,1000.2"
                    parts = msg.split(",")
                    if len(parts) >= 3:
                        left, right, dist = parts[:3]
                        # Sử dụng after() để update GUI trong main thread
                        self.after(0, lambda: self.update_display(left, right, dist))
                    # Nếu đang chạy Auto thì update đồng hồ
                    if self.timer_running:
                        self.timer_elapsed = time.time() - self.timer_start
            except Exception as ex:
                self.connected = False
                self.status_label.configure(text="ESP32 : Disconnected", text_color="red")
                self.ser = None
            # Giảm sleep từ 10ms xuống 1ms
            time.sleep(0.001)

    def update_connect_status(self):
        # Nếu quá 300ms không nhận được dữ liệu => mất kết nối
        if time.time() - self.last_rx_time > 0.3:
            self.connected = False
            self.status_label.configure(text="ESP32: Disconnected", text_color="red")
        else:
            self.connected = True
            self.status_label.configure(text="ESP32: Connected", text_color="green")
        self.after(100, self.update_connect_status)

    def toggle_mode(self, val):
        self.mode = val
        # Gửi lệnh tới ESP32
        if self.ser and self.ser.is_open:
            if val == "Auto":
                self.ser.write(b"MODE-A\n")
                print("Sent: MODE-A")
            else:
                self.ser.write(b"MODE-M\n")
                print("Sent: MODE-M")
        self.set_mode_state()

    def set_mode_state(self):
        if self.mode == "Auto":
            self.start_stop_btn.configure(state="normal")
            self.left_entry.configure(state="disabled")
            self.right_entry.configure(state="disabled")
            self.left_send.configure(state="disabled")
            self.right_send.configure(state="disabled")
            self.auto_frame.configure(fg_color="#daf7a6")
            self.manual_frame.configure(fg_color="#ddd")
        else:
            self.start_stop_btn.configure(state="disabled")
            self.left_entry.configure(state="normal")
            self.right_entry.configure(state="normal")
            self.left_send.configure(state="normal")
            self.right_send.configure(state="normal")
            self.auto_frame.configure(fg_color="#ddd")
            self.manual_frame.configure(fg_color="#aed6f1")

    def toggle_start_stop(self):
        if not self.is_running:
            # Start
            if self.ser and self.ser.is_open:
                self.ser.write(b"START\n")
                print("Sent: START")
            self.timer_running = True
            self.timer_start = time.time()
            self.timer_elapsed = 0
            self.is_running = True
            self.start_stop_btn.configure(text="Stop", fg_color="#f44336", hover_color="#d32f2f")
        else:
            # Stop
            if self.ser and self.ser.is_open:
                self.ser.write(b"STOP\n")
                print("Sent: STOP")
            self.timer_running = False
            self.is_running = False
            self.start_stop_btn.configure(text="Start", fg_color="#4CAF50", hover_color="#45a049")

    # def start_auto(self):
    #     if self.ser and self.ser.is_open:
    #         # self.ser.write(b"START\n")
    #         self.ser.write(b"100\n")
    #     self.timer_running = True
    #     self.timer_start = time.time()
    #     self.timer_elapsed = 0

    # def stop_auto(self):
    #     if self.ser and self.ser.is_open:
    #         # self.ser.write(b"STOP\n")
    #         self.ser.write(b"0\n")
    #     self.timer_running = False

    def update_timer(self):
        if self.timer_running:
            t = self.timer_elapsed
            min_ = int(t // 60)
            sec_ = int(t % 60)
            ms_ = int((t - int(t)) * 100)
            self.auto_time.configure(text=f"Time: {min_:02d}:{sec_:02d}.{ms_:02d}")
        self.after(30, self.update_timer)

    def send_left(self):
        val = self.left_entry.get()
        try:
            float(val)
            if self.ser and self.ser.is_open:
                cmd = f"L{val}\n"
                self.ser.write(cmd.encode())
                print(f"Sent: {cmd}")
        except ValueError:
            print("Invalid value\n")
            pass

    def send_right(self):
        val = self.right_entry.get()
        try:
            float(val)
            if self.ser and self.ser.is_open:
                cmd = f"R{val}\n"
                self.ser.write(cmd.encode())
                print(f"Sent: {cmd}")
        except ValueError:
            print("Invalid value\n")
            pass

    def on_close(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.destroy()

    def update_display(self, left, right, dist):
        """Update GUI display in main thread"""
        self.left_speed_label.configure(text=f"Left motor: {left} mm/s")
        self.right_speed_label.configure(text=f"Right motor: {right} mm/s")
        self.distance.configure(text=f"Distance: {dist} mm")

if __name__ == "__main__":
    app = ESP32Monitor()
    app.mainloop()

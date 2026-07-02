import tkinter as tk
from tkinter import ttk
import threading
import time
import subprocess
import sys
import hid
import struct
import re
from datetime import datetime
import queue
import os
import serial

class App(tk.Tk):

    INFO_COLOR =            "snow"
    ATTN_COLOR =            "gold"
    ERR_COLOR =             "orange red"
    SUCCESS_COLOR =         "lawn green"
    SEL_COLOR =             "lime"
    SEL_HIGHLIGHT_COLOR =   "lawngreen"
    UNSEL_COLOR =           "snow3"
    UNSEL_HIGHLIGHT_COLOR = "snow"
    START_COLOR =           "lime"

    CONTROL_SCREEN_PORT =   "DP-3"
    DUT_TMDS_PORT =         "HDMI-2"
    DUT_TYPEC_PORT =        "DP-1"

    USBPWR_PORT =           "/dev/ttyUSB0"

    RECONNECT_TIMEOUT =     25

    USBCMD_RESET =          0x00
    USBCMD_POWERDOWN =      0x01
    USBCMD_POWERUP =        0x02
    USBCMD_SETINPUT =       0x03
    USBCMD_REDRAW =         0x04
    USBCMD_SETMODE =        0x05
    USBCMD_NUKE =           0x06
    USBCMD_USBBOOT =        0x07
    USBCMD_RECV =           0x08

    USBRET_GENERALFAIL =    0x00
    USBRET_CHKSUMFAIL =     0x01
    USBRET_SUCCESS =        0x55

    PACKET_SIZE =           64
    PKT_DATA_SIZE =         PACKET_SIZE - 1

    tp_port =               0

    def __init__(self):
        super().__init__()

        print("Glider Flash Tool")
        print("Executable path:", sys.executable)

        subprocess.run(f"xrandr --output {self.DUT_TMDS_PORT} --off", shell=True)
        subprocess.run(f"xrandr --output {self.DUT_TYPEC_PORT} --off", shell=True)

        # Turn off DPMS
        subprocess.run(f"xset s off", shell=True)
        subprocess.run(f"xset -dpms", shell=True)
        subprocess.run(f"xset s noblank", shell=True)

        self.get_tp_port()

        self.scr_size = 6

        self.title("Glider Flashing & Testing Tool")
        self.configure(background="darkgrey")
        self.attributes("-fullscreen", True)

        # Hard coded to run on 1024x768 screen (1000x744)

        # We divide window to 3 parts: STATUS display, OPTION button, LOG output
        # STATUS: 300 px
        # OPTION: 288 px
        # LOG: 132 px

        self.status = tk.StringVar(value="设置屏幕尺寸")
        self.instr = tk.StringVar(value="选择要烧录的屏幕尺寸")

        self.title_label = tk.Label(self, text="Glider 烧录及测试工具", font=("Font", 20))
        self.title_label.pack(ipady=12, fill="x")

        self.status_frame = tk.Frame(self, width=1000, height=288, background=self.INFO_COLOR)
        self.status_frame.pack(padx = 12, pady = 12)

        self.status_label = tk.Label(self.status_frame, textvariable=self.status, font=("Font", 50), background=self.INFO_COLOR)
        self.status_label.place(x = 500, y = 60, anchor="center")

        self.instr_label = tk.Label(self.status_frame, textvariable=self.instr, font=("Font", 40), background=self.INFO_COLOR)
        self.instr_label.place(x=500, y=170, anchor="center")

        self.progress = ttk.Progressbar(self.status_frame, orient = tk.HORIZONTAL, length = 800, mode = 'determinate')
        self.progress.place(x=500, y=260, anchor="center")

        self.option_frame = tk.Frame(self, width=1000, height=240)
        self.option_frame.pack(padx = 12, pady = 0)

        self.btn_6in = tk.Button(self.option_frame, text="6英寸", font=("Font", 40), width = 5, height = 1, pady = 10, background=self.UNSEL_COLOR, command=self.set_6_in)
        self.btn_13in = tk.Button(self.option_frame, text="13英寸", font=("Font", 40), width = 5, height = 1, pady = 10, background=self.UNSEL_COLOR, command=self.set_13_in)

        self.btn_6in.place(x = 50, y = 20)
        self.btn_13in.place(x = 50, y = 130)

        self.btn_start = tk.Button(self.option_frame, text="开始", font=("Font", 50), padx = 80, pady = 50, background=self.UNSEL_COLOR, activebackground=self.SEL_HIGHLIGHT_COLOR, command=self.start_task)
        self.btn_start.place(x = 450, y = 120, anchor="center")
        self.btn_start.config(state="disabled")

        self.btn_stop = tk.Button(self.option_frame, text="取消", font=("Font", 50), padx = 80, pady = 50, background=self.UNSEL_COLOR, command=lambda: self.send_signal("stop"))
        self.btn_stop.place(x = 800, y = 120, anchor="center")
        self.btn_stop.config(state="disabled")

        self.log_frame = tk.Frame(self, width=1000, height=132)
        self.log_frame.pack(padx = 12, pady = 12)

        self.log_text = tk.Text(self.log_frame, height = 6, width = 120)
        self.log_text.place(x = 16, y = 12)
        #self.log_text.config(state="disabled")

        self.btn_exit = tk.Button(self, text="重启", command=self.restart)
        self.btn_exit.place(x = 950, y = 15)

        self.reset_tp_bg()

        self.signal_queue = queue.Queue()

        self.usbpwr_init()
        self.usbpwr_on()

    def restart(self):
        subprocess.Popen([sys.executable] + sys.argv)
        self.destroy()

    def get_tp_port(self):
        completedprocess = subprocess.run(
            'xinput list --id-only "ILITEK ILITEK-TP"',
            shell=True, capture_output=True)
        self.tp_port = int(completedprocess.stdout.decode("utf-8"))
        print(f"TP_PORT: {self.tp_port}")
    
    def usbpwr_init(self):
        self.ser = serial.Serial(self.USBPWR_PORT, 9600, timeout=1)
        print(self.ser.name)
    
    def usbpwr_on(self):
        self.ser.write(b'\xa0\x01\x01\xa2')

    def usbpwr_off(self):
        self.ser.write(b'\xa0\x01\x00\xa1')

    def start_task(self):
        self.btn_6in.config(state="disabled")
        self.btn_13in.config(state="disabled")
        self.btn_start.config(state="disabled")
        self.btn_start.config(background="grey")
        threading.Thread(target=self.flash_test_task, daemon=True).start()

    def send_signal(self, sig):
        self.signal_queue.put(sig)

    def set_ready(self):
        self.status.set("就绪")
        self.instr.set("按下烧录键并插入设备\n两条线均插入后，点击开始进行烧录")
        self.btn_start.config(state="normal")
        self.btn_start.config(background=self.START_COLOR)

    def set_6_in(self):
        self.btn_6in.config(background=self.SEL_COLOR)
        self.btn_6in.config(activebackground=self.SEL_HIGHLIGHT_COLOR)
        self.btn_13in.config(background=self.UNSEL_COLOR)
        self.btn_13in.config(activebackground=self.UNSEL_HIGHLIGHT_COLOR)
        self.scr_size = 6
        self.set_ready()

    def set_13_in(self):
        self.btn_6in.config(background=self.UNSEL_COLOR)
        self.btn_6in.config(activebackground=self.UNSEL_HIGHLIGHT_COLOR)
        self.btn_13in.config(background=self.SEL_COLOR)
        self.btn_13in.config(activebackground=self.SEL_HIGHLIGHT_COLOR)
        self.scr_size = 13
        self.set_ready()

    def flash_task(self):
        success = False
        nodevice = False
        cmd = "dfu-util -a 0 -i 0 -s 0x08000000:leave -D glider_ec_rtos.bin"
        process = subprocess.Popen(cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True,
            encoding='utf-8',
            errors='replace'
        )
        while True:
            realtime_output = process.stdout.readline()
            if realtime_output == "" and process.poll() is not None:
                break
            if realtime_output:
                self.after(0, lambda: self.log_status(realtime_output))
                if "No DFU capable USB device available" in realtime_output:
                    nodevice = True
                if "File downloaded successfully" in realtime_output:
                    success = True
                # Extract progress
                match = re.search(r'(\d+)%', realtime_output)
                if match:
                    progress = int(match.group(1))
                    self.after(0, lambda: self.update_progress(progress, 100))
        if success:
            return 0
        if nodevice:
            return 1
        return 2

    def crc16(self, data: bytes):
        '''
        CRC-16 (CCITT) implemented with a precomputed lookup table
        '''
        table = [
            0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50A5, 0x60C6, 0x70E7, 0x8108, 0x9129, 0xA14A, 0xB16B, 0xC18C, 0xD1AD, 0xE1CE, 0xF1EF,
            0x1231, 0x0210, 0x3273, 0x2252, 0x52B5, 0x4294, 0x72F7, 0x62D6, 0x9339, 0x8318, 0xB37B, 0xA35A, 0xD3BD, 0xC39C, 0xF3FF, 0xE3DE,
            0x2462, 0x3443, 0x0420, 0x1401, 0x64E6, 0x74C7, 0x44A4, 0x5485, 0xA56A, 0xB54B, 0x8528, 0x9509, 0xE5EE, 0xF5CF, 0xC5AC, 0xD58D,
            0x3653, 0x2672, 0x1611, 0x0630, 0x76D7, 0x66F6, 0x5695, 0x46B4, 0xB75B, 0xA77A, 0x9719, 0x8738, 0xF7DF, 0xE7FE, 0xD79D, 0xC7BC,
            0x48C4, 0x58E5, 0x6886, 0x78A7, 0x0840, 0x1861, 0x2802, 0x3823, 0xC9CC, 0xD9ED, 0xE98E, 0xF9AF, 0x8948, 0x9969, 0xA90A, 0xB92B,
            0x5AF5, 0x4AD4, 0x7AB7, 0x6A96, 0x1A71, 0x0A50, 0x3A33, 0x2A12, 0xDBFD, 0xCBDC, 0xFBBF, 0xEB9E, 0x9B79, 0x8B58, 0xBB3B, 0xAB1A,
            0x6CA6, 0x7C87, 0x4CE4, 0x5CC5, 0x2C22, 0x3C03, 0x0C60, 0x1C41, 0xEDAE, 0xFD8F, 0xCDEC, 0xDDCD, 0xAD2A, 0xBD0B, 0x8D68, 0x9D49,
            0x7E97, 0x6EB6, 0x5ED5, 0x4EF4, 0x3E13, 0x2E32, 0x1E51, 0x0E70, 0xFF9F, 0xEFBE, 0xDFDD, 0xCFFC, 0xBF1B, 0xAF3A, 0x9F59, 0x8F78,
            0x9188, 0x81A9, 0xB1CA, 0xA1EB, 0xD10C, 0xC12D, 0xF14E, 0xE16F, 0x1080, 0x00A1, 0x30C2, 0x20E3, 0x5004, 0x4025, 0x7046, 0x6067,
            0x83B9, 0x9398, 0xA3FB, 0xB3DA, 0xC33D, 0xD31C, 0xE37F, 0xF35E, 0x02B1, 0x1290, 0x22F3, 0x32D2, 0x4235, 0x5214, 0x6277, 0x7256,
            0xB5EA, 0xA5CB, 0x95A8, 0x8589, 0xF56E, 0xE54F, 0xD52C, 0xC50D, 0x34E2, 0x24C3, 0x14A0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
            0xA7DB, 0xB7FA, 0x8799, 0x97B8, 0xE75F, 0xF77E, 0xC71D, 0xD73C, 0x26D3, 0x36F2, 0x0691, 0x16B0, 0x6657, 0x7676, 0x4615, 0x5634,
            0xD94C, 0xC96D, 0xF90E, 0xE92F, 0x99C8, 0x89E9, 0xB98A, 0xA9AB, 0x5844, 0x4865, 0x7806, 0x6827, 0x18C0, 0x08E1, 0x3882, 0x28A3,
            0xCB7D, 0xDB5C, 0xEB3F, 0xFB1E, 0x8BF9, 0x9BD8, 0xABBB, 0xBB9A, 0x4A75, 0x5A54, 0x6A37, 0x7A16, 0x0AF1, 0x1AD0, 0x2AB3, 0x3A92,
            0xFD2E, 0xED0F, 0xDD6C, 0xCD4D, 0xBDAA, 0xAD8B, 0x9DE8, 0x8DC9, 0x7C26, 0x6C07, 0x5C64, 0x4C45, 0x3CA2, 0x2C83, 0x1CE0, 0x0CC1,
            0xEF1F, 0xFF3E, 0xCF5D, 0xDF7C, 0xAF9B, 0xBFBA, 0x8FD9, 0x9FF8, 0x6E17, 0x7E36, 0x4E55, 0x5E74, 0x2E93, 0x3EB2, 0x0ED1, 0x1EF0
        ]

        crc = 0x0
        for byte in data:
            crc = (crc << 8) ^ table[(crc >> 8) ^ byte]
            crc &= 0xFFFF                                   # important, crc must stay 16bits all the way through
        return crc

    def open_dev(self):
        vid = 0x1209
        pid = 0xae86

        self.hiddev = hid.device()
        self.hiddev.open(vid, pid)

        self.after(0, lambda: self.log_status(f"Manufacturer: {self.hiddev.get_manufacturer_string()}\n"))
        self.after(0, lambda: self.log_status(f"Product: {self.hiddev.get_product_string()}\n"))
        self.after(0, lambda: self.log_status(f"Serial No: {self.hiddev.get_serial_number_string()}\n"))

    def send_cmd(self, cmd, param, x0, y0, x1, y1, pid):
        byteseq = struct.pack('<bHHHHHH', cmd, param, x0, y0, x1, y1, pid)
        chksum = struct.pack('<H', self.crc16(byteseq))
        byteout = b'\x05' + byteseq + chksum + bytearray(48)
        self.hiddev.write(byteout)
        str_in = self.hiddev.read(self.PACKET_SIZE)
        if (str_in[1] != self.USBRET_SUCCESS):
            raise Exception("Send command failed!")

    def send_buffer(self, bin):
        if len(bin) % self.PKT_DATA_SIZE != 0:
            bin += bytearray(self.PKT_DATA_SIZE - len(bin) % self.PKT_DATA_SIZE)
        pkts = len(bin) // self.PKT_DATA_SIZE
        start_time = datetime.now()
        for i in range(pkts):
            self.after(0, lambda: self.update_progress(i, pkts))
            pkt = b'\x05' + bin[i*self.PKT_DATA_SIZE:(i+1)*self.PKT_DATA_SIZE]
            self.hiddev.write(pkt)
        str_in = self.hiddev.read(self.PACKET_SIZE)
        if (str_in[1] != self.USBRET_SUCCESS):
            raise Exception("Send data failed!")
        totaltime = (datetime.now() - start_time).total_seconds()
        self.after(0, lambda: self.log_status(f'Done ({totaltime} seconds, {len(bin)/totaltime/1000:.1f}KB/s)\n'))

    def send_file(self, fn, target_fn):
        fp = open(fn, 'rb')
        bin = fp.read()
        fp.close()
        fsize = len(bin)
        self.send_cmd(self.USBCMD_RECV, 1, fsize % 65536, fsize // 65536, 0, 0, 0)
        self.send_buffer(bytearray(target_fn, 'ascii'))
        self.send_buffer(bin)

    def update_progress(self, val, max):
        self.progress.config(maximum=max)
        self.progress.config(value=val)

    def update_status(self, color, status_text, instr_text):
        self.status.set(status_text)
        self.instr.set(instr_text)
        self.status_frame.config(background=color)
        self.status_label.config(background=color)
        self.instr_label.config(background=color)
        self.update_progress(0, 100) # auto reset progress
        self.log_status(status_text + "\n")

    def log_status(self, status):
        self.log_text.insert(tk.END, status)
        self.log_text.yview(tk.END)

    def finish_task(self):
        self.btn_start.config(state="normal")
        self.btn_start.config(text="开始")
        self.btn_start.config(background=self.START_COLOR)
        self.btn_start.config(command=self.start_task)
        self.btn_6in.config(state="normal")
        self.btn_13in.config(state="normal")

    def repurpose_button(self):
        self.btn_start.config(background=self.ATTN_COLOR)
        self.btn_start.config(text="继续")
        self.btn_start.config(command=lambda: self.send_signal("continue"))
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="normal")

    def disable_button(self):
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="disabled")

    def wait_display_port_connect(self, port, timeout):
        timeout = timeout * 4 # Convert to seconds
        name_translation = {
            "DP-1": "card0-DP-1",
            "DP-2": "card0-DP-2",
            "DP-3": "card0-DP-3",
            "HDMI-1": "card0-HDMI-A-1",
            "HDMI-2": "card0-HDMI-A-2",
            "HDMI-3": "card0-HDMI-A-3"
        }
        while timeout != 0:
            # completedprocess = subprocess.run(f"xrandr", shell=True, capture_output=True)
            # result = completedprocess.stdout.decode("utf-8")
            # if f"{port} connected" in result:
            #     return True
            file = open(f"/sys/class/drm/{name_translation[port]}/status")
            content = file.read()
            file.close()
            if content.startswith("connected"):
                return True
            time.sleep(0.25)
            timeout -= 1
        return False

    def flash_test_aborted(self):
        self.after(0, lambda: self.update_status(self.ERR_COLOR, "失败", "已中止"))
        self.after(0, lambda: self.finish_task())

    def switch_input(self, id):
        self.open_dev()
        self.send_cmd(self.USBCMD_SETINPUT, id, 0, 0, 0, 0, 0)

    def reset_tp_bg(self):
        #time.sleep(0.5)
        subprocess.run(f"xinput map-to-output {self.tp_port} {self.CONTROL_SCREEN_PORT}", shell=True)
        #time.sleep(2)
        #subprocess.run(f"icewmbg -i=/home/prod/testxga.png -a=1", shell=True)

    def flash_test_task(self):
        self.after(0, lambda: self.update_status(self.INFO_COLOR, "烧录主控中", "请稍候"))

        retry_count = 3
        while True:
            result = self.flash_task()
            if result == 0:
                break # Success
            if result == 1:
                # No device
                self.after(0, lambda: self.update_status(self.ERR_COLOR, "失败", "无法检测到设备\n请确认设备已进入烧录模式再重试"))
                self.after(0, lambda: self.finish_task())
                return
            if result == 2:
                self.after(0, lambda: self.update_status(self.INFO_COLOR, "烧录主控中", "烧录失败，正在重试，请稍候"))
                retry_count -= 1

        self.after(0, lambda: self.update_status(self.INFO_COLOR, "等待中", "设备正在初始化，等待重新连接，请稍候"))

        # Should take less than 25 seconds (formatting takes 15 seconds)
        timeout = self.RECONNECT_TIMEOUT
        self.after(0, lambda: self.btn_stop.config(state="normal"))
        while True:
            try:
                self.open_dev()
                break
            except OSError:
                # Not connected
                time.sleep(1)
                timeout -= 1
                self.after(0, lambda: self.update_progress(self.RECONNECT_TIMEOUT - timeout, self.RECONNECT_TIMEOUT))
                if timeout == 0:
                    self.after(0, lambda: self.update_status(self.ERR_COLOR, "失败", "无法重新连接到设备\n请重试烧录流程"))
                    self.after(0, lambda: self.finish_task())
                    return
            try:
                sig = self.signal_queue.get_nowait()
                if sig == "stop":
                    self.flash_test_aborted()
                    return
            except queue.Empty:
                pass
        self.after(0, lambda: self.btn_stop.config(state="disabled"))

        try:
            self.after(0, lambda: self.update_status(self.INFO_COLOR, "烧录资源中", "正在传输FPGA固件，请稍候"))
            self.send_file("fpga.bit", "fpga.bit")
            self.after(0, lambda: self.update_status(self.INFO_COLOR, "烧录资源中", "正在传输字体文件，请稍候"))
            for font in ['font_quicksand_16.bin', 'font_quicksand_20.bin', 'font_quicksand_28.bin']:
                self.send_file('fonts/' + font, 'fonts/' + font)
            self.after(0, lambda: self.update_status(self.INFO_COLOR, "烧录资源中", "正在传输配置文件，请稍候"))
            if self.scr_size == 6:
                subprocess.run("./cfggen/bin/cfggen 6 1448 1072 75", shell=True)
            else:
                subprocess.run("./cfggen/bin/cfggen 13.3 1600 1200 75", shell=True)
            self.send_file('config.bin', 'config.bin')
        except Exception as e:
            self.after(0, lambda: self.log_status(str(e) + "\n"))
            self.after(0, lambda: self.update_status(self.ERR_COLOR, "失败", "未知错误\n请反馈问题并重试烧录流程"))
            self.after(0, lambda: self.finish_task())
            return

        self.after(0, lambda: self.update_status(self.INFO_COLOR, "重启中", "正在重启设备，请稍候"))
        self.usbpwr_off()
        time.sleep(1)
        self.usbpwr_on()

        self.after(0, lambda: self.update_status(self.INFO_COLOR, "等待显示器初始化", "正在等待识别显示器，请稍候"))
        if not self.wait_display_port_connect(self.DUT_TMDS_PORT, 10):
            self.after(0, lambda: self.update_status(self.ERR_COLOR, "失败", "无法在TMDS端口上检测到设备"))
            self.after(0, lambda: self.finish_task())
            return

        subprocess.run(f"xrandr --output {self.DUT_TMDS_PORT} --auto --right-of {self.CONTROL_SCREEN_PORT}", shell=True)
        self.reset_tp_bg()
        self.after(0, lambda: self.update_status(self.INFO_COLOR, "等待显示器初始化", "已启用输出，等待显示器初始化，请稍候"))
        time.sleep(1)

        self.after(0, lambda: self.update_status(self.ATTN_COLOR, "请检查屏幕是否正常显示", "如果正常显示，请点击继续"))
        self.after(0, lambda: self.repurpose_button())

        sig = self.signal_queue.get()
        if sig == "stop":
            self.flash_test_aborted()
            return
        self.after(0, lambda: self.disable_button())

        # Set input back to auto so it's applied on next boot
        errcnt = 0
        while True:
            try:
                self.switch_input(0)
            except OSError:
                errcnt += 1
                if errcnt > 3:
                    self.after(0, lambda: self.update_status(self.ERR_COLOR, "失败", "无法打开HID设备"))
                    self.after(0, lambda: self.finish_task())
                    return
            finally:
                break
            time.sleep(1)

        self.after(0, lambda: self.update_status(self.INFO_COLOR, "正在关闭输出", "请稍候"))
        subprocess.run(f"xrandr --output {self.DUT_TMDS_PORT} --off", shell=True)
        self.reset_tp_bg()

        self.after(0, lambda: self.update_status(self.INFO_COLOR, "重启中", "正在重启设备，请稍候"))
        self.usbpwr_off()
        time.sleep(1)
        self.usbpwr_on()

        self.after(0, lambda: self.update_status(self.INFO_COLOR, "等待显示器初始化", "正在等待显示器重启，请稍候"))
        if not self.wait_display_port_connect(self.DUT_TYPEC_PORT, 20):
            # Unable to detect after 10 seconds, reset and retry
            self.usbpwr_off()
            time.sleep(1)
            self.usbpwr_on()
            if not self.wait_display_port_connect(self.DUT_TYPEC_PORT, 20):
                self.after(0, lambda: self.update_status(self.ERR_COLOR, "失败", "无法在Type-C端口上检测到设备"))
                self.after(0, lambda: self.finish_task())
                return

        subprocess.run(f"xrandr --output {self.DUT_TYPEC_PORT} --auto --right-of {self.CONTROL_SCREEN_PORT}", shell=True)
        self.reset_tp_bg()
        self.after(0, lambda: self.update_status(self.INFO_COLOR, "等待显示器初始化", "已启用输出，等待显示器初始化，请稍候"))
        time.sleep(2)

        self.after(0, lambda: self.update_status(self.ATTN_COLOR, "请检查屏幕是否正常显示", "如果正常显示\n请翻转后重新插入TypeC线，再点击继续"))
        self.after(0, lambda: self.repurpose_button())

        sig = self.signal_queue.get()
        if sig == "stop":
            self.flash_test_aborted()
            return
        self.after(0, lambda: self.disable_button())

        self.after(0, lambda: self.update_status(self.INFO_COLOR, "等待显示器初始化", "谢谢\n正在等待显示器重启，请稍候"))
        if not self.wait_display_port_connect(self.DUT_TYPEC_PORT, 20):
            # Unable to detect after 10 seconds, reset and retry
            self.usbpwr_off()
            time.sleep(1)
            self.usbpwr_on()
            if not self.wait_display_port_connect(self.DUT_TYPEC_PORT, 20):
                self.after(0, lambda: self.update_status(self.ERR_COLOR, "失败", "无法在Type-C端口上检测到设备"))
                self.after(0, lambda: self.finish_task())
                return

        self.after(0, lambda: self.update_status(self.ATTN_COLOR, "请检查屏幕是否正常显示", "如果正常显示\n请点击继续"))
        self.after(0, lambda: self.repurpose_button())

        sig = self.signal_queue.get()
        if sig == "stop":
            self.flash_test_aborted()
            return

        self.after(0, lambda: self.update_status(self.ATTN_COLOR, "请测试按下各个按钮", "如果所有按钮按下均有反应，请点击继续"))
        self.after(0, lambda: self.repurpose_button())

        sig = self.signal_queue.get()
        if sig == "stop":
            self.flash_test_aborted()
            return
        self.after(0, lambda: self.disable_button())

        self.after(0, lambda: self.update_status(self.SUCCESS_COLOR, "完成", "请长按靠近USB的按键关闭设备后拔出"))
        self.after(0, lambda: self.finish_task())

if __name__ == "__main__":
    app = App()
    app.mainloop()

#!/usr/bin/env python3

import argparse
import base64
import concurrent.futures
import csv
import datetime
from datetime import datetime, timedelta
import logging
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import ctypes
import warnings
import console
import requests
import re
import locale

# The URL for the VPN list
VPN_LIST_URL = "https://www.vpngate.net/api/iphone/"
SPEED_TEST_URL = "http://ipv4.download.thinkbroadband.com/100MB.zip"
LOCAL_CSV_PATH = "servers.csv"
# LOCAL_CSV_PATH = "list.csv"
DEFAULT_EXPIRED_TIME = 8
DEFAULT_MIN_SPEED = 0.1

# Support Ansi
console.ansi_capable

logger = logging.getLogger()

EU_COUNTRIES = [
    "AL",
    "AT",
    "BA",
    "BE",
    "BG",
    "CH",
    "CY",
    "DE",
    "DK",
    "EE",
    "ES",
    "FI",
    "FR",
    "GB",
    "GR",
    "HR",
    "HU",
    "IE",
    "IS",
    "IT",
    "LT",
    "LV",
    "MK",
    "MT",
    "NL",
    "NO",
    "PL",
    "PT",
    "RO",
    "RS",
    "SE",
    "SI",
]

# 新增：翻译字典
translations = {
    "en": {
        # info logger information
        "vpn_start_running": "\033[2J\033[H\033[32m[VPNGATE-CLIENT] for Windows, Start running...\033[0m",
        'vpnlist_expired':"VPN servers list expired,download now!",
        'download_from_url':"Downloading VPN list from \033[90;4m%s\033[0m",
        'vpnlist_download_saved_to_file':"VPN list downloaded and saved to \033[90;4m%s\033[0m",
        'failed_to_download_from_url':"Failed to download from %s: %s",
        'attempt_download_from_backup_url':"Attempting to download from backup URL: \033[90;4m%s\033[0m",
        "loading_vpn_list": "Loading VPN list from \033[90;4m%s\033[0m",
        "found_vpn_servers": "Found \033[32m%i\033[0m VPN servers",
        "filtering_servers": "Filtering out unresponsive VPN servers",
        'found_responding_vpns':"Found \033[32m%i\033[0m responding VPNs",
        "vpn_init_success": "VPN initialized successfully! Country: %s",
        "bad_download_speed": "\033[33mBad download speed,attempting next server...\033[0m",
        "next_vpn": "Next VPN...",
        'performing_speedtest':"\033[90mPerforming connection speed test. Press CTRL+C to stop it.\033[0m",
        'speedtest_canceled':"Speedtest Canceled!",
        'use_or_change':"Would you like to use this VPN ? (No = \033[1mCTRL+C\033[0m, Yes = Any Key)",
        "setup_finished": "\033[32mSetup finished!\033[0m \033[90m(Press CTRL+C to stop the VPN)\033[0m",
        "connection_disconnected": "\033[33mConnection is disconnected,attempting next server!\033[0m",
        "connection_closed": "\033[90mip %s port %s country %s,connection closed!\033[0m",
        "connecting_to_vpn": "Connecting to VPN...",
        "writing_config": "Writing config to %s",
        "executing_cmd": "Executing %s",
        "vpn_init_failed": "VPN initialization failed.",
        "vpn_init_timeout": "VPN Initialization timed out.",
        "received_keyboard_interrupt": "\033[31mReceived keyboard interrupt.\033[0m",
        "terminating_vpn": "Terminating VPN connection",
        "vpn_terminated": "VPN connection Terminated!",
        "termination_timeout": "Termination timed out. Killing the process.",
        "vpn_unkillable": "The VPN process can't be killed!",
        "exiting": "\033[31mExiting...\033[0m",

        # debug输出
        "probing_vpn": "Probing VPN endpoint",
        "cant_probe_udp": "Can't probe UDP servers",
        "vpn_not_responding": "VPN endpoint did not respond to connection",
        "connection_failed": "Connection failed",
        "vpn_listening": "VPN endpoint is listening",

        # help info
        "appDescription": "Client for vpngate.net VPNs",
        'positional_arguments': 'positional arguments',
        'optional_arguments': 'options',
        'h_help': 'show this help message and exit',
        "h_arg_country": "A 2 char country code (e.g. CA for Canada) from which to look for VPNs. If specified multiple times, VPNs from all the countries will be selected.",
        "h_arg_eu": "Adds European countries to the list of considerable countries.",
        "h_arg_probes": "Number of concurrent connection probes to send.",
        "h_arg_probe_timeout": "When probing, how long to wait for connection until marking the VPN as unavailable (milliseconds).",
        "h_arg_url": "URL of the VPN list (csv).",
        "h_arg_us": "Adds United States to the list of possible countries. Shorthand or --country US.",
        "h_arg_verbose": "More verbose output.",
        "h_arg_vpn_timeout": "Time to wait for a VPN to be established before giving up (seconds).",
        "h_arg_vpn_timeout_poll_interval": "Time between two checks for a potential timeout (seconds).",
        "h_arg_ovpnfile": "Connects to the OpenVPN VPN whose configuration is in the provided .ovpn file.",
        "h_arg_expired_time": "Time to wait for a ServersList to be expired.",
        "h_arg_min_speed": "Minimum download speed."

    },
    "zh": {
        # info
        "vpn_start_running": "\033[2J\033[H\033[32m[VPNGATE-CLIENT] Windows 客户端, 开始运行...\033[0m",
        'vpnlist_expired':"VPN 服务器列表已过期，重新下载!",
        'download_from_url':"从 \033[90;4m%s\033[0m 下载 VPN 服务器列表",
        'vpnlist_download_saved_to_file':"VPN 服务器列表已下载并保存到 \033[90;4m%s\033[0m",
        'failed_to_download_from_url':"从 %s 下载失败！错误信息： %s",
        'attempt_download_from_backup_url':"尝试从备用网址下载: \033[90;4m%s\033[0m",
        "loading_vpn_list": "从文件 \033[90;4m%s\033[0m 加载VPN服务器列表",
        "found_vpn_servers": "总共 \033[32m%i\033[0m 个 VPN 服务器",
        "filtering_servers": "过滤无响应服务器",
        'found_responding_vpns':"发现 \033[32m%i\033[0m 个可用 VPN 服务器",
        "vpn_init_success": "VPN初始化成功！国家：%s",
        'performing_speedtest':"\033[90m运行 VPN 连接速度测试，按 CTRL+C 终止测速.\033[0m",
        'speedtest_canceled':"下载速度测试取消!",
        "bad_download_speed": "下载速度不佳，尝试下一个服务器...",
        "next_vpn": "下一个VPN...", 
        'use_or_change':"是否使用此 VPN ? ( 按任意键确认！ 按 \033[1mCTRL+C\033[0m 切换VPN！)",
        "setup_finished": "\033[32mVPN 链接设置完成!\033[0m \033[90m(按 CTRL+C 结束连接并退出)\033[0m",
        "connection_disconnected": "连接已断开，尝试下一个服务器！",
        "connection_closed": "IP %s 端口 %s 国家 %s，连接已关闭！",
        "connecting_to_vpn": "正在连接VPN...",
        "writing_config": "正在将配置写入 %s",
        "executing_cmd": "执行命令 %s",
        "vpn_init_failed": "VPN初始化失败。",
        "vpn_init_timeout": "VPN初始化超时。",
        "received_keyboard_interrupt": "收到键盘中断。",
        "terminating_vpn": "正在终止VPN连接",
        "vpn_terminated": "VPN连接已终止！",
        "termination_timeout": "终止超时。正在强制结束进程。",
        "vpn_unkillable": "无法终止VPN进程！",
        "exiting": "\033[31m退出程序...\033[0m",

        # debug
        "probing_vpn": "正在探测VPN端点",
        "cant_probe_udp": "无法探测UDP服务器",
        "vpn_not_responding": "VPN端点未响应连接",
        "connection_failed": "连接失败",
        "vpn_listening": "VPN端点正在监听",
        
        # 帮助信息
        "appDescription": "vpngate.net 的VPN客户端",
        # 'appUsage': '用法: vpngateclientcn.py [选项] [ovpnfile]',
        'positional_arguments': '位置参数',
        'optional_arguments': '可选参数',
        'h_help': '显示此帮助信息并退出',
        "h_arg_country": "指定一个两位字母的国家代码（例如 CA 代表加拿大），用于选择 VPN。可多次指定多个国家的 VPN。",
        "h_arg_eu": "将欧洲国家添加到可考虑的国家列表中。",
        "h_arg_probes": "发送的并发连接探测数量。",
        "h_arg_probe_timeout": "探测时，等待连接的时间，超时后标记该 VPN 为不可用（以毫秒为单位）。",
        "h_arg_url": "VPN 列表的 URL（csv）。",
        "h_arg_us": "将美国添加到可能的国家列表中。简写为 --country US。",
        "h_arg_verbose": "输出更多详细信息。",
        "h_arg_vpn_timeout": "等待 VPN 建立连接的时间，超时后放弃（以秒为单位）。",
        "h_arg_vpn_timeout_poll_interval": "两次检查潜在超时的时间间隔（以秒为单位）。",
        "h_arg_ovpnfile": "连接到 OpenVPN 的 VPN，其配置文件为提供的 .ovpn 文件。",
        "h_arg_expired_time": "等待服务器列表过期的时间。",
        "h_arg_min_speed": "最低下载速度。"
    },
}


# 获取系统语言的函数
def get_system_language():
    try:
        return locale.getdefaultlocale()[0]
    except:
        return "en_US"


# 获取翻译文本的函数
def get_text(key, lang=None):
    # 忽略 locale.getdefaultlocale() 的弃用警告
    warnings.filterwarnings(
        "ignore", category=DeprecationWarning, message=".*getdefaultlocale.*"
    )

    if lang is None:
        lang = get_system_language()[:2]
    return translations.get(lang, translations["en"]).get(key, translations["en"][key])


class VPN:
    """A VPN server."""

    def __init__(self, data, args):
        # Command Line Arguments
        self.args = args

        # Logging
        self.log = logging.getLogger("VPN %s" % data["#HostName"])

        # VPN Information
        self.ip = data["IP"]
        self.country = data["CountryLong"]
        self.country_code = data["CountryShort"]

        # OpenVPN endpoint information
        self.proto = None
        self.port = None

        # OpenVPN Config
        conf = data["OpenVPN_ConfigData_Base64"]
        self.config = base64.b64decode(conf).decode("UTF-8")
        for line in self.config.splitlines():
            if line.startswith("remote") and len(line.split(" ")) == 3:
                # format: remote <ip> <port>
                _, ip, self.port = line.split(" ")

                # If the IP is different, something is not right.
                assert not self.ip or ip == self.ip

                # If the IP was not provided, use this one found here.
                self.ip = ip

            elif line.startswith("proto"):
                # format: proto tcp|udp
                _, self.proto = line.split(" ")

        self.log.debug(
            "New VPN: ip=%s, proto=%s port=%s country=%s (%s)",
            self.ip,
            self.proto,
            self.port,
            self.country,
            self.country_code,
        )

    def is_listening(self):
        """Probes the VPN endpoint to see if it's listening."""
        if self.proto == "udp":
            # TODO: Implement udp probing.
            self.log.debug(get_text('cant_probe_udp'))
            return True

        self.log.debug(get_text('probing_vpn'))

        # Create a socket with a timeout.
        s = socket.socket()
        s.settimeout(self.args.probe_timeout / 1000)

        try:
            # Try to connect to the VPN endpoint.
            s.connect((self.ip, int(self.port)))
            s.shutdown(socket.SHUT_RDWR)
            s.close()
        except socket.timeout:
            self.log.debug(get_text('vpn_not_responding'))
            return False
        except (ConnectionRefusedError, OSError):
            self.log.debug(get_text('connection_failed'))
            return False

        self.log.debug(get_text('vpn_listening'))
        return True

    def connect(self):
        """Initiates and manages the connection to this VPN server.

        Returns:
            (boolean) True if the connection was established and used, False if
            the connection failed and the next server should be tried

        Throws:
            (KeyboardInterrupt) if the process was aborted by the user.
        """

        self.log.info(get_text("connecting_to_vpn"))
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as conf:
            self.log.debug("Writing config to %s", conf.name)
            conf.write(self.config)
            # Add the data-ciphers option to the configuration
            conf.write("\ndata-ciphers AES-128-CBC\n")
            conf.write("\nremote-cert-tls server\n")
            conf.write("\ndisable-dco\n")

            conf.flush()
            conf.close()

            cmd, success_file, batch_file, statusFile = self.build_ovpn_command(
                conf.name
            )
            self.log.debug(get_text('executing_cmd'), cmd)
            # os.remove(conf.name)
            with subprocess.Popen(
                cmd,
                start_new_session=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ) as proc:
                # Wait for the VPN to initialize
                if not self.wait_for_vpn_ready(
                    proc, success_file, batch_file, conf.name
                ):
                    # VPN failed to initialize. Indicate the caller to try the
                    # next one.
                    os.remove(batch_file)
                    os.remove(conf.name)
                    return False

                # Perform a speedtest on the VPN
                if not self.speedtest():
                    print(get_text('bad_download_speed'))
                    self.terminate_vpn(proc)
                    os.remove(conf.name)
                    os.remove(statusFile)
                    return False

                # Ask the user if she wishes to use this VPN.
                if not self.prompt_use_vpn():
                    print("\033[33m"+get_text('next_vpn')+"\033[0m")
                    self.terminate_vpn(proc)
                    os.remove(conf.name)
                    os.remove(statusFile)
                    return False

                def read_stats(file_path):
                    stats = {}
                    with open(file_path, "r") as file:
                        for line in file:
                            if line.startswith("TUN/TAP read bytes"):
                                stats["tun_tap_read"] = int(line.split(",")[1].strip())
                            elif line.startswith("TUN/TAP write bytes"):
                                stats["tun_tap_write"] = int(line.split(",")[1].strip())
                            elif line.startswith("TCP/UDP read bytes"):
                                stats["tcp_udp_read"] = int(line.split(",")[1].strip())
                            elif line.startswith("TCP/UDP write bytes"):
                                stats["tcp_udp_write"] = int(line.split(",")[1].strip())
                            elif line.startswith("Auth read bytes"):
                                stats["auth_read"] = int(line.split(",")[1].strip())
                    return stats

                # vpn connection status monitor
                def monitor_connection(file_path):
                    try:
                        previous_stats = read_stats(file_path)
                        while True:
                            time.sleep(5)
                            current_stats = read_stats(file_path)
                            if (
                                current_stats["tun_tap_read"]
                                != previous_stats["tun_tap_read"]
                                or current_stats["tun_tap_write"]
                                != previous_stats["tun_tap_write"]
                                or current_stats["tcp_udp_read"]
                                != previous_stats["tcp_udp_read"]
                                or current_stats["tcp_udp_write"]
                                != previous_stats["tcp_udp_write"]
                                or current_stats["auth_read"]
                                != previous_stats["auth_read"]
                            ):
                                previous_stats = current_stats
                                return True
                            else:
                                previous_stats = current_stats
                                return False
                    except Exception as e:
                        print("connection error:{e}")
                        return False

                print(
                    get_text('setup_finished')
                )

                try:
                    # Check statusFile an wait to keyboardinterrrupt
                    while monitor_connection(statusFile):
                        time.sleep(5)
                    if not monitor_connection(statusFile):
                        time.sleep(5)
                        if not monitor_connection(statusFile):
                            self.terminate_vpn(proc)
                            os.remove(conf.name)
                            os.remove(statusFile)
                            print(
                                get_text('connection_disconnected')
                            )
                            return False

                except KeyboardInterrupt:
                    self.log.info(get_text('received_keyboard_interrupt'))
                    self.terminate_vpn(proc)
                    os.remove(conf.name)
                    os.remove(statusFile)
                    sys.exit(0)

                finally:
                    print(
                        get_text('connection_closed')
                        % (self.ip, self.port, self.country_code)
                    )

    def build_ovpn_command(self, conffile):
        pid = os.getpid()
        temp_dir = tempfile.gettempdir()
        success_file = os.path.join(temp_dir, f"vpn_success_{pid}.tmp")

        statusFile = os.path.join(temp_dir, f"vpn_status_{pid}.tmp")

        if platform.system() == "Windows":
            # 创建一个批处理文件来标记 VPN 连接成功并终止进程
            batch_file = os.path.join(temp_dir, f"vpn_success_and_kill_{pid}.bat")
            with open(batch_file, "w") as f:
                f.write("@echo off\n")
                f.write(f'echo. > "{success_file}"\n')
                # f.write(f'taskkill /PID {pid}\n')
                f.flush()
                f.close()
            up = batch_file
        else:
            # 对于非 Windows 系统，我们仍然使用 SIGUSR1
            up = f"kill -USR1 {pid}"

        command = [
            "openvpn",
            "--verb",
            "0",
            "--script-security",
            "2",
            "--route-up",
            up,
            "--connect-retry-max",
            "2",
            "--session-timeout",
            "infinite",
            "--ping-exit",
            "5",
            "--ping-restart",
            "2",
            "--connect-timeout",
            "10",
            "--status",
            statusFile,
            "2",
        ]

        command.extend(["--config", conffile])

        return command, success_file, batch_file, statusFile

    def wait_for_vpn_ready(self, proc, success_file, batch_file, conffileName):
        total_wait = 0

        try:
            while total_wait < self.args.vpn_timeout:
                # 检查进程是否还活着
                if proc.poll() is not None:
                    # print("VPN initialization failed.")
                    print(get_text("vpn_init_failed"))
                    return False

                # 非阻塞读取进程输出
                while True:
                    line = proc.stdout.readline()
                    if not line:
                        break
                    if self.args.verbose:
                        print(line.decode().strip())
                    if b"Initialization Sequence Completed" in line.strip():
                        total_wait -= 5
                        break

                # 检查成功文件是否存在
                if os.path.exists(success_file):
               
                    print(
                        "\033[2J\033[H\033[0m\033[32m"
                        + (get_text("vpn_init_success") % self.country_code)
                        + "\033[0m"
                    )
                    
                    os.remove(success_file)  # 清理临时文件
                    os.remove(batch_file)
                    proc.stdout.close()
                    return True

                time.sleep(self.args.vpn_timeout_poll_interval)
                total_wait += self.args.vpn_timeout_poll_interval

            self.log.warning("VPN Initialization timed out.")
            proc.stdout.close()
            self.terminate_vpn(proc)
            return False
        except KeyboardInterrupt:
            self.log.info(get_text('received_keyboard_interrupt'))
            self.terminate_vpn(proc)
            os.remove(batch_file)
            os.remove(conffileName)
            proc.stdout.close()
            raise KeyboardInterrupt

    def prompt_use_vpn(self):
        """Asks the user if she likes to continue using the VPN connection
        after speedtest.

         Returns:
             (boolean) True if the users wants to use this VPN, False if not

        """
        print(
            get_text('use_or_change')
        )

        try:
            input()
        except KeyboardInterrupt:
            return False

        return True

    def terminate_vpn(self, proc):
        """Terminates the given vpn process gracefully (or forcefully if the
           termination takes too long).

        Arguments:
            (Popen) proc: The Popen object for the openvpn process.
        """

        def terminated():
            """Checks if the process terminates in 5 seconds."""
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                return False

            return True

        self.log.info(get_text('terminating_vpn'))
        # 尝试优雅地终止进程
        try:
            proc.terminate()
        except AttributeError:
            # 如果 proc 没有 terminate 方法，尝试发送 SIGTERM 信号
            os.kill(proc.pid, signal.SIGTERM)
        finally:
            self.log.info(get_text('vpn_terminated'))

        if not terminated():
            self.warning("Termination timed out. Killing the process.")
            # proc.kill()
            os.kill(proc.pid, signal.SIGTERM)
            if not terminated():
                self.log.critical(get_text('vpn_unkillable'))
                self.log.critical(get_text('exiting'))
                sys.exit(1)

    def speedtest(self):
        """Performs a speed test on the VPN connection."""

        print(
            get_text('performing_speedtest')
        )
        
        try:
            download_speed = speedtest()
            if download_speed < self.args.min_speed:
                return False
            else:
                return True
        except KeyboardInterrupt:
            print(get_text('speedtest_canceled'))
            return True

    def __str__(self):
        return "ip=%-15s, country=%s, proto=%s, port=%s" % (
            self.ip,
            self.country_code,
            self.proto,
            self.port,
        )


class FileVPN(VPN):
    """A VPN whose config is read directly from an .openvpn file"""

    def __init__(self, args):
        conf = args.ovpnfile.read()
        b64conf = base64.b64encode(conf)

        data = {
            "IP": None,
            "CountryLong": "Unknown",
            "CountryShort": "Unknown",
            "#HostName": args.ovpnfile.name,
            "OpenVPN_ConfigData_Base64": b64conf,
        }

        super().__init__(data, args)


class VPNList:

    def __init__(self, args):
        print("\033[2J\033[H\033[32m" + get_text("vpn_start_running") + "\033[0m")
        self.args = args

        # Setup logging
        self.log = logging.getLogger("VPNList")

        # Check if the local CSV file exists and is not expired
        self.local_csv_path = LOCAL_CSV_PATH
        if self.is_file_expired(self.local_csv_path):
            self.log.info(get_text('vpnlist_expired'))
            self.download_vpn_list(self.args.url, self.local_csv_path)

        # Fetch the list
        self.load_vpns(self.local_csv_path)

        # Filter by country
        self.filter_by_country()

        # Filter out unresponsive servers
        self.filter_unresponsive_vpns()

    def is_file_expired(self, file_path):
        """Check if the file is older than the specified number of hours."""
        if not os.path.exists(file_path):
            return True
        file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
        return datetime.now() - file_mod_time > timedelta(hours=self.args.expired_time)

    def download_vpn_list(self, url, file_path):
        """Download the VPN list from the given URL and save it to the specified file path."""
        self.log.info(get_text('download_from_url'), url)

        try:
            # Download with proxy
            proxy = urllib.request.ProxyHandler(
                {"http": "http://localhost:10809", "https": "https://localhost:10809"}
            )
            opener = urllib.request.build_opener(proxy)
            urllib.request.install_opener(opener)

            req = urllib.request.urlopen(url)
            data = req.read()
            with open(file_path, "wb") as f:
                f.write(data)
            self.log.info(
                get_text('vpnlist_download_saved_to_file'), file_path
            )
        except Exception as e:
            self.log.error(get_text('failed_to_download_from_url'), url, e)
            backup_url = "https://mirror.ghproxy.com/https://github.com/sinspired/VpngateAPI/blob/main/servers.csv"
            self.log.info(
                get_text('attempt_download_from_backup_url'),
                backup_url,
            )
            try:
                # Uninstall proxy
                urllib.request.install_opener(None)
                req = urllib.request.urlopen(backup_url)
                data = req.read()
                with open(file_path, "wb") as f:
                    f.write(data)
                self.log.info(
                    get_text('vpnlist_download_saved_to_file'), file_path
                )
            except Exception as e:
                self.log.error(
                    "Failed to download from backup URL %s: %s", backup_url, e
                )

    def load_vpns(self, file_path):
        """Loads the VPN list from vpngate.net and parses then to |self.vpns|."""
        # self.log.info("Loading VPN list from %s", self.args.url)
        self.log.info(get_text("loading_vpn_list"), file_path)
        # Read the data
        with open(file_path, "r", encoding="utf8") as f:
            rows = filter(lambda r: not r.startswith("*"), f)
            reader = csv.DictReader(rows)
            self.vpns = [VPN(row, self.args) for row in reader]
        self.log.info(get_text("found_vpn_servers"), len(self.vpns))

    def filter_by_country(self):
        """Filters the VPN list based on geographic information."""
        # Check if anything needs to be filtered

        filters = []

        if self.args.eu:
            self.log.info("Including VPNs in Europe")
            filters.append(lambda vpn: vpn.country_code in EU_COUNTRIES)

        if self.args.us:
            self.log.info("Including VPNs in USA")
            filters.append(lambda vpn: vpn.country_code == "US")

        if self.args.country:
            countries = set(map(str.upper, self.args.country))
            self.log.info("Including VPNs in %s", countries)
            filters.append(lambda vpn: vpn.country_code in countries)

        if filters:

            def filter_fn(vpn):
                return any(f(vpn) for f in filters)

            self.vpns = list(filter(filter_fn, self.vpns))
            self.log.info(
                "Found %i VPN servers matching the geographic " + "restrictions",
                len(self.vpns),
            )

    def filter_unresponsive_vpns(self):
        """Probes VPN servers listening on TCP ports and removes those who do
        not reply in timely manner from the list of available VPNs.
        """
        self.log.info(get_text("filtering_servers"))

        # The number of concurrent probes
        n = self.args.probes

        # Parallelize the probing to a thread pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=n) as ex:
            futures = {ex.submit(vpn.is_listening): vpn for vpn in self.vpns}
            responding = []

            for future in concurrent.futures.as_completed(futures):
                vpn = futures[future]

                try:
                    # True if the VPN responded, False otherwise
                    if future.result():
                        responding.append(vpn)

                except:
                    self.log.exception("Availability probe failed")

        self.log.info(get_text('found_responding_vpns'), len(responding))

        self.vpns = responding


def speedtest():
    """Performs a speedtest printing connection speeds in kb/s."""
    url = SPEED_TEST_URL
    match = re.search(r"(\d+)MB", url)
    FILESIZE = float(match.group(1))

    chunk_size = 4096  # 每次读取的块大小，单位为字节
    duration = 5  # 测试持续时间，单位为秒
    timeout = 20  # 请求超时时间，单位为秒

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
    try:
        with requests.get(
            url, stream=True, timeout=timeout, headers=headers
        ) as response:
            if response.status_code == 200:
                file_size = 0
                start_time = time.time()
                end_time = start_time + duration

                for chunk in response.iter_content(chunk_size=chunk_size):
                    file_size += len(chunk)
                    current_time = time.time()
                    if file_size / (1024 * 1024) >= FILESIZE:
                        break
                    if current_time >= end_time:
                        break

                elapsed_time = current_time - start_time  # 实际下载时间，单位为秒
                file_size_mb = file_size / (1024 * 1024)  # 文件大小，单位为MB
                download_speed = file_size_mb / elapsed_time  # 下载速度，单位为MB/s

                print(
                    f"[ Filesize: \033[90;4m{file_size_mb:.2f}\033[0m MB, in \033[90;4m{elapsed_time:.2f}\033[0m s Download Speed: \033[32;4m{download_speed:.2f}\033[0m MB/s ]"
                )
                return download_speed
            else:
                print(f"下载失败，状态码: {response.status_code}")
                return 0
    except Exception as e:
        print(f"下载错误: {e}")
        return 0.1


def parse_args():
    """Parses the command line arguments."""
  
    p = argparse.ArgumentParser(description=get_text('appDescription'))
    p.add_argument(
        "--country",
        "-c",
        action="append",
        help=get_text('h_arg_country'),
    )
    p.add_argument(
        "--eu",
        action="store_true",
        help=get_text('h_arg_eu'),
    )
    # p.add_argument(
    #     "--iptables",
    #     "-i",
    #     action="store_true",
    #     help=get_text('h_arg_iptables'),
    # )
    p.add_argument(
        "--probes",
        action="store",
        default=100,
        type=int,
        help=get_text('h_arg_probes'),
    )
    p.add_argument(
        "--probe-timeout",
        action="store",
        default=1500,
        type=int,
        help=get_text('h_arg_probe_timeout'),
    )
    p.add_argument(
        "--url",
        action="store",
        default=VPN_LIST_URL,
        help=get_text('h_arg_url'),
    )
    p.add_argument(
        "--us",
        action="store_true",
        help=get_text('h_arg_us'),
    )
    p.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help=get_text('h_arg_verbose'),
    )
    p.add_argument(
        "--vpn-timeout",
        action="store",
        default=10,
        type=int,
        help=get_text('h_arg_vpn_timeout'),
    )
    p.add_argument(
        "--vpn-timeout-poll-interval",
        action="store",
        default=0.1,
        type=int,
        help=get_text('h_arg_vpn_timeout_poll_interval'),
    )
    p.add_argument(
        "ovpnfile",
        type=argparse.FileType("rb"),
        default=None,
        nargs="?",
        help=get_text('h_arg_ovpnfile'),
    )
    p.add_argument(
        "--expired-time",
        action="store",
        default=DEFAULT_EXPIRED_TIME,
        type=int,
        help=get_text('h_arg_expired_time'),
    )
    p.add_argument(
        "--min-speed",
        action="store",
        default=DEFAULT_MIN_SPEED,
        type=float,
        help=get_text('h_arg_min_speed'),
    )

    # 覆盖默认的 help 信息
    p._positionals.title = get_text('positional_arguments')
    p._optionals.title = get_text('optional_arguments')
    p._defaults['help'] = get_text('h_help')

    return p.parse_args()

def single_vpn_main(args):
    """Connects to the VPN is the given .ovpn file."""
    vpn = FileVPN(args)
    try:
        vpn.connect()
    except KeyboardInterrupt:
        logging.error("Aborted")


def vpn_list_main(args):
    """Fetches list of VPNs and connects to them."""

    vpnlist = VPNList(args)
    indexNum = 0
    total = len(vpnlist.vpns)

    # Connect to them one-by-one and let the user decide which one to use.
    for vpn in vpnlist.vpns:
        indexNum = indexNum + 1
        print(
            "\033[90m-----------------------------------------------------------+\33[0m"
        )
        print(
            "\033[32m%d\033[0m/\033[32m%d\033[0m %s\033[0m\033[90m"
            % (indexNum, total, vpn)
        )
        try:
            res = vpn.connect()
        except KeyboardInterrupt:
            break

        # The user was happy with this VPN, break the loop.
        if res:
            break
        else:
            continue

    logger.info(get_text('exiting'))


def isAdmin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def addOpenVPNtoSysPath():
    # OpenVPN bin 目录路径
    openvpn_bin_path = r"C:\Program Files\OpenVPN\bin"

    # 检查目录是否存在
    if os.path.exists(openvpn_bin_path):
        # 获取当前环境变量 PATH
        current_path = os.environ.get("PATH", "")

        # 检查 bin 目录是否在 PATH 中
        if openvpn_bin_path not in current_path:
            # 将 bin 目录添加到 PATH
            os.environ["PATH"] = f"{openvpn_bin_path};{current_path}"
            print(f"{openvpn_bin_path} 已添加到 PATH 环境变量中。")

            # 如果需要将修改后的 PATH 持久化，可以使用以下代码
            if sys.platform == "win32":
                import winreg

                def set_environment_variable(name, value):
                    with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE
                    ) as key:
                        winreg.SetValueEx(key, name, 0, winreg.REG_EXPAND_SZ, value)

                set_environment_variable("PATH", os.environ["PATH"])
                print("Environment PATH updated and add to Rigistry。")
    else:
        print(f"{openvpn_bin_path} doesn't exist,please install OpenVPN.")


def customLogger():
    args = parse_args()

    # 自定义时间格式
    def custom_time(*args):
        return datetime.now().strftime("%I:%M%p")

    # 定义颜色常量
    class LogColors:
        BLUE = "\033[34m"
        GREEN = "\033[32m"
        YELLOW = "\033[33m"
        RED = "\033[31m"
        RESET = "\033[0m"

    # 自定义格式化器
    class ColoredFormatter(logging.Formatter):
        def format(self, record):
            levelname = record.levelname
            color_map = {
                "DEBUG": LogColors.BLUE,
                "INFO": LogColors.GREEN,
                "WARNING": LogColors.YELLOW,
                "ERROR": LogColors.RED,
                "CRITICAL": LogColors.RED,
            }
            record.levelname = (
                f"{color_map.get(levelname, '')}{levelname}{LogColors.RESET}"
            )
            return super().format(record)

    # 日志格式
    verbose_format = "%(asctime)s %(levelname)s %(name)s: %(funcName)s: %(message)s"
    simple_format = "%(levelname)s:%(name)s %(message)s"

    # 配置日志处理器和格式化器
    handler = logging.StreamHandler()

    # 根据是否启用verbose模式设置不同的格式
    if args.verbose:
        handler.setFormatter(ColoredFormatter(verbose_format, datefmt="%I:%M%p"))
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
    else:
        handler.setFormatter(logging.Formatter(simple_format))
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)

    logger.handlers = []  # 清除所有默认的处理器
    logger.addHandler(handler)


def main():
    args = parse_args()

    # Check if OpenVPN is installed
    if not shutil.which("openvpn"):
        addOpenVPNtoSysPath()
        if not shutil.which("openvpn"):
            print(
                "\033[31mOpenVPN is not installed on this system or added in system PATH.\033[0m"
            )
            exit(1)

    if not isAdmin():
        params = " ".join([f'"{arg}"' for arg in sys.argv])
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, None, 1
        )
        return 1

    # 自定义输出格式
    customLogger()

    if args.ovpnfile:
        # Load a single VPN from the given file.
        return single_vpn_main(args)
    else:
        # Load list and try them in order
        return vpn_list_main(args)


if __name__ == "__main__":
    sys.exit(main())

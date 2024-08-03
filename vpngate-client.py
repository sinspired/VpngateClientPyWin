#!/usr/bin/env python3

import argparse
import base64
import concurrent.futures
import csv
import datetime
from datetime import datetime, timedelta
import io
import logging
import os
import platform
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import ctypes
import console


# The URL for the VPN list
VPN_LIST_URL = "https://www.vpngate.net/api/iphone/"
SPEED_TEST_URL = "http://cachefly.cachefly.net/10mb.test"
LOCAL_CSV_PATH = "servers.csv"
# LOCAL_CSV_PATH = "list.csv"
DEFAULT_EXPIRED_TIME = 8

# Support Ansi
console.ansi_capable

logger = logging.getLogger()


EU_COUNTRIES = ["AL", "AT", "BA", "BE", "BG", "CH", "CY", "DE", "DK", "EE",
                "ES", "FI", "FR", "GB", "GR", "HR", "HU", "IE", "IS", "IT",
                "LT", "LV", "MK", "MT", "NL", "NO", "PL", "PT", "RO", "RS",
                "SE", "SI"]


class VPN:
    """A VPN server."""

    def __init__(self, data, args):
        # Command Line Arguments
        self.args = args

        # Logging
        self.log = logging.getLogger("VPN: %s" % data["#HostName"])

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

        self.log.debug("New VPN: ip=%s, proto=%s port=%s country=%s (%s)",
                       self.ip, self.proto, self.port, self.country,
                       self.country_code)

    def is_listening(self):
        """Probes the VPN endpoint to see if it's listening."""
        if self.proto == "udp":
            # TODO: Implement udp probing.
            self.log.debug("Can't probe UDP servers")
            return True

        self.log.debug("Probing VPN endpoint")

        # Create a socket with a timeout.
        s = socket.socket()
        s.settimeout(self.args.probe_timeout / 1000)

        try:
            # Try to connect to the VPN endpoint.
            s.connect((self.ip, int(self.port)))
            s.shutdown(socket.SHUT_RDWR)
            s.close()
        except socket.timeout:
            self.log.debug("VPN endpoint did not respond to connection")
            return False
        except (ConnectionRefusedError, OSError):
            self.log.debug("Connection failed")
            return False

        self.log.debug("VPN endpoint is listening")
        return True

    def connect(self):
        """Initiates and manages the connection to this VPN server.

        Returns:
            (boolean) True if the connection was established and used, False if
            the connection failed and the next server should be tried

        Throws:
            (KeyboardInterrupt) if the process was aborted by the user.
        """

        self.log.info("Connecting to VPN...")
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as conf:
            self.log.debug("Writing config to %s", conf.name)
            conf.write(self.config)
            # Add the data-ciphers option to the configuration
            conf.write("\ndata-ciphers AES-128-CBC\n")
            conf.write("\nremote-cert-tls server\n")
            conf.write("\ndisable-dco\n")

            conf.flush()
            conf.close()

            cmd, success_file, batch_file,statusFile = self.build_ovpn_command(conf.name)
            self.log.debug("Executing %s", cmd)
            # os.remove(conf.name)
            with subprocess.Popen(cmd, start_new_session=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
                # Wait for the VPN to initialize
                if not self.wait_for_vpn_ready(proc, success_file, batch_file, conf.name):
                    # VPN failed to initialize. Indicate the caller to try the
                    # next one.
                    os.remove(batch_file)
                    os.remove(conf.name)
                    return False

                # Perform a speedtest on the VPN
                # self.speedtest()

                # Ask the user if she wishes to use this VPN.
                if not self.prompt_use_vpn():
                    print("\033[33mNext VPN...\033[0m")
                    os.remove(conf.name)
                    return False
                
                def read_stats(file_path):
                    stats = {}
                    with open(file_path, 'r') as file:
                        for line in file:
                            if line.startswith("TUN/TAP read bytes"):
                                stats['tun_tap_read'] = int(line.split(',')[1].strip())
                            elif line.startswith("TUN/TAP write bytes"):
                                stats['tun_tap_write'] = int(line.split(',')[1].strip())
                            elif line.startswith("TCP/UDP read bytes"):
                                stats['tcp_udp_read'] = int(line.split(',')[1].strip())
                            elif line.startswith("TCP/UDP write bytes"):
                                stats['tcp_udp_write'] = int(line.split(',')[1].strip())
                            elif line.startswith("Auth read bytes"):
                                stats['auth_read'] = int(line.split(',')[1].strip())
                    return stats

                def monitor_connection(file_path):
                    previous_stats = read_stats(file_path)
                    while True:
                        time.sleep(2)
                        current_stats = read_stats(file_path)
                        if (current_stats['tun_tap_read'] != previous_stats['tun_tap_read'] or
                            current_stats['tun_tap_write'] != previous_stats['tun_tap_write'] or
                            current_stats['tcp_udp_read'] != previous_stats['tcp_udp_read'] or
                            current_stats['tcp_udp_write'] != previous_stats['tcp_udp_write'] or
                            current_stats['auth_read'] != previous_stats['auth_read']):
                            previous_stats = current_stats
                            return True
                        else:
                            previous_stats = current_stats
                            return False
                
                print(
                    "\033[32mSetup finished!\033[0m \033[90m(Press CTRL+C to stop the VPN)\033[0m")

                try:
                    # 使用一个简单的循环来等待中断
                    while monitor_connection(statusFile):
                        time.sleep(1)
                    if not monitor_connection(statusFile):
                        return False
                        
                except KeyboardInterrupt:
                    self.terminate_vpn(proc)

                finally:
                    os.remove(conf.name)
                    # print("\033[32m临时配置文件已清除，退出程序！\033[0m")
                    # sys.exit(0)

    def build_ovpn_command(self, conffile):
        pid = os.getpid()
        temp_dir = tempfile.gettempdir()
        success_file = os.path.join(temp_dir, f"vpn_success_{pid}.tmp")
        
        statusFile=os.path.join(temp_dir, f"vpn_status_{pid}.tmp")

        if platform.system() == "Windows":
            # 创建一个批处理文件来标记 VPN 连接成功并终止进程
            batch_file = os.path.join(
                temp_dir, f"vpn_success_and_kill_{pid}.bat")
            with open(batch_file, "w") as f:
                f.write('@echo off\n')
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
            "--verb", "0",
            "--script-security", "2",
            "--route-up", up,
            "--connect-retry-max", "2",
            "--session-timeout", "infinite",
            "--ping-exit", "5",
            "--ping-restart", "2",
            "--connect-timeout", "3",
            "--status", statusFile, "2",
        ]

        command.extend(["--config", conffile])

        return command, success_file, batch_file,statusFile

    def wait_for_vpn_ready(self, proc, success_file, batch_file, conffileName):
        total_wait = 0

        try:
            while total_wait < self.args.vpn_timeout:
                # 检查进程是否还活着
                if proc.poll() is not None:
                    print("VPN initialization failed.")
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
                        "\033[2J\033[H\033[0m\033[32mVPN initialized successfully! Country: %s\033[0m" % (self.country_code))
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
            self.log.info(
                "\033[31mReceived keyboard interrupt.\033[0m")
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
        print("Would you like to use this VPN ? (No = \033[1mCTRL+C\033[0m, " +
              "Yes = Any Key)")

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

        self.log.info("Terminating VPN connection")
        # 尝试优雅地终止进程
        try:
            proc.terminate()
        except AttributeError:
            # 如果 proc 没有 terminate 方法，尝试发送 SIGTERM 信号
            os.kill(proc.pid, signal.SIGTERM)
        finally:
            self.log.info("VPN connection Terminated！")

        if not terminated():
            self.warning("Termination timed out. Killing the process.")
            # proc.kill()
            os.kill(proc.pid, signal.SIGTERM)
            if not terminated():
                self.log.critical("The VPN process can't be killed!")
                self.log.critical("Exiting...")
                sys.exit(1)

    def speedtest(self):
        """Performs a speed test on the VPN connection."""

        self.log.info("Performing connection speed test. Press CTRL+C to " +
                      "stop it.")
        try:
            speedtest()
        except KeyboardInterrupt:
            pass

    def __str__(self):
        return "ip=%-15s, country=%s, proto=%s, port=%s" % (self.ip, self.country_code, self.proto, self.port)


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
            "OpenVPN_ConfigData_Base64": b64conf
        }

        super().__init__(data, args)


class VPNList:
    def __init__(self, args):
        print(
            "\033[2J\033[H\033[32m[VPNGATE-CLIENT] for Windows, start running...\033[0m")
        self.args = args

        # Setup logging
        self.log = logging.getLogger("VPNList")

        # Check if the local CSV file exists and is not expired
        self.local_csv_path = LOCAL_CSV_PATH
        if self.is_file_expired(self.local_csv_path):
            self.log.info("VPN列表已过期，重新下载")
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
        self.log.info("Downloading VPN list from \033[90;4m%s\033[0m", url)

        # download with proxy
        proxy = urllib.request.ProxyHandler(
            {'http': 'http://localhost:10809', 'https': 'https://localhost:10809'})
        # proxy = urllib.request.getproxies()
        # print(proxy)
        opener = urllib.request.build_opener(proxy)
        urllib.request.install_opener(opener)

        req = urllib.request.urlopen(url)
        data = req.read()
        with open(file_path, 'wb') as f:
            f.write(data)
        self.log.info(
            "VPN list downloaded and saved to \033[90;4m%s\033[0m", file_path)

    def load_vpns(self, file_path):
        """Loads the VPN list from vpngate.net and parses then to |self.vpns|.
        """
        # self.log.info("Loading VPN list from %s", self.args.url)
        self.log.info("Loading VPN list from \033[90;4m%s\033[0m",
                      file_path)
        # Read the data
        with open(file_path, 'r', encoding='utf8') as f:
            rows = filter(lambda r: not r.startswith("*"), f)
            reader = csv.DictReader(rows)
            self.vpns = [VPN(row, self.args) for row in reader]
        self.log.info("Found \033[32m%i\033[0m VPN servers", len(self.vpns))

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
            def filter_fn(vpn): return any(f(vpn) for f in filters)
            self.vpns = list(filter(filter_fn, self.vpns))
            self.log.info("Found %i VPN servers matching the geographic " +
                          "restrictions", len(self.vpns))

    def filter_unresponsive_vpns(self):
        """Probes VPN servers listening on TCP ports and removes those who do
           not reply in timely manner from the list of available VPNs.
        """
        self.log.info("Filtering out unresponsive VPN servers")

        # The number of concurrent probes
        n = args.probes

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

        self.log.info(
            "Found \033[32m%i\033[0m responding VPNs", len(responding))

        self.vpns = responding


def speedtest():
    """Performs a speedtest printing connection speeds in kb/s."""
    try:
        start_time = time.time()
        req = urllib.request.urlopen(SPEED_TEST_URL)
        total_bytes = 0
        last_print = start_time
        chunk_size = 1024  # Increased chunk size

        while time.time() - start_time < 10:
            chunk = req.read(chunk_size)
            if not chunk:
                break
            total_bytes += len(chunk)

            current_time = time.time()
            if current_time - last_print >= 1:  # Update every second
                elapsed = current_time - start_time
                speed = (total_bytes / elapsed) / 1024  # KB/s
                print(f"\rCurrent Speed: {speed:.2f} KB/s", end="", flush=True)
                last_print = current_time

        print("\nTest completed.")

    except Exception as e:
        print(f"\nError occurred: {e}")


def parse_args():
    """Parses the command line arguments."""
    p = argparse.ArgumentParser(description="Client for vpngate.net VPNs")
    p.add_argument("--country", "-c", action="append",
                   help="A 2 char country code (e.g. CA for Canada) from " +
                        "which to look for a VPNs. If specified multiple " +
                        "times, VPNs from all the countries will be selected.")
    p.add_argument("--eu", action="store_true",
                   help="Adds European countries to the list of considerable" +
                        " countries")
    p.add_argument("--iptables", "-i", action="store_true",
                   help="Set iptables rules that block non-VPN traffic. " +
                        "WARNING: This option messes IPv6 iptables up!")
    p.add_argument("--probes", action="store", default=100, type=int,
                   help="Number of concurrent connection probes to send.")
    p.add_argument("--probe-timeout", action="store", default=1500, type=int,
                   help="When probing, how long to wait for " +
                        "connection until marking the VPN as unavailable " +
                        "(milliseconds)")
    p.add_argument("--url", action="store", default=VPN_LIST_URL,
                   help="URL of the VPN list (csv)")
    p.add_argument("--us", action="store_true",
                   help="Adds United States to the list of possible " +
                        "countries. Shorthand or --country US")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="More verbose output")
    p.add_argument("--vpn-timeout", action="store", default=10, type=int,
                   help="Time to wait for a VPN to be established " +
                        "before giving up (seconds).")
    p.add_argument("--vpn-timeout-poll-interval", action="store", default=0.1, type=int,
                   help="Time between two checks for a potential timeout (seconds)")
    p.add_argument("ovpnfile", type=argparse.FileType('rb'), default=None,
                   nargs="?",
                   help="Connects to the OpenVPN VPN whose configuration is " +
                        "in the provided .ovpn file")
    p.add_argument("--expired-time",  action="store", default=DEFAULT_EXPIRED_TIME, type=int,
                   help="Time to wait for a ServersList to be expired")
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
        indexNum = indexNum+1
        print(
            "\033[90m-----------------------------------------------------------+\33[0m")
        print("\033[32m%d\033[0m/\033[32m%d\033[0m %s\033[0m\033[90m" %
              (indexNum, total, vpn))
        try:
            res = vpn.connect()
        except KeyboardInterrupt:
            break

        # The user was happy with this VPN, break the loop.
        if res:
            break
        else:
            continue

    logger.info("\033[31mExiting...\033[0m")


def main(args):
    if args.ovpnfile:
        # Load a single VPN from the given file.
        return single_vpn_main(args)
    else:
        # Load list and try them in order
        return vpn_list_main(args)


def isAdmin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


if __name__ == "__main__":
    if isAdmin():
        args = parse_args()

        if args.verbose:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

        sys.exit(main(args))
    else:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, __file__, None, 1)

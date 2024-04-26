import subprocess


class OsProcess:
    def __init__(self):
        pass

    @staticmethod
    def execute(command):
        pipe = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
        out = pipe.stdout
        err = pipe.stderr
        out_str = out.read().decode()
        err_str = ""
        if err is not None:
            err_str = err.read().decode()
        result = {"stdout": out_str, "stderr": err_str}
        out.close()
        if err is not None:
            err.close()
        return result

    @staticmethod
    def get_output(command):
        return OsProcess.execute(command)["stdout"]

    @staticmethod
    def get_ip_address(interface="wlan0"):
        command = f"/usr/sbin/ifconfig {interface} | grep inet | head -n 1 | cut -d ' ' -f 10"
        return OsProcess.get_output(command)

import os, sys
import psutil
import asyncio
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
    ZI = True
except:
    ZI = False

log_dir = os.path.abspath(os.path.join(os.getcwd(), ".."))
log_file = os.path.join(log_dir, "ram.log")
os.makedirs(log_dir, exist_ok=True)

async def check_system_resources():

    # compute always here
    vmem = psutil.virtual_memory()
    total_ram = vmem.total

    if ZI:
        timestamp = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d-%m-%y:%H:%M:%S")
    else:
        timestamp = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%d-%m-%y:%H:%M:%S")

    if total_ram > 2 * 1024**3:
        print("Total RAM is more than 2GB. Stopping monitoring.")
        return False

    ram_usage = vmem.percent
    cpu_usage = psutil.cpu_percent(interval=None)

    message = (
        f"[{timestamp}] Total RAM: {total_ram / (1024**3):.2f} GB\n"
        f"[{timestamp}] RAM Usage: {ram_usage}%\n"
        f"[{timestamp}] CPU Usage: {cpu_usage}%"
    )

    # correct logical condition
    if (ram_usage >= 93 and cpu_usage >= 93) or (ram_usage >= 98 or cpu_usage >= 98):

        warning = f"[{timestamp}] High resource usage detected. Restarting process..."
        print(warning)
        try:
            with open(log_file, "a") as log:
                log.write(message + "\n\n")
                log.write(warning + "\n\n\n")
        except Exception:
            print(message + "\n")
            print(warning + "\n\n")

        os.execv(sys.executable, [sys.executable] + sys.argv)

    return True


async def monitor():
    while True:
        try:
            should_continue = await check_system_resources()
        except:
            should_continue = False

        if not should_continue:
            break

        await asyncio.sleep(5)

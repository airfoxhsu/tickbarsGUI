import os
import time
from datetime import datetime, timedelta

def cleanup_yuanta_logs(folder: str = ".", keep_days: int = 3):
    """
    清理 Yuanta API 自動產生的 log 檔案。
    預設只保留 keep_days 天內的檔案。
    
    參數：
    - folder: 日誌所在資料夾（預設當前路徑）。
    - keep_days: 要保留多少天內的 log。
    """

    now = time.time()
    keep_seconds = keep_days * 24 * 60 * 60

    for fname in os.listdir(folder):
        if not fname.lower().endswith(".log"):
            continue
        if not fname.startswith(("YuantaApiLog", "YuantaQuoteLog")):
            continue

        path = os.path.join(folder, fname)
        try:
            mtime = os.path.getmtime(path)
            if now - mtime > keep_seconds:
                print(f"🧹 刪除過期 API Log：{fname}")
                os.remove(path)
        except Exception as e:
            print(f"⚠️ 無法刪除 {fname}: {e}")


def clean_logs_folder():
    """
    清理 Logs/<日期>/ 底下的所有檔案，但保留 event.log。
    不刪除資料夾，不刪除 event.log。
    """

    base_path = os.getcwd()
    logs_path = os.path.join(base_path, "Logs")

    if not os.path.isdir(logs_path):
        print("⚠️ Logs 資料夾不存在，略過清理。")
        return

    # 遍歷 Logs 資料夾下所有子目錄
    for root, dirs, files in os.walk(logs_path):
        for fname in files:
            # 只保留 event.log
            if fname.lower() == "event.log":
                continue

            full_path = os.path.join(root, fname)
            try:
                os.remove(full_path)
                print(f"🗑️ 已刪除：{full_path}")
            except Exception as e:
                print(f"⚠️ 無法刪除 {full_path}: {e}")


def clean_logs_except_today():
    """
    清理 Logs/<日期>/ 底下的所有檔案，但：
    1. 不刪除今天的資料夾
    2. 所有資料夾中都保留 event.log
    """

    base_path = os.getcwd()
    logs_path = os.path.join(base_path, "Logs")

    if not os.path.isdir(logs_path):
        print("⚠️ Logs 資料夾不存在")
        return

    today_str = datetime.now().strftime("%Y%m%d")

    for folder in os.listdir(logs_path):
        folder_path = os.path.join(logs_path, folder)

        # 只處理資料夾
        if not os.path.isdir(folder_path):
            continue

        # ⚠️ 當天資料夾不刪除任何檔案
        if folder == today_str:
            # print(f"⏩ 略過今天的資料夾：{folder}")
            continue

        # 處理非當天資料夾
        for fname in os.listdir(folder_path):
            # 保留 event.log
            if fname.lower() == "event.log":
                continue

            full_path = os.path.join(folder_path, fname)
            if os.path.isfile(full_path):
                try:
                    os.remove(full_path)
                    print(f"🗑️ 已刪除：{full_path}")
                except Exception as e:
                    print(f"⚠️ 無法刪除 {full_path}: {e}")

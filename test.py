import queue
import threading

class MyClass:
    def __init__(self, name):
        self.name = name

    def worker(self, q):
        # 將當前實例放入隊列
        q.put(self)

# 創建一個隊列
q = queue.Queue()

# 創建 MyClass 的實例
my_instance = MyClass("Example")

# 創建一個線程
thread = threading.Thread(target=my_instance.worker, args=(q,))
thread.start()
thread.join()

# 從隊列中取出並使用實例
retrieved_instance = q.get()
print(retrieved_instance.name)  # 輸出: Example

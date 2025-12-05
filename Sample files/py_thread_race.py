import threading
counter = 0
def inc():
    global counter
    for _ in range(100000):
        counter += 1  # BUG: race without lock
t1 = threading.Thread(target=inc); t2 = threading.Thread(target=inc)
t1.start(); t2.start(); t1.join(); t2.join()
print('counter =', counter)  # not 200000
